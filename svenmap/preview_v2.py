"""SVG-превью планировки graph_v2 (P3.0).

Рисует blueprint сверху: реальные L/T/U-формы по прямоугольникам клеток,
связи по типам, цели, дверь, знак выхода и этажи отдельными панелями.
Это не замена рендеру в движке, но быстрый способ увидеть композицию
глазами — цифры QA такой «слепой угол» не ловят.
"""

from typing import Dict, List, Tuple

from .v2_entities import GRID

MARGIN = 60
WIDTH = 1000
FLOOR_HEADER = 42
PANEL_GAP = 26

TYPE_COLORS = {
    "spawn": "#4dff88",
    "objective": "#ff6b6b",
    "combat": "#ff9f43",
    "arena": "#ff9f43",
    "lab": "#5aa9ff",
    "storage": "#c8a24d",
    "secret": "#c77dff",
    "corridor": "#8fa3b0",
    "transition": "#ffd24d",
    "hub": "#7fd1c1",
}
EDGE_COLORS = {
    "main": "#6fcf97",
    "branch": "#5aa9ff",
    "loop": "#ffd24d",
    "secret": "#c77dff",
    "vertical": "#ff9f43",
    "locked": "#ff6b6b",
}


def _area_cells(area: dict) -> List[Tuple[int, int]]:
    """Мировые координаты клеток комнаты (клетка = 192 юнита)."""
    cells = area.get("cells")
    if cells:
        return [(area["x"] + c[0], area["y"] + c[1]) for c in cells]
    return [
        (x, y)
        for x in range(area["x"], area["x"] + area["w"])
        for y in range(area["y"], area["y"] + area["h"])
    ]


def _cell_center(cell: Tuple[int, int]) -> Tuple[float, float]:
    return ((cell[0] + 0.5) * GRID, (cell[1] + 0.5) * GRID)


def _area_center(area: dict) -> Tuple[float, float]:
    cells = _area_cells(area)
    return (
        sum(c[0] for c in cells) / len(cells) * GRID,
        sum(c[1] for c in cells) / len(cells) * GRID,
    )


