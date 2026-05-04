"""
Reranker precision-lift bench — UNPAIRED target version.

The previous rerank_lift_bench.py couldn't measure a reranker lift because the
existing eval has paired targets (`expected = [thai_id, english_id]`) — both
answers count, so any model that finds one of them at rank 1 scores MRR=1
regardless of cross-language reasoning. See vault learning
2026-05-05_reranker-lift-empirical-bench-blind.md for the analysis.

This bench fixes that. Same docs, same queries, but **expected** is restricted
to the *cross-language* paraphrase only:

  - Thai query → expects ONLY the English doc (forces cross-lingual retrieval)
  - English query → expects ONLY the Thai doc

Hypothesis: dense (cosine over bge-m3) is biased toward same-script matches
because vector geometry rewards lexical overlap; the reranker (cross-encoder)
should bridge across scripts better.

Run from arra-oracle-v3/services/reranker-py/ to reuse its venv:
    uv run --with requests python ~/Code/.../arra-mcp-installation-guide-oracle/ψ/lab/embedding-benchmark/rerank_lift_unpaired_bench.py
"""

from __future__ import annotations

import json
import time
from typing import List

import numpy as np
import requests
from sentence_transformers import SentenceTransformer

from sea_lion_bench import DOCS, QUERIES, is_thai  # type: ignore

RERANKER_URL = "http://127.0.0.1:8765/rerank"
DENSE_TOP_K = 10  # candidates passed to the reranker


def reciprocal_rank(ranked_ids: List[str], expected_id: str) -> float:
    for i, doc_id in enumerate(ranked_ids):
        if doc_id == expected_id:
            return 1.0 / (i + 1)
    return 0.0


def rerank_via_sidecar(query: str, candidate_texts: List[str]) -> List[int]:
    resp = requests.post(
        RERANKER_URL,
        json={"query": query, "candidates": candidate_texts},
        timeout=30,
    )
    resp.raise_for_status()
    return [r["index"] for r in resp.json()["results"]]


def build_unpaired_queries():
    """Derive single-target version of QUERIES — keep ONLY the cross-language id."""
    out = []
    for q in QUERIES:
        q_lang = "th" if is_thai(q["text"]) else "en"
        # Pick the expected id that does NOT match the query's language
        cross = next((e for e in q["expected"] if not e.startswith(q_lang)), None)
        if cross is None:
            continue  # skip if no cross-lang target (shouldn't happen on this set)
        out.append({"text": q["text"], "expected_id": cross, "label": q["label"], "query_lang": q_lang})
    return out


def main():
    print("Reranker UNPAIRED bench — bge-m3 alone vs bge-m3 + bge-reranker-v2-m3")
    print("Single cross-language target per query (Thai→en, English→th).")

    try:
        h = requests.get("http://127.0.0.1:8765/health", timeout=2).json()
        print(f"Reranker: {h}")
    except Exception as e:
        print(f"Reranker UNREACHABLE: {e}")
        return

    print("\nLoading BAAI/bge-m3...")
    model = SentenceTransformer("BAAI/bge-m3")
    doc_texts = [d["text"] for d in DOCS]
    doc_ids = [d["id"] for d in DOCS]
    doc_embs = model.encode(doc_texts, normalize_embeddings=True)
    print(f"Indexed {len(DOCS)} docs · dim={doc_embs.shape[1]}")

    queries = build_unpaired_queries()
    print(f"Queries: {len(queries)} (each with a single cross-language target)\n")

    rr_dense = []
    rr_reranked = []
    flips_to_correct = 0     # dense rank-1 was wrong, reranked rank-1 is right
    flips_away_from_correct = 0  # dense rank-1 was right, reranked rank-1 is wrong
    per_query = []

    for q in queries:
        q_emb = model.encode([q["text"]], normalize_embeddings=True)[0]
        order = np.argsort(-(doc_embs @ q_emb))

        dense_topk_idx = list(order[:DENSE_TOP_K])
        dense_full_ids = [doc_ids[i] for i in order]
        dense_topk_ids = [doc_ids[i] for i in dense_topk_idx]

        cand_texts = [doc_texts[i] for i in dense_topk_idx]
        try:
            rerank_order = rerank_via_sidecar(q["text"], cand_texts)
        except Exception as e:
            print(f"  rerank failed for {q['label']}: {e}")
            continue
        reranked_topk_ids = [doc_ids[dense_topk_idx[i]] for i in rerank_order]

        rr_d = reciprocal_rank(dense_full_ids, q["expected_id"])
        rr_r = reciprocal_rank(reranked_topk_ids, q["expected_id"])
        rr_dense.append(rr_d)
        rr_reranked.append(rr_r)

        dense_top1_correct = dense_topk_ids[0] == q["expected_id"] if dense_topk_ids else False
        rerank_top1_correct = reranked_topk_ids[0] == q["expected_id"] if reranked_topk_ids else False
        if not dense_top1_correct and rerank_top1_correct:
            flips_to_correct += 1
        if dense_top1_correct and not rerank_top1_correct:
            flips_away_from_correct += 1

        marker = "↑" if rr_r > rr_d else ("↓" if rr_r < rr_d else "≡")
        print(f"  {q['label']:50}  RR dense={rr_d:.3f}  rerank={rr_r:.3f}  {marker}  "
              f"target={q['expected_id']}  d-top1={dense_topk_ids[0]}  r-top1={reranked_topk_ids[0]}")

        per_query.append({
            "label": q["label"],
            "expected_id": q["expected_id"],
            "rr_dense": rr_d,
            "rr_reranked": rr_r,
            "dense_top1": dense_topk_ids[0] if dense_topk_ids else None,
            "reranked_top1": reranked_topk_ids[0] if reranked_topk_ids else None,
        })

    n = len(rr_dense)
    mrr_d = sum(rr_dense) / n
    mrr_r = sum(rr_reranked) / n

    # R@1 on unpaired target — strictest measure
    r1_d = sum(1 for q in per_query if q["dense_top1"] == q["expected_id"]) / n * 100
    r1_r = sum(1 for q in per_query if q["reranked_top1"] == q["expected_id"]) / n * 100

    print("\n" + "=" * 80)
    print("  AGGREGATES — unpaired (cross-language only) target")
    print("=" * 80)
    print(f"  Queries                      : {n}")
    print(f"  R@1 (dense only)             : {r1_d:.1f}%")
    print(f"  R@1 (dense + reranker)       : {r1_r:.1f}%")
    print(f"  Δ R@1                         : {r1_r - r1_d:+.1f} pts")
    print(f"  MRR (dense only)             : {mrr_d:.4f}")
    print(f"  MRR (dense + reranker)       : {mrr_r:.4f}")
    print(f"  Δ MRR                         : {mrr_r - mrr_d:+.4f}")
    print(f"  Flips toward correct         : {flips_to_correct}  (rerank fixed dense)")
    print(f"  Flips away from correct      : {flips_away_from_correct}  (rerank broke dense)")

    out = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "queries": n,
        "dense_top_k": DENSE_TOP_K,
        "r1_dense_only_pct": r1_d,
        "r1_reranked_pct": r1_r,
        "r1_delta_pts": r1_r - r1_d,
        "mrr_dense_only": mrr_d,
        "mrr_reranked": mrr_r,
        "mrr_delta": mrr_r - mrr_d,
        "flips_to_correct": flips_to_correct,
        "flips_away_from_correct": flips_away_from_correct,
        "per_query": per_query,
    }
    print("\n--- JSON ---")
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
