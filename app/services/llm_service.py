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

    return periods[:8]


def filter_financial_lines(text):

    lines = text.split("\n")

    keep = []

    keywords = [
        "revenue", "income", "expense", "profit", "tax",
        "ebitda", "total", "cost", "depreciation",
        "amortisation", "finance", "asset", "liability",
        "equity", "inventory", "cash", "debt", "eps"
    ]


    for line in lines:

        l = line.lower().strip()

        if len(l) < 5:
            continue


        # Keep keyword lines
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

def extract_income_section(text):

    text_lower = text.lower()

    start_keys = [
        "income statement",
        "statement of profit",
        "statement of profit and loss",
        "profit and loss",
        "p&l"
    ]

    end_keys = [
        "cash flow",
        "balance sheet",
        "notes",
        "assets",
        "liabilities"
    ]


    start = -1
    end = len(text)


    for k in start_keys:
        if k in text_lower:
            start = text_lower.find(k)
            break


    for k in end_keys:
        if k in text_lower:
            pos = text_lower.find(k)
            if pos != -1 and pos > start:
                end = pos
                break


    if start != -1:
        return text[start:end]

    return text

# ---------------- LLM Parser ----------------

def parse_with_llm(text, retry=True):

    logger.info("Cleaning chunk before sending to LLM")

    income_text = extract_income_section(text)
    # ✅ FIX: DEFINE cleaned_text
    cleaned_text = filter_financial_lines(income_text)


    if not cleaned_text.strip():

        logger.warning("Chunk empty after cleaning")

        return None


    periods = detect_periods(text)


    logger.info("Sending cleaned chunk to Groq LLM")


    prompt = f"""
You are a professional financial analyst.

Your task:
Extract ONLY Income Statement data.

Detected periods:
{periods}

Rules:
- DO NOT invent numbers
- DO NOT guess
- Use only provided text
- If value missing → "MISSING"
- No balance sheet
- No cashflow
- No ratios
- No notes
- No explanations

Return ONLY valid JSON.
No markdown.
No comments.

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

Text:
{cleaned_text[:MAX_TEXT_LENGTH]}
"""


    res = client.chat.completions.create(

        model="llama-3.1-8b-instant",

        messages=[
            {
                "role": "system",
                "content": "You output strict valid JSON only."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],

        temperature=0
    )


    content = res.choices[0].message.content.strip()


    logger.info("Raw LLM output (first 300 chars):")
    logger.info(content[:300])


    # ---------- Parse JSON ----------

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


    # ---------- Retry Once ----------

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
