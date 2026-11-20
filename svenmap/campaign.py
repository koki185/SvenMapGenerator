"""Модель кампании: последовательность карт, которые продолжают друг друга.

Описание задаётся в campaign.json. Валидация проверяет цепочку имён,
уникальность seed и наличие ровно одной финальной карты — до того,
как начнётся генерация геометрии.
"""

import json
from dataclasses import dataclass, field


@dataclass
class Chapter:
    name: str
    seed: int
    rooms: int = 6
    branches: int = 1
    theme: str = "industrial"
    final: bool = False
    puzzles: tuple = ()


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
        ))

    spec = CampaignSpec(name=data["name"], chapters=chapters)
    validate_campaign(spec)
    return spec


def validate_campaign(spec):
    if len(spec.chapters) < 2:
        raise ValueError("кампания должна содержать минимум 2 карты")

    names = [c.name for c in spec.chapters]
    if len(names) != len(set(names)):
        raise ValueError("имена карт в кампании не уникальны")

    finals = [c for c in spec.chapters if c.final]
    if len(finals) != 1 or not spec.chapters[-1].final:
        raise ValueError("финальной должна быть ровно последняя карта")

    seeds = [c.seed for c in spec.chapters]
    if len(seeds) != len(set(seeds)):
        raise ValueError("seed карт должны быть разными — иначе карты совпадут")

    spec._by_name = {c.name: c for c in spec.chapters}
    return spec
