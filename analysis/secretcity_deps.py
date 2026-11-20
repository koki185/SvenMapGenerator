import os, re, collections

DIR = r"K:\SteamLibrary\steamapps\common\Sven Co-op\svencoop\maps"
OUT = r"C:\Users\Koki185\Documents\Проект по умолчанию\notes\secretcity_dependencies.txt"
MAPS = ["secretcity_r_4", "secretcity_r_5", "secretcity_r_frac"]
ent_re = re.compile(r'"([^"\n]+)"\s+"([^"\n]*)"')

SKIP = {
    "classname", "targetname", "origin", "angles", "model", "spawnflags",
    "target", "message", "delay", "speed", "wait", "lip", "health", "frags",
    "style", "pitch", "pitchstart", "rendercolor", "renderamt", "rendermode",
    "renderfx", "skin", "body", "sequence", "displayname", "netname",
    "m_iszValueName", "m_iszNewValue", "m_iszScriptFile",
    "m_iszScriptFunctionName", "zhlt_embedlightmapresolution", "_light",
    "_fade", "_falloff", "maxhullsize", "minhullsize", "m_iMaxLiveChildren",
    "monstercount", "monstertype", "m_flCustomRespawnTime", "exclusivehold",
    "change_rendermode", "g_e", "g_a", "movesnd", "stopsnd", "vol",
}

def parse(name):
    path = os.path.join(DIR, name + ".ent")
    text = open(path, encoding="latin-1", errors="replace").read()
    ents = []
    for block in re.findall(r"\{([^{}]*)\}", text, re.S):
        d = dict(ent_re.findall(block))
        if "classname" in d:
            ents.append(d)
    return ents

def targets(e):
    out = []
    if e.get("target"):
        out.append(e["target"])
    if e["classname"] == "multi_manager":
        for k, v in e.items():
            if k in SKIP or k == "targetname":
                continue
            if re.fullmatch(r"-?\d+(\.\d+)?", v or ""):
                out.append(k)
    return sorted(set(out))

def label(e):
    parts = [e["classname"]]
    if e.get("targetname"):
        parts.append("@" + e["targetname"])
    if e.get("message"):
        parts.append("msg=" + e["message"][:45].replace("\n", " "))
    if e.get("health") and e["classname"] == "game_counter":
        parts.append("health=" + e["health"])
    if e.get("map"):
        parts.append("map=" + e["map"])
    return " ".join(parts)

lines = []
for name in MAPS:
    ents = parse(name)
    by_name = collections.defaultdict(list)
    for i, e in enumerate(ents):
        if e.get("targetname"):
            by_name[e["targetname"]].append(i)
    edges = {i: targets(e) for i, e in enumerate(ents)}
    targeted = set()
    for i, outs in edges.items():
        for t in outs:
            targeted.update(by_name.get(t, []))

    roots = [
        i for i, e in enumerate(ents)
        if e["classname"] in (
            "func_button", "item_security", "item_generic", "trigger_once",
            "trigger_multiple", "game_counter", "trigger_relay",
            "func_breakable", "trigger_changevalue",
        )
        and edges[i] and i not in targeted
    ]
    lines.append("=" * 78)
    lines.append("{}  entities={}  edges={}  roots={}".format(
        name, len(ents), sum(len(v) for v in edges.values()), len(roots)))
    lines.append("=" * 78)

    shown = 0
    for root in roots:
        chains = []
        seen_types = collections.Counter()

        def walk(i, depth, path):
            if depth >= 6:
                return
            for t in edges.get(i, []):
                for j in by_name.get(t, []):
                    seen_types[ents[j]["classname"]] += 1
                    chains.append(path + [j])
                    walk(j, depth + 1, path + [j])

        walk(root, 0, [root])
        if not chains:
            continue
        lines.append("\nROOT: " + label(ents[root]))
        lines.append("  reachable: " + ", ".join(
            "{}x{}".format(k, v) for k, v in seen_types.most_common(8)))
        # Показываем цепочки, которые заканчиваются «результатом».
        endings = ("func_door", "func_wall_toggle", "trigger_changelevel",
                   "game_text", "squadmaker", "func_illusionary",
                   "info_teleport_destination")
        good = [c for c in chains if any(
            ents[x]["classname"] in endings for x in c[1:])]
        for c in (good or chains)[:2]:
            lines.append("  CHAIN: " + " -> ".join(label(ents[x]) for x in c))
        shown += 1
        if shown >= 35:
            lines.append("  ... (дальше сокращено)")
            break

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
print("written:", OUT, "lines:", len(lines))
