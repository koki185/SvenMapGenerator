"""Планировщик уровня (этап 3).

По seed и параметрам строит граф помещений, раскладывает их на клеточной
сетке и возвращает готовый LevelSpec, который дальше идёт в builders.
Никакой случайности «просто ради случайности»: размеры и связи ограничены
типами комнат, а обязательные цели всегда связаны главной цепочкой.
"""

import random
from dataclasses import dataclass

from .level import Area, Connection, LevelSpec, validate

# Диапазон размеров в клетках для каждого типа помещения.
SIZE_RANGES = {
    "spawn":    (4, 7),
    "corridor": (3, 5),
    "lab":      (5, 8),
    "storage":  (4, 7),
    "arena":    (5, 8),
}

MAIN_TYPES = ("corridor", "lab", "storage")
BRANCH_TYPES = ("lab", "storage")

DIRECTIONS = ("E", "W", "N", "S")


@dataclass
class PlannerConfig:
    seed: int = 1
    grid: int = 192
    wall_thickness: int = 16
    floor_thickness: int = 16
    height: int = 256
    door_height: int = 128
    room_count: int = 6
    branch_count: int = 1
    theme: str = "industrial"


def _rects_overlap(a, b):
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    return ax0 < bx1 and bx0 < ax1 and ay0 < by1 and by0 < ay1


def _random_size(rng, room_type):
    lo, hi = SIZE_RANGES.get(room_type, (3, 5))
    return rng.randint(lo, hi), rng.randint(lo, hi)


def _candidate_sizes(rng, room_type):
    """Сначала желаемый размер, затем всё меньшие — до 2x2.

    Если площадь не втискивается, лучше сделать её чуть меньше,
    чем весь сегмент генерировать заново.
    """
    w, h = _random_size(rng, room_type)
    sizes = [(w, h)]
    while w > 2 or h > 2:
        w, h = max(2, w - 1), max(2, h - 1)
        sizes.append((w, h))
    return sizes


def _candidates(parent_rect, size):
    """Все варианты примыкания ребром к уже стоящей площади."""
    px0, py0, px1, py1 = parent_rect
    w, h = size

    variants = []

    # Восток / запад: смещение по вертикали, чтобы была общая полоса клеток.
    for side, x0 in (("E", px1), ("W", px0 - w)):
        for y0 in range(py0 - h + 1, py1):
            variants.append((side, (x0, y0, x0 + w, y0 + h)))

    # Север / юг: смещение по горизонтали.
    for side, y0 in (("N", py0 - h), ("S", py1)):
        for x0 in range(px0 - w + 1, px1):
            variants.append((side, (x0, y0, x0 + w, y0 + h)))

    return variants


def _shared_cells(parent_rect, child_rect, side):
    """Клетки площади A, чьё ребро выходит в площадь B."""
    px0, py0, px1, py1 = parent_rect
    cx0, cy0, cx1, cy1 = child_rect

    if side == "E":
        return [(px1 - 1, y) for y in range(max(py0, cy0), min(py1, cy1))]
    if side == "W":
        return [(px0, y) for y in range(max(py0, cy0), min(py1, cy1))]
    # "N"/"S" означают, что ребёнок стоит севернее/южнее родителя.
    # Значит общее ребро — северное (y = py0) или южное (y = py1 - 1).
    if side == "N":
        return [(x, py0) for x in range(max(px0, cx0), min(px1, cx1))]
    return [(x, py1 - 1) for x in range(max(px0, cx0), min(px1, cx1))]


def _place(rng, placed, parent_rect, size):
    """Выбрать позицию для новой площади. Возвращает (rect, side) или None."""
    variants = _candidates(parent_rect, size)
    rng.shuffle(variants)

    valid = []
    for side, rect in variants:
        if any(_rects_overlap(rect, other) for other in placed):
            continue
        shared = _shared_cells(parent_rect, rect, side)
        if not shared:
            continue
        # Компактность: ближе к центру и с большей общей стеной лучше.
        cx = (rect[0] + rect[2]) / 2.0
        cy = (rect[1] + rect[3]) / 2.0
        score = (cx * cx + cy * cy) ** 0.5 - 0.3 * len(shared)
        valid.append((score, side, rect))

    if not valid:
        return None
    valid.sort(key=lambda item: item[0])
    return valid[0][1], valid[0][2]


