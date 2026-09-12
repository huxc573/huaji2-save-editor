# -*- coding: utf-8 -*-
"""列出 Data\\Actors 里的召唤兽（含备注），用来给孵化蛋挑"该孵出什么"。

用法：python tools/probe_babies.py
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.stdout.reconfigure(errors="replace")

import xj_db  # noqa: E402


def main():
    _root, items = xj_db.load("Actors")
    print("Actors 共 %d 行" % len(items))
    for i, node in items:
        nm = xj_db.s(node, "@name")
        note = (xj_db.s(node, "@note") or "").replace("\r\n", " | ")
        if any(k in (note or "") for k in ("蛋", "资质", "召唤", "幼")):
            print("  #%-4s %-12s %s" % (i, nm, note[:90]))
    print()
    print("--- 蛋 id → 候选召唤兽（游戏里的 rand(...) 范围）---")
    for eid in (110, 111, 112, 113, 114):
        print("蛋 id=%d：见上方脚本 BabyManager（110:21-23,25-63 / 111:64-95,127-134"
              " / 112:96-126 / 113+:备注 神兽资质）" % eid)
    print()
    print("--- 备注里带“资质”的行 ---")
    for i, node in items:
        note = xj_db.s(node, "@note") or ""
        if "资质" in note:
            print("  #%-4s %-12s %s" % (i, xj_db.s(node, "@name"),
                                        note.replace("\r\n", " | ")[:80]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
