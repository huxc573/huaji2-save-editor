# -*- coding: utf-8 -*-
"""探针 04：反汇编 main.dll 的导出包装函数，猜参数个数；并找本机 32 位工具链。"""
import os
import struct
import sys

sys.stdout.reconfigure(errors="replace")

_OUT = []


def print(*a):  # noqa: A001  把输出同时写到文件，避开控制台编码问题
    line = " ".join(str(x) for x in a)
    _OUT.append(line)


def flush():
    open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "_out_04.txt"),
         "w", encoding="utf-8").write("\n".join(_OUT))

GAME = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))

try:
    from capstone import Cs, CS_ARCH_X86, CS_MODE_32
    HAVE_CS = True
except Exception:
    HAVE_CS = False

# 导出名 -> RVA（probe_03 的输出）
EXPORTS = {
    "qqeat": 0x0165AD, "init": 0x016335, "init_key": 0x016341, "dispose_key": 0x0165B9,
    "encryption_file": 0x015EF5, "decryption_file": 0x015F59,
    "encryption_buff": 0x0165C5, "decryption_buff": 0x016630,
    "get_md5": 0x016233, "init_debug": 0x01611B,
    "get_hard_disk_character": 0x0161A5, "shield": 0x01654E,
    "net_wrong_count": 0x016542, "read": 0x016095, "readFile": 0x01604D,
}


def load_sections(path):
    d = open(path, "rb").read()
    e = struct.unpack_from("<I", d, 0x3C)[0]
    coff = e + 4
    machine, nsec, _, _, _, opt_size, _ = struct.unpack_from("<HHIIIHH", d, coff)
    opt = coff + 20
    sec_off = opt + opt_size
    secs = []
    for i in range(nsec):
        name, vsize, vaddr, rawsize, rawptr = struct.unpack_from(
            "<8sIIII", d, sec_off + i * 40)
        secs.append((name.rstrip(b"\0").decode(), vaddr, vsize, rawptr, rawsize))
    return d, secs


def rva2off(secs, rva):
    for _, vaddr, vsize, rawptr, rawsize in secs:
        if vaddr <= rva < vaddr + max(vsize, rawsize):
            return rawptr + (rva - vaddr)
    return None


def main():
    print("capstone:", HAVE_CS)
    d, secs = load_sections(os.path.join(GAME, "System", "main.dll"))
    print("main.dll 节表:", [(n, hex(v), vs, hex(rp), rs) for n, v, vs, rp, rs in secs])
    if HAVE_CS:
        md = Cs(CS_ARCH_X86, CS_MODE_32)
        md.detail = False
        for name, rva in EXPORTS.items():
            off = rva2off(secs, rva)
            print("\n=== %s  rva=%#x off=%#x" % (name, rva, off))
            code = d[off:off + 96]
            for ins in md.disasm(code, rva):
                print("  %06X  %-10s %s" % (ins.address, ins.mnemonic, ins.op_str))
    else:
        # 没有 capstone 就打印原始字节
        for name, rva in EXPORTS.items():
            off = rva2off(secs, rva)
            print("%-24s %s" % (name, " ".join("%02X" % b for b in d[off:off + 48])))


if __name__ == "__main__":
    main()
    flush()
