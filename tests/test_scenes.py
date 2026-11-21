"""Библиотека сцен и наложение на комнаты (P3.2)."""

import unittest

from svenmap.campaign_schema import validate_data
from svenmap.scenes import (
    assign_scenes, load_scenes, scene_names, scene_profile,
    scene_variety, scene_warnings, validate_scene_names,
)


class TestScenes(unittest.TestCase):
    def test_library_is_closed(self):
        scenes = load_scenes()
        self.assertGreaterEqual(len(scenes), 8)
        self.assertEqual(set(scene_names()), set(scenes))
        for name, scene in scenes.items():
            self.assertTrue(scene["fits_roles"], name)
            self.assertTrue(scene["props"], name)
            self.assertEqual(len(scene["min_size"]), 2)

    def test_props_are_known_decor_kinds(self):
        from svenmap.decor import GENERATORS
        for scene in load_scenes().values():
            for prop in scene["props"]:
                self.assertIn(prop, GENERATORS)

    def test_scene_profile_overrides_light(self):
        p = scene_profile("server_hall")
        self.assertEqual(p.light_color, "150 220 255")
        self.assertEqual(p.light_brightness, 170)
        self.assertIn("panels", p.decor)

    def test_assign_scenes_deterministic(self):
        from svenmap.planning import BlueprintConfig, generate_blueprint
        bp = generate_blueprint(BlueprintConfig(seed=101, node_count=8))
        a = assign_scenes(bp, seed=101)
        b = assign_scenes(bp, seed=101)
        self.assertEqual(a, b)
        self.assertEqual(len(a), len(bp["spatial"]["areas"]))
        self.assertGreater(scene_variety(a), 0.0)

    def test_no_warnings_for_assigned_rooms(self):
        from svenmap.planning import BlueprintConfig, generate_blueprint
        bp = generate_blueprint(BlueprintConfig(seed=101, node_count=8))
        assignments = assign_scenes(bp, seed=101)
        self.assertEqual(scene_warnings(bp, assignments), [])

    def test_schema_rejects_unknown_scene(self):
        self.assertEqual(validate_scene_names(["lobby"]), [])
        self.assertIn("nope", validate_scene_names(["nope"]))
        base = {
            "name": "t",
            "chapters": [
                {"name": "a", "seed": 1, "scenes": ["lobby"]},
                {"name": "b", "seed": 2, "final": True},
            ],
        }
        self.assertEqual(validate_data(base), [])
        base["chapters"][0]["scenes"] = ["reactor_core"]
        self.assertTrue(any("scenes" in i.path for i in validate_data(base)))


if __name__ == "__main__":
    unittest.main()
