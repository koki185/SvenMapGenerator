"""Авто-ремонт LEAK по указанию BSP (Autonomous Refinement).

BSP явно называет сущность, с которой начался flood-fill наружу.
Такую сущность можно убрать или перенести в безопасную комнату и
пересобрать карту, не пересоздавая всю планировку.
"""

import os
import re
import subprocess

from .v2_entities import area_center_world, GRID

ENTITY_RE = re.compile(
    r"Entity\s+(\w+)\s+@\s*\(\s*([-\d.]+)[, ]+\s*([-\d.]+)[, ]+\s*([-\d.]+)\s*\)"
)


def _compile_quick(game_map, compilers_dir):
    log_path = os.path.splitext(game_map)[0] + ".log"
    if os.path.isfile(log_path):
        os.remove(log_path)
    results = []
    for tool in ("SC-CSG_x64.exe", "SC-BSP_x64.exe"):
        exe = os.path.join(compilers_dir, tool)
        proc = subprocess.run(
            [exe, game_map, "-console", "0", "-noinfo"],
            capture_output=True, text=True, errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        results.append(proc.returncode)

    if results != [0, 0]:
        return False
    log_path = os.path.splitext(game_map)[0] + ".log"
    if os.path.isfile(log_path):
        text = open(log_path, encoding="utf-8", errors="replace").read()
        if "=== LEAK" in text:
            return False
    return True


def repair_leaks(m, spec, blueprint, game_map, compilers_dir,
                 max_rounds=6):
    """Устранить entity-источники утечки. Возвращает True при успехе."""
    areas = {a["node_id"]: a for a in blueprint["spatial"]["areas"]}
    safe = area_center_world(areas[spec.start])

    for round_index in range(max_rounds):
        m.write(game_map)
        if _compile_quick(game_map, compilers_dir):
            return True

        log_path = os.path.splitext(game_map)[0] + ".log"
        if not os.path.isfile(log_path):
            return False
        text = open(log_path, encoding="utf-8", errors="replace").read()
        match = ENTITY_RE.search(text)
        if not match:
            return False
        classname = match.group(1)
        entity_origin = tuple(float(match.group(i)) for i in (2, 3, 4))

        target = None
        for entity in m.entities:
            if entity.get("classname") != classname:
                continue
            origin = entity.get("origin")
            if not origin:
                continue
            parts = tuple(float(v) for v in origin.split())
            if all(abs(a - b) < 1.0 for a, b in zip(parts, entity_origin)):
                target = entity
                break
        if target is None:
            return False

        if classname in ("item_security", "func_button",
                         "info_player_start", "info_player_deathmatch",
                         "light", "env_sprite"):
            spawn_area = areas[spec.start]
            cells = spawn_area.get("cells") or [
                [cx, cy]
                for cx in range(spawn_area["w"])
                for cy in range(spawn_area["h"])
            ]
            candidates = sorted(
                (
                    (spawn_area["x"] + c[0] + 0.5) * GRID,
                    (spawn_area["y"] + c[1] + 0.5) * GRID,
                )
                for c in cells
            )
            candidates.sort(
                key=lambda p: (p[0] - safe[0]) ** 2 + (p[1] - safe[1]) ** 2
            )
            nx, ny = candidates[(round_index + 1) % len(candidates)]
            target["origin"] = "{} {} {}".format(
                int(nx), int(ny),
                24 if classname != "light" else 240,
            )
        else:
            m.entities.remove(target)
    return False
