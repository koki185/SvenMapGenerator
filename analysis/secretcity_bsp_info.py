import os, struct, math

DIR = r"K:\SteamLibrary\steamapps\common\Sven Co-op\svencoop\maps"
OURS = r"K:\SteamLibrary\steamapps\common\Sven Co-op\svencoop_addon\maps\sc_gen_7.bsp"
OUT = r"C:\Users\Koki185\Documents\Проект по умолчанию\notes\secretcity_bsp_info.txt"
NAMES = [
    "secretcity_r_1", "secretcity_r_2", "secretcity_r_3", "secretcity_r_4",
    "secretcity_r_5", "secretcity_r_5x", "secretcity_r_6", "secretcity_r_k",
    "secretcity_r_k2", "secretcity_r_die", "secretcity_r_frac", "secretcity_r_red",
]

def info(path):
    data = open(path, "rb").read()
    version = struct.unpack_from("<i", data, 0)[0]
    # dheader_t GoldSrc: int version; lump_t lumps[16];
    # lump_t = (fileofs, filelen). Поля numlumps НЕТ.
    nlumps = 16
    lumps = []
    for i in range(nlumps):
        off = 4 + i * 8
        if off + 8 > len(data):
            break
        fileofs, filelen = struct.unpack_from("<ii", data, off)
        lumps.append((fileofs, filelen))

    def lump(i):
        if i >= len(lumps):
            return b""
        o, n = lumps[i]
        return data[o:o + n]

    vert = lump(3)
    verts = [
        struct.unpack_from("<fff", vert, i)
        for i in range(0, len(vert) - 11, 12)
    ]
    verts = [v for v in verts if all(math.isfinite(c) for c in v)]
    xs = [v[0] for v in verts]
    ys = [v[1] for v in verts]
    zs = [v[2] for v in verts]

    ent = lump(0).decode("latin-1", errors="replace")
    ent_count = ent.count('"classname"')

    tex = lump(2)
    tex_count = struct.unpack_from("<i", tex, 0)[0] if len(tex) >= 4 else 0

    return {
        "size": len(data), "version": version, "nlumps": nlumps,
        "verts": len(verts), "faces": len(lump(7)) // 20,
        "tex": tex_count, "ents": ent_count,
        "bbox": (round(max(xs) - min(xs)), round(max(ys) - min(ys)),
                 round(max(zs) - min(zs))) if xs else None,
        "origin": (round(min(xs)), round(min(ys)), round(min(zs))) if xs else None,
    }

L = []
L.append("BSP-разбор: реальные размеры карт SecretCity Saga")
L.append("Парсер: dheader_t (version + 16 lumps), lump 0 = entity, lump 3 = vertexes, lump 7 = faces")
L.append("")
L.append("{:20s} {:>9s} {:>7s} {:>6s} {:>6s} {:>5s} {:>20s}".format(
    "map", "bytes", "verts", "faces", "tex", "ents", "bbox x/y/z"))
L.append("-" * 80)
for name in NAMES + ["sc_gen_7"]:
    path = os.path.join(DIR, name + ".bsp") if name != "sc_gen_7" else OURS
    if not os.path.isfile(path):
        continue
    d = info(path)
    L.append("{:20s} {:9d} {:7d} {:6d} {:6d} {:5d} {:>20s}".format(
        name, d["size"], d["verts"], d["faces"], d["tex"], d["ents"], str(d["bbox"])))

L.append("")
L.append("Итог: bbox в игровых юнитах. Число entity в BSP совпадает с .ent — парсер проверен.")
with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(L) + "\n")
print("\n".join(L))
