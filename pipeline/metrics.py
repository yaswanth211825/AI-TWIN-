"""
Automatic scores for "does this reply sound like Yaswanth?". Standard library only, no API calls.

Two kinds of score:
- Closeness to the real reply (chrF): character n-gram overlap, robust to Tenglish spelling variants
  ("vachayi" vs "vachai"). 100 = identical.
- Style, compared with how your real replies look:
    length ratio       predicted length / real length (1.0 is perfect; medians reported)
    multiline          share of replies split over several lines, like your bursts
    tenglish           share of words that are romanized Telugu (learned from your training replies)
    your_vocabulary    share of words you have actually used before
    assistant_speak    share of replies that sound like a chatbot ("certainly", "I'd be happy to", lists ...)

Automatic metrics are a proxy. The final judge is a blind test with friends (step 9).
"""

from __future__ import annotations

import math
import re
import statistics
from collections import Counter
from pathlib import Path

from pipeline.retrieval import tokenize

ENGLISH_WORDS = Path("/usr/share/dict/words")

ASSISTANT_SPEAK = re.compile(
    r"(?i)\b(certainly|absolutely!|i'd be happy to|i would be happy|as an ai|great question|"
    r"here are some|feel free to|let me know if|i hope this helps|in summary|additionally|furthermore)\b"
    r"|^\s*(?:[-*•]|\d+\.)\s+\S.*\n\s*(?:[-*•]|\d+\.)\s+",
    re.MULTILINE,
)
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿]")


def chrf(pred: str, ref: str, max_n: int = 6, beta: float = 2.0) -> float:
    """Character n-gram F-score (Popović 2015), spaces removed, averaged over n = 1..max_n. 0..100."""
    p, r = pred.replace(" ", "").lower(), ref.replace(" ", "").lower()
    precisions, recalls = [], []
    for n in range(1, max_n + 1):
        pg = Counter(p[i:i + n] for i in range(len(p) - n + 1))
        rg = Counter(r[i:i + n] for i in range(len(r) - n + 1))
        if not pg or not rg:
            continue
        overlap = sum((pg & rg).values())
        precisions.append(overlap / sum(pg.values()))
        recalls.append(overlap / sum(rg.values()))
    if not precisions:
        return 0.0
    prec, rec = statistics.mean(precisions), statistics.mean(recalls)
    if prec + rec == 0:
        return 0.0
    return 100 * (1 + beta**2) * prec * rec / (beta**2 * prec + rec)


class StyleProfile:
    """What your writing looks like, learned from your training replies only (never from the test set)."""

    def __init__(self, training_replies: list[str], english: set[str] | None = None):
        if english is None:
            english = load_english_words()
        counts = Counter(t for reply in training_replies for t in tokenize(reply))
        self.vocabulary = {t for t, c in counts.items() if c >= 2}
        self.telugu = {
            t for t, c in counts.items()
            if c >= 3 and t.isalpha() and len(t) >= 3 and t not in english
        }

    def score(self, reply: str) -> dict:
        tokens = tokenize(reply)
        n = len(tokens) or 1
        return {
            "chars": len(reply),
            "multiline": "\n" in reply.strip(),
            "tenglish": sum(t in self.telugu for t in tokens) / n,
            "your_vocabulary": sum(t in self.vocabulary for t in tokens) / n,
            "emoji": bool(EMOJI.search(reply)),
            "assistant_speak": bool(ASSISTANT_SPEAK.search(reply)),
        }


def load_english_words() -> set[str]:
    if not ENGLISH_WORDS.exists():
        return set()
    return {w.strip().lower() for w in ENGLISH_WORDS.read_text(encoding="utf-8", errors="ignore").splitlines()}


def summarize(preds: list[str], refs: list[str], profile: StyleProfile) -> dict:
    """Averages over a test set. refs are your real replies, in the same order as preds."""
    styles = [profile.score(p) for p in preds]
    ratios = [max(len(p), 1) / max(len(r), 1) for p, r in zip(preds, refs)]
    return {
        "chrF": round(statistics.mean(chrf(p, r) for p, r in zip(preds, refs)), 1),
        "length_ratio_median": round(statistics.median(ratios), 2),
        "length_error": round(statistics.mean(abs(math.log(x)) for x in ratios), 2),
        "multiline": round(statistics.mean(s["multiline"] for s in styles), 2),
        "tenglish": round(statistics.mean(s["tenglish"] for s in styles), 2),
        "your_vocabulary": round(statistics.mean(s["your_vocabulary"] for s in styles), 2),
        "emoji": round(statistics.mean(s["emoji"] for s in styles), 2),
        "assistant_speak": round(statistics.mean(s["assistant_speak"] for s in styles), 2),
    }
