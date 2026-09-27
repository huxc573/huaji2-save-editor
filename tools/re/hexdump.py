# -*- coding: utf-8 -*-
"""十六进制转储小工具。

用法：python tools/hexdump.py <文件> [起始] [长度] [--out 文件]
输出：tools/_hex.txt
"""
import os
import sys

sys.stdout.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "_hex.txt")

path = sys.argv[1]
start = int(sys.argv[2], 0) if len(sys.argv) > 2 else 0
length = int(sys.argv[3], 0) if len(sys.argv) > 3 else 256

data = open(path, "rb").read()
a = max(0, start)
b = min(len(data), a + length)
L = ["文件 = %s (%d 字节)  区间 = %d..%d" % (path, len(data), a, b)]
for off in range(a, b, 16):
    row = data[off:off + 16]
    L.append("%08X  %-47s  %s" % (
        off, " ".join("%02x" % x for x in row),
        "".join(chr(x) if 32 <= x < 127 else "." for x in row)))
open(LOG, "w", encoding="utf-8").write("\n".join(L) + "\n")
print("done %d 字节" % (b - a))
