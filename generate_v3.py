"""PR-6 CLI: Blueprint -> геометрия по маскам -> сущности -> сборка.

Одиночная карта через graph_v2. Основная точка входа для кампаний —
generate_campaign.py; этот скрипт оставлен для отладки одной карты.
"""

import argparse
from collections import deque
import os
import shutil
import sys

from svenmap.v2_entities import add_basic_entities, add_vertical_transition, GRID
from svenmap.mechanics import add_objective, validate_objective
from svenmap.secrets import add_secrets, validate_secrets
from svenmap.pipeline import detect_roots, compile_map, smoke_test_load
from svenmap.planning import (
    BlueprintConfig, blueprint_to_aligned_spec, build_blueprint_map,
    generate_blueprint, get_interaction_point, get_item_point,
    portal_to_legacy_door, resolve_all_portals,
)
from svenmap.validator_portals import validate_portal_binding
from svenmap.scripts import write_map_script
from svenmap.textures import TextureLibrary

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_MAPS = os.path.join(HERE, "maps")
PROJECT_LOGS = os.path.join(HERE, "logs")


def wads(game_dir):
    """Список WAD в формате, ожидаемом MapFile (без диска)."""
    names = [
        os.path.join(game_dir, "svencoop", "zhlt.wad"),
        os.path.join(game_dir, "svencoop", "halflife.wad"),
    ]
    return [os.path.splitdrive(p)[1] for p in names if os.path.isfile(p)]


def _distance_from_start(blueprint):
    """Расстояние от старта до узла по графу — для осмысленного порядка точек."""
    graph = blueprint["graph"]
    adjacency = {}
    for edge in graph["edges"]:
        adjacency.setdefault(edge["a"], []).append(edge["b"])
        adjacency.setdefault(edge["b"], []).append(edge["a"])
    start = graph.get("start")
    if start not in adjacency:
        return {}
    dist = {start: 0}
    queue = deque([start])
    while queue:
        current = queue.popleft()
        for neighbour in adjacency[current]:
            if neighbour not in dist:
                dist[neighbour] = dist[current] + 1
                queue.append(neighbour)
    return dist


def _area_cell_points(area):
    """Центры занятых клеток комнаты, от центра к краям."""
    cells = area.get("cells")
    if cells:
        cell_set = {tuple(c) for c in cells}
        tx, ty = area["w"] / 2.0, area["h"] / 2.0

        def score(cell):
            neighbours = sum(
                (cell[0] + dx, cell[1] + dy) in cell_set
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
            )
            return (-neighbours,
                    (cell[0] - tx) ** 2 + (cell[1] - ty) ** 2)
    else:
        cell_set = [(cx, cy) for cx in range(area["w"])
                    for cy in range(area["h"])]
        tx, ty = area["w"] / 2.0, area["h"] / 2.0
        score = lambda c: (c[0] - tx) ** 2 + (c[1] - ty) ** 2

    return [
        ((area["x"] + c[0] + 0.5) * GRID,
         (area["y"] + c[1] + 0.5) * GRID)
        for c in sorted(cell_set, key=score)
    ]


