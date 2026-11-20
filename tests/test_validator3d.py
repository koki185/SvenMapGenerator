"""PR-4 acceptance tests: этажная проходимость и Legacy-совместимость."""

import unittest

from svenmap.geometry import Bounds
from svenmap.planning import BlueprintConfig, generate_blueprint
from svenmap.validator import build_grid, find_path
from svenmap.validator3d import (
    build_floor_graphs, build_traversal_graph, find_path_3d,
    validate_connector, validate_vertical_reachability,
)


class TestValidator3D(unittest.TestCase):
    def test_legacy_2d_still_works(self):
        floor = Bounds(0, 0, 0, 256, 256, 16)
        grid = build_grid([floor], z=24)
        ok, steps, _, _ = find_path(grid, (32, 32), (200, 200))
        self.assertTrue(ok)
        self.assertGreater(steps, 0)

    def test_single_floor_blueprint(self):
        data = generate_blueprint(BlueprintConfig(seed=7, floors=1))
        self.assertTrue(data["vertical_qa"]["passed"])
        self.assertEqual(len(data["spatial"]["vertical_connectors"]), 0)

    def test_two_floor_blueprint(self):
        for seed in (1, 7, 42):
            data = generate_blueprint(BlueprintConfig(seed=seed, floors=2))
            connectors = data["spatial"]["vertical_connectors"]
            self.assertGreater(len(connectors), 0, "seed {}".format(seed))
            self.assertTrue(data["vertical_qa"]["passed"],
                            "seed {}: {}".format(seed, data["vertical_qa"]))
            self.assertTrue(data["vertical_qa"]["path_found"])

    def test_determinism(self):
        a = generate_blueprint(BlueprintConfig(seed=42, floors=2))
        b = generate_blueprint(BlueprintConfig(seed=42, floors=2))
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
