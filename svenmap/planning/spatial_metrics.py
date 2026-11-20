"""Метрики пространственной композиции (PR-2)."""

from typing import Dict

from .models import SpatialArea, SpatialLayout, TopologyGraph


def rect_touch(a: SpatialArea, b: SpatialArea, spacing: int = 1) -> bool:
    """Соседние ли прямоугольники с зазором не больше spacing."""
    overlap_x = min(a.x + a.w, b.x + b.w) - max(a.x, b.x)
    overlap_y = min(a.y + a.h, b.y + b.h) - max(a.y, b.y)
    if overlap_x >= 0 and abs((a.y + a.h) - b.y) <= spacing:
        return True
    if overlap_x >= 0 and abs((b.y + b.h) - a.y) <= spacing:
        return True
    if overlap_y >= 0 and abs((a.x + a.w) - b.x) <= spacing:
        return True
    if overlap_y >= 0 and abs((b.x + b.w) - a.x) <= spacing:
        return True
    return False


def adjacency_ratio(graph: TopologyGraph, layout: SpatialLayout) -> float:
    if not graph.edges:
        return 1.0
    realized = 0
    for edge in graph.edges:
        a = layout.areas.get(edge.a)
        b = layout.areas.get(edge.b)
        if a and b and rect_touch(a, b):
            realized += 1
    return realized / len(graph.edges)


def compactness(layout: SpatialLayout, target: float = 0.65) -> float:
    if not layout.areas:
        return 0.0
    occupied = sum(a.w * a.h for a in layout.areas.values())
    min_x = min(a.x for a in layout.areas.values())
    max_x = max(a.x + a.w for a in layout.areas.values())
    min_y = min(a.y for a in layout.areas.values())
    max_y = max(a.y + a.h for a in layout.areas.values())
    box = max(1, (max_x - min_x) * (max_y - min_y))
    density = occupied / box
    return max(0.0, 1.0 - min(1.0, abs(density - target) / target))


def zone_clustering(graph: TopologyGraph, layout: SpatialLayout) -> float:
    groups: Dict[str, list] = {}
    for node in graph.nodes.values():
        if node.id in layout.areas:
            groups.setdefault(node.zone_id, []).append(node.id)
    if not groups:
        return 0.0
    penalties = []
    for zone_id, ids in groups.items():
        if len(ids) < 2:
            continue
        cx = sum(layout.areas[i].x + layout.areas[i].w / 2 for i in ids) / len(ids)
        cy = sum(layout.areas[i].y + layout.areas[i].h / 2 for i in ids) / len(ids)
        span = sum(
            ((layout.areas[i].x + layout.areas[i].w / 2 - cx) ** 2
             + (layout.areas[i].y + layout.areas[i].h / 2 - cy) ** 2) ** 0.5
            for i in ids
        ) / len(ids)
        penalties.append(min(1.0, span / 40.0))
    return 1.0 - (sum(penalties) / len(penalties)) if penalties else 1.0


def spatial_variety(layout: SpatialLayout) -> float:
    if len(layout.areas) < 2:
        return 0.0
    widths = {a.w for a in layout.areas.values()}
    heights = {a.h for a in layout.areas.values()}
    return min(1.0, (len(widths) + len(heights)) / 8.0)


def evaluate_spatial(graph: TopologyGraph, layout: SpatialLayout) -> Dict[str, float]:
    metrics = {
        "adjacency": adjacency_ratio(graph, layout),
        "compactness": compactness(layout),
        "zone_clustering": zone_clustering(graph, layout),
        "spatial_variety": spatial_variety(layout),
    }
    score = (
        0.35 * metrics["adjacency"]
        + 0.25 * metrics["compactness"]
        + 0.25 * metrics["zone_clustering"]
        + 0.15 * metrics["spatial_variety"]
    )
    metrics["score"] = round(score, 4)
    return {k: round(v, 4) for k, v in metrics.items()}
