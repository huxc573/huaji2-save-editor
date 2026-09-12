# -*- coding: utf-8 -*-
"""看清各种文件的真实格式：是明文 Marshal、Zip，还是加密的。

输出：tools/_inspect.txt
"""
import os
import sys

sys.stdout.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GAME = os.path.normpath(os.path.join(ROOT, "..", "..", ".."))
LOG = os.path.join(HERE, "_inspect.txt")
DEC = os.path.join(HERE, "_dec")

FILES = [
    "save.rvdata2",
    "AutoSave/save00.rvdata2",
    "AutoSave/save27.rvdata2",
    "Data/main.rvdata2",
    "Data/System.rvdata2",
    "Data/Scripts.rvdata2",
    "was.info",
    "System/Game.md5",
    "System/RGSS301.dll",
]


def head(p, n=32):
    with open(p, "rb") as f:
        return f.read(n)


def guess(b):
    if b[:2] == b"\x04\x08":
        return "Marshal 4.8 (明文)"
    if b[:2] == b"PK":
        return "ZIP"
    if b[:3] == b"\xef\xbb\xbf":
        return "UTF-8 BOM 文本"
    return "未知/加密"


L = []
for rel in FILES:
    p = os.path.join(GAME, rel.replace("/", os.sep))
    if not os.path.exists(p):
        L.append("%-26s 不存在" % rel)
        continue
    b = head(p)
    L.append("%-26s %8d  %s   %s" % (rel, os.path.getsize(p), b.hex(" "), guess(b)))

L.append("")
L.append("== System/Game.md5 解密后的内容 ==")
p = os.path.join(DEC, "System_Game.md5.bin")
if os.path.exists(p):
    raw = open(p, "rb").read()
    L.append("长度 = %d" % len(raw))
    try:
        L.append("文本: %r" % raw.decode("ascii", "replace"))
    except Exception as e:
        L.append("解码失败 %s" % e)
else:
    L.append("（没解密结果）")

L.append("")
L.append("== Data/main.rvdata2 原文 ==")
p = os.path.join(GAME, "Data", "main.rvdata2")
L.append(head(p, 70).hex(" "))

L.append("")
L.append("== save.rvdata2 前 64 字节 ==")
L.append(head(os.path.join(GAME, "save.rvdata2"), 64).hex(" "))

open(LOG, "w", encoding="utf-8").write("\n".join(L) + "\n")
print("done")
