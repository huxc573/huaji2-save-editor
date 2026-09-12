# -*- coding: utf-8 -*-
"""优先试"数字型"候选密钥（Data 密钥 761205 就是 6 位数字）。

从解壳镜像 / Game.exe / main.dll 原文里抽出所有 2..16 位的纯数字串，
再加上一些变形，先打一遍 —— 数量小，跑得快。

输出：tools/_digits_out.txt
"""
import os
import re
import sys

sys.stdout.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GAME = os.path.normpath(os.path.join(ROOT, "..", "..", ".."))
CAND = os.path.join(HERE, "_digits.txt")
LOG = os.path.join(HERE, "_digits_out.txt")

TARGETS = [
    os.path.join(GAME, "Data", "Scripts.rvdata2"),
    os.path.join(GAME, "save.rvdata2"),
]

blobs = []
for p in [os.path.join(HERE, "_ours_main.bin"),
          os.path.join(GAME, "Game.exe"),
          os.path.join(GAME, "System", "main.dll"),
          os.path.join(GAME, "System", "RGSS301.dll"),
          os.path.join(GAME, "was.info")]:
    if os.path.exists(p):
        blobs.append(open(p, "rb").read())

cands = set()
for b in blobs:
    for m in re.finditer(rb"[0-9]{2,16}", b):
        s = m.group().decode("ascii")
        cands.add(s)
        for L in range(3, len(s) + 1):
            for i in range(0, len(s) - L + 1):
                cands.add(s[i:i + L])

# 也加点"像密钥"的短串
for b in blobs[:1]:
    for m in re.finditer(rb"[0-9A-Za-z_]{3,12}", b):
        cands.add(m.group().decode("ascii"))

cands = sorted(c for c in cands if 2 <= len(c) <= 16)
with open(CAND, "w", encoding="utf-8") as f:
    f.write("\n".join(cands) + "\n")
print("候选 %d" % len(cands))

sys.path.insert(0, HERE)
from run_brute import run_brute  # noqa: E402

hits = run_brute(CAND, TARGETS, os.path.join(HERE, "_digits"), LOG)
print("hits = %r" % hits)
