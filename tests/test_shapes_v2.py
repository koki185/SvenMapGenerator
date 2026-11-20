"""PR-3 acceptance tests: формы комнат."""

import unittest

from svenmap.planning import (
    BlueprintConfig, apply_shapes, generate_blueprint, generate_topology,
    is_connected, make_l, make_rect, make_t, make_u, place_spatial,
    rotate_shape, TopologyConfig,
)


class TestShapesV2(unittest.TestCase):
    def test_shape_constructors(self):
        for cells in (
            make_rect(6, 5), make_l(6, 5, 2, 2),
            make_t(7, 6, 3), make_u(7, 6, 2, 2),
        ):
            self.assertTrue(cells)
            self.assertTrue(is_connected(cells))
        self.assertEqual(len(rotate_shape(make_l(6, 5, 2, 2))),
                         len(make_l(6, 5, 2, 2)))
        self.assertTrue(is_connected(rotate_shape(make_t(7, 6, 3))))

    def test_apply_shapes(self):
        for seed in range(1, 31):
            graph = generate_topology(TopologyConfig(seed=seed))
            layout = place_spatial(graph, seed=seed)
            shapes = apply_shapes(graph, layout, seed=seed)
            self.assertEqual(set(shapes), set(layout.areas))
            for node_id, data in shapes.items():
                cells = {tuple(c) for c in data["cells"]}
                self.assertTrue(cells, "seed {} пустая форма".format(seed))
                self.assertTrue(is_connected(cells),
                                "seed {} разорванная форма".format(seed))

    def test_shapes_in_blueprint(self):
        a = generate_blueprint(BlueprintConfig(seed=42))
        b = generate_blueprint(BlueprintConfig(seed=42))
        self.assertEqual(a, b)
        self.assertIn("shapes", a)
        non_rect = [
            v for v in a["shapes"].values() if v["shape"] != "rect"
        ]
        self.assertGreater(len(non_rect), 0)


if __name__ == "__main__":
    unittest.main()
