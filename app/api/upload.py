from fastapi import APIRouter, UploadFile, File
import uuid
import os
import re

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


# ---------------- FILTER CONFIG ----------------

CORE_KEYWORDS = [
    "revenue",
    "income",
    "expense",
    "cost",
    "depreciation",
    "amortisation",
    "finance",
    "interest",
    "ebitda",
    "profit",
    "tax",
    "eps",
    "earning",
    "margin"
]


CASHFLOW_WORDS = [
    "repayment",
    "lease liability",
    "cash equivalent",
    "interest paid",
    "dividend paid",
    "net cash",
    "operating activities",
    "investing activities",
    "financing activities"
]


JUNK_WORDS = [
    "gate", "sofa", "pna", "sss", "atom", "reofsiutian"
]


# ---------------- HELPERS ----------------

def is_valid_year(y: str) -> bool:

    y = y.strip()

    # 2024
    if re.match(r"^20\d{2}$", y):
        return True

    # 31/12/2025
    if re.match(r"^\d{2}/\d{2}/20\d{2}$", y):
        return True

    return False


def sort_year(y):

    if y.isdigit():
        return int(y)

    if "/" in y:
        return int(y.split("/")[-1])

    return 0


def is_useful_row(name: str) -> bool:

    if not name:
        return False


    n = name.lower().strip()


    # Too short = OCR junk
    if len(n) < 5:
        return False


    # ---------- Must contain core keyword ----------

    CORE = [
        "revenue",
        "income",
        "expense",
        "cost",
        "depreciation",
        "amortisation",
        "finance",
        "interest",
        "ebitda",
        "profit",
        "tax",
        "earning",
        "eps",
        "margin"
    ]

    if not any(k in n for k in CORE):
        return False


    # ---------- Remove footnotes / adjustments ----------

    BLOCK = [
        "allowance",
        "gain on",
        "loss on",
        "merger",
        "disposal",
        "exceptional",
        "adjustment",
        "share of",
        "non controlling",
        "minority",
        "segment",
        "reclassified",
        "write down",
        "impairment",
        "provision",
        "fair value",
        "derivative",
        "lease charge",
        "one time",
        "extraordinary"
    ]

    if any(b in n for b in BLOCK):
        return False


    # ---------- Remove balance-sheet items ----------

    BALANCE_SHEET = [
        "asset",
        "liability",
        "equity",
        "borrowings",
        "receivable",
        "payable",
        "inventory",
        "capital",
        "goodwill"
    ]

    if any(b in n for b in BALANCE_SHEET):
        return False


    return True



# ---------------- API ----------------

@router.post("/upload")
async def upload(file: UploadFile = File(...)):

    logger.info("Upload started")

    file_id = str(uuid.uuid4())

    pdf_path = f"{UPLOAD_DIR}/{file_id}.pdf"

    logger.info(f"Saving file: {file.filename}")

    with open(pdf_path, "wb") as f:
        f.write(await file.read())

    logger.info("File saved")


    # ---------- Try Table Extraction ----------

    tables = extract_tables(pdf_path)

    text = ""


    if tables:

        logger.info("Using Camelot extracted tables")

        for df in tables:
            text += df.to_csv(index=False)
            text += "\n\n"


    # ---------- OCR / Native Fallback ----------

    else:

        logger.info("No tables found. Using OCR/Text extraction")

        chunks = extract_text(pdf_path)

        if chunks:
            text = "\n\n".join(chunks)


    if not text.strip():

        logger.error("No usable text extracted")

        return {
            "status": "error",
            "message": "Could not extract content from PDF"
        }


    logger.info(f"Total extracted text length: {len(text)}")


    # ---------- Chunk for LLM ----------

    MAX_CHUNK = 3500

    chunks = [
        text[i:i + MAX_CHUNK]
        for i in range(0, len(text), MAX_CHUNK)
    ]

    logger.info(f"Split into {len(chunks)} LLM chunks")


    # ---------- Aggregate Results ----------

    row_map = {}
    all_years = set()

    currency = "UNKNOWN"
    unit = "UNKNOWN"


    for i, chunk in enumerate(chunks):

        if len(chunk.strip()) < 200:
            continue

        logger.info(f"Processing LLM chunk {i+1}/{len(chunks)}")

        result = parse_with_llm(chunk)

        if not result:
            continue


        # -------- Metadata --------

        currency = result.get("currency", currency)
        unit = result.get("unit", unit)


        # -------- Years --------

        for y in result.get("years", []):

            y = str(y).strip()

            if is_valid_year(y):
                all_years.add(y)


        # -------- Rows --------

        for r in result.get("rows", []):

            name = r.get("name", "").strip()

            if not name:
                continue


            lname = name.lower()


            # Remove cashflow rows
            if any(w in lname for w in CASHFLOW_WORDS):
                continue


            # Keep only income-statement rows
            if not is_useful_row(name):
                continue


            key = lname


            if key not in row_map:

                row_map[key] = {
                    "name": name,
                    "values": {}
                }


            for year, val in r.get("values", {}).items():

                year = str(year).strip()

                if is_valid_year(year):

                    row_map[key]["values"][year] = val


    # ---------- Limit to Last 7 Years ----------

    sorted_years = sorted(list(all_years), key=sort_year)

    if len(sorted_years) > 7:
        sorted_years = sorted_years[-7:]


    logger.info(f"Final years used: {sorted_years}")


    # ---------- Filter Row Values ----------

    for row in row_map.values():

        filtered = {}

        for y in sorted_years:
            filtered[y] = row["values"].get(y, "MISSING")

        row["values"] = filtered


    all_years = set(sorted_years)


    # ---------- Remove Empty Rows ----------

    cleaned_rows = []

    for row in row_map.values():

        if any(v != "MISSING" for v in row["values"].values()):
            cleaned_rows.append(row)


    row_map = {
        r["name"].lower(): r for r in cleaned_rows
    }


    # ---------- Final Object ----------

    raw = {
        "currency": currency,
        "unit": unit,
        "years": sorted(list(all_years), key=sort_year),
        "rows": list(row_map.values())
    }


    logger.info("Validating extracted data")

    data = validate_data(raw)


    # ---------- Export Excel ----------

    excel_path = export_excel(data, file_id)

    logger.info("Excel generated successfully")


    return {
        "status": "success",
        "file_id": file_id,
        "currency": data.currency,
        "unit": data.unit,
        "years": data.years,
        "rows": data.rows,
        "download": f"/outputs/{file_id}.xlsx"
    }
