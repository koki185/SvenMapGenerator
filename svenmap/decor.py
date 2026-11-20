"""Декоративные строительные компоненты (этап 4).

Все элементы ставятся кодом и не требуют ручной работы в редакторе.
Ограничения: декор не должен перекрывать дверные проёмы и центральный путь —
поэтому позиции фильтруются по расстоянию до дверей и до центра комнаты.
"""

import math

from .geometry import Bounds


def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _dist_to_segment(point, a, b):
    """Расстояние от точки до отрезка — для резервирования проходов."""
    ax, ay = a
    bx, by = b
    px, py = point
    dx, dy = bx - ax, by - ay
    length_sq = dx * dx + dy * dy
    if length_sq < 1e-9:
        return _dist(point, a)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length_sq))
    return _dist(point, (ax + t * dx, ay + t * dy))


def _clear_path(point, segments, margin=44.0):
    """Не ставить декор на маршруте между дверями и центром комнаты."""
    return all(_dist_to_segment(point, a, b) >= margin
               for a, b in segments)


def _grid_candidates(rect, inset=96, step=256):
    x0, y0, x1, y1 = rect
    if x1 - x0 < inset * 2 + 32 or y1 - y0 < inset * 2 + 32:
        return []
    xs, ys = [], []
    x = x0 + inset
    while x <= x1 - inset:
        xs.append(x)
        x += step
    if xs[-1] != x1 - inset:
        xs.append(x1 - inset)
    y = y0 + inset
    while y <= y1 - inset:
        ys.append(y)
        y += step
    if ys[-1] != y1 - inset:
        ys.append(y1 - inset)
    return [(x, y) for y in ys for x in xs]


def _near_center(point, rect, radius):
    cx = (rect[0] + rect[2]) / 2.0
    cy = (rect[1] + rect[3]) / 2.0
    return _dist(point, (cx, cy)) < radius


def _clear(point, doors, radius):
    return all(_dist(point, door) >= radius for door in doors)


def add_columns(m, rect, profile, rng, doors, spec, segments=()):
    """Колонны по периметру комнаты. Высота — от пола до потолка."""
    z0, z1 = spec.floor_thickness, spec.height
    size = 32.0
    cells = [
        c for c in _grid_candidates(rect)
        if (_clear(c, doors, 160) and not _near_center(c, rect, 128)
                and _clear_path(c, segments))
    ]
    rng.shuffle(cells)
    for x, y in cells[:2]:
        m.add_box(
            Bounds(x - size / 2, y - size / 2, z0,
                   x + size / 2, y + size / 2, z1),
            profile.accent,
        )


def add_crates(m, rect, profile, rng, doors, spec, segments=()):
    """Ящики у стен склада. Низкие, до 64 юнитов."""
    z0 = spec.floor_thickness
    cells = [
        c for c in _grid_candidates(rect)
        if (_clear(c, doors, 176) and not _near_center(c, rect, 128)
                and _clear_path(c, segments))
    ]
    rng.shuffle(cells)
    for x, y in cells[:4]:
        size = rng.choice((48.0, 64.0))
        height = rng.choice((48.0, 64.0))
        m.add_box(
            Bounds(x - size / 2, y - size / 2, z0,
                   x + size / 2, y + size / 2, z0 + height),
            profile.accent,
        )


def add_pipes(m, rect, profile, rng, doors, spec, segments=()):
    """Трубы под потолком вдоль стен. Выше игрока — путь не блокируют."""
    x0, y0, x1, y1 = rect
    z = spec.height - 32
    thick = 12.0
    walls = ["north", "south", "east", "west"]
    rng.shuffle(walls)
    for wall in walls[:2]:
        if wall == "north":
            box = Bounds(x0 + 16, y1 - 24 - thick / 2, z - thick / 2,
                         x1 - 16, y1 - 24 + thick / 2, z + thick / 2)
        elif wall == "south":
            box = Bounds(x0 + 16, y0 + 24 - thick / 2, z - thick / 2,
                         x1 - 16, y0 + 24 + thick / 2, z + thick / 2)
        elif wall == "east":
            box = Bounds(x1 - 24 - thick / 2, y0 + 16, z - thick / 2,
                         x1 - 24 + thick / 2, y1 - 16, z + thick / 2)
        else:
            box = Bounds(x0 + 24 - thick / 2, y0 + 16, z - thick / 2,
                         x0 + 24 + thick / 2, y1 - 16, z + thick / 2)
        m.add_box(box, profile.accent)


