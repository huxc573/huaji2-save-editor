# -*- coding: utf-8 -*-
"""探针 17：先调用 qqeat / init / init_key，再解密；看全局密钥从哪来。"""
import os
import shutil
import subprocess
import sys

sys.stdout.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
GAME = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))
DLL = os.path.join(GAME, "System", "main.dll")
HOST = os.path.join(HERE, "xjhost32.exe")
WORK = os.path.join(HERE, "_w17")_OUT = []


def print(*a):  # noqa: A001
    _OUT.append(" ".join(str(x) for x in a))


def flush(name="_out_17.txt"):
    open(os.path.join(HERE, name), "w", encoding="utf-8").write("\n".join(_OUT))


def run(lines, tag):
    sp = os.path.join(HERE, "_script.txt")
    with open(sp, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("######## %s ########" % tag)
    try:
        p = subprocess.run([HOST, "script", DLL, sp], cwd=GAME,
                           capture_output=True, timeout=600)
        out = (p.stdout or b"").decode("utf-8", "replace")
        err = (p.stderr or b"").decode("utf-8", "replace")
        for ln in out.splitlines():
            if ln.strip():
                print("  " + ln.rstrip())
        if err.strip():
            print("  STDERR: " + err.strip()[:1500])
        print("  rc=%s" % p.returncode)
    except subprocess.TimeoutExpired:
        print("  [超时/挂住]")
    print()


def main():
    os.makedirs(WORK, exist_ok=True)
    src = os.path.join(GAME, "Data", "System.rvdata2")
    lock = os.path.join(WORK, "sys_in.bin")
    out = os.path.join(WORK, "sys_out.bin")
    shutil.copyfile(src, lock)
    dec = "decryption_file;s%s;s%s;s" % (lock, out)

    def result():
        if os.path.exists(out):
            d = open(out, "rb").read()
            if len(d):
                return "解密 %d B  %s %s" % (len(d), d[:12].hex(" "),
                                            "★Marshal★" if d[:2] == b"\x04\x08" else "")
            return "解密 0 B"
        return "无输出"

    # 1) 只 qqeat
    if os.path.exists(out):
        os.remove(out)
    run(["qqeat", dec], "qqeat -> decryption_file")
    print("  => %s\n" % result())

    # 2) init -> dec
    if os.path.exists(out):
        os.remove(out)
    run(["init", dec], "init -> decryption_file")
    print("  => %s\n" % result())

    # 3) init_key(各种候选) -> dec
    keys = ["", "qqeat", "0", "1", "xjy.11", "画迹2", "huaji2", "huaji",
            "a36839d89d4822fcd7461364c46c4a42", "yqfz", "画迹", "yuán"]
    for k in keys:
        if os.path.exists(out):
            os.remove(out)
        run(["init_key;s%s" % k, dec], "init_key(%r) -> decryption_file" % k)
        r = result()
        print("  => %s\n" % r)
        if "Marshal" in r:
            print("!!!! 命中 key = %r" % k)
            break

    flush()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001
        import traceback
        print("[EXC] %s" % e)
        print(traceback.format_exc())
    finally:
        flush()
