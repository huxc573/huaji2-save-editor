# -*- coding: utf-8 -*-
"""看文件末尾 N 行（编码自动猜，终端不乱码）。

用法：python tools/tail.py <文件> [行数]
"""
import io
import sys

sys.stdout.reconfigure(errors="replace")

path = sys.argv[1]
n = int(sys.argv[2]) if len(sys.argv) > 2 else 40

raw = open(path, "rb").read()
for enc in ("utf-8", "gbk", "latin-1"):
    try:
        txt = raw.decode(enc)
        break
    except UnicodeDecodeError:
        continue
lines = txt.splitlines()
print("（%s：共 %d 行，显示最后 %d 行）" % (path, len(lines), n))
print("-" * 70)
print("\n".join(lines[-n:]))
