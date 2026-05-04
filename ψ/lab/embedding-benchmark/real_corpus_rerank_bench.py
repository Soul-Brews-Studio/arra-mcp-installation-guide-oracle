"""
Real-corpus reranker lift bench — production index, hand-labeled queries.

Uses the live arra-oracle-v3 hybrid search API (FTS5 + bge-m3 dense over
20,842 production docs) and the live reranker sidecar (:8765). For each
(query, expected_doc_id) pair, measures rank of expected doc BEFORE the
reranker (raw hybrid result) vs AFTER (reranker reordering).

Each query was hand-crafted by reading actual sampled docs from oracle.db
and writing a paraphrased query (often in the OTHER language) that should
retrieve that specific doc. 12 queries total — small but real.

Run from arra-oracle-v3/services/reranker-py/:
    uv run --with requests python ~/Code/.../arra-mcp-installation-guide-oracle/ψ/lab/embedding-benchmark/real_corpus_rerank_bench.py
"""

from __future__ import annotations

import json
import time
from typing import List

import requests

ARRA_API = "http://localhost:47778"
RERANKER_URL = "http://127.0.0.1:8765/rerank"
TOP_K_FROM_API = 20  # how many candidates the API returns; reranker reorders all


# Hand-labeled (query, expected_doc_id) pairs.
# Derived from real oracle.db docs. Cross-lingual where it makes sense.
EVAL = [
    # Thai queries → expect English-dominant production doc
    {
        "query": "หลีกเลี่ยงการ cd ลง subdirectory ก่อนใช้ git ใช้ -C แทน",
        "expected_id_substring": "maw-sync-best-practices",
        "label": "TH→EN  git anti-patterns (-C over cd)",
    },
    {
        "query": "การเกิดใหม่ทางพุทธศาสนาเปรียบเทียบกับการสร้าง oracle ใหม่",
        "expected_id_substring": "incarnation-vs-birth-oracle-identity",
        "label": "TH→EN  Buddhist rebirth as oracle identity metaphor",
    },
    {
        "query": "ใช้ direnv envrc แทน dotenv เพื่อแยก credential ตาม project",
        "expected_id_substring": "direnv-envrc-over-env-for-project-credential",
        "label": "TH→EN  direnv vs .env for project credentials",
    },
    {
        "query": "agent ตั้งเวลาเองด้วย /loop เทียบกับ cron ภายนอก",
        "expected_id_substring": "agent-self-scheduling-over-external-cron",
        "label": "TH→EN  self-scheduling agent vs external cron",
    },
    {
        "query": "ใช้ Haiku agent ขนานวิเคราะห์ไฟล์ใหญ่หลายตัวพร้อมกัน",
        "expected_id_substring": "maeon-craft-oracle-birth-analysis",
        "label": "TH→EN  parallel Haiku agents for large-file analysis",
    },
    {
        "query": "session 11 dual index bge-m3 timeline",
        "expected_id_substring": "session-11-dual-index-bge-m3",
        "label": "TH→EN  session 11 dual-index bge-m3 (mostly EN query)",
    },
    {
        "query": "voice tray ระบบเสียงรวมศูนย์ incubation graduation pattern",
        "expected_id_substring": "voice-tray-central-voice-system",
        "label": "TH→EN  voice tray central system",
    },

    # English queries → expect specific production doc
    {
        "query": "git -C subdir as alternative to cd then git inside agent worktree",
        "expected_id_substring": "maw-sync-best-practices",
        "label": "EN→EN  git -C anti-pattern (English variant)",
    },
    {
        "query": "Buddhist rebirth philosophical metaphor for oracle continuity",
        "expected_id_substring": "incarnation-vs-birth-oracle-identity",
        "label": "EN→EN  oracle incarnation philosophy",
    },
    {
        "query": "credentials in .envrc rather than .env for security isolation",
        "expected_id_substring": "direnv-envrc-over-env-for-project-credential",
        "label": "EN→EN  direnv security isolation",
    },
    {
        "query": "tradeoffs of in-process self-scheduling agent loop versus systemd cron",
        "expected_id_substring": "agent-self-scheduling-over-external-cron",
        "label": "EN→EN  self-scheduling vs cron tradeoffs",
    },
    {
        "query": "AI diary mobile session walking input typos responsive",
        "expected_id_substring": "tong-claude-code-training",
        "label": "EN→EN  mobile training AI diary",
    },
]


def query_arra_search(q: str, limit: int) -> list:
    """Hit the live hybrid search API. Returns list of result dicts."""
    resp = requests.get(
        f"{ARRA_API}/api/search",
        params={"q": q, "limit": limit, "mode": "hybrid"},
        timeout=10,
    )
    resp.raise_for_status()
    body = resp.json()
    return body.get("results", [])


def rerank(query: str, candidate_texts: List[str]) -> List[int]:
    resp = requests.post(
        RERANKER_URL,
        json={"query": query, "candidates": candidate_texts},
        timeout=30,
    )
    resp.raise_for_status()
    return [r["index"] for r in resp.json()["results"]]


