"""Межкарточная логика кампании (этап 9).

Собирает то, что отличает карту саги от одиночной:
- несколько точек спавна для коопа;
- trigger_changelevel в конце обычной карты;
- арену с волнами в финальной карте.
Ключи сущностей сверены с sven-coop.fgd и .ent карт SecretCity.
"""

from .geometry import Bounds
from .textures import TextureRef

TRIGGER_TEXTURE = TextureRef("AAATRIGGER", 1.0, 1.0)
# Видимая текстура выхода, чтобы игрок понимал, где changelevel.
EXIT_TEXTURE = TextureRef("EXIT1", 1.0, 1.0)
# Надпись LEVEL CHANGE — спрайт из hl_c02_a2 (а не текстура триггера:
# движок не рендерит brushes с classname trigger_*).
EXIT_SPRITE = "sprites/level_change.spr"


def add_multi_spawn(m, spec, count=4):
    """Несколько info_player_deathmatch рядом со стартом.

    Одна точка info_player_start остаётся «главной», остальные нужны,
    чтобы игроки не появлялись друг в друге.
    """
    cx, cy = spec.area_center(spec.start)
    z = spec.floor_thickness + 48
    offsets = ((-64, -64), (64, -64), (-64, 64), (64, 64),
               (-128, 0), (128, 0), (0, -128), (0, 128))
    points = offsets[:max(0, count)]
    for dx, dy in points:
        m.add_point_entity(
            "info_player_deathmatch",
            origin="{} {} {}".format(int(cx + dx), int(cy + dy), int(z)),
            angles="0 0 0",
        )


def add_changelevel(m, spec, next_map):
    """Выход в следующую карту кампании, внутри целевой комнаты."""
    cx, cy = spec.area_center(spec.goal)
    z0 = spec.floor_thickness
    m.add_brush_entity(
        "trigger_changelevel",
        Bounds(cx - 32, cy - 32, z0, cx + 32, cy + 32, z0 + 80),
        EXIT_TEXTURE,
        targetname="chapter_exit",
        map=next_map,
        spawnflags="0",
        keep_inventory="1",
    )
    # Видимая надпись LEVEL CHANGE по образцу hl_c02_a2.
    m.add_point_entity(
        "env_sprite",
        targetname="exit_sign",
        origin="{} {} {}".format(int(cx), int(cy), int(z0 + 72)),
        angles="0 0 0",
        model=EXIT_SPRITE,
        scale="0.25",
        framerate="10.0",
        rendermode="4",       # Solid — цвета спрайта без подсветки
        renderamt="255",
        rendercolor="0 0 0",
        spawnflags="1",       # Start on
    )
    m.meta.setdefault("campaign", {})["changelevel"] = next_map


def add_boss_arena(m, spec, waves=3):
    """Финальная карта: волны через squadmaker вместо changelevel."""
    cx, cy = spec.area_center(spec.goal)
    z = spec.floor_thickness + 40
    types = ("monster_zombie", "monster_hgrunt", "monster_alien_grunt")
    made = []
    for i in range(waves):
        name = "boss_wave_{}".format(i + 1)
        keys = dict(
            targetname=name,
            monstertype=types[i % len(types)],
            monstercount=str(4 + i * 2),
            delay="4",
            m_imaxlivechildren="3",
            spawnflags="33",  # Start ON + Auto Size BBox
            spawn_mode="1",
            origin="{} {} {}".format(int(cx), int(cy), int(z)),
            angles="0 0 0",
        )
        if i > 0:
            # Волна выключена, пока её не вызовет предыдущая.
            keys["spawnflags"] = "32"
        if i < waves - 1:
            keys["target"] = "boss_wave_{}".format(i + 2)
        m.add_point_entity("squadmaker", **keys)
        made.append(name)

    # Первая волна запускается входом игрока в финальную зону.
    m.add_brush_entity(
        "trigger_once",
        Bounds(cx - 48, cy - 48, spec.floor_thickness,
               cx + 48, cy + 48, spec.floor_thickness + 80),
        TRIGGER_TEXTURE,
        targetname="boss_start",
        target="boss_wave_1",
    )
    m.meta.setdefault("campaign", {})["boss_waves"] = made
