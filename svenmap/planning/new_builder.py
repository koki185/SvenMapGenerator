"""Новый builder: геометрия по клеточным маскам (PR-6).

В отличие от legacy builders.py, здесь стены строятся по контуру
реально занятых клеток, поэтому L/T/U-формы попадают в .map.
Коридоры для непрямых связей тоже строятся кодом.
"""

import random
from typing import Dict, Set, Tuple

from ..geometry import Bounds
from ..mapfile import MapFile
from ..profiles import get_profile, TRANSITION_PROFILE
from ..scenes import scene_profile
from ..textures import TextureRef

Cell = Tuple[int, int]
DIRECTIONS = ((1, 0), (-1, 0), (0, 1), (0, -1))


def _world_cells(area: dict) -> Set[Cell]:
    cells = area.get("cells")
    if cells:
        return {(area["x"] + cx, area["y"] + cy) for cx, cy in cells}
    return {
        (area["x"] + cx, area["y"] + cy)
        for cx in range(area["w"])
        for cy in range(area["h"])
    }


def _floor_base(floor: int, height: int, floor_t: int) -> int:
    return floor * (height + floor_t)


def _edge_box(cell: Cell, direction: str, grid: int, floor: int,
              height: int, floor_t: int, wall_t: int) -> Bounds:
    """Прямоугольник стены на заданном ребре клетки."""
    base = _floor_base(floor, height, floor_t)
    cx, cy = cell
    if direction == "E":
        return Bounds((cx + 1) * grid - wall_t / 2, cy * grid,
                      base + floor_t, (cx + 1) * grid + wall_t / 2,
                      (cy + 1) * grid, base + height)
    if direction == "W":
        return Bounds(cx * grid - wall_t / 2, cy * grid,
                      base + floor_t, cx * grid + wall_t / 2,
                      (cy + 1) * grid, base + height)
    if direction == "N":
        return Bounds(cx * grid, (cy + 1) * grid - wall_t / 2,
                      base + floor_t, (cx + 1) * grid,
                      (cy + 1) * grid + wall_t / 2, base + height)
    return Bounds(cx * grid, cy * grid - wall_t / 2,
                  base + floor_t, (cx + 1) * grid,
                  cy * grid + wall_t / 2, base + height)


def _add_region(m: MapFile, cells: Set[Cell], grid: int, floor: int,
                height: int, floor_t: int, wall_t: int,
                texture_name: str, openings: Set[Tuple[Cell, str]],
                door_height: int, external: Set[Cell] = None,
                skip_wall_cells: Set[Cell] = None):
    """Пол, потолок и стены произвольной области из клеток."""
    base = _floor_base(floor, height, floor_t)
    profile_ref = TextureRef(texture_name, 1.0, 1.0)
    # Пол и потолок идут сплошь по bounding box: вырезы L/T/U формы
    # остаются за стенами, но не становятся дырой в оболочке.
    min_x = min(x for x, _ in cells)
    max_x = max(x for x, _ in cells) + 1
    min_y = min(y for _, y in cells)
    max_y = max(y for _, y in cells) + 1
    m.add_box(
        Bounds(min_x * grid, min_y * grid, base,
               max_x * grid, max_y * grid, base + floor_t),
        profile_ref,
    )
    m.add_box(
        Bounds(min_x * grid, min_y * grid, base + height,
               max_x * grid, max_y * grid, base + height + floor_t),
        profile_ref,
    )

    # Стены по периметру bounding box: вырезы L/T/U forms становятся
    # закрытыми карманами, а не дырами в оболочке.
    solid = {
        (x, y)
        for x in range(min_x, max_x)
        for y in range(min_y, max_y)
    }
    for cx, cy in solid:
        if skip_wall_cells and (cx, cy) in skip_wall_cells:
            continue
        for dx, dy in DIRECTIONS:
            if (cx + dx, cy + dy) in solid:
                continue
            if external and (cx + dx, cy + dy) in external:
                continue
            if (dx, dy) == (1, 0):
                box = Bounds((cx + 1) * grid - wall_t / 2, cy * grid,
                             base + floor_t, (cx + 1) * grid + wall_t / 2,
                             (cy + 1) * grid, base + height)
            elif (dx, dy) == (-1, 0):
                box = Bounds(cx * grid - wall_t / 2, cy * grid,
                             base + floor_t, cx * grid + wall_t / 2,
                             (cy + 1) * grid, base + height)
            elif (dx, dy) == (0, 1):
                box = Bounds(cx * grid, (cy + 1) * grid - wall_t / 2,
                             base + floor_t, (cx + 1) * grid,
                             (cy + 1) * grid + wall_t / 2, base + height)
            else:
                box = Bounds(cx * grid, cy * grid - wall_t / 2,
                             base + floor_t, (cx + 1) * grid,
                             cy * grid + wall_t / 2, base + height)

            direction = "E" if dx == 1 else "W" if dx == -1 \
                else "N" if dy == 1 else "S"
            if ((cx, cy), direction) in openings:
                m.add_box(
                    Bounds(box.x0, box.y0, base + door_height,
                           box.x1, box.y1, base + height),
                    TextureRef("METAL_WALL01B", 1.0, 1.0),
                )
            else:
                m.add_box(box, profile_ref)


