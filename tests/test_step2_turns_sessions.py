"""Tests for step 2 using made-up messages."""

import unittest
from datetime import timedelta

from pipeline.step2_turns_sessions import build_turns, report_for

BURST = timedelta(minutes=2)
SESSION = timedelta(minutes=60)


def msg(ts: str, sender: str, text: str) -> dict:
    return {"ts": f"2026-03-14T{ts}", "sender": sender, "text": text}


CHAT = [
    msg("21:41:00", "friend", "bro free aa?"),
    msg("21:41:20", "friend", "TCS results vachaya?"),      # burst with previous (20 s)
    msg("21:50:00", "me", "ha vachayi"),
    msg("21:50:30", "me", "digital lo select ayya"),         # burst
    msg("21:51:00", "friend", "congrats ra!!"),
    msg("21:52:00", "me", "thanks bro"),
    msg("21:55:00", "me", "party eppudu ani adagaku"),       # same sender but 3 min later: new turn
    msg("23:30:00", "friend", "java or python?"),            # 95 min silence: new session
    msg("23:31:00", "me", "java"),
]


class BuildTurnsTests(unittest.TestCase):
    def setUp(self):
        self.turns = build_turns(CHAT, BURST, SESSION)

    def test_bursts_are_merged(self):
        self.assertEqual(self.turns[0].text, "bro free aa?\nTCS results vachaya?")
        self.assertEqual(self.turns[0].n_messages, 2)
        self.assertEqual(self.turns[1].text, "ha vachayi\ndigital lo select ayya")

    def test_same_sender_after_long_pause_is_new_turn(self):
        self.assertEqual([t.text for t in self.turns[3:5]], ["thanks bro", "party eppudu ani adagaku"])

    def test_sessions_cut_on_silence(self):
        self.assertEqual([t.session_id for t in self.turns], [1, 1, 1, 1, 1, 2, 2])

    def test_turn_never_crosses_session(self):
        chat = [msg("10:00:00", "me", "good night"), msg("11:30:00", "me", "good morning")]
        turns = build_turns(chat, timedelta(hours=5), SESSION)  # huge burst gap, still split by session
        self.assertEqual(len(turns), 2)

    def test_turn_times(self):
        self.assertEqual((self.turns[1].start, self.turns[1].end), ("2026-03-14T21:50:00", "2026-03-14T21:50:30"))

    def test_report_counts(self):
        report = report_for(CHAT, self.turns)
        self.assertEqual(report["turns"], 7)
        self.assertEqual(report["sessions"], 2)
        self.assertEqual(report["my_replies_in_session"], 3)  # 21:50, 21:52, 23:31


if __name__ == "__main__":
    unittest.main()
