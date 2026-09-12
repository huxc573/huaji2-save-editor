# -*- coding: utf-8 -*-
"""把 Game_Party / Game_Actor / Game_Baby 的 ivar 全列出来，找 背包 / 宠物 / 经验。

用法：python tools/probe_v04_party.py [--out 文件]
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


def key_str(k):
    kk = deref(k)
    return (getattr(kk, "name", None) or b2s(getattr(kk, "value", None)) or "?")


def short(node, n=70):
    node = deref(node)
    if node is None:
        return "None"
    if isinstance(node, M.ObjNode):
        return "<%s> %d 个 @变量" % (node.cls, len(node.ivars))
    if isinstance(node, M.ArrayNode):
        return "Array(%d)" % len(node.items)
    if isinstance(node, M.HashNode):
        return "Hash(%d)" % len(node.pairs)
    if isinstance(node, M.StrNode):
        return repr(b2s(node.data)[:n])
    if isinstance(node, M.SymbolNode):
        return ":" + node.name
    return repr(b2s(getattr(node, "value", node.type)))


def ivars(node, indent="  "):
    node = deref(node)
    if not isinstance(node, M.ObjNode):
        out.write("%s%s\n" % (indent, short(node)))
        return
    out.write("%s<%s>\n" % (indent, node.cls))
    for k, v in node.ivars:
        out.write("%s  %-26s %s\n" % (indent, b2s(k) if k else "?", short(v, 90)))


def pairs(node, indent="    ", limit=40):
    node = deref(node)
    if isinstance(node, M.HashNode):
        for k, v in node.pairs[:limit]:
            out.write("%s%-22s -> %s\n" % (indent, key_str(k), short(v, 100)))
    elif isinstance(node, M.ArrayNode):
        for i, v in enumerate(node.items[:limit]):
            out.write("%s[%-2d] %s\n" % (indent, i, short(v, 100)))


def main():
    global out
    if "--out" in sys.argv:
        out = open(sys.argv[sys.argv.index("--out") + 1], "w", encoding="utf-8")
    doc = xj_model.Doc(xj_env.save_path())
    contents = deref(doc.objects[-1]["node"])
    secs = {key_str(k): v for k, v in contents.pairs}

    party = deref(secs["party"])
    out.write("### Game_Party 全部 @变量\n")
    ivars(party)

    out.write("\n### party.@hash 的 16 项（可能是背包/仓库）\n")
    pairs(party_hash(party) if False else [v for k, v in party.ivars
                                           if b2s(k) == "@hash"][0])

    out.write("\n### party.@items 明细\n")
    items = [v for k, v in party.ivars if b2s(k) == "@items"][0]
    pairs(items, "    ", 20)

    actors = deref([v for k, v in contents.pairs
                    if key_str(k) == "actors"][0])
    data = deref([v for k, v in actors.ivars if b2s(k) == "@data"][0])
    out.write("\n### Game_Actors.@data（%d 槽）\n" % len(data.items))
    for i, a in enumerate(data.items):
        aa = deref(a)
        if aa is None or isinstance(aa, M.NilNode):
            out.write("  [%d] nil\n" % i)
        else:
            out.write("  [%d] %s  name=%s\n"
                      % (i, short(aa), fmt_name(aa)))

    for i, a in enumerate(data.items):
        aa = deref(a)
        if not isinstance(aa, M.ObjNode):
            continue
        out.write("\n" + "=" * 78 + "\n### actors.@data[%d] 全部 @变量（%s）\n"
                  % (i, fmt_name(aa)))
        ivars(aa)
        # 凡是 Array/Hash 的，展开前 20 项
        for k, v in aa.ivars:
            vv = deref(v)
            if isinstance(vv, (M.ArrayNode, M.HashNode)):
                out.write("  --- %s %s\n" % (b2s(k), short(vv)))
                pairs(vv, "        ", 20)
    out.write("\n（end）\n")
    out.flush()
    return 0


def fmt_name(node):
    for k, v in node.ivars:
        if b2s(k) == "@name":
            n = deref(v)
            return b2s(getattr(n, "data", None)) or "?"
    return "?"


if __name__ == "__main__":
    sys.exit(main())
