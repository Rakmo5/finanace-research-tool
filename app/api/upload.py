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


# ---------------- HELPERS ----------------

def is_valid_year(y: str) -> bool:

    y = y.strip()

    if y.isdigit():
        return 2000 <= int(y) <= CURRENT_YEAR

    if "/" in y:
        try:
            return int(y.split("/")[-1]) <= CURRENT_YEAR
        except:
            return False

    return False


def remove_empty_rows(rows, years):

    clean = []

    for r in rows:

        if any(r["values"].get(y) != "MISSING" for y in years):
            clean.append(r)

    return clean


def sort_key(y):

    if y.isdigit():
        return int(y)

    if "/" in y:
        return int(y.split("/")[-1])

    return 0


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
            "message": "No readable content"
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


        logger.info(f"LLM chunk {i+1}/{len(chunks)}")

        result = parse_with_llm(chunk)

        if not result:
            continue


        currency = result.get("currency", currency)
        unit = result.get("unit", unit)


        # Years
        for y in result.get("years", []):

            y = str(y).strip()

            if is_valid_year(y):
                all_years.add(y)


        # Rows
        for r in result.get("rows", []):

            name = r.get("name", "").strip()

            if not name:
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


    # ---------- Keep Last 7 Years ----------

    sorted_years = sorted(list(all_years), key=sort_key)

    if len(sorted_years) > 7:
        sorted_years = sorted_years[-7:]


    logger.info(f"Final years: {sorted_years}")


    # ---------- Filter Row Values ----------

    for row in row_map.values():

        filtered = {}

        for y in sorted_years:
            filtered[y] = row["values"].get(y, "MISSING")

        row["values"] = filtered


    # ---------- Remove Empty Rows ----------

    rows = remove_empty_rows(
        list(row_map.values()),
        sorted_years
    )


    # ---------- Final Object ----------

    raw = {
        "currency": currency,
        "unit": unit,
        "years": sorted_years,
        "rows": rows
    }


    data = validate_data(raw)


    # ---------- Excel ----------

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
