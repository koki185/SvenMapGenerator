"""Визуальная проверка планировки: SVG-схема сверху.

Это не замена рендеру в игре, но быстрый способ увидеть комнаты, двери,
свет и найденный маршрут без запуска Sven Co-op. Файл открывается
любым браузером.
"""

from .profiles import get_profile

MARGIN = 60
WIDTH = 900
LIGHT_RADIUS_SCALE = 0.012


def _rgb(color):
    parts = color.split()
    if len(parts) >= 3:
        try:
            return "#{:02x}{:02x}{:02x}".format(
                int(parts[0]), int(parts[1]), int(parts[2])
            )
        except ValueError:
            pass
    return "#dddddd"


def write_preview(spec, m, path_cells, grid, out_path):
    g = spec.grid
    rects = {}
    for area in spec.areas:
        x0, y0, x1, y1 = area.cell_rect
        rects[area.id] = (x0 * g, y0 * g, x1 * g, y1 * g)

    all_x = [v for r in rects.values() for v in (r[0], r[2])]
    all_y = [v for r in rects.values() for v in (r[1], r[3])]
    min_x, max_x = min(all_x), max(all_x)
    min_y, max_y = min(all_y), max(all_y)
    span_x, span_y = max_x - min_x, max_y - min_y
    scale = (WIDTH - 2 * MARGIN) / max(span_x, span_y, 1)
    height = int(span_y * scale + 2 * MARGIN)

    def px(x, y):
        return (MARGIN + (x - min_x) * scale,
                MARGIN + (max_y - y) * scale)

    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="{}" height="{}" '
        'viewBox="0 0 {} {}">'.format(WIDTH, height, WIDTH, height),
        '<rect width="100%" height="100%" fill="#111418"/>',
        '<text x="20" y="26" fill="#e8e8e8" font-family="sans-serif" '
        'font-size="16">{} — планировка (вид сверху)</text>'.format(spec.name),
    ]

    # Комнаты.
    for area in spec.areas:
        x0, y0, x1, y1 = rects[area.id]
        sx, sy = px(x0, y1)
        w, h = (x1 - x0) * scale, (y1 - y0) * scale
        color = _rgb(get_profile(spec.theme, area.type).light_color)
        lines.append(
            '<rect x="{:.1f}" y="{:.1f}" width="{:.1f}" height="{:.1f}" '
            'fill="{}" fill-opacity="0.10" stroke="{}" stroke-width="2"/>'
            .format(sx, sy, w, h, color, color)
        )
        cx, cy = px((x0 + x1) / 2, (y0 + y1) / 2)
        lines.append(
            '<text x="{:.1f}" y="{:.1f}" fill="#ffffff" font-family="sans-serif" '
            'font-size="12" text-anchor="middle">{}/{}</text>'
            .format(cx, cy - 10, area.id, area.type)
        )

    # Маршрут.
    if path_cells:
        points = []
        for cx, cy in path_cells:
            wx = grid["min_x"] + (cx + 0.5) * grid["cell"]
            wy = grid["min_y"] + (cy + 0.5) * grid["cell"]
            points.append("{:.1f},{:.1f}".format(*px(wx, wy)))
        lines.append(
            '<polyline points="{}" fill="none" stroke="#4dff88" '
            'stroke-width="3" stroke-opacity="0.85"/>'.format(" ".join(points))
        )

    # Двери.
    for door_x, door_y in m.meta.get("doors", []):
        dx, dy = px(door_x, door_y)
        lines.append(
            '<circle cx="{:.1f}" cy="{:.1f}" r="5" fill="#ffd24d" '
            'stroke="#000" stroke-width="1"/>'.format(dx, dy)
        )

    # Механика: дверь и кнопки-генераторы.
    mech = m.meta.get("mechanics")
    if mech:
        b = mech["door_bounds"]
        dx0, dy0 = px(b.x0, b.y1)
        dx1, dy1 = px(b.x1, b.y0)
        lines.append(
            '<rect x="{:.1f}" y="{:.1f}" width="{:.1f}" height="{:.1f}" '
            'fill="#ff5252" fill-opacity="0.35" stroke="#ff5252" '
            'stroke-width="2"/>'.format(
                min(dx0, dx1), min(dy0, dy1),
                abs(dx1 - dx0), abs(dy1 - dy0))
        )
        for i, button in enumerate(mech.get("buttons", []), start=1):
            bx, by = px(*button["center"])
            lines.append(
                '<rect x="{:.1f}" y="{:.1f}" width="10" height="10" '
                'fill="#5aa9ff" stroke="#fff" stroke-width="0.8"/>'
                .format(bx - 5, by - 5)
            )
            lines.append(
                '<text x="{:.1f}" y="{:.1f}" fill="#9ecbff" '
                'font-family="sans-serif" font-size="11" '
                'text-anchor="start">GEN{}</text>'.format(bx + 9, by + 4, i)
            )

    # Свет.
    for light in m.meta.get("lights", []):
        lx, ly = px(light["x"], light["y"])
        color = _rgb(light["color"])
        radius = max(3.0, light["brightness"] * LIGHT_RADIUS_SCALE)
        lines.append(
            '<circle cx="{:.1f}" cy="{:.1f}" r="{:.1f}" fill="{}" '
            'fill-opacity="0.55" stroke="#fff" stroke-width="0.6"/>'
            .format(lx, ly, radius, color)
        )

    # Старт и цель.
    for label, area_id, color in (
        ("START", spec.start, "#4dff88"), ("GOAL", spec.goal, "#ff6b6b")
    ):
        x, y = spec.area_center(area_id)
        sx, sy = px(x, y)
        lines.append(
            '<text x="{:.1f}" y="{:.1f}" fill="{}" font-family="sans-serif" '
            'font-size="13" font-weight="bold" text-anchor="middle">{}</text>'
            .format(sx, sy + 18, color, label)
        )

    lines.append(
        '<text x="20" y="{}" fill="#888" font-family="sans-serif" '
        'font-size="11">жёлтые точки — проёмы, красное — дверь, GEN — кнопки, '
        'цветные круги — свет, зелёная линия — маршрут</text>'.format(height - 14)
    )
    lines.append("</svg>")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return out_path
