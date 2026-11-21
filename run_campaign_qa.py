"""Пакетный QA кампании: все главы + отчёт.

Запуск:
    python run_campaign_qa.py
    python run_campaign_qa.py --no-smoke
"""

import argparse
import json
import os
import sys
import time

from svenmap.campaign import load_campaign
from svenmap.mechanics import validate_objective
from svenmap.pipeline import detect_roots, compile_map, smoke_test_load
from svenmap.progression import add_changelevel
from svenmap.secrets import validate_secrets
from svenmap.textures import TextureLibrary
from svenmap.validator import unreachable_areas
from svenmap.validator_portals import validate_portal_binding
from svenmap.planning import resolve_all_portals
from svenmap.scripts import write_map_script
from svenmap.leak_repair import repair_leaks
from svenmap.composition_metrics import summarize as summarize_composition

from generate_campaign import (
    CAMPAIGN_JSON, PROJECT_LOGS, PROJECT_MAPS,
    build_chapter, build_chapter_v2, wads,
)

NOTES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "notes")


def chapter_checks(chapter, m, level, campaign, index, blueprint=None):
    checks = {}
    nxt = campaign.next_chapter(chapter.name)

    if chapter.final:
        checks["no_changelevel"] = not any(
            e.get("classname") == "trigger_changelevel" for e in m.entities
        ) and not any(
            e.get("classname") == "trigger_changelevel" for e, _ in m.brush_entities
        )
        checks["boss_waves"] = len(m.meta.get("campaign", {}).get("boss_waves", [])) >= 3
    else:
        found = [
            e for e, _ in m.brush_entities
            if e.get("classname") == "trigger_changelevel"
        ]
        checks["changelevel"] = (
            len(found) == 1 and found[0].get("map") == (nxt.name if nxt else "")
        )

    spawns = sum(
        1 for e in m.entities if e.get("classname") == "info_player_deathmatch"
    )
    checks["coop_spawns"] = spawns >= 4

    if blueprint is not None:
        floors = {
            a["node_id"]: a.get("floor", 0)
            for a in blueprint["spatial"]["areas"]
        }
        bad = [
            area_id for area_id in unreachable_areas(m.solids, level)
            if floors.get(area_id, 0) == 0
        ]
        checks["all_areas"] = not bad
    else:
        checks["all_areas"] = (
            not unreachable_areas(m.solids, level)
            if not m.meta.get("secrets") else True
        )

    objective = validate_objective(level, m)
    for key, value in objective.items():
        checks[key] = value

    if m.meta.get("secrets"):
        for key, value in validate_secrets(level, m).items():
            checks[key] = value

    if blueprint is not None:
        portals = resolve_all_portals(blueprint)
        binding = validate_portal_binding(blueprint, portals, m)
        checks["portal_binding"] = binding["passed"]

    return checks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-smoke", action="store_true")
    parser.add_argument("--planner", choices=("legacy", "graph_v2"),
                        default="graph_v2")
    parser.add_argument("--only", default="",
                        help="проверить только одну главу по имени")
    args = parser.parse_args()

    _common, compilers_dir, game_dir = detect_roots()
    campaign = load_campaign(CAMPAIGN_JSON)
    chapters = campaign.chapters
    if args.only:
        chapters = [c for c in chapters if c.name == args.only]
        if not chapters:
            print("нет главы с именем", args.only)
            return 1
    tex_lib = TextureLibrary(game_dir)
    wad_list = wads(game_dir)

    started = time.time()
    results = []
    for index, chapter in enumerate(chapters, start=1):
        print("\n=== глава {}/{}: {} ===".format(
            index, len(chapters), chapter.name))
        blueprint = None
        if args.planner == "graph_v2":
            m, level, variant, secret_count, blueprint = build_chapter_v2(
                chapter, tex_lib, wad_list, game_dir
            )
        else:
            m, level, variant, secret_count = build_chapter(
                chapter, tex_lib, wad_list
            )
        if not chapter.final:
            nxt = campaign.next_chapter(chapter.name)
            add_changelevel(m, level, nxt.name)
        real_index = next(
            i for i, c in enumerate(campaign.chapters, start=1)
            if c.name == chapter.name
        )
        checks = chapter_checks(chapter, m, level, campaign, real_index,
                                blueprint)

        details = {
            "brush": len(m.brushes),
            "entities": len(m.entities),
            "secret_count": secret_count,
        }
        if blueprint is not None:
            details["composition"] = summarize_composition(blueprint)
        addon_maps = os.path.join(game_dir, "svencoop_addon", "maps")
        game_map = os.path.join(addon_maps, chapter.name + ".map")
        script_mode = "collect" if "collect" in chapter.puzzles else "buttons"
        write_map_script(
            game_dir, chapter.name,
            5 if script_mode == "collect" else 2,
            label="Samples" if script_mode == "collect" else "Generators",
            chapter=real_index, final=chapter.final,
            secret_total=secret_count,
        )
        m.write(game_map)
        if blueprint is not None and not args.no_smoke:
            repair_leaks(m, level, blueprint, game_map, compilers_dir)

        if not args.no_smoke:
            try:
                compile_map(game_map, compilers_dir, log_dir=PROJECT_LOGS)
                for stage in ("CSG", "BSP", "VIS", "RAD"):
                    checks["compile_" + stage] = True
                detailed = os.path.join(addon_maps, chapter.name + ".log")
                log = open(detailed, encoding="utf-8", errors="replace").read()
                checks["no_leak"] = not any(
                    p in log for p in ("LEAK", "Error:", "Illegal Brush")
                )
            except Exception as e:
                checks["compile"] = False
                details["compile_error"] = str(e)[:300]
            else:
                output = ""
                for _attempt in range(3):
                    output = smoke_test_load(
                        chapter.name, game_dir, seconds=9,
                        extra_args=("+developer", "1"),
                    )
                    if "Started map" in output:
                        break
                    if "Unable to initialize Steam" not in output:
                        break
                checks["map_load"] = "Started map" in output
                checks["script_compile"] = (
                    "Map script compilation succeeded" in output
                )
                bsp = os.path.join(addon_maps, chapter.name + ".bsp")
                details["bsp_bytes"] = (
                    os.path.getsize(bsp) if os.path.isfile(bsp) else 0
                )

        passed = all(checks.values())
        print("  ", "PASS" if passed else "FAIL", "|",
              ", ".join(k for k, v in checks.items() if not v) or "все проверки")
        results.append({
            "chapter": chapter.name, "passed": passed,
            "checks": checks, "details": details,
        })

    elapsed = time.time() - started
    os.makedirs(NOTES, exist_ok=True)
    md = os.path.join(NOTES, "campaign_qa_report.md")
    js = os.path.join(NOTES, "campaign_qa_report.json")

    lines = [
        "# SvenMap Generator — QA кампании",
        "",
        "Кампания: {}; глав: {}; время {:.1f} с.".format(
            campaign.name, len(results), elapsed),
        "",
        "| Глава | Результат | Brush | Entity | Секретов | BSP, КБ |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for r in results:
        d = r["details"]
        lines.append("| {} | {} | {} | {} | {} | {} |".format(
            r["chapter"], "PASS" if r["passed"] else "FAIL",
            d.get("brush", "—"), d.get("entities", "—"),
            d.get("secret_count", 0), d.get("bsp_bytes", 0) // 1024 or "—",
        ))
    lines.append("")

    compositional = [r for r in results if "composition" in r["details"]]
    if compositional:
        lines += [
            "## Метрики композиции (P3.0)",
            "",
            "| Глава | topo | spatial | stretch | глубина ветки | "
            "разнообразие форм | этажей |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
        for r in compositional:
            c = r["details"]["composition"]
            lines.append(
                "| {} | {:.3f} | {:.3f} | {:.2f} | {:.0f} | {:.2f} | {} |"
                .format(
                    r["chapter"], c["topology_score"], c["spatial_score"],
                    c["route_stretch"], c["branch_depth"],
                    c["shape_variety"], int(c["floors"]),
                )
            )
        lines += [
            "",
            "Превью планировок: `notes/previews/<имя>.svg`. Метрики — "
            "фильтр pass/warn, а не целевая функция: итоговое решение "
            "всегда за человеком, который проходит карту.",
            "",
        ]

    for r in results:
        lines.append("### {} — {}".format(
            r["chapter"], "PASS" if r["passed"] else "FAIL"))
        lines.append(", ".join(
            "{}={}".format(k, "OK" if v else "FAIL")
            for k, v in sorted(r["checks"].items())
        ))
        if r["details"].get("compile_error"):
            lines.append("Ошибка: " + r["details"]["compile_error"])
        lines.append("")

    passed = sum(1 for r in results if r["passed"])
    lines.append("Итого: {}/{}".format(passed, len(results)))

    with open(md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    with open(js, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print("\nИТОГ: {}/{} глав пройдено".format(passed, len(results)))
    print("Отчёт:", md)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
