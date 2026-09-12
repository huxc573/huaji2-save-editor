# -*- coding: utf-8 -*-
"""探针 13：用 32 位宿主调 main.dll，做「加密→解密」往返实验，找出正确参数。"""
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


def flush(name="_out_13.txt"):
    open(os.path.join(HERE, name), "w", encoding="utf-8").write("\n".join(_OUT))


def run_script(lines, tag):
    sp = os.path.join(HERE, "_script.txt")
    with open(sp, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    p = subprocess.run([HOST, "script", DLL, sp], cwd=GAME,
                       capture_output=True, timeout=180)
    out = (p.stdout or b"").decode("utf-8", "replace")
    err = (p.stderr or b"").decode("utf-8", "replace")
    print("---- [%s] rc=%s ----" % (tag, p.returncode))
    print(out.strip())
    if err.strip():
        print("STDERR: " + err.strip()[:2000])
    return out


def head(path, n=16):
    if not os.path.exists(path):
        return "<缺>"
    d = open(path, "rb").read()
    return "%d B  %s" % (len(d), d[:n].hex(" "))


def main():
    plain_src = os.path.join(GAME, "Data", "main.rvdata2")
    plain = os.path.join(HERE, "_plain.bin")
    open(plain, "wb").write(open(plain_src, "rb").read())
    print("明文样本 = Data/main.rvdata2 : %s" % head(plain))

    enc = os.path.join(HERE, "_enc.bin")
    dec = os.path.join(HERE, "_dec.bin")
    enc2 = os.path.join(HERE, "_enc2.bin")

    keys = ["", "0", "1", "xjy.11", "qqeat",
            "a36839d89d4822fcd7461364c46c4a42", "2026"]

    for k in keys:
        for f in (enc, dec, enc2):
            if os.path.exists(f):
                os.remove(f)
        label = k if k else "<空>"
        run_script([
            "encryption_file;s%s;s%s;s%s" % (plain, enc, k),
            "decryption_file;s%s;s%s;s%s" % (enc, dec, k),
            "encryption_file;s%s;s%s;s%s" % (plain, enc2, k),
        ], "key=" + label)
        same12 = (os.path.exists(enc) and os.path.exists(enc2)
                  and open(enc, "rb").read() == open(enc2, "rb").read())
        print("  明文 : %s" % head(plain))
        print("  密文 : %s   (两次加密相同? %s)" % (head(enc), same12))
        print("  还原 : %s   %s" % (
            head(dec),
            "★往返成功★" if (os.path.exists(dec) and
                            open(dec, "rb").read() == open(plain, "rb").read()) else ""))
        print()

    flush()


if __name__ == "__main__":
    main()
