# -*- coding: utf-8 -*-
"""诊断 2：游戏到底在哪儿判作弊（把所有 `cheated` 相关代码挖出来）+ 看存档现状。

输出 tools/_diag_cheat2.txt（UTF-8）。
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)        # 探针产物固定在 tools\ 下，跟脚本在不在 re\ 无关
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.stdout.reconfigure(errors="replace")

import paths         # noqa: E402
import game        # noqa: E402
import save        # noqa: E402

SD = os.path.join(TOOLS, "_scripts")
OUT = os.path.join(HERE, "_diag_cheat2.txt")
L = []


def w(s=""):
    L.append(s)


def lines_of(path):
    raw = open(path, "rb").read()
    u = raw.decode("utf-8", "replace")
    g = raw.decode("gbk", "replace")
    return (u if u.count("\ufffd") <= g.count("\ufffd") else g).split("\n")


def main():
    fs = [os.path.join(SD, n) for n in sorted(os.listdir(SD))
          if n.endswith(".rb")]
    fs.sort(key=os.path.getsize, reverse=True)
    ls = lines_of(fs[0]) if fs else []
    w("脚本 %s（%d 行）" % (os.path.basename(fs[0]) if fs else "?", len(ls)))

    w("\n" + "=" * 74)
    w("### 所有出现 cheated / VNE 的地方")
    w("=" * 74)
    rx = re.compile(r"cheated|VNE|keyword")
    for i, l in enumerate(ls):
        if rx.search(l):
            w("%6d| %s" % (i + 1, l.rstrip()[:165]))

    w("\n" + "=" * 74)
    w("### 周期检查那一整段（29420-29496）")
    w("=" * 74)
    for i in range(29419, min(len(ls), 29496)):
        w("%6d| %s" % (i + 1, ls[i].rstrip()[:165]))

    # ---- 存档现状
    w("\n" + "=" * 74)
    w("### 存档现状")
    w("=" * 74)
    sv = save.SaveDoc(paths.save_path())
    g = game.GameEditor(sv)
    for r in g.anti_cheat_report():
        w("  %s %-30s 当前 %-12s 上限 %-12s %s"
          % ("[超限]" if r[3] else "[ OK ]", r[0], r[1], r[2], r[4]))
    # 直接把 @cheated 读出来
    for name in ("@cheated", "@keyword", "@security"):
        try:
            node = sv.system_ivar(name) if hasattr(sv, "system_ivar") else None
        except Exception:
            node = None
        if node is not None:
            w("  %s = %r" % (name, node))

    io.open(OUT, "w", encoding="utf-8", newline="").write("\n".join(L) + "\n")
    print("已写 %s（%d 行）" % (OUT, len(L)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
