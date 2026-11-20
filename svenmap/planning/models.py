"""Модели топологии уровня (PR-1).

Три важных правила из ревью GPT:
1. Узел топологии НЕ знает координат.
2. Ребро может быть main / branch / loop / secret / vertical.
3. Обязательные ограничения проверяются жёстко, а не через score.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional, Set, Tuple
from collections import deque

AreaType = Literal[
    "spawn", "corridor", "lab", "storage", "arena",
    "hub", "combat", "objective", "secret", "transition",
]

EdgeType = Literal[
    "main", "branch", "loop", "secret", "vertical", "locked", "one_way",
]


@dataclass
class Footprint:
    w: int
    h: int
    floor: int = 0
    shape: str = "rect"


@dataclass
class SpatialArea:
    node_id: str
    x: int
    y: int
    w: int
    h: int
    floor: int = 0
    # PR-3: форма комнаты. Для rect cells == None (используем x/y/w/h).
    shape: str = "rect"
    cells: Optional[Set[Tuple[int, int]]] = None


@dataclass
class SpatialConnection:
    a: str
    b: str
    type: EdgeType
    portal_a: Tuple[int, int]
    portal_b: Tuple[int, int]
    # False = комнаты не касаются, для связи нужен коридор (PR-3).
    direct: bool = True


@dataclass
class SpatialLayout:
    areas: Dict[str, SpatialArea] = field(default_factory=dict)
    connections: List[SpatialConnection] = field(default_factory=list)
    score: float = 0.0

    def to_dict(self) -> dict:
        return {
            "areas": [
                {
                    "node_id": a.node_id, "x": a.x, "y": a.y,
                    "w": a.w, "h": a.h, "floor": a.floor,
                    "shape": a.shape,
                    "cells": (
                        [list(c) for c in sorted(a.cells)]
                        if a.cells else None
                    ),
                }
                for a in self.areas.values()
            ],
            "connections": [
                {
                    "a": c.a, "b": c.b, "type": c.type,
                    "portal_a": list(c.portal_a),
                    "portal_b": list(c.portal_b),
                    "direct": c.direct,
                }
                for c in self.connections
            ],
            "score": round(self.score, 4),
        }


@dataclass
class Zone:
    id: str
    purpose: str
    area_ids: List[str] = field(default_factory=list)
    theme: Optional[str] = None
    floor: int = 0


@dataclass
class TopologyNode:
    id: str
    type: AreaType
    zone_id: str
    role: str = "normal"
    optional: bool = False
    min_size: Tuple[int, int] = (3, 3)
    floor: int = 0


@dataclass
class TopologyEdge:
    a: str
    b: str
    type: EdgeType
    mandatory: bool = True
    connector_id: Optional[str] = None


@dataclass
class TopologyGraph:
    name: str
    seed: int
    nodes: Dict[str, TopologyNode] = field(default_factory=dict)
    edges: List[TopologyEdge] = field(default_factory=list)
    zones: Dict[str, Zone] = field(default_factory=dict)
    start: str = ""
    goal: str = ""

    def add_node(self, node: TopologyNode):
        if node.id in self.nodes:
            raise ValueError("дублирующийся id узла: " + node.id)
        self.nodes[node.id] = node

    def add_edge(self, edge: TopologyEdge):
        key = _edge_key(edge.a, edge.b)
        if any(_edge_key(e.a, e.b) == key for e in self.edges):
            return False
        self.edges.append(edge)
        return True

    def edge_exists(self, a: str, b: str) -> bool:
        key = _edge_key(a, b)
        return any(_edge_key(e.a, e.b) == key for e in self.edges)

    def neighbours(self, node_id: str) -> List[str]:
        out = []
        for e in self.edges:
            if e.a == node_id:
                out.append(e.b)
            elif e.b == node_id:
                out.append(e.a)
        return out

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        return len(self.edges)

    @property
    def cycle_count(self) -> int:
        if not self.nodes:
            return 0
        return max(0, self.edge_count - self.node_count + 1)

    def to_dict(self) -> dict:
        return {
            "version": 2,
            "name": self.name,
            "seed": self.seed,
            "zones": [
                {
                    "id": z.id,
                    "purpose": z.purpose,
                    "area_ids": list(z.area_ids),
                    "theme": z.theme,
                    "floor": z.floor,
                }
                for z in self.zones.values()
            ],
            "nodes": [
                {
                    "id": n.id,
                    "type": n.type,
                    "zone_id": n.zone_id,
                    "role": n.role,
                    "optional": n.optional,
                    "min_size": list(n.min_size),
                    "floor": n.floor,
                }
                for n in self.nodes.values()
            ],
            "edges": [
                {
                    "a": e.a, "b": e.b, "type": e.type,
                    "mandatory": e.mandatory,
                    "connector_id": e.connector_id,
                }
                for e in self.edges
            ],
            "start": self.start,
            "goal": self.goal,
        }


def _edge_key(a: str, b: str) -> Tuple[str, str]:
    return (a, b) if a <= b else (b, a)


def reachable(graph: TopologyGraph, start: str,
              skip_optional: bool = False) -> Set[str]:
    """BFS по неориентированному графу."""
    if start not in graph.nodes:
        return set()
    seen = {start}
    queue = deque([start])
    while queue:
        current = queue.popleft()
        for neighbour in graph.neighbours(current):
            if neighbour in seen:
                continue
            node = graph.nodes.get(neighbour)
            if node is None:
                continue
            if skip_optional and node.optional:
                continue
            seen.add(neighbour)
            queue.append(neighbour)
    return seen


def shortest_path_length(graph: TopologyGraph, a: str, b: str) -> Optional[int]:
    if a not in graph.nodes or b not in graph.nodes:
        return None
    if a == b:
        return 0
    dist = {a: 0}
    queue = deque([a])
    while queue:
        current = queue.popleft()
        for neighbour in graph.neighbours(current):
            if neighbour in dist:
                continue
            dist[neighbour] = dist[current] + 1
            if neighbour == b:
                return dist[neighbour]
            queue.append(neighbour)
    return None


def validate_topology(graph: TopologyGraph,
                      target_cycles: int = 0) -> List[str]:
    """Жёсткие ограничения до пространственного размещения."""
    errors = []
    if graph.start not in graph.nodes:
        errors.append("нет стартового узла")
    if graph.goal not in graph.nodes:
        errors.append("нет целевого узла")
    if graph.start == graph.goal:
        errors.append("start и goal совпадают")

    for e in graph.edges:
        if e.a == e.b:
            errors.append("петля на узел: " + e.a)
        if e.a not in graph.nodes or e.b not in graph.nodes:
            errors.append("ребро ссылается на несуществующий узел")
    keys = [_edge_key(e.a, e.b) for e in graph.edges]
    if len(keys) != len(set(keys)):
        errors.append("дублирующиеся рёбра")

    for n in graph.nodes.values():
        if n.zone_id not in graph.zones:
            errors.append("узел {} вне зоны {}".format(n.id, n.zone_id))

    if not errors:
        mandatory = {
            n.id for n in graph.nodes.values() if not n.optional
        }
        seen = reachable(graph, graph.start)
        missing = mandatory - seen
        if missing:
            errors.append("недостижимые обязательные узлы: " + str(sorted(missing)))
        if graph.goal not in seen:
            errors.append("goal недостижим")

    for n in graph.nodes.values():
        if n.type == "secret" and not graph.neighbours(n.id):
            errors.append("секрет без соединения: " + n.id)

    if target_cycles and graph.cycle_count < target_cycles:
        errors.append(
            "мало циклов: {} < {}".format(graph.cycle_count, target_cycles)
        )
    return errors
