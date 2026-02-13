import re
from app.models.schema import FinancialData
from app.core.logger import logger


def normalize(raw):

    raw["years"] = [str(y) for y in raw.get("years", [])]

    for row in raw.get("rows", []):

        new_vals = {}

        for k, v in row.get("values", {}).items():

            val = str(v).strip()

            # Remove currency symbols
            val = re.sub(r"[₹$€]", "", val)

            # Remove commas
            val = val.replace(",", "")

            # Empty
            if val in ["", "-", "—", "–"]:
                val = "MISSING"

            new_vals[str(k)] = val


        row["values"] = new_vals


    return raw



def validate_data(raw):

    logger.info("Normalizing")

    raw = normalize(raw)

    data = FinancialData(**raw)


    # Fill missing years
    for row in data.rows:

        for y in data.years:

            if y not in row.values:

                row.values[y] = "MISSING"


    return data