def find_rank(ranked_ids: List[str], target_substring: str) -> int | None:
    """1-based rank of the first id containing the target substring; None if absent."""
    for i, doc_id in enumerate(ranked_ids):
        if target_substring in doc_id:
            return i + 1
    return None


def reciprocal_rank(rank: int | None) -> float:
    return 1.0 / rank if rank else 0.0


def main():
    print("Real-corpus reranker lift bench — production index + hand-labeled queries")
    print(f"Queries: {len(EVAL)}")

    # Sanity check both services
    api_h = requests.get(f"{ARRA_API}/api/health", timeout=2).json()
    rer_h = requests.get("http://127.0.0.1:8765/health", timeout=2).json()
    print(f"arra-oracle-v3: {api_h.get('server')} v{api_h.get('version')}")
    print(f"reranker:       {rer_h.get('service')} (loaded={rer_h.get('model_loaded')})")
    print()

    rr_dense, rr_reranked = [], []
    r1_d, r1_r = 0, 0
    not_in_top_k = 0
    flips_to_correct = 0
    flips_away = 0
    per_query: list = []

    for q in EVAL:
        try:
            results = query_arra_search(q["query"], TOP_K_FROM_API)
        except Exception as e:
            print(f"  API failed for {q['label']}: {e}")
            continue
        if not results:
            print(f"  EMPTY API result for {q['label']}")
            continue

        dense_ids = [r.get("id", "") for r in results]
        dense_texts = [(r.get("content") or "")[:500] for r in results]

        try:
            rerank_order = rerank(q["query"], dense_texts)
        except Exception as e:
            print(f"  rerank failed for {q['label']}: {e}")
            continue
        reranked_ids = [dense_ids[i] for i in rerank_order]

        d_rank = find_rank(dense_ids, q["expected_id_substring"])
        r_rank = find_rank(reranked_ids, q["expected_id_substring"])

        if d_rank is None and r_rank is None:
            not_in_top_k += 1

        rr_dense.append(reciprocal_rank(d_rank))
        rr_reranked.append(reciprocal_rank(r_rank))
        if d_rank == 1: r1_d += 1
        if r_rank == 1: r1_r += 1

        if d_rank != 1 and r_rank == 1:
            flips_to_correct += 1
        if d_rank == 1 and r_rank != 1:
            flips_away += 1

        marker = "↑" if (r_rank or 99) < (d_rank or 99) else ("↓" if (r_rank or 99) > (d_rank or 99) else "≡")
        print(f"  {q['label']:55}  d#{d_rank}  r#{r_rank}  {marker}")

        per_query.append({
            "label": q["label"],
            "expected_substring": q["expected_id_substring"],
            "dense_rank": d_rank,
            "reranked_rank": r_rank,
            "dense_top1_id": dense_ids[0] if dense_ids else None,
            "reranked_top1_id": reranked_ids[0] if reranked_ids else None,
        })

    n = len(per_query)
    if n == 0:
        print("\nNo queries succeeded.")
        return
    mrr_d = sum(rr_dense) / n
    mrr_r = sum(rr_reranked) / n

    print("\n" + "=" * 80)
    print("  REAL-CORPUS AGGREGATES — production hybrid index → reranker")
    print("=" * 80)
    print(f"  Queries succeeded            : {n} / {len(EVAL)}")
    print(f"  Target not in top-{TOP_K_FROM_API} (either)  : {not_in_top_k}")
    print(f"  R@1 (dense hybrid)            : {r1_d / n * 100:.1f}%  ({r1_d}/{n})")
    print(f"  R@1 (dense + reranker)        : {r1_r / n * 100:.1f}%  ({r1_r}/{n})")
    print(f"  Δ R@1                          : {(r1_r - r1_d) / n * 100:+.1f} pts  ({r1_r - r1_d:+d} queries)")
    print(f"  MRR (dense hybrid)            : {mrr_d:.4f}")
    print(f"  MRR (dense + reranker)        : {mrr_r:.4f}")
    print(f"  Δ MRR                          : {mrr_r - mrr_d:+.4f}")
    print(f"  Flips toward correct          : {flips_to_correct}")
    print(f"  Flips away from correct       : {flips_away}")
    print(f"  Net flips                     : {flips_to_correct - flips_away:+d}")

    print("\n--- JSON ---")
    print(json.dumps({
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "queries": n,
        "top_k_from_api": TOP_K_FROM_API,
        "r1_dense_pct": r1_d / n * 100,
        "r1_reranked_pct": r1_r / n * 100,
        "r1_delta_pts": (r1_r - r1_d) / n * 100,
        "mrr_dense": mrr_d,
        "mrr_reranked": mrr_r,
        "mrr_delta": mrr_r - mrr_d,
        "flips_to_correct": flips_to_correct,
        "flips_away_from_correct": flips_away,
        "per_query": per_query,
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