def _pick_points(blueprint, portals, dist, count):
    """Разные комнаты и клетки, а не алфавитный порядок id порталов."""
    areas = {a["node_id"]: a for a in blueprint["spatial"]["areas"]}
    used = set()
    points = []
    keys = sorted(portals, key=lambda k: (
        dist.get(portals[k].area_a, 10 ** 6), k
    ))
    for key in keys:
        area_id = portals[key].area_a
        area = areas.get(area_id)
        if not area:
            continue
        for x, y in _area_cell_points(area):
            cell = (round(x, 3), round(y, 3))
            if cell in used:
                continue
            used.add(cell)
            points.append((x, y, 24, area_id))
            break
        if len(points) >= count:
            break
    return points


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--floors", type=int, default=1)
    parser.add_argument("--no-vertical", action="store_true")
    parser.add_argument("--no-secrets", action="store_true")
    parser.add_argument("--mode", choices=("collect", "buttons"),
                        default="collect")
    parser.add_argument("--with-secrets", action="store_true")
    parser.add_argument("--with-objective", action="store_true",
                        help="добавить цели и дверь (mechanics на graph_v2)")
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()

    _common, compilers_dir, game_dir = detect_roots()
    blueprint = generate_blueprint(
        BlueprintConfig(seed=args.seed, floors=args.floors,
                        secret_count=0 if args.no_secrets else 2)
    )
    spec = blueprint_to_aligned_spec(blueprint)
    wad_list = wads(game_dir)
    tex_lib = TextureLibrary(game_dir)

    m = build_blueprint_map(blueprint, wad_list, game_dir, seed=args.seed)
    add_basic_entities(m, blueprint)
    vertical = [] if args.no_vertical else add_vertical_transition(m, blueprint)
    if vertical:
        print("вертикальных переходов:", len(vertical))
    portals = resolve_all_portals(blueprint)
    print("порталов в registry:", len(portals))

    # Порядок порталов нужен и целям, и секретам — поэтому вне if.
    dist = _distance_from_start(blueprint)
    keys = sorted(portals, key=lambda k: (
        dist.get(portals[k].area_a, 10 ** 6), k
    ))

    if args.with_objective:
        goal_conn = next(
            (c for c in blueprint["spatial"]["connections"]
             if c["b"] == spec.goal or c["a"] == spec.goal),
            None,
        )
        if goal_conn is None:
            raise ValueError(
                "у целевой комнаты {} нет соединения — цель невозможна"
                .format(spec.goal)
            )
        portal_id = goal_conn["id"]
        portal = portals[portal_id]
        points = _pick_points(blueprint, portals, dist, 5)
        item_points = [(x, y, z, area) for x, y, z, area in points[:5]]
        button_points = [(x, y, 40, area) for x, y, _z, area in points[:2]]
        is_collect = args.mode == "collect"
        add_objective(
            m, spec, tex_lib, script_name=spec.name,
            mode=args.mode,
            item_count=5 if is_collect else 2,
            door_bounds=portal_to_legacy_door(portal),
            portal_id=portal_id,
            item_points=item_points if is_collect else None,
            button_points=None if is_collect else button_points,
        )
        checks = validate_objective(spec, m)
        binding = validate_portal_binding(blueprint, portals, m)
        print("механика:", "OK" if checks.get("objective") else "FAIL")
        print("portal binding:", "OK" if binding["passed"] else "FAIL",
              "| objective portal:", portal_id)

    if args.with_secrets:
        if not keys:
            raise ValueError("нет порталов для секретных дверей")
        candidates = [
            c["id"] for c in blueprint["spatial"]["connections"]
            if c.get("type") in ("secret", "branch")
            and c["id"] != (goal_conn["id"] if args.with_objective else None)
            and c["id"] in portals
        ]
        secret_keys = (candidates or [k for k in keys])[:2]
        secret_points = []
        for portal_key in secret_keys:
            source = portals[portal_key]
            x, y, z = get_interaction_point(source, side="a")
            secret_points.append((x, y, z, source.area_a))
        secret_door = portal_to_legacy_door(portals[secret_keys[0]])
        add_secrets(
            m, spec, script_name=spec.name, per_tier=2, tiers=1,
            button_points=secret_points, portal_ids=secret_keys,
            door_bounds=secret_door,
        )
        secret_checks = validate_secrets(spec, m)
        print("секреты:", "OK" if all(secret_checks.values()) else "FAIL",
              "| порталов:", len(secret_keys))

    script_count = 5 if args.mode == "collect" else 2
    script_label = "Samples" if args.mode == "collect" else "Generators"
    secret_total = 2 if args.with_secrets else 0
    write_map_script(game_dir, spec.name, script_count, label=script_label,
                     secret_total=secret_total)
    os.makedirs(PROJECT_MAPS, exist_ok=True)
    project_map = os.path.join(PROJECT_MAPS, spec.name + ".map")
    m.write(project_map)
    addon_maps = os.path.join(game_dir, "svencoop_addon", "maps")
    os.makedirs(addon_maps, exist_ok=True)
    game_map = os.path.join(addon_maps, spec.name + ".map")
    shutil.copyfile(project_map, game_map)
    print("brush:", len(m.brushes), "entity:", len(m.entities))
    print(".map:", project_map)

    if not args.build:
        return 0

    compile_map(game_map, compilers_dir, log_dir=PROJECT_LOGS)
    print("BSP:", os.path.splitext(game_map)[0] + ".bsp")

    if args.smoke:
        output = ""
        for _attempt in range(3):
            output = smoke_test_load(
                spec.name, game_dir, seconds=9,
                extra_args=("+developer", "1"),
            )
            if "Started map" in output:
                break
            if "Unable to initialize Steam" not in output:
                break
        print("загрузка:", "OK" if "Started map" in output else "FAIL")
        print("скрипт:",
              "OK" if "Map script compilation succeeded" in output else "FAIL")
        if "Started map" not in output:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
