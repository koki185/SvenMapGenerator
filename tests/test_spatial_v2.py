"""PR-2 acceptance tests: размещение графа."""

import math
import unittest

from svenmap.planning import (
    BlueprintConfig, SpatialConfig, generate_blueprint, generate_topology,
    place_spatial, TopologyConfig,
)
from svenmap.planning.models import validate_topology
from svenmap.planning.spatial_metrics import evaluate_spatial


class TestSpatialV2(unittest.TestCase):
    def test_determinism(self):
        for seed in range(1, 11):
            a = generate_blueprint(BlueprintConfig(seed=seed))
            b = generate_blueprint(BlueprintConfig(seed=seed))
            self.assertEqual(a, b, "seed {} не детерминирован".format(seed))

    def test_placement_constraints(self):
        for seed in range(1, 31):
            graph = generate_topology(TopologyConfig(seed=seed))
            layout = place_spatial(graph, SpatialConfig(), seed=seed)
            self.assertEqual(set(layout.areas), set(graph.nodes))
            areas = list(layout.areas.values())
            for i, a in enumerate(areas):
                for b in areas[i + 1:]:
                    overlap = (
                        a.x < b.x + b.w and b.x < a.x + a.w
                        and a.y < b.y + b.h and b.y < a.y + a.h
                    )
                    self.assertFalse(overlap, "seed {}: пересечение".format(seed))
            done = {(c.a, c.b) for c in layout.connections}
            done |= {(b, a) for a, b in done}
            for edge in graph.edges:
                if edge.mandatory:
                    self.assertIn(
                        (edge.a, edge.b), done,
                        "seed {}: не реализовано обязательное ребро".format(seed),
                    )
            metrics = evaluate_spatial(graph, layout)
            self.assertTrue(math.isfinite(metrics["score"]))

    def test_blueprint_shape(self):
        data = generate_blueprint(BlueprintConfig(seed=42))
        self.assertIn("graph", data)
        self.assertIn("spatial", data)
        self.assertIn("topology_metrics", data)
        self.assertEqual(data["graph"]["version"], 2)
        self.assertGreater(len(data["spatial"]["areas"]), 0)


if __name__ == "__main__":
    unittest.main()
