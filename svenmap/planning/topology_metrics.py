"""Метрики «интересности» топологии (PR-1).

Веса — стартовая эвристика из ревью, а не истина. Их нужно калибровать
после генерации десятков seed. Жёсткие ограничения живут в validate_topology,
а не здесь.
"""

from collections import deque
from typing import Dict

from .models import TopologyGraph, shortest_path_length


def loop_density(graph: TopologyGraph) -> float:
    vertices = max(1, graph.node_count)
    return min(1.0, graph.cycle_count / max(1.0, vertices / 4.0))


def branch_ratio(graph: TopologyGraph) -> float:
    if not graph.nodes:
        return 0.0
    optional = sum(1 for n in graph.nodes.values() if n.optional)
    return optional / graph.node_count


def _distance_map(graph, start):
    dist = {start: 0}
    queue = deque([start])
    while queue:
        current = queue.popleft()
        for neighbour in graph.neighbours(current):
            if neighbour in dist:
                continue
            dist[neighbour] = dist[current] + 1
            queue.append(neighbour)
    return dist


def route_stretch(graph: TopologyGraph) -> float:
    """Отношение самого длинного разумного маршрута к кратчайшему."""
    shortest = shortest_path_length(graph, graph.start, graph.goal)
    if not shortest:
        return 1.0
    dist = _distance_map(graph, graph.start)
    farthest = max(
        d for node, d in dist.items()
        if not graph.nodes[node].optional
    )
    return min(3.0, farthest / float(shortest))


def branch_depth(graph: TopologyGraph) -> float:
    mandatory = [
        n.id for n in graph.nodes.values() if not n.optional
    ]
    if not mandatory:
        return 0.0
    best = {}
    for node_id in mandatory:
        dist = _distance_map(graph, node_id)
        for other in dist:
            best[other] = min(best.get(other, 10 ** 6), dist[other])
    depths = [
        best[n.id] for n in graph.nodes.values()
        if n.optional and n.id in best
    ]
    return float(max(depths)) if depths else 0.0


def route_choice(graph: TopologyGraph) -> float:
    if not graph.nodes:
        return 0.0
    junctions = sum(
        1 for node in graph.nodes.values()
        if len(graph.neighbours(node.id)) >= 3
        and node.id not in (graph.start, graph.goal)
    )
    return min(1.0, junctions / max(1.0, graph.node_count / 5.0))


def evaluate(graph: TopologyGraph) -> Dict[str, float]:
    stretch = route_stretch(graph)
    depth = branch_depth(graph)
    stretch_quality = 1.0 - min(1.0, abs(stretch - 1.4) / 1.6)
    depth_quality = 1.0 - min(1.0, abs(depth - 2.0) / 3.0)

    metrics = {
        "cycle_count": float(graph.cycle_count),
        "loop_density": loop_density(graph),
        "branch_ratio": branch_ratio(graph),
        "route_stretch": stretch,
        "branch_depth": depth,
        "route_choice": route_choice(graph),
    }
    score = (
        0.25 * metrics["loop_density"]
        + 0.20 * metrics["branch_ratio"]
        + 0.20 * stretch_quality
        + 0.20 * metrics["route_choice"]
        + 0.15 * depth_quality
    )
    metrics["score"] = round(score, 4)
    return {k: round(v, 4) for k, v in metrics.items()}
