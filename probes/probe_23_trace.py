# -*- coding: utf-8 -*-
"""探针 23：自动跟踪 main.dll 的调用链（解壳镜像），找出加解密的核心函数。

main.dll 里所有间接调用都长这样：
    mov ebx, <目标地址>
    ... push 参数 ...
    call 0x19bXX        <- 蹦床（jmp dword ptr [IAT]）
所以只要跟踪 "mov ebx, imm" + "call 0x19bXX" 就能还原调用图。

另外 direct `call rel32` 也一起跟。

用法： python probes/probe_23_trace.py [根RVA ...]
结果： probes/_out_23.txt
"""
import os
import struct
import sys

sys.stdout.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
_OUT = []


def print(*a):  # noqa: A001
    _OUT.append(" ".join(str(x) for x in a))


from capstone import Cs, CS_ARCH_X86, CS_MODE_32  # noqa: E402

DATA = open(os.path.join(HERE, "_dump_main.bin"), "rb").read()
MD = Cs(CS_ARCH_X86, CS_MODE_32)

# 间接调用蹦床区间
TRAMP_LO, TRAMP_HI = 0x19B00, 0x19C00

ROOTS = {
    0x10102: "decryption_file 实现",
    0xB834: "encryption_file 实现",
    0x11B50: "decryption_buff 实现",
    0xFBAF: "encryption_buff 实现",
    0x146B1: "qqeat 实现",
    0x11986: "init 实现",
    0x12B0D: "init_key 实现",
    0x1001E: "dispose_key 实现",
    0x6650: "shield 核心",
    0x15C3E: "get_md5 核心",
}

SEEN = {}
EDGES = {}


def disasm_func(rva, maxn=400):
    """返回 (指令列表, 被调用目标集合)。"""
    insns = []
    callees = []
    last_ebx = None
    for ins in MD.disasm(DATA[rva:rva + 4096], rva):
        insns.append(ins)
        m, ops = ins.mnemonic, ins.op_str
        if m == "mov" and ops.startswith("ebx, "):
            v = ops[5:].strip()
            if v.startswith("0x"):
                try:
                    last_ebx = int(v, 16)
                except ValueError:
                    last_ebx = None
            else:
                last_ebx = None
        elif m == "call":
            if ops.startswith("0x"):
                t = int(ops, 16)
                if TRAMP_LO <= t < TRAMP_HI and last_ebx:
                    callees.append(last_ebx)
                elif not (TRAMP_LO <= t < TRAMP_HI):
                    callees.append(t)     # 直接调用
            last_ebx = None
        elif m == "jmp":
            if ops.startswith("0x"):
                t = int(ops, 16)
                if TRAMP_LO <= t < TRAMP_HI and last_ebx:
                    callees.append(last_ebx)
        if len(insns) > maxn:
            break
    return insns, callees


def walk(rva, name, depth, path):
    key = rva
    if key in SEEN and depth > 0:
        return
    SEEN[key] = name
    insns, callees = disasm_func(rva)
    EDGES[rva] = callees

    indent = "  " * depth
    print("\n%s=== [%d] %s @0x%06X  (%d 条指令) ===" % (indent, depth, name, rva, len(insns)))
    n = 0
    for ins in insns:
        print("%s  %06X  %-32s %s" % (indent, ins.address,
                                      ins.mnemonic + " " + ins.op_str, ""))
        n += 1
        if n >= 60 and depth > 0:
            print("%s  ...（截断）" % indent)
            break
    if callees:
        print("%s  调用：%s" % (indent, ["0x%06X" % c for c in callees]))
    if depth >= 4:
        return
    for c in callees:
        if c in path:
            continue
        if not (0x1000 <= c < 0x142000):
            continue
        walk(c, "sub_%06X" % c, depth + 1, path | {c})


def main():
    roots = {}
    for a in sys.argv[1:]:
        roots[int(a, 0)] = "root_%X" % int(a, 0)
    if not roots:
        roots = ROOTS
    print("镜像大小 = 0x%X" % len(DATA))
    for rva, name in roots.items():
        print("\n" + "#" * 78)
        print("### 从 %s (0x%06X) 开始" % (name, rva))
        print("#" * 78)
        walk(rva, name, 0, {rva})

    print("\n==== 调用图汇总 ====")
    for rva, cs in sorted(EDGES.items()):
        print("  0x%06X -> %s" % (rva, ["0x%06X" % c for c in cs]))

    open(os.path.join(HERE, "_out_23.txt"), "w", encoding="utf-8").write("\n".join(_OUT))
    print("\n(wrote _out_23.txt)")


if __name__ == "__main__":
    main()
