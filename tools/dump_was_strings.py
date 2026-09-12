# -*- coding: utf-8 -*-
"""把 was.info（明文 Marshal）里的字符串全捞出来，找密钥线索。

输出：tools/_was.txt
"""
import os
import re
import sys

sys.stdout.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GAME = os.path.normpath(os.path.join(ROOT, "..", "..", ".."))
LOG = os.path.join(HERE, "_was.txt")

data = open(os.path.join(GAME, "was.info"), "rb").read()

L = ["大小 = %d" % len(data)]
seen = set()


def add(tag, s):
    if s in seen:
        return
    seen.add(s)
    L.append("%-8s %s" % (tag, s))


# ASCII
for m in re.finditer(rb"[\x20-\x7E]{3,}", data):
    add("ascii", m.group().decode("ascii", "replace"))
# UTF-8 中文
for m in re.finditer(rb"(?:[\xe4-\xe9][\x80-\xbf]{2}){1,20}", data):
    try:
        add("utf8", m.group().decode("utf-8"))
    except Exception:
        pass
# GBK 中文（两字节序列）
for m in re.finditer(rb"(?:[\xb0-\xf7][\xa1-\xfe]){2,20}", data):
    try:
        add("gbk", m.group().decode("gbk"))
    except Exception:
        pass

open(LOG, "w", encoding="utf-8").write("\n".join(L) + "\n")
print("done %d" % len(L))
