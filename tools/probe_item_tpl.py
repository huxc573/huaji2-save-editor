# -*- coding: utf-8 -*-
"""对比：存档里的 RPG::Item 与 Data\\Items.rvdata2 里的模板，看 ivar 差在哪。"""
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


def ivar(node, name):
    node = deref(node)
    for k, v in node.ivars:
        if b2s(k) == name:
            return v
    return None


def brief(node, n=50):
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
    return "%s(%r)" % (node.type, b2s(getattr(node, "value", None)))


def main():
    global out
    if "--out" in sys.argv:
        out = open(sys.argv[sys.argv.index("--out") + 1], "w", encoding="utf-8")
    doc = xj_model.Doc(xj_env.save_path())
    contents = deref(doc.objects[-1]["node"])
    secs = {key_of(k): v for k, v in contents.pairs}
    party = deref(secs["party"])
    items = deref(ivar(party, "@items"))
    save_item = None
    for k, v in items.pairs:
        vv = deref(v)
        if isinstance(vv, M.ArrayNode):
            cand = deref(vv.items[0])
            if isinstance(cand, M.ObjNode) and cand.cls == "RPG::Item":
                save_item = cand
                break

    plain = os.path.join(HERE, "_plain", "Data_Items.rvdata2.bin")
    objs = M.parse_stream(open(plain, "rb").read())
    root = deref(objs[-1]["node"])
    tpl = None
    for it in root.items:
        n = deref(it)
        if isinstance(n, M.ObjNode) and str(xj_model) and n.cls == "RPG::Item":
            iid = deref(ivar(n, "@id"))
            if iid is not None and getattr(iid, "value", None) == 1:
                tpl = n
                break

    def names(node):
        return [b2s(k) for k, _ in node.ivars] if node else []

    a, b = names(save_item), names(tpl)
    out.write("存档里的 RPG::Item ivar（%d）：%s\n" % (len(a), a))
    out.write("\n模板 RPG::Item ivar（%d）：%s\n" % (len(b), b))
    out.write("\n只在存档里有：%s\n" % [x for x in a if x not in b])
    out.write("只在模板里有：%s\n" % [x for x in b if x not in a])
    out.write("\n### 逐项对比（存档 vs 模板）\n")
    for k in a:
        out.write("  %-18s %-34s %s\n" % (k, brief(ivar(save_item, k), 30),
                                          brief(ivar(tpl, k), 30)))
    out.flush()
    if "--out" in sys.argv:
        out.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
