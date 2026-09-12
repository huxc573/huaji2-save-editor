# -*- coding: utf-8 -*-
"""看看解出来的脚本到底全不全：列 class、行数、尾部。"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, "_scripts")
out = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def main():
    path = None
    for n in sorted(os.listdir(SCRIPTS)):
        p = os.path.join(SCRIPTS, n)
        if n.endswith(".rb") and os.path.getsize(p) > 100000:
            path = p
            break
    if not path:
        out.write("[NG] 没找到大脚本文件\n")
        return 1
    raw = open(path, "rb").read()
    txt = raw.decode("utf-8", "replace")
    lines = txt.split("\n")
    out.write("文件 %s\n%d 字节 / %d 行 / 替换字符 %d 个\n"
              % (os.path.basename(path), len(raw), len(lines),
                 txt.count("\ufffd")))
    out.write("class 定义 %d 个，def %d 个，module %d 个\n"
              % (len(re.findall(r"^\s*class\s", txt, re.M)),
                 len(re.findall(r"^\s*def\s", txt, re.M)),
                 len(re.findall(r"^\s*module\s", txt, re.M))))
    out.write("\n### 所有 class / module（行号）\n")
    for i, line in enumerate(lines):
        m = re.match(r"\s*(class|module)\s+([A-Za-z_][\w:]*)", line)
        if m:
            out.write("%7d  %s %s\n" % (i + 1, m.group(1), m.group(2)))
    out.write("\n### 最后 40 行\n")
    for j in range(max(0, len(lines) - 40), len(lines)):
        out.write("%7d| %s\n" % (j + 1, lines[j][:180]))
    out.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
