"""Размещение графа в пространстве через Beam Search (PR-2).

В отличие от legacy _place(), здесь размещается весь граф сразу,
а не «очередная комната рядом с родителем». Сохраняем несколько
перспективных раскладок и оцениваем каждую.
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple

from .models import (
    SpatialArea, SpatialConnection, SpatialLayout, TopologyGraph, TopologyNode,
)
from .rng import make_rng
from .spatial_metrics import evaluate_spatial, rect_touch

SIZE_BONUS = {
    "spawn": 2, "lab": 2, "arena": 2, "combat": 1,
    "storage": 1, "hub": 1, "corridor": 0, "secret": 0,
}


@dataclass
class SpatialConfig:
    beam_width: int = 10
    candidates_per_node: int = 20
    spacing: int = 1
    attempts: int = 8


def node_footprint(node: TopologyNode, rng) -> Tuple[int, int]:
    bonus = SIZE_BONUS.get(node.type, 1)
    w = rng.randint(node.min_size[0], node.min_size[0] + bonus)
    h = rng.randint(node.min_size[1], node.min_size[1] + bonus)
    return w, h


def _free(x, y, w, h, placed: Dict[str, SpatialArea], spacing: int) -> bool:
    for other in placed.values():
        if not (x + w + spacing <= other.x
                or x >= other.x + other.w + spacing
                or y + h + spacing <= other.y
                or y >= other.y + other.h + spacing):
            return False
    return True


def _candidates(w, h, neighbours: List[SpatialArea], spacing: int,
                limit: int, rng) -> List[Tuple[int, int]]:
    found = []
    for other in neighbours:
        for y in range(other.y - h + 1, other.y + other.h):
            found.append((other.x + other.w + spacing, y))
            found.append((other.x - w - spacing, y))
        for x in range(other.x - w + 1, other.x + other.w):
            found.append((x, other.y + other.h + spacing))
            found.append((x, other.y - h - spacing))
    found = list(dict.fromkeys(found))
    rng.shuffle(found)
    return found[:limit]


def _fallback_candidates(w, h, placed: Dict[str, SpatialArea], spacing: int,
                         limit: int, rng) -> List[Tuple[int, int]]:
    """Если рядом с соседями нет места — ищем свободное место в карте."""
    if placed:
        min_x = min(a.x for a in placed.values()) - 20
        max_x = max(a.x + a.w for a in placed.values()) + 20
        min_y = min(a.y for a in placed.values()) - 20
        max_y = max(a.y + a.h for a in placed.values()) + 20
    else:
        min_x = min_y = 0
        max_x = max_y = 40
    steps = 4
    found = []
    for x in range(min_x, max_x, steps):
        for y in range(min_y, max_y, steps):
            if _free(x, y, w, h, placed, spacing):
                found.append((x, y))
    rng.shuffle(found)
    return found[:limit]


def _order_nodes(graph: TopologyGraph) -> List[str]:
    """BFS от старта: родитель всегда размещён раньше ребёнка."""
    from collections import deque

    order = [graph.start]
    seen = {graph.start}
    queue = deque([graph.start])
    while queue:
        current = queue.popleft()
        for neighbour in graph.neighbours(current):
            if neighbour not in seen:
                seen.add(neighbour)
                order.append(neighbour)
                queue.append(neighbour)
    for node_id in graph.nodes:
        if node_id not in seen:
            order.append(node_id)
    return order


def _portal(a: SpatialArea, b: SpatialArea) -> Tuple[Tuple[int, int], Tuple[int, int]]:
    cx = (max(a.x, b.x) + min(a.x + a.w, b.x + b.w)) // 2
    cy = (max(a.y, b.y) + min(a.y + a.h, b.y + b.h)) // 2
    return ((cx, cy), (cx, cy))


def _quality(graph: TopologyGraph, areas: Dict[str, SpatialArea]) -> float:
    """Оценка с явным бонусом за обязательные связи."""
    base = evaluate_spatial(graph, SpatialLayout(areas=areas))["score"]
    mandatory = [e for e in graph.edges if e.mandatory]
    if not mandatory:
        return base
    realized = 0
    for edge in mandatory:
        a, b = areas.get(edge.a), areas.get(edge.b)
        if a and b and rect_touch(a, b):
            realized += 1
    return base + 0.5 * (realized / len(mandatory))


def _realize(graph: TopologyGraph, areas: Dict[str, SpatialArea]) -> SpatialLayout:
    layout = SpatialLayout(areas=dict(areas))
    for edge in graph.edges:
        a, b = areas.get(edge.a), areas.get(edge.b)
        if not a or not b:
            continue
        direct = rect_touch(a, b)
        if direct:
            pa, pb = _portal(a, b)
        else:
            pa = (a.x + a.w // 2, a.y + a.h // 2)
            pb = (b.x + b.w // 2, b.y + b.h // 2)
        layout.connections.append(SpatialConnection(
            a=edge.a, b=edge.b, type=edge.type,
            portal_a=pa, portal_b=pb, direct=direct,
        ))
    layout.score = evaluate_spatial(graph, layout)["score"]
    return layout


def _mandatory_realized(graph: TopologyGraph, layout: SpatialLayout) -> bool:
    done = {(c.a, c.b) for c in layout.connections}
    done |= {(b, a) for a, b in done}
    for edge in graph.edges:
        if edge.mandatory and (edge.a, edge.b) not in done:
            return False
    return True


def _repair_mandatory(graph: TopologyGraph, areas: Dict[str, SpatialArea],
                      spacing: int, rng) -> Dict[str, SpatialArea]:
    """Локальная починка: подвинуть комнату ради обязательной связи."""
    def realized_count(current):
        count = 0
        for edge in graph.edges:
            if not edge.mandatory:
                continue
            a, b = current.get(edge.a), current.get(edge.b)
            if a and b and rect_touch(a, b):
                count += 1
        return count

    current = dict(areas)
    for _pass in range(3):
        changed = False
        for edge in graph.edges:
            if not edge.mandatory:
                continue
            a, b = current.get(edge.a), current.get(edge.b)
            if not a or not b or rect_touch(a, b):
                continue
            before = realized_count(current)
            for node_id, other in ((edge.b, a), (edge.a, b)):
                w, h = current[node_id].w, current[node_id].h
                trial = dict(current)
                del trial[node_id]
                for x, y in _candidates(w, h, [other], spacing, 24, rng):
                    if not _free(x, y, w, h, trial, spacing):
                        continue
                    moved = dict(trial)
                    moved[node_id] = SpatialArea(
                        node_id=node_id, x=x, y=y, w=w, h=h
                    )
                    if realized_count(moved) > before:
                        current = moved
                        changed = True
                        break
                if changed:
                    break
            if changed:
                break
        if not changed:
            break
    return current


def place_spatial(graph: TopologyGraph, config: SpatialConfig = None,
                  seed: int = None) -> SpatialLayout:
    config = config or SpatialConfig()
    seed = graph.seed if seed is None else seed
    order = _order_nodes(graph)
    best = None

    for attempt in range(config.attempts):
        rng = make_rng(seed, "spatial:{}".format(attempt))
        sizes = {}
        for node_id in order:
            w, h = node_footprint(graph.nodes[node_id], rng)
            sizes[node_id] = (w, h)

        states = [({graph.start: SpatialArea(
            node_id=graph.start, x=0, y=0,
            w=sizes[graph.start][0], h=sizes[graph.start][1])}, 0.0)]

        for node_id in order[1:]:
            w, h = sizes[node_id]
            next_states = []
            for areas, _old_score in states:
                neighbours = [
                    areas[nid] for nid in graph.neighbours(node_id)
                    if nid in areas
                ]
                raw = _candidates(w, h, neighbours, config.spacing,
                                  config.candidates_per_node, rng)
                valid = [
                    (x, y) for x, y in raw
                    if _free(x, y, w, h, areas, config.spacing)
                ]
                if not valid:
                    valid = _fallback_candidates(
                        w, h, areas, config.spacing,
                        config.candidates_per_node, rng,
                    )
                for x, y in valid:
                    trial = dict(areas)
                    trial[node_id] = SpatialArea(
                        node_id=node_id, x=x, y=y, w=w, h=h
                    )
                    score = _quality(graph, trial)
                    next_states.append((trial, score))
            if not next_states:
                break
            next_states.sort(key=lambda item: item[1], reverse=True)
            states = next_states[:config.beam_width]

        for areas, _score in states:
            layout = _realize(graph, areas)
            quality = _quality(graph, areas)
            if best is None or quality > _quality(graph, best.areas):
                best = layout
            if _mandatory_realized(graph, layout):
                return layout

    if best is None:
        raise RuntimeError("не удалось разместить граф")

    repaired = _repair_mandatory(
        graph, best.areas, config.spacing,
        make_rng(seed, "spatial:repair"),
    )
    candidate = _realize(graph, repaired)
    if _mandatory_realized(graph, candidate):
        return candidate
    return best
