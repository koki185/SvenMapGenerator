"""Система текстур: проверка наличия текстур в WAD и нативный масштаб.

Опытным путём (20.11.2026) выяснено: в реальных картах Sven Co-op
подавляющее большинство граней использует масштаб 1.0 1.0. Попытка
«выровнять» тайлы по размеру в юнитах испортила рисунки: круглая кнопка
32x32 при масштабе 0.5 отображалась как две половинки («бабочка»).
Поэтому масштаб всегда 1.0, а модуль лишь проверяет, что текстура
реально есть в WAD.
"""

import os
import struct
from dataclasses import dataclass

# ВАЖНО: в реальных картах Sven Co-op 87% граней имеют масштаб 1.0 1.0.
# Текстуры WAD автором рассчитаны на нативный масштаб: попытка «выровнять
# тайл по юнитам» даёт разорванные рисунки (например, круглая кнопка
# превращается в две половинки). Поэтому масштаб всегда 1.0.
SPECIAL_PREFIXES = ("!", "{", "+", "-", "~")
SPECIAL_NAMES = {"NULL", "SKY", "AAATRIGGER", "ORIGIN", "CLIP", "HINT", "SKIP"}


@dataclass(frozen=True)
class TextureRef:
    name: str
    u_scale: float = 1.0
    v_scale: float = 1.0


def _wad_dimensions(path):
    """Имя -> (width, height) для всех miptex-блоков WAD2/WAD3."""
    with open(path, "rb") as f:
        data = f.read()
    if data[:4] not in (b"WAD2", b"WAD3"):
        return {}
    count, table_offset = struct.unpack_from("<ii", data, 4)
    result = {}
    for i in range(count):
        entry = table_offset + i * 32
        if entry + 32 > len(data):
            break
        filepos, _disk, _size, ltype, _comp, _pad = struct.unpack_from(
            "<iii BB H", data, entry
        )
        if ltype != 0x43 or filepos + 24 > len(data):
            continue
        name = data[entry + 16:entry + 32].split(b"\0", 1)[0]
        width, height = struct.unpack_from("<II", data, filepos + 16)
        if width and height:
            result[name.decode("latin-1", "replace")] = (width, height)
    return result


class TextureLibrary:
    """Кэш размеров текстур из WAD-файлов игры."""

    def __init__(self, game_dir):
        self.game_dir = game_dir
        self.paths = [
            os.path.join(game_dir, "svencoop", "halflife.wad"),
            os.path.join(game_dir, "svencoop", "zhlt.wad"),
            os.path.join(game_dir, "svencoop", "decals.wad"),
        ]
        self._cache = {}
        self.missing = set()

    def dimensions(self, name):
        if name not in self._cache:
            found = None
            for path in self.paths:
                if not os.path.isfile(path):
                    continue
                if not hasattr(self, "_wads"):
                    self._wads = {}
                if path not in self._wads:
                    self._wads[path] = _wad_dimensions(path)
                if name in self._wads[path]:
                    found = self._wads[path][name]
                    break
            self._cache[name] = found
        return self._cache[name]

    def ref(self, name, surface="wall"):
        """TextureRef с нативным масштабом 1.0 (как в картах SDK)."""
        if name not in SPECIAL_NAMES and not name.startswith(SPECIAL_PREFIXES):
            if self.dimensions(name) is None:
                self.missing.add(name)
        return TextureRef(name, 1.0, 1.0)
