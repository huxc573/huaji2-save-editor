# -*- coding: utf-8 -*-
"""整档重写的**语义**校验：原明文 vs 重写后明文，解析出来的树是否等价。

v0.4 起重写走 `serialize_doc()`（带符号表）——本来已经能逐字节一致，
这里再比一遍“规范形式”：结构、标量、以及**对象共享关系**（谁和谁是同一个对象）。
错位/串子之类的问题会在这一层暴露。

用法：python tools/test_semantic_equal.py [--out 文件]
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.stdout.reconfigure(errors="replace")

import xj_codec  # noqa: E402
import xj_env  # noqa: E402
import xj_marshal as M  # noqa: E402

out = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
OK = [0, 0]


def check(name, cond, extra=""):
    OK[0 if cond else 1] += 1
    out.write("  %s %-44s %s\n" % ("[OK]" if cond else "[NG]", name, extra))


def deref(n):
    while isinstance(n, M.LinkNode) and n.target is not None:
        n = n.target
    return n


def canon(node, tab):
    """规范文本：结构 + 标量 + 共享关系（同一对象第二次出现写 ref#id）。"""
    if node is None:
        return "nil"
    node = deref(node)
    if node is None:
        return "nil"
    numbered = isinstance(node, M.NUMBERED_NODES)
    if numbered:
        key = id(node)
        if key in tab:
            return "ref#%d" % tab[key]
        tab[key] = len(tab)
    if isinstance(node, M.NilNode):
        v = node.value
        return "nil(%r)" % (v,) if v is not None else "nil"
    if isinstance(node, M.BoolNode):
        return "bool(%s)" % node.value
    if isinstance(node, M.IntNode):
        return "int(%d)" % node.value
    if isinstance(node, M.BignumNode):
        return "big(%d)" % node.value
    if isinstance(node, M.FloatNode):
        return "flt(%r)" % node.value
    if isinstance(node, M.SymbolNode):
        return "sym(%s)" % node.name
    if isinstance(node, M.StrNode):
        return "str(%s,%r)" % (node.cls, node.data)
    if isinstance(node, M.ArrayNode):
        return "arr(%s)[%s]" % (node.cls,
                                ",".join(canon(x, tab) for x in node.items))
    if isinstance(node, M.HashNode):
        return "hash(%s,%s){%s}" % (
            node.cls, M.value_of(node.default) if node.default else None,
            ",".join("%s=>%s" % (canon(k, tab), canon(v, tab))
                     for k, v in node.pairs))
    if isinstance(node, (M.ObjNode, M.StructNode)):
        return "%s:%s{%s}" % ("o" if isinstance(node, M.ObjNode) else "S",
                              node.cls,
                              ",".join("%s=%s" % (k, canon(v, tab))
                                       for k, v in node.ivars))
    if isinstance(node, (M.ClassNode, M.ModuleNode)):
        return "%s:%s" % (node.type, node.name)
    if isinstance(node, M.UserDefNode):
        return "u:%s(%d)" % (node.cls, len(node.data))
    if isinstance(node, M.UserMarshalNode):
        return "U:%s(%s)" % (node.cls, canon(node.inner, tab))
    if isinstance(node, M.IVarNode):
        return "I(%s){%s}" % (canon(node.inner, tab),
                              ",".join("%s=%s" % (k, canon(v, tab))
                                       for k, v in node.ivars))
    if isinstance(node, M.LinkNode):
        return "link#%d" % node.index
    return "%s?" % node.type


def compare(plain, label):
    try:
        objs = M.parse_stream(plain)
    except Exception as e:
        check("%s 原始可解析" % label, False, repr(e))
        return
    new = M.serialize_doc(objs)
    try:
        objs2 = M.parse_stream(new)
    except Exception as e:
        check("%s 重写后可解析" % label, False, repr(e))
        return
    check("%s 顶层对象数一致" % label, len(objs) == len(objs2),
          "%d vs %d（%d -> %d 字节）" % (len(objs), len(objs2),
                                         len(plain), len(new)))
    for i, (o1, o2) in enumerate(zip(objs, objs2)):
        a = canon(o1["node"], {})
        b = canon(o2["node"], {})
        check("%s 第 %d 个顶层对象语义一致" % (label, i), a == b,
              "" if a == b else "长度 %d vs %d，首个差异处 %s"
              % (len(a), len(b), first_diff_text(a, b)))


def first_diff_text(a, b):
    for i in range(min(len(a), len(b))):
        if a[i] != b[i]:
            return "…%s… vs …%s…" % (a[max(0, i - 40):i + 40],
                                     b[max(0, i - 40):i + 40])
    return "前缀相同，长度不同"


def main():
    global out
    if "--out" in sys.argv:
        out = open(sys.argv[sys.argv.index("--out") + 1], "w", encoding="utf-8")
    game = xj_env.find_game_dir()
    out.write("游戏目录 = %s\n" % game)
    sp = xj_env.save_path()
    out.write("\n### 存档 %s\n" % os.path.basename(sp))
    import xj_model
    doc = xj_model.Doc(sp)
    compare(doc.raw, "save")

    pdir = os.path.join(HERE, "_plain")
    if os.path.isdir(pdir):
        out.write("\n### tools/_plain 下的明文\n")
        for n in sorted(os.listdir(pdir)):
            p = os.path.join(pdir, n)
            if os.path.getsize(p) < 10 or n.startswith("System_Game.md5"):
                continue
            compare(open(p, "rb").read(), n)
    out.write("\n==== %d 通过 / %d 失败 ====\n" % (OK[0], OK[1]))
    out.flush()
    if "--out" in sys.argv:
        out.close()
    return 1 if OK[1] else 0


if __name__ == "__main__":
    sys.exit(main())
