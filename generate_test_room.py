"""Этап 1: минимальная карта, собранная полностью кодом.

Цель — проверить весь цикл: описание -> .map -> CSG/BSP/VIS/RAD -> загрузка.
Никаких механик и скриптов на этом этапе нет намеренно.

Запуск:
    python generate_test_room.py            # только сгенерировать .map
    python generate_test_room.py --build    # сгенерировать и скомпилировать
    python generate_test_room.py --build --smoke   # ещё и проверить загрузку
"""

import argparse
import os
import shutil
import sys

from svenmap.geometry import Bounds
from svenmap.mapfile import MapFile
from svenmap.pipeline import detect_roots, compile_map, smoke_test_load
from svenmap.validator import (
    build_grid, find_path, parse_origin, ascii_map, to_cell,
)

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_MAPS = os.path.join(HERE, "maps")
PROJECT_LOGS = os.path.join(HERE, "logs")
MAP_NAME = "sm_test_room"

# Текстуры из halflife.wad — проверено, что они там есть.
TEX_FLOOR = "LAB1_FLOOR1"
TEX_CEILING = "BABTECH_CEIL01"
TEX_WALL = "C1A0_LABW1"
TEX_DIVIDER = "METAL_WALL01B"


def wad_paths(game_dir):
    """Пути к WAD в формате, который использует рабочий .map из SDK.

    В эталонной карте J.A.C.K. пишет пути без буквы диска:
    '\\SteamLibrary\\...\\halflife.wad'. Повторяем это, чтобы не
    привязываться к букве при переносе проекта.
    """
    names = [
        os.path.join(game_dir, "svencoop", "zhlt.wad"),
        os.path.join(game_dir, "svencoop", "halflife.wad"),
    ]
    return [os.path.splitdrive(p)[1] for p in names if os.path.isfile(p)]


def build_map(game_dir):
    m = MapFile(wads=wad_paths(game_dir), skyname="DESERT")

    # Оболочка помещения: пол, потолок и четыре стены.
    m.add_box(Bounds(0, 0, 0, 1024, 512, 16), TEX_FLOOR)
    m.add_box(Bounds(0, 0, 272, 1024, 512, 288), TEX_CEILING)
    m.add_box(Bounds(0, 0, 16, 1024, 16, 272), TEX_WALL)       # юг
    m.add_box(Bounds(0, 496, 16, 1024, 512, 272), TEX_WALL)    # север
    m.add_box(Bounds(0, 16, 16, 16, 496, 272), TEX_WALL)       # запад
    m.add_box(Bounds(1008, 16, 16, 1024, 496, 272), TEX_WALL)  # восток

    # Внутренняя стена с дверным проёмом 128x128 по центру.
    # Проём сделан разбиением стены на сегменты — без булевой резки.
    m.add_box(Bounds(504, 16, 16, 520, 192, 272), TEX_DIVIDER)   # левая часть
    m.add_box(Bounds(504, 320, 16, 520, 496, 272), TEX_DIVIDER)  # правая часть
    m.add_box(Bounds(504, 192, 144, 520, 320, 272), TEX_DIVIDER) # перемычка

    # Игрок стартует в первой комнате; во второй просто можно зайти.
    m.add_point_entity(
        "info_player_start",
        origin="256 256 24",
        angles="0 0 0",
    )

    # Два источника света, чтобы обе комнаты были видны.
    for origin in ("256 256 240", "768 256 240"):
        m.add_point_entity(
            "light",
            origin=origin,
            angles="0 0 0",
            _light="255 255 255 220",
            _falloff="0",
            _fade="1.0",
            style="0",
            spawnflags="0",
        )

    return m


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()

    steam_common, compilers_dir, game_dir = detect_roots()
    print("Steam common:", steam_common)
    print("Компиляторы:", compilers_dir)
    print("Игра:", game_dir)

    os.makedirs(PROJECT_MAPS, exist_ok=True)
    project_map = os.path.join(PROJECT_MAPS, MAP_NAME + ".map")

    m = build_map(game_dir)
    m.write(project_map)
    print("Создан .map:", project_map)
    print("  brush-объектов:", len(m.brushes))
    print("  entity:", len(m.entities))

    # Проверка проходимости: старт -> вторая комната через проём.
    start = parse_origin(m.entities[0]["origin"])[:2]
    goal = (768.0, 256.0)
    grid = build_grid(m.solids)
    found, steps, path, reason = find_path(grid, start, goal)
    print("\n--- Проверка проходимости ---")
    print("старт:", start, "-> цель:", goal)
    print("результат:", "ПРОХОДИМО" if found else "НЕ ПРОХОДИМО", reason)
    if found:
        print("длина пути (клеток):", steps)
        print(ascii_map(grid, path, to_cell(grid, start), to_cell(grid, goal)))
    else:
        return 1

    # Кладём исходник туда, где компиляторы и игра его ожидают.
    # SDK просит использовать svencoop_addon, а не svencoop.
    addon_maps = os.path.join(game_dir, "svencoop_addon", "maps")
    os.makedirs(addon_maps, exist_ok=True)
    game_map = os.path.join(addon_maps, MAP_NAME + ".map")
    shutil.copyfile(project_map, game_map)
    print("Скопирован в игру:", game_map)

    if not args.build:
        print("\nБез флага --build компиляция не запускалась.")
        return 0

    print("\n--- Компиляция ---")
    result = compile_map(game_map, compilers_dir, log_dir=PROJECT_LOGS)
    print("BSP:", result["bsp"])

    if args.smoke:
        print("\n--- Проверка загрузки (дедикальный сервер) ---")
        output = smoke_test_load(MAP_NAME, game_dir, seconds=10)
        log_path = os.path.join(PROJECT_LOGS, "server_load.log")
        with open(log_path, "w", encoding="utf-8", errors="replace") as f:
            f.write(output)
        print("Лог сервера:", log_path)
        loaded = [line for line in output.splitlines() if "Started map" in line]
        if loaded:
            print("КАРТА ЗАГРУЖЕНА:", loaded[0].strip())
        else:
            print("ВНИМАНИЕ: строка 'Started map' в логе не найдена")
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
