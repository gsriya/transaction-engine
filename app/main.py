from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import engine, get_db, Base
from app.models import Transaction
from app.schemas import TransactionCreate, TransactionResponse
import logging
from datetime import datetime

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Transaction Processing Engine",
    description="Production-grade API for processing financial transactions",
    version="1.0.0"
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.post("/transactions", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
def create_transaction(
    transaction: TransactionCreate,
    db: Session = Depends(get_db)
):
    if transaction.sender_account == transaction.receiver_account:
        logger.warning(f"Invalid transaction: sender same as receiver")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sender and receiver must be different"
        )
    
    db_transaction = Transaction(
        sender_account=transaction.sender_account,
        receiver_account=transaction.receiver_account,
        amount=transaction.amount,
        currency=transaction.currency,
        description=transaction.description,
        reference_id=transaction.reference_id,
        status="COMPLETED"
    )
    
    db.add(db_transaction)
    db.commit()
    db.refresh(db_transaction)
    
    logger.info(f"Transaction created: {db_transaction.id} for ${transaction.amount}")
    
    return db_transaction

@app.get("/transactions/{transaction_id}", response_model=TransactionResponse)
def get_transaction(
    transaction_id: str,
    db: Session = Depends(get_db)
):
    db_transaction = db.query(Transaction).filter(
        Transaction.id == transaction_id
    ).first()
    
    if not db_transaction:
        logger.warning(f"Transaction not found: {transaction_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction {transaction_id} not found"
        )
    
    return db_transaction

@app.get("/transactions", response_model=list[TransactionResponse])
def list_transactions(
    account: str = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    query = db.query(Transaction)
    
    if account:
        query = query.filter(
            (Transaction.sender_account == account) |
            (Transaction.receiver_account == account)
        )
    
    transactions = query.limit(limit).all()
    
    logger.info(f"Retrieved {len(transactions)} transactions")
    
    return transactions

@app.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    transactions = db.query(Transaction).all()
    
    if not transactions:
        return {
            "total_transactions": 0,
            "total_volume": 0,
            "average_transaction": 0
        }
    
    total_volume = sum(t.amount for t in transactions)
    
    return {
        "total_transactions": len(transactions),
        "total_volume": total_volume,
        "average_transaction": total_volume / len(transactions),
        "transactions_by_status": {
            "completed": len([t for t in transactions if t.status == "COMPLETED"]),
            "pending": len([t for t in transactions if t.status == "PENDING"]),
            "failed": len([t for t in transactions if t.status == "FAILED"])
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)