# -*- coding: utf-8 -*-
"""统计存档明文里 'I' 包装符号的写法（I :name {E=>true} / I ;N {E=>true}）。

用法：python tools/probe_isym.py [--out 文件]
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.stdout.reconfigure(errors="replace")

import xj_env  # noqa: E402
import xj_model  # noqa: E402

out = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def main():
    global out
    if "--out" in sys.argv:
        out = open(sys.argv[sys.argv.index("--out") + 1], "w", encoding="utf-8")
    doc = xj_model.Doc(xj_env.save_path())
    buf = doc.raw
    out.write("明文 %d 字节\n" % len(buf))

    for tag, pat in (("I:  (符号定义+ivar)", b"I:"),
                     ("I;  (符号链接+ivar)", b"I;"),
                     ("I\"  (字符串+ivar)", b'I"'),
                     ("I@  (对象链接+ivar)", b"I@")):
        idxs = [m.start() for m in re.finditer(re.escape(pat), buf)]
        out.write("\n%s 出现 %d 次\n" % (tag, len(idxs)))
        for i in idxs[:6]:
            out.write("  @0x%06X  %r\n" % (i, buf[i:i + 28]))

    # 看一个具体的 I :@体质 附近
    m = re.search(b"I:\x0c@\xe4\xbd\x93\xe8\xb4\xa8", buf)
    if m:
        s = m.start()
        out.write("\n### I :@体质 上下文 @0x%06X\n  %r\n" % (s, buf[s:s + 24]))
        out.write("  → 符号名长度 %d，后面是 %r（ivar 个数 + :E + 值）\n"
                  % (buf[s + 2], buf[s + 2 + 1 + buf[s + 2]:s + 2 + 1 + buf[s + 2] + 6]))
    # 有没有"非 ASCII 符号但**没有** I 包装"的情况
    bad = 0
    for m in re.finditer(b":", buf):
        i = m.start()
        n = buf[i + 1] if i + 1 < len(buf) else 0
        if 1 <= n <= 30 and all(0x20 <= b < 0x80 or b >= 0x80
                                for b in buf[i + 2:i + 2 + n]):
            name = buf[i + 2:i + 2 + n]
            if any(b >= 0x80 for b in name) and not buf[i - 1:i] == b"I":
                # 排除误判：前一字节是 I 的已经算包装
                if buf[i - 1:i] != b"I":
                    bad += 1
                    if bad <= 6:
                        out.write("  [裸非 ASCII 符号] @0x%06X %r 前一字节 %r\n"
                                  % (i, name, buf[max(0, i - 3):i]))
    out.write("\n没有 I 包装的非 ASCII 符号出现次数 = %d\n" % bad)
    out.flush()
    if "--out" in sys.argv:
        out.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
