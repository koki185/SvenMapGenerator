"""Этап 3: планировщик — уровень генерируется по seed, а не вручную.

Запуск:
    python generate_procedural.py --seed 7
    python generate_procedural.py --seed 7 --rooms 7 --branches 2
    python generate_procedural.py --seed 7 --build --smoke
"""

import argparse
import json
import os
import shutil
import sys

from svenmap.builders import build_level
from svenmap.pipeline import detect_roots, compile_map, smoke_test_load
from svenmap.mechanics import add_objective, validate_objective
from svenmap.planner import PlannerConfig, plan, spec_to_dict
from svenmap.preview import write_preview
from svenmap.scripts import write_map_script
from svenmap.textures import TextureLibrary
from svenmap.validator import (
    build_grid, find_path, ascii_map, to_cell, spawn_is_clear,
    unreachable_areas,
)

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_MAPS = os.path.join(HERE, "maps")
PROJECT_LOGS = os.path.join(HERE, "logs")


def wad_paths(game_dir):
    names = [
        os.path.join(game_dir, "svencoop", "zhlt.wad"),
        os.path.join(game_dir, "svencoop", "halflife.wad"),
    ]
    return [os.path.splitdrive(p)[1] for p in names if os.path.isfile(p)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--rooms", type=int, default=6)
    parser.add_argument("--branches", type=int, default=1)
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--no-decor", action="store_true",
                        help="построить карту без декора (для сравнения)")
    parser.add_argument("--no-mechanics", action="store_true",
                        help="не добавлять дверь и генераторы")
    parser.add_argument("--no-script", action="store_true",
                        help="не генерировать AngelScript и CFG")
    args = parser.parse_args()

    steam_common, compilers_dir, game_dir = detect_roots()
    use_script = not args.no_script

    config = PlannerConfig(
        seed=args.seed,
        room_count=args.rooms,
        branch_count=args.branches,
    )
    spec = plan(config)
    print("Сгенерирован уровень:", spec.name)
    print("seed:", config.seed, "| комнат:", len(spec.areas),
          "| связей:", len(spec.connections))
    print("\nПланировка (клетки):")
    for area in spec.areas:
        print("  {:6s} {:9s} {}".format(area.id, area.type, area.cells))
    print("Связи:")
    for conn in spec.connections:
        print("  {} -> {}  дверь в клетке {}".format(conn.a, conn.b, conn.cell))

    os.makedirs(PROJECT_MAPS, exist_ok=True)
    json_path = os.path.join(PROJECT_MAPS, spec.name + ".json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(spec_to_dict(spec), f, ensure_ascii=False, indent=2)
    print("\nОписание сохранено:", json_path)

    wads = wad_paths(game_dir)
    tex_lib = TextureLibrary(game_dir)
    start = spec.area_center(spec.start)
    goal = spec.area_center(spec.goal)

    # Декор может случайно перекрыть проход. Перебираем варианты его
    # расстановки и оставляем первый, при котором путь существует.
    m = None
    variant_used = 0
    variants = range(12) if not args.no_decor else range(1)
    for variant in variants:
        candidate = build_level(
            spec, wads,
            seed=config.seed + variant * 101,
            use_decor=not args.no_decor,
            texture_lib=tex_lib,
        )
        grid = build_grid(candidate.solids, z=24)
        found, steps, path, reason = find_path(grid, start, goal)
        # Требуем доступность ВСЕХ комнат, а не только цели — иначе
        # боковые ветки могут быть отрезаны декором при «PASS».
        bad_areas = unreachable_areas(candidate.solids, spec)
        if found and not bad_areas:
            m = candidate
            variant_used = variant
            break

    if m is None:
        # Запасной вариант: геометрия без декора всегда проходима.
        m = build_level(spec, wads, seed=config.seed,
                        use_decor=False, texture_lib=tex_lib)
        grid = build_grid(m.solids, z=24)
        found, steps, path, reason = find_path(grid, start, goal)
        bad_areas = unreachable_areas(m.solids, spec)
        if not found or bad_areas:
            print("ВНИМАНИЕ: даже без декора недоступны:", bad_areas)
            return 1
        print("ВНИМАНИЕ: декор перекрывал путь, карта собрана без декора")
        variant_used = -1

    spawn_z = spec.floor_thickness + 48
    if not spawn_is_clear(m.solids, (start[0], start[1], spawn_z),
                          z=spawn_z - 36):
        print("ВНИМАНИЕ: точка спавна внутри геометрии")
        return 1

    print("\n--- Проверка проходимости ---")
    print("Brush-объектов:", len(m.brushes), "| entity:", len(m.entities),
          "| вариант декора:", variant_used)
    print("старт {} -> цель {}: {}".format(
        start, goal, "ПРОХОДИМО" if found else "НЕ ПРОХОДИМО"))
    if not found:
        print("причина:", reason)
        return 1
    print("длина пути (клеток):", steps)
    print("недоступных комнат:", len(bad_areas))
    print(ascii_map(grid, path, to_cell(grid, start), to_cell(grid, goal),
                    max_x=110, max_y=45))

    if not args.no_mechanics:
        add_objective(m, spec, tex_lib,
                      script_name=spec.name if use_script else None)
        if use_script:
            script_path, cfg_path = write_map_script(
                game_dir, spec.name, 2
            )
            print("\nAngelScript:", script_path)
            print("CFG карты:", cfg_path)
        checks = validate_objective(spec, m)
        print("\n--- Проверка механики ---")
        for name, ok in checks.items():
            print("  {}: {}".format(name, "OK" if ok else "FAIL"))
        if not checks.get("objective"):
            return 1

    # Визуальная проверка: SVG со схемой комнат, дверей, света и маршрута.
    preview_path = os.path.join(PROJECT_MAPS, spec.name + "_preview.svg")
    write_preview(spec, m, path, grid, preview_path)
    print("\nПревью:", preview_path)
    print("Светильников:", len(m.meta.get("lights", [])))
    if tex_lib.missing:
        print("ВНИМАНИЕ — текстуры не найдены:", sorted(tex_lib.missing))

    project_map = os.path.join(PROJECT_MAPS, spec.name + ".map")
    m.write(project_map)
    addon_maps = os.path.join(game_dir, "svencoop_addon", "maps")
    os.makedirs(addon_maps, exist_ok=True)
    game_map = os.path.join(addon_maps, spec.name + ".map")
    shutil.copyfile(project_map, game_map)
    print("\n.map:", project_map)

    if not args.build:
        print("Без флага --build компиляция не запускалась.")
        return 0

    print("\n--- Компиляция ---")
    result = compile_map(game_map, compilers_dir, log_dir=PROJECT_LOGS)
    print("BSP:", result["bsp"])

    if args.smoke:
        print("\n--- Проверка загрузки ---")
        output = smoke_test_load(
            spec.name, game_dir, seconds=10,
            extra_args=("+developer", "1"),
        )
        log_path = os.path.join(PROJECT_LOGS, "server_load_gen.log")
        with open(log_path, "w", encoding="utf-8", errors="replace") as f:
            f.write(output)
        loaded = [line for line in output.splitlines() if "Started map" in line]
        print("Лог сервера:", log_path)
        if not loaded:
            print("ВНИМАНИЕ: строка 'Started map' не найдена")
            return 1
        print("КАРТА ЗАГРУЖЕНА:", loaded[0].strip())

        if use_script:
            compiled = [
                line for line in output.splitlines()
                if "Map script compilation succeeded" in line
            ]
            if compiled:
                print("ANGELSCRIPT: компиляция скрипта успешна")
            else:
                print("ВНИМАНИЕ: подтверждение компиляции скрипта не найдено")
                return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
