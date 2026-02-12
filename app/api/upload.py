from fastapi import APIRouter, UploadFile, File
import uuid
import os

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


@router.post("/upload")
async def upload(file: UploadFile = File(...)):

    logger.info("Upload started")

    file_id = str(uuid.uuid4())
    pdf_path = f"{UPLOAD_DIR}/{file_id}.pdf"

    logger.info(f"Saving file: {file.filename}")

    with open(pdf_path, "wb") as f:
        f.write(await file.read())

    logger.info("File saved")


    # ---------- Try Table Extraction First ----------

    tables = extract_tables(pdf_path)

    text = ""


    if tables:

        logger.info("Using Camelot extracted tables")

        for df in tables:
            text += df.to_csv(index=False)
            text += "\n\n"


    # ---------- Fallback to OCR/Text ----------

    else:

        logger.info("No tables found. Using OCR extraction")

        chunks = extract_text(pdf_path)

        text = "\n\n".join(chunks)


    if not text.strip():

        logger.error("No usable text extracted")

        return {
            "status": "error",
            "message": "Could not extract content from PDF"
        }


    logger.info(f"Total extracted text length: {len(text)}")


    # ---------- Chunk Large Text for LLM ----------

    MAX_CHUNK = 3500

    chunks = [
        text[i:i+MAX_CHUNK]
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


        # Metadata
        currency = result.get("currency", currency)
        unit = result.get("unit", unit)


        # Years
        for y in result.get("years", []):
            all_years.add(str(y))


        # Merge rows
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
                row_map[key]["values"][str(year)] = val


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

