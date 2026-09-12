# -*- coding: utf-8 -*-
"""把 Data\main.rvdata2（明文 Marshal）里的 zlib 脚本正文解出来看。

输出：tools/_boot.txt 和 tools/_boot.rb
"""
import os
import re
import sys
import zlib

sys.stdout.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GAME = os.path.normpath(os.path.join(ROOT, "..", "..", ".."))
LOG = os.path.join(HERE, "_boot.txt")
SRC = os.path.join(GAME, "Data", "main.rvdata2")

data = open(SRC, "rb").read()
L = ["文件大小 = %d" % len(data), "前 16 字节 = " + data[:16].hex(" ")]

out = b""
for m in re.finditer(rb"\x78[\x01\x5e\x9c\xda]", data):
    try:
        d = zlib.decompressobj().decompress(data[m.start():])
        L.append("[zlib] 偏移 %d 解出 %d 字节" % (m.start(), len(d)))
        out += d + b"\n\n"
    except Exception as e:
        L.append("[zlib] 偏移 %d 失败: %r" % (m.start(), e))

txt = out.decode("utf-8", "replace")
L.append("总解出 = %d 字节" % len(out))
L.append("---- 正文 ----")
L.append(txt)

open(LOG, "w", encoding="utf-8").write("\n".join(L) + "\n")
open(os.path.join(HERE, "_boot.rb"), "wb").write(out)
print("done %d" % len(out))
