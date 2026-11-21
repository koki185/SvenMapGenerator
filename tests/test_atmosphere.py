"""Событийный свет, звук и нарратив (P4)."""

import os
import unittest

from svenmap.atmosphere import (
    add_atmosphere, load_presets, preset_names, validate_assets,
)
from svenmap.campaign_schema import validate_data
from svenmap.planning import BlueprintConfig, build_blueprint_map, generate_blueprint

GAME = r"K:\SteamLibrary\steamapps\common\Sven Co-op"


class TestAtmosphere(unittest.TestCase):
    def test_presets_load(self):
        self.assertEqual(len(load_presets()), 4)
        self.assertEqual(set(preset_names()),
                         {"quiet_lab", "ventilation", "security", "boss"})

    @unittest.skipUnless(os.path.isdir(GAME), "игра не установлена")
    def test_assets_exist(self):
        for name in preset_names():
            self.assertEqual(validate_assets(name, GAME), [], name)

    def test_unknown_preset(self):
        self.assertTrue(validate_assets("no_such_preset", GAME))

    def test_entities_added(self):
        bp = generate_blueprint(BlueprintConfig(seed=101, node_count=8))
        m = build_blueprint_map(bp, [], None)
        summary = add_atmosphere(m, bp, "quiet_lab", GAME)
        names = {e.get("targetname") for e in m.entities}
        self.assertIn("p4_intro_text", names)
        self.assertIn("p4_intro_mm", names)
        self.assertIn("p4_intro_auto", names)
        self.assertIn("p4_alarm_mm", names)
        self.assertIn("p4_alarm_sound", names)
        self.assertEqual(summary["ambient_sources"],
                         len(bp["spatial"]["areas"]))
        self.assertGreater(summary["alarm_lights"], 0)

    def test_door_hook(self):
        bp = generate_blueprint(BlueprintConfig(seed=7, node_count=7))
        m = build_blueprint_map(bp, [], None)
        m.add_point_entity("multi_manager", targetname="door_manager")
        summary = add_atmosphere(m, bp, "security", GAME)
        self.assertEqual(summary["alarm_hook"], "door_manager")
        manager = next(e for e in m.entities
                       if e.get("targetname") == "door_manager")
        self.assertIn("p4_alarm_mm", manager)

    def test_schema_narrative(self):
        base = {
            "name": "t",
            "chapters": [
                {"name": "a", "seed": 1, "narrative": "boss"},
                {"name": "b", "seed": 2, "final": True},
            ],
        }
        self.assertEqual(validate_data(base), [])
        base["chapters"][0]["narrative"] = "epic_cutscene"
        self.assertTrue(any("narrative" in i.path for i in validate_data(base)))


if __name__ == "__main__":
    unittest.main()
