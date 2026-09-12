# -*- coding: utf-8 -*-
"""诊断 Marshal 解析错位：打印出错点前的解析轨迹。

用法：python tools/parse_diag.py <明文文件> [出错偏移]
输出：tools/_diag.txt
"""
import os
import sys

sys.stdout.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
import xj_marshal  # noqa: E402

LOG = os.path.join(HERE, "_diag.txt")
path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    HERE, "_dec", "save.rvdata2.bin")
data = open(path, "rb").read()

p = xj_marshal.Parser(data, 0)
p.trace = []
p.i = 2 if data[:2] == b"\x04\x08" else 0
L = ["文件 = %s (%d 字节)" % (path, len(data))]
objs = 0
try:
    while p.i < len(data):
        p.links = []
        p.symbols = []
        if data[p.i:p.i + 2] == b"\x04\x08":
            p.i += 2
        start = p.i
        node = p.read_object()
        objs += 1
        L.append("顶层对象 #%d @%d..%d  根类型=%s" %
                 (objs, start, p.i, type(node).__name__))
except Exception as e:
    L.append("解析失败: %s" % e)
    # 把递归调用链上的 start 局部变量挖出来 —— 这样不用改解析器也能看到"套娃"结构
    import traceback
    tb = sys.exc_info()[2]
    chain = []
    while tb is not None:
        fr = tb.tb_frame
        if "start" in fr.f_locals:
            chain.append((fr.f_code.co_name, fr.f_locals["start"],
                          fr.f_locals.get("c"), tb.tb_lineno))
        tb = tb.tb_next
    L.append("调用链（由外到内）共 %d 层：" % len(chain))
    for i, (fn, st, cc, ln) in enumerate(chain[-40:]):
        L.append("   %2d) %-14s start=%-8d 类型=%r" % (i, fn, st, cc))
    L.append("轨迹条数 = %d" % len(p.trace))
    L.append("---- 最后 120 步 ----")
    for off, c in p.trace[-120:]:
        shown = repr(c)
        if c.isprintable() and c not in "'\\":
            shown = "'%s'" % c
        L.append("  @%-8d %-6s 以下 12 字节: %s" %
                 (off, shown, data[off:off + 12].hex(" ")))
    import re as _re
    m = _re.search(r"@(\d+)", str(e))
    if m:
        fail = int(m.group(1))
        a, b = max(0, fail - 96), min(len(data), fail + 96)
        L.append("---- 出错点 @%d 附近 ----" % fail)
        for off in range(a, b, 16):
            row = data[off:off + 16]
            L.append("  @%-8d %-47s %s" % (
                off, row.hex(" "),
                "".join(chr(x) if 32 <= x < 127 else "." for x in row)))

open(LOG, "w", encoding="utf-8").write("\n".join(L) + "\n")
print("\n".join(L[:3]))
