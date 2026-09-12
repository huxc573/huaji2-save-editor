# -*- coding: utf-8 -*-
"""诊断 Scripts.rvdata2 的明文结构：到底有几个 zlib 段、结构是不是 [[id,name,code]...]。"""
import os
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.stdout.reconfigure(errors="replace")

import xj_marshal as M  # noqa: E402

import io  # noqa: E402

out = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def deref(n):
    while isinstance(n, M.LinkNode) and n.target is not None:
        n = n.target
    return n


def main():
    plain = os.path.join(HERE, "_dec", "Data_Scripts.rvdata2.bin")
    data = open(plain, "rb").read()
    out.write("明文 %s  %d 字节\n" % (plain, len(data)))

    # ---- 全部 zlib 段
    segs = []
    i = 0
    n = len(data)
    while i < n - 1:
        if data[i] == 0x78 and data[i + 1] in (0x01, 0x5E, 0x9C, 0xDA):
            try:
                d = zlib.decompressobj()
                dec = d.decompress(data[i:])
                tail = d.unused_data
            except Exception:
                dec = b""
                tail = b""
            if len(dec) > 100:
                used = len(data) - i - len(tail)
                segs.append((i, used, len(dec)))
                i += max(2, used)
                continue
        i += 1
    out.write("zlib 段数 = %d，解出总字节 = %d\n"
              % (len(segs), sum(s[2] for s in segs)))
    for k, (off, used, ln) in enumerate(segs[:12]):
        out.write("  #%02d off=0x%06X 压缩 %d -> %d 字节\n" % (k, off, used, ln))
    if len(segs) > 12:
        out.write("  …（还有 %d 段）\n" % (len(segs) - 12))

    # ---- Marshal 结构
    objs = M.parse_stream(data)
    out.write("顶层对象数 = %d：%s\n" % (len(objs), [o["node"].type for o in objs]))
    root = deref(objs[-1]["node"])
    out.write("根类型 = %s\n" % type(root).__name__)
    if isinstance(root, M.ArrayNode):
        out.write("根元素数 = %d\n" % len(root.items))
        for k, it in enumerate(root.items[:5]):
            e = deref(it)
            out.write("  [%d] %s" % (k, type(e).__name__))
            if isinstance(e, M.ArrayNode):
                kinds = []
                for x in e.items[:4]:
                    xx = deref(x)
                    v = getattr(xx, "value", None)
                    kinds.append("%s:%r" % (type(xx).__name__,
                                            (v[:20] if isinstance(v, bytes) else v)))
                out.write("  len=%d  %s" % (len(e.items), kinds))
            out.write("\n")
    elif isinstance(root, M.HashNode):
        out.write("根 %d 对\n" % len(root.pairs))
        for k, v in root.pairs[:5]:
            out.write("  key=%r val=%s\n"
                      % (getattr(deref(k), "value", None),
                         type(deref(v)).__name__))
    out.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
