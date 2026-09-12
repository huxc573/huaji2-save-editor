# -*- coding: utf-8 -*-
"""按路径删文件/目录（仓库内的相对路径）。

为什么需要它：本工作区路径含 `!` `【】[]`，在 PowerShell 里
`!` 会被转义搞坏、中文文件名会被吃成乱码，`Remove-Item` 经常删不掉。
用 Python 走 `os.remove` 最稳。

用法：
    python tools/rmfile.py tests/test_gui_quick.py
    python tools/rmfile.py tools/_gui --dir
"""
import os
import shutil
import sys

sys.stdout.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
as_dir = "--dir" in sys.argv

for rel in [a for a in sys.argv[1:] if not a.startswith("--")]:
    p = os.path.join(ROOT, rel.replace("/", os.sep))
    if not os.path.exists(p):
        print("[-- ] %s（不存在）" % rel)
        continue
    if as_dir or os.path.isdir(p):
        shutil.rmtree(p, ignore_errors=True)
    else:
        os.remove(p)
    print("[del] %s" % rel)