def _direction_towards(portal: tuple, other: tuple) -> str:
    dx = other[0] - portal[0]
    dy = other[1] - portal[1]
    if abs(dx) >= abs(dy):
        return "E" if dx >= 0 else "W"
    return "N" if dy >= 0 else "S"


def _corridor_cells(a: Tuple[int, int], b: Tuple[int, int]) -> Set[Cell]:
    """L-образный коридор между двумя порталами."""
    cells = set()
    x, y = a
    step_x = 1 if b[0] >= a[0] else -1
    while x != b[0]:
        cells.add((x, y))
        x += step_x
    step_y = 1 if b[1] >= a[1] else -1
    while y != b[1]:
        cells.add((x, y))
        y += step_y
    cells.add(b)
    # Добавляем клетки вокруг порталов: проём может быть на ребре,
    # диагональном к точке портала (особенно у L/T/U-масок).
    for portal in (a, b):
        for dx, dy in DIRECTIONS:
            cells.add((portal[0] + dx, portal[1] + dy))
    return cells


def _accent_cells(cells, seed, room_id, fraction=0.08, min_gap=2):
    """Детерминированные 5–10% клеток под акцент, вдали друг от друга."""
    rng = random.Random("{}:accent:{}".format(seed, room_id))
    count = max(1, round(len(cells) * fraction)) if len(cells) >= 4 else 0
    pool = list(cells)
    rng.shuffle(pool)
    chosen = []
    for cell in pool:
        if len(chosen) >= count:
            break
        if all(max(abs(cell[0] - c[0]), abs(cell[1] - c[1])) >= min_gap
               for c in chosen):
            chosen.append(cell)
    return set(chosen)


def _trim_boxes(cx, cy, dx, dy, grid, wall_t, base, height, floor_t):
    """Плинтус, карниз и вставку на открытом ребре клетки."""
    z0, z1 = base + floor_t, base + height
    span_lo = cy * grid if dx else cx * grid
    span_hi = span_lo + grid
    if dx == 1:
        inner = (cx + 1) * grid - wall_t / 2
        def box(depth, za, zb, a=None, b=None):
            return Bounds(inner - depth, a if a is not None else span_lo, za,
                          inner, b if b is not None else span_hi, zb)
    elif dx == -1:
        inner = cx * grid + wall_t / 2
        def box(depth, za, zb, a=None, b=None):
            return Bounds(inner, a if a is not None else span_lo, za,
                          inner + depth, b if b is not None else span_hi, zb)
    elif dy == 1:
        inner = (cy + 1) * grid - wall_t / 2
        def box(depth, za, zb, a=None, b=None):
            return Bounds(a if a is not None else span_lo, inner - depth, za,
                          b if b is not None else span_hi, inner, zb)
    else:
        inner = cy * grid + wall_t / 2
        def box(depth, za, zb, a=None, b=None):
            return Bounds(a if a is not None else span_lo, inner, za,
                          b if b is not None else span_hi, inner + depth, zb)

    mid = (span_lo + span_hi) / 2
    return (
        box(4.0, z0, z0 + 12),                      # плинтус
        box(6.0, z1 - 16, z1),                      # карниз
        box(2.0, z0 + 80, z0 + 144, mid - 48, mid + 48),  # вставка
    )


