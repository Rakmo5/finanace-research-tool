from fastapi import APIRouter, UploadFile, File
import uuid
import os
import re
import datetime

from app.core.config import UPLOAD_DIR, OUTPUT_DIR
from app.core.logger import logger

from app.services.pdf_service import extract_text
from app.services.table_service import extract_tables
from app.services.llm_service import parse_with_llm
from app.services.validator import validate_data
from app.services.excel_service import export_excel


router = APIRouter()

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

CURRENT_YEAR = datetime.datetime.now().year


# ---------------- YEAR NORMALIZER ----------------

def normalize_year(y: str):

    y = y.strip()

    if "/" in y:
        parts = y.split("/")
        if len(parts) == 3:
            y = parts[-1]

    if re.match(r"^20\d{2}-\d{2}$", y):
        base = int(y[:4])
        y = str(base + 1)

    if re.match(r"^Q[1-4]\s*20\d{2}$", y.upper()):
        y = y[-4:]

    if re.match(r"^20\d{2}$", y):

        iy = int(y)

        if 2010 <= iy <= CURRENT_YEAR + 1:
            return y

    return None


# ---------------- ROW FILTER ----------------

def is_useful_row(name: str):

    if not name:
        return False

    n = name.lower().strip()

    if len(n) < 4:
        return False

    KEYWORDS = [
        "revenue", "income", "expense", "profit", "loss", "tax",
        "margin", "cost", "depreciation", "amortisation",
        "ebitda", "interest", "segment", "asset", "debt",
        "equity", "dividend", "cash", "turnover"
    ]

    if not any(k in n for k in KEYWORDS):
        return False

    JUNK = ["gate", "sofa", "pna", "sss", "atom", "reofsiutian"]

    if any(j in n for j in JUNK):
        return False

    return True


# ---------------- API ----------------

@router.post("/upload")
async def upload(file: UploadFile = File(...)):

    logger.info("Upload started")

    file_id = str(uuid.uuid4())

    pdf_path = f"{UPLOAD_DIR}/{file_id}.pdf"

    with open(pdf_path, "wb") as f:
        f.write(await file.read())

    logger.info("File saved")


    # ---------- Extract Text ----------

    tables = extract_tables(pdf_path)

    text = ""


    if tables:

        logger.info("Using Camelot tables")

        for df in tables:
            text += df.to_csv(index=False)
            text += "\n\n"

    else:

        logger.info("Using OCR/Text")

        chunks = extract_text(pdf_path)

        if chunks:
            text = "\n\n".join(chunks)


    if not text.strip():

        return {
            "status": "error",
            "message": "No content extracted"
        }


    # ---------- Chunk ----------

    MAX_CHUNK = 3500

    chunks = [
        text[i:i + MAX_CHUNK]
        for i in range(0, len(text), MAX_CHUNK)
    ]


    # ---------- Aggregate ----------

    row_map = {}
    all_years = set()

    currency = "UNKNOWN"
    unit = "UNKNOWN"


    for i, chunk in enumerate(chunks):

        if len(chunk.strip()) < 200:
            continue

        logger.info(f"Processing chunk {i+1}/{len(chunks)}")

        result = parse_with_llm(chunk)

        if not result:
            continue


        currency = result.get("currency", currency)
        unit = result.get("unit", unit)


        # Years
        for y in result.get("years", []):

            ny = normalize_year(str(y))

            if ny:
                all_years.add(ny)


        # Rows
        for r in result.get("rows", []):

            name = r.get("name", "").strip()

            if not is_useful_row(name):
                continue


            key = name.lower()


            if key not in row_map:

                row_map[key] = {
                    "name": name,
                    "values": {}
                }


            for y, v in r.get("values", {}).items():

                ny = normalize_year(str(y))

                if ny:
                    row_map[key]["values"][ny] = v


    # ---------- Limit to Last 7 Years ----------

    sorted_years = sorted(all_years)

    if len(sorted_years) > 7:
        sorted_years = sorted_years[-7:]


    logger.info(f"Final years: {sorted_years}")


    for row in row_map.values():

        filtered = {}

        for y in sorted_years:
            filtered[y] = row["values"].get(y, "MISSING")

        row["values"] = filtered


    all_years = set(sorted_years)


    # ---------- Remove Empty Rows ----------

    clean_rows = {}

    for k, row in row_map.items():

        if any(v != "MISSING" for v in row["values"].values()):
            clean_rows[k] = row


    row_map = clean_rows


    # ---------- Final ----------

    raw = {
        "currency": currency,
        "unit": unit,
        "years": sorted(list(all_years)),
        "rows": list(row_map.values())
    }


    data = validate_data(raw)

    excel_path = export_excel(data, file_id)


    return {
        "status": "success",
        "file_id": file_id,
        "currency": data.currency,
        "unit": data.unit,
        "years": data.years,
        "rows": data.rows,
        "download": f"/outputs/{file_id}.xlsx"
    }
