"""
Step 7 check: does embedding search (pgvector, from the Java app) find better style examples than BM25?

Input : data/eval/retrieved_embedding.jsonl   written by app/ RetrievalExporter (top-k hits per test message)
        data/rag.jsonl, data/test.jsonl
Output: data/eval/step7_retrieval.json
        data/eval/replies_nearest_reply@embedding.jsonl   (top-1 hit's reply, so step 5 scores it too)

Measures, for every held-out test message:
    topic@1   the best hit is about the same topic as the real exchange (tags from step 3b)
    topic@k   share of the top-k hits on the same topic
    chrF@1    the best hit's reply compared with your real reply
A random pick would match topics with probability sum(p_topic^2); that is printed as the chance level.

Run from the project root, after the Java exporter:
    python3 -m pipeline.step7_retrieval_eval
"""

from __future__ import annotations

import json
import statistics
from collections import Counter

from pipeline import config
from pipeline.metrics import chrf, paired_bootstrap
from pipeline.retrieval import BM25
from pipeline.step5_baseline import EVAL_DIR, last_friend_turn, load


def run() -> dict:
    rag = load(config.DATA_DIR / "rag.jsonl")
    test = {e["exchange_id"]: e for e in load(config.DATA_DIR / "test.jsonl")}
    embedded = load(EVAL_DIR / "retrieved_embedding.jsonl")
    k = config.RAG_TOP_K
    index = BM25([r["embed_text"] for r in rag])

    rows = {"bm25": [], "embedding": []}
    for item in embedded:
        e = test[item["exchange_id"]]
        bm25_hits = [{"topic": rag[i]["topic"], "reply": rag[i]["reply"]}
                     for i, _ in index.search(last_friend_turn(e), k=k)]
        for name, hits in (("bm25", bm25_hits), ("embedding", item["hits"][:k])):
            top = hits[0] if hits else {"topic": None, "reply": ""}
            rows[name].append({
                "topic@1": float(top["topic"] == e["topic"]),
                f"topic@{k}": sum(h["topic"] == e["topic"] for h in hits) / k,
                "chrF@1": chrf(top["reply"], e["reply"]),
                "found": float(bool(hits)),
            })

    topic_share = Counter(r["topic"] for r in rag)
    chance = sum((n / len(rag)) ** 2 for n in topic_share.values())

    summary = {name: {m: round(statistics.mean(r[m] for r in rs), 3) for m in rs[0]} for name, rs in rows.items()}
    significance = {}
    for metric in ("topic@1", "chrF@1"):
        mean, lo, hi = paired_bootstrap([r[metric] for r in rows["embedding"]], [r[metric] for r in rows["bm25"]])
        significance[f"embedding minus bm25, {metric}"] = {
            "mean": round(mean, 3), "ci95": [round(lo, 3), round(hi, 3)], "real": lo > 0 or hi < 0}

    with (EVAL_DIR / "replies_nearest_reply@embedding.jsonl").open("w", encoding="utf-8") as f:
        for item in embedded:
            reply = item["hits"][0]["reply"] if item["hits"] else ""
            f.write(json.dumps({"exchange_id": item["exchange_id"], "reply": reply}, ensure_ascii=False) + "\n")

    report = {"test_messages": len(embedded), "top_k": k, "topic_chance_level": round(chance, 3),
              "results": summary, "significance": significance}
    (EVAL_DIR / "step7_retrieval.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
