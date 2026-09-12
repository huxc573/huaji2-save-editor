# -*- coding: utf-8 -*-
"""存档结构探查 v0.4（有界版）：找 存银 / 背包仓库 / 召唤兽(Baby) / 经验 存在哪儿。

只扫 :party / :actors / :system 三个分区（:map/:player/:troop 太大且无关），
并且限制访问节点数和深度，避免组合爆炸。

用法：python tools/probe_v04_save.py [--out 文件]
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
NODES = [0]
LIMIT = 300000


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


def walk(node, path, depth, classes):
    NODES[0] += 1
    if NODES[0] > LIMIT or depth > 25:
        return
    node = deref(node)
    if node is None:
        return
    if isinstance(node, M.ObjNode):
        classes.setdefault(node.cls, []).append(path)
        for k, v in node.ivars:
            walk(v, path + "." + (b2s(k) if k else "?"), depth + 1, classes)
    elif isinstance(node, M.ArrayNode):
        for i, v in enumerate(node.items[:200]):
            walk(v, path + "[%d]" % i, depth + 1, classes)
    elif isinstance(node, M.HashNode):
        for k, v in node.pairs[:200]:
            walk(v, path + "{%s}" % key_str(k), depth + 1, classes)


def dump_obj(node, indent, depth, maxdepth):
    node = deref(node)
    if not isinstance(node, M.ObjNode):
        out.write("%s%s\n" % (indent, short(node)))
        return
    out.write("%s<%s>\n" % (indent, node.cls))
    if depth >= maxdepth:
        return
    for k, v in node.ivars:
        out.write("%s  %-24s %s\n" % (indent, b2s(k) if k else "?", short(v)))
        vv = deref(v)
        if depth + 1 < maxdepth and isinstance(vv, M.ObjNode):
            dump_obj(vv, indent + "      ", depth + 1, maxdepth)


def main():
    global out
    if "--out" in sys.argv:
        out = open(sys.argv[sys.argv.index("--out") + 1], "w", encoding="utf-8")
    path = xj_env.save_path()
    out.write("存档 = %s\n" % path)
    doc = xj_model.Doc(path)
    contents = deref(doc.objects[-1]["node"])
    secs = {}
    for k, v in contents.pairs:
        secs[key_str(k)] = v
    out.write("明文 %d 字节，顶层分区：%s\n\n" % (len(doc.raw), list(secs)))

    classes = {}
    for name in ("party", "actors", "system"):
        if name in secs:
            walk(secs[name], name, 0, classes)
    out.write("### :party/:actors/:system 里出现过的类（访问 %d 个节点）\n" % NODES[0])
    for cls in sorted(classes):
        out.write("  %-36s %5d 处   例：%s\n"
                  % (cls, len(classes[cls]), classes[cls][0][:100]))

    for name in ("party", "actors", "system"):
        if name not in secs:
            continue
        out.write("\n" + "=" * 78 + "\n### :%s 展开\n" % name)
        dump_obj(secs[name], "  ", 0, 2)
    out.write("\n（end，访问 %d 个节点）\n" % NODES[0])
    out.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
