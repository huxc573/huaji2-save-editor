# -*- coding: utf-8 -*-
"""把仓库里的文本文件统一成 LF（仓库历史存的就是 LF）。

用法：
    python tools/normalize_eol.py          # 干活
    python tools/normalize_eol.py --dry    # 只列清单

为什么要有这个：本仓库 `core.autocrlf=false`，一旦某个文件在工作区被写成 CRLF，
git 就会把它当**整文件改动**，diff 没法看、评审没法做。

扫的是工作区（不是 `git ls-files`）—— 这样连「刚要入库还没 add」的新文件也一起管。
二进制、带 BOM 的、被 .gitignore 忽略的中间产物都跳过。
"""
import os
import sys

sys.stdout.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DRY = "--dry" in sys.argv
os.chdir(ROOT)

BIN_EXT = {".exe", ".dll", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".bmp",
           ".rvdata2", ".ogg", ".wav", ".mp3", ".was", ".zip", ".7z", ".pdf",
           ".pyc", ".pyd", ".so", ".bin", ".dat", ".md5"}
SKIP_DIRS = {".git", "__pycache__", "build", "dist", "_tmp", ".vs", ".idea"}

changed = []
for dp, dns, fns in os.walk(ROOT):
    dns[:] = [d for d in dns if d not in SKIP_DIRS]
    for fn in fns:
        if os.path.splitext(fn)[1].lower() in BIN_EXT:
            continue
        p = os.path.join(dp, fn)
        rel = os.path.relpath(p, ROOT)
        try:
            b = open(p, "rb").read()
        except OSError:
            continue
        if b"\0" in b or b"\r\n" not in b:
            continue                    # 二进制 / 本来就是 LF
        if b.startswith(b"\xef\xbb\xbf"):
            print("  ! 带 BOM，跳过（先手工确认）：%s" % rel)
            continue
        nb = b.replace(b"\r\n", b"\n")
        changed.append((rel, b.count(b"\r\n")))
        if not DRY:
            open(p, "wb").write(nb)

print("%s%d 个文件%s" % ("将要转 LF：" if DRY else "已转 LF：", len(changed),
                        "（--dry 预演，没写盘）" if DRY else ""))
for rel, n in changed:
    print("   %-52s %d 行" % (rel, n))
