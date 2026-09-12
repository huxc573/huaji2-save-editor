# -*- coding: utf-8 -*-
"""对比"存档里的物品对象"和"Data 模板"，找出加进去的东西缺了什么。

用法：python tools/probe_item_diff.py [关键词]
默认关键词 = 孵化（初级孵化蛋）
"""
import os
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
import xj_save        # noqa: E402
from xj_save import _deref, ivar  # noqa: E402

KW = sys.argv[1] if len(sys.argv) > 1 else "孵化"


def type_of(n):
    n = _deref(n)
    return "nil" if n is None else getattr(n, "type", "?")


def dump_ivars(node, indent="    "):
    n = _deref(node)
    out = []
    for k, v in getattr(n, "ivars", []):
        c = _deref(v)
        cls = getattr(c, "cls", "")
        val = M.value_of(c)
        if val is None and hasattr(c, "items"):
            val = "<%s %d 项>" % (c.type, len(c.items))
        elif val is None and hasattr(c, "pairs"):
            val = "<hash %d 对>" % len(c.pairs)
        out.append("%s%-20s %-6s %s" % (indent, k, type_of(v), repr(val)[:60]))
    return out


def main():
    path = xj_env.save_path()
    doc = xj_model.Doc(path)
    sv = xj_save.SaveDoc(doc=doc)
    g = xj_game.GameEditor(sv)
    print("存档:", path)
    print()

    # 1) 每个容器里到底是些什么对象
    for key, ivname, cn, db in xj_game.KINDS:
        try:
            h = g.container(key)
        except Exception as e:
            print("[%s] 读不到：%s" % (cn, e))
            continue
        print("=== %s（%s / 名字表 %s）===" % (cn, ivname, db))
        for k, v in h.pairs:
            slot = M.value_of(_deref(k))
            arr = _deref(v)
            if not isinstance(arr, M.ArrayNode) or not arr.items:
                print("   槽 %s = %s" % (slot, type_of(v)))
                continue
            item = _deref(arr.items[0])
            cls = getattr(item, "cls", "?")
            iid = M.value_of(_deref(ivar(item, "@id")))
            nm = M.value_of(_deref(ivar(item, "@name")))
            if isinstance(nm, bytes):
                nm = nm.decode("utf-8", "replace")
            cnt = M.value_of(_deref(arr.items[1])) if len(arr.items) > 1 else None
            # 用两张表分别查名字，看哪张对得上
            hit = []
            for t in ("Items", "Weapons", "Armors"):
                try:
                    m = xj_db.name_map(t)
                except Exception:
                    m = {}
                if iid in m:
                    hit.append("%s=%s" % (t, m[iid]))
            print("   槽 %-3s %-14s id=%-4s 名称=%-14r 数量=%s  表命中: %s"
                  % (slot, cls, iid, nm, cnt, "、".join(hit) or "（两张表都没有）"))
        print()

    # 2) 找关键词对应的物品，跟模板逐字段比
    print("=== 关键词 %r 的物品 ===" % KW)
    for key, ivname, cn, db in xj_game.KINDS:
        try:
            h = g.container(key)
        except Exception:
            continue
        for k, v in h.pairs:
            arr = _deref(v)
            if not isinstance(arr, M.ArrayNode) or not arr.items:
                continue
            item = _deref(arr.items[0])
            nm = M.value_of(_deref(ivar(item, "@name")))
            if isinstance(nm, bytes):
                nm = nm.decode("utf-8", "replace")
            if not nm or KW not in nm:
                continue
            iid = M.value_of(_deref(ivar(item, "@id")))
            print("--- 存档里：%s / %s 槽 %s id=%s"
                  % (cn, nm, M.value_of(_deref(k)), iid))
            for ln in dump_ivars(item):
                print(ln)
            # 模板
            try:
                _r, items = xj_db.load("Items")
                tpl = dict(items).get(iid)
            except Exception:
                tpl = None
            if tpl is not None:
                print("--- Data 模板（RPG::Item id=%s）" % iid)
                for ln in dump_ivars(tpl):
                    print(ln)
                have = set(x[0] for x in getattr(item, "ivars", []))
                thave = set(x[0] for x in getattr(tpl, "ivars", []))
                print("--- 存档有、模板没有：%s" % sorted(have - thave))
                print("--- 模板有、存档没有：%s" % sorted(thave - have))
            else:
                print("   （Data\\Items 里没有 id=%s）" % iid)
            # 游戏自己给的同名物品（如果还有别的）也列出来比
            print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
