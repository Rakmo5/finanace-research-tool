# app/services/validator.py

import datetime, re
from app.models.schema import FinancialData
from app.core.logger import logger

def is_future_year(y):
    y = str(y).strip()
    # 2026 or 31/12/2026 etc.
    m = re.search(r"(20\d{2})", y)
    if m:
        year = int(m.group(1))
        return year > datetime.datetime.now().year
    return False

def post_process(raw, max_periods=7):
    # convert years to strings and drop future years
    years = [str(y) for y in raw.get("years", []) if not is_future_year(y)]
    # dedupe/preserve order
    years = list(dict.fromkeys(years))

    # keep only last max_periods (by numeric year when possible)
    def key_fn(y):
        if y.isdigit():
            return int(y)
        if "/" in y:
            return int(y.split("/")[-1])
        if y.upper().startswith("Q"):
            # treat as current-year quarters (lowest priority)
            return datetime.datetime.now().year
        return 0

    years_sorted = sorted(years, key=key_fn)
    if len(years_sorted) > max_periods:
        years_sorted = years_sorted[-max_periods:]

    # rebuild rows: keep only rows with at least one non-MISSING value
    processed_rows = []
    for r in raw.get("rows", []):
        vals = {str(k): str(v) for k, v in r.get("values", {}).items() if str(k) in years_sorted}
        # count non-missing
        non_missing = sum(1 for v in vals.values() if v and v != "MISSING")
        if non_missing == 0:
            continue
        processed_rows.append({
            "name": r.get("name"),
            "values": {y: vals.get(y, "MISSING") for y in years_sorted}
        })

    return {
        "currency": raw.get("currency", "UNKNOWN"),
        "unit": raw.get("unit", "UNKNOWN"),
        "years": years_sorted,
        "rows": processed_rows
    }

def validate_data(raw):
    logger.info("Post-processing LLM output")
    cleaned = post_process(raw, max_periods=7)
    # Use pydantic schema to ensure shape
    data = FinancialData(**cleaned)
    # ensure each row has years keys
    for row in data.rows:
        for y in data.years:
            if y not in row.values:
                row.values[y] = "MISSING"
    return data
