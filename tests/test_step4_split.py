"""Tests for step 4 using made-up exchanges."""

import unittest

from pipeline.step4_split import split_by_session, to_chat, to_rag, usable


def ex(i: int, session: int, day: int, quality: int = 3, private: bool = False) -> dict:
    return {
        "exchange_id": i, "session_id": session, "ts": f"2026-03-{day:02d}T10:00:{i % 60:02d}",
        "context": [{"sender": "friend", "text": f"q{i}"}], "reply": f"a{i}",
        "topic": "career", "type": "answer", "quality": quality, "private": private,
    }


class FilterTests(unittest.TestCase):
    def test_private_and_low_quality_dropped(self):
        kept, dropped = usable([ex(1, 1, 1), ex(2, 1, 1, quality=2), ex(3, 1, 1, private=True)], min_quality=3)
        self.assertEqual([e["exchange_id"] for e in kept], [1])
        self.assertEqual(dropped, {"low_quality": 1, "private": 1})


class SplitTests(unittest.TestCase):
    def setUp(self):
        # 10 sessions on 10 days, 2 exchanges each, given out of order
        rows = [ex(s * 2 + k, s, s + 1) for s in range(10) for k in range(2)]
        self.train, self.val, self.test = split_by_session(list(reversed(rows)), (0.8, 0.1, 0.1))

    def test_sizes(self):
        self.assertEqual((len(self.train), len(self.val), len(self.test)), (16, 2, 2))

    def test_time_order(self):
        self.assertLess(max(e["ts"] for e in self.train), min(e["ts"] for e in self.val))
        self.assertLess(max(e["ts"] for e in self.val), min(e["ts"] for e in self.test))

    def test_no_session_in_two_splits(self):
        sessions = [{e["session_id"] for e in part} for part in (self.train, self.val, self.test)]
        self.assertFalse(sessions[0] & sessions[2])
        self.assertFalse(sessions[1] & sessions[2])


class FormatTests(unittest.TestCase):
    EXCHANGE = {
        "exchange_id": 7, "session_id": 1, "ts": "2026-03-14T21:50:00", "topic": "career", "type": "answer",
        "context": [
            {"sender": "friend", "text": "bro free aa?"},
            {"sender": "me", "text": "ha cheppu"},
            {"sender": "friend", "text": "TCS results vachaya?"},
            {"sender": "friend", "text": "cheppu ra"},
        ],
        "reply": "ha vachayi\ndigital lo select ayya",
    }

    def test_chat_format(self):
        msgs = to_chat(self.EXCHANGE, "SYS")["messages"]
        self.assertEqual([m["role"] for m in msgs], ["system", "user", "assistant", "user", "assistant"])
        self.assertEqual(msgs[2]["weight"], 0)          # earlier reply is context only
        self.assertNotIn("weight", msgs[-1])            # final reply is learned
        self.assertEqual(msgs[3]["content"], "TCS results vachaya?\ncheppu ra")  # double text merged

    def test_rag_embeds_last_friend_turn(self):
        rec = to_rag(self.EXCHANGE)
        self.assertEqual(rec["embed_text"], "cheppu ra")
        self.assertEqual(rec["reply"], "ha vachayi\ndigital lo select ayya")


if __name__ == "__main__":
    unittest.main()
