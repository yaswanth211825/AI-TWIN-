"""Tests for step 3 using made-up turns."""

import unittest

from pipeline.step3_exchanges import apply_filters, find_candidates, is_low_value


def turn(turn_id: int, session_id: int, sender: str, text: str, minute: int, n: int = 1) -> dict:
    ts = f"2026-03-14T21:{minute:02d}:00"
    return {"turn_id": turn_id, "session_id": session_id, "sender": sender,
            "start": ts, "end": ts, "n_messages": n, "text": text}


TURNS = [
    turn(1, 1, "friend", "bro free aa?", 0),
    turn(2, 1, "me", "ha cheppu", 1),
    turn(3, 1, "friend", "TCS results vachaya?", 2),
    turn(4, 1, "me", "ha vachayi\ndigital lo select ayya", 5, n=2),
    turn(5, 1, "me", "party eppudu ani adagaku", 9),           # my second turn: not a reply
    turn(6, 2, "me", "good morning", 0),                         # session start, nobody to reply to
    turn(7, 2, "friend", "java or python?", 1),
    turn(8, 2, "me", "java", 2),
]


class CandidateTests(unittest.TestCase):
    def setUp(self):
        self.c = find_candidates(TURNS, context_turns=3)

    def test_only_replies_to_friend(self):
        self.assertEqual([c["turn_id"] for c in self.c], [2, 4, 8])

    def test_context_is_previous_turns_in_order(self):
        self.assertEqual([x["text"] for x in self.c[1]["context"]],
                         ["bro free aa?", "ha cheppu", "TCS results vachaya?"])
        self.assertEqual(self.c[1]["reply"], "ha vachayi\ndigital lo select ayya")

    def test_context_never_crosses_session(self):
        self.assertEqual([x["text"] for x in self.c[2]["context"]], ["good morning", "java or python?"])

    def test_context_limited_to_k(self):
        c = find_candidates(TURNS, context_turns=1)
        self.assertEqual([x["text"] for x in c[1]["context"]], ["TCS results vachaya?"])

    def test_latency(self):
        self.assertEqual(self.c[1]["latency_seconds"], 180)


class FilterTests(unittest.TestCase):
    def test_low_value(self):
        for text in ["ok", "Okkk", "hmm", "hahaha", "😂😂", "??", "k."]:
            self.assertTrue(is_low_value(text), text)
        for text in ["java, DSA ki best", "ha vachayi", "first arrays practice chey"]:
            self.assertFalse(is_low_value(text), text)

    def test_placeholder_and_length_dropped(self):
        cands = [
            {"turn_id": 1, "reply": "mail me at [EMAIL]"},
            {"turn_id": 2, "reply": "x" * 50},
            {"turn_id": 3, "reply": "fine"},
        ]
        kept, dropped = apply_filters(cands, max_same=5, max_chars=40)
        self.assertEqual([c["turn_id"] for c in kept], [3])
        self.assertEqual(dropped["reply_has_placeholder"], 1)
        self.assertEqual(dropped["reply_too_long"], 1)

    def test_repeated_replies_capped_and_stable(self):
        cands = [{"turn_id": i, "reply": "Ha ok" if i % 2 else "ha  OK"} for i in range(1, 11)]
        kept1, dropped = apply_filters(cands, max_same=3, max_chars=100)
        kept2, _ = apply_filters(cands, max_same=3, max_chars=100)
        self.assertEqual(len(kept1), 3)
        self.assertEqual(dropped["repeated_reply"], 7)
        self.assertEqual(kept1, kept2)
        self.assertEqual([c["turn_id"] for c in kept1], sorted(c["turn_id"] for c in kept1))


if __name__ == "__main__":
    unittest.main()
