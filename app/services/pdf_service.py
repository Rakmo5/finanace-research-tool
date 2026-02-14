# app/services/pdf_service.py
import fitz  # PyMuPDF
import re
import tempfile
import os
import cv2
from PIL import Image
import pytesseract
from app.core.logger import logger

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
# you likely already set pytesseract.pytesseract.tesseract_cmd elsewhere

INCOME_HEADINGS = [
    r"statement of profit and loss",
    r"consolidated statement of profit and loss",
    r"statement of profit \(and\) loss",
    r"income statement",
    r"profit and loss",
    r"statement of profit and loss",
    r"consolidated income",
    r"consolidated statement of profit",
]

SECTION_BREAKS = [
    r"balance sheet",
    r"statement of financial position",
    r"cash flow",
    r"statement of cash flows",
    r"notes to accounts",
    r"notes to the financial statements"
]

def _matches_any(text, patterns):
    t = text.lower()
    for p in patterns:
        if re.search(p, t):
            return True
    return False

def extract_income_section_text(path, max_pages_context=2):
    """
    Try to find the "Profit & Loss / Income Statement" section in the PDF and
    return the text for only that section (or nearby pages).
    If nothing found, return None so caller can fallback to full OCR.
    """
    logger.info("Searching for income-statement section in PDF")
    doc = fitz.open(path)

    # gather page-level text (native) first (fast)
    page_texts = []
    for p in doc:
        try:
            txt = p.get_text()
        except Exception:
            txt = ""
        page_texts.append(txt or "")

    # find candidate page indices where heading appears
    candidate_pages = []
    for i, txt in enumerate(page_texts):
        snippet = txt[:4000].lower()
        if _matches_any(snippet, INCOME_HEADINGS):
            candidate_pages.append(i)

    # If found, collect a few pages around each candidate until we hit SECTION_BREAKS
    if candidate_pages:
        blocks = []
        for pg in candidate_pages:
            start = max(0, pg - max_pages_context)
            # collect until next section break or +max_pages_context*3
            end = min(len(doc)-1, pg + max_pages_context + 3)
            # but if a page contains section break heading, stop earlier
            for j in range(pg+1, end+1):
                if _matches_any(page_texts[j] if j < len(page_texts) else "", SECTION_BREAKS):
                    end = j-1
                    break
            # join native text for these pages
            block_txt = "\n\n".join(page_texts[start:end+1])
            blocks.append(block_txt)
        # return the longest block (most content)
        best = max(blocks, key=lambda s: len(s))
        logger.info(f"Found income-statement around pages {candidate_pages}")
        return best

    logger.info("No income section via native text search")
    return None


# keep your OCR function but make it able to process only a few pages (for robustness)
def ocr_pages_from_pdf(path, page_indices=None, dpi=300):
    """
    Convert the provided page_indices to images and OCR them.
    If page_indices is None -> OCR entire doc.
    Returns list of page texts.
    """
    logger.info("Running OCR on selected pages")
    doc = fitz.open(path)
    texts = []

    with tempfile.TemporaryDirectory() as tmpdir:
        pages = range(len(doc)) if page_indices is None else page_indices
        for i in pages:
            page = doc[i]
            pix = page.get_pixmap(dpi=dpi)
            img_path = os.path.join(tmpdir, f"page_{i}.png")
            pix.save(img_path)

            img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
            if img is None:
                texts.append("")
                continue

            # quick preprocessing
            img = cv2.equalizeHist(img)
            img = cv2.medianBlur(img, 3)
            # adaptive threshold (improves table OCR often)
            thresh = cv2.adaptiveThreshold(img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                           cv2.THRESH_BINARY, 31, 2)
            processed = Image.fromarray(thresh)

            conf = r"--oem 3 --psm 6 -c preserve_interword_spaces=1"
            txt = pytesseract.image_to_string(processed, lang="eng", config=conf)
            texts.append(txt)

    return texts


def extract_text(path):
    """
    Hybrid extractor:
    - try to detect income section natively
    - if found, return that block (as single-element list)
    - else fall back to full native extraction; if native fails, do full OCR
    """
    logger.info("Starting hybrid extraction (income-aware)")

    # 1) try to find income section using native text
    income_block = extract_income_section_text(path)

    if income_block and len(income_block.strip()) > 100:
        logger.info("Returning income block (native)")
        return [income_block]

    # 2) fallback: try native extract of each page
    doc = fitz.open(path)
    native_pages = []
    for i, page in enumerate(doc):
        try:
            t = page.get_text()
        except Exception:
            t = ""
        native_pages.append(t or "")

    # if many pages have text, return them
    nonempty = [p for p in native_pages if p and len(p.strip()) > 50]
    if nonempty:
        logger.info("Returning native-extracted pages")
        return nonempty

    # 3) Final fallback: full OCR (slow)
    logger.info("Falling back to full OCR")
    return ocr_pages_from_pdf(path)
