"""Tests for retrieval, metrics and step 5 prompt building, with made-up text."""

import unittest

from pipeline.metrics import StyleProfile, chrf, summarize
from pipeline.retrieval import BM25
from pipeline.step5_baseline import build_messages


class ChrfTests(unittest.TestCase):
    def test_identical_is_100(self):
        self.assertAlmostEqual(chrf("ha vachayi", "ha vachayi"), 100.0)

    def test_spelling_variant_scores_high_unrelated_low(self):
        self.assertGreater(chrf("ha vachai", "ha vachayi"), 60)
        self.assertLess(chrf("certainly, here you go", "ha vachayi"), 25)

    def test_empty(self):
        self.assertEqual(chrf("", "ha"), 0.0)


class BM25Tests(unittest.TestCase):
    def test_best_match_first(self):
        index = BM25(["tcs results vachaya", "java or python", "dinner ayinda"])
        self.assertEqual(index.search("TCS results?", k=1)[0][0], 0)

    def test_no_match_returns_empty(self):
        self.assertEqual(BM25(["java"]).search("zzz", k=3), [])


class StyleTests(unittest.TestCase):
    def setUp(self):
        replies = ["ha vachayi", "ha cheppu ra", "vachayi ra", "cheppu cheppu", "ra ra ra", "the java"] * 2
        self.profile = StyleProfile(replies, english={"the", "java", "ha"})

    def test_telugu_words_learned_not_english(self):
        self.assertIn("vachayi", self.profile.telugu)
        self.assertNotIn("java", self.profile.telugu)

    def test_assistant_speak_detected(self):
        self.assertTrue(self.profile.score("Certainly! I'd be happy to help.")["assistant_speak"])
        self.assertFalse(self.profile.score("ha cheppu ra")["assistant_speak"])

    def test_summary_of_perfect_copy(self):
        refs = ["ha vachayi\nra", "cheppu"]
        s = summarize(refs, refs, self.profile)
        self.assertEqual((s["chrF"], s["length_ratio_median"], s["length_error"]), (100.0, 1.0, 0.0))


class PromptTests(unittest.TestCase):
    EXCHANGE = {"context": [{"sender": "friend", "text": "bro free aa?"}, {"sender": "me", "text": "ha"},
                            {"sender": "friend", "text": "TCS results?"}]}

    def test_roles_and_examples(self):
        msgs = build_messages(self.EXCHANGE, [{"embed_text": "results?", "reply": "vachayi ra"}])
        self.assertEqual([m["role"] for m in msgs], ["system", "user", "assistant", "user"])
        self.assertIn("TCS results?", msgs[-1]["content"])
        self.assertIn("Yaswanth replied: vachayi ra", msgs[-1]["content"])

    def test_prompt_only_has_no_examples(self):
        self.assertEqual(build_messages(self.EXCHANGE, None)[-1]["content"], "TCS results?")


if __name__ == "__main__":
    unittest.main()
