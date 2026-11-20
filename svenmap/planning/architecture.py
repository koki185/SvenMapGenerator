"""Формы комнат вместо обязательного прямоугольника (PR-3).

Маска — набор локальных клеток (x, y) внутри прямоугольника SpatialArea.
Для legacy-генератора всё остаётся прямоугольником: здесь мы только
обогащаем Blueprint, не меняя сборку .map.
"""

from collections import deque
from typing import Dict, Optional, Set, Tuple

from .models import SpatialLayout, TopologyGraph
from .rng import make_rng

Cells = Set[Tuple[int, int]]


def make_rect(w: int, h: int) -> Cells:
    return {(x, y) for y in range(h) for x in range(w)}


def make_l(w: int, h: int, cut_w: int, cut_h: int) -> Cells:
    cells = make_rect(w, h)
    for x in range(w - cut_w, w):
        for y in range(h - cut_h, h):
            cells.discard((x, y))
    return cells


def make_t(w: int, h: int, stem_w: int) -> Cells:
    cells = set()
    half = h // 2
    for y in range(half):
        for x in range(w):
            cells.add((x, y))
    x0 = (w - stem_w) // 2
    for y in range(half, h):
        for x in range(x0, x0 + stem_w):
            cells.add((x, y))
    return cells


def make_u(w: int, h: int, arm_w: int, opening_h: int) -> Cells:
    cells = make_rect(w, h)
    x0 = arm_w
    x1 = w - arm_w
    y0 = h - opening_h
    for x in range(x0, x1):
        for y in range(y0, h):
            cells.discard((x, y))
    return cells


def rotate_shape(cells: Cells) -> Cells:
    if not cells:
        return set()
    height = max(y for _, y in cells) + 1
    rotated = {(height - 1 - y, x) for x, y in cells}
    return normalize(rotated)


def normalize(cells: Cells) -> Cells:
    if not cells:
        return set()
    min_x = min(x for x, _ in cells)
    min_y = min(y for _, y in cells)
    return {(x - min_x, y - min_y) for x, y in cells}


def is_connected(cells: Cells) -> bool:
    if not cells:
        return False
    start = next(iter(cells))
    seen = {start}
    queue = deque([start])
    while queue:
        x, y = queue.popleft()
        for neighbour in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if neighbour in cells and neighbour not in seen:
                seen.add(neighbour)
                queue.append(neighbour)
    return len(seen) == len(cells)


def _valid(cells: Cells, w: int, h: int) -> bool:
    if not is_connected(cells):
        return False
    if len(cells) < max(6, int(w * h * 0.55)):
        return False
    if max(x for x, _ in cells) >= w or max(y for _, y in cells) >= h:
        return False
    return True


SHAPE_WEIGHTS = {
    "corridor": ("rect", "rect", "rect", "l"),
    "spawn": ("rect", "l", "t"),
    "hub": ("rect", "t", "l"),
    "lab": ("rect", "l", "t", "u"),
    "storage": ("rect", "u", "l"),
    "arena": ("rect", "rect", "t"),
    "combat": ("rect", "t", "l"),
    "objective": ("rect", "l", "t"),
    "secret": ("rect", "l"),
    "transition": ("rect",),
}


def candidates_for(shape: str, w: int, h: int) -> Cells:
    if shape == "rect":
        return make_rect(w, h)
    if shape == "l":
        return make_l(w, h, max(1, w // 3), max(1, h // 3))
    if shape == "t":
        return make_t(w, h, max(2, w // 3))
    if shape == "u":
        return make_u(w, h, max(1, w // 4), max(1, h // 3))
    return make_rect(w, h)


def _portals_for(node_id: str, layout: SpatialLayout) -> list:
    result = []
    for connection in layout.connections:
        if connection.a == node_id:
            result.append((
                connection.portal_a[0], connection.portal_a[1],
            ))
        elif connection.b == node_id:
            result.append((
                connection.portal_b[0], connection.portal_b[1],
            ))
    return result


def _contains_portals(area, cells: Cells, portals: list) -> bool:
    for px, py in portals:
        local = (px - area.x, py - area.y)
        if local in cells:
            continue
        # Портал может быть на границе соседней клетки — допускаем ±1.
        if any(
            (local[0] + dx, local[1] + dy) in cells
            for dx in (-1, 0, 1) for dy in (-1, 0, 1)
        ):
            continue
        return False
    return True


def apply_shapes(graph: TopologyGraph, layout: SpatialLayout,
                 seed: int) -> Dict[str, dict]:
    """Подобрать форму каждой комнаты, сохранив порталы связей."""
    rng = make_rng(seed, "architecture")
    result = {}
    for node_id, area in layout.areas.items():
        node = graph.nodes[node_id]
        portals = _portals_for(node_id, layout)
        shapes = list(SHAPE_WEIGHTS.get(node.type, ("rect",)))
        rng.shuffle(shapes)
        chosen = ("rect", make_rect(area.w, area.h))

        for shape in shapes:
            base = candidates_for(shape, area.w, area.h)
            if not _valid(base, area.w, area.h):
                continue
            for _rotation in range(4):
                if _contains_portals(area, base, portals):
                    chosen = (shape, set(base))
                    break
                base = rotate_shape(base)
            if chosen[0] != "rect" or shape == "rect":
                break
        shape_name, cells = chosen
        area.shape = shape_name
        area.cells = normalize(cells)
        result[node_id] = {
            "shape": shape_name,
            "cells": sorted(area.cells),
        }

    return result