def write_blueprint_preview(blueprint: dict, m, out_path: str,
                            name: str = "") -> str:
    """Записать SVG-превью blueprint в out_path, вернуть путь."""
    graph = blueprint["graph"]
    spatial = blueprint["spatial"]
    areas = spatial["areas"]
    connections = spatial["connections"]
    area_by_id = {a["node_id"]: a for a in areas}
    node_by_id = {n["id"]: n for n in graph["nodes"]}

    cells_by_floor: Dict[int, List[Tuple[int, int]]] = {}
    for area in areas:
        cells_by_floor.setdefault(area.get("floor", 0), []).extend(
            _area_cells(area)
        )
    if not cells_by_floor:
        cells_by_floor[0] = []

    def floor_geometry(floor):
        """Свой масштаб на этаж: иначе этаж 0 сжимается из-за далёкого F1."""
        cells = cells_by_floor.get(floor, [])
        if cells:
            min_cx = min(c[0] for c in cells)
            max_cx = max(c[0] for c in cells) + 1
            min_cy = min(c[1] for c in cells)
            max_cy = max(c[1] for c in cells) + 1
        else:
            min_cx = max_cx = min_cy = max_cy = 0
        span_x = max(1, (max_cx - min_cx) * GRID)
        span_y = max(1, (max_cy - min_cy) * GRID)
        scale = (WIDTH - 2 * MARGIN) / max(span_x, span_y, 1)
        scale = min(scale, 100.0 / GRID)  # комната не растягивается на экран
        panel_h = int(span_y * scale) + FLOOR_HEADER + 22

        def px(x, y, top):
            return (
                MARGIN + (x - min_cx * GRID) * scale,
                top + FLOOR_HEADER + (max_cy * GRID - y) * scale,
            )
        return px, panel_h, scale

    heights = {f: floor_geometry(f)[1] for f in cells_by_floor}
    total_h = 70 + sum(heights.values()) + PANEL_GAP * (
        len(cells_by_floor) - 1) + 46

    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="{}" '
        'height="{}" viewBox="0 0 {} {}">'.format(
            WIDTH, total_h, WIDTH, total_h),
        '<rect width="100%" height="100%" fill="#111418"/>',
        '<text x="24" y="32" fill="#e8e8e8" font-family="sans-serif" '
        'font-size="17" font-weight="bold">{} — планировка (вид сверху)'
        '</text>'.format(name or graph.get("name", "map")),
        '<text x="24" y="52" fill="#8895a3" font-family="sans-serif" '
        'font-size="12">seed {} · {} комнат · {} связей · {} этаж(ей)'
        '</text>'.format(
            graph.get("seed", 0), len(areas), len(connections),
            len(cells_by_floor)),
    ]

    y_offset = 70
    for floor in sorted(cells_by_floor):
        px_floor, panel_h, scale = floor_geometry(floor)

        def px(x, y):
            return px_floor(x, y, y_offset)

        lines.append(
            '<text x="24" y="{}" fill="#d8e2ea" font-family="sans-serif" '
            'font-size="13" font-weight="bold">ЭТАЖ {}</text>'.format(
                y_offset + 24, floor)
        )
        lines.append(
            '<line x1="24" y1="{}" x2="{}" y2="{}" stroke="#39434d" '
            'stroke-width="1"/>'.format(
                y_offset + 34, WIDTH - 24, y_offset + 34)
        )

        floor_areas = [
            a for a in areas if a.get("floor", 0) == floor
        ]

        # Пол комнаты — по каждой занятой клетке, чтобы L/T/U были видны.
        for area in floor_areas:
            node = node_by_id.get(area["node_id"], {})
            color = TYPE_COLORS.get(node.get("type", ""), "#9ecbff")
            if area["node_id"] == graph.get("goal"):
                color = TYPE_COLORS["objective"]
            for cx, cy in _area_cells(area):
                sx, sy = px(cx * GRID, (cy + 1) * GRID)
                lines.append(
                    '<rect x="{:.1f}" y="{:.1f}" width="{:.1f}" '
                    'height="{:.1f}" fill="{}" fill-opacity="0.13" '
                    'stroke="{}" stroke-opacity="0.28" '
                    'stroke-width="0.5"/>'.format(
                        sx, sy, GRID * scale, GRID * scale, color, color)
                )
            ex, ey = _area_center(area)
            lx, ly = px(ex, ey)
            lines.append(
                '<text x="{:.1f}" y="{:.1f}" fill="{}" '
                'font-family="sans-serif" font-size="11" '
                'font-weight="bold" text-anchor="middle">{}</text>'.format(
                    lx, ly - 4, color, area["node_id"])
            )
            lines.append(
                '<text x="{:.1f}" y="{:.1f}" fill="#7e8c99" '
                'font-family="sans-serif" font-size="9" '
                'text-anchor="middle">{}/{}</text>'.format(
                    lx, ly + 9, node.get("type", "?"),
                    area.get("shape", "rect"))
            )

        # Связи: линия между центрами комнат + точка общего портала.
        # У прямых соединений portal_a == portal_b (общая клетка), поэтому
        # линия по порталам была бы нулевой длины и невидимой.
        for conn in connections:
            a = area_by_id.get(conn["a"])
            b = area_by_id.get(conn["b"])
            if not a or not b:
                continue
            if a.get("floor", 0) != floor and b.get("floor", 0) != floor:
                continue
            color = EDGE_COLORS.get(conn.get("type", "main"), "#6fcf97")
            p1 = px(*_area_center(a))
            p2 = px(*_area_center(b))
            dash = '' if conn.get("direct", True) else \
                ' stroke-dasharray="7 5"'
            lines.append(
                '<line x1="{:.1f}" y1="{:.1f}" x2="{:.1f}" y2="{:.1f}" '
                'stroke="{}" stroke-width="2.4" stroke-opacity="0.75"{}/>'.format(
                    p1[0], p1[1], p2[0], p2[1], color, dash)
            )
            portal = px(*_cell_center(tuple(conn["portal_a"])))
            lines.append(
                '<circle cx="{:.1f}" cy="{:.1f}" r="4" fill="{}" '
                'stroke="#0b0e12" stroke-width="1"/>'.format(
                    portal[0], portal[1], color)
            )

        # Вертикальные переходы — оранжевой пунктирной стрелкой.
        for vc in spatial.get("vertical_connectors", []):
            a = area_by_id.get(vc.get("area_a"))
            b = area_by_id.get(vc.get("area_b"))
            if not a or not b:
                continue
            if floor not in (a.get("floor", 0), b.get("floor", 0)):
                continue
            # Не рисуем линию в координатах другого этажа — она ушла бы
            # за край панели. Оставляем пометку у комнаты на этом этаже.
            here = a if a.get("floor", 0) == floor else b
            other_floor = b.get("floor", 0) if here is a else a.get("floor", 0)
            p = px(*_area_center(here))
            lines.append(
                '<text x="{:.1f}" y="{:.1f}" fill="#ffb56b" '
                'font-family="sans-serif" font-size="11" '
                'font-weight="bold">↕ {} → этаж {}</text>'.format(
                    p[0] + 6, p[1] - 12,
                    vc.get("type", "stairs"), other_floor)
            )

        # Маркеры механики (этаж 0 — где стоят Objectives).
        if floor == 0:
            mech = m.meta.get("mechanics", {})
            for item in mech.get("items", []):
                sx, sy = px(item["center"][0], item["center"][1])
                lines.append(
                    '<circle cx="{:.1f}" cy="{:.1f}" r="6" '
                    'fill="#ffe066" stroke="#000" stroke-width="1"/>'.format(
                        sx, sy)
                )
            for i, button in enumerate(mech.get("buttons", []), start=1):
                sx, sy = px(button["center"][0], button["center"][1])
                lines.append(
                    '<rect x="{:.1f}" y="{:.1f}" width="11" height="11" '
                    'fill="#ffe066" stroke="#000" stroke-width="1"/>'.format(
                        sx - 5, sy - 5)
                )
                lines.append(
                    '<text x="{:.1f}" y="{:.1f}" fill="#ffe066" '
                    'font-family="sans-serif" font-size="9">G{}</text>'.format(
                        sx + 8, sy + 3, i)
                )
            door = mech.get("door_bounds")
            if door is not None:
                d1 = px(door.x0, door.y1)
                d2 = px(door.x1, door.y0)
                lines.append(
                    '<rect x="{:.1f}" y="{:.1f}" width="{:.1f}" '
                    'height="{:.1f}" fill="#ff5252" fill-opacity="0.45" '
                    'stroke="#ff5252" stroke-width="2"/>'.format(
                        min(d1[0], d2[0]), min(d1[1], d2[1]),
                        max(6, abs(d2[0] - d1[0])),
                        max(6, abs(d2[1] - d1[1])))
                )
            for entity in m.entities:
                if (entity.get("classname") == "env_sprite"
                        and entity.get("targetname") == "exit_sign"):
                    origin = [float(v) for v in entity["origin"].split()]
                    sx, sy = px(origin[0], origin[1])
                    lines.append(
                        '<rect x="{:.1f}" y="{:.1f}" width="96" '
                        'height="16" fill="#111418" fill-opacity="0.85"/>'
                        .format(sx - 48, sy - 32)
                    )
                    lines.append(
                        '<text x="{:.1f}" y="{:.1f}" fill="#ff8ad8" '
                        'font-family="sans-serif" font-size="11" '
                        'font-weight="bold" text-anchor="middle">'
                        'LEVEL CHANGE</text>'.format(sx, sy - 20)
                    )

        y_offset += panel_h + PANEL_GAP

    lines.append(
        '<text x="24" y="{}" fill="#8895a3" font-family="sans-serif" '
        'font-size="11">жёлтое — цели, красное — дверь, розовое — знак '
        'выхода, пунктир — коридор/переход; цвет комнат — тип узла'
        '</text>'.format(total_h - 18)
    )
    lines.append("</svg>")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return out_path
