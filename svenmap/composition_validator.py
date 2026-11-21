"""Валидатор композиции (P3.3): ритм, разнообразие, структура маршрута.

Объединяет три метрики «интересности» из ревью Claude в одну проверку с
человекочитаемыми предупреждениями. Это фильтр pass/warn, а не жёсткий
QA: он не блокирует сборку, а показывает, что именно стоит улучшить.
Окончательное решение всегда за человеком, который проходит карту.
"""

from dataclasses import dataclass
from typing import List

from .pacing import (
    backbone_nodes, evaluate as evaluate_pacing, ordered_node_ids,
)
from .scenes import scene_variety

SCENE_VARIETY_MIN = 0.6
MAX_SCENE_RUN = 2
PATH_RATIO_RANGE = (0.6, 0.8)


@dataclass
class CompositionIssue:
    path: str
    message: str

    def __str__(self):
        return "{}: {}".format(self.path, self.message)


def _scene_run(assignments, order) -> int:
    """Самая длинная серия одной и той же сцены в порядке обхода."""
    seq = [assignments.get(i) for i in order if assignments.get(i)]
    best = run = 0
    for i, name in enumerate(seq):
        run = run + 1 if i and name == seq[i - 1] else 1
        best = max(best, run)
    return best


def _route_metrics(graph: dict) -> dict:
    nodes = graph["nodes"]
    total = len(nodes)
    backbone = backbone_nodes(graph)
    path_ratio = len(backbone) / total if total else 0.0

    optional = {n["id"] for n in nodes if n.get("optional")}
    loops = [e for e in graph["edges"] if e.get("type") == "loop"]
    # add_loops не соединяет необязательные узлы, поэтому ищем иначе:
    # ответвление «с возвратом» — его родитель лежит на цикле.
    loop_nodes = set()
    for edge in loops:
        loop_nodes.update((edge["a"], edge["b"]))
    branch_return = any(
        any(nb in loop_nodes for nb in _neighbours(graph, opt))
        for opt in optional
    )
    junctions = sum(
        1 for n in nodes if len(_neighbours(graph, n["id"])) >= 3
    )
    return {
        "critical_path": float(len(backbone)),
        "path_ratio": round(path_ratio, 4),
        "loop_count": float(len(loops)),
        "branch_with_return": branch_return,
        "junctions": float(junctions),
    }


def _neighbours(graph: dict, node_id: str) -> List[str]:
    out = []
    for e in graph["edges"]:
        if e["a"] == node_id:
            out.append(e["b"])
        elif e["b"] == node_id:
            out.append(e["a"])
    return out


def evaluate_composition(blueprint: dict, chapter_name: str,
                         profile: str = "") -> dict:
    """Оценить композицию blueprint. Возвращает metrics и список issues."""
    issues: List[CompositionIssue] = []

    # 1. Ритм — EXISTS в pacing.py.
    pacing = evaluate_pacing(blueprint, profile)
    for warning in pacing["warnings"]:
        issues.append(CompositionIssue(
            "ритм",
            warning + ". Добавьте combat-комнату или ослабьте профиль",
        ))

    # 2. Разнообразие сцен и ролей.
    assignments = blueprint.get("scene_assignments", {})
    order = ordered_node_ids(blueprint["graph"])
    variety = scene_variety(assignments)
    scene_run = _scene_run(assignments, order)
    roles = {n["id"]: n.get("type", "?") for n in blueprint["graph"]["nodes"]}
    role_variety = round(
        len(set(roles.values())) / max(1, len(roles)), 4
    )
    if variety < SCENE_VARIETY_MIN:
        issues.append(CompositionIssue(
            "разнообразие",
            "сцен {:.2f} < {:.2f} — карта может выглядеть однообразно; "
            "раздайте комнатам разные сцены".format(variety, SCENE_VARIETY_MIN)
        ))
    if scene_run > MAX_SCENE_RUN:
        issues.append(CompositionIssue(
            "разнообразие",
            "одна сцена повторяется {} раза подряд — чередуйте сцены"
            .format(scene_run)
        ))

    # 3. Структура маршрута.
    route = _route_metrics(blueprint["graph"])
    low, high = PATH_RATIO_RANGE
    if not low <= route["path_ratio"] <= high:
        issues.append(CompositionIssue(
            "маршрут",
            "критический путь {:.0%} комнат вне диапазона {:.0%}–{:.0%}; "
            "нужна развилка или цикл".format(
                route["path_ratio"], low, high)
        ))
    # Карта без необязательных комнат линейна по замыслу — не ругаем её.
    has_optional = any(n.get("optional") for n in blueprint["graph"]["nodes"])
    if (has_optional and len(blueprint["graph"]["nodes"]) >= 8
            and not route["branch_with_return"]):
        issues.append(CompositionIssue(
            "маршрут",
            "нет развилки с возвратом на карте из {} комнат — "
            "добавьте цикл к боковой комнате".format(
                len(blueprint["graph"]["nodes"]))
        ))

    return {
        "chapter": chapter_name,
        "profile": pacing["profile"],
        "passed": not issues,
        "issues": [{"path": i.path, "message": i.message} for i in issues],
        "metrics": {
            "rhythm": pacing["metrics"],
            "variety": {
                "scene_variety": variety,
                "role_variety": role_variety,
                "scene_run": float(scene_run),
            },
            "route": route,
        },
    }
