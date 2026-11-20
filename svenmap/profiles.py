"""Профили оформления помещений.

Профиль задаёт не только текстуры, но и набор декоративных компонентов,
а также цвет и яркость света. Все имена текстур проверены в halflife.wad.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RoomProfile:
    floor: str
    wall: str
    ceiling: str
    accent: str
    light_color: str
    light_brightness: int
    decor: tuple


DEFAULT_PROFILE = RoomProfile(
    floor="LAB1_FLOOR1",
    wall="C1A0_LABW1",
    ceiling="BABTECH_CEIL01",
    accent="METAL_BORD01",
    light_color="255 255 255",
    light_brightness=200,
    decor=("panels",),
)

PROFILES = {
    "industrial": {
        "spawn": RoomProfile(
            "LAB1_FLOOR1", "C1A0_LABW1", "BABTECH_CEIL01", "LAB1_PANEL1",
            "255 255 255", 220, ("columns", "panels", "pipes"),
        ),
        "corridor": RoomProfile(
            "LAB1_FLOOR1", "METAL_WALL01B", "BABTECH_CEIL01", "C3A2A_PIPE1",
            "200 225 255", 180, ("pipes", "panels"),
        ),
        "lab": RoomProfile(
            "LAB1_FLOOR1", "C1A0_LABW1", "BABTECH_CEIL01", "LAB1_PANEL2",
            "190 230 255", 220, ("columns", "panels", "pipes"),
        ),
        "storage": RoomProfile(
            "SUBWAY_FLOOR1", "BASEWALL01A", "BABTECH_CEIL01", "BCRATE09A",
            "255 210 160", 150, ("crates", "pipes"),
        ),
        "arena": RoomProfile(
            "SUBWAY_FLOOR1", "METAL_WALL04", "BABTECH_CEIL01", "GRATE_RUST",
            "255 180 150", 240, ("columns", "platform"),
        ),
    },
}


def get_profile(theme, area_type):
    theme_profiles = PROFILES.get(theme, {})
    return theme_profiles.get(area_type, DEFAULT_PROFILE)
