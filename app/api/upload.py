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


# ---------------- CONFIG ----------------

CURRENT_YEAR = datetime.datetime.now().year


IMPORTANT_ROWS = [
    "revenue",
    "income",
    "expense",
    "profit",
    "tax",
    "loss",
    "earning",
    "eps",
    "depreciation",
    "finance",
    "interest",
    "cost",
    "margin",
    "comprehensive"
]


# ---------------- HELPERS ----------------
def is_valid_year(y: str) -> bool:

    y = y.upper().strip()

    # Year
    if re.match(r"^20\d{2}$", y):
        return True

    # Financial year
    if re.match(r"^20\d{2}-\d{2}$", y):
        return True

    # Quarter
    if re.match(r"^Q[1-4]$", y):
        return True

    # Month period
    if re.match(r"^\d+M$", y):
        return True

    # Date
    if re.match(r"^\d{2}/\d{2}/20\d{2}$", y):
        return True

    return False
def is_useful_row(name: str) -> bool:

    if not name:
        return False

    n = name.lower().strip()

    # Too short → junk
    if len(n) < 4:
        return False

    # Must contain at least one finance keyword
    KEYWORDS = [
        "revenue", "income", "expense", "profit", "loss", "tax",
        "margin", "cost", "depreciation", "amortisation",
        "ebitda", "interest", "segment", "asset", "debt",
        "equity", "dividend", "cash", "liability", "turnover"
    ]

    if not any(k in n for k in KEYWORDS):
        return False

    # Junk patterns
    JUNK = [
        "gate", "sofa", "pna", "sss", "atom", "reofsiutian"
    ]

    if any(j in n for j in JUNK):
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


            # Remove junk OCR rows
            if not is_useful_row(name):
                continue


            key = name.lower()


            if key not in row_map:

                row_map[key] = {
                    "name": name,
                    "values": {}
                }


            for year, val in r.get("values", {}).items():

                year = str(year).strip()

                if is_valid_year(year):

                    row_map[key]["values"][year] = val

# ---------- Limit to Last 7 Periods ----------

def sort_key(y):
    # Put real years first
    if y.isdigit():
        return int(y)

    # Handle dates like 31/12/2025
    if "/" in y:
        parts = y.split("/")
        return int(parts[-1])

    return 0


# Sort years properly
sorted_years = sorted(list(all_years), key=sort_key)

# Keep only last 7
if len(sorted_years) > 7:
    sorted_years = sorted_years[-7:]

logger.info(f"Using final years: {sorted_years}")

# Remove other years from rows
for row in row_map.values():

    filtered = {}

    for y in sorted_years:
        filtered[y] = row["values"].get(y, "MISSING")

    row["values"] = filtered

all_years = set(sorted_years)

    # ---------- Final Object ----------

    raw = {
        "currency": currency,
        "unit": unit,
        "years": sorted(list(all_years)),
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
