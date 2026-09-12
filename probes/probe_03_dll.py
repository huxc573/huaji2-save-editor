# -*- coding: utf-8 -*-
"""探针 03：解出 main.rvdata2 里的引导脚本 + 列出 main.dll 导出 + 解析 was.info。"""
import os
import re
import struct
import sys
import zlib

sys.stdout.reconfigure(errors="replace")

GAME = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))


def p(*a):
    print(*a)


# ---------------------------------------------------------------- PE 导出表
def pe_exports(path):
    d = open(path, "rb").read()
    e_lfanew = struct.unpack_from("<I", d, 0x3C)[0]
    assert d[e_lfanew:e_lfanew + 4] == b"PE\0\0"
    coff = e_lfanew + 4
    machine, nsec, _, _, _, opt_size, _ = struct.unpack_from("<HHIIIHH", d, coff)
    opt = coff + 20
    magic = struct.unpack_from("<H", d, opt)[0]
    is64 = magic == 0x20B
    dd_off = opt + (112 if is64 else 96)
    exp_rva, exp_size = struct.unpack_from("<II", d, dd_off)
    sec_off = opt + opt_size
    secs = []
    for i in range(nsec):
        name, vsize, vaddr, rawsize, rawptr = struct.unpack_from(
            "<8sIIII", d, sec_off + i * 40)
        secs.append((name.rstrip(b"\0").decode(), vaddr, vsize, rawptr, rawsize))

    def rva2off(rva):
        for _, vaddr, vsize, rawptr, rawsize in secs:
            if vaddr <= rva < vaddr + max(vsize, rawsize):
                return rawptr + (rva - vaddr)
        return None

    if not exp_rva:
        return []
    eo = rva2off(exp_rva)
    nfun, nname = struct.unpack_from("<II", d, eo + 20)
    addr_rva, name_rva, ord_rva = struct.unpack_from("<III", d, eo + 28)
    ao, no = rva2off(addr_rva), rva2off(name_rva)
    out = []
    for i in range(nname):
        nrva = struct.unpack_from("<I", d, no + i * 4)[0]
        off = rva2off(nrva)
        end = d.index(b"\0", off)
        nm = d[off:end].decode("ascii", "replace")
        frva = struct.unpack_from("<I", d, ao + i * 4)[0]
        out.append((nm, frva))
    # 未命名导出（按序号）
    oo = rva2off(ord_rva) if ord_rva else None
    named_ord = set()
    if oo:
        for i in range(nname):
            named_ord.add(struct.unpack_from("<H", d, oo + i * 2)[0])
    for i in range(nfun):
        if i not in named_ord:
            frva = struct.unpack_from("<I", d, ao + i * 4)[0]
            if frva:
                out.append(("ordinal_%d" % i, frva))
    return out


def main():
    # ---- 1. main.rvdata2 的引导脚本
    raw = open(os.path.join(GAME, "Data", "main.rvdata2"), "rb").read()
    m = re.search(rb"x\x9c", raw)
    blob = raw[m.start():]
    try:
        code = zlib.decompressobj().decompress(blob)
    except Exception as e:
        code = b"<fail %s>" % str(e).encode()
    p("=" * 70)
    p("main.rvdata2 解出的引导脚本（%d 字节）：" % len(code))
    p("=" * 70)
    p(code.decode("utf-8", "replace"))
    p()

    # ---- 2. main.dll 导出
    p("=" * 70)
    p("System/main.dll 导出表：")
    p("=" * 70)
    for nm, rva in pe_exports(os.path.join(GAME, "System", "main.dll")):
        p("  %-28s rva=0x%06X" % (nm, rva))
    p()

    # ---- 3. main.dll 全量可读字符串（关键字过滤放宽）
    dll = open(os.path.join(GAME, "System", "main.dll"), "rb").read()
    p("=" * 70)
    p("main.dll 中与 .rvdata2 / 文件名 / 口令 / URL 有关的字符串：")
    p("=" * 70)
    pats = re.compile(rb"(?i)\.(rvdata2|rxdata|info|ini|md5|dll|png|txt)|http|www|"
                      rb"key|password|passwd|salt|hash|base64|tool|cheat|debug|"
                      rb"save|load|script|main\.|data\\")
    seen = set()
    for mm in re.finditer(rb"[\x20-\x7E]{5,}", dll):
        s = mm.group()
        if pats.search(s) and s not in seen:
            seen.add(s)
            p("  %08X  %s" % (mm.start(), s.decode("ascii", "replace")[:150]))
    p("  （共 %d 条）" % len(seen))
    p()

    # ---- 4. main.dll 里的宽字符（UTF-16LE）中文串 —— 保护系统自己的提示语
    p("=" * 70)
    p("main.dll 中的 UTF-16LE 中文串（前 80 条）：")
    p("=" * 70)
    n = 0
    for mm in re.finditer(rb"(?:[\x20-\x7E\u0080-\uFFFF]\x00){3,}", dll):
        try:
            s = mm.group().decode("utf-16-le")
        except Exception:
            continue
        if any("\u4e00" <= ch <= "\u9fff" for ch in s):
            p("  %08X  %s" % (mm.start(), s[:120]))
            n += 1
            if n >= 80:
                break
    p()


if __name__ == "__main__":
    main()
