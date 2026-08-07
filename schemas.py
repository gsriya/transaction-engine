from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class TransactionCreate(BaseModel):
    sender_account: str = Field(..., min_length=1)
    receiver_account: str = Field(..., min_length=1)
    amount: float = Field(..., gt=0)
    currency: str = Field(default="USD")
    description: Optional[str] = None
    reference_id: Optional[str] = None

class TransactionResponse(BaseModel):
    id: str
    sender_account: str
    receiver_account: str
    amount: float
    currency: str
    status: str
    created_at: datetime
    description: Optional[str] = None

    class Config:
        from_attributes = True
        