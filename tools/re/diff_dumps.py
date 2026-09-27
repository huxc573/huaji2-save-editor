# -*- coding: utf-8 -*-
"""差分两个 main.dll 内存镜像（外部加载的 vs 游戏进程里的），找出"密钥状态"。

用法：
    python tools/diff_dumps.py <ours.bin> <game.bin> [--max N]

输出 tools/_diff.txt：
  * 总差异字节数
  * 每个连续差异段：RVA、长度、差异字节比例、两侧 hex（截断）
"""
import os
import sys

sys.stdout.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "_diff.txt")


def main():
    argv = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(argv) < 2:
        print("用法: python tools/diff_dumps.py <ours.bin> <game.bin>")
        return
    a = open(argv[0], "rb").read()
    b = open(argv[1], "rb").read()
    n = min(len(a), len(b))
    max_show = 48
    if "--max" in sys.argv:
        max_show = int(sys.argv[sys.argv.index("--max") + 1])

    L = []
    L.append("A(外部加载) = %s  %d 字节" % (argv[0], len(a)))
    L.append("B(游戏进程) = %s  %d 字节" % (argv[1], len(b)))
    L.append("比较长度 = %d（0x%X）" % (n, n))

    diffs = [i for i in range(n) if a[i] != b[i]]
    L.append("\n差异字节总数 = %d (%.2f%%)" % (len(diffs), 100.0 * len(diffs) / n))

    # 合并成连续段（间隔 <= 16 视为同段）
    segs = []
    for i in diffs:
        if segs and i - segs[-1][1] <= 16:
            segs[-1][1] = i
        else:
            segs.append([i, i])
    L.append("差异段数 = %d" % len(segs))

    L.append("\n==== 差异段一览（按长度降序） ====")
    segs_sorted = sorted(segs, key=lambda s: -(s[1] - s[0]))
    for s, e in segs_sorted[:60]:
        ln = e - s + 1
        nd = sum(1 for i in range(s, e + 1) if a[i] != b[i])
        L.append("  RVA 0x%06X .. 0x%06X  长度 %-6d 差异 %-6d (%.0f%%)" % (
            s, e, ln, nd, 100.0 * nd / ln))

    if "--hex" in sys.argv:
        L.append("\n==== 差异段内容 ====")
        for s, e in segs_sorted[:max_show]:
            ln = e - s + 1
            L.append("\n-- RVA 0x%06X 长度 %d" % (s, ln))
            for k in range(0, min(ln, 256), 16):
                o = s + k
                ha = " ".join("%02X" % x for x in a[o:o + 16])
                hb = " ".join("%02X" % x for x in b[o:o + 16])
                L.append("   %06X  A: %-47s" % (o, ha))
                L.append("          B: %-47s" % hb)

    # 顺便看看哪些段"在 A 里全是 0"
    L.append("\n==== A 全 0 而 B 非 0 的段（最可能是被 qqeat 装好的状态） ====")
    cnt = 0
    for s, e in segs_sorted:
        ln = e - s + 1
        if ln >= 4 and all(x == 0 for x in a[s:e + 1]) and any(x != 0 for x in b[s:e + 1]):
            L.append("  RVA 0x%06X 长度 %-6d  B hex: %s" % (
                s, ln, " ".join("%02X" % x for x in b[s:min(e + 1, s + 64)])))
            cnt += 1
            if cnt >= 40:
                break
    L.append("  共 %d 段" % cnt)

    open(OUT, "w", encoding="utf-8").write("\n".join(L))
    print("done")


if __name__ == "__main__":
    main()
