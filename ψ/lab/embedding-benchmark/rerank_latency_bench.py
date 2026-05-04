"""
Reranker latency-under-load bench.

Measures p50/p95/p99 latency of POST /rerank under concurrent requests.
The reranker is a single-process FastAPI app — there's no model-level
concurrency. PyTorch serializes calls. So we expect:

  - p50 roughly stable across concurrency
  - p95/p99 grow with queue depth
  - throughput plateaus at the model's serial capacity

Operational question: at what concurrency does p95 cross our acceptable
threshold (say 1500ms — half the typical 3s search timeout budget)?

Run from arra-oracle-v3/services/reranker-py/:
    uv run --with 'aiohttp,numpy' python ~/Code/.../arra-mcp-installation-guide-oracle/ψ/lab/embedding-benchmark/rerank_latency_bench.py
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import List

import aiohttp
import numpy as np

URL = "http://127.0.0.1:8765/rerank"

# Realistic payload: query against 50 candidates (matches PR #1101 RERANK_POOL_SIZE).
# Texts are mock paraphrases of typical retrieval results — varied length.
QUERY = "การตรวจวัดคุณภาพอากาศด้วยเซ็นเซอร์เครือข่ายขนาดใหญ่"
CANDIDATES: List[str] = [
    f"Sample doc {i}. " + (
        "Air quality monitoring with PM2.5 sensors deployed across many stations. "
        "Real-time data feeding into a database for trend analysis and alerting. "
        if i % 3 == 0 else
        "การตรวจวัดคุณภาพอากาศด้วยเซ็นเซอร์ติดตามฝุ่น PM2.5 ทั่วประเทศ "
        "ส่งข้อมูลเข้าฐานข้อมูลแบบเรียลไทม์เพื่อแจ้งเตือน "
        if i % 3 == 1 else
        "Flood monitoring radar JIBCHAIN L1 blockchain ESP32 LoRa Meshtastic "
        "sensor mesh network for remote-area data relay without WiFi "
    ) for i in range(50)
]


async def one_request(session: aiohttp.ClientSession) -> tuple[bool, float]:
    t0 = time.perf_counter()
    try:
        async with session.post(URL, json={"query": QUERY, "candidates": CANDIDATES}, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            await resp.read()
            ok = resp.status == 200
    except Exception:
        ok = False
    return ok, (time.perf_counter() - t0) * 1000  # ms


async def run_load(concurrency: int, total: int) -> dict:
    """Fire `total` requests through `concurrency` workers."""
    sem = asyncio.Semaphore(concurrency)
    latencies: List[float] = []
    errors = 0
    wall_start = time.perf_counter()

    async with aiohttp.ClientSession() as session:
        async def bounded():
            nonlocal errors
            async with sem:
                ok, ms = await one_request(session)
                if ok:
                    latencies.append(ms)
                else:
                    errors += 1

        await asyncio.gather(*(bounded() for _ in range(total)))

    wall_ms = (time.perf_counter() - wall_start) * 1000

    if not latencies:
        return {"concurrency": concurrency, "total": total, "ok": 0, "errors": errors,
                "wall_ms": round(wall_ms), "p50": None, "p95": None, "p99": None,
                "rps": 0.0}

    arr = np.array(latencies)
    return {
        "concurrency": concurrency,
        "total": total,
        "ok": len(latencies),
        "errors": errors,
        "wall_ms": round(wall_ms),
        "p50_ms": round(float(np.percentile(arr, 50))),
        "p95_ms": round(float(np.percentile(arr, 95))),
        "p99_ms": round(float(np.percentile(arr, 99))),
        "min_ms": round(float(arr.min())),
        "max_ms": round(float(arr.max())),
        "mean_ms": round(float(arr.mean())),
        "rps": round(len(latencies) / (wall_ms / 1000), 2),
    }


async def main():
    print(f"Reranker latency-under-load — POST {URL}")
    print(f"Payload: query + {len(CANDIDATES)} candidates ≈ "
          f"{sum(len(c) for c in CANDIDATES)} chars")

    async with aiohttp.ClientSession() as session:
        async with session.get("http://127.0.0.1:8765/health", timeout=aiohttp.ClientTimeout(total=2)) as resp:
            print(f"Reranker health: {await resp.json()}")

    # Warmup — ensure the model is loaded
    print("\nWarmup (1 request)...")
    async with aiohttp.ClientSession() as session:
        ok, ms = await one_request(session)
        print(f"  warmup: ok={ok}, {ms:.0f}ms")

    print("\n" + "=" * 80)
    print(f"  {'Concurrency':<12}  {'p50':>8}  {'p95':>8}  {'p99':>8}  {'mean':>8}  {'min':>6}  {'max':>6}  {'rps':>8}  errors")
    print("=" * 80)

    levels = [
        (1, 30),
        (2, 30),
        (4, 30),
        (8, 30),
        (16, 30),
    ]
    results = []
    for concurrency, total in levels:
        r = await run_load(concurrency, total)
        results.append(r)
        if r["p50_ms"] is None:
            print(f"  {concurrency:<12}  ALL ERRORED ({r['errors']})")
        else:
            print(f"  {concurrency:<12}  "
                  f"{r['p50_ms']:>6}ms  {r['p95_ms']:>6}ms  {r['p99_ms']:>6}ms  "
                  f"{r['mean_ms']:>6}ms  {r['min_ms']:>4}ms  {r['max_ms']:>4}ms  "
                  f"{r['rps']:>6} rps  {r['errors']}")

    print("\n--- JSON ---")
    print(json.dumps({
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "url": URL,
        "candidates_per_request": len(CANDIDATES),
        "results": results,
    }, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
