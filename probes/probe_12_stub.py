# -*- coding: utf-8 -*-
"""探针 12：反汇编关键 stub 与 helper，看清 main.dll 的真实调用约定与加密入口。"""
import os
import sys

sys.stdout.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
_OUT = []


def print(*a):  # noqa: A001
    _OUT.append(" ".join(str(x) for x in a))


def flush(name="_out_12.txt"):
    open(os.path.join(HERE, name), "w", encoding="utf-8").write("\n".join(_OUT))


from capstone import Cs, CS_ARCH_X86, CS_MODE_32  # noqa: E402

DATA = open(os.path.join(HERE, "_dump_main.bin"), "rb").read()
MD = Cs(CS_ARCH_X86, CS_MODE_32)


def show(rva, n=40, title=""):
    print("\n--- 0x%06X %s" % (rva, title))
    cnt = 0
    for ins in MD.disasm(DATA[rva:rva + 600], rva):
        print("  %06X  %-30s %s" % (ins.address, ins.mnemonic + " " + ins.op_str, ""))
        cnt += 1
        if cnt >= n:
            break


def dump(rva, n=64, title=""):
    print("\n--- DATA 0x%06X %s" % (rva, title))
    for i in range(0, n, 16):
        b = DATA[rva + i:rva + i + 16]
        asc = "".join(chr(c) if 32 <= c < 127 else "." for c in b)
        print("  %06X  %-47s  %s" % (rva + i, b.hex(" "), asc))


def main():
    print("dump size 0x%X" % len(DATA))
    for r in (0x19B90, 0x19B9F, 0x19BAB, 0x19BB1, 0x19BBD, 0x19BC9, 0x19BD5):
        show(r, 12, "stub")

    for r, t in ((0x10DD, "arg dup/ansi"),
                 (0x11C8A, "decryption_buff 核心"),
                 (0xFCCD, "buff 后处理"),
                 (0x146B1, "qqeat 实现"),
                 (0x11C8A, ""),
                 (0x12B0D, "init_key 实现"),
                 (0x15C3E, "get_md5 核心")):
        show(r, 60, t)

    for r, t in ((0x1001B120, "@0x1001b120"),
                 (0x1001BB60, "@0x1001bb60"),
                 (0x1007A590, "@0x1007a590"),
                 (0x1007A5B0, "@0x1007a5b0"),
                 (0x100BA3C0, "@0x100ba3c0 (空串?)"),
                 (0x100BA3C9, "@0x100ba3c9"),
                 (0x100BA907, "@0x100ba907"),
                 (0x100BA911, "@0x100ba911 (注册表路径)"),
                 (0x100BA967, "@0x100ba967")):
        dump(r - 0x10000000, 48, t)

    flush()


if __name__ == "__main__":
    main()
