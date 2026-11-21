"""Схема campaign.json и валидатор с человекочитаемыми ошибками.

Принцип (из ревью Claude): слабый локальный ИИ не пишет код, а заполняет
маленький JSON из закрытых словарей. Валидатор должен отвечать одной
строкой с точным путём и подсказкой, а не traceback'ом:

    chapters[2].seed: seed 101 уже используется в chapters[0].
    Выберите другое число.

Жёсткие ограничения проверяются до генерации геометрии. Схема для
редакторов лежит рядом — campaign.schema.json.
"""

from dataclasses import dataclass
from typing import List

from .atmosphere import preset_names as narrative_names
from .pacing import profile_names
from .profiles import PROFILES
from .scenes import validate_scene_names

# Узкий словарь: чем меньше выбор, тем лучше его делает маленькая модель.
ALLOWED_THEMES = tuple(sorted(PROFILES))
ALLOWED_PUZZLES = (
    "buttons", "collect", "enemies", "multi_floor", "secret", "super_secret",
)
ALLOWED_PACINGS = profile_names()
ALLOWED_NARRATIVES = narrative_names()
ROOMS_RANGE = (4, 16)
BRANCHES_RANGE = (0, 4)


@dataclass
class ValidationIssue:
    path: str
    message: str

    def __str__(self):
        return "{}: {}".format(self.path, self.message)


class CampaignValidationError(ValueError):
    """Все найденные проблемы кампании в человекочитаемом виде."""

    def __init__(self, issues: List[ValidationIssue]):
        self.issues = issues
        super().__init__("\n".join(str(i) for i in issues))


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _allowed(values):
    return ", ".join(values)


