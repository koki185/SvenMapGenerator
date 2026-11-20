"""Система освещения: зоны, подсветка дверей и акцент на цели.

Вместо одного светильника в центре комнаты ставим сетку светильников
с шагом примерно 384 юнита — так большая лаборатория не остаётся тёмной
по краям. У дверей добавляются слабые локальные источники, а целевая зона
получает более яркий свет, чтобы читалась цель уровня.
"""

from .mapfile import num

LIGHT_SPACING = 384.0
DOOR_LIGHT_BRIGHTNESS = 60
GOAL_BRIGHTNESS_BONUS = 80


def _area_world_rect(spec, area):
    g = spec.grid
    x0, y0, x1, y1 = area.cell_rect
    return x0 * g, y0 * g, x1 * g, y1 * g


def add_light(m, x, y, z, color, brightness, meta=None, kind="area"):
    m.add_point_entity(
        "light",
        origin="{} {} {}".format(num(x), num(y), num(z)),
        angles="0 0 0",
        _light="{} {}".format(color, int(round(brightness))),
        _falloff="0",
        _fade="1.0",
        style="0",
        spawnflags="0",
    )
    if meta is not None:
        meta.setdefault("lights", []).append({
            "x": x, "y": y, "z": z, "color": color,
            "brightness": brightness, "kind": kind,
        })


def place_lights(m, spec, area, profile, doors, is_goal=False):
    """Расставить светильники для одной площади."""
    meta = getattr(m, "meta", None)
    x0, y0, x1, y1 = _area_world_rect(spec, area)
    width, depth = x1 - x0, y1 - y0
    nx = max(1, int(round(width / LIGHT_SPACING)))
    ny = max(1, int(round(depth / LIGHT_SPACING)))
    count = nx * ny
    brightness = profile.light_brightness * (0.6 if count > 1 else 1.0)
    z = spec.height - 24

    for i in range(nx):
        for j in range(ny):
            x = x0 + (i + 0.5) * width / nx
            y = y0 + (j + 0.5) * depth / ny
            add_light(m, x, y, z, profile.light_color, brightness,
                      meta, kind="area")

    # Слабая подсветка у дверей — чтобы проём читался в тёмном коридоре.
    for door_x, door_y in doors:
        add_light(m, door_x, door_y, z - 32,
                  profile.light_color, DOOR_LIGHT_BRIGHTNESS,
                  meta, kind="door")

    if is_goal:
        gx, gy = spec.area_center(area.id)
        add_light(m, gx, gy, z, profile.light_color,
                  profile.light_brightness + GOAL_BRIGHTNESS_BONUS,
                  meta, kind="goal")
