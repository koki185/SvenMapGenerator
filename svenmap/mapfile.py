"""Сериализация сцены в текстовый исходник GoldSrc .map (формат Valve 220).

Синтаксис сверен с рабочим файлом J.A.C.K. (ns_escape.map из SDK):
каждая грань — три точки, имя текстуры, два вектора текстурных осей
и масштабы.
"""

from .geometry import box_faces
from .textures import TextureRef

# Текстурные оси для грани с заданной нормалью.
# В формате 220 пишется: [ ux uy uz shift ] [ vx vy vz shift ] rot uscale vscale
TEXTURE_AXES = {
    "x": ((0, 1, 0, 0), (0, 0, -1, 0)),
    "y": ((1, 0, 0, 0), (0, 0, -1, 0)),
    # Для горизонтальных граней в реальных картах чаще V = (0,-1,0).
    "z": ((1, 0, 0, 0), (0, -1, 0, 0)),
}


def num(value):
    """Число без лишних нулей и без '-0'."""
    value = float(value)
    if abs(value) < 1e-9:
        value = 0.0
    text = "{:.4f}".format(value).rstrip("0").rstrip(".")
    return text if text not in ("", "-") else "0"


def _quote(key, value):
    return '"{}" "{}"'.format(key, value)


class MapFile:
    """Простая модель .map: worldspawn + brush-объекты + point entity."""

    def __init__(self, wads=(), skyname="DESERT"):
        self.world_keys = {
            "classname": "worldspawn",
            "mapversion": "220",
            "skyname": skyname,
            "wad": ";".join(wads),
        }
        # brush — список пар (Face, имя текстуры)
        self.brushes = []
        # исходные границы brush — нужны валидатору проходимости
        self.solids = []
        # point entity — словарь ключ -> значение
        self.entities = []
        # brush entity: (словарь ключей, список граней)
        self.brush_entities = []
        # служебные данные для превью и проверок (в .map не пишутся)
        self.meta = {}

    @staticmethod
    def _make_brush(bounds, textures):
        brush = []
        for face in box_faces(bounds):
            if isinstance(textures, (str, TextureRef)):
                texture = textures
            else:
                texture = textures.get(face.axis, textures.get("default", "NULL"))
            brush.append((face, texture))
        return brush

    def add_box(self, bounds, textures):
        """Добавить прямоугольный brush в worldspawn."""
        brush = self._make_brush(bounds, textures)
        self.brushes.append(brush)
        self.solids.append(bounds)
        return brush

    def add_point_entity(self, classname, **keys):
        entity = {"classname": classname}
        entity.update(keys)
        self.entities.append(entity)
        return entity

    def add_brush_entity(self, classname, bounds, textures, **keys):
        """Сущность со своей геометрией: дверь, кнопка, триггер."""
        entity = {"classname": classname}
        entity.update(keys)
        brush = self._make_brush(bounds, textures)
        self.brush_entities.append((entity, brush))
        return entity

    @staticmethod
    def _face_line(face, texture):
        points = " ".join(
            "( {} )".format(" ".join(num(c) for c in point))
            for point in face.points
        )
        u_axis, v_axis = TEXTURE_AXES[face.axis]
        if isinstance(texture, TextureRef):
            name = texture.name
            u_scale, v_scale = texture.u_scale, texture.v_scale
        else:
            name, u_scale, v_scale = texture, 1.0, 1.0
        return "{} {} [ {} ] [ {} ] 0 {} {}".format(
            points, name,
            " ".join(num(c) for c in u_axis),
            " ".join(num(c) for c in v_axis),
            num(u_scale), num(v_scale),
        )

    @staticmethod
    def _write_entity(lines, entity, brush=None):
        lines.append("{")
        for key, value in entity.items():
            lines.append(_quote(key, value))
        if brush is not None:
            lines.append("{")
            for face, texture in brush:
                lines.append(MapFile._face_line(face, texture))
            lines.append("}")
        lines.append("}")

    def to_text(self):
        lines = ["{"]
        for key, value in self.world_keys.items():
            lines.append(_quote(key, value))

        for brush in self.brushes:
            lines.append("{")
            for face, texture in brush:
                lines.append(self._face_line(face, texture))
            lines.append("}")
        lines.append("}")

        for entity, brush in self.brush_entities:
            self._write_entity(lines, entity, brush)

        for entity in self.entities:
            self._write_entity(lines, entity)

        return "\n".join(lines) + "\n"

    def write(self, path):
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(self.to_text())
        return path
