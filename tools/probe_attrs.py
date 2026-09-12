# -*- coding: utf-8 -*-
"""把 Game_Baby_Attr / Game_Actor_Attr / RPG::Item 模板的 ivar 全列出来。

用法：python tools/probe_attrs.py [--out 文件]
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.stdout.reconfigure(errors="replace")

import xj_env  # noqa: E402
import xj_marshal as M  # noqa: E402
import xj_model  # noqa: E402

out = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def deref(n):
    while isinstance(n, M.LinkNode) and n.target is not None:
        n = n.target
    return n


def b2s(v):
    if isinstance(v, bytes):
        try:
            return v.decode("utf-8")
        except UnicodeDecodeError:
            return v.decode("gbk", "replace")
    return v


def key_of(k):
    kk = deref(k)
    return (getattr(kk, "name", None) or b2s(getattr(kk, "value", None)) or "?")


def brief(node, n=40):
    node = deref(node)
    if node is None:
        return "None"
    if isinstance(node, M.ObjNode):
        return "<%s> %d ivars" % (node.cls, len(node.ivars))
    if isinstance(node, M.ArrayNode):
        return "Array(%d)" % len(node.items)
    if isinstance(node, M.HashNode):
        return "Hash(%d)" % len(node.pairs)
    if isinstance(node, M.StrNode):
        return repr(b2s(node.data)[:n])
    if isinstance(node, M.SymbolNode):
        return ":" + node.name
    return repr(b2s(getattr(node, "value", node.type)))


def dump(node, indent="    ", maxdepth=1, depth=0):
    node = deref(node)
    if isinstance(node, M.ObjNode):
        out.write("%s<%s> %d ivars\n" % (indent, node.cls, len(node.ivars)))
        if depth >= maxdepth:
            return
        for k, v in node.ivars:
            out.write("%s  %-24s %s\n" % (indent, b2s(k) if k else "?", brief(v)))
            vv = deref(v)
            if isinstance(vv, M.ObjNode) and depth + 1 < maxdepth:
                dump(vv, indent + "      ", maxdepth, depth + 1)
    elif isinstance(node, M.HashNode):
        out.write("%sHash(%d)\n" % (indent, len(node.pairs)))
        for k, v in node.pairs[:30]:
            out.write("%s  %-20s %s\n" % (indent, key_of(k), brief(v)))


def ivar(node, name):
    node = deref(node)
    if not isinstance(node, M.ObjNode):
        return None
    for k, v in node.ivars:
        if b2s(k) == name:
            return v
    return None


def main():
    global out
    if "--out" in sys.argv:
        out = open(sys.argv[sys.argv.index("--out") + 1], "w", encoding="utf-8")
    doc = xj_model.Doc(xj_env.save_path())
    contents = deref(doc.objects[-1]["node"])
    secs = {key_of(k): v for k, v in contents.pairs}

    actors = deref(secs["actors"])
    data = deref(ivar(actors, "@data"))
    for i, a in enumerate(data.items):
        aa = deref(a)
        if not isinstance(aa, M.ObjNode):
            continue
        out.write("\n### actors.@data[%d].@attr（Game_Actor_Attr）\n" % i)
        dump(ivar(aa, "@attr"), "  ", 1)
        babys = deref(ivar(aa, "@babys"))
        if isinstance(babys, M.ArrayNode):
            for j, b in enumerate(babys.items):
                bb = deref(b)
                out.write("\n### actors.@data[%d].@babys[%d]（Game_Baby）\n" % (i, j))
                out.write("  @name=%s @level=%s @exp=%s @hp=%s @mp=%s\n"
                          % (brief(ivar(bb, "@name")), brief(ivar(bb, "@level")),
                             brief(ivar(bb, "@exp")), brief(ivar(bb, "@hp")),
                             brief(ivar(bb, "@mp"))))
                out.write("  --- @attr（Game_Baby_Attr）\n")
                dump(ivar(bb, "@attr"), "    ", 1)
                out.write("  --- 其它关键字段\n")
                for k, v in bb.ivars:
                    ks = b2s(k)
                    if ks in ("@exp", "@skills", "@equips", "@seed", "@seeds",
                              "@signature"):
                        out.write("    %-14s %s\n" % (ks, brief(v, 200)))
                        vv = deref(v)
                        if isinstance(vv, M.HashNode):
                            for k2, v2 in vv.pairs:
                                out.write("        %-12s %s\n"
                                          % (key_of(k2), brief(v2, 40)))
        break

    # RPG::Item 模板（Data\\Items.rvdata2 里 id=1 那件）
    import xj_codec
    game = xj_env.find_game_dir()
    plain = os.path.join(HERE, "_plain", "Data_Items.rvdata2.bin")
    if os.path.exists(plain):
        objs = M.parse_stream(open(plain, "rb").read())
        root = deref(objs[-1]["node"])
        out.write("\n### Data\\Items.rvdata2 里第 1 件（模板结构）\n")
        if isinstance(root, M.ArrayNode):
            for i, it in enumerate(root.items[:3]):
                if i == 1:
                    dump(it, "  ", 1)
    out.write("\n（end）\n")
    out.flush()
    if "--out" in sys.argv:
        out.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
