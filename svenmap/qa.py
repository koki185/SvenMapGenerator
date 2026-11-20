"""Автоматический QA-контур (этап 8).

Для каждого seed проходит весь путь: планировщик -> валидация ->
геометрия -> механика -> скрипт -> компиляция -> загрузка в игру.
Ошибки одного seed не останавливают остальные — всё собирается в отчёт.
"""

import os
import shutil
from dataclasses import dataclass, field

from .builders import build_level
from .mechanics import add_objective, validate_objective
from .pipeline import CompileError, compile_map, detect_roots, smoke_test_load
from .planner import PlannerConfig, plan
from .scripts import write_map_script
from .textures import TextureLibrary
from .validator import (
    build_grid, find_path, spawn_is_clear, unreachable_areas,
)

BAD_LOG_PATTERNS = (
    "LEAK", "Error:", "Illegal Brush", "Exceeded MAX_LEAF_FACES",
    "WARNING: output file",
)


@dataclass
class QAResult:
    seed: int
    map_name: str = ""
    checks: dict = field(default_factory=dict)
    details: dict = field(default_factory=dict)
    errors: list = field(default_factory=list)

    @property
    def passed(self):
        return bool(self.checks) and all(self.checks.values()) and not self.errors

    def check(self, name, ok):
        self.checks[name] = bool(ok)


def _wads(game_dir):
    names = [
        os.path.join(game_dir, "svencoop", "zhlt.wad"),
        os.path.join(game_dir, "svencoop", "halflife.wad"),
    ]
    return [os.path.splitdrive(p)[1] for p in names if os.path.isfile(p)]


def _parse_seeds(text):
    """'1-5,7' -> [1,2,3,4,5,7]."""
    seeds = []
    for part in str(text).split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            lo, hi = part.split("-", 1)
            seeds.extend(range(int(lo), int(hi) + 1))
        else:
            seeds.append(int(part))
    return sorted(set(seeds))


def check_seed(seed, game_dir, compilers_dir, project_maps, project_logs,
               rooms=6, branches=1, smoke_seconds=8, compile_map_file=True):
    """Прогнать один seed. Возвращает QAResult."""
    result = QAResult(seed=seed)
    config = PlannerConfig(seed=seed, room_count=rooms, branch_count=branches)

    try:
        spec = plan(config)
        result.map_name = spec.name
        result.check("plan", True)
    except Exception as e:
        result.check("plan", False)
        result.errors.append("plan: " + str(e))
        return result

    try:
        wads = _wads(game_dir)
        tex_lib = TextureLibrary(game_dir)
        start = spec.area_center(spec.start)
        goal = spec.area_center(spec.goal)

        # Перебор вариантов декора, пока путь не станет проходимым.
        m = None
        variant = -1
        for candidate_variant in range(12):
            candidate = build_level(
                spec, wads,
                seed=seed + candidate_variant * 101,
                texture_lib=tex_lib,
            )
            grid = build_grid(candidate.solids, z=24)
            found, steps, _path, _reason = find_path(grid, start, goal)
            bad_areas = unreachable_areas(candidate.solids, spec)
            if found and not bad_areas:
                m = candidate
                variant = candidate_variant
                break
        if m is None:
            # Запасной вариант — геометрия без декора.
            m = build_level(spec, wads, seed=seed, texture_lib=tex_lib,
                            use_decor=False)
            bad_areas = unreachable_areas(m.solids, spec)
            grid = build_grid(m.solids, z=24)
            found, steps, _path, _reason = find_path(grid, start, goal)
            variant = -1
            if not found or bad_areas:
                raise RuntimeError(
                    "недоступные комнаты даже без декора: " + str(bad_areas)
                )

        result.check("all_rooms_reachable", not bad_areas)
        spawn_z = spec.floor_thickness + 48
        result.check("spawn_clear", spawn_is_clear(
            m.solids, (start[0], start[1], spawn_z), z=spawn_z - 36
        ))

        result.details["brush"] = len(m.brushes)
        result.details["decor_variant"] = variant
        result.details["path_steps"] = steps
        result.check("path", True)

        add_objective(m, spec, tex_lib, script_name=spec.name)
        objective = validate_objective(spec, m)
        for name, ok in objective.items():
            if name != "objective":
                result.check(name, ok)
        result.check("objective", objective.get("objective", False))
        result.details["missing_textures"] = sorted(tex_lib.missing)

        script_path, cfg_path = write_map_script(
            game_dir, spec.name, len(m.meta["mechanics"]["buttons"])
        )
        result.check("script_files",
                     os.path.isfile(script_path) and os.path.isfile(cfg_path))

        os.makedirs(project_maps, exist_ok=True)
        project_map = os.path.join(project_maps, spec.name + ".map")
        m.write(project_map)

        addon_maps = os.path.join(game_dir, "svencoop_addon", "maps")
        os.makedirs(addon_maps, exist_ok=True)
        game_map = os.path.join(addon_maps, spec.name + ".map")
        shutil.copyfile(project_map, game_map)
    except Exception as e:
        result.check("path", False)
        result.errors.append("build: " + str(e))
        return result

    if compile_map_file:
        try:
            compile_map(game_map, compilers_dir, log_dir=project_logs)
            for stage in ("CSG", "BSP", "VIS", "RAD"):
                result.check("compile_" + stage, True)
        except CompileError as e:
            result.errors.append("compile: " + str(e)[:300])
            for stage in ("CSG", "BSP", "VIS", "RAD"):
                result.check("compile_" + stage, False)
            return result

        detailed = os.path.join(addon_maps, spec.name + ".log")
        try:
            with open(detailed, "r", encoding="utf-8", errors="replace") as f:
                log = f.read()
        except OSError:
            log = ""
        found_bad = [p for p in BAD_LOG_PATTERNS if p in log]
        result.check("no_leak", not found_bad)
        if found_bad:
            result.errors.append("компиляция: " + ", ".join(found_bad))
        bsp = os.path.join(addon_maps, spec.name + ".bsp")
        result.details["bsp_bytes"] = (
            os.path.getsize(bsp) if os.path.isfile(bsp) else 0
        )

    if smoke_seconds > 0:
        output = ""
        for attempt in range(3):
            output = smoke_test_load(
                spec.name, game_dir, seconds=smoke_seconds,
                extra_args=("+developer", "1"),
            )
            if "Started map" in output:
                break
            if "Unable to initialize Steam" not in output:
                break
        os.makedirs(project_logs, exist_ok=True)
        with open(os.path.join(project_logs, "qa_" + spec.name + ".log"),
                  "w", encoding="utf-8", errors="replace") as f:
            f.write(output)
        result.check("map_load", "Started map" in output)
        result.check("script_compile",
                     "Map script compilation succeeded" in output)
        if "Started map" not in output:
            result.errors.append("карта не загрузилась")

    return result
