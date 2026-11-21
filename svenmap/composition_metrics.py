"""Сводка метрик композиции для отчётов (P3.0).

Метрики topology/spatial считаются в planning/pipeline.py. Здесь они
собираются в плоский словарь, пригодный для QA-отчёта и будущего
валидатора композиции (P3.3) и авто выбора seed (P3.4).

Важно: это не целевая функция, а фильтр pass/warn. Автовыбор по
максимальному score уводит карты в усреднённое «всё одинаково».
"""

from collections import Counter
from typing import Dict


def summarize(blueprint: dict) -> Dict[str, float]:
    """Плоская сводка метрик и фактов композиции blueprint."""
    areas = blueprint["spatial"]["areas"]
    topology = blueprint.get("topology_metrics", {})
    spatial = blueprint.get("spatial_metrics", {})

    shape_counts = Counter(a.get("shape", "rect") for a in areas)
    floors = max((a.get("floor", 0) for a in areas), default=0) + 1

    summary = {
        # Итоговые оценки планировщика.
        "topology_score": topology.get("score", 0.0),
        "spatial_score": spatial.get("score", 0.0),
        # Структура маршрута.
        "cycle_count": topology.get("cycle_count", 0.0),
        "route_stretch": topology.get("route_stretch", 0.0),
        "branch_ratio": topology.get("branch_ratio", 0.0),
        "branch_depth": topology.get("branch_depth", 0.0),
        "route_choice": topology.get("route_choice", 0.0),
        # Пространственная композиция.
        "adjacency": spatial.get("adjacency", 0.0),
        "compactness": spatial.get("compactness", 0.0),
        "zone_clustering": spatial.get("zone_clustering", 0.0),
        "spatial_variety": spatial.get("spatial_variety", 0.0),
        # Факты, доступные уже сейчас.
        "shape_variety": round(
            len(shape_counts) / max(1, len(areas)), 4
        ),
        "indirect_edges": float(len(blueprint.get("indirect_edges", []))),
        "unrealized_edges": float(len(blueprint.get("unrealized_edges", []))),
        "floors": float(floors),
    }
    for shape, count in sorted(shape_counts.items()):
        summary["shape_" + shape] = float(count)
    return summary
