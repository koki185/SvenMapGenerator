"""Единый валидатор композиции (P3.3)."""

import unittest

from svenmap.composition_validator import (
    evaluate_composition, _route_metrics, _scene_run,
)
from svenmap.planning import BlueprintConfig, generate_blueprint
from svenmap.scenes import assign_scenes


def _blueprint(seed=101, rooms=8):
    bp = generate_blueprint(BlueprintConfig(seed=seed, node_count=rooms))
    bp["scene_assignments"] = assign_scenes(bp, seed=seed)
    return bp


class TestCompositionValidator(unittest.TestCase):
    def test_all_three_metric_families(self):
        result = evaluate_composition(_blueprint(), "test", "standard_8")
        self.assertIn("rhythm", result["metrics"])
        self.assertIn("variety", result["metrics"])
        self.assertIn("route", result["metrics"])
        self.assertIsInstance(result["passed"], bool)
        self.assertIsInstance(result["issues"], list)

    def test_issues_are_human_readable(self):
        result = evaluate_composition(_blueprint(), "test", "standard_8")
        for issue in result["issues"]:
            self.assertIn("path", issue)
            self.assertIn("message", issue)
            self.assertTrue(issue["message"])

    def test_scene_run_detection(self):
        assignments = {"a": "lobby", "b": "lobby", "c": "lobby", "d": "warehouse"}
        order = ["a", "b", "c", "d"]
        self.assertEqual(_scene_run(assignments, order), 3)

    def test_route_metrics(self):
        bp = _blueprint()
        route = _route_metrics(bp["graph"])
        self.assertIn("critical_path", route)
        self.assertIn("path_ratio", route)
        self.assertIn("branch_with_return", route)
        self.assertGreater(route["path_ratio"], 0.0)

    def test_linear_map_has_no_branch_warning(self):
        bp = generate_blueprint(BlueprintConfig(
            seed=8, node_count=8, branch_count=0, secret_count=0,
        ))
        bp["scene_assignments"] = assign_scenes(bp, seed=8)
        result = evaluate_composition(bp, "linear", "standard_8")
        for issue in result["issues"]:
            self.assertNotIn("развилки", issue["message"])


if __name__ == "__main__":
    unittest.main()
