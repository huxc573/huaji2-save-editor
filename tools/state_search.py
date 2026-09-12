# -*- coding: utf-8 -*-
"""逐个"差异片段"探测：哪些字节真正影响 main.dll 的密码输出。

判定：同一段明文，在「无状态」与「写了某片段」两种情况下加密的密文是否不同。
  不同      -> 该片段参与密码运算（密钥状态的一部分）
  变 0 字节 -> 该片段让 DLL 拒绝工作（多半是自校验/指针）
  完全相同  -> 与密码无关

用法： python tools/state_search.py [--max-seg N]
结果： tools/_search.txt
"""
import os
import shutil
import subprocess
import sys

sys.stdout.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GAME = os.path.normpath(os.path.join(ROOT, "..", "..", ".."))
HOST = os.path.join(ROOT, "src", "XJCodec32.exe")
DLL = os.path.join(GAME, "System", "main.dll")
STATE = os.path.join(ROOT, "src", "xj_state.txt")
WORK = os.path.join(HERE, "_ss")
LOG = os.path.join(HERE, "_search.txt")
OURS = os.path.join(HERE, "_ours_main.bin")
PIDDUMP = os.path.join(HERE, "_pid_main.bin")

sys.path.insert(0, HERE)
import make_state as MS  # noqa: E402


def run(args):
    p = subprocess.run([HOST] + args, capture_output=True, timeout=300, cwd=GAME)
    return (p.stdout or b"").decode("utf-8", "replace")


def write_state(segs, b):
    lines = []
    for s, e in segs:
        lines.append("0x%06X %s" % (s, b[s:e + 1].hex()))
    open(STATE, "w", encoding="utf-8").write("\n".join(lines) + "\n")


def enc_head(plain, out):
    if os.path.exists(out):
        os.remove(out)
    run(["encrypt", DLL, plain, out])
    if not os.path.exists(out):
        return 0, ""
    d = open(out, "rb").read()
    return len(d), d[:16].hex(" ")


def main():
    if os.path.isdir(WORK):
        shutil.rmtree(WORK, ignore_errors=True)
    os.makedirs(WORK)
    plain = os.path.join(WORK, "plain.bin")
    open(plain, "wb").write(bytes(range(256)) * 4)

    a = open(OURS, "rb").read()
    b = open(PIDDUMP, "rb").read()
    segs = MS.find_segments(a, b)
    L = []
    L.append("片段数 = %d" % len(segs))
    for i, (s, e) in enumerate(segs):
        L.append("  #%-2d RVA 0x%06X 长度 %-5d %s" % (
            i, s, e - s + 1, b[s:min(e + 1, s + 24)].hex(" ")))

    # 还原备份，保证测完不留垃圾
    bak = STATE + ".bak"
    had = os.path.exists(STATE)
    if had:
        shutil.copyfile(STATE, bak)
    try:
        if os.path.exists(STATE):
            os.remove(STATE)
        n0, h0 = enc_head(plain, os.path.join(WORK, "base.bin"))
        L.append("\n基线（无状态）：长度=%d 头=%s" % (n0, h0))

        L.append("\n==== 单个片段 ====")
        effect = []
        for i, (s, e) in enumerate(segs):
            write_state([(s, e)], b)
            n, h = enc_head(plain, os.path.join(WORK, "s%d.bin" % i))
            same = (n == n0 and h == h0)
            tag = "无影响" if same else ("输出 0 字节（拒绝工作）" if n == 0 else "★改变了密码输出★")
            L.append("  #%-2d len=%-5d -> %-6d %s  %s" % (i, e - s + 1, n, h, tag))
            if not same and n > 0:
                effect.append(i)

        L.append("\n改变输出的片段 = %s" % effect)
        if effect:
            write_state([segs[i] for i in effect], b)
            n, h = enc_head(plain, os.path.join(WORK, "combo.bin"))
            L.append("只用这些片段：长度=%d 头=%s（基线 %d / %s）" % (n, h, n0, h0))
            # 试解密
            for rel in ("Data/System.rvdata2", "save.rvdata2"):
                src = os.path.join(GAME, rel.replace("/", os.sep))
                out = os.path.join(WORK, "dec_" + os.path.basename(rel))
                if os.path.exists(out):
                    os.remove(out)
                run(["decrypt", DLL, src, out])
                sz = os.path.getsize(out) if os.path.exists(out) else 0
                marshal = ""
                if sz:
                    d = open(out, "rb").read(4)
                    marshal = " ★Marshal★" if d[:2] == b"\x04\x08" else ""
                L.append("  解密 %-20s -> %d 字节%s" % (rel, sz, marshal))
    finally:
        if had and os.path.exists(bak):
            shutil.copyfile(bak, STATE)
            os.remove(bak)

    open(LOG, "w", encoding="utf-8").write("\n".join(L))
    print("done")


if __name__ == "__main__":
    main()
