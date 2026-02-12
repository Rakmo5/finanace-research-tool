from app.models.schema import FinancialData
from app.core.logger import logger


def normalize(raw):

    # Convert years to strings
    raw["years"] = [str(y) for y in raw.get("years", [])]

    # Convert values to strings
    for row in raw.get("rows", []):

        new_vals = {}

        for k, v in row.get("values", {}).items():

            new_vals[str(k)] = str(v)

        row["values"] = new_vals

    return raw


def validate_data(raw):

    logger.info("Normalizing data")

    raw = normalize(raw)

    logger.info("Validating extracted data")

    data = FinancialData(**raw)

    # Fill missing years
    for row in data.rows:
        for y in data.years:
            if y not in row.values:
                row.values[y] = "MISSING"

    return data
