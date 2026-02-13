import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import tempfile
import os
import cv2
import numpy as np

from app.core.logger import logger


# ---- HARD SET TESSERACT PATH ----
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


# ---------------- Check if PDF has real text ----------------

def is_text_pdf(path: str) -> bool:
    try:
        doc = fitz.open(path)

        for page in doc:
            text = page.get_text().strip()
            if len(text) > 100:
                return True

        return False

    except Exception as e:
        logger.warning(f"PDF text check failed: {e}")
        return False


# ---------------- Native Text Extraction ----------------

def extract_text_native(path):

    logger.info("Using native PDF text extraction")

    chunks = []

    doc = fitz.open(path)

    for i, page in enumerate(doc):

        text = page.get_text()

        if text and len(text.strip()) > 50:
            chunks.append(text)
            logger.info(f"Extracted native text from page {i+1}")

    return chunks


# ---------------- OCR Extraction ----------------

def extract_text_ocr(path):

    logger.info("Using OCR extraction")

    chunks = []

    doc = fitz.open(path)

    with tempfile.TemporaryDirectory() as tmpdir:

        for i, page in enumerate(doc):

            # Render page to high-quality image
            pix = page.get_pixmap(dpi=400)

            img_path = os.path.join(tmpdir, f"page_{i}.png")
            pix.save(img_path)

            # Load image
            img = cv2.imread(img_path)

            if img is None:
                continue

            # Convert to grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            # Improve contrast
            gray = cv2.equalizeHist(gray)

            # Remove noise
            gray = cv2.medianBlur(gray, 3)

            # Adaptive threshold for table clarity
            thresh = cv2.adaptiveThreshold(
                gray,
                255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                31,
                2
            )

            processed = Image.fromarray(thresh)

            custom_config = r"""
            --oem 3
            --psm 6
            -c preserve_interword_spaces=1
            """

            text = pytesseract.image_to_string(
                processed,
                lang="eng",
                config=custom_config
            )

            if text and len(text.strip()) > 50:
                chunks.append(text)
                logger.info(f"OCR extracted text from page {i+1}")

    return chunks


# ---------------- Hybrid Extractor ----------------

def extract_text(path):

    logger.info("Starting hybrid PDF extraction")

    # Case 1: Text PDF
    if is_text_pdf(path):

        logger.info("Detected text-based PDF")

        chunks = extract_text_native(path)

        if chunks:
            return chunks

        logger.warning("Native extraction empty. Falling back to OCR...")

    # Case 2: Scanned PDF
    logger.info("Using OCR fallback")

    chunks = extract_text_ocr(path)

    if not chunks:
        logger.error("OCR failed to extract text")
        return []

    return chunks
