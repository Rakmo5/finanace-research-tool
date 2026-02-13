from fastapi import APIRouter, UploadFile, File
import uuid
import os
import re
import datetime

from app.core.config import UPLOAD_DIR, OUTPUT_DIR
from app.core.logger import logger

from app.services.pdf_service import extract_text
from app.services.llm_service import parse_with_llm
from app.services.validator import validate_data
from app.services.excel_service import export_excel
from app.services.rule_extractor import extract_core_rows


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


    # -------- Extract Text --------

    chunks = extract_text(pdf_path)

    if not chunks:

        return {
            "status": "error",
            "message": "No text extracted"
        }


    full_text = "\n\n".join(chunks)

    logger.info(f"Text length: {len(full_text)}")


    # -------- Chunk for LLM --------

    MAX_CHUNK = 3500

    llm_chunks = [
        full_text[i:i+MAX_CHUNK]
        for i in range(0, len(full_text), MAX_CHUNK)
    ]


    # -------- Rule Extract --------

    rule_data = extract_core_rows(full_text)


    # -------- Aggregation --------

    row_map = {}
    all_years = set()

    currency = "UNKNOWN"
    unit = "UNKNOWN"


    # -------- LLM Pass --------

    for i, chunk in enumerate(llm_chunks):

        if len(chunk.strip()) < 200:
            continue

        logger.info(f"LLM chunk {i+1}/{len(llm_chunks)}")

        result = parse_with_llm(chunk)

        if not result:
            continue


        currency = result.get("currency", currency)
        unit = result.get("unit", unit)


        # Years
        for y in result.get("years", []):

            y = str(y).strip()

            if re.search(r"\d{4}", y):
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

                row_map[key]["values"][str(year)] = val


    # -------- Merge Rule Rows --------

    for cname, values in rule_data.items():

        key = cname.lower()

        if key not in row_map:

            row_map[key] = {
                "name": cname,
                "values": {}
            }


        for i, y in enumerate(sorted(all_years)):

            if i < len(values):

                if y not in row_map[key]["values"]:

                    row_map[key]["values"][y] = values[i]


    # -------- Final Object --------

    raw = {
        "currency": currency,
        "unit": unit,
        "years": sorted(list(all_years)),
        "rows": list(row_map.values())
    }


    data = validate_data(raw)


    # -------- Export --------

    export_excel(data, file_id)


    return {
        "status": "success",
        "file_id": file_id,
        "currency": data.currency,
        "unit": data.unit,
        "years": data.years,
        "rows": data.rows,
        "download": f"/outputs/{file_id}.xlsx"
    }
