# -*- coding: utf-8 -*-
"""看存档里"机器码"相关的字段（`$game_system.config[:hard_disk_code]`）。

用法：python tools/probe_machine.py [存档路径]
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.stdout.reconfigure(errors="replace")

import xj_env          # noqa: E402
import xj_marshal as M  # noqa: E402
import xj_model        # noqa: E402
import xj_save         # noqa: E402


def brief(node, depth=0, out=None):
    if out is None:
        out = []
    n = M.deref(node) if hasattr(M, "deref") else node
    while isinstance(n, M.LinkNode) and n.target is not None:
        n = n.target
    t = getattr(n, "type", "?")
    if isinstance(n, M.StrNode):
        out.append("  " * depth + "str %r" % (n.data,))
    elif isinstance(n, M.IntNode):
        out.append("  " * depth + "int %d" % n.value)
    elif isinstance(n, M.ArrayNode):
        out.append("  " * depth + "array[%d]" % len(n.items))
        for x in n.items:
            brief(x, depth + 1, out)
    elif isinstance(n, M.HashNode):
        out.append("  " * depth + "hash{%d}" % len(n.pairs))
        for k, v in n.pairs[:20]:
            kk = M.value_of(M._deref(k)) if hasattr(M, "_deref") else M.value_of(k)
            out.append("  " * depth + "  key=%r" % (kk,))
            brief(v, depth + 2, out)
    elif isinstance(n, M.ObjNode):
        out.append("  " * depth + "obj %s{%d ivars}" % (n.cls, len(n.ivars)))
    else:
        out.append("  " * depth + "%s" % t)
    return out


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else xj_env.save_path()
    doc = xj_model.Doc(path)
    sv = xj_save.SaveDoc(doc=doc)
    print("存档:", path)
    sysn = sv.section("system")
    cfg = None
    for k, v in sysn.ivars:
        if k == "@config":
            cfg = v
    if cfg is None:
        print(":system 里没有 @config")
        return 1
    h = cfg
    while isinstance(h, M.LinkNode) and h.target is not None:
        h = h.target
    print("@config 是 %s" % getattr(h, "type", "?"))
    if isinstance(h, M.HashNode):
        for k, v in h.pairs:
            kk = M.value_of(k)
            print("--- key = %r" % (kk,))
            for ln in brief(v, 1):
                print(ln)
    print()
    print("所有含 hard 的 ivar / key：")
    for name, v in sysn.ivars:
        if "hard" in name.lower():
            print("   ivar", name, brief(v, 1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
