"""Многоэтажная проверка проходимости (PR-4).

Старый validator.py остаётся: он проверяет один Z-срез через BFS.
Здесь строится TraversalGraph по этажам и проверенным вертикальным
соединителям. Игровой тест всё равно остаётся окончательной проверкой.
"""

from collections import deque
from typing import Dict, List, Optional, Set, Tuple

from .planning.models import SpatialLayout, TopologyGraph, VerticalConnector

Cell = Tuple[int, int]
Node3D = Tuple[int, int, int]
ALLOWED_TYPES = ("stairs", "ladder", "elevator", "ramp")


def world_cells(layout: SpatialLayout, floor: int) -> Set[Cell]:
    """Все проходимые клетки заданного этажа."""
    result = set()
    for area in layout.areas.values():
        if area.floor != floor:
            continue
        if area.cells:
            for cx, cy in area.cells:
                result.add((area.x + cx, area.y + cy))
        else:
            for cx in range(area.w):
                for cy in range(area.h):
                    result.add((area.x + cx, area.y + cy))
    return result


def build_floor_graphs(layout: SpatialLayout) -> Dict[int, Set[Cell]]:
    floors = sorted({area.floor for area in layout.areas.values()})
    return {floor: world_cells(layout, floor) for floor in floors}


def _near(cell: Cell, cells: Set[Cell], radius: int = 1) -> bool:
    x, y = cell
    return any(
        (x + dx, y + dy) in cells
        for dx in range(-radius, radius + 1)
        for dy in range(-radius, radius + 1)
    )


def validate_connector(connector: VerticalConnector, layout: SpatialLayout) -> List[str]:
    errors = []
    a = layout.areas.get(connector.area_a)
    b = layout.areas.get(connector.area_b)
    if not a or not b:
        return ["коннектор ссылается на несуществующую площадь"]
    if connector.type not in ALLOWED_TYPES:
        errors.append("неизвестный тип коннектора: " + connector.type)
    if connector.floor_a == connector.floor_b:
        errors.append("коннектор не меняет этаж")
    if connector.height_delta <= 0:
        errors.append("некорректная разность высот")
    if not _near(connector.landing_a, world_cells(layout, connector.floor_a)):
        errors.append("площадка A вне проходимой зоны")
    if not _near(connector.landing_b, world_cells(layout, connector.floor_b)):
        errors.append("площадка B вне проходимой зоны")
    return errors


def validate_landing(connector: VerticalConnector, layout: SpatialLayout) -> bool:
    return not validate_connector(connector, layout)


def _area_world_cells(area) -> Set[Cell]:
    if area.cells:
        return {(area.x + cx, area.y + cy) for cx, cy in area.cells}
    return {
        (x, y)
        for x in range(area.x, area.x + area.w)
        for y in range(area.y, area.y + area.h)
    }


def _link_portal(graph, floor: int, portal: Cell, area) -> None:
    node = (floor, portal[0], portal[1])
    cells = _area_world_cells(area)
    if portal in cells:
        return
    if not cells:
        return
    nearest = min(
        cells,
        key=lambda c: abs(c[0] - portal[0]) + abs(c[1] - portal[1]),
    )
    target = (floor, nearest[0], nearest[1])
    graph.setdefault(node, set()).add(target)
    graph.setdefault(target, set()).add(node)


def _area_cell(area) -> Cell:
    if area.cells:
        cx, cy = min(area.cells)
        return (area.x + cx, area.y + cy)
    return (area.x + area.w // 2, area.y + area.h // 2)


def build_traversal_graph(
    layout: SpatialLayout,
) -> Dict[Node3D, Set[Node3D]]:
    floor_graphs = build_floor_graphs(layout)
    connectors = layout.vertical_connectors
    graph: Dict[Node3D, Set[Node3D]] = {}
    for floor, cells in floor_graphs.items():
        present = {(floor, cx, cy) for cx, cy in cells}
        for cx, cy in cells:
            node = (floor, cx, cy)
            graph[node] = set()
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                neighbour = (floor, cx + dx, cy + dy)
                if neighbour in present:
                    graph[node].add(neighbour)

    # Порталы связей соединяют комнаты через зазор между ними.
    for connection in layout.connections:
        area_a = layout.areas.get(connection.a)
        area_b = layout.areas.get(connection.b)
        if not area_a or not area_b:
            continue
        pa = (area_a.floor, connection.portal_a[0], connection.portal_a[1])
        pb = (area_b.floor, connection.portal_b[0], connection.portal_b[1])
        graph.setdefault(pa, set()).add(pb)
        graph.setdefault(pb, set()).add(pa)
        _link_portal(graph, area_a.floor, connection.portal_a, area_a)
        _link_portal(graph, area_b.floor, connection.portal_b, area_b)

    for connector in connectors:
        if connector.floor_a not in floor_graphs or connector.floor_b not in floor_graphs:
            continue
        a = (connector.floor_a, connector.landing_a[0], connector.landing_a[1])
        b = (connector.floor_b, connector.landing_b[0], connector.landing_b[1])
        graph.setdefault(a, set()).add(b)
        if connector.bidirectional:
            graph.setdefault(b, set()).add(a)
    return graph


def find_path_3d(graph: Dict[Node3D, Set[Node3D]],
                 start: Node3D, goal: Node3D) -> Optional[List[Node3D]]:
    if start not in graph or goal not in graph:
        return None
    parents = {start: None}
    queue = deque([start])
    while queue:
        current = queue.popleft()
        if current == goal:
            path = []
            while current is not None:
                path.append(current)
                current = parents[current]
            return list(reversed(path))
        for neighbour in graph.get(current, set()):
            if neighbour not in parents:
                parents[neighbour] = current
                queue.append(neighbour)
    return None


def validate_vertical_reachability(
    graph: TopologyGraph, layout: SpatialLayout,
) -> dict:
    connectors = layout.vertical_connectors
    floors = build_floor_graphs(layout)
    errors = []
    for connector in connectors:
        errors.extend(validate_connector(connector, layout))

    traversal = build_traversal_graph(layout)
    start_area = layout.areas.get(graph.start)
    goal_area = layout.areas.get(graph.goal)
    result = {"connector_errors": errors}
    if start_area and goal_area:
        sx, sy = _area_cell(start_area)
        gx, gy = _area_cell(goal_area)
        start = (start_area.floor, sx, sy)
        goal = (goal_area.floor, gx, gy)
        path = find_path_3d(traversal, start, goal)
        result["path_found"] = path is not None
        result["path_length"] = len(path) if path else 0
    else:
        result["path_found"] = False
    result["passed"] = not errors and result["path_found"]
    return result
