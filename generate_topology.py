"""PR-1 CLI: сгенерировать топологию уровня и посмотреть её.

    python generate_topology.py --seed 42
    python generate_topology.py --seed 1 --count 100 --no-preview

Геометрия пока НЕ строится — только граф, зоны и метрики.
"""

import argparse
import json
import os
from collections import deque

from svenmap.planning import TopologyConfig, generate_topology
from svenmap.planning.topology_metrics import evaluate

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "topology")


def write_svg(graph, path):
    dist = {graph.start: 0}
    queue = deque([graph.start])
    while queue:
        current = queue.popleft()
        for neighbour in graph.neighbours(current):
            if neighbour not in dist:
                dist[neighbour] = dist[current] + 1
                queue.append(neighbour)

    layers = {}
    for node_id, depth in dist.items():
        layers.setdefault(depth, []).append(node_id)
    for node_id in graph.nodes:
        if node_id not in dist:
            layers.setdefault(99, []).append(node_id)

    positions = {}
    max_layer = max(layers) if layers else 0
    for depth in sorted(layers):
        row = sorted(layers[depth])
        for index, node_id in enumerate(row):
            x = 80 + depth * (820 / max(1, max_layer))
            y = 80 + index * (520 / max(1, len(row)))
            positions[node_id] = (x, y)

    colors = {
        "main": "#4dff88", "branch": "#5aa9ff", "loop": "#ffd24d",
        "secret": "#ff6bd6", "vertical": "#c77dff", "locked": "#888888",
    }
    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="680" '
        'viewBox="0 0 1000 680">',
        '<rect width="100%" height="100%" fill="#111418"/>',
        '<text x="20" y="28" fill="#ddd" font-family="sans-serif" '
        'font-size="16">{} (seed {})</text>'.format(graph.name, graph.seed),
    ]
    for edge in graph.edges:
        if edge.a not in positions or edge.b not in positions:
            continue
        x1, y1 = positions[edge.a]
        x2, y2 = positions[edge.b]
        color = colors.get(edge.type, "#ffffff")
        lines.append(
            '<line x1="{:.1f}" y1="{:.1f}" x2="{:.1f}" y2="{:.1f}" '
            'stroke="{}" stroke-width="2" stroke-opacity="0.8"/>'
            .format(x1, y1, x2, y2, color)
        )
    for node_id, (x, y) in positions.items():
        node = graph.nodes[node_id]
        fill = "#ff5252" if node_id == graph.goal else (
            "#4dff88" if node_id == graph.start else (
                "#ff6bd6" if node.type == "secret" else "#5aa9ff"))
        lines.append(
            '<circle cx="{:.1f}" cy="{:.1f}" r="15" fill="{}"/>'
            .format(x, y, fill)
        )
        lines.append(
            '<text x="{:.1f}" y="{:.1f}" fill="#fff" font-family="sans-serif" '
            'font-size="10" text-anchor="middle">{}</text>'
            .format(x, y + 4, node_id)
        )
    lines.append("</svg>")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--nodes", type=int, default=10)
    parser.add_argument("--branches", type=int, default=2)
    parser.add_argument("--loops", type=int, default=2)
    parser.add_argument("--secrets", type=int, default=2)
    parser.add_argument("--no-preview", action="store_true")
    args = parser.parse_args()

    os.makedirs(OUT, exist_ok=True)
    for seed in range(args.seed, args.seed + args.count):
        config = TopologyConfig(
            seed=seed,
            node_count=args.nodes,
            branch_count=args.branches,
            loop_count=args.loops,
            secret_count=args.secrets,
        )
        graph = generate_topology(config)
        metrics = evaluate(graph)
        json_path = os.path.join(OUT, "{}.json".format(graph.name))
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(
                {"graph": graph.to_dict(), "metrics": metrics},
                f, ensure_ascii=False, indent=2,
            )
        if not args.no_preview:
            svg_path = os.path.join(OUT, "{}.svg".format(graph.name))
            write_svg(graph, svg_path)
            print("{}: V={} E={} cycles={} score={} -> {}, {}".format(
                graph.name, graph.node_count, graph.edge_count,
                graph.cycle_count, metrics["score"],
                os.path.basename(json_path), os.path.basename(svg_path),
            ))
        else:
            print("{}: V={} E={} cycles={} score={}".format(
                graph.name, graph.node_count, graph.edge_count,
                graph.cycle_count, metrics["score"],
            ))


if __name__ == "__main__":
    main()
