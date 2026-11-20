"""PR-6 CLI: Blueprint -> геометрия по маскам -> сущности -> сборка."""

import argparse
import os
import shutil
import sys

from svenmap.mapfile import num
from svenmap.mechanics import add_objective, validate_objective
from svenmap.pipeline import detect_roots, compile_map, smoke_test_load
from svenmap.planning import (
    BlueprintConfig, blueprint_to_aligned_spec, blueprint_to_level_spec,
    build_blueprint_map, generate_blueprint,
)
from svenmap.scripts import write_map_script
from svenmap.textures import TextureLibrary

from generate_campaign import PROJECT_LOGS, PROJECT_MAPS, wads


def add_basic_entities(m, blueprint):
    graph = blueprint["graph"]
    spatial = blueprint["spatial"]
    areas = {a["node_id"]: a for a in spatial["areas"]}
    grid = 192

    spawn = areas.get(graph["start"])
    if spawn:
        cx = (spawn["x"] + spawn["w"] / 2) * grid
        cy = (spawn["y"] + spawn["h"] / 2) * grid
        m.add_point_entity(
            "info_player_start",
            origin="{} {} {}".format(num(cx), num(cy), 64),
            angles="0 0 0",
        )
        for dx, dy in ((-64, -64), (64, -64), (-64, 64), (64, 64)):
            m.add_point_entity(
                "info_player_deathmatch",
                origin="{} {} {}".format(num(cx + dx), num(cy + dy), 64),
                angles="0 0 0",
            )

    for node_id, area in areas.items():
        cx = (area["x"] + area["w"] / 2) * grid
        cy = (area["y"] + area["h"] / 2) * grid
        m.add_point_entity(
            "light",
            origin="{} {} {}".format(num(cx), num(cy), 240),
            angles="0 0 0",
            _light="255 255 255 200",
            _falloff="0",
            _fade="1.0",
            style="0",
            spawnflags="0",
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--with-objective", action="store_true",
                        help="добавить механики (пока не согласованы с новой геометрией)")
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()

    _common, compilers_dir, game_dir = detect_roots()
    blueprint = generate_blueprint(BlueprintConfig(seed=args.seed, floors=1))
    spec = blueprint_to_aligned_spec(blueprint)
    wad_list = wads(game_dir)
    tex_lib = TextureLibrary(game_dir)

    m = build_blueprint_map(blueprint, wad_list, game_dir, seed=args.seed)
    add_basic_entities(m, blueprint)
    if args.with_objective:
        add_objective(m, spec, tex_lib, script_name=spec.name,
                      mode="collect", item_count=5)
        checks = validate_objective(spec, m)
        print("механика:", "OK" if checks.get("objective") else "FAIL",
              "(новая геометрия пока не согласована с дверью)")

    write_map_script(game_dir, spec.name, 5, label="Samples")
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
        print("скрипт:", "OK" if "Map script compilation succeeded" in output else "FAIL")
        if "Started map" not in output:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
