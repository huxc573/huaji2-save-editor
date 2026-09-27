# -*- coding: utf-8 -*-
"""从解包脚本里提取"被动技能互斥组"（第二版：全量上下文 dump）。

把脚本里所有 `is_passive?($skills[:X])` 出现处按块 dump 出来，
再人工归纳互斥组 / 优先级。

输出：tools/_skill_excl_raw.txt
"""
import os
import re
import sys

sys.stdout.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)        # 探针产物固定在 tools\ 下，跟脚本在不在 re\ 无关
SRC = os.path.join(TOOLS, "_scripts", "0000_000015.rb")
OUT = os.path.join(HERE, "_skill_excl_raw.txt")

lines = open(SRC, encoding="utf-8", errors="replace").read().split("\n")
N = len(lines)

SK = re.compile(r"is_passive\?\(\$skills\[:([^\]]+)\]\)")

# 每处命中的行号
hit_lines = []
for i, ln in enumerate(lines):
    if SK.search(ln):
        hit_lines.append(i)

# 合并成连续块（块内行距 <= 4 视为同一块）
blocks = []
for i in hit_lines:
    if blocks and i - blocks[-1][-1] <= 4:
        blocks[-1].append(i)
    else:
        blocks.append([i])

out = []
def w(s=""):
    out.append(s)

w("共 %d 处 is_passive，分成 %d 块" % (len(hit_lines), len(blocks)))
w("")
for bi, blk in enumerate(blocks):
    lo, hi = max(0, blk[0] - 1), min(N, blk[-1] + 2)
    w("=" * 78)
    w("块#%02d 行 %d..%d（%d 行）" % (bi, lo + 1, hi, hi - lo))
    w("=" * 78)
    for j in range(lo, hi):
        tag = ">>" if j in blk else "  "
        w("%s%5d| %s" % (tag, j + 1, lines[j].rstrip()[:220]))
    w("")

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(out) + "\n")
print("已写出 %s" % OUT)
