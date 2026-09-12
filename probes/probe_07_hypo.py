# -*- coding: utf-8 -*-
"""探针 07：多个假设的快速排除法。"""
import os
import sys
import zlib

sys.stdout.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
GAME = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))
_OUT = []


def print(*a):  # noqa: A001
    _OUT.append(" ".join(str(x) for x in a))


def flush(name="_out_07.txt"):
    open(os.path.join(HERE, name), "w", encoding="utf-8").write("\n".join(_OUT))


def walk(rel, depth=0, maxdepth=2):
    p = os.path.join(GAME, rel)
    if not os.path.isdir(p):
        print("  [缺] %s" % rel)
        return
    for name in sorted(os.listdir(p)):
        full = os.path.join(p, name)
        relfull = rel + "/" + name
        if os.path.isdir(full):
            print("  [d] %-40s" % relfull)
            if depth < maxdepth:
                walk(relfull, depth + 1, maxdepth)
        else:
            print("  [f] %-40s %d" % (relfull, os.path.getsize(full)))


def try_inflate_at(data, off, wbits):
    try:
        d = zlib.decompressobj(wbits)
        out = d.decompress(data[off:off + 4_000_000])
        if len(out) > 8:
            return out[:16]
    except Exception:
        return None
    return None


def main():
    print("==== 1. 目录速查 ====")
    for rel in ("System", "Logs", "AutoSave", "Audio/SE"):
        print("-- %s" % rel)
        walk(rel, 0, 1)

    print("\n==== 2. 假设：加密文件其实是一段偏移处的裸 zlib ====")
    for rel in ("save.rvdata2", "Data/Scripts.rvdata2", "Data/System.rvdata2",
                "was.info", "System/Game.md5"):
        data = open(os.path.join(GAME, rel.replace("/", os.sep)), "rb").read()
        found = []
        for off in range(0, 64):
            for wbits in (15, -15, 47):
                r = try_inflate_at(data, off, wbits)
                if r:
                    found.append((off, wbits, r.hex()))
        print("  %-26s -> %s" % (rel, found[:5] if found else "无"))

    print("\n==== 3. 假设：整个文件与某个固定密钥流异或（找 8 字节重复块） ====")
    for rel in ("save.rvdata2", "AutoSave/save00.rvdata2", "Data/Scripts.rvdata2"):
        data = open(os.path.join(GAME, rel.replace("/", os.sep)), "rb").read()
        for blk in (4, 8, 16):
            counts = {}
            for i in range(0, len(data) - blk + 1, blk):
                k = data[i:i + blk]
                counts[k] = counts.get(k, 0) + 1
            top = sorted(counts.items(), key=lambda kv: -kv[1])[:3]
            print("  %-26s blk=%2d 最多重复 %s" % (
                rel, blk, [(v, k.hex()) for k, v in top]))

    print("\n==== 4. 假设：文件头 0..N 是明文头 ====")
    for rel in ("save.rvdata2", "AutoSave/save00.rvdata2"):
        data = open(os.path.join(GAME, rel.replace("/", os.sep)), "rb").read()
        print("  %s (%d B) 前 64 字节：" % (rel, len(data)))
        for i in range(0, 64, 16):
            print("    %04X  %s" % (i, " ".join("%02X" % b for b in data[i:i + 16])))

    print("\n==== 5. 两个存档的差异分布（判断是否有对齐/分块特征） ====")
    a = open(os.path.join(GAME, "save.rvdata2"), "rb").read()
    b = open(os.path.join(GAME, "AutoSave", "save00.rvdata2"), "rb").read()
    n = min(len(a), len(b))
    same = 0
    runs = []
    cur = None
    for i in range(n):
        if a[i] == b[i]:
            same += 1
            if cur is None:
                cur = i
        else:
            if cur is not None:
                runs.append((cur, i - cur))
                cur = None
    if cur is not None:
        runs.append((cur, n - cur))
    print("  相同字节 %d / %d (%.1f%%)" % (same, n, 100.0 * same / n))
    print("  相同片段（前 30 段）：%s" % runs[:30])

    flush()


if __name__ == "__main__":
    main()
