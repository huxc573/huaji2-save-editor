# -*- coding: utf-8 -*-
"""探针 01：确认存档 / 数据文件是明文 Marshal、zlib 还是自加密。

用法： python probe_01_format.py
"""
import os
import sys
import zlib

sys.stdout.reconfigure(errors="replace")

GAME = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))

TARGETS = [
    "save.rvdata2",
    "was.info",
    "Data/main.rvdata2",
    "Data/System.rvdata2",
    "Data/Map001.rvdata2",
    "Data/Actors.rvdata2",
    "AutoSave/save00.rvdata2",
]


def entropy(data: bytes) -> float:
    import math
    if not data:
        return 0.0
    counts = [0] * 256
    for b in data:
        counts[b] += 1
    n = len(data)
    e = 0.0
    for c in counts:
        if c:
            p = c / n
            e -= p * math.log2(p)
    return e


def head(data: bytes, n: int = 16) -> str:
    return " ".join("%02X" % b for b in data[:n])


def zlib_scan(data: bytes, limit: int = 4096):
    """找出所有可能的 zlib 流起始位置。"""
    hits = []
    for i in range(min(len(data), limit)):
        if data[i] == 0x78 and i + 1 < len(data) and data[i + 1] in (0x01, 0x5E, 0x9C, 0xDA):
            try:
                out = zlib.decompressobj().decompress(data[i:i + 200000])
                hits.append((i, len(out), head(out, 8)))
            except Exception:
                pass
    return hits


def main():
    print("GAME =", GAME)
    for rel in TARGETS:
        p = os.path.join(GAME, rel.replace("/", os.sep))
        if not os.path.exists(p):
            print("[--] %-26s 不存在" % rel)
            continue
        data = open(p, "rb").read()
        info = "[--] %-26s size=%-8d head=%s ent=%.2f" % (
            rel, len(data), head(data), entropy(data[:65536]))
        if data[:2] == b"\x04\x08":
            info += "  => Ruby Marshal 4.8 明文"
        else:
            hits = zlib_scan(data)
            if hits:
                info += "  => zlib @ %s" % hits[:3]
        print(info)


if __name__ == "__main__":
    main()
