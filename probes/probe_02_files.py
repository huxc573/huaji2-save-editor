# -*- coding: utf-8 -*-
"""探针 02：was.info / Game.md5 / main.dll 的粗看。"""
import os
import re
import struct
import sys

sys.stdout.reconfigure(errors="replace")

GAME = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))


def hexdump(data, off=0, n=128, width=16):
    lines = []
    for i in range(0, min(n, len(data)), width):
        chunk = data[i:i + width]
        hx = " ".join("%02X" % b for b in chunk)
        asc = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append("%08X  %-*s  %s" % (off + i, width * 3 - 1, hx, asc))
    return "\n".join(lines)


def ascii_strings(data, minlen=6):
    out = []
    for m in re.finditer(rb"[\x20-\x7E]{%d,}" % minlen, data):
        out.append((m.start(), m.group().decode("ascii", "replace")))
    return out


def file_info(rel):
    p = os.path.join(GAME, rel.replace("/", os.sep))
    if not os.path.exists(p):
        print("== %s 不存在" % rel)
        return None
    data = open(p, "rb").read()
    print("== %s  size=%d" % (rel, len(data)))
    print(hexdump(data, 0, 160))
    print()
    return data


def main():
    print("GAME =", GAME, "\n")
    info = file_info("was.info")
    file_info("System/Game.md5")
    file_info("Data/main.rvdata2")

    if info:
        print("-- was.info 里的 ASCII 串（前 60 条）--")
        for off, s in ascii_strings(info, 6)[:60]:
            print("  %08X  %s" % (off, s[:120]))
        print("\n-- was.info 大小 / 结构猜测 --")
        print("  前 4 字节 =", info[:4].hex())
        # 看是否有大量 0 区
        zeros = sum(1 for b in info[:65536] if b == 0)
        print("  前 64K 中 0x00 占比 = %.1f%%" % (zeros / 655.36))

    md5 = file_info("System/Game.md5")
    if md5:
        print("-- Game.md5 内容 --")
        print(md5.decode("utf-8", "replace")[:4000])

    dll = file_info("System/main.dll")
    if dll:
        print("-- main.dll 大小 = %d, MZ=%s" % (len(dll), dll[:2] == b"MZ"))
        print("-- main.dll 可疑字符串 --")
        pats = re.compile(rb"(?i)(decrypt|encrypt|marshal|rgss|load|save|key|was|md5|"
                          rb"Game\.md5|\.rvdata2|\.info|Config\.ini|cheat|debug)")
        for off, s in ascii_strings(dll, 5):
            if pats.search(s.encode()):
                print("  %08X  %s" % (off, s[:140]))


if __name__ == "__main__":
    main()
