# -*- coding: utf-8 -*-
"""PE 体检：从解壳镜像里取 main.dll 的导出 RVA；看 Game.exe 是否静态导入 main.dll。

输出：tools/_pe.txt
"""
import os
import struct
import sys

sys.stdout.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GAME = os.path.normpath(os.path.join(ROOT, "..", "..", ".."))
LOG = os.path.join(HERE, "_pe.txt")

L = []


def rva2off(sections, rva, flat=False):
    if flat:
        return rva
    for name, va, vsz, rawsz, pto in sections:
        if va <= rva < va + max(vsz, rawsz):
            return pto + (rva - va)
    return None


def parse_pe(buf, label, flat=False):
    out = {"exports": {}, "imports": [], "sections": []}
    if buf[:2] != b"MZ":
        L.append("%s: 不是 PE" % label)
        return out
    e_lfanew = struct.unpack_from("<I", buf, 0x3C)[0]
    if buf[e_lfanew:e_lfanew + 4] != b"PE\0\0":
        L.append("%s: 没有 PE 签名" % label)
        return out
    coff = e_lfanew + 4
    nsec = struct.unpack_from("<H", buf, coff + 2)[0]
    optsz = struct.unpack_from("<H", buf, coff + 16)[0]
    opt = coff + 20
    magic = struct.unpack_from("<H", buf, opt)[0]
    L.append("%s: machine=0x%04X magic=0x%04X 节数=%d" %
             (label, struct.unpack_from("<H", buf, coff)[0], magic, nsec))
    dd = opt + (96 if magic == 0x10B else 112)
    secoff = opt + optsz
    for i in range(nsec):
        s = secoff + i * 40
        name = buf[s:s + 8].rstrip(b"\0").decode("ascii", "replace")
        vsz, va, rawsz, pto = struct.unpack_from("<IIII", buf, s + 8)
        out["sections"].append((name, va, vsz, rawsz, pto))
        L.append("    节 %-8s VA=0x%08X VSize=0x%06X Raw=0x%06X" % (name, va, vsz, rawsz))
    # 导出
    exp_rva, exp_sz = struct.unpack_from("<II", buf, dd)
    if exp_rva:
        o = rva2off(out["sections"], exp_rva, flat)
        nfun, nname = struct.unpack_from("<II", buf, o + 20)[0], struct.unpack_from("<I", buf, o + 24)[0]
        aof = struct.unpack_from("<I", buf, o + 28)[0]
        anf = struct.unpack_from("<I", buf, o + 32)[0]
        aon = struct.unpack_from("<I", buf, o + 36)[0]
        of = rva2off(out["sections"], aof, flat)
        nf = rva2off(out["sections"], anf, flat)
        on = rva2off(out["sections"], aon, flat)
        for i in range(nname):
            if on is None or on + i * 4 + 4 > len(buf):
                L.append("  （导出名表越界，跳过）")
                break
            nr = struct.unpack_from("<I", buf, on + i * 4)[0]
            no = rva2off(out["sections"], nr, flat)
            if no is None or no >= len(buf):
                continue
            end = buf.find(b"\0", no)
            nm = buf[no:end if end > 0 else no + 32].decode("ascii", "replace")
            idx = struct.unpack_from("<H", buf, nf + i * 2)[0]
            if of is None or of + idx * 4 + 4 > len(buf):
                continue
            fr = struct.unpack_from("<I", buf, of + idx * 4)[0]
            out["exports"][nm] = fr
        L.append("  导出 %d 个（函数表 %d）" % (nname, nfun))
        for nm in ("encryption_file", "decryption_file", "encryption_buff",
                   "decryption_buff", "init_key", "init", "qqeat"):
            if nm in out["exports"]:
                L.append("    %-18s RVA=0x%08X" % (nm, out["exports"][nm]))
    # 导入
    imp_rva = struct.unpack_from("<I", buf, dd + 8)[0]
    if imp_rva:
        o = rva2off(out["sections"], imp_rva, flat)
        while True:
            desc = buf[o:o + 20]
            if len(desc) < 20 or desc == b"\0" * 20:
                break
            name_rva = struct.unpack_from("<I", buf, o + 12)[0]
            if name_rva:
                no = rva2off(out["sections"], name_rva, flat)
                nm = buf[no:buf.index(b"\0", no)].decode("ascii", "replace")
                out["imports"].append(nm)
            o += 20
        L.append("  DLL 导入: %s" % ", ".join(out["imports"]))
    return out


dump = open(os.path.join(HERE, "_ours_main.bin"), "rb").read()
L.append("== 解壳镜像 _ours_main.bin (%d 字节) ==" % len(dump))
mi = parse_pe(dump, "main.dll(镜像)", flat=True)

for rel in ("Game.exe", "System/RGSS301.dll"):
    p = os.path.join(GAME, rel.replace("/", os.sep))
    if not os.path.exists(p):
        continue
    buf = open(p, "rb").read()
    L.append("")
    L.append("== %s ==" % rel)
    r = parse_pe(buf, rel)
    for kw in (b"main.dll", b"decryption_file", b"encryption_file", b"qqeat",
               b"init_key", b"shield", b"decryption_buff"):
        idx = buf.find(kw)
        L.append("  文件里出现 %-18s : %s" % (kw.decode(), ("偏移 0x%X" % idx) if idx >= 0 else "无"))
    # 导入表里是否有 main.dll
    for i in r["imports"]:
        if "main" in i.lower():
            L.append("  *** 导入表里有 %s" % i)

open(LOG, "w", encoding="utf-8").write("\n".join(L) + "\n")
print("done")
