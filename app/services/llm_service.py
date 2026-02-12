from groq import Groq
import json
import re

from app.core.config import GROQ_KEY, MAX_TEXT_LENGTH
from app.core.logger import logger


client = Groq(api_key=GROQ_KEY)


# ---------------- CLEANER ----------------

def detect_periods(text):

    years = re.findall(r"(20\d{2})", text)

    dates = re.findall(r"\d{2}/\d{2}/\d{4}", text)

    periods = list(set(years + dates))

    return periods[:8]  # limit to avoid noise


def filter_financial_lines(text):

    lines = text.split("\n")

    keep = []

    keywords = [
        "revenue", "income", "expense", "profit", "tax",
        "ebitda", "total", "cost", "depreciation",
        "amortisation", "finance", "asset", "liability",
        "equity", "inventory", "cash", "debt"
    ]

    for line in lines:

        l = line.lower().strip()

        if len(l) < 5:
            continue

        # Keep financial keyword rows
        if any(k in l for k in keywords):
            keep.append(line)

        # Keep numeric-heavy rows
        elif sum(c.isdigit() for c in line) >= 6:
            keep.append(line)

    # Normalize spaces
    cleaned = []

    for l in keep:
        l = " ".join(l.split())
        cleaned.append(l)

    return "\n".join(cleaned)


# ---------------- JSON Extractor ----------------

def extract_json(text):

    match = re.search(r"\{.*\}", text, re.DOTALL)

    if match:
        return match.group()

    return None


# ---------------- LLM Parser ----------------

def parse_with_llm(text, retry=True):

    logger.info("Cleaning chunk before sending to LLM")

    cleaned_text = filter_financial_lines(text)
    periods = detect_periods(text)
    if not cleaned_text.strip():
        logger.warning("Chunk empty after cleaning")
        return None


    logger.info("Sending cleaned chunk to Groq LLM")

    prompt = f"""
You are a financial analyst.

Extract income statement data from this document chunk.

Detected periods: {periods}
Use these as columns when possible.

Return ONLY valid JSON.
NO explanation.
NO markdown.

Schema:
{{
 "currency":"",
 "unit":"",
 "years":[],
 "rows":[
   {{
    "name":"",
    "values":{{}}
   }}
 ]
}}

Rules:
- Do NOT invent numbers
- Extract ONLY from given text
- Use "MISSING" if not present
- Years must be strings
- Values must be strings

Text:
{cleaned_text[:MAX_TEXT_LENGTH]}
"""

    res = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": "You output strict financial JSON only."},
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )

    content = res.choices[0].message.content.strip()

    logger.info("Raw LLM output (first 300 chars):")
    logger.info(content[:300])


    # Try direct parse
    try:
        return json.loads(content)

    except Exception:

        logger.warning("Direct JSON parse failed. Trying extraction...")

        extracted = extract_json(content)

        if extracted:
            try:
                return json.loads(extracted)
            except Exception:
                pass


    # Retry once
    if retry:

        logger.warning("Retrying this chunk once...")

        return parse_with_llm(text, retry=False)


    logger.error("LLM failed on this chunk")

    return {
        "currency": "UNKNOWN",
        "unit": "UNKNOWN",
        "years": [],
        "rows": []
    }
