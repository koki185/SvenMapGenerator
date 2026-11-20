"""Новый pipeline проектирования уровня (SvenMapGenerator 2.0).

PR-1: генерация топологии — граф, зоны, метрики. Геометрия пока не строится.
Legacy-планировщик в svenmap/planner.py остаётся рабочим.
"""

from .adapters import blueprint_to_level_spec
from .architecture import (
    apply_shapes, candidates_for, is_connected, make_l, make_rect,
    make_t, make_u, rotate_shape,
)
from .models import (
    AreaType, EdgeType, Footprint, SpatialArea, SpatialConnection,
    SpatialLayout, TopologyEdge, TopologyGraph, TopologyNode, VerticalConnector,
    Zone, validate_topology,
)
from .pipeline import BlueprintConfig, generate_blueprint
from .spatial import SpatialConfig, place_spatial
from .topology import TopologyConfig, generate_topology

__all__ = [
    "AreaType", "EdgeType", "TopologyEdge", "TopologyGraph",
    "TopologyNode", "Zone", "validate_topology",
    "Footprint", "SpatialArea", "SpatialConnection", "SpatialLayout",
    "TopologyConfig", "generate_topology",
    "SpatialConfig", "place_spatial",
    "BlueprintConfig", "generate_blueprint",
    "make_rect", "make_l", "make_t", "make_u", "rotate_shape",
    "is_connected", "candidates_for", "apply_shapes",
    "VerticalConnector",
    "blueprint_to_level_spec",
]
