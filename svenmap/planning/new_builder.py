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


def _add_region(m: MapFile, cells: Set[Cell], grid: int, floor: int,
                height: int, floor_t: int, wall_t: int,
                texture_name: str, openings: Set[Tuple[Cell, str]],
                door_height: int):
    """Пол, потолок и стены произвольной области из клеток."""
    base = _floor_base(floor, height, floor_t)
    profile_ref = TextureRef(texture_name, 1.0, 1.0)
    for cx, cy in cells:
        x0, y0 = cx * grid, cy * grid
        m.add_box(
            Bounds(x0, y0, base, x0 + grid, y0 + grid, base + floor_t),
            profile_ref,
        )
        m.add_box(
            Bounds(x0, y0, base + height,
                   x0 + grid, y0 + grid, base + height + floor_t),
            profile_ref,
        )

    for cx, cy in cells:
        for dx, dy in DIRECTIONS:
            if (cx + dx, cy + dy) in cells:
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

    for conn in spatial["connections"]:
        a, b = areas.get(conn["a"]), areas.get(conn["b"])
        if not a or not b:
            continue
        pa, pb = tuple(conn["portal_a"]), tuple(conn["portal_b"])
        openings[conn["a"]].add((
            (pa[0] - a["x"], pa[1] - a["y"]),
            _direction_towards(pa, pb),
        ))
        openings[conn["b"]].add((
            (pb[0] - b["x"], pb[1] - b["y"]),
            _direction_towards(pb, pa),
        ))

    occupied: Dict[int, Set[Cell]] = {}
    for node_id, area in areas.items():
        floor = area.get("floor", 0)
        cells = _world_cells(area)
        occupied.setdefault(floor, set()).update(cells)
        texture = get_profile("industrial", graph_node_type(graph, node_id)).wall
        _add_region(m, cells, grid, floor, height, floor_t, wall_t,
                    texture, openings[node_id], door_h)

    # Коридоры для непрямых связей.
    indirect = [c for c in spatial["connections"] if not c.get("direct", True)]
    for conn in indirect:
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
                    "METAL_WALL01B", set(), door_h)
        occupied.setdefault(floor, set()).update(free)

    m.meta["blueprint"] = blueprint["graph"]["name"]
    return m


def graph_node_type(graph: dict, node_id: str) -> str:
    for node in graph["nodes"]:
        if node["id"] == node_id:
            return node.get("type", "corridor")
    return "corridor"
