# -*- coding: utf-8 -*-
"""给外部文件打"目录"：列出 class / def / 关键调用行号，方便按行号精读。

本工作区路径含 `!` `【】`，命令行传路径会被 PowerShell 搞坏，所以脚本**自己找**
huaji1 仓库的位置（从自身位置往上找到游戏根，再在同级目录里找 `【画迹1*`）。

用法：python tools/outline.py [要看的文件] [--grep 关键字]
    不带参数就看 huaji1 的 src/xj_viewer.py
输出：tools/_outline.txt
"""
import os
import re
import sys

sys.stdout.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                 # huaji2-save-editor
GITHUB = os.path.dirname(ROOT)               # !Tools/Github
TOOLS = os.path.dirname(GITHUB)              # !Tools
GAME = os.path.dirname(TOOLS)                # 游戏根
PARENT = os.path.dirname(GAME)               # 画迹/
LOG = os.path.join(HERE, "_outline.txt")


def find_huaji1():
    """在同级目录里找 【画迹1* 下的 huaji1-save-editor。"""
    try:
        names = sorted(os.listdir(PARENT))
    except OSError:
        return None
    for n in names:
        if n.startswith("【画迹1"):
            p = os.path.join(PARENT, n, "!Tools", "Github", "huaji1-save-editor")
            if os.path.isdir(p):
                return p
    return None


PAT = re.compile(r"^\s*(?:class\s+\w+|def\s+\w+|\w+\s*=\s*(?:ttk|tk)\.|"
                 r".*\bnb\.add\b|.*Notebook\(|.*\.title\(|.*geometry\(|"
                 r".*Style\(|.*Treeview\(|.*Listbox\(|.*Text\(|"
                 r".*bind\(|.*command=|.*columns=)")

args = [a for a in sys.argv[1:] if not a.startswith("--")]
kw = None
if "--grep" in sys.argv:
    kw = sys.argv[sys.argv.index("--grep") + 1]
    args = [a for a in args if a != kw]

if args:
    target = args[0]
else:
    h1 = find_huaji1()
    if not h1:
        print("找不到 huaji1 仓库（在 %s 下扫 【画迹1*）" % PARENT)
        sys.exit(1)
    target = os.path.join(h1, "src", "xj_viewer.py")

lines = open(target, encoding="utf-8", errors="replace").read().splitlines()
out = ["文件 = %s" % target, "总行数 = %d" % len(lines), ""]
for i, ln in enumerate(lines, 1):
    if kw:
        if kw.lower() in ln.lower():
            out.append("%5d| %s" % (i, ln.rstrip()))
    elif PAT.match(ln):
        out.append("%5d| %s" % (i, ln.rstrip()))
open(LOG, "w", encoding="utf-8").write("\n".join(out) + "\n")
print("共 %d 行，命中 %d 行，详见 %s" % (len(lines), len(out) - 3, LOG))
