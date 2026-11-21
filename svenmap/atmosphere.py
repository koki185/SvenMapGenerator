"""Событийный свет, звук и нарратив (P4).

Данные — закрытый словарь narrative.json. Модель выбирает только имя пресета.
Генератор добавляет:
  - фоновый звук (ambient_generic) в каждой комнате;
  - музыку по зоне (ambient_music, необязательно);
  - вступление (game_text через trigger_auto + multi_manager);
  - тревогу при открытии двери: красные лампы (изначально выключенные),
    звук сирены и текст.

Проверка существования звуков идёт до записи .map — отсутствующий файл
даёт человекочитаемую ошибку, а не тихую карту.
"""

import json
import os
from typing import List

from .mapfile import num
from .v2_entities import area_center_world, GRID, HEIGHT, FLOOR_T

_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "narrative.json",
)
_CACHE = {}


def load_presets(path: str = "") -> dict:
    path = path or _PATH
    if path not in _CACHE:
        with open(path, encoding="utf-8") as f:
            _CACHE[path] = json.load(f)
    return _CACHE[path]


def preset_names() -> tuple:
    return tuple(sorted(load_presets()))


def validate_assets(preset_name: str, game_dir: str) -> List[str]:
    """Проверить, что звуки пресета реально есть в установке игры."""
    preset = load_presets().get(preset_name)
    if not preset:
        return ["неизвестный нарративный пресет: " + str(preset_name)]
    issues = []
    for key in ("ambient", "music", "alarm_sound"):
        rel = preset.get(key)
        if not rel:
            continue
        path = os.path.join(game_dir, "svencoop", "sound", rel.replace("/", os.sep))
        if not os.path.isfile(path):
            issues.append(
                "{}: звук {!r} не найден в svencoop\\sound".format(key, rel)
            )
    return issues


def add_atmosphere(m, blueprint: dict, preset_name: str,
                   game_dir: str) -> dict:
    """Добавить звук, вступление и тревогу. Возвращает сводку."""
    presets = load_presets()
    if preset_name not in presets:
        preset_name = preset_names()[0]
    preset = presets[preset_name]
    graph = blueprint["graph"]
    areas = blueprint["spatial"]["areas"]

    # 1. Фоновый звук по комнатам.
    ambient_targets = []
    for area in areas:
        cx, cy = area_center_world(area)
        base = area.get("floor", 0) * (HEIGHT + FLOOR_T)
        name = "p4_amb_" + area["node_id"]
        m.add_point_entity(
            "ambient_generic",
            targetname=name,
            origin="{} {} {}".format(num(cx), num(cy), base + 96),
            message=preset["ambient"],
            health="4",
            playmode="2",          # Loop
            attenuation="3",
        )
        ambient_targets.append(name)

    # 2. Музыка по зоне (в стартовой комнате).
    music_target = ""
    if preset.get("music"):
        spawn = next(
            (a for a in areas if a["node_id"] == graph.get("start")), None
        )
        if spawn:
            cx, cy = area_center_world(spawn)
            music_target = "p4_music"
            m.add_point_entity(
                "ambient_music",
                targetname=music_target,
                origin="{} {} {}".format(num(cx), num(cy), 96),
                message=preset["music"],
                volume="4",
                spawnflags="2",    # Loop, не Start Silent
            )

    # 3. Вступление: trigger_auto -> multi_manager -> game_text.
    m.add_point_entity(
        "game_text", targetname="p4_intro_text",
        message=preset["intro"], x="-1", y="0.72",
        effect="0", holdtime="5", fxtime="0.5",
        fadein="0.5", fadeout="1.0",
        color="255 220 120", spawnflags="1",  # All Players
    )
    m.add_point_entity(
        "multi_manager", targetname="p4_intro_mm",
        p4_intro_text="0",
    )
    m.add_point_entity(
        "trigger_auto", targetname="p4_intro_auto",
        target="p4_intro_mm", delay="2", triggerstate="1",
        spawnflags="1",
    )

    # 4. Тревога: красные лампы изначально выключены, включаются событием.
    alarm_lights = []
    for area in areas[:3]:
        cx, cy = area_center_world(area)
        base = area.get("floor", 0) * (HEIGHT + FLOOR_T)
        name = "p4_alarm_light_" + area["node_id"]
        m.add_point_entity(
            "light", targetname=name,
            origin="{} {} {}".format(num(cx), num(cy), base + HEIGHT - 32),
            _light="{} {}".format(preset["emergency_color"],
                                  preset["emergency_brightness"]),
            _falloff="0", _fade="1.0", style="0",
            spawnflags="1",        # Initially dark
        )
        alarm_lights.append(name)

    m.add_point_entity(
        "ambient_generic", targetname="p4_alarm_sound",
        origin="0 0 64", message=preset["alarm_sound"],
        health="9", playmode="1",   # Play Once
    )
    m.add_point_entity(
        "game_text", targetname="p4_alarm_text",
        message=preset["alarm"], x="-1", y="0.66",
        effect="0", holdtime="5", fxtime="0.5",
        fadein="0.3", fadeout="1.0",
        color="255 90 70", spawnflags="1",
    )
    mm_keys = {name: "0" for name in alarm_lights}
    mm_keys["p4_alarm_sound"] = "0"
    mm_keys["p4_alarm_text"] = "0.4"
    m.add_point_entity("multi_manager", targetname="p4_alarm_mm", **mm_keys)

    # Подключаем тревогу к открытию двери, если механика есть.
    hook = "auto (10s)"
    for entity in m.entities:
        if (entity.get("classname") == "multi_manager"
                and entity.get("targetname") == "door_manager"):
            entity["p4_alarm_mm"] = "0"
            hook = "door_manager"
            break
    if hook != "door_manager":
        m.add_point_entity(
            "trigger_auto", targetname="p4_alarm_auto",
            target="p4_alarm_mm", delay="10", triggerstate="1",
            spawnflags="1",
        )

    return {
        "preset": preset_name,
        "ambient_sources": len(ambient_targets),
        "music": bool(music_target),
        "alarm_lights": len(alarm_lights),
        "alarm_hook": hook,
    }
