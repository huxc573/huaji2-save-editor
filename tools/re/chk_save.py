# -*- coding: utf-8 -*-
"""一次性：快速打印指定存档里每个角色的等级/经验/累计经验，用来比对备份。"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import game  # noqa: E402
import save  # noqa: E402

for p in sys.argv[1:]:
    doc = save.SaveDoc(p)
    sv = doc
    g = game.GameEditor(doc)
    print("### %s" % os.path.basename(p))
    for _i, a in sv.actors():
        print("   %-6s lv=%-3s exp=%-12s lim=%-12s"
              % (sv.actor_name(a), g.actor_level(a), g.exp(a),
                 g.limit_exp(a)))
