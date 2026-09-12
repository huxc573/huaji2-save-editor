# -*- coding: utf-8 -*-
"""整档重写安全性验证：parse → serialize(table={}, base=0) 是否逐字节还原？

这是"能往容器里加东西"的前提：只有整条顶层对象按 Ruby 的规则重新编号，
才能安全地新增/删除对象（否则后面所有 '@N' 全会错位）。

用法：python tools/test_roundtrip.py [--out 文件]
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.stdout.reconfigure(errors="replace")

import xj_codec  # noqa: E402
import xj_env  # noqa: E402
import xj_marshal as M  # noqa: E402

out = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
OK = [0, 0]


def check(name, cond, extra=""):
    OK[0 if cond else 1] += 1
    out.write("  %s %-40s %s\n" % ("[OK]" if cond else "[NG]", name, extra))


def roundtrip(plain, label):
    objs = M.parse_stream(plain)
    new = M.serialize_doc(objs)
    same = (new == plain)
    check("%s 重写逐字节一致" % label, same,
          "" if same else "原 %d 字节 / 新 %d 字节，首个不同处 %s"
          % (len(plain), len(new), first_diff(plain, new)))
    if same:
        return True
    # 不一致也要确认"改后还能解析"
    try:
        objs2 = M.parse_stream(new)
        check("%s 重写后仍可解析" % label,
              len(objs2) == len(objs), "%d 个顶层对象" % len(objs2))
    except Exception as e:
        check("%s 重写后仍可解析" % label, False, repr(e))
    return False


def first_diff(a, b):
    for i in range(min(len(a), len(b))):
        if a[i] != b[i]:
            return "offset 0x%X: %r vs %r" % (i, a[i:i + 8], b[i:i + 8])
    return "长度不同"


def main():
    global out
    if "--out" in sys.argv:
        out = open(sys.argv[sys.argv.index("--out") + 1], "w", encoding="utf-8")
    game = xj_env.find_game_dir()
    out.write("游戏目录 = %s\n" % game)

    # 1) 存档
    sp = xj_env.save_path()
    doc_objs = None
    try:
        import xj_model
        doc = xj_model.Doc(sp)
        doc_objs = doc
        out.write("\n### 存档 %s（明文 %d 字节）\n" % (os.path.basename(sp),
                                                      len(doc.raw)))
        roundtrip(doc.raw, "save")
    except Exception as e:
        check("存档 round-trip", False, repr(e))

    # 2) 所有解密出来的明文（tools/_plain/*.bin）
    pdir = os.path.join(HERE, "_plain")
    if os.path.isdir(pdir):
        out.write("\n### tools/_plain 下的明文文件\n")
        for n in sorted(os.listdir(pdir)):
            p = os.path.join(pdir, n)
            if os.path.getsize(p) < 10:
                continue
            # Game.md5 是纯文本校验文件，不是 Marshal
            if n.startswith("System_Game.md5"):
                continue
            try:
                data = open(p, "rb").read()
                roundtrip(data, n)
            except Exception as e:
                check(n, False, repr(e))
    out.write("\n==== %d 通过 / %d 失败 ====\n" % (OK[0], OK[1]))
    out.flush()
    if "--out" in sys.argv:
        out.close()
    return 1 if OK[1] else 0


if __name__ == "__main__":
    sys.exit(main())
