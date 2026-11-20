"""PR-1 acceptance tests: topology graph без геометрии."""

import math
import unittest

from svenmap.planning import (
    TopologyConfig, generate_topology, validate_topology,
)
from svenmap.planning.topology_metrics import evaluate


class TestTopologyV2(unittest.TestCase):
    def test_determinism(self):
        for seed in range(1, 21):
            config = TopologyConfig(seed=seed)
            a = generate_topology(config).to_dict()
            b = generate_topology(config).to_dict()
            self.assertEqual(a, b, "seed {} не детерминирован".format(seed))

    def test_100_seeds(self):
        for seed in range(1, 101):
            config = TopologyConfig(seed=seed)
            graph = generate_topology(config)
            errors = validate_topology(graph, target_cycles=config.loop_count)
            self.assertEqual(errors, [], "seed {}: {}".format(seed, errors))
            self.assertGreaterEqual(graph.cycle_count, config.loop_count)
            self.assertTrue(any(n.optional for n in graph.nodes.values()))
            metrics = evaluate(graph)
            self.assertTrue(math.isfinite(metrics["score"]))
            self.assertTrue(0.0 <= metrics["score"] <= 1.0)

    def test_no_duplicate_or_self_edges(self):
        for seed in (1, 7, 42, 99):
            graph = generate_topology(TopologyConfig(seed=seed))
            keys = [tuple(sorted((e.a, e.b))) for e in graph.edges]
            self.assertEqual(len(keys), len(set(keys)))
            self.assertTrue(all(e.a != e.b for e in graph.edges))

    def test_zones_and_json(self):
        graph = generate_topology(TopologyConfig(seed=42))
        data = graph.to_dict()
        self.assertEqual(data["version"], 2)
        self.assertEqual(data["start"], "spawn")
        self.assertEqual(data["goal"], "goal")
        self.assertGreaterEqual(len(data["zones"]), 3)
        self.assertEqual(len(data["nodes"]), graph.node_count)
        self.assertEqual(len(data["edges"]), graph.edge_count)


if __name__ == "__main__":
    unittest.main()
