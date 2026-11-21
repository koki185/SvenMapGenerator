"""Новый pipeline PR-1 + PR-2: topology -> spatial blueprint."""

from dataclasses import dataclass, field
from typing import Dict

from .architecture import apply_shapes
from .models import TopologyGraph, VerticalConnector
from .spatial import SpatialConfig, place_spatial
from .spatial_metrics import evaluate_spatial
from .topology import TopologyConfig, generate_topology
from .topology_metrics import evaluate as evaluate_topology
from ..validator3d import validate_vertical_reachability


@dataclass
class BlueprintConfig:
    seed: int = 42
    node_count: int = 10
    branch_count: int = 2
    loop_count: int = 2
    secret_count: int = 2
    name: str = ""
    floors: int = 1
    spatial: SpatialConfig = field(default_factory=SpatialConfig)


def _landing(area):
    if area.cells:
        cx, cy = min(area.cells)
        return (area.x + cx, area.y + cy)
    return (area.x + area.w // 2, area.y + area.h // 2)


def add_vertical_layer(graph, layout, floors: int) -> None:
    """Поднять одну ветку на второй этаж и соединить лестницей."""
    if floors < 2:
        return
    upper = next((n for n in graph.nodes.values()
                  if n.id.startswith("b")), None)
    if upper is None or upper.id not in layout.areas:
        return
    parent_edge = next((e for e in graph.edges if e.b == upper.id), None)
    if parent_edge is None:
        return
    area = layout.areas[upper.id]
    area.floor = 1
    # GoldSrc CSG даёт LEAK, если пол второго этажа лежит точно поверх
    # потолка первого. Разводим крылья по XY; связь — через коннектор.
    area.x = 100
    parent = layout.areas.get(parent_edge.a)
    if parent is None:
        return
    # Обычные порталы в новом крыле не нужны: переход идёт через
    # VerticalConnector/телепорт. Иначе в Blueprint остаются порталы
    # со старыми координатами.
    layout.connections = [
        c for c in layout.connections
        if c.a != upper.id and c.b != upper.id
    ]
    layout.vertical_connectors.append(VerticalConnector(
        id="stairs_" + upper.id,
        type="stairs",
        area_a=parent_edge.a,
        area_b=upper.id,
        floor_a=0,
        floor_b=1,
        height_delta=128,
        landing_a=_landing(parent),
        landing_b=_landing(area),
    ))


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
    add_vertical_layer(graph, layout, config.floors)
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
        "spatial_metrics": evaluate_spatial(graph, layout),
        "vertical_qa": validate_vertical_reachability(graph, layout),
        "unrealized_edges": missing,
        "indirect_edges": indirect,
    }
