"""Библиотека сцен и их наложение на комнаты blueprint (P3.2).

Сцена — именованный набор: для каких ролей подходит, минимальный размер,
допустимые формы, профиль оформления, свет и компоненты декора. Модель
выбирает только из закрытого списка имён; если сцену не указать, генератор
подберёт её сам по роли комнаты.

Сцены влияют на текстуры, свет и декор — это не просто метаданные.
"""

from dataclasses import replace
import json
import os
from typing import Dict, List

import random

from .pacing import role_by_node
from .profiles import DEFAULT_PROFILE, PROFILES, RoomProfile


def _rng(seed, subsystem):
    """Тот же поток, что planning.rng, но без циклического импорта."""
    return random.Random("{}:{}".format(int(seed), subsystem))

_PROFILES_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "scenes.json",
)
_CACHE: Dict[str, dict] = {}


def load_scenes(path: str = "") -> Dict[str, dict]:
    path = path or _PROFILES_PATH
    if path not in _CACHE:
        with open(path, encoding="utf-8") as f:
            _CACHE[path] = json.load(f)
    return _CACHE[path]


def scene_names() -> tuple:
    return tuple(sorted(load_scenes()))


def scene_profile(name: str) -> RoomProfile:
    """Профиль оформления сцены (текстуры + свет + декор)."""
    scene = load_scenes().get(name)
    if not scene:
        return DEFAULT_PROFILE
    base = PROFILES.get("industrial", {}).get(
        scene.get("profile", ""), DEFAULT_PROFILE
    )
    light = scene.get("light", {})
    return replace(
        base,
        light_color=light.get("color", base.light_color),
        light_brightness=light.get("brightness", base.light_brightness),
        decor=tuple(scene.get("props", ())),
    )


def assign_scenes(blueprint: dict, allowed=(), seed: int = 0) -> Dict[str, str]:
    """Назначить сцены комнатам по роли, форме и детерминированному RNG.

    allowed — закрытый список имён из campaign.json (если модель указала
    свои сцены); пустой значит «выбрать из всех подходящих».
    """
    scenes = load_scenes()
    allowed_set = set(allowed) & set(scenes)
    candidates_pool = allowed_set or set(scenes)
    roles = role_by_node(blueprint["graph"])
    result: Dict[str, str] = {}

    for area in blueprint["spatial"]["areas"]:
        node_id = area["node_id"]
        role = roles.get(node_id, "rest")
        shape = area.get("shape", "rect")
        suitable = [
            name for name in candidates_pool
            if role in scenes[name]["fits_roles"]
        ]
        if not suitable:
            # Роль без сцены: берём первую подходящую по всей библиотеке.
            suitable = [
                name for name in scenes
                if role in scenes[name]["fits_roles"]
            ]
        if not suitable:
            continue
        def fits_size(name):
            min_w, min_h = scenes[name].get("min_size", [2, 2])
            return area["w"] >= min_w and area["h"] >= min_h

        def fits_shape(name):
            shapes = scenes[name].get("shapes", [])
            return not shapes or shape.lower() in [
                s.lower() for s in shapes
            ]

        # Сначала сцены, подходящие и по размеру, и по форме.
        perfect = [n for n in suitable if fits_size(n) and fits_shape(n)]
        sized = [n for n in suitable if fits_size(n)]
        shaped = [n for n in suitable if fits_shape(n)]
        pool = perfect or sized or shaped or suitable
        rng = _rng(seed, "scene_" + node_id)
        result[node_id] = sorted(pool)[rng.randrange(len(pool))]
    return result


def scene_variety(assignments: Dict[str, str]) -> float:
    if not assignments:
        return 0.0
    return round(len(set(assignments.values())) / len(assignments), 4)


def scene_warnings(blueprint: dict, assignments: Dict[str, str]) -> List[str]:
    """Человекочитаемые предупреждения: размер, форма, неизвестная роль."""
    scenes = load_scenes()
    roles = role_by_node(blueprint["graph"])
    issues = []
    for area in blueprint["spatial"]["areas"]:
        node_id = area["node_id"]
        name = assignments.get(node_id)
        if not name or name not in scenes:
            continue
        scene = scenes[name]
        min_w, min_h = scene.get("min_size", [2, 2])
        if area["w"] < min_w or area["h"] < min_h:
            issues.append(
                "{}: комната {}x{} меньше минимума сцены {} ({}x{})"
                .format(node_id, area["w"], area["h"], name, min_w, min_h)
            )
        shape = area.get("shape", "rect")
        shapes = scene.get("shapes", [])
        if shapes and shape.lower() not in [s.lower() for s in shapes]:
            issues.append(
                "{}: форма {} не подходит сцене {} ({})"
                .format(node_id, shape, name, ", ".join(shapes))
            )
    return issues


def validate_scene_names(names) -> List[str]:
    """Проверка списка сцен из campaign.json — для схемы валидатора."""
    known = set(scene_names())
    return [name for name in (names or []) if name not in known]


def add_scene_decor(m, blueprint: dict, spec, seed: int = 0) -> int:
    """Поставить компоненты сцены в комнаты. Возвращает число комнат с декором."""
    from .decor import decorate

    assignments = blueprint.get("scene_assignments", {})
    made = 0
    for area in blueprint["spatial"]["areas"]:
        scene_name = assignments.get(area["node_id"])
        if not scene_name:
            continue
        cells = area.get("cells")
        if cells:
            world = [(area["x"] + c[0], area["y"] + c[1]) for c in cells]
        else:
            world = [
                (x, y)
                for x in range(area["x"], area["x"] + area["w"])
                for y in range(area["y"], area["y"] + area["h"])
            ]
        if not world:
            continue
        grid = 192
        x0 = min(c[0] for c in world) * grid
        y0 = min(c[1] for c in world) * grid
        x1 = (max(c[0] for c in world) + 1) * grid
        y1 = (max(c[1] for c in world) + 1) * grid
        profile = scene_profile(scene_name)
        if not profile.decor:
            continue
        decorate(
            m, (x0, y0, x1, y1), profile,
            _rng(seed, "decor_" + area["node_id"]),
            [], spec,
        )
        made += 1
    return made
