"""Tests for step 1 using made-up messages (no real chat data in the repo).

Run from the project root:
    python3 -m unittest discover -s tests -v
"""

import json
import tempfile
import unittest
from collections import Counter
from datetime import datetime
from pathlib import Path

from pipeline.step1_parse_clean import clean, parse, parse_timestamp, redact, run

SAMPLE = "\n".join([
    "‎[06/05/25, 11:46:48 PM] Ravi: ‎Messages and calls are end-to-end encrypted.",
    "[06/05/25, 11:47:02 PM] Ravi: bro free aa?",
    "[06/05/25, 11:47:10 PM] Ravi: TCS results",
    "vachaya??",
    "‎[06/05/25, 11:47:30 PM] Ravi: ‎sticker omitted",
    "[06/05/25, 11:48:01 PM] Prosessor: ha vachayi ‎<This message was edited>",
    "‎[06/05/25, 11:48:05 PM] Prosessor: ‎This message was deleted.",
    "[06/05/25, 11:49:00 PM] Ravi: https://example.com/result",
    "[06/05/25, 11:49:30 PM] Ravi: call me 98765 43210 or ravi@example.com",
    "‎[06/05/25, 11:50:00 PM] Prosessor: ‎Missed voice call, ‎Click to call back",
])


class ParseTests(unittest.TestCase):
    def test_timestamp_with_narrow_space(self):
        self.assertEqual(parse_timestamp("06/05/25", "11:46:48 PM"), datetime(2025, 5, 6, 23, 46, 48))

    def test_day_comes_first(self):
        self.assertEqual(parse_timestamp("12/01/26", "9:05:00 AM").month, 1)

    def test_continuation_line_joins_previous_message(self):
        messages, orphans = parse(SAMPLE.split("\n"))
        self.assertEqual(len(messages), 9)
        self.assertEqual(messages[2].text, "TCS results\nvachaya??")
        self.assertEqual(orphans, 0)


class CleanTests(unittest.TestCase):
    def test_drop_reasons(self):
        self.assertEqual(clean("‎sticker omitted").drop_reason, "media")
        self.assertEqual(clean("‎image omitted").drop_reason, "media")
        self.assertEqual(clean("Resume_2026.pdf • 1 page ‎document omitted").drop_reason, "media")
        self.assertEqual(clean("‎You deleted this message.").drop_reason, "deleted")
        self.assertEqual(clean("‎Voice call, ‎12 min").drop_reason, "call")
        self.assertEqual(clean("https://example.com/x").drop_reason, "link_only")
        self.assertEqual(clean("   ").drop_reason, "empty")

    def test_caption_kept_marker_removed(self):
        result = clean("hostel food chudu ‎image omitted")
        self.assertEqual((result.text, result.was_caption), ("hostel food chudu", True))
        self.assertEqual(clean("idhi chudu\n‎image omitted").text, "idhi chudu")

    def test_edited_marker_removed_and_text_kept(self):
        result = clean("ha vachayi ‎<This message was edited>")
        self.assertEqual((result.text, result.drop_reason, result.was_edited), ("ha vachayi", None, True))

    def test_normal_message_is_kept(self):
        self.assertEqual(clean("java, DSA ki best").text, "java, DSA ki best")

    def test_line_breaks_are_kept(self):
        self.assertEqual(clean("ha\ncheppu").text, "ha\ncheppu")


class RedactTests(unittest.TestCase):
    def test_private_data_replaced(self):
        counts = Counter()
        out = redact("call 98765 43210, +91 9876543210, mail a.b@example.com, upi ravi@okaxis, otp is 482913", counts)
        self.assertEqual(out, "call [PHONE], [PHONE], mail [EMAIL], upi [UPI], otp is [OTP]")
        self.assertEqual(counts["phone"], 2)

    def test_link_inside_text(self):
        self.assertEqual(redact("see https://x.com/a?b=1 bro", Counter()), "see [LINK] bro")

    def test_ordinary_numbers_untouched(self):
        self.assertEqual(redact("8 LPA, 2026 batch, room 204", Counter()), "8 LPA, 2026 batch, room 204")


class RunTests(unittest.TestCase):
    def test_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "_chat.txt"
            src.write_text(SAMPLE, encoding="utf-8")
            report = run(src, Path(tmp) / "out")
            rows = [json.loads(line) for line in (Path(tmp) / "out" / "messages.jsonl").read_text().splitlines()]

        self.assertEqual(report["parsed_messages"], 9)
        self.assertEqual(report["dropped"], {"system": 1, "media": 1, "deleted": 1, "link_only": 1, "call": 1})
        self.assertEqual([r["sender"] for r in rows], ["friend", "friend", "me", "friend"])
        self.assertEqual(rows[3]["text"], "call me [PHONE] or [EMAIL]")
        self.assertEqual(report["edited_markers_removed"], 1)


if __name__ == "__main__":
    unittest.main()
