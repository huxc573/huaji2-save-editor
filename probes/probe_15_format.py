# -*- coding: utf-8 -*-
"""探针 15：摸清 main.dll 的加密文件格式（额外 8 字节是什么？ECB 还是流式？）。

做法：加密几组精心构造的定长明文，观察差分。
"""
import os
import subprocess
import sys

sys.stdout.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
GAME = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))
DLL = os.path.join(GAME, "System", "main.dll")
HOST = os.path.join(HERE, "xjhost32.exe")
WORK = os.path.join(HERE, "_w15")
_OUT = []


def print(*a):  # noqa: A001
    _OUT.append(" ".join(str(x) for x in a))


def flush(name="_out_15.txt"):
    open(os.path.join(HERE, name), "w", encoding="utf-8").write("\n".join(_OUT))


def run(lines):
    sp = os.path.join(HERE, "_script.txt")
    with open(sp, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    p = subprocess.run([HOST, "script", DLL, sp], cwd=GAME,
                       capture_output=True, timeout=600)
    return (p.stdout or b"").decode("utf-8", "replace")


def hexs(d, n=None):
    return " ".join("%02X" % b for b in (d[:n] if n else d))


def blocks(d):
    return [d[i:i + 8] for i in range(0, len(d) - 7, 8)]


def main():
    os.makedirs(WORK, exist_ok=True)

    # --- 构造样本
    samples = {}
    samples["z64"] = bytes(64)
    p = bytearray(64)
    p[0] = 0xFF
    samples["z64_b0"] = bytes(p)
    p = bytearray(64)
    p[8] = 0xFF
    samples["z64_b8"] = bytes(p)
    p = bytearray(64)
    p[16] = 0xFF
    samples["z64_b16"] = bytes(p)
    p = bytearray(64)
    p[63] = 0xFF
    samples["z64_b63"] = bytes(p)
    p = bytearray(64)
    for i in range(64):
        p[i] = i
    samples["seq64"] = bytes(p)

    lines = []
    for name, data in samples.items():
        open(os.path.join(WORK, name + ".in"), "wb").write(data)
        lines.append("encryption_file;s%s;s%s;s" % (
            os.path.join(WORK, name + ".in"), os.path.join(WORK, name + ".enc")))
    # 同一输入加密两次，看是否确定
    open(os.path.join(WORK, "z64_2.in"), "wb").write(bytes(64))
    lines.append("encryption_file;s%s;s%s;s" % (
        os.path.join(WORK, "z64_2.in"), os.path.join(WORK, "z64_2.enc")))
    print(run(lines))

    print("\n==== 密文（每个样本 64B -> ? B） ====")
    outs = {}
    for name in list(samples) + ["z64_2"]:
        fp = os.path.join(WORK, name + ".enc")
        if not os.path.exists(fp):
            print("  %-10s <缺>" % name)
            continue
        d = open(fp, "rb").read()
        outs[name] = d
        print("  %-10s %3d B  %s" % (name, len(d), hexs(d, 40)))

    print("\n==== 差分：哪个密文块随明文字节变化 ====")
    base = outs.get("z64")
    if base:
        for name in ("z64_b0", "z64_b8", "z64_b16", "z64_b63"):
            d = outs.get(name)
            if not d:
                continue
            diffs = [i for i in range(min(len(base), len(d))) if base[i] != d[i]]
            blks = sorted({i // 8 for i in diffs})
            print("  %-10s 变化字节数=%d  受影响的 8B 块号=%s  首尾=%s" % (
                name, len(diffs), blks, ("%d..%d" % (diffs[0], diffs[-1])) if diffs else "-"))

    print("\n==== 是否 ECB：z64 的密文块是否重复 ====")
    if base:
        bs = blocks(base)
        from collections import Counter
        cnt = Counter(b.hex() for b in bs)
        print("  z64 密文 %d 块，唯一 %d：%s" % (len(bs), len(cnt), cnt.most_common(4)))

    print("\n==== 把 0x00 块的密文与真实存档里的高频块对比 ====")
    if base:
        bs = blocks(base)
        print("  z64 首块 = %s" % bs[0].hex())
        print("  真实存档最高频块 = 37d016ac746442d6")
        print("  相等? %s" % (bs[0].hex() == "37d016ac746442d6"))

    print("\n==== 更大样本：4096 个 0 字节 ====")
    big = os.path.join(WORK, "big0.in")
    open(big, "wb").write(bytes(4096))
    run(["encryption_file;s%s;s%s;s" % (big, os.path.join(WORK, "big0.enc"))])
    fp = os.path.join(WORK, "big0.enc")
    if os.path.exists(fp):
        d = open(fp, "rb").read()
        print("  密文 %d B 前 64: %s" % (len(d), hexs(d, 64)))
        from collections import Counter
        cnt = Counter(b.hex() for b in blocks(d))
        print("  块统计: %s" % cnt.most_common(3))

    flush()


if __name__ == "__main__":
    main()