def build_blueprint_map(blueprint: dict, wads, game_dir, seed: int = 0) -> MapFile:
    """Собрать MapFile по Blueprint: стены по единой маске клеток."""
    graph = blueprint["graph"]
    spatial = blueprint["spatial"]
    areas = {a["node_id"]: a for a in spatial["areas"]}
    grid = 192
    height, floor_t, wall_t, door_h = 256, 16, 16, 128

    m = MapFile(wads=wads, skyname="DESERT")
    connections = spatial["connections"]
    scene_assignments = blueprint.get("scene_assignments", {})

    def area_profile(node_id, area_type, cell_key=None):
        if cell_key is not None and cell_key in corridor_cells:
            return TRANSITION_PROFILE
        scene_name = scene_assignments.get(node_id)
        if scene_name:
            return scene_profile(scene_name)
        return get_profile("industrial", area_type)

    def nearest(cells, target):
        return min(
            cells,
            key=lambda c: abs(c[0] - target[0]) + abs(c[1] - target[1]),
        )

    occupied = {}
    owner = {}
    corridor_cells = set()
    for node_id, area in areas.items():
        floor = area.get("floor", 0)
        cells = occupied.setdefault(floor, set())
        for cell in _world_cells(area):
            cells.add(cell)
            owner[(floor, cell)] = node_id

    # Коридоры объединяются с комнатами ДО вычисления стен.
    anchors = {}
    for index, conn in enumerate(connections):
        a, b = areas.get(conn["a"]), areas.get(conn["b"])
        if not a or not b:
            continue
        if a.get("floor", 0) != 0 or b.get("floor", 0) != 0:
            continue
        pa, pb = tuple(conn["portal_a"]), tuple(conn["portal_b"])
        near_a = nearest(_world_cells(a), pa)
        near_b = nearest(_world_cells(b), pb)
        anchors[index] = (near_a, near_b)
        corridor = _corridor_cells(near_a, near_b)
        free = corridor - occupied.get(0, set())
        for cell in free:
            occupied[0].add(cell)
            owner[(0, cell)] = conn["a"]
            corridor_cells.add((0, cell))

    # Акценты: отдельные RNG для пола и потолка, геометрия не меняется.
    floor_accents, ceil_accents = {}, {}
    for node_id, area in areas.items():
        cells = _world_cells(area)
        floor_accents[node_id] = _accent_cells(
            cells, seed, node_id + ":floor", 0.08
        )
        ceil_accents[node_id] = _accent_cells(
            cells, seed, node_id + ":ceil", 0.12, 3
        )

    # Пол и потолок по реально занятым клеткам: разные текстуры, акцент точечно.
    surface_report = {"floor": {}, "ceiling": {}}
    for floor, cells in occupied.items():
        base = _floor_base(floor, height, floor_t)
        for cx, cy in cells:
            node_id = owner.get((floor, (cx, cy)), "")
            area_type = graph_node_type(graph, node_id) if node_id else "corridor"
            profile = area_profile(node_id, area_type, (floor, (cx, cy)))
            floor_tex, ceil_tex = profile.floor, profile.ceiling
            if profile.floor_accent and (cx, cy) in floor_accents.get(node_id, ()):
                floor_tex = profile.floor_accent
            if profile.ceiling_detail and (cx, cy) in ceil_accents.get(node_id, ()):
                ceil_tex = profile.ceiling_detail
            x0, y0 = cx * grid, cy * grid
            m.add_box(
                Bounds(x0, y0, base, x0 + grid, y0 + grid, base + floor_t),
                TextureRef(floor_tex, 1.0, 1.0),
            )
            m.add_box(
                Bounds(x0, y0, base + height, x0 + grid, y0 + grid,
                       base + height + floor_t),
                TextureRef(ceil_tex, 1.0, 1.0),
            )
            if node_id:
                surface_report["floor"].setdefault(node_id, set()).add(floor_tex)
                surface_report["ceiling"].setdefault(node_id, set()).add(ceil_tex)

    # Стены по exposed edges единой маски.
    for floor, cells in occupied.items():
        base = _floor_base(floor, height, floor_t)
        for cx, cy in cells:
            for dx, dy in DIRECTIONS:
                if (cx + dx, cy + dy) in cells:
                    continue
                if dx == 1:
                    box = Bounds((cx + 1) * grid - wall_t / 2, cy * grid,
                                 base + floor_t, (cx + 1) * grid + wall_t / 2,
                                 (cy + 1) * grid, base + height)
                elif dx == -1:
                    box = Bounds(cx * grid - wall_t / 2, cy * grid,
                                 base + floor_t, cx * grid + wall_t / 2,
                                 (cy + 1) * grid, base + height)
                elif dy == 1:
                    box = Bounds(cx * grid, (cy + 1) * grid - wall_t / 2,
                                 base + floor_t, (cx + 1) * grid,
                                 (cy + 1) * grid + wall_t / 2, base + height)
                else:
                    box = Bounds(cx * grid, cy * grid - wall_t / 2,
                                 base + floor_t, (cx + 1) * grid,
                                 cy * grid + wall_t / 2, base + height)
                node_id = owner.get((floor, (cx, cy)), "")
                area_type = graph_node_type(graph, node_id) if node_id else "corridor"
                profile = area_profile(node_id, area_type, (floor, (cx, cy)))
                m.add_box(box, TextureRef(profile.wall, 1.0, 1.0))

                # Отделка поверх стены: проёмов здесь нет (они — отсутствующие
                # рёбра единой маски), поэтому плинтус и карниз идут по всему ребру.
                base_b, cornice_b, insert_b = _trim_boxes(
                    cx, cy, dx, dy, grid, wall_t, base, height, floor_t
                )
                if profile.trim:
                    m.add_box(base_b, TextureRef(profile.trim, 1.0, 1.0))
                    m.add_box(cornice_b, TextureRef(profile.trim, 1.0, 1.0))
                if profile.insert:
                    key = "{}:{}:{}:{}:insert".format(seed, node_id, cx, cy)
                    if random.Random(key).random() < 0.4:
                        m.add_box(insert_b, TextureRef(profile.insert, 1.0, 1.0))

    # Наружная оболочка.
    all_cells = set().union(*occupied.values()) if occupied else set()
    if all_cells:
        wx0 = min(c[0] for c in all_cells) * grid - 64
        wx1 = (max(c[0] for c in all_cells) + 1) * grid + 64
        wy0 = min(c[1] for c in all_cells) * grid - 64
        wy1 = (max(c[1] for c in all_cells) + 1) * grid + 64
        top = (max(occupied) + 1) * (height + floor_t) + 32
        shell = TextureRef("BASEWALL01A", 1.0, 1.0)
        for bounds in (
            Bounds(wx0, wy0 - 32, -32, wx1, wy0, top),
            Bounds(wx0, wy1, -32, wx1, wy1 + 32, top),
            Bounds(wx0 - 32, wy0, -32, wx0, wy1, top),
            Bounds(wx1, wy0, -32, wx1 + 32, wy1, top),
        ):
            m.add_box(bounds, shell)

    m.meta["openings"] = {}
    surface_meta = {}
    for room, floors in surface_report["floor"].items():
        surface_meta[room] = {
            "floor": sorted(floors),
            "ceiling": sorted(surface_report["ceiling"].get(room, set())),
        }
    m.meta["surface"] = surface_meta
    m.meta["blueprint"] = graph["name"]
    return m



def graph_node_type(graph: dict, node_id: str) -> str:
    for node in graph["nodes"]:
        if node["id"] == node_id:
            return node.get("type", "corridor")
    return "corridor"
