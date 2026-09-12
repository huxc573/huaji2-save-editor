# -*- coding: utf-8 -*-
"""在导出的脚本里按关键字打印上下文窗口（脚本被混淆成超长行，按字符取窗口最稳）。

用法：python tools/grep_ctx.py <关键字> [窗口字符数]
输出：tools/_ctx.txt
"""
import os
import re
import sys

sys.stdout.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
SC = os.path.join(HERE, "_scripts")
LOG = os.path.join(HERE, "_ctx.txt")

pat = sys.argv[1]
win = int(sys.argv[2]) if len(sys.argv) > 2 else 700

L = ["关键字 = %r  窗口 = %d" % (pat, win)]
rx = re.compile(pat)
for fn in sorted(os.listdir(SC)):
    if not fn.endswith(".rb"):
        continue
    txt = open(os.path.join(SC, fn), encoding="utf-8", errors="replace").read()
    for m in rx.finditer(txt):
        a = max(0, m.start() - win)
        b = min(len(txt), m.end() + win)
        L.append("==== %s @%d ====" % (fn, m.start()))
        L.append(txt[a:b].replace("\r", "\\r"))
open(LOG, "w", encoding="utf-8").write("\n".join(L) + "\n")
print("命中 %d 段" % (len(L) - 1))
