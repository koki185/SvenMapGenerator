"""Автоподбор seed по композиции (P3.4)."""

import os
import unittest

from svenmap.campaign import load_campaign
from svenmap.seed_selector import (
    evaluate_seed, format_candidates, propose,
)

CAMPAIGN = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "campaign.json",
)


class TestSeedSelector(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.campaign = load_campaign(CAMPAIGN)
        cls.chapter = cls.campaign.chapters[0]

    def test_evaluate_seed_structure(self):
        c = evaluate_seed(self.chapter, 109)
        self.assertEqual(c.seed, 109)
        self.assertEqual(c.delta, 8)
        self.assertIsInstance(c.passed, bool)
        self.assertIsInstance(c.issues, list)
        self.assertIn("variety", c.metrics)

    def test_propose_limits_and_excludes_used(self):
        candidates = propose(self.chapter, self.campaign, count=8, top=3)
        self.assertLessEqual(len(candidates), 3)
        used = {ch.seed for ch in self.campaign.chapters}
        used.discard(self.chapter.seed)
        self.assertFalse({c.seed for c in candidates} & used)

    def test_propose_deterministic(self):
        a = propose(self.chapter, self.campaign, count=8, top=3)
        b = propose(self.chapter, self.campaign, count=8, top=3)
        self.assertEqual([c.seed for c in a], [c.seed for c in b])

    def test_sorted_by_issues(self):
        candidates = propose(self.chapter, self.campaign, count=10, top=3)
        counts = [c.issue_count for c in candidates]
        self.assertEqual(counts, sorted(counts))

    def test_format_candidates(self):
        candidates = propose(self.chapter, self.campaign, count=6, top=2)
        text = format_candidates(self.chapter, candidates)
        self.assertIn(self.chapter.name, text)
        self.assertIn("seed в campaign.json не меняется", text.lower())


if __name__ == "__main__":
    unittest.main()
