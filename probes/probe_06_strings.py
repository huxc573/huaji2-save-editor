# -*- coding: utf-8 -*-
"""探针 06：从「解壳后的 main.dll 内存镜像」里挖字符串，找密钥/URL/文件名/协议。"""
import os
import re
import sys

sys.stdout.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
_OUT = []


def print(*a):  # noqa: A001
    _OUT.append(" ".join(str(x) for x in a))


def flush(name="_out_06.txt"):
    open(os.path.join(HERE, name), "w", encoding="utf-8").write("\n".join(_OUT))


def main():
    data = open(os.path.join(HERE, "_dump_main.bin"), "rb").read()
    print("dump size = 0x%X" % len(data))

    # ---- 1) ASCII 串
    print("\n########## ASCII 串（长度>=6, 前 400 条） ##########")
    seen = set()
    cnt = 0
    for m in re.finditer(rb"[\x20-\x7E]{6,}", data):
        s = m.group().decode("ascii", "replace")
        if s in seen:
            continue
        seen.add(s)
        print("  %06X  %s" % (m.start(), s[:160]))
        cnt += 1
        if cnt >= 400:
            break
    print("  ... 共 %d 条唯一串（截断到 400）" % len(seen))

    # ---- 2) 关键字命中
    print("\n########## 关键字命中 ##########")
    kw = (rb"(?i)(http|www\.|\.com|\.cn|key|passw|pwd|salt|md5|rvdata2|rxdata|"
          rb"save|\.info|\.ini|\.dll|token|secret|aes|des|rc4|blowfish|xor|"
          rb"encrypt|decrypt|qq|weixin|wx|api|post|upload|device|machine|"
          rb"harddisk|serial|uuid|hwid|crc|zlib|marshal)")
    hits = []
    for m in re.finditer(rb"[\x20-\x7E]{4,}", data):
        s = m.group()
        if re.search(kw, s):
            hits.append((m.start(), s.decode("ascii", "replace")))
    for off, s in hits[:500]:
        print("  %06X  %s" % (off, s[:170]))
    print("  ... 命中 %d 条" % len(hits))

    # ---- 3) UTF-16LE 串（提示语）
    print("\n########## UTF-16LE 串（含中文） ##########")
    n = 0
    run_start = None
    run_raw = bytearray()

    def flush_run(start, raw):
        nonlocal n
        if len(raw) >= 8:
            try:
                s = bytes(raw).decode("utf-16-le")
            except Exception:
                return
            if any("\u4e00" <= ch <= "\u9fff" for ch in s):
                print("  %06X  %s" % (start, s[:150]))
                n += 1

    i = 0
    ln = len(data)
    while i + 1 < ln:
        lo, hi = data[i], data[i + 1]
        ch = None
        if hi == 0 and 0x20 <= lo < 0x7F:
            ch = chr(lo)
        elif 0x4E <= hi <= 0x9F or 0x34 <= hi <= 0x4D or hi in (0x30, 0x31, 0x32, 0x33):
            ch = chr(lo | (hi << 8))
            if not (0x3000 <= ord(ch) <= 0x9FFF or 0xFF00 <= ord(ch) <= 0xFFEF
                    or 0x2000 <= ord(ch) <= 0x206F):
                ch = None
        if ch is not None:
            if run_start is None:
                run_start = i
                run_raw = bytearray()
            run_raw += data[i:i + 2]
        else:
            if run_start is not None:
                flush_run(run_start, run_raw)
                if n >= 300:
                    break
            run_start = None
        i += 2
    if run_start is not None and n < 300:
        flush_run(run_start, run_raw)
    print("  ... 共 %d 条" % n)

    flush()


if __name__ == "__main__":
    main()
