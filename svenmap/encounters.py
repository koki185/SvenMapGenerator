"""Враги по триггерам (этап 13).

Монстры не стоят на карте заранее: вход игрока в зону включает
squadmaker, который выпускает волну. Это паттерн SecretCity
(environment-as-atmosphere), а не просто «наставленные монстры».
"""

from .geometry import Bounds
from .textures import TextureRef

TRIGGER_TEXTURE = TextureRef("AAATRIGGER", 1.0, 1.0)
MONSTER_TYPES = ("monster_zombie", "monster_hgrunt", "monster_alien_grunt")


def add_encounters(m, spec, seed=0, count=2):
    """Добавить N засад — по одной на комнату вдоль главного пути."""
    import random

    rng = random.Random("encounter:{}".format(seed))
    areas = [
        a for a in spec.areas
        if a.id not in (spec.start, spec.goal)
        and not a.id.startswith("b")
    ]
    rng.shuffle(areas)

    made = []
    for index, area in enumerate(areas[:count], start=1):
        cx, cy = spec.area_center(area.id)
        z = spec.floor_thickness + 40
        wave_name = "encounter_wave_{}".format(index)
        m.add_point_entity(
            "squadmaker",
            targetname=wave_name,
            monstertype=MONSTER_TYPES[index % len(MONSTER_TYPES)],
            monstercount=str(3 + index),
            delay="3",
            m_imaxlivechildren="3",
            spawnflags="32",  # выключен, ждёт триггера
            spawn_mode="1",
            origin="{} {} {}".format(int(cx), int(cy), int(z)),
            angles="0 0 0",
        )
        m.add_brush_entity(
            "trigger_once",
            Bounds(cx - 48, cy - 48, spec.floor_thickness,
                   cx + 48, cy + 48, spec.floor_thickness + 80),
            TRIGGER_TEXTURE,
            targetname="encounter_trigger_{}".format(index),
            target=wave_name,
        )
        made.append(wave_name)

    m.meta.setdefault("encounters", made)
    return made