def plan(config, max_attempts=16):
    """Сгенерировать LevelSpec по конфигурации.

    Если раскладка не удалась, пробуем другие варианты того же seed —
    на больших картах часть раскладок не имеет свободного ребра.
    """
    if config.room_count < 2:
        raise ValueError("room_count должен быть не меньше 2")
    last_error = None
    for attempt in range(max_attempts):
        try:
            return _plan_once(config, attempt)
        except RuntimeError as e:
            last_error = e
    raise RuntimeError(
        "не удалось разложить карту после {} попыток: {}".format(
            max_attempts, last_error
        )
    )


def _plan_once(config, attempt):
    """Одна попытка раскладки с собственным состоянием RNG."""
    rng = random.Random(config.seed + attempt * 1009)

    # 1. Граф: главная цепочка + боковые ветки.
    main_ids = ["n{}".format(i) for i in range(config.room_count)]
    main_types = ["spawn"] + [
        MAIN_TYPES[i % len(MAIN_TYPES)] for i in range(config.room_count - 2)
    ] + ["arena"]

    edges = [(main_ids[i], main_ids[i + 1]) for i in range(len(main_ids) - 1)]
    branch_ids = []
    branch_parents = {}
    for i in range(config.branch_count):
        bid = "b{}".format(i)
        branch_ids.append(bid)
        parent = rng.choice(main_ids[1:-1] if len(main_ids) > 2 else main_ids)
        branch_parents[bid] = parent
        edges.append((parent, bid))

    types = dict(zip(main_ids, main_types))
    for bid in branch_ids:
        types[bid] = rng.choice(BRANCH_TYPES)

    # 2. Порядок расстановки: ветка ставится сразу после своего родителя,
    # пока вокруг ещё есть свободные рёбра.
    order = []
    for mid in main_ids:
        order.append(mid)
        for bid in branch_ids:
            if branch_parents[bid] == mid:
                order.append(bid)

    rects = {}
    connections_data = {}

    root_size = _random_size(rng, types[main_ids[0]])
    rects[main_ids[0]] = (0, 0, root_size[0], root_size[1])

    for node_id in order[1:]:
        parent_id = next(a for a, b in edges if b == node_id)
        result = None
        for size in _candidate_sizes(rng, types[node_id]):
            result = _place(rng, list(rects.values()), rects[parent_id], size)
            if result is not None:
                break
        if result is None:
            raise RuntimeError(
                "не удалось разместить {} при seed={}: нет свободного "
                "рёбра у {}".format(node_id, config.seed, parent_id)
            )
        side, rect = result
        rects[node_id] = rect

        shared = _shared_cells(rects[parent_id], rect, side)
        door_cell = rng.choice(shared)
        connections_data[node_id] = (parent_id, door_cell)

    # 3. Собираем LevelSpec.
    areas = [
        Area(node_id, types[node_id], tuple(rects[node_id]))
        for node_id in order
    ]
    connections = [
        Connection(parent_id, node_id, door_cell)
        for node_id, (parent_id, door_cell) in connections_data.items()
    ]

    spec = LevelSpec(
        name="sc_gen_{}".format(config.seed),
        theme=config.theme,
        grid=config.grid,
        wall_thickness=config.wall_thickness,
        floor_thickness=config.floor_thickness,
        height=config.height,
        door_height=config.door_height,
        areas=areas,
        connections=connections,
        start=main_ids[0],
        goal=main_ids[-1],
    )
    validate(spec)
    return spec


def spec_to_dict(spec):
    """Экспорт сгенерированной планировки — для просмотра и повторения."""
    return {
        "name": spec.name,
        "theme": spec.theme,
        "grid": spec.grid,
        "wall_thickness": spec.wall_thickness,
        "floor_thickness": spec.floor_thickness,
        "height": spec.height,
        "door_height": spec.door_height,
        "start": spec.start,
        "goal": spec.goal,
        "areas": [
            {"id": a.id, "type": a.type, "cells": list(a.cells)}
            for a in spec.areas
        ],
        "connections": [
            {"a": c.a, "b": c.b, "cell": list(c.cell)}
            for c in spec.connections
        ],
    }
