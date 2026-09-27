# -*- coding: utf-8 -*-
"""一次性：用真实存档核对「升级所需经验」的修法对不对（只读，不写盘）。"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import paths  # noqa: E402
import game  # noqa: E402
import save  # noqa: E402

real = paths.save_path()
doc = save.SaveDoc(real)
g = game.GameEditor(doc)
sv = doc

print("%-8s %-6s %-12s %-14s %-14s %s" % ("名字", "等级", "本级经验", "升级所需(查表)",
                                          "累计获得", "还差"))
for aid, actor in sv.actors():
    name = sv.actor_name(actor)
    lv = g.actor_level(actor)
    cur = g.exp(actor)
    nxt = g.next_level_exp(actor)
    lim = g.limit_exp(actor)
    gap = "" if nxt is None else max(0, nxt - cur)
    print("%-8s %-6s %-12s %-14s %-14s %s"
          % (name, lv, cur, nxt, lim, gap))

print()
print("期望：乐天凌 40 级 → 升级所需 = 332296（游戏界面上显示的那个数）")
print("期望：没入过队的角色 → 累计获得 = 0（不再是空白）")
