"""Генерация топологии уровня: backbone, ветки, циклы, секреты.

Это PR-1: только граф и его проверки. Координат и brush здесь нет.
"""

from dataclasses import dataclass
from typing import List, Tuple

from .models import (
    TopologyEdge, TopologyGraph, TopologyNode, Zone,
    reachable, shortest_path_length, validate_topology,
)
from .rng import make_rng

ZONE_PURPOSES = {
    "z_entry": "entry_security",
    "z_research": "research",
    "z_combat": "combat_arena",
    "z_logistics": "logistics",
}

NODE_ZONE = {
    "spawn": "z_entry",
    "hub": "z_entry",
    "corridor": "z_entry",
    "lab": "z_research",
    "objective": "z_research",
    "storage": "z_logistics",
    "combat": "z_combat",
    "arena": "z_combat",
    "secret": "z_research",
    "transition": "z_entry",
}

BACKBONE_TYPES = ("corridor", "lab", "storage", "combat", "lab", "corridor")
BRANCH_TYPES = ("storage", "lab", "corridor")


@dataclass
class TopologyConfig:
    seed: int = 1
    node_count: int = 10
    branch_count: int = 2
    loop_count: int = 2
    secret_count: int = 2
    name: str = ""


def _create_zones(graph: TopologyGraph):
    for zone_id, purpose in ZONE_PURPOSES.items():
        graph.zones[zone_id] = Zone(id=zone_id, purpose=purpose)


def create_backbone(graph: TopologyGraph, config: TopologyConfig, rng) -> List[str]:
    interior = max(1, config.node_count - 2)
    ids = ["spawn"] + ["n{}".format(i + 1) for i in range(interior)] + ["goal"]

    for index, node_id in enumerate(ids):
        if node_id == "spawn":
            node_type, role = "spawn", "start"
        elif node_id == "goal":
            node_type, role = "arena", "final"
        elif index == 1:
            node_type, role = "hub", "hub"
        else:
            node_type = BACKBONE_TYPES[(index - 2) % len(BACKBONE_TYPES)]
            role = "normal"
        graph.add_node(TopologyNode(
            id=node_id,
            type=node_type,
            zone_id=NODE_ZONE[node_type],
            role=role,
        ))

    for a, b in zip(ids, ids[1:]):
        graph.add_edge(TopologyEdge(a=a, b=b, type="main", mandatory=True))
    return ids


def add_branches(graph: TopologyGraph, config: TopologyConfig, rng) -> None:
    backbone = [
        n.id for n in graph.nodes.values()
        if n.id not in ("spawn", "goal") and not n.optional
    ]
    if not backbone:
        return
    for i in range(config.branch_count):
        parent = rng.choice(backbone)
        length = rng.choice((1, 2))
        prev = parent
        for j in range(length):
            node_id = "b{}_{}".format(i + 1, j)
            node_type = BRANCH_TYPES[(i + j) % len(BRANCH_TYPES)]
            graph.add_node(TopologyNode(
                id=node_id,
                type=node_type,
                zone_id=NODE_ZONE[node_type],
                role="optional_area",
                optional=True,
            ))
            graph.add_edge(TopologyEdge(
                a=prev, b=node_id, type="branch", mandatory=False
            ))
            prev = node_id


def _creates_bad_shortcut(graph: TopologyGraph, a: str, b: str) -> bool:
    before = shortest_path_length(graph, graph.start, graph.goal)
    graph.add_edge(TopologyEdge(a=a, b=b, type="loop", mandatory=False))
    after = shortest_path_length(graph, graph.start, graph.goal)
    # Удаляем временное ребро.
    graph.edges.pop()
    if before is None or after is None or before <= 2:
        return True
    return after < before * 0.6


def add_loops(graph: TopologyGraph, config: TopologyConfig, rng) -> None:
    candidates = [
        (a, b)
        for i, a in enumerate(graph.nodes)
        for b in list(graph.nodes)[i + 1:]
        if not graph.nodes[a].optional and not graph.nodes[b].optional
        and not graph.edge_exists(a, b)
    ]
    rng.shuffle(candidates)
    for a, b in candidates:
        if graph.cycle_count >= config.loop_count:
            break
        if _creates_bad_shortcut(graph, a, b):
            continue
        graph.add_edge(TopologyEdge(a=a, b=b, type="loop", mandatory=False))


def add_secrets(graph: TopologyGraph, config: TopologyConfig, rng) -> None:
    hosts = [
        n.id for n in graph.nodes.values()
        if n.id != graph.goal and not n.optional
    ]
    if not hosts:
        return
    for i in range(config.secret_count):
        parent = rng.choice(hosts)
        node_id = "secret_{}".format(i + 1)
        graph.add_node(TopologyNode(
            id=node_id,
            type="secret",
            zone_id="z_research",
            role="hidden",
            optional=True,
        ))
        graph.add_edge(TopologyEdge(
            a=parent, b=node_id, type="secret", mandatory=False
        ))


def assign_zones(graph: TopologyGraph) -> None:
    for node in graph.nodes.values():
        zone = graph.zones.get(node.zone_id)
        if zone and node.id not in zone.area_ids:
            zone.area_ids.append(node.id)


def generate_topology(config: TopologyConfig) -> TopologyGraph:
    rng = make_rng(config.seed, "topology")
    name = config.name or "sc_topo_{}".format(config.seed)
    graph = TopologyGraph(name=name, seed=config.seed)
    _create_zones(graph)
    create_backbone(graph, config, rng)
    # start/goal нужны уже на этапе циклов: add_loops проверяет,
    # не сокращает ли новое ребро маршрут.
    graph.start = "spawn"
    graph.goal = "goal"
    add_branches(graph, config, rng)
    add_loops(graph, config, rng)
    add_secrets(graph, config, rng)
    assign_zones(graph)

    errors = validate_topology(graph, target_cycles=config.loop_count)
    if errors:
        raise RuntimeError(
            "топология seed={} не прошла валидацию: {}".format(
                config.seed, "; ".join(errors)
            )
        )
    return graph
