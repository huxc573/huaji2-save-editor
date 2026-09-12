# -*- coding: utf-8 -*-
"""穷举 main.dll 的所有（安全的）导出，看哪个调用之后能解密游戏原档。

每个候选都在**独立进程**里试（状态会串），顺序：候选调用 -> decryption_file。
结果：tools/_try_exports.txt

用法： python tools/try_exports.py            # 自动提权
"""
import ctypes
import os
import shutil
import subprocess
import sys

sys.stdout.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GAME = os.path.normpath(os.path.join(ROOT, "..", "..", ".."))
DLL = os.path.join(GAME, "System", "main.dll")
HOST = os.path.join(ROOT, "probes", "xjhost32b.exe")
WORK = os.path.join(HERE, "_te")
LOG = os.path.join(HERE, "_try_exports.txt")
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


CANDIDATES = [
    ["test"],
    ["init_debug", "i0"], ["init_debug", "i1"], ["init_debug", "e"],
    ["shield", "e", "e"], ["shield", "i0", "i0"], ["shield", "i1", "i1"],
    ["get_md5", "s" + os.path.join(GAME, "Game.exe")],
    ["get_md5", "s" + os.path.join(GAME, "System", "Game.md5")],
    ["readFile", "s" + os.path.join(GAME, "System", "Game.md5")],
    ["readFile", "s" + os.path.join(GAME, "was.info")],
    ["read", "i0"], ["read", "e"],
    ["seek", "i0", "i0"], ["seek", "e", "e"],
    ["net_wrong_count"],
    ["utf8_to_ansi", "sabc"],
    ["get_fsp"], ["find_fsp", "sabc"], ["find_fsp", "s" + os.path.join(GAME, "Data")],
    ["file_enum", "e"], ["file_enum", "s" + os.path.join(GAME, "System")],
    ["dir_count", "s" + os.path.join(GAME, "System")],
    ["get_ttf_name", "e"],
    ["copy_text", "sabc"], ["copy", "sabc"],
    ["init_key", "s0"], ["init_key", "s1"],
    ["init"], ["dispose_key"],
    ["get_qq"], ["init_key", "s" + os.path.join(GAME, "was.info")],
]


def main():
    if not is_admin():
        if relaunch():
            print("已请求管理员权限（UAC 点「是」），进度看 tools/_try_exports.txt")
            return 0
        print("[NG] 提权失败")
        return 1

    os.makedirs(WORK, exist_ok=True)
    src = os.path.join(GAME, "Data", "System.rvdata2")
    lock = os.path.join(WORK, "in.bin")
    out = os.path.join(WORK, "out.bin")

    L = ["admin = %s" % is_admin()]
    hits = []
    for cand in CANDIDATES:
        shutil.copyfile(src, lock)
        if os.path.exists(out):
            os.remove(out)
        lines = [";".join(cand),
                 "decryption_file;s%s;s%s;s" % (lock, out)]
        with open(SCRIPT, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        tag = " ".join(cand)[:70]
        try:
            p = subprocess.run([HOST, "script", DLL, SCRIPT], capture_output=True,
                               timeout=90, cwd=GAME)
            txt = (p.stdout or b"").decode("utf-8", "replace")
            rc = p.returncode
            rets = [ln.strip() for ln in txt.splitlines() if "ret=" in ln]
        except subprocess.TimeoutExpired:
            rc, rets = "timeout", ["<超时>"]
        sz = os.path.getsize(out) if os.path.exists(out) else 0
        mark = ""
        if sz:
            d = open(out, "rb").read(4)
            mark = "  ★Marshal★" if d[:2] == b"\x04\x08" else "  (非 Marshal)"
            hits.append((tag, sz))
        L.append("%-72s rc=%-6s 输出=%-8d %s | %s" % (
            tag, rc, sz, mark, " / ".join(rets)[:120]))

    L.append("\n命中：%s" % (hits or "无"))
    open(LOG, "w", encoding="utf-8").write("\n".join(L))
    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
