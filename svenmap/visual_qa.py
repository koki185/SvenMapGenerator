"""Измеримые проверки визуального качества (P5).

Две hard-проверки (оси граней и «пол != потолок») не меняют геометрию,
но ловят регрессии вроде чёрных колонн и заливки акцентом. Остальные —
warn-метрики: они показывают, что улучшить, но не блокируют сборку.
"""

from typing import List

from .mapfile import TEXTURE_AXES, compiler_codec


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


MOJIBAKE_CHARS = "ÐÑÃâ€"


def looks_mojibake(text: str) -> bool:
    """Кракозябры вида «Ð Ñ Đâ» — признак двойного кодирования."""
    if not any("\u0400" <= ch <= "\u04ff" for ch in text):
        return sum(ch in MOJIBAKE_CHARS for ch in text) >= 2
    return False


def check_text_encoding(m) -> List[str]:
    """Кругооборот строки через кодировку CSG должен быть без потерь."""
    enc = compiler_codec()
    issues = []
    for entity in m.entities:
        if entity.get("classname") != "game_text":
            continue
        message = entity.get("message", "")
        try:
            back = message.encode(enc).decode(enc)
        except UnicodeEncodeError:
            issues.append("game_text {!r}: символ нельзя записать в {}"
                          .format(entity.get("targetname"), enc))
            continue
        if back != message:
            issues.append("game_text {!r}: кругооборот через {} исказил текст"
                          .format(entity.get("targetname"), enc))
        if looks_mojibake(message):
            issues.append("game_text {!r}: текст выглядит как кракозябры"
                          .format(entity.get("targetname")))
    return issues


FORBIDDEN_TEXTURES = {"BCRATE09A"}  # decal-картинка на маленьком кубе


def check_texture_roles(m) -> List[str]:
    """Запрещённые текстуры наBrushах."""
    issues = []
    for brush in m.brushes:
        for _face, texture in brush:
            name = getattr(texture, "name", str(texture))
            if name in FORBIDDEN_TEXTURES:
                issues.append("запрещённая текстура {} на браше".format(name))
    return issues[:8]


def check_decor_clearance(m, blueprint=None) -> List[str]:
    """Декор не должен стоять в проёме."""
    if not blueprint:
        return []
    grid = 192
    zones = []
    for conn in blueprint["spatial"]["connections"]:
        pa, pb = tuple(conn["portal_a"]), tuple(conn["portal_b"])
        zones.append((
            ((pa[0] + pb[0] + 1) / 2.0) * grid,
            ((pa[1] + pb[1] + 1) / 2.0) * grid,
            conn.get("id", "?"),
        ))
    issues = []
    for item in m.meta.get("decor_brushes", []):
        x0, y0, z0, x1, y1, z1 = item["bounds"]
        if z1 < 16 or z0 > 120:
            continue
        for zx, zy, portal_id in zones:
            if (x0 - 96 <= zx <= x1 + 96 and y0 - 96 <= zy <= y1 + 96):
                issues.append(
                    "декор {} ({}) на проёме {} ({:.0f} {:.0f})"
                    .format(item["area"], "/".join(item["kinds"]),
                            portal_id, zx, zy)
                )
                break
    return issues[:8]


def check_bsp_text(bsp_path: str, m) -> List[str]:
    """Истина после компиляции: ожидаемые строки должны лежать в BSP."""
    import struct

    with open(bsp_path, "rb") as f:
        data = f.read()
    offset, length = struct.unpack_from("<ii", data, 4)
    entities = data[offset:offset + length].rstrip(b"\0").decode(
        "utf-8", errors="replace")
    issues = []
    for entity in m.entities:
        if entity.get("classname") != "game_text":
            continue
        expected = entity.get("message", "")
        if expected and expected not in entities:
            issues.append(
                "game_text {}: в BSP нет строки {!r}"
                .format(entity.get("targetname"), expected)
            )
    return issues


def evaluate_visual(m, blueprint=None) -> dict:
    axis_errors = check_face_axes(m)
    surface_errors = check_surfaces(m)
    text_errors = check_text_encoding(m)
    texture_errors = check_texture_roles(m)
    decor_errors = check_decor_clearance(m, blueprint)
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
        "passed": (not axis_errors and not surface_errors
                   and not text_errors and not texture_errors
                   and not decor_errors),
        "axis_errors": axis_errors,
        "surface_errors": surface_errors,
        "text_errors": text_errors,
        "texture_errors": texture_errors,
        "decor_errors": decor_errors,
        "warnings": warnings,
        "metrics": metrics,
    }
