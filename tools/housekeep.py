# -*- coding: utf-8 -*-
"""整理：把非游戏文件搬出游戏目录。

  1) <游戏根>\.venv                -> <游戏根>\!Tools\Github\.venv
  2) 删除 <游戏根>\save.rvdata2.xj_plain 等我们产生的残留
  3) 报告结果

用法： python tools/housekeep.py [--dry]
"""
import os
import shutil
import sys

sys.stdout.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GITHUB = os.path.dirname(ROOT)
GAME = os.path.normpath(os.path.join(ROOT, "..", "..", ".."))
OUT = os.path.join(HERE, "_housekeep.txt")

DRY = "--dry" in sys.argv

# 我们（探针/工具）在游戏根可能留下的垃圾：文件名前缀/后缀特征
JUNK_SUFFIX = (".xj_plain", ".xj_new", ".plain", ".enc", ".bak")
JUNK_PREFIX = ("_xj", "xj_")


def move(src, dst):
    if os.path.exists(dst):
        return "[跳过] 目标已存在：%s" % dst
    if DRY:
        return "[dry] %s -> %s" % (src, dst)
    shutil.move(src, dst)
    return "[搬走] %s -> %s" % (src, dst)


def main():
    L = []
    L.append("GAME   = %s" % GAME)
    L.append("GITHUB = %s" % GITHUB)

    L.append("\n== 1. .venv ==")
    v = os.path.join(GAME, ".venv")
    target = os.path.join(GITHUB, ".venv")
    if os.path.isdir(v):
        try:
            L.append("  " + move(v, target))
        except Exception as e:
            L.append("  [失败] %s  （可能被占用）" % e)
    else:
        L.append("  游戏根没有 .venv")

    L.append("\n== 2. 清理残留 ==")
    for name in sorted(os.listdir(GAME)):
        p = os.path.join(GAME, name)
        if not os.path.isfile(p):
            continue
        if name.endswith(JUNK_SUFFIX) or name.startswith(JUNK_PREFIX):
            if name.startswith("save.rvdata2.bak"):
                L.append("  [保留] %s（存档备份）" % name)
                continue
            if DRY:
                L.append("  [dry] 删除 %s" % name)
            else:
                os.remove(p)
                L.append("  [删除] %s" % name)

    L.append("\n== 3. 之后游戏根的非预期文件 ==")
    EXPECTED = {"Audio", "AutoSave", "Data", "Fonts", "Graphics", "Logs", "System",
                "Config.ini", "Game.exe", "Game.ini", "save.rvdata2", "was.info",
                "!Tools", ".vscode"}
    extra = [n for n in sorted(os.listdir(GAME)) if n not in EXPECTED]
    L.append("  %s" % (extra or "无"))

    open(OUT, "w", encoding="utf-8").write("\n".join(L))
    print("done")


if __name__ == "__main__":
    main()
