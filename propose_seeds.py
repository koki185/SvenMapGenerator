"""Предложить лучшие seed по метрикам композиции (P3.4).

    python propose_seeds.py --chapter sc_exp_1
    python propose_seeds.py --all
    python propose_seeds.py --all --count 20 --top 3

Ничего не перезаписывает: только печатает и пишет notes/seed_suggestions.md.
"""

import argparse
import os

from svenmap.campaign import load_campaign
from svenmap.seed_selector import format_candidates, propose

CAMPAIGN_JSON = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "campaign.json"
)
OUT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "notes", "seed_suggestions.md",
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--chapter", default="")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--count", type=int, default=12)
    parser.add_argument("--top", type=int, default=3)
    args = parser.parse_args()

    campaign = load_campaign(CAMPAIGN_JSON)
    chapters = campaign.chapters
    if args.all or not args.chapter:
        chapters = list(campaign.chapters)
    else:
        chapters = [c for c in chapters if c.name == args.chapter]
        if not chapters:
            print("нет главы с именем", args.chapter)
            return 1

    lines = ["# Предложения seed по композиции (P3.4)", ""]
    for chapter in chapters:
        candidates = propose(chapter, campaign, args.count, args.top)
        lines.append(format_candidates(chapter, candidates))
        print("\n" + lines[-1])

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\nОтчёт:", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
