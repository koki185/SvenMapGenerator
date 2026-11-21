"""Модель кампании: последовательность карт, которые продолжают друг друга.

Описание задаётся в campaign.json. Валидация проверяет цепочку имён,
уникальность seed и наличие ровно одной финальной карты — до того,
как начнётся генерация геометрии.
"""

import json
from dataclasses import dataclass, field

from .campaign_schema import (
    CampaignValidationError, validate_data, validate_spec,
)


@dataclass
class Chapter:
    name: str
    seed: int
    rooms: int = 6
    branches: int = 1
    theme: str = "industrial"
    final: bool = False
    puzzles: tuple = ()
    pacing: str = ""


@dataclass
class CampaignSpec:
    name: str
    chapters: list
    _by_name: dict = field(default_factory=dict, repr=False)

    def chapter(self, name):
        return self._by_name[name]

    def next_chapter(self, name):
        """Следующая по цепочке карта или None для финала."""
        for i, chapter in enumerate(self.chapters[:-1]):
            if chapter.name == name:
                return self.chapters[i + 1]
        return None


def load_campaign(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Проверяем до создания Chapter: ошибки должны быть человекочитаемыми
    # и указывать точный путь в JSON, а не падать traceback'ом позже.
    issues = validate_data(data)
    if issues:
        raise CampaignValidationError(issues)

    chapters = []
    for raw in data.get("chapters", []):
        chapters.append(Chapter(
            name=raw["name"],
            seed=int(raw["seed"]),
            rooms=int(raw.get("rooms", 6)),
            branches=int(raw.get("branches", 1)),
            theme=raw.get("theme", "industrial"),
            final=bool(raw.get("final", False)),
            puzzles=tuple(raw.get("puzzles", ())),
            pacing=raw.get("pacing", ""),
        ))

    spec = CampaignSpec(name=data["name"], chapters=chapters)
    spec._by_name = {c.name: c for c in spec.chapters}
    return spec


def validate_campaign(spec):
    """Проверить CampaignSpec теми же правилами (совместимость)."""
    validate_spec(spec)
    spec._by_name = {c.name: c for c in spec.chapters}
    return spec
