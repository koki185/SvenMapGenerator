"""Генератор кампании: несколько карт, которые продолжают друг друга.

Запуск:
    python generate_campaign.py
    python generate_campaign.py --build --smoke
"""

import argparse
import os
import shutil
import sys

from svenmap.builders import build_level
from svenmap.campaign import load_campaign
from svenmap.encounters import add_encounters
from svenmap.mechanics import add_objective, validate_objective
from svenmap.pipeline import detect_roots, compile_map, smoke_test_load
from svenmap.planner import PlannerConfig, plan
from svenmap.planning import (
    BlueprintConfig, blueprint_to_aligned_spec, build_blueprint_map,
    generate_blueprint, get_interaction_point, get_item_point,
    portal_to_legacy_door, resolve_all_portals,
)
from svenmap.validator_portals import validate_portal_binding
from svenmap.v2_entities import (
    add_basic_entities, add_vertical_transition, area_center_world, GRID,
)
from svenmap.leak_repair import repair_leaks
from svenmap.composition_metrics import summarize as summarize_composition
from svenmap.pacing import evaluate as evaluate_pacing
from svenmap.preview_v2 import write_blueprint_preview
from svenmap.progression import (
    add_boss_arena, add_changelevel, add_multi_spawn,
)
from svenmap.scripts import write_map_script
from svenmap.secrets import add_secrets, validate_secrets
from svenmap.textures import TextureLibrary
from svenmap.validator import (
    build_grid, find_path, spawn_is_clear, unreachable_areas, to_cell,
)

HERE = os.path.dirname(os.path.abspath(__file__))
CAMPAIGN_JSON = os.path.join(HERE, "campaign.json")
PROJECT_MAPS = os.path.join(HERE, "maps")
PROJECT_LOGS = os.path.join(HERE, "logs")
PROJECT_PREVIEWS = os.path.join(HERE, "notes", "previews")


def wads(game_dir):
    names = [
        os.path.join(game_dir, "svencoop", "zhlt.wad"),
        os.path.join(game_dir, "svencoop", "halflife.wad"),
    ]
    return [os.path.splitdrive(p)[1] for p in names if os.path.isfile(p)]


def build_chapter(chapter, tex_lib, wad_list):
    """Одна карта кампании. Возвращает (MapFile, LevelSpec, вариант декора)."""
    level = plan(PlannerConfig(
        seed=chapter.seed,
        room_count=chapter.rooms,
        branch_count=chapter.branches,
    ))
    start = level.area_center(level.start)
    m = None
    variant = -1
    for candidate_variant in range(12):
        candidate = build_level(
            level, wad_list,
            seed=chapter.seed + candidate_variant * 101,
            texture_lib=tex_lib,
        )
        grid = build_grid(candidate.solids, z=24)
        found, _steps, _path, _reason = find_path(
            grid, start, level.area_center(level.goal)
        )
        if found and not unreachable_areas(candidate.solids, level):
            m = candidate
            variant = candidate_variant
            break
    if m is None:
        raise RuntimeError("нет проходимого варианта декора для " + chapter.name)

    spawn_z = level.floor_thickness + 48
    if not spawn_is_clear(m.solids, (start[0], start[1], spawn_z),
                          z=spawn_z - 36):
        raise RuntimeError("спавн внутри геометрии: " + chapter.name)

    add_multi_spawn(m, level, count=4)
    mode = "collect" if "collect" in chapter.puzzles else "buttons"
    add_objective(m, level, tex_lib, script_name=chapter.name,
                  mode=mode, item_count=5)
    if not chapter.final and "enemies" in chapter.puzzles:
        add_encounters(m, level, seed=chapter.seed, count=3)

    secret_count = 0
    if not chapter.final and "secret" in chapter.puzzles:
        tiers = 2 if "super_secret" in chapter.puzzles else 1
        meta = add_secrets(m, level, script_name=chapter.name,
                           per_tier=2, tiers=tiers)
        if meta:
            secret_count = meta["count"]

    if chapter.final:
        add_boss_arena(m, level, waves=5)
    return m, level, variant, secret_count


