# -*- coding: utf-8 -*-
"""在文件里找含某些关键词的行，只打印「行号 + 行内容」。

为什么不用 grep_search：它只搜工作区，画迹1 的仓库在工作区外；
而且终端里传中文关键词会被 GBK/引号吃掉。

用法：
    python tools/findlines.py <文件> def tab_
    python tools/findlines.py <文件> @items count
给的行内容会截断到 150 字符。
"""
import sys

sys.stdout.reconfigure(errors="replace")

path = sys.argv[1]
kws = sys.argv[2:]
if not kws:
    print("用法：python tools/findlines.py <文件> 关键词...")
    raise SystemExit(2)

n = 0
with open(path, encoding="utf-8", errors="replace") as f:
    for i, ln in enumerate(f, 1):
        s = ln.rstrip("\n")
        if any(k in s for k in kws):
            n += 1
            print("%5d | %s" % (i, s[:150]))
print("（命中 %d 行）" % n)
