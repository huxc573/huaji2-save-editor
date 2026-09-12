# -*- coding: utf-8 -*-
"""探针 18：在解壳镜像里搜「谁调用了 init_key」（搜 0x00012B0D / 0x00016341 立即数）。"""
import os
import re
import struct
import sys

sys.stdout.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
_OUT = []


def print(*a):  # noqa: A001
    _OUT.append(" ".join(str(x) for x in a))


def flush(name="_out_18.txt"):
    open(os.path.join(HERE, name), "w", encoding="utf-8").write("\n".join(_OUT))


from capstone import Cs, CS_ARCH_X86, CS_MODE_32  # noqa: E402

DATA = open(os.path.join(HERE, "_dump_main.bin"), "rb").read()
MD = Cs(CS_ARCH_X86, CS_MODE_32)

TARGETS = {
    "init_key 实现 0x12B0D": 0x12B0D,
    "init_key 导出 0x16341": 0x16341,
    "qqeat 实现 0x146B1": 0x146B1,
    "qqeat 导出 0x165AD": 0x165AD,
    "decryption_buff 实现 0x11B50": 0x11B50,
    "encryption_buff 实现 0xFBAF": 0xFBAF,
    "decryption_file 实现 0x10102": 0x10102,
    "encryption_file 实现 0xB834": 0xB834,
    "encrypt/decrypt 中间 0x1001B120": 0x1001B120,
    "0x1007D633": 0x1007D633,
    "0x1001A260": 0x1001A260,
    "0x1001B890": 0x1001B890,
    "0x1001BB60": 0x1001BB60,
    "0x1001BD20": 0x1001BD20,
    "0x1001A280": 0x1001A280,
    "0x1007A1B0": 0x1007A1B0,
    "0x1007A590": 0x1007A590,
    "0x1007A5B0": 0x1007A5B0,
    "0x1000FB (test impl)": 0x1000FB,
}


def main():
    for name, va in TARGETS.items():
        pat = struct.pack("<I", 0x10000000 + (va - 0x10000000) if va >= 0x10000000 else va)
        if va < 0x10000000:
            pat = struct.pack("<I", va)
        hits = [m.start() for m in re.finditer(re.escape(pat), DATA)]
        print("%-32s 引用 %d 处: %s" % (name, len(hits),
                                        ["0x%06X" % h for h in hits[:20]]))

    # 对每个引用点，看看附近是什么指令
    print("\n==== 引用点上下文（各取前 24 字节反汇编） ====")
    for name, va in TARGETS.items():
        pat = struct.pack("<I", va)
        hits = [m.start() for m in re.finditer(re.escape(pat), DATA)]
        for h in hits[:6]:
            start = max(0, h - 16)
            print("\n-- %s 引用点 0x%06X (某函数内偏移 -%d)" % (name, h, h - start))
            n = 0
            for ins in MD.disasm(DATA[start:h + 24], start):
                mark = "   <<<" if (start + 0) < 0 else ""
                print("     %06X  %-28s %s" % (ins.address, ins.mnemonic + " " + ins.op_str, ""))
                n += 1
                if n > 14:
                    break

    flush()


if __name__ == "__main__":
    main()
