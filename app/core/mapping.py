# app/core/mapping.py


CANONICAL_ROWS = {

    # ---------------- REVENUE ----------------

    "revenue": [
        "revenue",
        "revenue from operations",
        "income from operations",
        "sales",
        "net sales",
        "operating revenue"
    ],


    "other income": [
        "other income",
        "non operating income",
        "miscellaneous income"
    ],


    "total income": [
        "total income",
        "total revenue",
        "gross income"
    ],


    # ---------------- EXPENSES ----------------

    "cost of materials consumed": [
        "cost of materials",
        "raw material",
        "materials consumed",
        "cost of goods sold",
        "cogs"
    ],


    "employee benefits expense": [
        "employee benefits",
        "employee cost",
        "salary",
        "wages",
        "staff cost",
        "personnel expense"
    ],


    "depreciation and amortisation": [
        "depreciation",
        "amortisation",
        "depreciation and amortisation"
    ],


    "finance costs": [
        "finance cost",
        "finance costs",
        "interest expense",
        "borrowing cost",
        "interest cost"
    ],


    "other expenses": [
        "other expenses",
        "administrative expenses",
        "selling expenses",
        "distribution expenses",
        "operating expenses"
    ],


    "total expenses": [
        "total expenses",
        "total cost",
        "total expenditure"
    ],


    # ---------------- PROFIT ----------------

    "ebitda": [
        "ebitda",
        "operating profit",
        "operating income",
        "earnings before interest"
    ],


    "profit before tax": [
        "profit before tax",
        "pbt",
        "profit before taxation"
    ],


    "tax expense": [
        "tax",
        "tax expense",
        "provision for tax",
        "income tax"
    ],


    "net profit": [
        "net profit",
        "profit after tax",
        "pat",
        "net income",
        "profit for the year"
    ],


    "eps": [
        "earnings per share",
        "eps",
        "basic eps",
        "diluted eps"
    ]
}


# Rows we really care about
CORE_ROWS = list(CANONICAL_ROWS.keys())
