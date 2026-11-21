"""Общие сущности для v2/v3 builder (спавны, свет, вертикальный переход)."""

from .geometry import Bounds
from .mapfile import num
from .textures import TextureRef

GRID = 192
HEIGHT = 256
FLOOR_T = 16


def area_center_world(area):
    """Центр реально занятой клетки (не bounding box вырезанной формы)."""
    cells = area.get("cells")
    if cells:
        tx, ty = area["w"] / 2.0, area["h"] / 2.0
        cx, cy = min(
            cells,
            key=lambda c: (c[0] - tx) ** 2 + (c[1] - ty) ** 2,
        )
        return (
            (area["x"] + cx + 0.5) * GRID,
            (area["y"] + cy + 0.5) * GRID,
        )
    return (
        (area["x"] + area["w"] / 2) * GRID,
        (area["y"] + area["h"] / 2) * GRID,
    )


def add_basic_entities(m, blueprint):
    graph = blueprint["graph"]
    spatial = blueprint["spatial"]
    areas = {a["node_id"]: a for a in spatial["areas"]}

    spawn = areas.get(graph["start"])
    if spawn:
        cx, cy = area_center_world(spawn)
        base = spawn.get("floor", 0) * (HEIGHT + FLOOR_T)
        m.add_point_entity(
            "info_player_start",
            origin="{} {} {}".format(num(cx), num(cy), base + 48),
            angles="0 0 0",
        )
        for dx, dy in ((-64, -64), (64, -64), (-64, 64), (64, 64)):
            m.add_point_entity(
                "info_player_deathmatch",
                origin="{} {} {}".format(num(cx + dx), num(cy + dy), base + 48),
                angles="0 0 0",
            )

    for area in areas.values():
        cx, cy = area_center_world(area)
        floor_base = area.get("floor", 0) * (HEIGHT + FLOOR_T)
        m.add_point_entity(
            "light",
            origin="{} {} {}".format(num(cx), num(cy), floor_base + 240),
            angles="0 0 0",
            _light="255 255 255 200",
            _falloff="0",
            _fade="1.0",
            style="0",
            spawnflags="0",
        )


def add_vertical_transition(m, blueprint):
    """Лестница + телепорт на верхний этаж."""
    made = []
    for connector in blueprint["spatial"].get("vertical_connectors", []):
        la = connector["landing_a"]
        wx, wy = la[0] * GRID, la[1] * GRID
        steps = 8
        for i in range(steps):
            m.add_box(
                Bounds(wx - 48, wy - 48, FLOOR_T + i * 32,
                       wx + 48, wy + 48, FLOOR_T + (i + 1) * 32),
                TextureRef("BASEWALL01A", 1.0, 1.0),
            )
        top_z = FLOOR_T + steps * 32 + 24
        dest_name = "upper_dest_" + connector["id"]
        upper = next(
            a for a in blueprint["spatial"]["areas"]
            if a["node_id"] == connector["area_b"]
        )
        dx = int((upper["x"] + upper["w"] / 2) * GRID)
        dy = int((upper["y"] + upper["h"] / 2) * GRID)
        upper_z = upper.get("floor", 0) * (HEIGHT + FLOOR_T) + FLOOR_T + 24
        m.add_point_entity(
            "info_teleport_destination",
            targetname=dest_name,
            origin="{} {} {}".format(dx, dy, upper_z),
            angles="0 0 0",
        )
        m.add_brush_entity(
            "trigger_teleport",
            Bounds(wx - 48, wy - 48, FLOOR_T + steps * 32,
                   wx + 48, wy + 48, top_z + 56),
            TextureRef("AAATRIGGER", 1.0, 1.0),
            target=dest_name,
        )
        made.append(connector["id"])
    return made
