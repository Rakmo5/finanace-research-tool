from pydantic import BaseModel
from typing import Dict, List


class FinancialRow(BaseModel):
    name: str
    values: Dict[str, str]


class FinancialData(BaseModel):
    currency: str
    unit: str
    years: List[str]
    rows: List[FinancialRow]
