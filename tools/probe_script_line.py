# -*- coding: utf-8 -*-
"""按游戏报错里的行号看脚本原文。

游戏报 `Script '0000' line 13251` 时，行号是**该脚本段自己的行号**；
我们的 dump 文件（tools\\_scripts\\*.rb）为了好看，每行代码后面插了一个空行，
所以 dump 里的行号 ≈ 真实行号 × 2。这个工具就是按真实行号取一段出来看。

用法：python tools/probe_script_line.py 13251 [上下文行数]
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.stdout.reconfigure(errors="replace")

DUMP = os.path.join(HERE, "_scripts", "0000_000015.rb")

line = int(sys.argv[1])
ctx = int(sys.argv[2]) if len(sys.argv) > 2 else 14

raw = open(DUMP, encoding="utf-8", errors="replace").read().splitlines()
# 去掉“插入的空行”：连续两行里第二行是空的那种
slim = []
for i, ln in enumerate(raw):
    if ln.strip() == "" and i + 1 < len(raw) and raw[i + 1].strip() == "":
        continue
    slim.append(ln)
# 再去掉纯插入的单个空行（每行代码后面那个）
slim2 = [ln for i, ln in enumerate(slim)
         if not (ln.strip() == "" and i + 1 < len(slim))]
print("dump 行数 %d → 去空行后 %d 行（真实行号大致就是后者）"
      % (len(raw), len(slim2)))
print("-" * 70)
for i in range(max(1, line - ctx), min(len(slim2), line + ctx) + 1):
    mark = ">>" if i == line else "  "
    print("%s %6d| %s" % (mark, i, slim2[i - 1]))
