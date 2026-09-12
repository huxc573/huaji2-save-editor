# -*- coding: utf-8 -*-
"""探针 10：判定密文结构 —— ECB？逐字节替换？流密码？

判据：
 A. 相邻两次自动存档（内容几乎相同）密文的公共 8 字节块数量
    - 多 -> 位置无关的分组/替换类
    - 少 -> 带位置/随机量的流式
 B. 相对最高频块的汉明距离分布
    - 只差 1 个字节的块大量存在 -> 逐字节替换（可破）
 C. 相同明文的块是否总出现在相同偏移
"""
import os
import sys
from collections import Counter

sys.stdout.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
GAME = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))
_OUT = []


def print(*a):  # noqa: A001
    _OUT.append(" ".join(str(x) for x in a))


def flush(name="_out_10.txt"):
    open(os.path.join(HERE, name), "w", encoding="utf-8").write("\n".join(_OUT))


def loads(rel):
    return open(os.path.join(GAME, rel.replace("/", os.sep)), "rb").read()


def blk(data):
    return [data[i:i + 8] for i in range(0, len(data) - 7, 8)]


def main():
    save = loads("save.rvdata2")
    autos = {}
    for i in range(30):
        autos["A%02d" % i] = loads("AutoSave/save%02d.rvdata2" % i)

    print("==== A. 与 save.rvdata2 的公共 8 字节块 ====")
    bsave = blk(save)
    ssave = set(bsave)
    print("  save: %d 块, 唯一 %d" % (len(bsave), len(ssave)))
    for name, data in autos.items():
        ba = blk(data)
        sa = set(ba)
        inter = len(sa & ssave)
        print("  %-4s size=%-8d 块=%-7d 唯一=%-7d 与 save 公共=%d (%.1f%%)" % (
            name, len(data), len(ba), len(sa), inter, 100.0 * inter / max(1, len(sa))))

    print("\n==== A2. 相邻自动存档互相比较 ====")
    keys = sorted(autos)
    for i in range(len(keys) - 1):
        a, b = autos[keys[i]], autos[keys[i + 1]]
        sa, sb = set(blk(a)), set(blk(b))
        # 相同偏移处相同的块（说明是位置相关的流或 ECB 且明文同）
        n = min(len(a), len(b)) // 8
        same_same = sum(1 for k in range(n) if a[8 * k:8 * k + 8] == b[8 * k:8 * k + 8])
        print("  %s vs %s: 集合公共=%-6d  同偏移相同=%-6d / %d" % (
            keys[i], keys[i + 1], len(sa & sb), same_same, n))

    print("\n==== B. 相对最高频块的汉明距离分布 ====")
    cnt = Counter(bsave)
    top = cnt.most_common(3)
    print("  Top3: %s" % [(k.hex(), v) for k, v in top])
    c0 = top[0][0]
    hist = Counter()
    per_pos = [Counter() for _ in range(8)]
    for b in set(bsave):
        d = sum(1 for j in range(8) if b[j] != c0[j])
        hist[d] += 1
        if d == 1:
            for j in range(8):
                if b[j] != c0[j]:
                    per_pos[j][b[j]] += 1
    print("  与最高频块相差 k 字节的唯一块数: %s" % sorted(hist.items()))
    print("  只差 1 字节时，各位置出现的不同字节值个数: %s" % [len(p) for p in per_pos])

    print("\n==== C. 相同块的偏移集合是否有规律 ====")
    for k, v in top[:2]:
        offs = [i * 8 for i in range(len(bsave)) if bsave[i] == k]
        print("  %s count=%d 偏移%%8 分布=%s 偏移%%16 分布=%s" % (
            k.hex(), v,
            sorted(Counter(o % 8 for o in offs).items()),
            sorted(Counter(o % 16 for o in offs).items())))
        # 连续出现的情况
        runs = []
        cur = 1
        for i in range(1, len(offs)):
            if offs[i] == offs[i - 1] + 8:
                cur += 1
            else:
                runs.append(cur)
                cur = 1
        runs.append(cur)
        print("     连续段长度分布: %s" % sorted(Counter(runs).items())[:12])

    print("\n==== D. 十六进制片段（save 中部，看是否有 8 字节周期） ====")
    print("  offset 238600..238752:")
    for i in range(238600, 238760, 32):
        print("    %06X  %s" % (i, save[i:i + 32].hex(" ")))

    flush()


if __name__ == "__main__":
    main()
