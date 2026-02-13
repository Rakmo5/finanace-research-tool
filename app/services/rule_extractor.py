import re
from app.core.logger import logger


# Canonical financial rows we care about
CORE_ROWS = {
    "revenue from operations": ["revenue", "revenue from operations"],
    "total income": ["total income"],
    "total expenses": ["total expenses", "total expenditure"],
    "profit before tax": ["profit before tax", "pbt"],
    "profit after tax": ["profit after tax", "pat", "net profit"],
    "tax expense": ["tax expense", "income tax"]
}


def extract_core_rows(text):

    lines = text.split("\n")

    results = {}

    for line in lines:

        l = line.lower().strip()

        for canonical, variants in CORE_ROWS.items():

            if any(v in l for v in variants):

                # Extract numbers (incl negative/decimal)
                nums = re.findall(r"-?\d[\d,]*\.?\d*", line)

                if nums:

                    clean = [n.replace(",", "") for n in nums]

                    results[canonical] = clean

                    logger.info(f"Rule hit: {canonical} -> {clean}")

    return results
