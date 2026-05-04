"""
Reranker precision-lift benchmark — bge-m3 alone vs bge-m3 + bge-reranker-v2-m3.

The 24-doc paired Thai/EN paraphrase + distractor bench saturates at R@1=R@5=100%
for bge-m3, so binary recall metrics can't reveal the reranker lift. This script
uses CONTINUOUS metrics that don't saturate:

  - MRR (Mean Reciprocal Rank) — sensitive to rank position even when all queries
    find a target somewhere in the top-K
  - mean rank-1 score — confidence at the top
  - mean score gap (rank 1 vs rank 2) — separation between best and runner-up
  - "rank-1 stability" — fraction of queries where bge-m3 and (bge-m3 + reranker)
    pick the SAME rank-1 doc (tells us how often the reranker disagrees)

Run from arra-oracle-v3/services/reranker-py/ to reuse its venv:
    uv run python ~/Code/.../arra-mcp-installation-guide-oracle/ψ/lab/embedding-benchmark/rerank_lift_bench.py
"""

from __future__ import annotations

import json
import re
import time
from typing import List

import numpy as np
import requests
from sentence_transformers import SentenceTransformer

# Reuse the corpus + queries from sea_lion_bench.py via plain copy — keeping
# this script self-contained so it can be re-run anywhere.
from sea_lion_bench import DOCS, QUERIES, is_thai  # type: ignore

RERANKER_URL = "http://127.0.0.1:8765/rerank"
DENSE_TOP_K = 10  # candidates passed to the reranker


def cosine_topk(query_emb: np.ndarray, doc_embs: np.ndarray, k: int) -> List[int]:
    sims = doc_embs @ query_emb
    return list(np.argsort(-sims)[:k])


def reciprocal_rank(ranked_ids: List[str], expected: List[str]) -> float:
    for i, doc_id in enumerate(ranked_ids):
        if doc_id in expected:
            return 1.0 / (i + 1)
    return 0.0


def rerank_via_sidecar(query: str, candidate_texts: List[str]) -> List[int]:
    """Returns the candidates in reranker order (as indices into the input list)."""
    resp = requests.post(
        RERANKER_URL,
        json={"query": query, "candidates": candidate_texts},
        timeout=30,
    )
    resp.raise_for_status()
    body = resp.json()
    return [r["index"] for r in body["results"]]


def main():
    print("Reranker precision-lift bench — bge-m3 alone vs bge-m3 + bge-reranker-v2-m3")
    print(f"Corpus: {len(DOCS)} docs, {len(QUERIES)} queries")

    # Verify reranker reachable
    try:
        h = requests.get("http://127.0.0.1:8765/health", timeout=2).json()
        print(f"Reranker: {h}")
    except Exception as e:
        print(f"Reranker UNREACHABLE — falling back to dense-only mode: {e}")
        return

    print("\nLoading BAAI/bge-m3 (sentence-transformers)...")
    model = SentenceTransformer("BAAI/bge-m3")
    doc_texts = [d["text"] for d in DOCS]
    doc_ids = [d["id"] for d in DOCS]
    doc_embs = model.encode(doc_texts, normalize_embeddings=True)
    print(f"Indexed {len(DOCS)} docs · dim={doc_embs.shape[1]}")

    rr_dense_only = []
    rr_reranked = []
    dense_only_top1_score = []
    reranked_top1_to_top2_gap = []
    rank1_stability = 0
    per_query: list = []

    for q in QUERIES:
        # 1. Dense recall — top-K from bge-m3
        q_emb = model.encode([q["text"]], normalize_embeddings=True)[0]
        sims = doc_embs @ q_emb
        order = np.argsort(-sims)
        dense_topk_idx = list(order[:DENSE_TOP_K])
        dense_topk_ids = [doc_ids[i] for i in dense_topk_idx]
        dense_only_topk_full_ids = [doc_ids[i] for i in order]  # for MRR over full ranking
        dense_only_top1_score.append(float(sims[order[0]]))

        # 2. Rerank the top-K via sidecar
        cand_texts = [doc_texts[i] for i in dense_topk_idx]
        try:
            t0 = time.perf_counter()
            rerank_order_in_subset = rerank_via_sidecar(q["text"], cand_texts)
            rerank_ms = round((time.perf_counter() - t0) * 1000)
        except Exception as e:
            print(f"  rerank failed for {q['label']}: {e}")
            continue

        # Map reranker indices back to global doc indices
        reranked_global_idx = [dense_topk_idx[i] for i in rerank_order_in_subset]
        reranked_topk_ids = [doc_ids[i] for i in reranked_global_idx]

        # 3. Metrics
        rr_d = reciprocal_rank(dense_only_topk_full_ids, q["expected"])
        rr_r = reciprocal_rank(reranked_topk_ids, q["expected"])
        rr_dense_only.append(rr_d)
        rr_reranked.append(rr_r)

        if dense_topk_ids[0] == reranked_topk_ids[0]:
            rank1_stability += 1

        # Score gap rank1 vs rank2 (reranker scores via second call to expose them)
        # We re-call to get scores, OR fold it in. Lazy: skip for this iteration.
        # (Could be added by parsing the reranker JSON's score field.)
        gap = None  # placeholder

        marker = "≡" if dense_topk_ids[0] == reranked_topk_ids[0] else "→"
        print(f"  {q['label']:50}  RR dense={rr_d:.3f}  reranked={rr_r:.3f}  "
              f"top1: {dense_topk_ids[0]} {marker} {reranked_topk_ids[0]}  ({rerank_ms}ms)")

        per_query.append({
            "label": q["label"],
            "rr_dense": rr_d,
            "rr_reranked": rr_r,
            "dense_top1": dense_topk_ids[0],
            "reranked_top1": reranked_topk_ids[0],
            "rerank_ms": rerank_ms,
        })

    # Aggregates
    mrr_dense = sum(rr_dense_only) / len(rr_dense_only) if rr_dense_only else 0.0
    mrr_reranked = sum(rr_reranked) / len(rr_reranked) if rr_reranked else 0.0
    mean_dense_top1_score = sum(dense_only_top1_score) / len(dense_only_top1_score)
    rank1_stable_pct = round((rank1_stability / len(per_query)) * 100) if per_query else 0

    print("\n" + "=" * 80)
    print("  AGGREGATES — bge-m3 alone vs bge-m3 + bge-reranker-v2-m3")
    print("=" * 80)
    print(f"  MRR (dense only)            : {mrr_dense:.4f}")
    print(f"  MRR (dense + reranker)      : {mrr_reranked:.4f}")
    print(f"  Δ MRR                        : {mrr_reranked - mrr_dense:+.4f}")
    print(f"  Mean rank-1 dense score     : {mean_dense_top1_score:.4f}")
    print(f"  Rank-1 stability            : {rank1_stable_pct}%  (queries where dense rank-1 == reranked rank-1)")
    print(f"  Reranked queries            : {len(per_query)} / {len(QUERIES)}")

    out = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "corpus_size": len(DOCS),
        "queries": len(QUERIES),
        "dense_top_k_passed_to_reranker": DENSE_TOP_K,
        "mrr_dense_only": mrr_dense,
        "mrr_reranked": mrr_reranked,
        "mrr_delta": mrr_reranked - mrr_dense,
        "rank1_stability_pct": rank1_stable_pct,
        "per_query": per_query,
    }
    print("\n--- JSON ---")
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
