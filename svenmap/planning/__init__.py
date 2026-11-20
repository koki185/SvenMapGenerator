"""Новый pipeline проектирования уровня (SvenMapGenerator 2.0).

PR-1: генерация топологии — граф, зоны, метрики. Геометрия пока не строится.
Legacy-планировщик в svenmap/planner.py остаётся рабочим.
"""

from .models import (
    AreaType, EdgeType, TopologyEdge, TopologyGraph, TopologyNode,
    Zone, validate_topology,
)
from .topology import TopologyConfig, generate_topology

__all__ = [
    "AreaType", "EdgeType", "TopologyEdge", "TopologyGraph",
    "TopologyNode", "Zone", "validate_topology",
    "TopologyConfig", "generate_topology",
]
