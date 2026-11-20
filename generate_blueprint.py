"""PR-2 CLI: topology + размещение в пространстве -> Blueprint JSON/SVG."""

import argparse
import json
import os

from svenmap.planning import BlueprintConfig, generate_blueprint

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "blueprints")


def write_spatial_svg(blueprint, path):
    areas = blueprint["spatial"]["areas"]
    edges = blueprint["spatial"]["connections"]
    if not areas:
        return
    min_x = min(a["x"] for a in areas)
    min_y = min(a["y"] for a in areas)
    max_x = max(a["x"] + a["w"] for a in areas)
    max_y = max(a["y"] + a["h"] for a in areas)
    scale = min(900 / max(1, max_x - min_x), 600 / max(1, max_y - min_y))

    colors = {"main": "#4dff88", "branch": "#5aa9ff", "loop": "#ffd24d",
              "secret": "#ff6bd6"}
    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="700" '
        'viewBox="0 0 1000 700">',
        '<rect width="100%" height="100%" fill="#111418"/>',
    ]
    for edge in edges:
        a = next((x for x in areas if x["node_id"] == edge["a"]), None)
        b = next((x for x in areas if x["node_id"] == edge["b"]), None)
        if not a or not b:
            continue
        ax = 50 + (a["x"] + a["w"] / 2 - min_x) * scale
        ay = 50 + (a["y"] + a["h"] / 2 - min_y) * scale
        bx = 50 + (b["x"] + b["w"] / 2 - min_x) * scale
        by = 50 + (b["y"] + b["h"] / 2 - min_y) * scale
        lines.append(
            '<line x1="{:.1f}" y1="{:.1f}" x2="{:.1f}" y2="{:.1f}" '
            'stroke="{}" stroke-width="2"/>'.format(
                ax, ay, bx, by, colors.get(edge["type"], "#fff"))
        )
    for area in areas:
        x = 50 + (area["x"] - min_x) * scale
        y = 50 + (area["y"] - min_y) * scale
        cells = area.get("cells")
        if cells:
            for cx, cy in cells:
                lines.append(
                    '<rect x="{:.1f}" y="{:.1f}" width="{:.1f}" height="{:.1f}" '
                    'fill="#5aa9ff" fill-opacity="0.20" stroke="#5aa9ff" '
                    'stroke-width="0.5"/>'.format(
                        x + cx * scale, y + cy * scale,
                        max(1.0, scale - 0.5), max(1.0, scale - 0.5))
                )
        else:
            lines.append(
                '<rect x="{:.1f}" y="{:.1f}" width="{:.1f}" height="{:.1f}" '
                'fill="#5aa9ff" fill-opacity="0.18" stroke="#5aa9ff"/>'
                .format(x, y, area["w"] * scale, area["h"] * scale)
            )
        lines.append(
            '<text x="{:.1f}" y="{:.1f}" fill="#fff" font-family="sans-serif" '
            'font-size="10">{} [{}]</text>'.format(
                x + 2, y + 12, area["node_id"], area.get("shape", "rect"))
        )
    lines.append("</svg>")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--no-preview", action="store_true")
    args = parser.parse_args()

    os.makedirs(OUT, exist_ok=True)
    for seed in range(args.seed, args.seed + args.count):
        config = BlueprintConfig(seed=seed)
        blueprint = generate_blueprint(config)
        name = blueprint["graph"]["name"]
        json_path = os.path.join(OUT, name + ".json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(blueprint, f, ensure_ascii=False, indent=2)
        if not args.no_preview:
            svg_path = os.path.join(OUT, name + "_spatial.svg")
            write_spatial_svg(blueprint, svg_path)
        print("{}: areas={} links={} indirect={} spatial_score={}".format(
            name,
            len(blueprint["spatial"]["areas"]),
            len(blueprint["spatial"]["connections"]),
            len(blueprint["indirect_edges"]),
            blueprint["spatial"]["score"],
        ))


if __name__ == "__main__":
    main()
