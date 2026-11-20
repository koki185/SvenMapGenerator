"""Библиотека строительных функций (этапы 2 и 4).

Стены не задаются вручную: они строятся по рёбрам занятых клеток.
Если соседней клетки нет — наружная стена. Если сосед из другой
площади — внутренняя стена. На связях вместо нижней части стены ставится
только перемычка, то есть получается проём.

С этапа 4 геометрию дополняют декоративные компоненты из decor.py,
а оформление берётся из профиля типа помещения (profiles.py).
"""

import random
from dataclasses import replace

from . import decor
from .geometry import Bounds
from .lighting import place_lights
from .mapfile import MapFile, num
from .profiles import get_profile
from .textures import TextureRef

DOOR_LINTEL_TEXTURE = "METAL_WALL01B"

# В реальных картах точка игрока стоит на пол + 48...52 юнита.
# Hull игрока ~72 юнита с центром в origin: при смещении 8 юнитов
# нижняя половина уходит в пол и игрок не может двигаться.
SPAWN_Z_OFFSET = 48


def _world_rect(spec, area):
    g = spec.grid
    x0, y0, x1, y1 = area.cell_rect
    return x0 * g, y0 * g, x1 * g, y1 * g


def _doors_by_area(spec):
    """Мировые координаты центров дверей для каждой площади."""
    result = {area.id: [] for area in spec.areas}
    g = spec.grid
    for conn in spec.connections:
        cx, cy = conn.cell
        result[conn.a].append(((cx + 0.5) * g, (cy + 0.5) * g))
        dx, dy = conn.direction
        result[conn.b].append(((cx + dx + 0.5) * g, (cy + dy + 0.5) * g))
    return result


def _path_segments(spec, area, area_doors):
    """Маршруты от каждой двери к центру комнаты — их нельзя заставлять декором."""
    center = spec.area_center(area.id)
    points = area_doors or [center]
    return [(point, center) for point in points]


def _tex(texture_lib, name, surface):
    if texture_lib is None:
        return TextureRef(name)
    return texture_lib.ref(name, surface)


def build_level(spec, wads, seed=0, use_decor=True, texture_lib=None):
    """Превратить LevelSpec в MapFile."""
    t = spec.wall_thickness
    g = spec.grid
    z_floor = spec.floor_thickness
    z_top = spec.height
    cell_map = spec.cell_map()
    doors = _doors_by_area(spec)

    # Рёбра, на которых должен быть проём. Ключ — пара соседних клеток.
    door_edges = set()
    for conn in spec.connections:
        cx, cy = conn.cell
        dx, dy = conn.direction
        door_edges.add(frozenset(((cx, cy), (cx + dx, cy + dy))))

    m = MapFile(wads=wads, skyname="DESERT")
    m.meta["doors"] = [point for points in doors.values() for point in points]

    # Пол и потолок — по одному brush на площадь.
    for area in spec.areas:
        profile = get_profile(spec.theme, area.type)
        x0, y0, x1, y1 = _world_rect(spec, area)
        m.add_box(
            Bounds(x0 - t / 2, y0 - t / 2, 0,
                   x1 + t / 2, y1 + t / 2, z_floor),
            _tex(texture_lib, profile.floor, "floor"),
        )
        m.add_box(
            Bounds(x0 - t / 2, y0 - t / 2, z_top,
                   x1 + t / 2, y1 + t / 2, z_top + z_floor),
            _tex(texture_lib, profile.ceiling, "ceiling"),
        )

    # Стены — по рёбрам клеток. Проверяем все 4 направления: если
    # смотреть только «вправо» и «вверх», теряются южные и западные
    # наружные стены и в карте появляется LEAK.
    seen_edges = set()
    for cell, area in sorted(cell_map.items()):
        cx, cy = cell
        wall_texture = get_profile(spec.theme, area.type).wall
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            neighbour = (cx + dx, cy + dy)
            edge_key = frozenset((cell, neighbour))
            if edge_key in seen_edges:
                continue
            seen_edges.add(edge_key)

            neighbour_area = cell_map.get(neighbour)

            if dx != 0:
                edge = (cx + (1 if dx > 0 else 0)) * g
                bx0, bx1 = edge - t / 2, edge + t / 2
                by0, by1 = cy * g, (cy + 1) * g
            else:
                edge = (cy + (1 if dy > 0 else 0)) * g
                bx0, bx1 = cx * g, (cx + 1) * g
                by0, by1 = edge - t / 2, edge + t / 2

            def box(z0, z1):
                return Bounds(bx0, by0, z0, bx1, by1, z1)

            wall_ref = _tex(texture_lib, wall_texture, "wall")
            if neighbour_area is None:
                m.add_box(box(z_floor, z_top), wall_ref)
            elif neighbour_area.id != area.id:
                if edge_key in door_edges:
                    # Проём: только перемычка над дверью.
                    m.add_box(box(spec.door_height, z_top),
                              _tex(texture_lib, DOOR_LINTEL_TEXTURE, "accent"))
                else:
                    m.add_box(box(z_floor, z_top), wall_ref)
            # Сосед из той же площади — стены нет.

    # Декор по профилям помещений.
    if use_decor:
        for area in spec.areas:
            profile = get_profile(spec.theme, area.type)
            decor_profile = replace(
                profile,
                accent=_tex(texture_lib, profile.accent, "accent"),
            )
            rng = random.Random("{}:{}".format(seed, area.id))
            decor.decorate(
                m, _world_rect(spec, area), decor_profile, rng,
                doors[area.id], spec,
                segments=_path_segments(spec, area, doors[area.id]),
            )

    # Стартовая точка и свет по зонам.
    sx, sy = spec.area_center(spec.start)
    m.add_point_entity(
        "info_player_start",
        origin="{} {} {}".format(
            num(sx), num(sy), spec.floor_thickness + SPAWN_Z_OFFSET
        ),
        angles="0 0 0",
    )
    for area in spec.areas:
        profile = get_profile(spec.theme, area.type)
        place_lights(
            m, spec, area, profile, doors[area.id],
            is_goal=(area.id == spec.goal),
        )

    return m
