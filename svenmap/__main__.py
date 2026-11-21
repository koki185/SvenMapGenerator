"""Единый вход: python -m svenmap <команда> [аргументы].

Команды:
    campaign   генерация кампании (generate_campaign.py)
    qa         QA кампании (run_campaign_qa.py)
    propose    подбор seed (propose_seeds.py)
    map        одиночная карта через graph_v2 (generate_v3.py)
    schema     проверка campaign.json

Старые generate_*.py остаются для истории и regression-режима.
"""

import sys


HELP = """SvenMap Generator

Использование:
    python -m svenmap campaign [--only sc_exp_1] [--build] [--smoke]
    python -m svenmap qa [--only sc_exp_1] [--no-smoke]
    python -m svenmap propose [--all] [--count 12] [--top 3]
    python -m svenmap map [--seed 42] [--build] [--smoke]
    python -m svenmap schema [path/to/campaign.json]
"""


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(HELP)
        return 0

    command = sys.argv[1]
    rest = sys.argv[2:]

    if command == "campaign":
        from generate_campaign import main as entry
        sys.argv = ["generate_campaign.py"] + rest
    elif command == "qa":
        from run_campaign_qa import main as entry
        sys.argv = ["run_campaign_qa.py"] + rest
    elif command == "propose":
        from propose_seeds import main as entry
        sys.argv = ["propose_seeds.py"] + rest
    elif command == "map":
        from generate_v3 import main as entry
        sys.argv = ["generate_v3.py"] + rest
    elif command == "schema":
        import json
        from svenmap.campaign_schema import validate_data

        path = rest[0] if rest else "campaign.json"
        with open(path, encoding="utf-8") as f:
            issues = validate_data(json.load(f))
        if issues:
            for issue in issues:
                print("  - " + str(issue))
            return 1
        print("campaign.json: OK")
        return 0
    else:
        print("неизвестная команда:", command)
        print(HELP)
        return 1

    return entry()


if __name__ == "__main__":
    sys.exit(main())
