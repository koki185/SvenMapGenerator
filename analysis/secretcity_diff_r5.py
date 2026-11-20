import os, re, collections

DIR = r"K:\SteamLibrary\steamapps\common\Sven Co-op\svencoop\maps"
OUT = r"C:\Users\Koki185\Documents\Проект по умолчанию\notes\secretcity_r5_diff.txt"
ent_re = re.compile(r'"([^"\n]+)"\s+"([^"\n]*)"')

def parse(name):
    text = open(os.path.join(DIR, name + ".ent"), encoding="latin-1", errors="replace").read()
    out = []
    for block in re.findall(r"\{([^{}]*)\}", text, re.S):
        d = dict(ent_re.findall(block))
        if "classname" in d:
            out.append(d)
    return out

a, b = parse("secretcity_r_5"), parse("secretcity_r_5x")
ca = collections.Counter(e["classname"] for e in a)
cb = collections.Counter(e["classname"] for e in b)
na = collections.Counter(e.get("targetname", "") for e in a if e.get("targetname"))
nb = collections.Counter(e.get("targetname", "") for e in b if e.get("targetname"))

L = []
L.append("secretcity_r_5 vs secretcity_r_5x")
L.append("entities: r5={}  r5x={}".format(len(a), len(b)))
L.append("\n=== classname delta (r5x - r5) ===")
allc = sorted(set(ca) | set(cb))
for c in allc:
    d = cb.get(c, 0) - ca.get(c, 0)
    if d:
        L.append("  {:28s} {:4d} -> {:4d}  ({:+d})".format(c, ca.get(c,0), cb.get(c,0), d))

L.append("\n=== targetnames only in r5 ===")
L.append("  " + ", ".join(sorted(set(na) - set(nb))[:60]))
L.append("\n=== targetnames only in r5x ===")
L.append("  " + ", ".join(sorted(set(nb) - set(na))[:60]))

L.append("\n=== canistercount details ===")
for label, ents in (("r5", a), ("r5x", b)):
    rows = [
        (e.get("target", ""), e.get("health", ""), e.get("delay", ""),
         e.get("origin", ""))
        for e in ents if e.get("targetname") == "canistercount"
    ]
    L.append("  {}: {} counters".format(label, len(rows)))
    for r in sorted(rows, key=lambda x: x[1])[:12]:
        L.append("    target={} health={} delay={}".format(*r[:3]))

L.append("\n=== item_security (skin/target) ===")
for label, ents in (("r5", a), ("r5x", b)):
    items = [e for e in ents if e["classname"] == "item_security"]
    L.append("  {}: {} items".format(label, len(items)))
    L.append("    targets: " + str(collections.Counter(
        e.get("target", "") for e in items).most_common(8)))
    L.append("    skins:   " + str(collections.Counter(
        e.get("skin", "") for e in items).most_common(8)))

L.append("\n=== texts specific to r5x (not in r5) ===")
ta = {e.get("message", "") for e in a if e["classname"] == "game_text"}
tb = {e.get("message", "") for e in b if e["classname"] == "game_text"}
for t in sorted(tb - ta)[:20]:
    L.append("  " + t[:110].replace("\n", " "))

L.append("\n=== entities with '_OLD' or 'old' in targetname ===")
for label, ents in (("r5", a), ("r5x", b)):
    old = [e.get("targetname", "") for e in ents
           if "old" in e.get("targetname", "").lower()]
    L.append("  {}: {}".format(label, sorted(set(old))[:20]))

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(L) + "\n")
print("written:", OUT, "lines:", len(L))
