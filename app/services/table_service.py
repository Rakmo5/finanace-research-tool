import camelot
import fitz

from app.core.logger import logger


# ---------------- Quick Text Check ----------------

def has_text_first_pages(path, max_pages=2):

    doc = fitz.open(path)

    pages = min(len(doc), max_pages)

    for i in range(pages):

        txt = doc[i].get_text().strip()

        if len(txt) > 100:
            return True

    return False


# ---------------- Table Extractor ----------------

def extract_tables(pdf_path):

    # Quick reject: no text → skip Camelot
    if not has_text_first_pages(pdf_path):

        logger.info("PDF likely scanned. Skipping Camelot.")

        return []


    logger.info("Trying Camelot table extraction")

    try:

        # Only try first 3 pages
        tables = camelot.read_pdf(
            pdf_path,
            pages="1-3",
            flavor="stream"
        )

        if tables.n == 0:

            logger.info("Camelot found no tables")

            return []


        logger.info(f"Camelot found {tables.n} tables")

        return [t.df for t in tables]


    except Exception as e:

        logger.warning(f"Camelot failed: {e}")

        return []
