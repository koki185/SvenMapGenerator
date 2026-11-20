"""Адаптер Blueprint -> Legacy LevelSpec (PR-5).

Новый pipeline пока работает с прямоугольными комнатами и одним этажом:
маски L/T/U и вертикальные коннекторы остаются в Blueprint, но в legacy
builder не попадают. Это позволяет проверить совместимость до переписывания
геометрии.
"""

from typing import Dict, Tuple

from ..level import Area, Connection, LevelSpec, validate

Rect = Tuple[int, int, int, int]  # x0, y0, x1, y1 (исключительно)


def _overlap(a: Rect, b: Rect) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _shared_length(a: Rect, b: Rect) -> int:
    if a[2] == b[0] or b[2] == a[0]:
        return max(0, min(a[3], b[3]) - max(a[1], b[1]))
    if a[3] == b[1] or b[3] == a[1]:
        return max(0, min(a[2], b[2]) - max(a[0], b[0]))
    return 0


def _touching(a: Rect, b: Rect) -> bool:
    return _shared_length(a, b) > 0


def _door_cell(a: Rect, b: Rect) -> Tuple[int, int]:
    if a[2] == b[0]:
        y0 = max(a[1], b[1])
        y1 = min(a[3], b[3])
        return (a[2] - 1, (y0 + y1) // 2)
    if b[2] == a[0]:
        y0 = max(a[1], b[1])
        y1 = min(a[3], b[3])
        return (a[0], (y0 + y1) // 2)
    if a[3] == b[1]:
        x0 = max(a[0], b[0])
        x1 = min(a[2], b[2])
        return ((x0 + x1) // 2, a[3] - 1)
    x0 = max(a[0], b[0])
    x1 = min(a[2], b[2])
    return ((x0 + x1) // 2, a[1])


def _overlap_area(a: Rect, b: Rect) -> int:
    return max(0, min(a[2], b[2]) - max(a[0], b[0])) * \
           max(0, min(a[3], b[3]) - max(a[1], b[1]))


def _snap(a: Rect, b: Rect, placed: Dict[str, Rect]) -> Rect:
    """Подвинуть B так, чтобы он касался A и минимизировал пересечения."""
    x0, y0, x1, y1 = b
    w, h = x1 - x0, y1 - y0
    candidates = []
    for offset in range(0, 12):
        for y in range(a[1] - h + 1, a[3]):
            candidates.append((a[2] + offset, y, a[2] + offset + w, y + h))
            candidates.append((a[0] - w - offset, y, a[0] - offset, y + h))
        for x in range(a[0] - w + 1, a[2]):
            candidates.append((x, a[3] + offset, x + w, a[3] + offset + h))
            candidates.append((x, a[1] - h - offset, x + w, a[1] - offset))

    free = [
        c for c in candidates
        if not any(_overlap_area(c, other) > 0 for other in placed.values())
    ]
    if free:
        return free[0]
    return min(
        candidates,
        key=lambda c: sum(_overlap_area(c, other) for other in placed.values()),
    )


def portal_to_legacy_door(portal):
    """Преобразовать ResolvedPortal в legacy Bounds — без пересчёта.

    Adapter не ищет дверь и не меняет координаты: он только возвращает
    уже разрешённый resolver-ом проём в формате, понятном mechanics.
    """
    return portal.door_bounds


def blueprint_to_aligned_spec(blueprint: dict) -> LevelSpec:
    """LevelSpec с координатами Blueprint — для механик нового builder."""
    graph = blueprint["graph"]
    spatial = blueprint["spatial"]
    types = {n["id"]: n.get("type", "corridor") for n in graph["nodes"]}
    areas = []
    for a in spatial["areas"]:
        x, y = a["x"], a["y"]
        areas.append(Area(a["node_id"], types.get(a["node_id"], "corridor"),
                          (x, y, x + a["w"], y + a["h"])))

    connections = []
    for c in spatial["connections"]:
        a = next((x for x in areas if x.id == c["a"]), None)
        b = next((x for x in areas if x.id == c["b"]), None)
        if not a or not b:
            continue
        # Портал уже рассчитан новым pipeline; валидацию adjacency не делаем:
        # геометрию строит new_builder, а не legacy.
        cell = tuple(c.get("portal_a", [a.cells[0], a.cells[1]]))
        connection = Connection(a=a.id, b=b.id, cell=cell)
        bx = (b.cells[0] + b.cells[2]) / 2.0
        by = (b.cells[1] + b.cells[3]) / 2.0
        dx, dy = bx - cell[0], by - cell[1]
        connection.direction = (
            (1, 0) if abs(dx) >= abs(dy) and dx >= 0 else
            (-1, 0) if abs(dx) >= abs(dy) else
            (0, 1) if dy >= 0 else (0, -1)
        )
        connections.append(connection)

    spec = LevelSpec(
        name=graph["name"], theme="industrial", grid=192,
        wall_thickness=16, floor_thickness=16,
        height=256, door_height=128,
        areas=areas, connections=connections,
        start=graph["start"], goal=graph["goal"],
    )
    return spec


def blueprint_to_level_spec(blueprint: dict) -> LevelSpec:
    graph = blueprint["graph"]
    spatial = blueprint["spatial"]
    areas_data = {a["node_id"]: a for a in spatial["areas"]}
    types = {n["id"]: n["type"] for n in graph["nodes"]}

    edges = graph["edges"]

    # Размеры берём из Blueprint, размещение — по графу: так гарантированно
    # сохраняется связность. Пространственные координаты Blueprint пока
    # используются только как источник footprint.
    sizes = {
        node_id: (areas_data[node_id]["w"], areas_data[node_id]["h"])
        for node_id in areas_data
    }
    neighbours_of = {node_id: [] for node_id in sizes}
    for edge in edges:
        if edge["a"] in neighbours_of and edge["b"] in neighbours_of:
            neighbours_of[edge["a"]].append(edge["b"])
            neighbours_of[edge["b"]].append(edge["a"])

    from collections import deque

    start = graph["start"]
    rects: Dict[str, Rect] = {}
    if start in sizes:
        w, h = sizes[start]
        rects[start] = (0, 0, w, h)
        queue = deque([start])
        placed_order = [start]
        while queue:
            current = queue.popleft()
            for neighbour in neighbours_of[current]:
                if neighbour in rects:
                    continue
                w, h = sizes[neighbour]
                origin = (0, 0, w, h)
                rects[neighbour] = _snap(rects[current], origin, rects)
                placed_order.append(neighbour)
                queue.append(neighbour)
        for node_id in sizes:
            if node_id not in rects:
                w, h = sizes[node_id]
                rects[node_id] = (0, 0, w, h)

    connections = []
    for edge in edges:
        a, b = edge["a"], edge["b"]
        if a not in rects or b not in rects:
            continue
        if not _touching(rects[a], rects[b]):
            continue
        connections.append(Connection(a=a, b=b, cell=_door_cell(rects[a], rects[b])))

    areas = [
        Area(node_id, types.get(node_id, "corridor"), tuple(rects[node_id]))
        for node_id in rects
    ]
    spec = LevelSpec(
        name=graph["name"],
        theme="industrial",
        grid=192,
        wall_thickness=16,
        floor_thickness=16,
        height=256,
        door_height=128,
        areas=areas,
        connections=connections,
        start=graph["start"],
        goal=graph["goal"],
    )
    validate(spec)
    return spec
