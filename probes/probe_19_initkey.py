# -*- coding: utf-8 -*-
"""探针 19：在沙箱目录里试 init_key 的各种候选；并检查游戏目录有没有被污染。

每步都把结果追加写进 _out_19.txt，避免中途被杀丢日志。
"""
import os
import shutil
import subprocess
import sys

sys.stdout.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
GAME = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))
DLL = os.path.join(GAME, "System", "main.dll")
HOST = os.path.join(HERE, "xjhost32.exe")
SBOX = os.path.join(HERE, "_sandbox")
LOG = os.path.join(HERE, "_out_19.txt")


def print(*a):  # noqa: A001
    line = " ".join(str(x) for x in a)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


open(LOG, "w", encoding="utf-8").write("")

SKIP_DIRS = {"!Tools", ".venv", "Audio", "Graphics", "Fonts", "AutoSave", "Logs"}


def build_sandbox():
    if os.path.isdir(SBOX):
        shutil.rmtree(SBOX, ignore_errors=True)
    os.makedirs(SBOX)
    for name in ("Config.ini", "Game.ini", "save.rvdata2", "was.info"):
        src = os.path.join(GAME, name)
        if os.path.exists(src):
            shutil.copyfile(src, os.path.join(SBOX, name))
    os.makedirs(os.path.join(SBOX, "System"))
    for name in ("main.dll", "RGSS301.dll", "ws2_32.dll", "AStar.dll", "Game.md5"):
        src = os.path.join(GAME, "System", name)
        if os.path.exists(src):
            shutil.copyfile(src, os.path.join(SBOX, "System", name))
    os.makedirs(os.path.join(SBOX, "Data"))
    for name in ("main.rvdata2", "System.rvdata2"):
        src = os.path.join(GAME, "Data", name)
        if os.path.exists(src):
            shutil.copyfile(src, os.path.join(SBOX, "Data", name))
    os.makedirs(os.path.join(SBOX, "Logs", "Temp"), exist_ok=True)
    os.makedirs(os.path.join(SBOX, "Logs", "value"), exist_ok=True)


def run(lines, tag):
    sp = os.path.join(HERE, "_script.txt")
    with open(sp, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    try:
        p = subprocess.run([HOST, "script", os.path.join(SBOX, "System", "main.dll"), sp],
                           cwd=SBOX, capture_output=True, timeout=300)
        out = (p.stdout or b"").decode("utf-8", "replace")
        for ln in out.splitlines():
            if ln.strip() and not ln.startswith(">> "):
                print("    " + ln.strip())
        print("    rc=%s" % p.returncode)
    except subprocess.TimeoutExpired:
        print("    [超时]")
    except Exception as e:  # noqa: BLE001
        print("    [EXC %s]" % e)


def main():
    # --- 1. 污染检查
    print("==== 1. 目录污染检查 ====")
    for label, d in (("probes", HERE), ("game", GAME)):
        extra = []
        for name in sorted(os.listdir(d)):
            p = os.path.join(d, name)
            if os.path.isfile(p) and name in ("0", "1", "qqeat", "xjy.11"):
                extra.append((name, os.path.getsize(p)))
        print("  %s 可疑文件: %s" % (label, extra))
    print()

    build_sandbox()
    print("沙箱: %s" % SBOX)

    out = os.path.join(SBOX, "Data", "sys_out.bin")
    lock = os.path.join(SBOX, "Data", "sys_in.bin")
    dec = "decryption_file;s%s;s%s;s" % (lock, out)

    candidates = [
        ("（不调 init_key）", None),
        ("空串", ""),
        ("md5(Config.ini)", "a36839d89d4822fcd7461364c46c4a42"),
        ("was.info", "was.info"),
        ("Config.ini", "./Config.ini"),
        ("Game.ini", "./Game.ini"),
        ("Game.md5", "System/Game.md5"),
        ("main.dll", "System/main.dll"),
        ("qqeat", "qqeat"),
        ("xjy.11", "xjy.11"),
    ]
    print("\n==== 2. init_key 候选测试 ====")
    for label, key in candidates:
        shutil.copyfile(os.path.join(GAME, "Data", "System.rvdata2"), lock)
        if os.path.exists(out):
            os.remove(out)
        lines = []
        if key is not None:
            lines.append("init_key;s%s" % key)
        lines.append(dec)
        print("-- %s (key=%r)" % (label, key))
        run(lines, label)
        if os.path.exists(out):
            n = os.path.getsize(out)
            head = open(out, "rb").read(8).hex(" ")
            print("    => 输出 %d B  %s %s" % (n, head,
                                              "★Marshal★" if head.startswith("04 08") else ""))
        else:
            print("    => 无输出")

    print("\n==== 3. 先 init_key 再 qqeat 再 dec ====")
    for label, key in (("qqeat", None), ("was.info", "was.info")):
        shutil.copyfile(os.path.join(GAME, "Data", "System.rvdata2"), lock)
        if os.path.exists(out):
            os.remove(out)
        lines = []
        if key:
            lines.append("init_key;s%s" % key)
        lines += ["qqeat", dec]
        print("-- %s" % label)
        run(lines, label)
        if os.path.exists(out):
            print("    => 输出 %d B %s" % (os.path.getsize(out),
                                         open(out, "rb").read(8).hex(" ")))
        else:
            print("    => 无输出")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001
        import traceback
        print("[EXC] %s" % e)
        print(traceback.format_exc())
