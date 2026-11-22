from pydantic import BaseModel, Field
from typing import Literal, Optional

class NormalizedTransaction(BaseModel):
    transaction_id: str
    date: str
    merchant: str
    description: str
    amount: float = Field(gt=0)
    currency: str = "INR"
    type: Literal["debit", "credit"]
    source: str
    category: str = "Other"
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    reason: str = ""
    needs_review: bool = False
    is_duplicate: bool = False
