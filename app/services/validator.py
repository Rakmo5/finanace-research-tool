import re
from app.models.schema import FinancialData
from app.core.logger import logger


def clean_value(val):

    if val is None:
        return "MISSING"


    v = str(val).strip()


    # Remove commas
    v = v.replace(",", "")


    # Handle brackets ( (1234) => -1234 )
    if v.startswith("(") and v.endswith(")"):
        v = "-" + v[1:-1]


    # Remove currency
    v = re.sub(r"[₹$€]", "", v)


    # Remove junk chars
    v = re.sub(r"[A-Za-z]", "", v)


    # Normalize dash
    if v in ["-", "—", "–", ""]:
        return "MISSING"


    # Valid number
    if re.match(r"^-?\d+(\.\d+)?$", v):
        return v


    return "MISSING"



def normalize(raw):

    raw["years"] = [str(y) for y in raw.get("years", [])]


    for row in raw.get("rows", []):

        new_vals = {}


        for k, v in row.get("values", {}).items():

            new_vals[str(k)] = clean_value(v)


        row["values"] = new_vals


    return raw



def validate_data(raw):

    logger.info("Normalizing extracted data")

    raw = normalize(raw)


    logger.info("Validating schema")

    data = FinancialData(**raw)


    # Fill missing years
    for row in data.rows:

        for y in data.years:

            if y not in row.values:
                row.values[y] = "MISSING"


    return data
