# -*- coding: utf-8 -*-
"""探针 14：往返实验 v2 —— 输入长度取 8 的倍数，先试空口令。"""
import os
import subprocess
import sys

sys.stdout.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
GAME = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))
DLL = os.path.join(GAME, "System", "main.dll")
HOST = os.path.join(HERE, "xjhost32.exe")
_OUT = []


def print(*a):  # noqa: A001
    _OUT.append(" ".join(str(x) for x in a))


def flush(name="_out_14.txt"):
    open(os.path.join(HERE, name), "w", encoding="utf-8").write("\n".join(_OUT))


def run(lines, tag):
    sp = os.path.join(HERE, "_script.txt")
    with open(sp, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    p = subprocess.run([HOST, "script", DLL, sp], cwd=GAME,
                       capture_output=True, timeout=300)
    out = (p.stdout or b"").decode("utf-8", "replace")
    print("---- [%s] rc=%s ----" % (tag, p.returncode))
    for ln in out.splitlines():
        if ln.startswith(">> "):
            continue
        print(ln.rstrip())
    return out


def info(path):
    if not os.path.exists(path):
        return "<缺>"
    d = open(path, "rb").read()
    return "%d B  %s" % (len(d), d[:12].hex(" "))


def main():
    # 造一个 8 字节整数倍的明文样本：用 Battle.bt2 明文 + 补零到 2048
    src = os.path.join(GAME, "Logs", "Battle")
    sample = None
    for d in sorted(os.listdir(src)):
        p = os.path.join(src, d, "Battle.bt2")
        if os.path.exists(p):
            sample = p
            break
    raw = open(sample, "rb").read() if sample else b""
    raw = (raw + b"\0" * 2048)[:2048]
    plain = os.path.join(HERE, "_plain.bin")
    open(plain, "wb").write(raw)
    print("明文样本 %s -> 2048 B (取自语 %s)" % (sample, "Battle.bt2"))

    enc = os.path.join(HERE, "_enc.bin")
    dec = os.path.join(HERE, "_dec.bin")

    keys = ["", "0", "1", "qqeat", "a36839d89d4822fcd7461364c46c4a42", "xjy.11"]
    for k in keys:
        for f in (enc, dec):
            if os.path.exists(f):
                os.remove(f)
        label = k if k else "<空>"
        run([
            "encryption_file;s%s;s%s;s%s" % (plain, enc, k),
            "decryption_file;s%s;s%s;s%s" % (enc, dec, k),
        ], "key=" + label)
        ok = (os.path.exists(dec) and open(dec, "rb").read() == raw)
        print("  明文 %s\n  密文 %s\n  还原 %s  %s" % (
            info(plain), info(enc), info(dec), "★往返成功★" if ok else ""))
        print()

    # 补一个：直接尝试解密真正的存档
    save_copy = os.path.join(HERE, "_save_copy.bin")
    open(save_copy, "wb").write(open(os.path.join(GAME, "save.rvdata2"), "rb").read())
    print("真实存档副本: %s" % info(save_copy))
    for k in keys:
        out = os.path.join(HERE, "_save_dec_%d.bin" % keys.index(k))
        if os.path.exists(out):
            os.remove(out)
        run(["decryption_file;s%s;s%s;s%s" % (save_copy, out, k)], "解密真存档 key=" + (k or "<空>"))
        print("  -> %s" % info(out))

    flush()


if __name__ == "__main__":
    main()
