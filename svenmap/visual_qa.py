"""Измеримые проверки визуального качества (P5).

Две hard-проверки (оси граней и «пол != потолок») не меняют геометрию,
но ловят регрессии вроде чёрных колонн и заливки акцентом. Остальные —
warn-метрики: они показывают, что улучшить, но не блокируют сборку.
"""

from typing import List

from .mapfile import TEXTURE_AXES


def check_face_axes(m) -> List[str]:
    """Osi текстуры должны лежать в плоскости грани."""
    bad = []
    for brush in m.brushes:
        for face, _texture in brush:
            n = face.normal
            u_axis, v_axis = TEXTURE_AXES[face.axis]
            for vec in (u_axis, v_axis):
                dot = abs(n[0] * vec[0] + n[1] * vec[1] + n[2] * vec[2])
                if dot > 1e-6:
                    bad.append("{} face {}".format(face.axis, vec))
                    break
    return bad[:8]


def check_surfaces(m) -> List[str]:
    """У каждой комнаты пол и потолок должны различаться."""
    issues = []
    for room, data in m.meta.get("surface", {}).items():
        floors = set(data.get("floor", []))
        ceilings = set(data.get("ceiling", []))
        if floors and ceilings and not (floors & ceilings):
            continue
        issues.append(
            "{}: пол и потолок используют общие текстуры {}".format(
                room, sorted(floors & ceilings)
            )
        )
    return issues


def visual_metrics(m) -> dict:
    """Warn-метрики по уже сохранённым метаданным сцены."""
    surface = m.meta.get("surface", {})
    textures = set()
    same_floor_ceiling = 0
    for data in surface.values():
        floors = set(data.get("floor", []))
        ceilings = set(data.get("ceiling", []))
        textures |= floors | ceilings
        if floors & ceilings:
            same_floor_ceiling += 1
    lamps = sum(
        1 for e in m.entities
        if e.get("classname") == "light"
        and str(e.get("targetname", "")).startswith("room_light_")
    )
    fills = sum(
        1 for e in m.entities
        if str(e.get("targetname", "")).startswith("fill_light_")
    )
    return {
        "distinct_textures": len(textures),
        "rooms_same_floor_ceiling": same_floor_ceiling,
        "visible_lamps": lamps,
        "fill_lights": fills,
        "rooms": len(surface),
    }


def evaluate_visual(m) -> dict:
    axis_errors = check_face_axes(m)
    surface_errors = check_surfaces(m)
    metrics = visual_metrics(m)
    warnings = []
    if metrics["rooms"] and metrics["visible_lamps"] < metrics["rooms"]:
        warnings.append(
            "видимых ламп {} меньше числа комнат {}".format(
                metrics["visible_lamps"], metrics["rooms"]
            )
        )
    if 4 <= metrics["rooms"] and metrics["distinct_textures"] < 4:
        warnings.append("мало разных текстур: {}".format(
            metrics["distinct_textures"]))
    return {
        "passed": not axis_errors and not surface_errors,
        "axis_errors": axis_errors,
        "surface_errors": surface_errors,
        "warnings": warnings,
        "metrics": metrics,
    }
