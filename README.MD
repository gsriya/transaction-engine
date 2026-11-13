# Transaction API

[![CI](https://github.com/gsriya/transaction-engine/actions/workflows/ci.yml/badge.svg)](https://github.com/gsriya/transaction-engine/actions/workflows/ci.yml)

A small REST API for recording and querying financial transactions, built with **FastAPI**, **SQLAlchemy** and **PostgreSQL**.

The goal of this project is to get the basics of money-handling software right: exact decimal amounts, input validation, and making sure a retried request can never create a duplicate payment. It's a learning project, not a production payment system. The [limitations](#limitations-and-next-steps) section is honest about what it doesn't do.

## What it does

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Liveness check |
| `POST` | `/transactions` | Record a transaction (`201`), or return the original one (`200`) if the `reference_id` has been seen before |
| `GET` | `/transactions/{id}` | Fetch one transaction (`404` if it doesn't exist) |
| `GET` | `/transactions?account=&limit=&offset=` | List transactions, newest first, optionally for one account (as sender or receiver) |
| `GET` | `/stats` | Count, total volume, average amount, and count by status |

Interactive docs are served at `/docs` once the API is running.

Example request:

```bash
curl -X POST localhost:8000/transactions \
  -H "Content-Type: application/json" \
  -d '{"sender_account":"ACC-1","receiver_account":"ACC-2","amount":"25.50","currency":"GBP","reference_id":"order-1001"}'
```

## Design decisions

- **Money is never a float.** Amounts are `Decimal` in Python and `NUMERIC(18,2)` in PostgreSQL, so `0.10 + 0.20` is exactly `0.30`. There's a test for this.
- **Safe retries (idempotency).** Clients can send a `reference_id`. If the same request is retried (for example after a network timeout), the API returns the original transaction instead of creating a second one. A unique constraint in the database backs this up, so two identical requests racing each other still produce one row. A PostgreSQL test fires 20 concurrent copies of the same request and checks that exactly one transaction exists.
- **Validation at the edge.** Pydantic rejects non-positive amounts, more than 2 decimal places, invalid currency codes (must be 3 capital letters), and over-long fields. The API also rejects a sender equal to the receiver.
- **Aggregates run in the database.** `/stats` uses SQL `COUNT`, `SUM` and `GROUP BY` instead of loading every row into Python.
- **Bounded pagination.** `limit` is capped at 1000, so one request can't pull the whole table.
- **Indexes** on sender, receiver and created time for the account-filtered, newest-first listing.

## Run it

With Docker (API and PostgreSQL):

```bash
docker compose up --build
# API on http://localhost:8000, docs on http://localhost:8000/docs
```

Locally:

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env            # point DATABASE_URL at your PostgreSQL
uvicorn app.main:app --reload
```

## Tests

```bash
pytest -q                       # uses a temporary SQLite database
DATABASE_URL=postgresql+psycopg2://user:password@localhost:5432/transactions_db pytest -q
```

There are 9 tests covering creation and lookup, 404s, validation errors, idempotent retries, concurrent retries (PostgreSQL only), filtering and pagination limits, and exact decimal stats. GitHub Actions runs the suite against both SQLite and a real PostgreSQL 16 service container, and checks that the Docker image builds.

## Load test

`scripts/benchmark.py` sends `POST /transactions` requests from concurrent clients and reports throughput and latency percentiles.

```bash
python scripts/benchmark.py --url http://localhost:8000 --requests 2000 --concurrency 20
```

Measured result: 2,000 writes with 20 concurrent clients, repeated 3 times, gave **about 210–240 requests/s, p50 80–92 ms, p95 125–141 ms, and 0 errors**. The setup was one uvicorn worker and PostgreSQL 16 on a 2-vCPU Linux VM, with the load generator running on the same machine. After all runs, every stored `reference_id` was unique.

These numbers are a baseline for this small setup, not a capacity claim. The client, API and database were all competing for 2 CPUs.

## Project structure

```
app/
  main.py        # FastAPI routes
  models.py      # SQLAlchemy model
  schemas.py     # Pydantic request/response schemas
  database.py    # engine and session setup
tests/           # pytest suite
scripts/         # load-test script
Dockerfile
docker-compose.yml
.github/workflows/ci.yml
```

## Limitations and next steps

- **No account balances.** Transactions are recorded, but there's no balance table, so overdrafts aren't prevented. Next step: a balances table with row-level locking (`SELECT ... FOR UPDATE`) inside one database transaction.
- **Status is always `COMPLETED`.** There's no pending/failed lifecycle or reversal flow yet.
- **Tables are created on startup.** A real deployment should use migrations (Alembic).
- **No authentication or rate limiting.**
- **Single currency per transaction**, with no FX conversion.
