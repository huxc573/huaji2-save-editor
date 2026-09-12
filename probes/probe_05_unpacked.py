# -*- coding: utf-8 -*-
"""探针 05：反汇编「解壳后」的内存镜像，搞清 encrypt/decrypt 的接口与算法。"""
import os
import re
import struct
import sys

sys.stdout.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
_OUT = []


def print(*a):  # noqa: A001
    _OUT.append(" ".join(str(x) for x in a))


def flush(name="_out_05.txt"):
    open(os.path.join(HERE, name), "w", encoding="utf-8").write("\n".join(_OUT))


from capstone import Cs, CS_ARCH_X86, CS_MODE_32  # noqa: E402

BASE = 0x10000000

EXPORTS = {
    "qqeat": 0x0165AD, "init": 0x016335, "init_key": 0x016341, "dispose_key": 0x0165B9,
    "encryption_file": 0x015EF5, "decryption_file": 0x015F59,
    "encryption_buff": 0x0165C5, "decryption_buff": 0x016630,
    "get_md5": 0x016233, "init_debug": 0x01611B,
    "get_hard_disk_character": 0x0161A5, "shield": 0x01654E,
    "test": 0x015D9A, "read": 0x016095,
}


def disasm(md, data, rva, maxn=60, title=""):
    print("\n" + "=" * 78)
    print("=== %s   rva=0x%06X" % (title or ("rva_%06X" % rva), rva))
    print("=" * 78)
    n = 0
    for ins in md.disasm(data[rva:rva + 400], rva):
        print("  %06X  %-34s %s" % (ins.address, ins.mnemonic + " " + ins.op_str, ""))
        n += 1
        if ins.mnemonic == "ret" or ins.mnemonic.startswith("ret"):
            print("  ---- (ret 结束, 共 %d 条) ----" % n)
            break
        if n >= maxn:
            print("  ---- (截断) ----")
            break


def main():
    data = open(os.path.join(HERE, "_dump_main.bin"), "rb").read()
    print("dump size = %d (0x%X)" % (len(data), len(data)))

    # 1) 确认是否已解壳：看 .MPRESS1 区域的可执行代码密度
    mz = data[:2] == b"MZ"
    print("memory image starts with MZ:", mz)
    if mz:
        e = struct.unpack_from("<I", data, 0x3C)[0]
        print("e_lfanew = 0x%X sig=%r" % (e, data[e:e + 4]))
        nsec = struct.unpack_from("<H", data, e + 6)[0]
        optsz = struct.unpack_from("<H", data, e + 20)[0]
        sec_off = e + 24 + optsz
        for i in range(nsec):
            o = sec_off + i * 40
            nm = data[o:o + 8].rstrip(b"\0").decode("ascii", "replace")
            vsz, va, rsz, rp = struct.unpack_from("<IIII", data, o + 8)
            print("  %-10s va=0x%06X vsz=0x%06X raw=0x%06X/0x%06X" % (nm, va, vsz, rp, rsz))

    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.detail = False

    # 2) 完整反汇编 thunk，确定参数个数（看 ret N）
    for name, rva in EXPORTS.items():
        disasm(md, data, rva, 60, name)

    # 3) 真正的实现体
    for rva, title in ((0x10102, "decryption_file 实现"),
                       (0xb834, "encryption_file 实现"),
                       (0x11b50, "decryption_buff 实现"),
                       (0xfbaf, "encryption_buff 实现"),
                       (0x12b0d, "init_key 实现"),
                       (0x13652, "参数转换 helper"),
                       (0x11986, "init 实现"),
                       (0x1001e, "dispose_key 实现"),
                       (0x146b1, "qqeat 实现")):
        disasm(md, data, rva, 120, title)

    flush()



if __name__ == "__main__":
    main()
