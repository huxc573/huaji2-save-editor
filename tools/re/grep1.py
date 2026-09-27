# -*- coding: utf-8 -*-
"""在**任意路径**的文件里搜关键词（工作区外的 huaji1 仓库也能搜）。

工作区外的文件 grep_search 够不到，所以自己写一个：中文关键词放代码里最安全。

用法：python tools/_grep1.py <文件> <关键词1,关键词2,...> [上下文行数]
输出：直接打屏（UTF-8）。
"""
import io
import sys

sys.stdout.reconfigure(errors="replace")

path = sys.argv[1]
kws = [x for x in sys.argv[2].split(",") if x]
ctx = int(sys.argv[3]) if len(sys.argv) > 3 else 2

raw = open(path, "rb").read()
u = raw.decode("utf-8", "replace")
g = raw.decode("gbk", "replace")
lines = (u if u.count("\ufffd") <= g.count("\ufffd") else g).split("\n")
print("== %s（共 %d 行）" % (path, len(lines)))
for kw in kws:
    hits = [i for i, l in enumerate(lines) if kw in l]
    print("\n### %s → %d 处" % (kw, len(hits)))
    last = -99
    for i in hits:
        if i - last > ctx * 2 + 1:
            print("  " + "-" * 60)
        last = i
        for j in range(max(0, i - ctx), min(len(lines), i + ctx + 1)):
            print("%6d| %s" % (j + 1, lines[j].rstrip()[:150]))
