"""Профили оформления помещений.

Профиль задаёт не только текстуры, но и набор декоративных компонентов,
а также цвет и яркость света. Все имена текстур проверены в halflife.wad
и zhlt.wad (контактный лист снят 21.11.2026).

Правила (из разбора скриншота):
- пол и потолок — РАЗНЫЕ текстуры;
- акцентная «наклейка» не заливает комнату, а идёт только на 5–10% клеток;
- у каждой комнаты есть отделка (плинтус/карниз/вставка) и видимая лампа;
- колонна — шахта + база + капитель, а не один brush с акцентом.
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
    # Новые роли поверхностей (P5).
    floor_accent: str = ""
    ceiling_detail: str = ""
    trim: str = ""
    insert: str = ""
    lamp: str = ""
    column: str = ""


DEFAULT_PROFILE = RoomProfile(
    floor="LAB1_FLOOR2A",
    wall="C1A0_LABW4",
    ceiling="BABTECH_CEIL01",
    accent="LAB1_PANEL1",
    light_color="255 245 230",
    light_brightness=180,
    decor=(),
    floor_accent="LAB1_FLOOR3",
    ceiling_detail="BABTECH_CEIL03",
    trim="METAL_BORD01",
    insert="C1A0_LABW2",
    lamp="EMERGLIGHT",
    column="METAL_WALL04",
)

PROFILES = {
    "industrial": {
        "spawn": RoomProfile(
            "LAB1_FLOOR2A", "C1A0_LABW4", "BABTECH_CEIL01",
            "LAB1_PANEL1", "255 245 230", 190,
            ("columns", "pipes"),
            floor_accent="LAB1_FLOOR3",
            ceiling_detail="BABTECH_CEIL03",
            trim="METAL_BORD01",
            insert="C1A0_LABW2",
            lamp="EMERGLIGHT",
            column="METAL_WALL04",
        ),
        "corridor": RoomProfile(
            "SUBWAY_FLOOR1", "METAL_WALL01B", "C3A2_CEIL",
            "C3A2A_PIPE1", "200 225 255", 150,
            ("pipes",),
            floor_accent="GRATE_RUST",
            ceiling_detail="BABTECH_CEIL03",
            trim="METAL_BORD05",
            insert="C1A0_LABW7",
            lamp="SUBWAY_LIGHTS",
            column="METAL_WALL04",
        ),
        "lab": RoomProfile(
            "LAB1_FLOOR2B", "C1A0_LABW1", "CRETE3_CEIL01",
            "LAB1_PANEL2", "190 230 255", 200,
            ("columns", "pipes"),
            floor_accent="LAB1_FLOOR3",
            ceiling_detail="BABTECH_CEIL03",
            trim="BABTECH_BORDL5",
            insert="C1A0_LABW2",
            lamp="SUBWAY_LIGHTS",
            column="METAL_WALL04",
        ),
        "storage": RoomProfile(
            "GRATE_RUST", "C1A0_LABGLU", "FIFTIES_CEIL4",
            "C1A1_CRATE1", "255 210 160", 140,
            ("crates", "pipes"),
            floor_accent="SUBWAY_FLOOR1",
            ceiling_detail="FIFTIES_CEIL5",
            trim="METAL_BORD06",
            insert="LAB1_PANELE",
            lamp="EMERGLIGHT",
            column="BASEWALL01A",
        ),
        "arena": RoomProfile(
            "LAB1_FLOOR3", "METAL_WALL04", "C3A2_CEIL",
            "GRATE_RUST", "255 180 150", 210,
            ("columns", "platform"),
            floor_accent="GRATE_RUST",
            ceiling_detail="BABTECH_CEIL03",
            trim="METAL_BORD03",
            insert="LAB1_PANELF",
            lamp="~LIGHT5D",
            column="METAL_WALL04",
        ),
    },
}


# Коридоры между разными комнатами получают нейтральное оформление —
# это «шлюз», который оправдывает смену темы вместо резкого скачка.
TRANSITION_PROFILE = RoomProfile(
    floor="LAB1_FLOOR3",
    wall="METAL_WALL01B",
    ceiling="C3A2_CEIL",
    accent="METAL_BORD01",
    light_color="210 230 255",
    light_brightness=130,
    decor=("pipes",),
    floor_accent="GRATE_RUST",
    ceiling_detail="BABTECH_CEIL03",
    trim="METAL_BORD01",
    insert="LAB1_PANEL1",
    lamp="SUBWAY_LIGHTS",
    column="METAL_WALL04",
)


def get_profile(theme, area_type):
    theme_profiles = PROFILES.get(theme, {})
    return theme_profiles.get(area_type, DEFAULT_PROFILE)
