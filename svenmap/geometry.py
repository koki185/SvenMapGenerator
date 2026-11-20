"""Геометрия brush для GoldSrc .map.

Для прямоугольных (ось-выровненных) brush каждая грань задаётся
тремя точками. ВАЖНО: в формате .map GoldSrc точки идут по часовой
стрелке, если смотреть на грань снаружи, — то есть нормаль по правилу
правой руки направлена ВНУТРЬ brush. Это подтверждено эталонной картой
SDK (ns_escape.map): у грани x = -3368 нормаль -X, хотя наружу там +X.

Если сделать нормали наружу, CSG ругается «Illegal Brush (edge without
opposite face)», а BSP падает с «Exceeded MAX_LEAF_FACES».

Порядок точек вычисляется по правилу, а не берётся «на память»,
и дополнительно проверяется через векторное произведение.
"""

import math

_AXIS_INDEX = {"x": 0, "y": 1, "z": 2}

# Для оси A берём пару (B, C) так, чтобы B x C = +A (циклическая перестановка).
_BC = {"x": ("y", "z"), "y": ("z", "x"), "z": ("x", "y")}


class Bounds:
    """Ось-выровненный параллелепипед: x0..x1, y0..y1, z0..z1."""

    __slots__ = ("x0", "y0", "z0", "x1", "y1", "z1")

    def __init__(self, x0, y0, z0, x1, y1, z1):
        self.x0, self.y0, self.z0 = float(x0), float(y0), float(z0)
        self.x1, self.y1, self.z1 = float(x1), float(y1), float(z1)
        for name in ("x", "y", "z"):
            lo, hi = getattr(self, name + "0"), getattr(self, name + "1")
            if hi <= lo:
                raise ValueError(
                    "Bounds: {} must be > {}".format(name + "1", hi, lo)
                )

    def __repr__(self):
        return "Bounds({:g}, {:g}, {:g}, {:g}, {:g}, {:g})".format(
            self.x0, self.y0, self.z0, self.x1, self.y1, self.z1
        )


class Face:
    """Одна грань brush: три точки, ось и знак нормали."""

    __slots__ = ("points", "axis", "sign")

    def __init__(self, points, axis, sign):
        self.points = points
        self.axis = axis
        self.sign = sign

    @property
    def normal(self):
        return face_normal(self.points)


def face_normal(points):
    """Единичная нормаль грани по трём точкам (правило правой руки)."""
    (x1, y1, z1), (x2, y2, z2), (x3, y3, z3) = points
    v1 = (x2 - x1, y2 - y1, z2 - z1)
    v2 = (x3 - x1, y3 - y1, z3 - z1)
    n = (
        v1[1] * v2[2] - v1[2] * v2[1],
        v1[2] * v2[0] - v1[0] * v2[2],
        v1[0] * v2[1] - v1[1] * v2[0],
    )
    length = math.sqrt(sum(c * c for c in n))
    if length < 1e-9:
        raise ValueError("вырожденная грань (точки лежат на одной прямой)")
    return tuple(c / length for c in n)


def _face_points(b, axis, sign):
    b_axis, c_axis = _BC[axis]
    coord = getattr(b, axis + ("0" if sign < 0 else "1"))
    b0, b1 = getattr(b, b_axis + "0"), getattr(b, b_axis + "1")
    c0, c1 = getattr(b, c_axis + "0"), getattr(b, c_axis + "1")

    def point(bv, cv):
        values = {axis: coord, b_axis: bv, c_axis: cv}
        return (values["x"], values["y"], values["z"])

    p1 = point(b0, c0)
    p2 = point(b1, c0)
    p3 = point(b0, c1)
    if sign > 0:
        # У грани на максимальной координате нормаль должна смотреть
        # в минус по оси (внутрь brush), поэтому меняем порядок точек.
        p2, p3 = p3, p2
    return p1, p2, p3


def box_faces(bounds):
    """Шесть граней коробки с нормалями внутрь (как требует .map)."""
    faces = []
    for axis in ("x", "y", "z"):
        for sign in (-1, 1):
            face = Face(_face_points(bounds, axis, sign), axis, sign)
            _assert_inward(face)
            faces.append(face)
    return faces


def _assert_inward(face):
    # sign = -1 — минимальная координата, inward-нормаль +axis;
    # sign = +1 — максимальная координата, inward-нормаль -axis.
    expected = [0.0, 0.0, 0.0]
    expected[_AXIS_INDEX[face.axis]] = -float(face.sign)
    actual = face.normal
    if any(abs(a - e) > 1e-6 for a, e in zip(actual, expected)):
        raise AssertionError(
            "неверная нормаль грани {}{}: {} (ожидалось {})".format(
                face.axis, "+" if face.sign > 0 else "-", actual, expected
            )
        )
