# -*- coding: utf-8 -*-
"""看存档里 Game_Actor / Game_Actor_Attr 的字段挂在哪儿（设计"角色"页签用）。

用法：python tools/actor_ivars.py
输出：tools/_actor_ivars.txt
"""
import os
import sys

sys.stdout.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))

import xj_env  # noqa: E402
import xj_marshal as M  # noqa: E402
import xj_model  # noqa: E402
import xj_save  # noqa: E402

LOG = os.path.join(HERE, "_actor_ivars.txt")
L = []

doc = xj_model.Doc(xj_env.save_path())
sv = xj_save.SaveDoc(doc=doc)


def shape(n, depth=1):
    n = xj_save._deref(n)
    if n is None:
        return "nil"
    if isinstance(n, M.ObjNode):
        if depth <= 0:
            return "Obj:%s" % n.cls
        return "%s{%s}" % (n.cls, ", ".join(
            "%s=%s" % (k, shape(v, depth - 1)) for k, v in n.ivars[:4]))
    if isinstance(n, M.ArrayNode):
        return "Array(%d)%s" % (len(n.items), shape(n.items[0], 0) if n.items else "")
    if isinstance(n, M.HashNode):
        return "Hash(%d)" % len(n.pairs)
    if isinstance(n, M.IVarNode):
        return "IVar(%s)" % shape(n.inner, depth - 1)
    if isinstance(n, M.LinkNode):
        return "Link->%s" % shape(n.target, depth - 1)
    v = M.value_of(n)
    if isinstance(v, bytes):
        v = v.decode("utf-8", "replace")
    return repr(v)[:60]


for aid, actor in sv.actors():
    L.append("=" * 70)
    L.append("Game_Actor #%d  %s" % (aid, sv.actor_summary(actor)))
    for k, v in actor.ivars:
        L.append("   %-26s %s" % (k, shape(v)))
    break

# 找所有 Game_Actor_Attr 出现的位置
L.append("")
L.append("== 存档里所有 Game_Actor_Attr 出现位置 ==")
count = [0]


def walk(node, path, seen, depth=0):
    node = xj_save._deref(node)
    if node is None or id(node) in seen or depth > 6:
        return
    seen = seen | {id(node)}
    if isinstance(node, M.ObjNode):
        if node.cls.split("::")[-1] == "Game_Actor_Attr" and count[0] < 3:
            count[0] += 1
            L.append("  %s  -> %s" % (path, shape(node, 2)))
        for k, v in node.ivars:
            walk(v, path + "." + k, seen, depth + 1)
    elif isinstance(node, (M.ArrayNode,)):
        for i, v in enumerate(node.items):
            walk(v, "%s[%d]" % (path, i), seen, depth + 1)
    elif isinstance(node, M.HashNode):
        for k, v in node.pairs:
            walk(v, "%s[%s]" % (path, M.value_of(k)), seen, depth + 1)
    elif isinstance(node, M.IVarNode):
        walk(node.inner, path + "(inner)", seen, depth + 1)


for name, v in sv.sections():
    walk(v, ":" + name, frozenset())

open(LOG, "w", encoding="utf-8").write("\n".join(L) + "\n")
print("已写出 %s（%d 行）" % (LOG, len(L)))
