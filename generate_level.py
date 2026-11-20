"""Этап 2: уровень из JSON-описания через библиотеку строительных функций.

Запуск:
    python generate_level.py                         # собрать и проверить
    python generate_level.py --build                 # + компиляция
    python generate_level.py --build --smoke         # + проверка загрузки
"""

import argparse
import os
import shutil
import sys

from svenmap.builders import build_level
from svenmap.level import load_level
from svenmap.pipeline import detect_roots, compile_map, smoke_test_load
from svenmap.validator import build_grid, find_path, parse_origin, ascii_map, to_cell

HERE = os.path.dirname(os.path.abspath(__file__))
LEVEL_JSON = os.path.join(HERE, "level.json")
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
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()

    steam_common, compilers_dir, game_dir = detect_roots()

    # 1. Читаем и ПРОВЕРЯЕМ описание до того, как строить геометрию.
    spec = load_level(LEVEL_JSON)
    print("Уровень:", spec.name, "| тема:", spec.theme)
    print("Площадей:", len(spec.areas), "| связей:", len(spec.connections))

    # 2. Строим геометрию библиотекой.
    # Этап 2 демонстрирует чистую геометрию без декора (декор — этап 4).
    m = build_level(spec, wad_paths(game_dir), use_decor=False)
    print("Brush-объектов:", len(m.brushes), "| entity:", len(m.entities))

    # 3. Проверяем проходимость старт -> цель.
    start = spec.area_center(spec.start)
    goal = spec.area_center(spec.goal)
    grid = build_grid(m.solids, z=24)
    found, steps, path, reason = find_path(grid, start, goal)
    print("\n--- Проверка проходимости ---")
    print("старт:", start, "-> цель:", goal)
    print("результат:", "ПРОХОДИМО" if found else "НЕ ПРОХОДИМО", reason)
    if not found:
        return 1
    print("длина пути (клеток):", steps)
    print(ascii_map(grid, path, to_cell(grid, start), to_cell(grid, goal),
                    max_x=110, max_y=45))

    # 4. Пишем .map и кладём его в игру.
    os.makedirs(PROJECT_MAPS, exist_ok=True)
    name = spec.name
    project_map = os.path.join(PROJECT_MAPS, name + ".map")
    m.write(project_map)
    print("\nСоздан .map:", project_map)

    addon_maps = os.path.join(game_dir, "svencoop_addon", "maps")
    os.makedirs(addon_maps, exist_ok=True)
    game_map = os.path.join(addon_maps, name + ".map")
    shutil.copyfile(project_map, game_map)
    print("Скопирован в игру:", game_map)

    if not args.build:
        print("\nБез флага --build компиляция не запускалась.")
        return 0

    print("\n--- Компиляция ---")
    result = compile_map(game_map, compilers_dir, log_dir=PROJECT_LOGS)
    print("BSP:", result["bsp"])

    if args.smoke:
        print("\n--- Проверка загрузки ---")
        output = smoke_test_load(name, game_dir, seconds=10)
        log_path = os.path.join(PROJECT_LOGS, "server_load_level.log")
        with open(log_path, "w", encoding="utf-8", errors="replace") as f:
            f.write(output)
        loaded = [line for line in output.splitlines() if "Started map" in line]
        print("Лог сервера:", log_path)
        if loaded:
            print("КАРТА ЗАГРУЖЕНА:", loaded[0].strip())
        else:
            print("ВНИМАНИЕ: строка 'Started map' не найдена")
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
