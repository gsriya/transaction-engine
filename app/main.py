import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Response, status
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import Base, engine, get_db
from app.models import Transaction
from app.schemas import Stats, TransactionCreate, TransactionResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("transaction_api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Transaction API",
    description="A small REST API for recording and querying financial transactions on PostgreSQL.",
    version="1.1.0",
    lifespan=lifespan,
)


@app.get("/health")
def health_check():
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.post("/transactions", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
def create_transaction(transaction: TransactionCreate, response: Response, db: Session = Depends(get_db)):
    if transaction.sender_account == transaction.receiver_account:
        logger.warning("rejected transaction: sender equals receiver")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Sender and receiver must be different")

    # Idempotency: a retried request with the same reference_id must not create a second transaction.
    if transaction.reference_id:
        existing = db.query(Transaction).filter(Transaction.reference_id == transaction.reference_id).first()
        if existing:
            response.status_code = status.HTTP_200_OK
            return existing

    db_transaction = Transaction(**transaction.model_dump(), status="COMPLETED")
    db.add(db_transaction)
    try:
        db.commit()
    except IntegrityError:
        # Two identical requests raced past the check above; the unique constraint keeps only one.
        db.rollback()
        existing = db.query(Transaction).filter(Transaction.reference_id == transaction.reference_id).first()
        if existing is None:
            raise
        response.status_code = status.HTTP_200_OK
        return existing
    db.refresh(db_transaction)
    logger.info("transaction created id=%s amount=%s %s", db_transaction.id, transaction.amount, transaction.currency)
    return db_transaction


@app.get("/transactions/{transaction_id}", response_model=TransactionResponse)
def get_transaction(transaction_id: str, db: Session = Depends(get_db)):
    db_transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not db_transaction:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Transaction {transaction_id} not found")
    return db_transaction


@app.get("/transactions", response_model=list[TransactionResponse])
def list_transactions(
    account: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(Transaction)
    if account:
        query = query.filter(or_(Transaction.sender_account == account, Transaction.receiver_account == account))
    return query.order_by(Transaction.created_at.desc(), Transaction.id).offset(offset).limit(limit).all()


@app.get("/stats", response_model=Stats)
def get_stats(db: Session = Depends(get_db)):
    # Aggregates run inside the database instead of loading every row into memory.
    count, total = db.query(func.count(Transaction.id), func.coalesce(func.sum(Transaction.amount), 0)).one()
    by_status = dict(db.query(Transaction.status, func.count(Transaction.id)).group_by(Transaction.status).all())
    total = Decimal(total).quantize(Decimal("0.01"))
    average = (total / count).quantize(Decimal("0.01")) if count else Decimal("0.00")
    return Stats(
        total_transactions=count,
        total_volume=total,
        average_transaction=average,
        transactions_by_status={s.lower(): n for s, n in by_status.items()},
    )
