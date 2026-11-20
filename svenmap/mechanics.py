"""Игровая механика этапа 6: генераторы -> счётчик -> дверь.

Две кнопки-«генератора» бьют в trigger_counter (count=2), тот открывает
func_door, закрывающую вход в целевую комнату. Ключи сущностей сверены
с sven-coop.fgd и реальными .map из SDK.
"""

import math

from .geometry import Bounds
from .mapfile import num
from .validator import build_grid, find_path

DOOR_TEXTURE = "LAB1_DOOR1"
BUTTON_TEXTURE = "+0BUTTON1"
COUNTER_TEXTURE = "NULL"

DOOR_TARGETNAME = "exit_door"
COUNTER_TARGETNAME = "gen_counter"


def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _world_rect(spec, area):
    g = spec.grid
    x0, y0, x1, y1 = area.cell_rect
    return x0 * g, y0 * g, x1 * g, y1 * g


def _door_bounds(spec, conn):
    g, t = spec.grid, spec.wall_thickness
    cx, cy = conn.cell
    dx, dy = conn.direction
    if dx != 0:
        edge = (cx + (1 if dx > 0 else 0)) * g
        bx0, bx1 = edge - t / 2, edge + t / 2
        by0, by1 = cy * g, (cy + 1) * g
    else:
        edge = (cy + (1 if dy > 0 else 0)) * g
        bx0, bx1 = cx * g, (cx + 1) * g
        by0, by1 = edge - t / 2, edge + t / 2
    return Bounds(bx0, by0, spec.floor_thickness, bx1, by1, spec.door_height)


def _button_bounds(spec, area, doors, panels=()):
    x0, y0, x1, y1 = _world_rect(spec, area)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    candidates = []
    # Несколько отступов от стены: если вплотную мешает панель декора,
    # кнопка отодвигается дальше, но остаётся на этой же стене.
    for inset in (24, 56, 88):
        candidates.extend((
            Bounds(cx - 16, y0 + inset, 40, cx + 16, y0 + inset + 8, 56),
            Bounds(cx - 16, y1 - inset - 8, 40, cx + 16, y1 - inset, 56),
            Bounds(x0 + inset, cy - 16, 40, x0 + inset + 8, cy + 16, 56),
            Bounds(x1 - inset - 8, cy - 16, 40, x1 - inset, cy + 16, 56),
        ))

    def panel_distance(point):
        px, py = point
        best = 1e9
        for p in panels:
            dx = max(p.x0 - px, 0.0, px - p.x1)
            dy = max(p.y0 - py, 0.0, py - p.y1)
            best = min(best, math.hypot(dx, dy))
        return best

    def door_distance(point):
        if not doors:
            return 1e9
        return min(_dist(point, d) for d in doors)

    # Не отсекаем кандидаты жёстко: если все «идеальные» заняты,
    # всё равно берём самое свободное место, а не первое попавшееся.
    scored = []
    for bounds in candidates:
        center = ((bounds.x0 + bounds.x1) / 2, (bounds.y0 + bounds.y1) / 2)
        score = min(door_distance(center), panel_distance(center))
        scored.append((score, bounds))
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1]


def _item_positions(m, spec, count, doors, panels):
    """Свободные позиции для предметов в комнатах до двери."""
    grid = build_grid(m.solids, z=24)
    areas = [a for a in spec.areas if a.id != spec.goal]

    def near_panel(point):
        px, py = point
        return any(
            p.x0 - 24 <= px <= p.x1 + 24 and p.y0 - 24 <= py <= p.y1 + 24
            for p in panels
        )

    per_area = {}
    for area in areas:
        cx, cy = spec.area_center(area.id)
        found = []
        for dx, dy in ((0, 0), (72, 0), (-72, 0), (0, 72), (0, -72),
                       (72, 72), (-72, -72), (72, -72), (-72, 72)):
            point = (cx + dx, cy + dy)
            if point in grid["blocked"]:
                continue
            if not all(_dist(point, d) > 96 for d in doors):
                continue
            if near_panel(point):
                continue
            found.append((point[0], point[1], spec.floor_thickness + 8, area.id))
        per_area[area.id] = found

    result = []
    while len(result) < count:
        added = False
        for area in areas:
            if per_area[area.id]:
                result.append(per_area[area.id].pop(0))
                added = True
                if len(result) >= count:
                    break
        if not added:
            break
    return result


