"""Portal Resolver (Patch 1 по рекомендации GPT).

Один resolver преобразует Blueprint-порталы в нормализованные физические
данные. Builder, механики и QA используют ОДИН И ТОТ ЖЕ registry —
никаких пересчётов дверей из room bounds.
"""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from ..geometry import Bounds
from .new_builder import _edge_box, _world_cells

GRID = 192
HEIGHT = 256
FLOOR_T = 16
WALL_T = 16
DOOR_H = 128


@dataclass(frozen=True)
class ResolvedPortal:
    id: str
    area_a: str
    area_b: str
    floor: int
    x: int
    y: int
    z: int
    normal: Tuple[int, int]
    width: int
    height: int
    side_a: Tuple[int, int, int]
    side_b: Tuple[int, int, int]
    interaction_point: Tuple[int, int, int]
    item_point: Tuple[int, int, int]
    door_bounds: Bounds
    kind: str = "door"
    locked: bool = False
    lock_id: Optional[str] = None


def _nearest(cells, target):
    return min(
        cells,
        key=lambda c: abs(c[0] - target[0]) + abs(c[1] - target[1]),
    )


def _direction(point: Tuple[int, int], target: Tuple[int, int]) -> Tuple[int, int]:
    dx, dy = target[0] - point[0], target[1] - point[1]
    if abs(dx) >= abs(dy):
        return (1, 0) if dx >= 0 else (-1, 0)
    return (0, 1) if dy >= 0 else (0, -1)


def resolve_portal(blueprint: dict, portal_id: str) -> ResolvedPortal:
    spatial = blueprint["spatial"]
    connection = next(
        (c for c in spatial["connections"] if c.get("id") == portal_id), None
    )
    if connection is None:
        raise KeyError("нет портала " + portal_id)
    areas = {a["node_id"]: a for a in spatial["areas"]}
    a, b = areas[connection["a"]], areas[connection["b"]]
    pa = tuple(connection["portal_a"])
    pb = tuple(connection["portal_b"])

    cells_a, cells_b = _world_cells(a), _world_cells(b)
    near_a, near_b = _nearest(cells_a, pa), _nearest(cells_b, pb)
    dir_a = _direction(near_a, pa)
    direction = "E" if dir_a == (1, 0) else "W" if dir_a == (-1, 0) \
        else "N" if dir_a == (0, 1) else "S"

    floor = a.get("floor", 0)
    # Дверь = одна клетка коридора у входа в комнату. Широкая плита
    # (старый вариант с margin=2) в игре застревает в стенах
    # и не открывается, хотя в QA блокирует путь.
    # Дверь покрывает портал и по одной клетке с каждой стороны:
    # узкая дверь оставляла обход по краю коридора.
    base = floor * (HEIGHT + FLOOR_T)
    bounds = Bounds(
        (pa[0] - 1) * GRID, (pa[1] - 1) * GRID,
        base + FLOOR_T,
        (pa[0] + 2) * GRID, (pa[1] + 2) * GRID,
        base + HEIGHT,
    )
    cx = int((bounds.x0 + bounds.x1) / 2)
    cy = int((bounds.y0 + bounds.y1) / 2)
    base = floor * (HEIGHT + FLOOR_T)
    z = base + FLOOR_T + DOOR_H // 2

    side_a = (cx + dir_a[0] * 48, cy + dir_a[1] * 48, base + FLOOR_T + 8)
    side_b = (cx - dir_a[0] * 48, cy - dir_a[1] * 48, base + FLOOR_T + 8)
    interaction = (side_a[0], side_a[1], base + FLOOR_T + 24)
    item = (side_a[0] + dir_a[0] * 32, side_a[1] + dir_a[1] * 32,
            base + FLOOR_T + 8)

    return ResolvedPortal(
        id=portal_id,
        area_a=connection["a"], area_b=connection["b"],
        floor=floor, x=cx, y=cy, z=z,
        normal=dir_a, width=GRID, height=DOOR_H,
        side_a=side_a, side_b=side_b,
        interaction_point=interaction, item_point=item,
        door_bounds=bounds,
        kind=connection.get("type", "door"),
    )


def resolve_all_portals(blueprint: dict) -> Dict[str, ResolvedPortal]:
    result = {}
    for connection in blueprint["spatial"]["connections"]:
        portal_id = connection.get("id")
        if not portal_id:
            continue
        result[portal_id] = resolve_portal(blueprint, portal_id)
    return result


def get_portal_center(portal: ResolvedPortal) -> Tuple[int, int, int]:
    return (portal.x, portal.y, portal.z)


def get_portal_side(portal: ResolvedPortal, area_id: str):
    return portal.side_a if area_id == portal.area_a else portal.side_b


def get_interaction_point(portal: ResolvedPortal, side: str = "a"):
    return portal.interaction_point if side == "a" else portal.side_b


def get_item_point(portal: ResolvedPortal, side: str = "a"):
    return portal.item_point if side == "a" else portal.side_b


def validate_portal_geometry(portal: ResolvedPortal, blueprint: dict) -> list:
    errors = []
    areas = {a["node_id"]: a for a in blueprint["spatial"]["areas"]}
    if portal.area_a not in areas or portal.area_b not in areas:
        errors.append("портал ссылается на несуществующую площадь")
    if portal.width <= 0 or portal.height <= 0:
        errors.append("некорректный размер портала")
    if portal.floor < 0:
        errors.append("некорректный этаж портала")
    return errors