def validate_data(data) -> List[ValidationIssue]:
    """Проверить сырые данные campaign.json. Никогда не бросает исключений."""
    issues: List[ValidationIssue] = []

    def add(path, message):
        issues.append(ValidationIssue(path, message))

    if not isinstance(data, dict):
        add("campaign", "ожидается JSON-объект с полями name и chapters")
        return issues

    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        add("name", 'отсутствует имя кампании. Укажите, например, "sc_expedition"')
    elif not name.replace("_", "").isalnum():
        add("name", "имя кампании должно содержать только буквы, цифры и _")

    chapters = data.get("chapters")
    if not isinstance(chapters, list):
        add("chapters", "ожидается список глав")
        return issues
    if len(chapters) < 2:
        add("chapters", "кампания должна содержать минимум 2 карты; "
                        "сейчас {}. Добавьте ещё главу".format(len(chapters)))
        return issues

    seen_names, seen_seeds = {}, {}
    final_indexes = []

    for i, raw in enumerate(chapters):
        path = "chapters[{}]".format(i)
        if not isinstance(raw, dict):
            add(path, "ожидается объект главы")
            continue

        ch_name = raw.get("name")
        if not isinstance(ch_name, str) or not ch_name.strip():
            add(path + ".name", "отсутствует имя карты. Пример: sc_exp_1")
        elif not all(c.isalnum() or c == "_" for c in ch_name):
            add(path + ".name", 'имя карты может содержать только a-z, 0-9 и _; '
                                'получено "{}"'.format(ch_name))
        elif ch_name in seen_names:
            add(path + ".name", 'имя "{}" уже использовано в {}; укажите '
                                'уникальное имя'.format(ch_name, seen_names[ch_name]))
        else:
            seen_names[ch_name] = path

        seed = raw.get("seed")
        if not _is_int(seed):
            add(path + ".seed", "нужно целое число; получено {!r}. "
                                "Пример: 101".format(seed))
        else:
            if seed in seen_seeds:
                add(path + ".seed", "seed {} уже используется в {}; выберите "
                                    "другое число".format(seed, seen_seeds[seed]))
            else:
                seen_seeds[seed] = path

        rooms = raw.get("rooms", 6)
        if not _is_int(rooms) or not ROOMS_RANGE[0] <= rooms <= ROOMS_RANGE[1]:
            add(path + ".rooms", "нужно целое число от {} до {}; получено {!r}"
                .format(ROOMS_RANGE[0], ROOMS_RANGE[1], rooms))

        branches = raw.get("branches", 1)
        if (not _is_int(branches)
                or not BRANCHES_RANGE[0] <= branches <= BRANCHES_RANGE[1]):
            add(path + ".branches", "нужно целое число от {} до {}; получено {!r}"
                .format(BRANCHES_RANGE[0], BRANCHES_RANGE[1], branches))

        theme = raw.get("theme", "industrial")
        if theme not in ALLOWED_THEMES:
            add(path + ".theme", 'тема {!r} не поддерживается. Доступно: {}'
                .format(theme, _allowed(ALLOWED_THEMES)))

        pacing = raw.get("pacing")
        if pacing is not None and pacing not in ALLOWED_PACINGS:
            add(path + ".pacing", 'профиль ритма {!r} не найден. Доступно: {}'
                .format(pacing, _allowed(ALLOWED_PACINGS)))

        narrative = raw.get("narrative")
        if narrative is not None and narrative not in ALLOWED_NARRATIVES:
            add(path + ".narrative",
                'нарративный пресет {!r} не найден. Доступно: {}'
                .format(narrative, _allowed(ALLOWED_NARRATIVES)))

        scenes = raw.get("scenes")
        if scenes is not None:
            if not isinstance(scenes, list):
                add(path + ".scenes", "ожидается список имён сцен")
            else:
                for j, bad in enumerate(validate_scene_names(scenes)):
                    add("{}.scenes[{}]".format(path, j),
                        'сцена {!r} не найдена. Проверьте scenes.json'.format(bad))

        puzzles = raw.get("puzzles", [])
        if not isinstance(puzzles, list):
            add(path + ".puzzles", "ожидается список механик, например "
                                   '["collect", "enemies"]')
        else:
            known = set(ALLOWED_PUZZLES)
            for j, token in enumerate(puzzles):
                if token not in known:
                    add("{}.puzzles[{}]".format(path, j),
                        'неизвестная механика {!r}. Доступно: {}'.format(
                            token, _allowed(ALLOWED_PUZZLES)))
            if "collect" in puzzles and "buttons" in puzzles:
                add(path + ".puzzles", 'нельзя указывать и "collect", и "buttons" '
                                       'в одной главе — выберите один тип цели')
            if len(set(puzzles)) != len(puzzles):
                add(path + ".puzzles", "механики не должны повторяться")

        if raw.get("final", False):
            if not isinstance(raw["final"], bool):
                add(path + ".final", "ожидается true или false")
            else:
                final_indexes.append(i)

    if not final_indexes:
        add("chapters", "нет финальной карты. Добавьте "
                        '"final": true в последнюю главу')
    elif len(final_indexes) > 1:
        add("chapters", "финальных карт {}; должна быть ровно одна"
            .format(len(final_indexes)))
    elif final_indexes[0] != len(chapters) - 1:
        bad = chapters[final_indexes[0]].get("name", "?")
        last = chapters[-1].get("name", "?") if isinstance(chapters[-1], dict) else "?"
        add("chapters[{}].final".format(final_indexes[0]),
            'final=true у "{}", а последняя глава — "{}". '
            'Финальной должна быть только последняя глава'.format(bad, last))

    return issues


def spec_to_data(spec) -> dict:
    """Обратное преобразование CampaignSpec в данные для валидации."""
    return {
        "name": spec.name,
        "chapters": [
            {
                "name": c.name, "seed": c.seed, "rooms": c.rooms,
                "branches": c.branches, "theme": c.theme,
                "final": c.final, "puzzles": list(c.puzzles),
                "pacing": c.pacing or None,
                "scenes": list(c.scenes),
                "narrative": c.narrative or None,
            }
            for c in spec.chapters
        ],
    }


def validate_spec(spec) -> None:
    """Проверить уже загруженную CampaignSpec (совместимость)."""
    issues = validate_data(spec_to_data(spec))
    if issues:
        raise CampaignValidationError(issues)


if __name__ == "__main__":
    import json
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else "campaign.json"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    issues = validate_data(data)
    if issues:
        print("campaign.json: найдены ошибки:")
        for issue in issues:
            print("  - " + str(issue))
        sys.exit(1)
    print("campaign.json: OK — {} глав".format(len(data.get("chapters", []))))