def add_objective(m, spec, texture_lib=None, script_name=None,
                  mode="buttons", item_count=5, door_bounds=None,
                  portal_id=None, item_points=None, button_points=None):
    """Добавить дверь и задачу: кнопки или сбор предметов.

    mode="buttons" — две func_button -> trigger_counter (этап 6).
    mode="collect" — N item_security -> N game_counter с порогами health
    (этап 10, паттерн из SecretCity r_5/r_5x).

    Если задан script_name, ставятся trigger_script и multi_manager:
    скрипт только печатает сообщения, дверь открывается сущностями.
    """
    goal_conn = next(c for c in spec.connections if c.b == spec.goal)
    if door_bounds is None:
        door_bounds = _door_bounds(spec, goal_conn)
    doors = m.meta.get("doors", [])
    panels = m.meta.get("panels", [])

    # Две кнопки в комнатах по эту сторону двери.
    button_areas = [spec.start, goal_conn.a]
    if button_areas[0] == button_areas[1]:
        others = [a.id for a in spec.areas
                  if a.id not in (spec.goal, spec.start)]
        if others:
            button_areas[1] = others[0]
    button_areas = list(dict.fromkeys(button_areas))[:2]

    # Двери: уезжают вверх, остаются открытыми (wait = -1).
    door_list = door_bounds if isinstance(door_bounds, list) else [door_bounds]
    door_names = []
    for index, bounds in enumerate(door_list):
        name = DOOR_TARGETNAME if index == 0 else "{}_{}".format(
            DOOR_TARGETNAME, index + 1
        )
        door_names.append(name)
        door_key = (portal_id or DOOR_TARGETNAME) if index == 0 else (
            "{}_{}".format(portal_id or DOOR_TARGETNAME, index + 1)
        )
        m.meta.setdefault("built_doors", {})[door_key] = bounds
        m.add_brush_entity(
            "func_door", bounds, DOOR_TEXTURE,
            targetname=name,
            angles="-90 0 0",
            speed="80",
            lip="0",
            wait="-1",
            movesnd="1",
            stopsnd="1",
        )

    counter_target = DOOR_TARGETNAME
    if script_name:
        # Любая задача -> multi_manager -> все двери + скриптовое сообщение.
        manager_keys = {name: "0" for name in door_names}
        manager_keys["door_script"] = "0"
        m.add_point_entity(
            "multi_manager", targetname="door_manager", **manager_keys
        )
        m.add_point_entity(
            "trigger_script", targetname="door_script",
            m_iszScriptFile=script_name,
            m_iszScriptFunctionName="DoorOpened",
            m_iMode="1",
        )
        counter_target = "door_manager"

    buttons = []
    items = []

    if mode == "collect":
        positions = list(item_points) if item_points else _item_positions(
            m, spec, item_count, doors, panels
        )
        if len(positions) < item_count:
            raise RuntimeError(
                "не хватает свободных мест для {} предметов".format(item_count)
            )
        # Прогресс считает СКРИПТ, а не имя предмета: сообщение всегда
        # показывает реальное состояние задачи, независимо от порядка.
        if script_name:
            m.add_point_entity(
                "multi_manager", targetname="collect_manager",
                **{"collect_counter": "0", "collect_script": "0"}
            )
            m.add_point_entity(
                "trigger_script", targetname="collect_script",
                m_iszScriptFile=script_name,
                m_iszScriptFunctionName="Progress",
                m_iMode="1",
            )
        item_target = "collect_manager" if script_name else "collect_counter"

        for i in range(1, item_count + 1):
            keys = dict(
                targetname="collect_counter",
                health=str(i), frags="0", spawnflags="1",
            )
            if i == item_count:
                keys["target"] = counter_target
            # Паттерн SecretCity: общий targetname и порог health = i.
            m.add_point_entity("game_counter", **keys)

        for index, (x, y, z, area_id) in enumerate(positions, start=1):
            name = "sample_{}".format(index)
            m.add_point_entity(
                "item_security", targetname=name,
                target=item_target,
                origin="{} {} {}".format(num(x), num(y), num(z)),
                angles="0 0 0",
                model="models/w_security.mdl",
            )
            items.append({
                "name": name, "area": area_id,
                "center": (x, y),
            })
    else:
        # Режим этапа 6: две кнопки -> trigger_counter.
        area = spec.area(goal_conn.a)
        x0, y0, _x1, _y1 = _world_rect(spec, area)
        m.add_brush_entity(
            "trigger_counter",
            Bounds(x0 - 8, y0 - 8, spec.height - 40,
                   x0, y0, spec.height - 32),
            COUNTER_TEXTURE,
            targetname=COUNTER_TARGETNAME,
            target=counter_target,
            count=str(len(button_areas)),
            spawnflags="1",
        )
        if script_name:
            # Один общий вызов: скрипт сам считает, сколько нажато.
            m.add_point_entity(
                "multi_manager", targetname="gen_manager",
                **{COUNTER_TARGETNAME: "0", "gen_script": "0"}
            )
            m.add_point_entity(
                "trigger_script", targetname="gen_script",
                m_iszScriptFile=script_name,
                m_iszScriptFunctionName="Progress",
                m_iMode="1",
            )
        button_target = "gen_manager" if script_name else COUNTER_TARGETNAME

        for i, area_id in enumerate(button_areas, start=1):
            if button_points:
                px, py, pz, _area = button_points[i - 1]
                bounds = Bounds(px - 16, py - 8, pz - 8,
                                px + 16, py + 8, pz + 8)
            else:
                bounds = _button_bounds(spec, spec.area(area_id), doors, panels)
            name = "gen_button_{}".format(i)

            m.add_brush_entity(
                "func_button", bounds, BUTTON_TEXTURE,
                targetname=name, target=button_target,
                spawnflags="1", wait="-1", sounds="3", angles="0 0 0",
            )
            buttons.append({
                "name": name, "area": area_id,
                "center": ((bounds.x0 + bounds.x1) / 2,
                           (bounds.y0 + bounds.y1) / 2),
                "bounds": bounds,
            })

    meta = {
        "door_bounds": door_list[0],
        "door_bounds_list": door_list,
        "door_center": ((door_list[0].x0 + door_list[0].x1) / 2,
                        (door_list[0].y0 + door_list[0].y1) / 2),
        "kind": mode,
        "buttons": buttons,
        "items": items,
        "counter": COUNTER_TARGETNAME,
        "script": script_name,
        "portal_id": portal_id,
    }
    m.meta["mechanics"] = meta
    return meta


def validate_objective(spec, m):
    """Проверить, что кнопки достижимы, а дверь реально запирает цель."""
    mech = m.meta.get("mechanics")
    if not mech:
        return {"objective": False}
    start = spec.area_center(spec.start)
    goal = spec.area_center(spec.goal)

    closed = build_grid(m.solids + mech.get("door_bounds_list", [mech["door_bounds"]]), z=24)
    opened = build_grid(m.solids, z=24)

    checks = {}
    for button in mech.get("buttons", []):
        ok, _steps, _path, _reason = find_path(closed, start, button["center"])
        checks["button_" + button["name"]] = ok
    for item in mech.get("items", []):
        ok, _steps, _path, _reason = find_path(closed, start, item["center"])
        checks["item_" + item["name"]] = ok
    ok_open, _steps, _path, _reason = find_path(opened, start, goal)
    ok_closed, _steps, _path, _reason = find_path(closed, start, goal)
    checks["goal_after_door_opens"] = ok_open
    checks["goal_gated_by_door"] = not ok_closed
    checks["objective"] = all(checks.values())
    return checks
