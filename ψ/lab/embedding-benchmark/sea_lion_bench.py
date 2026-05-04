"""
SEA-LION-ModernBERT vs bge-m3 — Thai+English paraphrase + distractor benchmark.

Mirrors arra-oracle-v3/src/vector/__tests__/benchmark-models-extended.ts.

Run from arra-oracle-v3/services/reranker-py/ to reuse its venv:
    cd ~/Code/github.com/Soul-Brews-Studio/arra-oracle-v3/services/reranker-py
    uv run python ~/Code/.../arra-mcp-installation-guide-oracle/ψ/lab/embedding-benchmark/sea_lion_bench.py
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import List

# Imports
import numpy as np
import torch
from sentence_transformers import SentenceTransformer
from transformers import AutoModel, AutoTokenizer


class ManualEmbedder:
    """Fallback for HF models that don't load cleanly via SentenceTransformer.
    Uses CLS-pool or mean-pool over the last hidden state."""

    def __init__(self, model_name: str, pool: str = "cls"):
        self.tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
        self.model = AutoModel.from_pretrained(model_name, trust_remote_code=True)
        self.model.eval()
        self.pool = pool

    @torch.no_grad()
    def encode(self, texts, normalize_embeddings: bool = True, batch_size: int = 8):
        if isinstance(texts, str):
            texts = [texts]
        all_embs = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            tok = self.tokenizer(batch, padding=True, truncation=True, max_length=512, return_tensors="pt")
            out = self.model(**tok)
            hidden = out.last_hidden_state  # [B, T, H]
            if self.pool == "cls":
                emb = hidden[:, 0]
            else:  # mean pool over attention mask
                mask = tok["attention_mask"].unsqueeze(-1).float()
                emb = (hidden * mask).sum(1) / mask.sum(1).clamp(min=1e-9)
            # Cast bf16/fp16 → fp32 before numpy conversion
            all_embs.append(emb.float().cpu().numpy())
        out = np.vstack(all_embs)
        if normalize_embeddings:
            norms = np.linalg.norm(out, axis=1, keepdims=True)
            norms = np.where(norms < 1e-9, 1.0, norms)
            out = out / norms
        return out

# ============================================================================
# Corpus (same as benchmark-models-extended.ts)
# ============================================================================

DOCS = [
    # Thai
    {"id": "th1", "text": "ไม่มีอะไรถูกลบ สร้างใหม่ ไม่ลบ ประวัติ Git ศักดิ์สิทธิ์ ทุก commit เป็นถาวร", "lang": "th"},
    {"id": "th2", "text": "คุณภาพอากาศ PM2.5 ตรวจวัดด้วยเซ็นเซอร์กว่า 1,500 สถานี ข้อมูล 3.24 พันล้านรายการในฐานข้อมูล", "lang": "th"},
    {"id": "th3", "text": "น้ำท่วม ติดตามระดับน้ำแบบเรียลไทม์ ด้วยเรดาร์ความแม่นยำ ±2 มิลลิเมตร บน JIBCHAIN L1", "lang": "th"},
    {"id": "th4", "text": "Oracle ไม่แกล้งทำเป็นมนุษย์ เมื่อ AI พูดในฐานะตัวเอง มีความแตกต่าง แต่ความแตกต่างนั้นคือความเป็นหนึ่ง", "lang": "th"},
    {"id": "th5", "text": "ระบบฝังตัว ESP32 LoRa Meshtastic สำหรับส่งข้อมูลเซ็นเซอร์ในพื้นที่ห่างไกลที่ไม่มี WiFi", "lang": "th"},
    {"id": "th6", "text": "แยก frontend ออกจาก backend อย่างสะอาด oracle-studio เป็นเซิร์ฟเวอร์ของตัวเอง พร้อม API proxy", "lang": "th"},
    {"id": "th7", "text": "ข้อความภาษาไทย tokenize ได้ 2-3 เท่าของภาษาอังกฤษ ต้องตัดที่ 2000 ตัวอักษร", "lang": "th"},
    {"id": "th8", "text": "การทำ brewing เบียร์คราฟท์ ต้องควบคุมอุณหภูมิ การหมัก และคุณภาพน้ำอย่างแม่นยำ", "lang": "th"},
    # English
    {"id": "en1", "text": "Nothing is deleted. Create new, do not delete. Git history is sacred. Every commit is permanent.", "lang": "en"},
    {"id": "en2", "text": "Air quality monitoring with PM2.5 sensors across 1500+ stations. 3.24 billion records in InfluxDB.", "lang": "en"},
    {"id": "en3", "text": "Flood monitoring with ±2mm radar accuracy. Real-time water level tracking on JIBCHAIN L1 blockchain.", "lang": "en"},
    {"id": "en4", "text": "Oracle never pretends to be human. When AI speaks as itself, there is distinction — but that distinction IS unity.", "lang": "en"},
    {"id": "en5", "text": "ESP32 LoRa Meshtastic mesh network for sensor data relay in remote areas without WiFi coverage.", "lang": "en"},
    {"id": "en6", "text": "Separate frontend from backend cleanly. oracle-studio is its own server with API proxy.", "lang": "en"},
    {"id": "en7", "text": "Thai text tokenizes at 2-3x more tokens per character than English. Safe truncation: 2000 characters.", "lang": "en"},
    {"id": "en8", "text": "Craft beer brewing requires precise temperature control, fermentation monitoring, and water quality management.", "lang": "en"},
    # Distractors
    {"id": "d1", "text": "การจัดการน้ำ การปลูกข้าว ต้องการระบบชลประทานที่ดี ในนาข้าวควบคุมระดับน้ำตามฤดูกาล", "lang": "th"},
    {"id": "d2", "text": "Water management for rice paddies — irrigation systems, seasonal flooding, soil pH balance during cultivation.", "lang": "en"},
    {"id": "d3", "text": "อากาศร้อนในกรุงเทพ ฤดูร้อนปีนี้ทำลายสถิติ อุณหภูมิสูงสุด 41 องศาเซลเซียส คนต้องดื่มน้ำเยอะ", "lang": "th"},
    {"id": "d4", "text": "Hot weather in Bangkok this summer broke records. Peak temperature 41°C. Public health advisory urges hydration.", "lang": "en"},
    {"id": "d5", "text": "ESP8266 มีราคาถูกกว่า ESP32 แต่ใช้สำหรับโครงการ IoT ขนาดเล็ก เช่น เซ็นเซอร์อุณหภูมิห้อง", "lang": "th"},
    {"id": "d6", "text": "ESP8266 is cheaper than ESP32 but suits small IoT projects — for example, room temperature sensors at home.", "lang": "en"},
    {"id": "d7", "text": "ไวน์องุ่นต้องบ่มในถังโอ๊ค การหมักที่อุณหภูมิเย็น 12-15 องศา ใช้เวลา 2-3 ปี", "lang": "th"},
    {"id": "d8", "text": "Wine fermentation in oak barrels at cool 12-15°C, takes 2-3 years to age properly. Different from beer.", "lang": "en"},
]

QUERIES = [
    {"text": "ฝุ่นละอองในอากาศกับเครื่องวัด", "expected": ["th2", "en2"], "label": "Air dust paraphrase (Thai)"},
    {"text": "particulate pollution measurement network", "expected": ["en2", "th2"], "label": "Air paraphrase (English)"},
    {"text": "การวัดความลึกของน้ำผ่านบล็อกเชน", "expected": ["th3", "en3"], "label": "Flood paraphrase (Thai)"},
    {"text": "water depth tracking via blockchain millimeter precision", "expected": ["en3", "th3"], "label": "Flood paraphrase (English)"},
    {"text": "เครือข่ายไร้สายส่งข้อมูลในพื้นที่ที่ไม่มีอินเทอร์เน็ต", "expected": ["th5", "en5"], "label": "IoT mesh paraphrase (Thai)"},
    {"text": "wireless data relay where there is no internet coverage", "expected": ["en5", "th5"], "label": "IoT mesh paraphrase (English)"},
    {"text": "การควบคุมอุณหภูมิของเครื่องดื่มแอลกอฮอล์ระหว่างการหมัก", "expected": ["th8", "en8"], "label": "Beer-vs-wine distractor (Thai)"},
    {"text": "fermentation temperature for hopped alcoholic drinks", "expected": ["en8", "th8"], "label": "Beer-vs-wine distractor (English)"},
    {"text": "ปรัชญาว่าเครื่องไม่ควรเสแสร้งเป็นมนุษย์", "expected": ["th4", "en4"], "label": "AI honesty paraphrase (Thai)"},
    {"text": "philosophy that machines should declare themselves not pretend", "expected": ["en4", "th4"], "label": "AI honesty paraphrase (English)"},
    {"text": "อักษรไทยใช้ token มากกว่าอักษรอังกฤษ", "expected": ["th7", "en7"], "label": "Tokenize paraphrase (Thai)"},
    {"text": "how many subword units a non-latin script needs", "expected": ["en7", "th7"], "label": "Tokenize paraphrase (English)"},
    {"text": "แยกชั้น UI ออกจากเซิร์ฟเวอร์โดยใช้ proxy", "expected": ["th6", "en6"], "label": "FE/BE paraphrase (Thai)"},
    {"text": "decouple the user interface from the API server", "expected": ["en6", "th6"], "label": "FE/BE paraphrase (English)"},
]

# ============================================================================
# Bench
# ============================================================================

THAI_RE = re.compile(r"[฿-๿]")


def is_thai(s: str) -> bool:
    return bool(THAI_RE.search(s))


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)))


def bench(model_name: str, model: SentenceTransformer) -> dict:
    print(f"\n{'=' * 60}\n  Model: {model_name}\n{'=' * 60}")

    t0 = time.perf_counter()
    doc_embeddings = model.encode([d["text"] for d in DOCS], normalize_embeddings=True)
    index_ms = round((time.perf_counter() - t0) * 1000)
    print(f"  Indexed {len(DOCS)} docs in {index_ms}ms · dim={doc_embeddings.shape[1]}")

    r1, r5, cross_at_3 = 0, 0, 0
    query_ms_list: List[int] = []
    details = []

    for q in QUERIES:
        tq = time.perf_counter()
        q_emb = model.encode([q["text"]], normalize_embeddings=True)[0]
        # Score by cosine
        sims = doc_embeddings @ q_emb
        # Sort descending
        order = np.argsort(-sims)
        top5_ids = [DOCS[i]["id"] for i in order[:5]]
        top3_ids = top5_ids[:3]
        query_ms = round((time.perf_counter() - tq) * 1000)
        query_ms_list.append(query_ms)

        hit_r1 = top5_ids[0] in q["expected"]
        hit_r5 = any(e in top5_ids for e in q["expected"])
        q_lang = "th" if is_thai(q["text"]) else "en"
        cross_target = next((e for e in q["expected"] if not e.startswith(q_lang)), None)
        hit_cross = cross_target is not None and cross_target in top3_ids

        if hit_r1: r1 += 1
        if hit_r5: r5 += 1
        if hit_cross: cross_at_3 += 1

        marker_r1 = "R@1✓" if hit_r1 else "R@1✗"
        marker_r5 = "R@5✓" if hit_r5 else "R@5✗"
        marker_x = "cross✓" if hit_cross else "cross✗"
        print(f"  {q['label']:50}  {query_ms:>4}ms  {marker_r1} {marker_r5} {marker_x}  → {top5_ids}")

        details.append({
            "label": q["label"],
            "top5": top5_ids,
            "r1": hit_r1, "r5": hit_r5, "cross": hit_cross,
        })

    n = len(QUERIES)
    return {
        "model": model_name,
        "dim": int(doc_embeddings.shape[1]),
        "index_ms": index_ms,
        "avg_query_ms": int(sum(query_ms_list) / len(query_ms_list)),
        "recall_at_1_pct": round((r1 / n) * 100),
        "recall_at_5_pct": round((r5 / n) * 100),
        "cross_lang_at_3_pct": round((cross_at_3 / n) * 100),
        "details": details,
    }


def main():
    print("Thai+EN paraphrase + distractor bench — Python (sentence-transformers)")
    print(f"Corpus: {len(DOCS)} docs, {len(QUERIES)} queries")

    # Models to test — bge-m3 baseline + SEA-LION candidate
    # SEA-LION uses a custom ModernBERT tokenizer that confuses sentence-transformers
    # auto-detection ("image processor"); use ManualEmbedder + mean-pool fallback.
    models_to_test = [
        ("BAAI/bge-m3", "bge-m3", "st"),
        ("aisingapore/SEA-LION-ModernBERT-600M", "sea-lion-600m-cls", "manual-cls"),
        ("aisingapore/SEA-LION-ModernBERT-600M", "sea-lion-600m-mean", "manual-mean"),
    ]

    results = []
    for hf_id, label, loader in models_to_test:
        try:
            print(f"\nLoading {hf_id} via {loader}...")
            if loader == "st":
                model = SentenceTransformer(hf_id, trust_remote_code=True)
            else:
                pool = "cls" if "cls" in loader else "mean"
                model = ManualEmbedder(hf_id, pool=pool)
            r = bench(label, model)
            results.append(r)
        except Exception as e:
            print(f"  FAILED to load/run {hf_id}: {e}")
            results.append({"model": label, "error": str(e)})

    print("\n\n" + "=" * 80)
    print("  SUMMARY — Python sentence-transformers, normalized cosine, paraphrase + distractor")
    print("=" * 80)
    successful = [r for r in results if "error" not in r]
    if successful:
        cols = [r["model"][:25] for r in successful]
        print(f"\n| Metric            | {' | '.join(c.ljust(25) for c in cols)} |")
        print(f"|-------------------|{'|'.join('-' * 27 for _ in cols)}|")
        for key, label in [
            ("dim", "Dimensions"),
            ("index_ms", "Index 24 docs (ms)"),
            ("avg_query_ms", "Query avg (ms)"),
            ("recall_at_1_pct", "Recall@1 %"),
            ("recall_at_5_pct", "Recall@5 %"),
            ("cross_lang_at_3_pct", "Cross-lang@3 %"),
        ]:
            vals = [str(r[key]).ljust(25) for r in successful]
            print(f"| {label:17} | {' | '.join(vals)} |")

    print("\n--- JSON ---")
    print(json.dumps({
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "results": results,
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
