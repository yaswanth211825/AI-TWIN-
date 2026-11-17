"""Tests for step 9 comparison and the blind-test sheet, with made-up text."""

import unittest

from pipeline.step9_compare import APP, blind_sheet, compare


def exchange(i, reply, private=False):
    return {"exchange_id": f"id{i}", "ts": f"2026-01-{i + 1:02d}T10:00:00", "private": private,
            "context": [{"sender": "friend", "text": f"msg {i}"}], "reply": reply}


class CompareTests(unittest.TestCase):
    def test_app_beating_baseline_has_positive_interval(self):
        refs = ["ha vachayi ra"] * 20
        report = compare({APP: refs, "random_reply": ["certainly, here you go"] * 20}, refs)
        mean, lo, hi = report["app_minus_baseline"]["beta2"]["random_reply"]
        self.assertGreater(lo, 0)
        self.assertEqual(report["chrF_mean"]["beta2"][APP], 100.0)


class BlindSheetTests(unittest.TestCase):
    def test_skips_private_and_key_matches_sheet(self):
        test = [exchange(i, f"real reply {i}", private=(i == 0)) for i in range(6)]
        app = {e["exchange_id"]: f"twin reply {i}" for i, e in enumerate(test)}
        sheet, key = blind_sheet(test, app, n=5)
        self.assertEqual(len(key), 5)
        self.assertNotIn("id0", [k["exchange_id"] for k in key])
        self.assertNotIn("real reply 0", sheet)
        for k in key:
            i = k["exchange_id"][2:]
            self.assertIn(f"**{k['real']}:** real reply {i}", sheet)


if __name__ == "__main__":
    unittest.main()
