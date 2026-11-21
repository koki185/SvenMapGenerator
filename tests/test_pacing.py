"""Пейсинг-профили и метрики ритма (P3.1)."""

import json
import os
import unittest

from svenmap.campaign_schema import validate_data
from svenmap.pacing import (
    default_pacing, evaluate, load_profiles, profile_names,
    rhythm_metrics,
)


class TestPacing(unittest.TestCase):
    def test_three_profiles_load(self):
        profiles = load_profiles()
        self.assertEqual(len(profiles), 3)
        self.assertEqual(set(profile_names()),
                         {"short_6", "standard_8", "dense_10"})
        for profile in profiles.values():
            self.assertIn("roles", profile)
            self.assertIn("max_combat_in_row", profile)
            self.assertIn("min_rest_every", profile)
            self.assertIn("combat_share", profile)

    def test_default_by_rooms(self):
        self.assertEqual(default_pacing(6), "short_6")
        self.assertEqual(default_pacing(8), "standard_8")
        self.assertEqual(default_pacing(11), "dense_10")

    def test_rhythm_metrics(self):
        roles = ["intro", "corridor", "combat", "combat", "rest", "puzzle",
                 "finale"]
        m = rhythm_metrics(roles)
        # 3 боевых (2 combat + finale) из 7.
        self.assertAlmostEqual(m["combat_share"], 3 / 7, places=3)
        self.assertEqual(m["max_combat_run"], 2)
        # Между стартом и передышкой: corridor + 2 combat = 3.
        self.assertEqual(m["rest_gap"], 3)

    def test_evaluate_real_blueprint(self):
        from svenmap.planning import BlueprintConfig, generate_blueprint
        bp = generate_blueprint(BlueprintConfig(seed=101, node_count=8))
        result = evaluate(bp, "standard_8")
        self.assertIn("profile", result)
        self.assertEqual(result["profile"], "standard_8")
        self.assertTrue(result["roles"])
        self.assertIsInstance(result["warnings"], list)

    def test_unknown_profile_falls_back(self):
        from svenmap.planning import BlueprintConfig, generate_blueprint
        bp = generate_blueprint(BlueprintConfig(seed=7, node_count=7))
        result = evaluate(bp, "no_such_profile")
        self.assertIn(result["profile"], profile_names())

    def test_schema_rejects_unknown_pacing(self):
        base = {
            "name": "t",
            "chapters": [
                {"name": "a", "seed": 1, "pacing": "standard_8"},
                {"name": "b", "seed": 2, "final": True},
            ],
        }
        self.assertEqual(validate_data(base), [])
        base["chapters"][0]["pacing"] = "epic_20"
        self.assertTrue(any("pacing" in i.path for i in validate_data(base)))


if __name__ == "__main__":
    unittest.main()
