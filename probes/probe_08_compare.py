# -*- coding: utf-8 -*-
"""探针 08：对比画迹1与画迹2的游戏目录结构 / dll / 存档头。"""
import os
import re
import sys

sys.stdout.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
GAME2 = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))
GAME1 = r"D:\Life\Game\Local\MH\画迹\【画迹1：落日情缘】[正式版+资料片]"
_OUT = []


def print(*a):  # noqa: A001
    _OUT.append(" ".join(str(x) for x in a))


def flush(name="_out_08.txt"):
    open(os.path.join(HERE, name), "w", encoding="utf-8").write("\n".join(_OUT))


def head(path, n=16):
    with open(path, "rb") as f:
        return f.read(n)


def scan_root(root, label):
    print("\n==== %s : %s ====" % (label, root))
    if not os.path.isdir(root):
        print("  [不存在]")
        return
    for name in sorted(os.listdir(root)):
        full = os.path.join(root, name)
        if os.path.isdir(full):
            print("  [d] %-28s" % name)
        else:
            sz = os.path.getsize(full)
            print("  [f] %-28s %-10d head=%s" % (
                name, sz, head(full, 8).hex(" ")))

    # 关键文件
    for pat in ("*.dll", "*.DLL"):
        for dirpath, _, files in os.walk(root):
            for f in files:
                if f.lower().endswith(".dll"):
                    p = os.path.join(dirpath, f)
                    rel = os.path.relpath(p, root)
                    print("  DLL %-46s %-9d head=%s" % (
                        rel, os.path.getsize(p), head(p, 8).hex(" ")))


def main():
    scan_root(GAME1, "画迹1 根目录")
    print("\n  画迹1 Audio/BGM 内容（前 20）:")
    p = os.path.join(GAME1, "Audio", "BGM")
    if os.path.isdir(p):
        for n in sorted(os.listdir(p))[:20]:
            fp = os.path.join(p, n)
            if os.path.isfile(fp):
                print("    %-30s %-10d head=%s" % (n, os.path.getsize(fp),
                                                   head(fp, 8).hex(" ")))

    scan_root(GAME2, "画迹2 根目录")

    # 画迹1 的存档（sy.ogg）
    sy = os.path.join(GAME1, "Audio", "BGM", "sy.ogg")
    if os.path.exists(sy):
        d = open(sy, "rb").read()
        print("\n  画迹1 存档 sy.ogg: size=%d head=%s" % (len(d), d[:24].hex(" ")))
        if len(d) > 8:
            import struct
            print("  魔数=%08X 声明长度=%d" % (
                struct.unpack_from("<I", d, 0)[0], struct.unpack_from("<I", d, 4)[0]))

    # 画迹2 存档（8 字节块对齐检查）
    d2 = open(os.path.join(GAME2, "save.rvdata2"), "rb").read()
    print("\n  画迹2 save.rvdata2: size=%d  %%8=%d  %%4=%d  %%16=%d" % (
        len(d2), len(d2) % 8, len(d2) % 4, len(d2) % 16))

    # 常见 8 字节块的偏移分布
    counts = {}
    for i in range(0, len(d2) - 7, 8):
        k = d2[i:i + 8]
        counts.setdefault(k, []).append(i)
    top = sorted(counts.items(), key=lambda kv: -len(kv[1]))[:8]
    print("  按 8 字节对齐统计 Top8：")
    for k, offs in top:
        mods = {}
        for o in offs:
            mods[o % 16] = mods.get(o % 16, 0) + 1
        print("    %s  count=%-6d 偏移%%16 分布=%s 前 8 个偏移=%s" % (
            k.hex(), len(offs), sorted(mods.items()), offs[:8]))

    # 尾部
    print("  尾部 32 字节: %s" % d2[-32:].hex(" "))

    flush()


if __name__ == "__main__":
    main()
