"""Новый builder: геометрия по клеточным маскам (PR-6).

В отличие от legacy builders.py, здесь стены строятся по контуру
реально занятых клеток, поэтому L/T/U-формы попадают в .map.
Коридоры для непрямых связей тоже строятся кодом.
"""

from typing import Dict, Set, Tuple

from ..geometry import Bounds
from ..mapfile import MapFile
from ..profiles import get_profile
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
                door_height: int, external: Set[Cell] = None):
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

    for cx, cy in cells:
        for dx, dy in DIRECTIONS:
            if (cx + dx, cy + dy) in cells:
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


def build_blueprint_map(blueprint: dict, wads, game_dir, seed: int = 0) -> MapFile:
    """Собрать MapFile по Blueprint."""
    graph = blueprint["graph"]
    spatial = blueprint["spatial"]
    areas = {a["node_id"]: a for a in spatial["areas"]}
    grid = 192
    height, floor_t, wall_t, door_h = 256, 16, 16, 128

    m = MapFile(wads=wads, skyname="DESERT")
    openings: Dict[str, Set[Tuple[Cell, str]]] = {
        node_id: set() for node_id in areas
    }
    opening_records = []

    for index, conn in enumerate(spatial["connections"]):
        a, b = areas.get(conn["a"]), areas.get(conn["b"])
        if not a or not b:
            continue
        pa, pb = tuple(conn["portal_a"]), tuple(conn["portal_b"])
        cells_a, cells_b = _world_cells(a), _world_cells(b)

        def nearest(cells, target):
            return min(
                cells,
                key=lambda c: abs(c[0] - target[0]) + abs(c[1] - target[1]),
            )

        near_a = nearest(cells_a, pa)
        near_b = nearest(cells_b, pb)
        local_a = (near_a[0] - a["x"], near_a[1] - a["y"])
        local_b = (near_b[0] - b["x"], near_b[1] - b["y"])
        dir_a = _direction_towards(near_a, pa)
        dir_b = _direction_towards(near_b, pb)
        # Стены проверяются в мировых координатах клеток.
        openings[conn["a"]].add((near_a, dir_a))
        openings[conn["b"]].add((near_b, dir_b))
        opening_records.append((index, local_a, dir_a, a.get("floor", 0),
                                local_b, dir_b, b.get("floor", 0)))

    occupied: Dict[int, Set[Cell]] = {}
    for node_id, area in areas.items():
        floor = area.get("floor", 0)
        cells = _world_cells(area)
        occupied.setdefault(floor, set()).update(cells)
        texture = get_profile("industrial", graph_node_type(graph, node_id)).wall
        _add_region(m, cells, grid, floor, height, floor_t, wall_t,
                    texture, openings[node_id], door_h)

    # Коридоры: даже «прямые» связи имеют зазор в одну клетку.
    for conn in spatial["connections"]:
        a, b = areas.get(conn["a"]), areas.get(conn["b"])
        if not a or not b:
            continue
        pa, pb = tuple(conn["portal_a"]), tuple(conn["portal_b"])
        corridor = _corridor_cells(pa, pb)
        floor = a.get("floor", 0)
        free = corridor - occupied.get(floor, set())
        if not free:
            continue
        _add_region(m, free, grid, floor, height, floor_t, wall_t,
                    "METAL_WALL01B", set(), door_h,
                    external=occupied.get(floor, set()))
        occupied.setdefault(floor, set()).update(free)

    # Точные координаты проёмов — mechanics ставит дверь сюда, а не по legacy.
    m.meta["openings"] = {}
    for index, la, da, fa, lb, db, fb in opening_records:
        m.meta["openings"][index] = {
            "a": _edge_box(la, da, grid, fa, height, floor_t, wall_t),
            "b": _edge_box(lb, db, grid, fb, height, floor_t, wall_t),
        }

    m.meta["blueprint"] = blueprint["graph"]["name"]
    return m


def graph_node_type(graph: dict, node_id: str) -> str:
    for node in graph["nodes"]:
        if node["id"] == node_id:
            return node.get("type", "corridor")
    return "corridor"
