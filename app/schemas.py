from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class TransactionCreate(BaseModel):
    sender_account: str = Field(..., min_length=1, max_length=64)
    receiver_account: str = Field(..., min_length=1, max_length=64)
    amount: Decimal = Field(..., gt=0, max_digits=18, decimal_places=2)
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$", description="ISO 4217 code, e.g. GBP")
    description: Optional[str] = Field(default=None, max_length=255)
    reference_id: Optional[str] = Field(
        default=None, max_length=64, description="Idempotency key: repeats return the original transaction"
    )


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    sender_account: str
    receiver_account: str
    amount: Decimal
    currency: str
    status: str
    created_at: datetime
    description: Optional[str] = None
    reference_id: Optional[str] = None


class Stats(BaseModel):
    total_transactions: int
    total_volume: Decimal
    average_transaction: Decimal
    transactions_by_status: dict[str, int]
