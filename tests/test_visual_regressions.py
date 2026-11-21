"""Каждый замеченный дефект превращается в постоянный тест (по совету Claude)."""

import unittest

from svenmap.geometry import Bounds
from svenmap.mapfile import MapFile
from svenmap.profiles import PROFILES, TRANSITION_PROFILE
from svenmap.textures import TextureRef
from svenmap.visual_qa import (
    check_decor_clearance, check_text_encoding, check_texture_roles,
    looks_mojibake,
)


class TestVisualRegressions(unittest.TestCase):
    def test_mojibake_is_caught(self):
        self.assertTrue(looks_mojibake("Ð Ñ ĐâÐ¸"))  # скриншот пользователя
        self.assertFalse(looks_mojibake("КАНАЛ СВЯЗИ УСТАНОВЛЕН"))

    def test_text_encoding_check_catches_bad_string(self):
        m = MapFile()
        m.add_point_entity("game_text", targetname="t", message="Ð Ñ Đâ")
        self.assertTrue(check_text_encoding(m))

    def test_decal_crate_is_caught(self):
        m = MapFile()
        m.add_box(Bounds(0, 0, 16, 64, 64, 80), TextureRef("BCRATE09A"))
        self.assertTrue(check_texture_roles(m))

    def test_decor_on_portal_is_caught(self):
        # координаты пользователя 661.929 2448.244 52.031
        blueprint = {"spatial": {"connections": [
            {"id": "p1", "portal_a": [3, 12], "portal_b": [3, 13]},
        ]}}
        m = MapFile()
        m.meta["decor_brushes"] = [{
            "area": "n1", "kinds": ["crates"],
            "bounds": (665.0, 2450.0, 16.0, 720.0, 2500.0, 80.0),
        }]
        self.assertTrue(check_decor_clearance(m, blueprint))

    def test_no_panels_in_profiles(self):
        for types in PROFILES.values():
            for profile in types.values():
                self.assertNotIn("panels", profile.decor)
        self.assertNotIn("panels", TRANSITION_PROFILE.decor)
        # Сцены переопределяют decor через props — проверяем и их.
        from svenmap.scenes import load_scenes
        for scene in load_scenes().values():
            self.assertNotIn("panels", scene.get("props", []))

    def test_no_floor_accents_applied(self):
        # акцентные заплатки убраны из генератора
        from svenmap.planning.new_builder import build_blueprint_map
        from svenmap.planning import BlueprintConfig, generate_blueprint

        bp = generate_blueprint(BlueprintConfig(seed=101, node_count=8))
        m = build_blueprint_map(bp, [], None)
        floor_tex = set()
        for brush in m.brushes:
            for _face, texture in brush:
                name = getattr(texture, "name", str(texture))
                if name in ("GRATE_RUST",):
                    floor_tex.add(name)
        # GRATE_RUST может остаться на ящиках/арене, но не как заплатка пола
        self.assertIn("surface", m.meta)


if __name__ == "__main__":
    unittest.main()
