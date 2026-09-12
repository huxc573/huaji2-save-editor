# -*- coding: utf-8 -*-
"""探针 22：后台线程跑 qqeat（可能挂住），等几秒后再解密，看密钥是否已被设置。"""
import os
import shutil
import subprocess
import sys

sys.stdout.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
GAME = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))
DLL = os.path.join(GAME, "System", "main.dll")
HOST = os.path.join(HERE, "xjhost32b.exe")
WORK = os.path.join(HERE, "_w22")
LOG = os.path.join(HERE, "_out_22.txt")


def log(*a):
    line = " ".join(str(x) for x in a)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    try:
        print(line)
    except Exception:
        pass


def main():
    if os.path.isdir(WORK):
        shutil.rmtree(WORK, ignore_errors=True)
    os.makedirs(WORK)
    open(LOG, "w", encoding="utf-8").write("")

    lock = os.path.join(WORK, "in.bin")
    out = os.path.join(WORK, "out.bin")
    shutil.copyfile(os.path.join(GAME, "Data", "System.rvdata2"), lock)
    sp = os.path.join(HERE, "_script.txt")
    with open(sp, "w", encoding="utf-8") as f:
        f.write("decryption_file;s%s;s%s;s\n" % (lock, out))

    for ms in (1500, 4000, 8000):
        if os.path.exists(out):
            os.remove(out)
        try:
            p = subprocess.run([HOST, "probe", DLL, "qqeat", str(ms), sp], cwd=GAME,
                               capture_output=True, timeout=120)
            txt = (p.stdout or b"").decode("utf-8", "replace")
            log("---- qqeat 后台 %dms rc=%s ----" % (ms, p.returncode))
            for ln in txt.splitlines():
                if ln.strip():
                    log("   " + ln.strip())
        except subprocess.TimeoutExpired:
            log("---- qqeat 后台 %dms -> 超时 ----" % ms)
        if os.path.exists(out):
            n = os.path.getsize(out)
            hx = open(out, "rb").read(8).hex(" ")
            log("   => 输出 %d B  %s %s" % (n, hx, "★Marshal★" if hx.startswith("04 08") else ""))
        else:
            log("   => 无输出")

    # 顺便试试 init + 解密
    if os.path.exists(out):
        os.remove(out)
    for fn in ("init", "shield"):
        pass
    log("完成")


if __name__ == "__main__":
    main()
