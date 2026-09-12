# -*- coding: utf-8 -*-
"""打印存档各分区的结构（键、类名、ivar 名），用来设计"快捷修改"面板。

用法：python tools/dump_save_tree.py [depth]
输出：tools/_savetree.txt
"""
import os
import sys

sys.stdout.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))

import xj_codec  # noqa: E402
import xj_env  # noqa: E402
import xj_marshal as M  # noqa: E402
import xj_model  # noqa: E402

LOG = os.path.join(HERE, "_savetree.txt")
MAXDEPTH = int(sys.argv[1]) if len(sys.argv) > 1 else 3

doc = xj_model.Doc(xj_env.save_path())
L = []
L.append("存档 = %s  明文 %d 字节  顶层对象 %d" %
         (doc.path, len(doc.raw), len(doc.objects)))


def val(n):
    v = M.value_of(n)
    if isinstance(v, bytes):
        try:
            return v.decode("utf-8")
        except UnicodeDecodeError:
            return repr(v[:24])
    return v


def desc(n):
    if n is None:
        return "nil"
    t = type(n).__name__
    if isinstance(n, M.HashNode):
        return "Hash(%d)" % len(n.pairs)
    if isinstance(n, M.ArrayNode):
        return "Array(%d)" % len(n.items)
    if isinstance(n, M.ObjNode):
        return "Obj:%s(%d ivar)" % (n.cls, len(n.ivars))
    if isinstance(n, M.StrNode):
        return "Str(%d)" % len(n.data)
    if isinstance(n, M.SymbolNode):
        return "Sym:%s" % n.name
    if isinstance(n, M.IVarNode):
        return "IVar"
    if isinstance(n, M.LinkNode):
        return "Link#%d" % n.index
    return t


def walk(n, name, depth, seen):
    pad = "  " * depth
    n2 = n.target if isinstance(n, M.LinkNode) and n.target is not None else n
    L.append("%s%s = %s" % (pad, name, desc(n)))
    if depth >= MAXDEPTH or n2 is None or id(n2) in seen:
        return
    seen = seen | {id(n2)}
    if isinstance(n2, M.HashNode):
        for k, v in n2.pairs[:24]:
            walk(v, "[%s]" % val(k), depth + 1, seen)
    elif isinstance(n2, M.ArrayNode):
        for i, v in enumerate(n2.items[:12]):
            walk(v, "[%d]" % i, depth + 1, seen)
    elif isinstance(n2, (M.ObjNode, M.StructNode)):
        for nm, v in n2.ivars:
            walk(v, nm, depth + 1, seen)
    elif isinstance(n2, M.IVarNode):
        walk(n2.inner, "(inner)", depth + 1, seen)


contents = doc.objects[-1]["node"]
walk(contents, "contents", 0, frozenset())
open(LOG, "w", encoding="utf-8").write("\n".join(L) + "\n")
print("\n".join(L[:40]))
