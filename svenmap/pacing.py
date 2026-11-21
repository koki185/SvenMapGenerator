"""Пейсинг-профили и метрики ритма (P3.1).

Профиль задаёт шаблон последовательности ролей комнат и ограничения:
сколько боевых комнат подряд допустимо, как часто нужна передышка и
какая доля боевых комнат считается нормой. Роли выводятся из типов узлов
топологии — генерацию менять не нужно.

Метрики — фильтр pass/warn, а не целевая функция. Человек всё равно
проходит карту и решает, скучно ли в ней.
"""

from collections import deque
import json
import os
from typing import Dict, List

_PROFILES_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "pacing.json",
)
_CACHE: Dict[str, dict] = {}

# Тип узла -> роль пейсинга. Закрытый словарь, как и в campaign_schema.
ROLE_BY_TYPE = {
    "spawn": "intro",
    "hub": "intro",
    "corridor": "corridor",
    "transition": "corridor",
    "lab": "puzzle",
    "storage": "rest",
    "combat": "combat",
    "arena": "finale",
    "secret": "secret",
    "objective": "reward",
}
REST_ROLES = ("rest", "reward", "secret")


def load_profiles(path: str = "") -> Dict[str, dict]:
    """Загрузить профили из pacing.json (кэшируется)."""
    path = path or _PROFILES_PATH
    if path not in _CACHE:
        with open(path, encoding="utf-8") as f:
            _CACHE[path] = json.load(f)
    return _CACHE[path]


def profile_names() -> tuple:
    return tuple(sorted(load_profiles()))


def default_pacing(rooms: int) -> str:
    """Профиль по размеру главы, если модель его не указала."""
    if rooms <= 7:
        return "short_6"
    if rooms >= 10:
        return "dense_10"
    return "standard_8"


def _adjacency(graph: dict) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {n["id"]: [] for n in graph["nodes"]}
    for edge in graph["edges"]:
        a, b = edge["a"], edge["b"]
        out.setdefault(a, []).append(b)
        out.setdefault(b, []).append(a)
    return out


def _backbone(graph: dict) -> List[str]:
    """Кратчайший путь spawn -> goal по рёбрам графа."""
    adj = _adjacency(graph)
    start, goal = graph.get("start"), graph.get("goal")
    if start not in adj or goal not in adj:
        return list(adj)
    dist = {start: 0}
    prev = {}
    queue = deque([start])
    while queue:
        current = queue.popleft()
        for neighbour in adj.get(current, []):
            if neighbour in dist:
                continue
            dist[neighbour] = dist[current] + 1
            prev[neighbour] = current
            queue.append(neighbour)
    if goal not in dist:
        return list(adj)
    path = [goal]
    while path[-1] != start:
        path.append(prev[path[-1]])
    return list(reversed(path))


def role_by_node(graph: dict) -> Dict[str, str]:
    """Роль пейсинга для каждого узла (нужна сценам и валидатору)."""
    return {
        n["id"]: ROLE_BY_TYPE.get(n.get("type", ""), "rest")
        for n in graph["nodes"]
    }


def backbone_nodes(graph: dict) -> List[str]:
    """Узлы кратчайшего пути start → goal (публичная обёртка)."""
    return _backbone(graph)


def ordered_node_ids(graph: dict) -> List[str]:
    """Порядок обхода: backbone, затем ветки/секреты."""
    backbone = _backbone(graph)
    rest = [n["id"] for n in graph["nodes"] if n["id"] not in backbone]
    return backbone + rest


def ordered_roles(graph: dict) -> List[str]:
    """Роли комнат в порядке прохождения: backbone, затем ветки/секреты."""
    roles = role_by_node(graph)
    return [roles[i] for i in ordered_node_ids(graph) if i in roles]


def rhythm_metrics(roles: List[str]) -> Dict[str, float]:
    """Три метрики ритма: доля боевых, серия подряд, расстояние до передышки."""
    if not roles:
        return {"combat_share": 0.0, "max_combat_run": 0,
                "rest_gap": 0, "role_variety": 0.0}

    # Финал (арена босса) — тоже бой, иначе доля боевых занижается.
    combat_roles = ("combat", "finale")
    combat_share = sum(r in combat_roles for r in roles) / len(roles)

    max_run = run = 0
    for role in roles:
        run = run + 1 if role in combat_roles else 0
        max_run = max(max_run, run)

    # Старт и финал — границы, а не «дорога без передышки».
    gap = max_gap = 0
    for role in roles:
        if role in ("intro", "finale"):
            continue
        if role in REST_ROLES:
            gap = 0
        else:
            gap += 1
            max_gap = max(max_gap, gap)

    return {
        "combat_share": round(combat_share, 4),
        "max_combat_run": float(max_run),
        "rest_gap": float(max_gap),
        "role_variety": round(len(set(roles)) / len(roles), 4),
    }


def evaluate(blueprint: dict, profile_name: str) -> Dict:
    """Оценить ритм blueprint по профилю. Возвращает метрики и warn-список."""
    profiles = load_profiles()
    if profile_name not in profiles:
        profile_name = default_pacing(
            len(blueprint["spatial"]["areas"])
        )
    profile = profiles[profile_name]
    roles = ordered_roles(blueprint["graph"])
    metrics = rhythm_metrics(roles)
    warnings: List[str] = []

    low, high = profile["combat_share"]
    share = metrics["combat_share"]
    if share < low:
        warnings.append(
            "доля боевых комнат {:.0%} ниже порога профиля {} ({:.0%}–{:.0%})"
            .format(share, profile_name, low, high)
        )
    elif share > high:
        warnings.append(
            "доля боевых комнат {:.0%} выше порога профиля {} ({:.0%}–{:.0%})"
            .format(share, profile_name, low, high)
        )

    if metrics["max_combat_run"] > profile["max_combat_in_row"]:
        warnings.append(
            "боевых комнат подряд {} — больше допустимых {}"
            .format(int(metrics["max_combat_run"]), profile["max_combat_in_row"])
        )
    if metrics["rest_gap"] > profile["min_rest_every"]:
        warnings.append(
            "передышка только каждые {} комнат — реже, чем нужно ({})"
            .format(int(metrics["rest_gap"]), profile["min_rest_every"])
        )

    return {
        "profile": profile_name,
        "roles": roles,
        "metrics": metrics,
        "warnings": warnings,
        "passed": not warnings,
    }
