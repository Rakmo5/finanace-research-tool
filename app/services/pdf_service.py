import fitz
import pytesseract
from PIL import Image
import io

from app.core.logger import logger


# Windows path (change if needed)
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def extract_text(path):

    logger.info("Starting Hybrid PDF extraction")

    doc = fitz.open(path)

    chunks = []   # ✅ store page-wise text

    # ---------- Try Native Text ----------
    for page in doc:

        t = page.get_text("text")

        if t and len(t.strip()) > 50:
            chunks.append(t.strip())


    # If native worked → return
    if len(chunks) >= len(doc) // 2:

        logger.info("Using native extraction")

        doc.close()
        return chunks


    # ---------- OCR Fallback ----------
    logger.warning("Native extraction failed. Using OCR...")


    chunks = []  # reset

    for i, page in enumerate(doc):

        pix = page.get_pixmap(dpi=300)

        img = Image.open(io.BytesIO(pix.tobytes("png")))

        ocr_text = pytesseract.image_to_string(
            img,
            lang="eng",
            config="--psm 6"
        )

        if ocr_text and len(ocr_text.strip()) > 50:
            chunks.append(ocr_text.strip())

        logger.info(f"OCR processed page {i+1}")

    doc.close()

    logger.info("OCR extraction complete")

    return chunks
