# -*- coding: utf-8 -*-
"""从两个内存镜像的差分里提取"密钥状态"，生成 src/xj_state.txt。

用法：
    python tools/make_state.py <ours.bin> <game.bin> [--rva 0x0F5E3C] [--len 128]
    python tools/make_state.py <ours.bin> <game.bin> --auto

  * --rva/--len：手工指定一段（默认就是差分里最像状态的那张表）
  * --auto    ：把所有「A 全 0 且 B 非 0」的段都写进去（可能包含指针，慎用）
"""
import os
import sys

sys.stdout.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
STATE = os.path.join(ROOT, "src", "xj_state.txt")
LOG = os.path.join(HERE, "_state.txt")

DEFAULT_RVA = 0x0F5E3C
DEFAULT_LEN = 128


def find_segments(a, b, gap=32, minlen=4, maxlen=8192):
    """A 里是 0、B 里非 0 的位置，按 gap 合并成段。"""
    n = min(len(a), len(b))
    hits = [i for i in range(n) if a[i] == 0 and b[i] != 0]
    if not hits:
        return []
    segs = []
    s = e = hits[0]
    for i in hits[1:]:
        if i - e <= gap:
            e = i
        else:
            segs.append((s, e))
            s = e = i
    segs.append((s, e))
    return [(s, e) for s, e in segs if minlen <= e - s + 1 <= maxlen]


def main():
    argv = [x for x in sys.argv[1:] if not x.startswith("--")]
    if len(argv) < 2:
        print("用法: python tools/make_state.py <ours.bin> <game.bin> [--rva 0x..] [--len N] [--auto]")
        return
    a = open(argv[0], "rb").read()
    b = open(argv[1], "rb").read()

    L = []
    lines = []

    if "--auto" in sys.argv:
        segs = find_segments(a, b)
        L.append("自动模式：找到 %d 段「A 全 0 / B 非 0」" % len(segs))
        for s, e in segs:
            ln = e - s + 1
            data = b[s:e + 1]
            L.append("  RVA 0x%06X 长度 %d  %s" % (s, ln, data[:32].hex(" ")))
            if ln <= 4096:
                lines.append("0x%06X %s" % (s, data.hex()))
    else:
        rva = DEFAULT_RVA
        ln = DEFAULT_LEN
        if "--rva" in sys.argv:
            rva = int(sys.argv[sys.argv.index("--rva") + 1], 0)
        if "--len" in sys.argv:
            ln = int(sys.argv[sys.argv.index("--len") + 1], 0)
        data = b[rva:rva + ln]
        L.append("RVA 0x%06X 长度 %d" % (rva, ln))
        L.append("  A(外部): %s" % a[rva:rva + ln].hex(" "))
        L.append("  B(游戏): %s" % data.hex(" "))
        lines.append("0x%06X %s" % (rva, data.hex()))

    open(STATE, "w", encoding="utf-8").write(
        "# main.dll 外部加载时要补写的\"密钥状态\"字节\n"
        "# 由 tools/make_state.py 生成，格式： RVA(十六进制) <十六进制字节>\n"
        "# 来源：游戏进程里的 System/main.dll 内存镜像\n" + "\n".join(lines) + "\n")
    L.append("\n已写入 %s（%d 行）" % (STATE, len(lines)))

    # 顺便把上下文打出来
    rva = DEFAULT_RVA
    L.append("\n==== 0x%06X 附近上下文 ====" % rva)
    for o in range(rva - 64, rva + 192, 16):
        if o < 0:
            continue
        L.append("  %06X  A: %-47s  B: %-47s" % (
            o, " ".join("%02X" % x for x in a[o:o + 16]),
            " ".join("%02X" % x for x in b[o:o + 16])))

    open(LOG, "w", encoding="utf-8").write("\n".join(L))
    print("done")


if __name__ == "__main__":
    main()
