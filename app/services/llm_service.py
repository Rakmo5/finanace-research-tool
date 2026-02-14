# app/services/llm_service.py (replace parse_with_llm / filter / prompt parts)

import json, re
from groq import Groq
from app.core.config import GROQ_KEY, MAX_TEXT_LENGTH
from app.core.logger import logger

client = Groq(api_key=GROQ_KEY)

KEEP_KEYWORDS = [
    "revenue","income","profit","loss","tax","expense","cost","ebitda","depreciation",
    "interest","finance","employee","salary","wages","eps","earning","dividend"
]

def filter_financial_lines(text):
    """
    Keep lines that 1) contain a finance keyword OR 2) have >=4 digits
    Also collapse multi-spaces and strip page headers/footers heuristics.
    """
    lines = []
    for raw in text.splitlines():
        l = raw.strip()
        if not l:
            continue
        # remove likely footers/headers (page numbers)
        if re.match(r"^(page|pg|www|\d{1,3})\b", l.lower()):
            continue
        # keep if numeric heavy
        digits = sum(c.isdigit() for c in l)
        if digits >= 4:
            lines.append(" ".join(l.split()))
            continue
        # keep if contains finance keyword and at least one digit
        low = l.lower()
        if any(k in low for k in KEEP_KEYWORDS) and any(c.isdigit() for c in l):
            lines.append(" ".join(l.split()))
            continue
    return "\n".join(lines)


def extract_json(text):
    m = re.search(r"\{.*\}", text, re.DOTALL)
    return m.group() if m else None


def parse_with_llm(text, retry=True):
    logger.info("Preparing chunk for LLM")
    cleaned = filter_financial_lines(text)
    if not cleaned.strip():
        logger.warning("Chunk empty after cleaning")
        return None

    # try to detect years heuristically
    periods = list(dict.fromkeys(re.findall(r"(20\d{2}|Q[1-4]|\d+M|\d{2}/\d{2}/20\d{2})", text)))

    prompt = f"""
You are a conservative financial analytics assistant. Extract an income-statement-like table from the text.
Return STRICT JSON only (no explanation). If uncertain, use "MISSING".
Schema:
{{
 "currency":"",
 "unit":"",
 "years":[],
 "rows":[{{"name":"","values":{{}},"source_sample":""}}]
}}

Rules (be strict):
- Do NOT invent numbers. Only return numbers/strings exactly present in the provided text.
- Years must be strings.
- Values must be strings.
- If a value cannot be located exactly, use "MISSING".
- Limit rows to income-statement lines (revenue, other income, cogs, expenses, finance costs, depreciation, pbt, tax, pat, eps).
- Use the provided 'DetectedPeriods' list if helpful.

DetectedPeriods: {periods}

TEXT:
{cleaned[:MAX_TEXT_LENGTH]}
"""

    res = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role":"system","content":"You must output valid JSON only."},
            {"role":"user","content":prompt}
        ],
        temperature=0
    )

    content = res.choices[0].message.content.strip()
    logger.info("LLM raw output preview: " + content[:400])

    # try parse
    try:
        return json.loads(content)
    except Exception:
        logger.warning("LLM JSON parse failed, extracting braces")
        extracted = extract_json(content)
        if extracted:
            try:
                return json.loads(extracted)
            except Exception:
                logger.error("Extraction parse failed")
    # retry once
    if retry:
        logger.warning("Retrying LLM once (more conservative)")
        return parse_with_llm(text, retry=False)

    return {"currency":"UNKNOWN","unit":"UNKNOWN","years":[],"rows":[]}
