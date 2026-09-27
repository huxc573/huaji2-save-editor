# -*- coding: utf-8 -*-
"""看一眼「防作弊体检」每一项的结果（哪个超限了）。

用法：python tools/probe_guard.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.stdout.reconfigure(errors="replace")

import paths          # noqa: E402
import doctree        # noqa: E402
import save         # noqa: E402
import game         # noqa: E402


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else paths.save_path()
    doc = doctree.Doc(path)
    sv = save.SaveDoc(doc=doc)
    g = game.GameEditor(sv)
    print("存档:", path)
    print("%-28s %-14s %-14s %s" % ("项目", "当前", "上限", "状态"))
    for row in g.anti_cheat_report():
        name, cur, lim, bad = row[0], row[1], row[2], row[3]
        print("%-28s %-14s %-14s %s" % (name, cur, lim, "超限!" if bad else "OK"))
    print()
    print("物品计数校验（物品id, 名称, 游戏记录, 背包实际）:")
    for iid, name, sec, act in g.security_rows():
        flag = "" if sec == act else "   <-- 不一致!"
        print("    #%-4s %-14s 记录=%-4s 实际=%-4s%s" % (iid, name, sec, act, flag))
    print("背包实际计数 item_counts:", g.item_counts())
    return 0


if __name__ == "__main__":
    sys.exit(main())
