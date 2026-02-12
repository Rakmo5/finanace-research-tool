import camelot
import pandas as pd

from app.core.logger import logger


def extract_tables(pdf_path):

    logger.info("Starting Camelot table extraction")

    tables = []

    try:
        # Try lattice first (best for bordered tables)
        t1 = camelot.read_pdf(pdf_path, pages="all", flavor="lattice")

        if t1 and len(t1) > 0:
            logger.info(f"Lattice extracted {len(t1)} tables")
            tables.extend(t1)

    except Exception as e:
        logger.warning(f"Lattice failed: {e}")


    try:
        # Fallback to stream (for borderless tables)
        t2 = camelot.read_pdf(pdf_path, pages="all", flavor="stream")

        if t2 and len(t2) > 0:
            logger.info(f"Stream extracted {len(t2)} tables")
            tables.extend(t2)

    except Exception as e:
        logger.warning(f"Stream failed: {e}")


    if not tables:
        logger.warning("No tables found via Camelot")


    # Convert to DataFrames
    dfs = []

    for i, table in enumerate(tables):

        df = table.df

        if len(df) > 2 and len(df.columns) > 2:
            dfs.append(df)
            logger.info(f"Accepted table {i+1}")


    return dfs
