# -*- coding: utf-8 -*-
"""探针 16：用 decryption_file 解密游戏里各种加密文件，看谁解得开。"""
import os
import shutil
import subprocess
import sys

sys.stdout.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
GAME = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))
DLL = os.path.join(GAME, "System", "main.dll")
HOST = os.path.join(HERE, "xjhost32.exe")
WORK = os.path.join(HERE, "_w16")
_OUT = []


def print(*a):  # noqa: A001
    _OUT.append(" ".join(str(x) for x in a))


def flush(name="_out_16.txt"):
    open(os.path.join(HERE, name), "w", encoding="utf-8").write("\n".join(_OUT))


def run(lines):
    sp = os.path.join(HERE, "_script.txt")
    with open(sp, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    p = subprocess.run([HOST, "script", DLL, sp], cwd=GAME,
                       capture_output=True, timeout=900)
    return (p.stdout or b"").decode("utf-8", "replace")


def main():
    os.makedirs(WORK, exist_ok=True)
    targets = ["Data/System.rvdata2", "Data/Actors.rvdata2", "Data/Classes.rvdata2",
               "Data/Scripts.rvdata2", "Data/Map001.rvdata2", "Data/Items.rvdata2",
               "System/Game.md5", "save.rvdata2",
               "AutoSave/save00.rvdata2", "AutoSave/save05.rvdata2",
               "Logs/Battle/2026-09-12 20-12-16/Battle.bt1"]
    lines = []
    outs = {}
    for i, rel in enumerate(targets):
        src = os.path.join(GAME, rel.replace("/", os.sep))
        if not os.path.exists(src):
            print("  [缺] " + rel)
            continue
        lock = os.path.join(WORK, "in%02d.bin" % i)
        shutil.copyfile(src, lock)
        out = os.path.join(WORK, "out%02d.bin" % i)
        outs[rel] = (lock, out)
        lines.append("decryption_file;s%s;s%s;s" % (lock, out))
    print(run(lines))

    print("\n==== 结果 ====")
    for rel, (lock, out) in outs.items():
        if not os.path.exists(out):
            print("  %-42s <无输出>" % rel)
            continue
        d = open(out, "rb").read()
        src = os.path.join(GAME, rel.replace("/", os.sep))
        n = os.path.getsize(src)
        marshal = len(d) > 2 and d[0] == 4 and d[1] == 8
        print("  %-42s 密文=%-8d 解密=%-8d %s %s" % (
            rel, n, len(d), d[:12].hex(" "), "★Marshal!★" if marshal else ""))

    flush()


if __name__ == "__main__":
    main()
