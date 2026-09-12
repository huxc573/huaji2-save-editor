# -*- coding: utf-8 -*-
"""把两个同类物品对象**深层**摊开对比（找出运行时缺什么导致 nil 报错）。

用法：python tools/probe_item_deep.py <槽号A> <槽号B> [kind]
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
B = int(sys.argv[2]) if len(sys.argv) > 2 else 17
KIND = sys.argv[3] if len(sys.argv) > 3 else "Items"


def s_of(n):
    v = M.value_of(_deref(n))
    if isinstance(v, bytes):
        try:
            return v.decode("utf-8")
        except UnicodeDecodeError:
            return v.decode("gbk", "replace")
    return v


def render(node, depth=0, maxdepth=6):
    n = _deref(node)
    if n is None:
        return "nil"
    if isinstance(n, M.NilNode):
        return "nil"
    if isinstance(n, M.ArrayNode):
        if depth >= maxdepth:
            return "[%d 项]" % len(n.items)
        return "[%s]" % ", ".join(render(x, depth + 1, maxdepth) for x in n.items)
    if isinstance(n, M.HashNode):
        if depth >= maxdepth:
            return "{%d 对}" % len(n.pairs)
        return "{%s}" % ", ".join(
            "%s => %s" % (render(k, depth + 1, maxdepth),
                          render(v, depth + 1, maxdepth))
            for k, v in n.pairs)
    if isinstance(n, M.ObjNode):
        if depth >= maxdepth:
            return "<%s %d ivar>" % (n.cls, len(n.ivars))
        return "<%s %s>" % (n.cls, " ".join(
            "%s=%s" % (k, render(v, depth + 1, maxdepth)) for k, v in n.ivars))
    if isinstance(n, M.StrNode):
        return repr(s_of(n))
    v = M.value_of(n)
    if isinstance(v, float):
        return "%.4f" % v
    return repr(v)


def get_slot(g, kind, slot):
    for k, v in g.container(kind).pairs:
        if M.value_of(_deref(k)) == slot:
            arr = _deref(v)
            return _deref(arr.items[0]), _deref(arr.items[1]) if len(arr.items) > 1 \
                else None
    return None, None


def main():
    doc = xj_model.Doc(xj_env.save_path())
    sv = xj_save.SaveDoc(doc=doc)
    g = xj_game.GameEditor(sv)
    print("存档:", xj_env.save_path())
    a, ac = get_slot(g, KIND, A)
    b, bc = get_slot(g, KIND, B)
    for label, it, cnt, slot in (("A", a, ac, A), ("B", b, bc, B)):
        print()
        print("=== %s：槽 %s ===" % (label, slot))
        if it is None:
            print("   （空）")
            continue
        print("   数量 =", render(cnt))
        for k, v in it.ivars:
            print("   %-18s %s" % (k, render(v)))
    if a is not None and b is not None:
        ka = [k for k, _ in a.ivars]
        kb = [k for k, _ in b.ivars]
        print()
        print("字段差异：A 多 %s / B 多 %s" % (sorted(set(ka) - set(kb)),
                                          sorted(set(kb) - set(ka))))
        for k, va in a.ivars:
            for k2, vb in b.ivars:
                if k2 != k:
                    continue
                ra, rb = render(va), render(vb)
                if ra != rb:
                    print("值不同 %s:\n   A=%s\n   B=%s" % (k, ra, rb))
    return 0


if __name__ == "__main__":
    sys.exit(main())
