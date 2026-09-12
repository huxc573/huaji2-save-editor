# -*- coding: utf-8 -*-
"""逐个看背包里“运行时内容”物品的 @attr 现状（孵化蛋、要诀、礼包…）。

用法：python tools/probe_payload_now.py [--fix]
    --fix：在**存档副本**上跑一遍“一键修复”，看看修完变成什么样（不动原档）。
"""
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.stdout.reconfigure(errors="replace")

import xj_db          # noqa: E402
import xj_env         # noqa: E402
import xj_game        # noqa: E402
import xj_marshal as M  # noqa: E402
import xj_model       # noqa: E402
import xj_payload     # noqa: E402
import xj_save        # noqa: E402

FIX = "--fix" in sys.argv
WORK = os.path.join(HERE, "_payload")


def render(node, depth=0):
    n = xj_save._deref(node)
    if n is None or isinstance(n, M.NilNode):
        return "nil"
    if isinstance(n, M.HashNode):
        return "{%s}" % ", ".join("%s=>%s" % (render(k, depth + 1),
                                              render(v, depth + 1))
                                  for k, v in n.pairs)
    if isinstance(n, M.ArrayNode):
        return "[%s]" % ", ".join(render(x, depth + 1) for x in n.items)
    if isinstance(n, M.SymbolNode):
        return ":%s" % n.name
    v = M.value_of(n)
    return repr(v)


def main():
    real = xj_env.save_path()
    path = real
    if FIX:
        shutil.rmtree(WORK, ignore_errors=True)
        os.makedirs(WORK, exist_ok=True)
        path = os.path.join(WORK, "copy.rvdata2")
        shutil.copyfile(real, path)
    print("存档:", path, "（--fix：在副本上操作）" if FIX else "")

    doc = xj_model.Doc(path)
    sv = xj_save.SaveDoc(doc=doc)
    g = xj_game.GameEditor(sv)

    def dump(tag):
        print("\n=== %s ===" % tag)
        for kind, _iv, cn, _db in xj_game.KINDS:
            for slot, _p, _i, iid, nm, cnt in g.bag(kind):
                need, nm2 = g.item_needs_payload(kind, iid)
                if not need:
                    continue
                it = g._item_node(kind, slot)
                t, d = g.item_payload(it)
                kk = ""
                try:
                    a = xj_save._deref(xj_save.ivar(it, "@attr"))
                    if a is not None and a.pairs:
                        kd = xj_save._deref(a.pairs[0][0])
                        kk = "键=%s%s" % (type(kd).__name__,
                                         "（游戏读不到！）"
                                         if not g.payload_key_ok(it) else "")
                except Exception:
                    pass
                print("  [%-3s] 槽 %-3s %-12s ×%-3s type=%-16s %s data=%s"
                      % (cn, slot, nm, cnt, t, kk,
                         render(d) if d is not None
                         else "（空，游戏里会少提示/报错）"))
                if t and d is not None:
                    kid = M.value_of(xj_save._deref(xj_save.hash_get(d, "id")))
                    if kid and "孵化蛋" in (nm2 or ""):
                        acts = {}
                        try:
                            _r, items = xj_db.load("Actors")
                            acts = dict((i, xj_db.s(n, "@name"))
                                        for i, n in items)
                        except Exception:
                            pass
                        print("         → 诞生对象 id=%s（%s）"
                              % (kid, acts.get(kid, "?")))

    dump("修复前")
    rows = g.pack_report()
    pay = [r for r in rows if r[5].get("payload")]
    print("\n体检里“缺运行时内容”的：%d 项" % len(pay))
    for r in pay:
        print("   [%s] 槽 %s %s" % (r[0], r[1], r[2]))

    if FIX:
        done = g.pack_fix(rows)
        print("\n一键修复：%d 项" % len(done))
        for d in done:
            print("   ", d)
        dump("修复后")
        sv.doc.save()
        print("\n已保存到副本：", path)
        sv2 = xj_save.SaveDoc(path)
        g2 = xj_game.GameEditor(sv2)
        print("重开后复查：")
        for kind, _iv, cn, _db in xj_game.KINDS:
            for slot, _p, _i, iid, nm, cnt in g2.bag(kind):
                need, _ = g2.item_needs_payload(kind, iid)
                if not need:
                    continue
                t, d = g2.item_payload(g2._item_node(kind, slot))
                print("  [%-3s] 槽 %-3s %-12s type=%s data=%s"
                      % (cn, slot, nm, t, render(d) if d is not None else "（空）"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