def area_cell_points(area):
    """Центры всех реально занятых клеток комнаты, от центра к краям.

    Используется для расстановки нескольких предметов в одной комнате:
    просто взятие центра приводило к тому, что образцы с порталами из
    одной комнаты ставились в одну точку и накладывались друг на друга.
    """
    cells = area.get("cells")
    if cells:
        cell_set = {tuple(c) for c in cells}
        tx, ty = area["w"] / 2.0, area["h"] / 2.0

        def score(cell):
            neighbours = sum(
                (cell[0] + dx, cell[1] + dy) in cell_set
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
            )
            return (
                -neighbours,
                (cell[0] - tx) ** 2 + (cell[1] - ty) ** 2,
            )
    else:
        cell_set = [
            (cx, cy)
            for cx in range(area["w"])
            for cy in range(area["h"])
        ]
        tx, ty = area["w"] / 2.0, area["h"] / 2.0
        score = lambda cell: (cell[0] - tx) ** 2 + (cell[1] - ty) ** 2

    return [
        ((area["x"] + c[0] + 0.5) * GRID,
         (area["y"] + c[1] + 0.5) * GRID)
        for c in sorted(cell_set, key=score)
    ]


def build_chapter_v2(chapter, tex_lib, wad_list, game_dir):
    """Кампания через новый Blueprint pipeline."""
    floors = 2 if "multi_floor" in chapter.puzzles else 1
    blueprint = generate_blueprint(BlueprintConfig(
        seed=chapter.seed,
        node_count=chapter.rooms,
        branch_count=chapter.branches,
        secret_count=2 if "secret" in chapter.puzzles else 0,
        floors=floors,
    ))
    spec = blueprint_to_aligned_spec(blueprint)
    m = build_blueprint_map(blueprint, wad_list, game_dir, seed=chapter.seed)
    add_basic_entities(m, blueprint)
    add_vertical_transition(m, blueprint)

    portals = resolve_all_portals(blueprint)
    keys = sorted(portals)
    goal_conns = [
        c for c in blueprint["spatial"]["connections"]
        if c["b"] == spec.goal or c["a"] == spec.goal
    ]
    goal_ids = [c["id"] for c in goal_conns if c["id"] in portals]
    portal_id = goal_ids[0]
    door_list = [portal_to_legacy_door(portals[key]) for key in goal_ids]
    mode = "collect" if "collect" in chapter.puzzles else "buttons"
    secret_keys = []
    if not chapter.final and "secret" in chapter.puzzles:
        secret_candidates = [
            c["id"] for c in blueprint["spatial"]["connections"]
            if c.get("type") in ("secret", "branch")
            and c["id"] not in goal_ids and c["id"] in portals
        ]
        secret_keys = (secret_candidates or [
            k for k in keys if k not in goal_ids        ])[:2]
    floor_of_area = {
        a["node_id"]: a.get("floor", 0)
        for a in blueprint["spatial"]["areas"]
    }
    available = [
        k for k in keys
        if k not in goal_ids and k not in secret_keys
        and floor_of_area.get(portals[k].area_a, 0) == 0
        and floor_of_area.get(portals[k].area_b, 0) == 0
    ]
    reachable_ids = set()
    from svenmap.validator import reachable_areas_ids
    reachable_ids = reachable_areas_ids(m.solids, spec)
    available = [
        k for k in available
        if portals[k].area_a in reachable_ids
        or portals[k].area_b in reachable_ids
    ]
    # Предметы должны быть доступны ДО открытия двери.
    closed_grid = build_grid(m.solids + door_list, z=24)
    level_start = spec.area_center(spec.start)
    available = [
        k for k in available
        if find_path(
            closed_grid, level_start,
            tuple(portals[k].item_point[:2])
        )[0]
    ]

    blueprint_areas = {
        a["node_id"]: a for a in blueprint["spatial"]["areas"]
    }
    # Каждый образец/кнопка получает отдельную клетку, даже если у нескольких
    # порталов одна и та же комната (иначе предметы накладываются друг на друга).
    used_xy = set()
    item_points, button_points = [], []

    def take_point(area_id, z_offset):
        for x, y in area_cell_points(blueprint_areas[area_id]):
            key_xy = (round(x, 3), round(y, 3))
            if key_xy in used_xy:
                continue
            used_xy.add(key_xy)
            return (x, y, spec.floor_thickness + z_offset, area_id)
        return None

    for key in available:
        if len(item_points) >= 5:
            break
        point = take_point(portals[key].area_a, 8)
        if point is not None:
            item_points.append(point)
    for key in available:
        if len(button_points) >= 2:
            break
        point = take_point(portals[key].area_a, 24)
        if point is not None:
            button_points.append(point)

    add_objective(
        m, spec, tex_lib, script_name=chapter.name,
        mode=mode, item_count=5 if mode == "collect" else 2,
        door_bounds=door_list,
        portal_id=portal_id,
        item_points=item_points if mode == "collect" else None,
        button_points=button_points if mode == "buttons" else None,
    )

    secret_count = 0
    if not chapter.final and "secret" in chapter.puzzles:
        # Дверь секрета не должна отрезать цель: выбираем portfolio,
        # при закрытии которого goal остаётся доступным.
        secret_door_bounds = None
        for key in secret_keys:
            trial_bounds = portal_to_legacy_door(portals[key])
            closed = build_grid(
                m.solids + door_list + [trial_bounds], z=24
            )
            if find_path(
                closed, spec.area_center(spec.start),
                spec.area_center(spec.goal)
            )[0]:
                secret_door_bounds = trial_bounds
                break
        if secret_door_bounds is None:
            secret_keys = []
        else:
            secret_points = []
            for key in secret_keys:
                x, y, z = get_interaction_point(portals[key], side="a")
                secret_points.append((x, y, z, portals[key].area_a))
            add_secrets(
                m, spec, script_name=chapter.name, per_tier=2, tiers=1,
                button_points=secret_points, portal_ids=secret_keys,
                door_bounds=secret_door_bounds,
            )
            secret_count = 2

    if chapter.final:
        add_boss_arena(m, spec, waves=5)

    binding = validate_portal_binding(blueprint, portals, m)
    if not binding["passed"]:
        raise RuntimeError(
            "portal binding FAIL в {}: {}".format(chapter.name, binding["errors"])
        )
    return m, spec, 0, secret_count, blueprint


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--planner", choices=("legacy", "graph_v2"),
                        default="graph_v2")
    parser.add_argument("--only", default="",
                        help="собрать только одну главу по имени")
    args = parser.parse_args()

    _common, compilers_dir, game_dir = detect_roots()
    campaign = load_campaign(CAMPAIGN_JSON)
    tex_lib = TextureLibrary(game_dir)
    wad_list = wads(game_dir)

    print("Кампания:", campaign.name)
    print("Карт:", len(campaign.chapters))
    for chapter in campaign.chapters:
        print("  {} (seed {}, комнат {}, финал={})".format(
            chapter.name, chapter.seed, chapter.rooms, chapter.final))

    os.makedirs(PROJECT_MAPS, exist_ok=True)
    all_ok = True
    chapters = campaign.chapters
    if args.only:
        chapters = [c for c in chapters if c.name == args.only]
        if not chapters:
            print("нет главы с именем", args.only)
            return 1

    for index, chapter in enumerate(chapters, start=1):
        print("\n=== глава {}/{}: {} ===".format(
            index, len(chapters), chapter.name))
        if args.planner == "graph_v2":
            m, level, variant, secret_count, blueprint = build_chapter_v2(
                chapter, tex_lib, wad_list, game_dir
            )
        else:
            m, level, variant, secret_count = build_chapter(
                chapter, tex_lib, wad_list
            )
            blueprint = None

        # Выход в следующую карту — только у нефинальных глав.
        if not chapter.final:
            nxt = campaign.next_chapter(chapter.name)
            add_changelevel(m, level, nxt.name)
        else:
            nxt = None

        checks = validate_objective(level, m)
        print("  brush={} entity={} вариант декора={}".format(
            len(m.brushes), len(m.entities), variant))
        print("  механика:", "OK" if checks.get("objective") else "FAIL")
        if not checks.get("objective"):
            all_ok = False
            continue

        secret_checks = validate_secrets(level, m)
        if secret_checks:
            print("  секреты:", len(m.meta["secrets"]["secrets"]),
                  "шкал;", ", ".join(
                      "{}={}".format(k, "OK" if v else "FAIL")
                      for k, v in secret_checks.items()
                  ))
            if not all(secret_checks.values()):
                all_ok = False
                continue

        script_mode = "collect" if "collect" in chapter.puzzles else "buttons"
        script_count = 5 if script_mode == "collect" else 2
        script_label = "Samples" if script_mode == "collect" else "Generators"
        script_path, cfg_path = write_map_script(
            game_dir, chapter.name, script_count,
            label=script_label, chapter=index, final=chapter.final,
            secret_total=secret_count,
        )
        project_map = os.path.join(PROJECT_MAPS, chapter.name + ".map")
        m.write(project_map)
        addon_maps = os.path.join(game_dir, "svencoop_addon", "maps")
        os.makedirs(addon_maps, exist_ok=True)
        game_map = os.path.join(addon_maps, chapter.name + ".map")
        shutil.copyfile(project_map, game_map)
        if blueprint is not None and args.build:
            repaired = repair_leaks(
                m, level, blueprint, game_map, compilers_dir
            )
            print("  авто-ремонт LEAK:",
                  "OK" if repaired else "не устранён")
            shutil.copyfile(game_map, project_map)
        if blueprint is not None:
            os.makedirs(PROJECT_PREVIEWS, exist_ok=True)
            preview_path = os.path.join(
                PROJECT_PREVIEWS, chapter.name + ".svg"
            )
            write_blueprint_preview(blueprint, m, preview_path,
                                    name=chapter.name)
            facts = summarize_composition(blueprint)
            print("  превью:", preview_path)
            print("  метрики: topo={:.3f} spatial={:.3f} stretch={:.2f} "
                  "shapes={}".format(
                      facts["topology_score"], facts["spatial_score"],
                      facts["route_stretch"], facts["shape_variety"]))
            pacing = evaluate_pacing(blueprint, chapter.pacing)
            m.meta["pacing"] = pacing
            print("  ритм: {} | боевых {:.0%}, подряд {:.0f}, "
                  "передышка {:.0f}{}".format(
                      pacing["profile"],
                      pacing["metrics"]["combat_share"],
                      pacing["metrics"]["max_combat_run"],
                      pacing["metrics"]["rest_gap"],
                      " | WARN: " + "; ".join(pacing["warnings"])
                      if pacing["warnings"] else "",
                  ))
        print("  .map:", project_map)
        print("  скрипт:", script_path)
        print("  переход:", nxt.name if nxt else "финал (арена босса)")

        if args.build:
            print("  --- компиляция ---")
            try:
                compile_map(game_map, compilers_dir, log_dir=PROJECT_LOGS)
            except Exception as e:
                print("  ОШИБКА компиляции:", str(e)[:200])
                all_ok = False
                continue
            if args.smoke:
                output = ""
                for attempt in range(3):
                    output = smoke_test_load(
                        chapter.name, game_dir, seconds=9,
                        extra_args=("+developer", "1"),
                    )
                    if "Started map" in output:
                        break
                    if "Unable to initialize Steam" not in output:
                        break
                log_path = os.path.join(PROJECT_LOGS, "campaign_" + chapter.name + ".log")
                with open(log_path, "w", encoding="utf-8", errors="replace") as f:
                    f.write(output)
                loaded = "Started map" in output
                compiled_script = "Map script compilation succeeded" in output
                print("  загрузка:", "OK" if loaded else "FAIL",
                      "| скрипт:", "OK" if compiled_script else "FAIL")
                if not (loaded and compiled_script):
                    all_ok = False

    print("\nИТОГ:", "все главы собраны" if all_ok else "есть ошибки")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
