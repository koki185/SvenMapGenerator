"""PR-6: геометрия по клеточным маскам."""

import unittest

from svenmap.planning import (
    BlueprintConfig, build_blueprint_map, generate_blueprint,
)


class TestNewBuilder(unittest.TestCase):
    def test_mask_geometry(self):
        blueprint = generate_blueprint(BlueprintConfig(seed=42, floors=1))
        non_rect = sum(
            1 for v in blueprint["shapes"].values() if v["shape"] != "rect"
        )
        self.assertGreater(non_rect, 0)
        m = build_blueprint_map(blueprint, [], None)
        self.assertGreater(len(m.brushes), 200)

    def test_determinism(self):
        blueprint = generate_blueprint(BlueprintConfig(seed=7, floors=1))
        a = build_blueprint_map(blueprint, [], None).to_text()
        b = build_blueprint_map(blueprint, [], None).to_text()
        self.assertEqual(a, b)

    def test_blueprint_with_shapes(self):
        blueprint = generate_blueprint(BlueprintConfig(seed=1, floors=1))
        self.assertIn("shapes", blueprint)
        m = build_blueprint_map(blueprint, [], None)
        self.assertTrue(all(face.points for brush in m.brushes
                            for face, _texture in brush))


if __name__ == "__main__":
    unittest.main()
