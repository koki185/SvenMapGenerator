"""Проверка профилей оформления и визуальных метрик (P5)."""

import os
import unittest

from svenmap.geometry import Bounds
from svenmap.mapfile import MapFile, TEXTURE_AXES
from svenmap.profiles import PROFILES, get_profile
from svenmap.textures import TextureLibrary
from svenmap.visual_qa import check_face_axes, evaluate_visual

GAME = r"K:\SteamLibrary\steamapps\common\Sven Co-op"


class TestProfiles(unittest.TestCase):
    def test_floor_and_ceiling_differ(self):
        for theme, types in PROFILES.items():
            for name, profile in types.items():
                self.assertNotEqual(
                    profile.floor, profile.ceiling,
                    "{}/{}: пол и потолок одинаковые".format(theme, name),
                )

    def test_new_roles_present(self):
        for types in PROFILES.values():
            for profile in types.values():
                for attr in ("floor_accent", "ceiling_detail", "trim",
                             "insert", "lamp", "column"):
                    self.assertTrue(getattr(profile, attr),
                                    "пустая роль " + attr)

    @unittest.skipUnless(os.path.isdir(GAME), "игра не установлена")
    def test_all_textures_exist_in_wads(self):
        lib = TextureLibrary(GAME)
        missing = set()
        for types in PROFILES.values():
            for profile in types.values():
                for attr in ("floor", "wall", "ceiling", "accent",
                             "floor_accent", "ceiling_detail", "trim",
                             "insert", "lamp", "column"):
                    name = getattr(profile, attr)
                    if not name:
                        continue
                    if lib.dimensions(name) is None:
                        missing.add(name)
        self.assertEqual(missing, set(), "нет в WAD: " + str(sorted(missing)))

    def test_face_axes_are_in_plane(self):
        m = MapFile()
        m.add_box(Bounds(0, 0, 0, 192, 192, 16), "TEST")
        self.assertEqual(check_face_axes(m), [])
        self.assertTrue(TEXTURE_AXES)

    def test_visual_evaluate(self):
        m = MapFile()
        m.meta["surface"] = {
            "r1": {"floor": ["FLOOR"], "ceiling": ["CEIL"]},
        }
        m.add_point_entity("light", targetname="room_light_r1")
        result = evaluate_visual(m)
        self.assertTrue(result["passed"])
        self.assertEqual(result["warnings"], [])


if __name__ == "__main__":
    unittest.main()
