# -*- coding: utf-8 -*-
"""把两个格子的 @attr 逐层摊开，连“节点类型 / value_of 结果”一起打出来。

专门用来查：为什么工具读不出游戏写的内容（键是 Symbol 还是 String？）。

用法：python tools/probe_attr_node.py [槽A] [槽B] [kind]
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.stdout.reconfigure(errors="replace")

import xj_env          # noqa: E402
import xj_game         # noqa: E402
import xj_marshal as M  # noqa: E402
import xj_model        # noqa: E402
import xj_save         # noqa: E402
from xj_save import _deref, ivar  # noqa: E402

A = int(sys.argv[1]) if len(sys.argv) > 1 else 0
B = int(sys.argv[2]) if len(sys.argv) > 2 else 1
KIND = sys.argv[3] if len(sys.argv) > 3 else "Items"


def walk(node, label, depth=0):
    n = _deref(node)
    pad = "  " * depth
    if n is None:
        print("%s%s: None" % (pad, label))
        return
    print("%s%s: type=%s cls=%r value_of=%r raw_type=%r"
          % (pad, label, getattr(n, "type", "?"), getattr(n, "cls", None),
             M.value_of(n), type(n).__name__))
    if isinstance(n, M.HashNode):
        for k, v in n.pairs:
            kd = _deref(k)
            print("%s  [键] type=%s value_of=%r class=%s"
                  % (pad, getattr(kd, "type", "?"), M.value_of(kd),
                     type(kd).__name__))
            walk(v, "值", depth + 2)
    elif isinstance(n, M.ArrayNode):
        for i, x in enumerate(n.items):
            walk(x, "[%d]" % i, depth + 1)


def main():
    doc = xj_model.Doc(xj_env.save_path())
    sv = xj_save.SaveDoc(doc=doc)
    g = xj_game.GameEditor(sv)
    for slot in (A, B):
        it = g._item_node(KIND, slot)
        print("=" * 66)
        print("槽 %d：%s" % (slot, g.item_display_name(it, "?")))
        walk(ivar(it, "@attr"), "@attr")
        print("→ item_payload() = %r" % (g.item_payload(it),))
        print("→ payload_summary() = %r" % (g.payload_summary(it),))
        print("→ hash_get(@attr,'data') = %r"
              % (xj_save.hash_get(_deref(ivar(it, "@attr")), "data"),))
    return 0


if __name__ == "__main__":
    sys.exit(main())
