"""Автоподбор seed по метрикам композиции (P3.4).

Важно (по совету Claude): это НЕ оптимизация по максимальному score —
она уводит карты в усреднённое «всё одинаково». Генератор перебирает
N соседних seed, отбрасывает непрошедшие и показывает 2–3 лучших
человеку. Seed в campaign.json меняется только вручную.
"""

from dataclasses import dataclass
from typing import List

from .composition_validator import evaluate_composition
from .planning import BlueprintConfig, generate_blueprint
from .scenes import assign_scenes


@dataclass
class Candidate:
    seed: int
    delta: int
    passed: bool
    issues: List[dict]
    metrics: dict

    @property
    def issue_count(self):
        return len(self.issues)


def evaluate_seed(chapter, seed: int) -> Candidate:
    """Собрать blueprint для seed и оценить его валидатором композиции."""
    floors = 2 if "multi_floor" in chapter.puzzles else 1
    blueprint = generate_blueprint(BlueprintConfig(
        seed=seed,
        node_count=chapter.rooms,
        branch_count=chapter.branches,
        secret_count=2 if "secret" in chapter.puzzles else 0,
        floors=floors,
    ))
    blueprint["scene_assignments"] = assign_scenes(
        blueprint, chapter.scenes, seed=seed
    )
    verdict = evaluate_composition(
        blueprint, chapter.name, chapter.pacing
    )
    return Candidate(
        seed=seed,
        delta=seed - chapter.seed,
        passed=verdict["passed"],
        issues=verdict["issues"],
        metrics=verdict["metrics"],
    )


def _rank(candidate: Candidate):
    """Меньше замечаний — лучше; затем выше разнообразие сцен."""
    variety = candidate.metrics["variety"]["scene_variety"]
    return (
        not candidate.passed,
        candidate.issue_count,
        -variety,
    )


def propose(chapter, campaign=None, count: int = 12, top: int = 3) -> List[Candidate]:
    """Предложить 2–3 кандидата. Используемые кампанией seed пропускаются."""
    used = {c.seed for c in campaign.chapters} if campaign else set()
    used.discard(chapter.seed)
    candidates: List[Candidate] = []
    seed = chapter.seed
    tried = 0
    while tried < count:
        if seed not in used:
            try:
                candidates.append(evaluate_seed(chapter, seed))
            except (RuntimeError, ValueError, KeyError):
                pass  # непроходимый seed просто не предлагаем
            tried += 1
        seed += 1
    candidates.sort(key=_rank)
    return candidates[:top]


def format_candidates(chapter, candidates: List[Candidate]) -> str:
    lines = [
        "### {} — предложения seed (текущий {})".format(
            chapter.name, chapter.seed),
        "",
        "| seed | сдвиг | результат | замечаний | разнообразие сцен |",
        "|---:|---:|---|---:|---:|",
    ]
    for c in candidates:
        lines.append(
            "| {} | {:+d} | {} | {} | {:.2f} |".format(
                c.seed, c.delta,
                "PASS" if c.passed else "WARN",
                c.issue_count,
                c.metrics["variety"]["scene_variety"],
            )
        )
        for issue in c.issues[:3]:
            lines.append("  - {}: {}".format(issue["path"], issue["message"]))
    lines.append("")
    if not any(c.passed for c in candidates):
        lines.append(
            "> Ни один кандидат не прошёл полностью — покажите 2–3 с "
            "наименьшим числом замечаний человеку и решите сами."
        )
    lines.append(
        "> Seed в campaign.json не меняется автоматически: выберите "
        "подходящий и внесите его вручную."
    )
    return "\n".join(lines)
