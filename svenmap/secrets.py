"""Уровни секретов (этап 14).

Каждый уровень: скрытые кнопки в ДОСТУПНЫХ комнатах -> счётчик ->
дверь в свою бонусную ветку. Общий счётчик в скрипте показывает,
сколько секретов найдено всего: "Secrets: X/N".
"""

from .geometry import Bounds
from .profiles import get_profile
from .mechanics import (
    _button_bounds, _door_bounds, _world_rect, COUNTER_TEXTURE,
)

SECRET_DOOR_TEXTURE = "LAB1_DOOR1"


def add_secrets(m, spec, script_name=None, per_tier=2, tiers=1):
    """Добавить tiers уровней секретов. Возвращает метаданные или None."""
    branch_conns = [
        c for c in spec.connections
        if c.b.startswith("b")
    ][:tiers]
    if not branch_conns:
        return None

    used_rooms = set()
    used_rooms.update(
        b["area"] for b in m.meta.get("mechanics", {}).get("buttons", [])
    )
    used_rooms.update(
        i["area"] for i in m.meta.get("mechanics", {}).get("items", [])
    )

    doors = m.meta.get("doors", [])
    panels = m.meta.get("panels", [])
    tier_meta = []
    all_buttons = []
    all_doors = []

    for tier, conn in enumerate(branch_conns, start=1):
        candidates = [
            a for a in spec.areas
            if a.id not in (spec.goal, spec.start, conn.b)
            and a.id not in used_rooms
        ]
        if not candidates:
            candidates = [
                a for a in spec.areas
                if a.id not in (spec.goal, spec.start, conn.b)
            ]
        if not candidates:
            continue
        candidates.sort(
            key=lambda a: 0 if a.type in ("corridor", "storage") else 1
        )

        counter_name = "secret_counter_{}".format(tier)
        door_name = "secret_door_{}".format(tier)
        door_bounds = _door_bounds(spec, conn)

        m.add_brush_entity(
            "func_door", door_bounds, SECRET_DOOR_TEXTURE,
            targetname=door_name,
            angles="-90 0 0", speed="80", lip="0", wait="-1",
            movesnd="1", stopsnd="1",
        )
        all_doors.append(door_bounds)

        if script_name:
            m.add_point_entity(
                "multi_manager", targetname="secret_manager_{}".format(tier),
                **{counter_name: "0", "secret_script": "0"}
            )
            m.add_point_entity(
                "multi_manager", targetname="secret_done_{}".format(tier),
                **{door_name: "0", "secret_tier_script_{}".format(tier): "0"}
            )
            m.add_point_entity(
                "trigger_script",
                targetname="secret_tier_script_{}".format(tier),
                m_iszScriptFile=script_name,
                m_iszScriptFunctionName="TierDone",
                m_iMode="1",
            )

        # trigger_counter — SolidClass, нужен brush.
        sx0, sy0, _sx1, _sy1 = _world_rect(spec, spec.area(spec.start))
        m.add_brush_entity(
            "trigger_counter",
            Bounds(sx0 - 8, sy0 - 8 - tier * 8, spec.height - 40,
                   sx0, sy0 - tier * 8, spec.height - 32),
            COUNTER_TEXTURE,
            targetname=counter_name,
            target="secret_done_{}".format(tier) if script_name else door_name,
            count=str(per_tier),
            spawnflags="1",
        )

        tier_buttons = []
        for index, area in enumerate(candidates[:per_tier], start=1):
            bounds = _button_bounds(spec, area, doors, panels)
            name = "secret_{}_{}".format(tier, index)
            hidden_texture = get_profile(spec.theme, area.type).wall
            m.add_brush_entity(
                "func_button", bounds, hidden_texture,
                targetname=name,
                target="secret_manager_{}".format(tier) if script_name
                else counter_name,
                spawnflags="1", wait="-1", sounds="3", angles="0 0 0",
            )
            info = {
                "name": name,
                "area": area.id,
                "center": ((bounds.x0 + bounds.x1) / 2,
                           (bounds.y0 + bounds.y1) / 2),
            }
            tier_buttons.append(info)
            all_buttons.append(info)
            used_rooms.add(area.id)

        tier_meta.append({
            "tier": tier,
            "door_bounds": door_bounds,
            "door": door_name,
            "buttons": tier_buttons,
            "bonus_area": conn.b,
        })

    if not tier_meta:
        return None

    if script_name:
        m.add_point_entity(
            "trigger_script", targetname="secret_script",
            m_iszScriptFile=script_name,
            m_iszScriptFunctionName="SecretFound",
            m_iMode="1",
        )

    meta = {
        "tiers": tier_meta,
        "door_bounds": all_doors[0],
        "doors": all_doors,
        "secrets": all_buttons,
        "count": len(all_buttons),
    }
    m.meta["secrets"] = meta
    return meta


def validate_secrets(spec, m):
    """Проверить, что секретные двери НЕ запирают цель уровня."""
    meta = m.meta.get("secrets")
    if not meta:
        return {}
    from .validator import build_grid, find_path

    closed = build_grid(m.solids + meta["doors"], z=24)
    ok, _steps, _path, _reason = find_path(
        closed, spec.area_center(spec.start), spec.area_center(spec.goal)
    )
    return {"goal_reachable_without_secrets": ok}
