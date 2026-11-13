import os
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest


def make(client, **overrides):
    body = {"sender_account": "ACC-1", "receiver_account": "ACC-2", "amount": "10.00", "currency": "GBP"}
    body.update(overrides)
    return client.post("/transactions", json=body)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "healthy"


def test_create_and_fetch(client):
    r = make(client, description="rent")
    assert r.status_code == 201
    tx = r.json()
    assert tx["status"] == "COMPLETED" and Decimal(tx["amount"]) == Decimal("10.00")
    fetched = client.get(f"/transactions/{tx['id']}")
    assert fetched.status_code == 200 and fetched.json()["description"] == "rent"


def test_unknown_transaction_is_404(client):
    assert client.get("/transactions/does-not-exist").status_code == 404


def test_sender_cannot_equal_receiver(client):
    r = make(client, receiver_account="ACC-1")
    assert r.status_code == 400


def test_validation_rules(client):
    assert make(client, amount="0").status_code == 422  # must be positive
    assert make(client, amount="-5").status_code == 422
    assert make(client, amount="1.234").status_code == 422  # at most 2 decimal places
    assert make(client, currency="pounds").status_code == 422  # ISO 4217 code
    assert make(client, sender_account="").status_code == 422


def test_reference_id_makes_retries_safe(client):
    first = make(client, reference_id="order-42")
    retry = make(client, reference_id="order-42", amount="999.00")
    assert first.status_code == 201 and retry.status_code == 200
    assert retry.json()["id"] == first.json()["id"]
    assert Decimal(retry.json()["amount"]) == Decimal("10.00")  # the original, not the retry
    assert client.get("/stats").json()["total_transactions"] == 1


def test_list_filters_by_account_and_paginates(client):
    make(client, sender_account="A", receiver_account="B")
    make(client, sender_account="B", receiver_account="C")
    make(client, sender_account="C", receiver_account="D")
    assert len(client.get("/transactions", params={"account": "B"}).json()) == 2
    assert len(client.get("/transactions", params={"limit": 2}).json()) == 2
    assert len(client.get("/transactions", params={"limit": 2, "offset": 2}).json()) == 1
    assert client.get("/transactions", params={"limit": 0}).status_code == 422
    assert client.get("/transactions", params={"limit": 5000}).status_code == 422


def test_stats_are_exact(client):
    empty = client.get("/stats").json()
    assert empty["total_transactions"] == 0 and Decimal(empty["total_volume"]) == 0
    make(client, amount="0.10")
    make(client, amount="0.20")
    stats = client.get("/stats").json()
    # With floats this would be 0.30000000000000004; decimals keep money exact.
    assert Decimal(stats["total_volume"]) == Decimal("0.30")
    assert Decimal(stats["average_transaction"]) == Decimal("0.15")
    assert stats["transactions_by_status"] == {"completed": 2}


@pytest.mark.skipif(not os.environ["DATABASE_URL"].startswith("postgresql"), reason="needs PostgreSQL for real concurrency")
def test_concurrent_retries_create_one_transaction(client):
    payload = {"sender_account": "ACC-1", "receiver_account": "ACC-2", "amount": "25.00", "reference_id": "race-1"}

    def send(_):
        return client.post("/transactions", json=payload)

    with ThreadPoolExecutor(max_workers=10) as pool:
        responses = list(pool.map(send, range(20)))

    assert all(r.status_code in (200, 201) for r in responses)
    assert len({r.json()["id"] for r in responses}) == 1
    assert client.get("/stats").json()["total_transactions"] == 1
