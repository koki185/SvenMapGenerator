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


def build_blueprint_map(blueprint: dict, wads, game_dir, seed: int = 0) -> MapFile:
    """Собрать MapFile по Blueprint."""
    graph = blueprint["graph"]
    spatial = blueprint["spatial"]
    areas = {a["node_id"]: a for a in spatial["areas"]}
    grid = 192
    height, floor_t, wall_t, door_h = 256, 16, 16, 128

    m = MapFile(wads=wads, skyname="DESERT")
    connections = spatial["connections"]

    def rect_cells(area):
        return {
            (x, y)
            for x in range(area["x"], area["x"] + area["w"])
            for y in range(area["y"], area["y"] + area["h"])
        }

    def nearest(cells, target):
        return min(
            cells,
            key=lambda c: abs(c[0] - target[0]) + abs(c[1] - target[1]),
        )

    occupied: Dict[int, Set[Cell]] = {}
    for area in areas.values():
        floor = area.get("floor", 0)
        occupied.setdefault(floor, set()).update(rect_cells(area))

    # 1. Якоря connections и коридоры считаем ДО стен.
    anchors = {}
    corridors = {}
    for index, conn in enumerate(connections):
        a, b = areas.get(conn["a"]), areas.get(conn["b"])
        if not a or not b:
            continue
        if a.get("floor", 0) != 0 or b.get("floor", 0) != 0:
            continue
        pa, pb = tuple(conn["portal_a"]), tuple(conn["portal_b"])
        near_a = nearest(rect_cells(a), pa)
        near_b = nearest(rect_cells(b), pb)
        anchors[index] = (near_a, near_b)
        corridors[index] = _corridor_cells(near_a, near_b)

    free_by_index = {
        index: corridor - occupied.get(0, set())
        for index, corridor in corridors.items()
    }
    corridor_cells = set()
    for free in free_by_index.values():
        corridor_cells |= free

    # 2. Проёмы — только те рёбра bounding box, которые реально
    #    примыкают к клетке коридора. Это не режет лишние стены.
    openings: Dict[str, Set[Tuple[Cell, str]]] = {
        node_id: set() for node_id in areas
    }
    area_by_cell = {}
    for node_id, area in areas.items():
        for cell in rect_cells(area):
            area_by_cell[cell] = node_id

    for index, conn in enumerate(connections):
        corridor = corridors.get(index)
        if not corridor:
            continue
        # Со стороны клетки коридора открываем и саму комнату, и соседний
        # brush другой комнаты: без этого остаётся сплошная стена...
        for cell in corridor:
            for dx, dy in DIRECTIONS:
                neighbour = (cell[0] + dx, cell[1] + dy)
                node_id = area_by_cell.get(neighbour)
                if not node_id:
                    continue
                direction = "W" if dx == 1 else "E" if dx == -1 \
                    else "S" if dy == 1 else "N"
                openings[node_id].add((neighbour, direction))

    # 3. Комнаты.
    for node_id, area in areas.items():
        floor = area.get("floor", 0)
        texture = get_profile("industrial", graph_node_type(graph, node_id)).wall
        _add_region(m, _world_cells(area), grid, floor, height, floor_t,
                    wall_t, texture, openings[node_id], door_h,
                    skip_wall_cells=corridor_cells if floor == 0 else None)

    # 4. Коридоры.
    for index, conn in enumerate(connections):
        corridor = corridors.get(index)
        if not corridor:
            continue
        a = areas[conn["a"]]
        floor = a.get("floor", 0)
        free = free_by_index.get(index)
        if not free:
            continue
        _add_region(m, free, grid, floor, height, floor_t, wall_t,
                    "METAL_WALL01B", set(), door_h,
                    external=occupied.get(floor, set()))
        occupied.setdefault(floor, set()).update(free)

    # Точные координаты проёмов для Portal Registry.
    m.meta["openings"] = {}
    for index, (near_a, near_b) in anchors.items():
        conn = connections[index]
        a, b = areas[conn["a"]], areas[conn["b"]]
        m.meta["openings"][index] = {
            "a": _edge_box(near_a, _direction_towards(
                near_a, tuple(conn["portal_a"])), grid,
                a.get("floor", 0), height, floor_t, wall_t),
            "b": _edge_box(near_b, _direction_towards(
                near_b, tuple(conn["portal_b"])), grid,
                b.get("floor", 0), height, floor_t, wall_t),
        }

    # Внешняя оболочка карты: страхует от щелей в углах вырезов.
    all_cells = set()
    for cells in occupied.values():
        all_cells |= cells
    if all_cells:
        wx0 = min(c[0] for c in all_cells) * grid - 64
        wx1 = (max(c[0] for c in all_cells) + 1) * grid + 64
        wy0 = min(c[1] for c in all_cells) * grid - 64
        wy1 = (max(c[1] for c in all_cells) + 1) * grid + 64
        top = (max(a.get("floor", 0) for a in areas.values()) + 1) * (
            height + floor_t) + 32
        shell = TextureRef("BASEWALL01A", 1.0, 1.0)
        for bounds in (
            Bounds(wx0, wy0 - 32, -32, wx1, wy0, top),
            Bounds(wx0, wy1, -32, wx1, wy1 + 32, top),
            Bounds(wx0 - 32, wy0, -32, wx0, wy1, top),
            Bounds(wx1, wy0, -32, wx1 + 32, wy1, top),
        ):
            m.add_box(bounds, shell)

    m.meta["blueprint"] = graph["name"]
    return m



def graph_node_type(graph: dict, node_id: str) -> str:
    for node in graph["nodes"]:
        if node["id"] == node_id:
            return node.get("type", "corridor")
    return "corridor"
