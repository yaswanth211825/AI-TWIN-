"""
BM25 keyword retrieval over the RAG records, standard library only.

Used for the offline baselines (no API calls). Step 7 replaces it with embeddings in pgvector;
the interface stays the same: search(query, k) -> [(record_index, score), ...].
"""

from __future__ import annotations

import math
import re
from collections import Counter

TOKEN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return TOKEN.findall(text.lower())


class BM25:
    def __init__(self, docs: list[str], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.doc_tokens = [Counter(tokenize(d)) for d in docs]
        self.doc_len = [sum(c.values()) for c in self.doc_tokens]
        self.avg_len = sum(self.doc_len) / len(docs) if docs else 0.0
        df: Counter[str] = Counter()
        for counts in self.doc_tokens:
            df.update(counts.keys())
        n = len(docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def search(self, query: str, k: int) -> list[tuple[int, float]]:
        terms = set(tokenize(query))
        scores = []
        for i, counts in enumerate(self.doc_tokens):
            s = 0.0
            for t in terms:
                tf = counts.get(t)
                if tf:
                    norm = 1 - self.b + self.b * self.doc_len[i] / self.avg_len
                    s += self.idf[t] * tf * (self.k1 + 1) / (tf + self.k1 * norm)
            if s > 0:
                scores.append((i, s))
        scores.sort(key=lambda x: -x[1])
        return scores[:k]