def _panel(m, wall, rect, profile, spec, fraction):
    x0, y0, x1, y1 = rect
    z0 = spec.floor_thickness + 48
    z1 = z0 + 96
    depth, half = 8.0, 32.0
    if wall in ("west", "east"):
        along = y0 + (y1 - y0) * fraction
        if along - half < y0 + 16 or along + half > y1 - 16:
            return
        if wall == "west":
            box = Bounds(x0 + 8, along - half, z0, x0 + 8 + depth, along + half, z1)
        else:
            box = Bounds(x1 - 8 - depth, along - half, z0, x1 - 8, along + half, z1)
    else:
        along = x0 + (x1 - x0) * fraction
        if along - half < x0 + 16 or along + half > x1 - 16:
            return
        if wall == "south":
            box = Bounds(along - half, y0 + 8, z0, along + half, y0 + 8 + depth, z1)
        else:
            box = Bounds(along - half, y1 - 8 - depth, z0, along + half, y1 - 8, z1)
    m.add_box(box, profile.accent)


def add_panels(m, rect, profile, rng, doors, spec, segments=()):
    """Небольшие панели на внутренней поверхности стен.

    Позиции запоминаются в meta: mechanics использует их, чтобы не
    поставить кнопку вплотную к панели. Панели также не ставятся у дверей
    и на зарезервированных маршрутах.
    """
    x0, y0, x1, y1 = rect
    walls = ["west", "east", "south", "north"]
    rng.shuffle(walls)
    placed = 0
    for wall in walls:
        if placed >= 2:
            break
        for fraction in rng.sample((0.35, 0.65), 2):
            if wall in ("west", "east"):
                center = (x0 + 12 if wall == "west" else x1 - 12,
                          y0 + (y1 - y0) * fraction)
            else:
                center = (x0 + (x1 - x0) * fraction,
                          y0 + 12 if wall == "south" else y1 - 12)
            if not _clear(center, doors, 96):
                continue
            if not _clear_path(center, segments):
                continue
            before = len(m.brushes)
            _panel(m, wall, rect, profile, spec, fraction)
            if len(m.brushes) > before:
                m.meta.setdefault("panels", []).append(m.solids[-1])
                placed += 1
            if placed >= 2:
                break


def add_platform(m, rect, profile, rng, doors, spec, segments=()):
    """Возвышение в углу арены с одной ступенью."""
    x0, y0, x1, y1 = rect
    z0 = spec.floor_thickness
    size, inset = 128.0, 96.0
    corners = [(x0, y0), (x1, y0), (x0, y1), (x1, y1)]
    rng.shuffle(corners)
    for cx, cy in corners:
        px = cx + inset if cx == x0 else cx - inset - size
        py = cy + inset if cy == y0 else cy - inset - size
        center = (px + size / 2, py + size / 2)
        if not _clear(center, doors, 192) or _near_center(center, rect, 160):
            continue
        if not _clear_path(center, segments, margin=96):
            continue
        m.add_box(Bounds(px, py, z0, px + size, py + size, z0 + 16),
                  profile.accent)
        m.add_box(Bounds(px + size - 64, py + size - 64, z0,
                         px + size, py + size, z0 + 8), profile.accent)
        return


GENERATORS = {
    "columns": add_columns,
    "crates": add_crates,
    "pipes": add_pipes,
    "panels": add_panels,
    "platform": add_platform,
}


def decorate(m, rect, profile, rng, doors, spec, segments=()):
    for kind in profile.decor:
        generator = GENERATORS.get(kind)
        if generator is not None:
            generator(m, rect, profile, rng, doors, spec, segments)
