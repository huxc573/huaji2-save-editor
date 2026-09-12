# -*- coding: utf-8 -*-
"""探针 11：在解壳镜像里找已知密码学常量 / 256 项表 / 可疑密钥。"""
import os
import re
import struct
import sys
from collections import Counter

sys.stdout.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
_OUT = []


def print(*a):  # noqa: A001
    _OUT.append(" ".join(str(x) for x in a))


def flush(name="_out_11.txt"):
    open(os.path.join(HERE, name), "w", encoding="utf-8").write("\n".join(_OUT))


CONSTS = {
    "TEA delta 0x9E3779B9 (LE)": bytes.fromhex("b979379e"),
    "TEA delta 0x9E3779B9 (BE)": bytes.fromhex("9e3779b9"),
    "RC5 0xB7E15163 (LE)": bytes.fromhex("6351e1b7"),
    "golden 0x61C88647 (LE)": bytes.fromhex("4786c861"),
    "MD5 A 0x67452301 (LE)": bytes.fromhex("01234567"),
    "MD5 B 0xEFCDAB89 (LE)": bytes.fromhex("89abcdef"),
    "SHA1 K1 0x5A827999 (BE)": bytes.fromhex("5a827999"),
    "SHA1 K4 0xCA62C1D6 (BE)": bytes.fromhex("ca62c1d6"),
    "SHA256 H0 0x6A09E667 (BE)": bytes.fromhex("6a09e667"),
    "AES sbox head": bytes.fromhex("637c777bf26b6fc5"),
    "Blowfish P head": bytes.fromhex("243f6a8885a308d3"),
    "DES S1 head": bytes.fromhex("0e040d0102"),
    "CRC32 poly table 2nd": bytes.fromhex("77073096"),
    "MD5 table 1st": bytes.fromhex("d76aa478"),
}


def main():
    data = open(os.path.join(HERE, "_dump_main.bin"), "rb").read()
    print("dump 0x%X bytes" % len(data))

    print("\n==== 已知常量 ====")
    for name, pat in CONSTS.items():
        offs = [m.start() for m in re.finditer(re.escape(pat), data)]
        print("  %-32s %s" % (name, ["0x%06X" % o for o in offs[:6]] or "无"))

    print("\n==== 疑似 256 项字节表（排列 / 查表） ====")
    hits = []
    for i in range(0, len(data) - 256):
        chunk = data[i:i + 256]
        if len(set(chunk)) >= 250:      # 近似排列
            hits.append(i)
    # 合并相邻
    merged = []
    for o in hits:
        if merged and o - merged[-1][1] <= 4:
            merged[-1][1] = o
        else:
            merged.append([o, o])
    print("  找到 %d 处，前 40：" % len(merged))
    for a, b in merged[:40]:
        print("    0x%06X (%d 字节排列)" % (a, len(set(data[a:a + 256]))))

    print("\n==== 疑似 256 项 32 位表 ====")
    hist = {}
    for i in range(0, len(data) - 1024, 4):
        vals = struct.unpack_from("<256I", data, i)
        uniq = len(set(vals))
        if uniq >= 200:
            hist[i] = uniq
    cands = sorted(hist.items())
    merged = []
    for o, u in cands:
        if merged and o - merged[-1][1] <= 8:
            merged[-1][1] = o
        else:
            merged.append([o, o])
    print("  找到 %d 处，前 30：" % len(merged))
    for a, b in merged[:30]:
        print("    0x%06X .. 0x%06X" % (a, b))

    print("\n==== 8 字节对齐的高熵常量区（可能是密钥） ====")
    # 找 .MPRESS2/.rsrc 之外、且不是代码的区域较难；这里只列出 8 字节窗口
    # 在「非代码」节内的高熵 16 字节窗口
    print("  （跳过：见下一探针）")

    flush()


if __name__ == "__main__":
    main()
