# -*- coding: utf-8 -*-
"""诊断 3：还有哪些地方会判作弊 + 扫描**所有**存档（含 AutoSave）的作弊状态。

输出 tools/_diag_cheat3.txt（UTF-8）。
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
OUT = os.path.join(HERE, "_diag_cheat3.txt")
L = []


def w(s=""):
    L.append(s)


def lines_of(path):
    raw = open(path, "rb").read()
    u = raw.decode("utf-8", "replace")
    g = raw.decode("gbk", "replace")
    return (u if u.count("\ufffd") <= g.count("\ufffd") else g).split("\n")


def dump(ls, lo, hi, title):
    w("\n" + "=" * 74)
    w("### %s（第 %d-%d 行）" % (title, lo, hi))
    w("=" * 74)
    for i in range(max(0, lo - 1), min(len(ls), hi)):
        w("%6d| %s" % (i + 1, ls[i].rstrip()[:170]))


def saves():
    """所有可能是存档的文件：游戏根 save*.rvdata2 + AutoSave/*.rvdata2"""
    root = os.path.dirname(paths.save_path())
    out = []
    for n in sorted(os.listdir(root)):
        if n.lower().endswith(".rvdata2") and "save" in n.lower():
            out.append(os.path.join(root, n))
    d = os.path.join(root, "AutoSave")
    if os.path.isdir(d):
        for n in sorted(os.listdir(d)):
            if n.lower().endswith(".rvdata2"):
                out.append(os.path.join(d, n))
    return out


def main():
    fs = [os.path.join(SD, n) for n in sorted(os.listdir(SD))
          if n.endswith(".rb")]
    fs.sort(key=os.path.getsize, reverse=True)
    ls = lines_of(fs[0]) if fs else []
    dump(ls, 320, 345, "另一处判作弊（328-339）")
    dump(ls, 1160, 1190, "SHIELD 关键字检查（1168-1180）")

    w("\n" + "=" * 74)
    w("### 所有存档文件的作弊状态")
    w("=" * 74)
    for p in saves():
        try:
            sv = save.SaveDoc(p)
            g = game.GameEditor(sv)
            rows = g.anti_cheat_report()
            over = [r for r in rows if r[3]]
            kw = ""
            try:
                kw = "　keyword=%r" % (sv.system_keyword(),)
            except Exception:
                kw = ""
            w("  %-58s %s" % (os.path.relpath(p, os.path.dirname(p)),
                              "**有问题**：" + "、".join(
                                  "%s(%s)" % (r[0], r[1]) for r in over)
                              if over else "干净 ✔"))
            w("      %s 项体检，%d 项超限%s" % (len(rows), len(over), kw))
        except Exception as e:
            w("  %-58s 读不了：%s" % (os.path.basename(p), e))

    io.open(OUT, "w", encoding="utf-8", newline="").write("\n".join(L) + "\n")
    print("已写 %s（%d 行）" % (OUT, len(L)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
