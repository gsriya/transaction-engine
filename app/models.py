import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Numeric, String

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    sender_account = Column(String, nullable=False, index=True)
    receiver_account = Column(String, nullable=False, index=True)
    # Money is stored as an exact decimal, never a float, so 0.10 + 0.20 is 0.30.
    amount = Column(Numeric(18, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="USD")
    status = Column(String, nullable=False, default="COMPLETED")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
    description = Column(String, nullable=True)
    # Optional client-supplied key: sending the same reference_id twice
    # returns the original transaction instead of creating a duplicate.
    reference_id = Column(String, nullable=True, unique=True)
