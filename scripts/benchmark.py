"""Small load test: sends N POST /transactions requests with C concurrent clients and reports latency.

Usage: python scripts/benchmark.py --url http://localhost:8000 --requests 2000 --concurrency 20
"""
import argparse
import asyncio
import statistics
import time
import uuid

import httpx


async def worker(client, url, queue, latencies, errors):
    while True:
        try:
            queue.get_nowait()
        except asyncio.QueueEmpty:
            return
        body = {
            "sender_account": "ACC-1",
            "receiver_account": "ACC-2",
            "amount": "10.00",
            "currency": "GBP",
            "reference_id": str(uuid.uuid4()),
        }
        start = time.perf_counter()
        r = await client.post(f"{url}/transactions", json=body)
        latencies.append((time.perf_counter() - start) * 1000)
        if r.status_code != 201:
            errors.append(r.status_code)


async def main(url, total, concurrency):
    queue = asyncio.Queue()
    for i in range(total):
        queue.put_nowait(i)
    latencies, errors = [], []
    limits = httpx.Limits(max_connections=concurrency)
    async with httpx.AsyncClient(limits=limits, timeout=30) as client:
        start = time.perf_counter()
        await asyncio.gather(*(worker(client, url, queue, latencies, errors) for _ in range(concurrency)))
        elapsed = time.perf_counter() - start
    latencies.sort()
    pct = lambda p: latencies[min(len(latencies) - 1, int(len(latencies) * p))]
    print(f"requests={total} concurrency={concurrency} errors={len(errors)}")
    print(f"throughput={total / elapsed:.0f} req/s")
    print(f"latency_ms p50={statistics.median(latencies):.1f} p95={pct(0.95):.1f} p99={pct(0.99):.1f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8000")
    ap.add_argument("--requests", type=int, default=2000)
    ap.add_argument("--concurrency", type=int, default=20)
    a = ap.parse_args()
    asyncio.run(main(a.url, a.requests, a.concurrency))
