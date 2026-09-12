# -*- coding: utf-8 -*-
"""快速侦察（不做递归求大小，避免卡在 Graphics/Audio）。"""
import os
import subprocess
import sys

sys.stdout.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GITHUB = os.path.dirname(ROOT)
GAME = os.path.normpath(os.path.join(ROOT, "..", "..", ".."))
OUT = os.path.join(HERE, "_recon.txt")

EXPECTED = {"Audio", "AutoSave", "Data", "Fonts", "Graphics", "Logs", "System",
            "Config.ini", "Game.exe", "Game.ini", "save.rvdata2", "was.info",
            "!Tools", ".venv", ".vscode"}


def main():
    L = []
    L.append("GITHUB = %s" % GITHUB)
    L.append("ROOT   = %s" % ROOT)
    L.append("GAME   = %s" % GAME)

    L.append("\n== 1. 游戏根目录（只列一层） ==")
    for name in sorted(os.listdir(GAME)):
        p = os.path.join(GAME, name)
        if os.path.isdir(p):
            try:
                n = len(os.listdir(p))
            except OSError:
                n = -1
            info = "dir  (%d 项)" % n
        else:
            info = "file %d B" % os.path.getsize(p)
        tag = "" if name in EXPECTED else "   <<< 非游戏文件"
        L.append("  %-22s %-22s%s" % (name, info, tag))

    L.append("\n== 2. .venv ==")
    v = os.path.join(GAME, ".venv")
    if os.path.isdir(v):
        L.append("  项数 = %d" % len(os.listdir(v)))
        for name in sorted(os.listdir(v))[:30]:
            L.append("    %s" % name)
        cfg = os.path.join(v, "pyvenv.cfg")
        if os.path.exists(cfg):
            L.append("  --- pyvenv.cfg ---")
            for ln in open(cfg, encoding="utf-8", errors="replace").read().splitlines():
                L.append("    " + ln)
        for sub in ("Lib", os.path.join("Lib", "site-packages")):
            p = os.path.join(v, sub)
            if os.path.isdir(p):
                L.append("  %s: %d 项 -> %s" % (sub, len(os.listdir(p)),
                                                sorted(os.listdir(p))[:12]))
    else:
        L.append("  没有 .venv")

    L.append("\n== 3. !Tools 结构（两层） ==")
    t = os.path.join(GAME, "!Tools")
    if os.path.isdir(t):
        for name in sorted(os.listdir(t)):
            p = os.path.join(t, name)
            L.append("  %s%s" % (name, "/" if os.path.isdir(p) else "  (file)"))
            if os.path.isdir(p) and name.lower() == "github":
                for n2 in sorted(os.listdir(p)):
                    p2 = os.path.join(p, n2)
                    L.append("      %s%s" % (n2, "/" if os.path.isdir(p2) else "  (file)"))
    else:
        L.append("  没有 !Tools")

    L.append("\n== 4. 进程 ==")
    try:
        p = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Game.exe",
                            "/FO", "CSV", "/NH"], capture_output=True, timeout=30)
        txt = (p.stdout or b"").decode("gbk", "replace").strip()
        L.append("  " + (txt or "<无输出>"))
    except Exception as e:
        L.append("  tasklist 失败: %s" % e)

    open(OUT, "w", encoding="utf-8").write("\n".join(L))
    print("done")


if __name__ == "__main__":
    main()
