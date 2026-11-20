"""Этап 8: пакетный QA по нескольким seed и итоговый отчёт.

Запуск:
    python run_qa.py --seeds 1-8
    python run_qa.py --seeds 1,3,5 --rooms 6 --branches 1 --no-smoke
"""

import argparse
import json
import os
import sys
import time

from svenmap.pipeline import detect_roots
from svenmap.qa import _parse_seeds, check_seed

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_MAPS = os.path.join(HERE, "maps")
PROJECT_LOGS = os.path.join(HERE, "logs")
NOTES = os.path.join(HERE, "notes")


def write_report(results, args, elapsed):
    os.makedirs(NOTES, exist_ok=True)
    md_path = os.path.join(NOTES, "qa_report.md")
    json_path = os.path.join(NOTES, "qa_report.json")

    lines = [
        "# SvenMap Generator — отчёт пакетного QA",
        "",
        "Дата: 20 ноября 2026 г.",
        "",
        "Параметры: seed {}; комнат {}; веток {}; компиляция {}; загрузка {}.".format(
            args.seeds, args.rooms, args.branches,
            "да" if not args.no_compile else "нет",
            "да" if not args.no_smoke else "нет",
        ),
        "Время выполнения: {:.1f} с.".format(elapsed),
        "",
        "| Seed | Карта | Результат | Brush | Вариант декора | BSP, КБ |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        size = r.details.get("bsp_bytes", 0) // 1024
        lines.append("| {} | {} | {} | {} | {} | {} |".format(
            r.seed, r.map_name or "—",
            "PASS" if r.passed else "FAIL",
            r.details.get("brush", "—"),
            r.details.get("decor_variant", "—"),
            size or "—",
        ))

    lines.extend(["", "## Детали по проверкам", ""])
    for r in results:
        lines.append("### seed {} ({}) — {}".format(
            r.seed, r.map_name or "—", "PASS" if r.passed else "FAIL"))
        checks = ", ".join(
            "{}={}".format(k, "OK" if v else "FAIL")
            for k, v in sorted(r.checks.items())
        )
        lines.append(checks or "нет проверок")
        if r.details.get("path_steps"):
            lines.append("Длина пути: {} клеток.".format(r.details["path_steps"]))
        if r.details.get("missing_textures"):
            lines.append("Не найденные текстуры: {}".format(
                ", ".join(r.details["missing_textures"])))
        if r.errors:
            lines.extend(["Ошибки:"] + ["- " + e for e in r.errors])
        lines.append("")

    passed = sum(1 for r in results if r.passed)
    lines.extend([
        "## Итог",
        "",
        "Пройдено {}/{} seed.".format(passed, len(results)),
    ])

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(
            [{"seed": r.seed, "map": r.map_name, "passed": r.passed,
              "checks": r.checks, "details": r.details, "errors": r.errors}
             for r in results],
            f, ensure_ascii=False, indent=2,
        )
    return md_path, json_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", default="1-8")
    parser.add_argument("--rooms", type=int, default=6)
    parser.add_argument("--branches", type=int, default=1)
    parser.add_argument("--no-compile", action="store_true")
    parser.add_argument("--no-smoke", action="store_true")
    args = parser.parse_args()

    steam_common, compilers_dir, game_dir = detect_roots()
    seeds = _parse_seeds(args.seeds)
    print("QA: seed", seeds)

    started = time.time()
    results = []
    for seed in seeds:
        print("\n--- seed {} ---".format(seed))
        result = check_seed(
            seed, game_dir, compilers_dir, PROJECT_MAPS, PROJECT_LOGS,
            rooms=args.rooms, branches=args.branches,
            smoke_seconds=0 if args.no_smoke else 8,
            compile_map_file=not args.no_compile,
        )
        results.append(result)
        print("  ", "PASS" if result.passed else "FAIL",
              "|", ", ".join(
                  k for k, v in result.checks.items() if not v
              ) or "все проверки пройдены")

    elapsed = time.time() - started
    md_path, json_path = write_report(results, args, elapsed)
    passed = sum(1 for r in results if r.passed)
    print("\nИТОГ: {}/{} seed пройдено".format(passed, len(results)))
    print("Отчёт:", md_path)
    print("JSON:", json_path)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
