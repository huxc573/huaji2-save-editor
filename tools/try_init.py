# -*- coding: utf-8 -*-
"""用管理员权限，把 main.dll 的各种"初始化"入口都试一遍，看哪个能把密钥状态装好。

用法： python tools/try_init.py           # 会自动弹 UAC
结果： tools/_try_init.txt
"""
import ctypes
import os
import subprocess
import sys

sys.stdout.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GAME = os.path.normpath(os.path.join(ROOT, "..", "..", ".."))
DLL = os.path.join(GAME, "System", "main.dll")
HOST = os.path.join(ROOT, "probes", "xjhost32b.exe")
WORK = os.path.join(HERE, "_ti")
LOG = os.path.join(HERE, "_try_init.txt")
SCRIPT = os.path.join(WORK, "script.txt")


def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch():
    params = " ".join('"%s"' % a for a in sys.argv[1:])
    return ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable,
        '"%s" %s' % (os.path.abspath(__file__), params), ROOT, 1) > 32


def main():
    if not is_admin():
        if relaunch():
            print("已请求管理员权限（请在 UAC 弹窗点「是」），结果看 tools/_try_init.txt")
            return 0
        print("[NG] 提权失败")
        return 1

    os.makedirs(WORK, exist_ok=True)
    src = os.path.join(GAME, "Data", "System.rvdata2")
    lock = os.path.join(WORK, "in.bin")
    out = os.path.join(WORK, "out.bin")

    L = []
    L.append("admin = %s" % is_admin())
    L.append("host = %s" % HOST)

    def test(tag, lines, mode="script", wait=None):
        import shutil
        shutil.copyfile(src, lock)
        if os.path.exists(out):
            os.remove(out)
        with open(SCRIPT, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        args = [HOST, mode, DLL]
        if mode == "probe":
            args += ["qqeat", str(wait)]
        args.append(SCRIPT)
        try:
            p = subprocess.run(args, capture_output=True, timeout=180, cwd=GAME)
            txt = (p.stdout or b"").decode("utf-8", "replace")
            rc = p.returncode
        except subprocess.TimeoutExpired:
            txt, rc = "<超时>", "timeout"
        sz = os.path.getsize(out) if os.path.exists(out) else 0
        head = ""
        if sz:
            d = open(out, "rb").read(8)
            head = d.hex(" ") + ("  ★Marshal★" if d[:2] == b"\x04\x08" else "")
        L.append("\n---- %s (mode=%s rc=%s) ----" % (tag, mode, rc))
        for ln in txt.splitlines():
            if ln.strip() and not ln.startswith(">> "):
                L.append("   " + ln.strip())
        L.append("   => 输出 %d 字节 %s" % (sz, head))
        return sz > 0

    dec = "decryption_file;s%s;s%s;s" % (lock, out)

    test("基线：什么都不调，直接解密", [dec])
    test("init -> 解密", ["init", dec])
    test("init_key('') -> 解密", ["init", "init_key;s", dec])
    test("init -> init_key -> get_hard_disk_character -> 解密",
         ["init", "init_key;s", "get_hard_disk_character", dec])
    test("qqeat（后台线程等 10 秒）-> 解密", [dec], mode="probe", wait=10000)
    test("qqeat（后台线程等 20 秒）-> 解密", [dec], mode="probe", wait=20000)
    test("dispose_key -> 解密", ["dispose_key", dec])
    test("init_key('was.info') -> 解密", ["init_key;swas.info", dec])

    open(LOG, "w", encoding="utf-8").write("\n".join(L))
    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
