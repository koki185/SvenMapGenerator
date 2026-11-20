"""PR-5: новый pipeline строит реальную карту и проверяет её.

    python generate_v2.py --seed 42
    python generate_v2.py --seed 42 --build --smoke --next sc_exp_2
"""

import argparse
import os
import shutil
import sys

from svenmap.builders import build_level
from svenmap.mechanics import add_objective, validate_objective
from svenmap.pipeline import detect_roots, compile_map, smoke_test_load
from svenmap.planning import BlueprintConfig, blueprint_to_level_spec, generate_blueprint
from svenmap.progression import add_changelevel
from svenmap.scripts import write_map_script
from svenmap.textures import TextureLibrary
from svenmap.validator import build_grid, find_path, spawn_is_clear, unreachable_areas

from generate_campaign import PROJECT_LOGS, PROJECT_MAPS, wads

HERE = os.path.dirname(os.path.abspath(__file__))


def build_map(spec, wad_list, tex_lib, seed, script_name, next_map):
    start = spec.area_center(spec.start)
    chosen = None
    variant = -1
    for candidate_variant in range(12):
        candidate = build_level(
            spec, wad_list, seed=seed + candidate_variant * 101,
            texture_lib=tex_lib,
        )
        grid = build_grid(candidate.solids, z=24)
        found, steps, _path, _reason = find_path(
            grid, start, spec.area_center(spec.goal)
        )
        if found and not unreachable_areas(candidate.solids, spec):
            chosen = candidate
            variant = candidate_variant
            break
    if chosen is None:
        raise RuntimeError("нет проходимого варианта декора")

    spawn_z = spec.floor_thickness + 48
    if not spawn_is_clear(chosen.solids, (start[0], start[1], spawn_z),
                          z=spawn_z - 36):
        raise RuntimeError("спавн внутри геометрии")

    add_objective(chosen, spec, tex_lib, script_name=script_name,
                  mode="collect", item_count=5)
    if next_map:
        add_changelevel(chosen, spec, next_map)
    return chosen, variant, steps


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--next", default="", help="карта campaigns next")
    args = parser.parse_args()

    _common, compilers_dir, game_dir = detect_roots()
    blueprint = generate_blueprint(BlueprintConfig(seed=args.seed, floors=1))
    spec = blueprint_to_level_spec(blueprint)
    print("Blueprint:", blueprint["graph"]["name"])
    print("комнат:", len(spec.areas), "связей:", len(spec.connections))

    tex_lib = TextureLibrary(game_dir)
    wad_list = wads(game_dir)
    m, variant, steps = build_map(
        spec, wad_list, tex_lib, args.seed, spec.name, args.next or None
    )
    checks = validate_objective(spec, m)
    print("вариант декора:", variant, "длина пути:", steps)
    print("механика:", "OK" if checks.get("objective") else "FAIL")
    if not checks.get("objective"):
        return 1

    write_map_script(game_dir, spec.name, 5, label="Samples")
    os.makedirs(PROJECT_MAPS, exist_ok=True)
    project_map = os.path.join(PROJECT_MAPS, spec.name + ".map")
    m.write(project_map)
    addon_maps = os.path.join(game_dir, "svencoop_addon", "maps")
    os.makedirs(addon_maps, exist_ok=True)
    game_map = os.path.join(addon_maps, spec.name + ".map")
    shutil.copyfile(project_map, game_map)
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
        log_path = os.path.join(PROJECT_LOGS, "v2_" + spec.name + ".log")
        with open(log_path, "w", encoding="utf-8", errors="replace") as f:
            f.write(output)
        print("загрузка:", "OK" if "Started map" in output else "FAIL")
        print("скрипт:", "OK" if "Map script compilation succeeded" in output else "FAIL")
        if "Started map" not in output:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
