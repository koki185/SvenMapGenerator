"""Описание уровня в абстрактном виде и загрузка из JSON.

Площади задаются прямоугольниками КЛЕТОК сетки, а не координатами
 brushes. Это позволит библиотеке builders сама считать стены и проёмы.
"""

import json
from dataclasses import dataclass, field

DIRECTIONS = {
    "east": (1, 0),
    "west": (-1, 0),
    "north": (0, 1),
    "south": (0, -1),
}


@dataclass
class Area:
    id: str
    type: str
    # (cx0, cy0, cx1, cy1) — правый и верхний индексы НЕ входят в площадь
    cells: tuple

    @property
    def cell_rect(self):
        return tuple(int(v) for v in self.cells)

    def contains(self, cx, cy):
        x0, y0, x1, y1 = self.cell_rect
        return x0 <= cx < x1 and y0 <= cy < y1

    def cell_list(self):
        x0, y0, x1, y1 = self.cell_rect
        return [(cx, cy) for cy in range(y0, y1) for cx in range(x0, x1)]


@dataclass
class Connection:
    a: str
    b: str
    # клетка площади A, на рёбре которой делается проём
    cell: tuple
    # направление от клетки A к клетке B (определяется при валидации)
    direction: tuple = None


@dataclass
class LevelSpec:
    name: str
    theme: str
    grid: int
    wall_thickness: int
    floor_thickness: int
    height: int
    door_height: int
    areas: list
    connections: list
    start: str
    goal: str
    _cell_map: dict = field(default_factory=dict, repr=False)

    def area(self, area_id):
        for area in self.areas:
            if area.id == area_id:
                return area
        raise KeyError("нет площади с id " + area_id)

    def cell_map(self):
        return self._cell_map

    def area_center(self, area_id):
        x0, y0, x1, y1 = self.area(area_id).cell_rect
        return (
            (x0 + x1) * self.grid / 2.0,
            (y0 + y1) * self.grid / 2.0,
        )


def load_level(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    areas = [
        Area(a["id"], a["type"], tuple(a["cells"]))
        for a in data.get("areas", [])
    ]
    connections = [
        Connection(c["a"], c["b"], tuple(c["cell"]))
        for c in data.get("connections", [])
    ]

    spec = LevelSpec(
        name=data["name"],
        theme=data.get("theme", "industrial"),
        grid=int(data.get("grid", 128)),
        wall_thickness=int(data.get("wall_thickness", 16)),
        floor_thickness=int(data.get("floor_thickness", 16)),
        height=int(data.get("height", 256)),
        door_height=int(data.get("door_height", 128)),
        areas=areas,
        connections=connections,
        start=data["start"],
        goal=data["goal"],
    )
    validate(spec)
    return spec


def validate(spec):
    """Проверить описание до генерации геометрии. При ошибке — ValueError."""
    ids = [a.id for a in spec.areas]
    if len(ids) != len(set(ids)):
        raise ValueError("повторяющиеся id площадей: " + str(ids))

    cell_map = {}
    for area in spec.areas:
        x0, y0, x1, y1 = area.cell_rect
        if x1 <= x0 or y1 <= y0:
            raise ValueError("площадь {} имеет пустой прямоугольник".format(area.id))
        for cell in area.cell_list():
            if cell in cell_map:
                raise ValueError(
                    "клетка {} принадлежит и {}, и {}".format(
                        cell, cell_map[cell].id, area.id
                    )
                )
            cell_map[cell] = area
    spec._cell_map = cell_map

    if spec.door_height <= 0 or spec.door_height >= spec.height:
        raise ValueError("door_height должен быть между 0 и height")
    if spec.wall_thickness <= 0 or spec.wall_thickness >= spec.grid:
        raise ValueError("wall_thickness должен быть меньше grid")

    for conn in spec.connections:
        area_a = spec.area(conn.a)
        spec.area(conn.b)  # проверка существования
        cx, cy = conn.cell
        if not area_a.contains(cx, cy):
            raise ValueError(
                "проём связи {}->{}={} не внутри площади {}".format(
                    conn.a, conn.b, conn.cell, conn.a
                )
            )
        matches = []
        for name, (dx, dy) in DIRECTIONS.items():
            neighbour = cell_map.get((cx + dx, cy + dy))
            if neighbour is not None and neighbour.id == conn.b:
                matches.append((name, (dx, dy)))
        if len(matches) != 1:
            raise ValueError(
                "связь {}->{}: для клетки {} найдено {} соседей из {}. "
                "Ожидался ровно один общий рёберный переход.".format(
                    conn.a, conn.b, conn.cell, len(matches), conn.b
                )
            )
        conn.direction = matches[0][1]

    spec.area(spec.start)
    spec.area(spec.goal)
    return spec
