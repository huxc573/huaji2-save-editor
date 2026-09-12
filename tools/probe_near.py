# -*- coding: utf-8 -*-
"""在 main.dll 里「761205」附近（RVA 0x118850）挖候选密钥，直接对
Data\\Scripts.rvdata2 和存档做小规模爆破。

思路：Data 数据库的密钥 761205 就藏在解壳镜像 RVA 0x118850，
      同族的密钥（脚本/存档用）很可能就在附近。

输出：tools/_near.txt
"""
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GAME = os.path.normpath(os.path.join(ROOT, "..", "..", ".."))
HOST = os.path.join(ROOT, "src", "XJCodec32.exe")
DLL = os.path.join(GAME, "System", "main.dll")
DUMP = os.path.join(HERE, "_ours_main.bin")
CAND = os.path.join(HERE, "_near.txt")
LOG = os.path.join(HERE, "_near_out.txt")

TARGETS = [
    os.path.join(GAME, "Data", "Scripts.rvdata2"),
    os.path.join(GAME, "save.rvdata2"),
]

dump = open(DUMP, "rb").read()

cands = set()
REGIONS = [(0x110000, 0x11A000), (0x0A0000, 0x0C0000)]

# 1) 区域里的 ASCII 串
for a, b in REGIONS:
    seg = dump[a:b]
    for m in re.finditer(rb"[\x20-\x7E]{3,40}", seg):
        s = m.group().decode("ascii", "replace")
        cands.add(s)
        # 2) 所有 3..12 长度子串
        for L in range(3, min(13, len(s) + 1)):
            for i in range(0, len(s) - L + 1):
                cands.add(s[i:i + L])

# 3) 已知密钥的变形
base = "761205"
for pre in ("", "s", "S", "xjy", "hj", "save", "Save", "SAVE"):
    for suf in ("", "s", "S", "save", "Save", "SAVE", "xjy", "0", "1",
                "_save", "-save", "save_", "data", "Data"):
        cands.add(pre + base + suf)
        cands.add(pre + base + suf + base)

cands = sorted(c for c in cands if c and len(c) <= 48)
with open(CAND, "w", encoding="utf-8") as f:
    f.write("\n".join(cands) + "\n")
print("候选 %d" % len(cands))

sys.path.insert(0, HERE)
from run_brute import run_brute  # noqa: E402

hits = run_brute(CAND, TARGETS, os.path.join(HERE, "_near"), LOG)
print("hits = %r" % hits)
