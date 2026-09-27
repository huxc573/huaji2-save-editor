# -*- coding: utf-8 -*-
"""按真实行号打印脚本里的片段（grep 的行号看起来偏了，用这个核对）。"""
import io
import os
import sys

sys.stdout.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)        # 探针产物固定在 tools\ 下，跟脚本在不在 re\ 无关
P = os.path.join(TOOLS, "_scripts", "0000_000015.rb")
KEY = sys.argv[1] if len(sys.argv) > 1 else "cheated"
BEFORE = int(sys.argv[2]) if len(sys.argv) > 2 else 3
AFTER = int(sys.argv[3]) if len(sys.argv) > 3 else 22

lines = io.open(P, encoding="utf-8", errors="replace", newline="").read().split("\n")
print("文件 %s 共 %d 行" % (os.path.basename(P), len(lines)))
for i, ln in enumerate(lines):
    if KEY in ln:
        print("=" * 70)
        for j in range(max(0, i - BEFORE), min(len(lines), i + AFTER)):
            print("%6d| %s" % (j + 1, lines[j].rstrip("\r")))
