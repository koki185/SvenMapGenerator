"""Новый pipeline PR-1 + PR-2: topology -> spatial blueprint."""

from dataclasses import dataclass, field
from typing import Dict

from .architecture import apply_shapes
from .models import TopologyGraph
from .spatial import SpatialConfig, place_spatial
from .topology import TopologyConfig, generate_topology
from .topology_metrics import evaluate as evaluate_topology


@dataclass
class BlueprintConfig:
    seed: int = 42
    node_count: int = 10
    branch_count: int = 2
    loop_count: int = 2
    secret_count: int = 2
    name: str = ""
    spatial: SpatialConfig = field(default_factory=SpatialConfig)


def generate_blueprint(config: BlueprintConfig) -> Dict:
    graph: TopologyGraph = generate_topology(TopologyConfig(
        seed=config.seed,
        node_count=config.node_count,
        branch_count=config.branch_count,
        loop_count=config.loop_count,
        secret_count=config.secret_count,
        name=config.name,
    ))
    layout = place_spatial(graph, config.spatial, seed=graph.seed)
    shapes = apply_shapes(graph, layout, seed=graph.seed)
    realized = {(c.a, c.b) for c in layout.connections}
    realized |= {(b, a) for a, b in realized}
    missing = [
        {"a": e.a, "b": e.b, "type": e.type}
        for e in graph.edges if (e.a, e.b) not in realized
    ]
    indirect = [
        {"a": c.a, "b": c.b, "type": c.type}
        for c in layout.connections if not c.direct
    ]
    return {
        "graph": graph.to_dict(),
        "spatial": layout.to_dict(),
        "shapes": shapes,
        "topology_metrics": evaluate_topology(graph),
        "unrealized_edges": missing,
        "indirect_edges": indirect,
    }
