# -*- coding: utf-8 -*-
"""发行版实测：把 dist/ 整个拷到临时目录，跑 exe 的自检。

重点验证"不依赖源码/解释器也能跑"：
  * 清掉 PYTHONHOME / PYTHONPATH / VIRTUAL_ENV 等（否则 PyInstaller 引导会失败）；
  * 在临时目录里跑（cwd 变了也能找到挨着的 XJCodec32.exe）；
  * 读 selftest_result.txt / error.log 判断结果。

用法：python tools/test_dist.py
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.stdout.reconfigure(errors="replace")

DIST = os.path.join(ROOT, "dist")
EXE_NAMES = [n for n in (os.listdir(DIST) if os.path.isdir(DIST) else [])
             if n.endswith(".exe") and "XJCodec" not in n]
BAD_ENV = ("PYTHONHOME", "PYTHONPATH", "PYTHONSTARTUP", "PYTHONEXECUTABLE",
           "VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT")


def find_game(root):
    """从仓库往上找游戏根（含 Game.exe + System/main.dll），供 exe 定位存档。"""
    cur = os.path.abspath(root)
    for _ in range(8):
        if (os.path.exists(os.path.join(cur, "Game.exe"))
                and os.path.isdir(os.path.join(cur, "System"))):
            return cur
        p = os.path.dirname(cur)
        if p == cur:
            break
        cur = p
    return None


def main():
    if not EXE_NAMES:
        print("[NG] dist/ 里没有主程序 exe，先跑 python tools\\build.py")
        return 1
    exe_name = EXE_NAMES[0]
    game = os.environ.get("XJ_GAME") or find_game(ROOT)
    save = os.path.join(game, "save.rvdata2") if game else None
    if not (save and os.path.exists(save)):
        print("[NG] 找不到游戏存档，自检没法跑（设一下 XJ_GAME）")
        return 1
    tmp = tempfile.mkdtemp(prefix="xj_dist_")
    ok = 1
    try:
        work = os.path.join(tmp, "dist")
        shutil.copytree(DIST, work)
        exe = os.path.join(work, exe_name)
        env = dict(os.environ)
        for k in BAD_ENV:
            env.pop(k, None)
        env["XJ_SELFTEST"] = "1"
        env["XJ_GAME"] = game
        env["XJ_SAVE"] = save
        print("发行目录 = %s" % DIST)
        print("拷到 %s 后运行 %s" % (work, exe_name))
        print("（游戏目录 %s，存档 %s）" % (game, save))
        p = subprocess.run([exe], cwd=work, env=env, timeout=300,
                           capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        txt = ""
        for name in ("selftest_result.txt", "error.log"):
            f = os.path.join(work, name)
            if os.path.exists(f):
                txt += open(f, encoding="utf-8", errors="replace").read()
        print("-" * 70)
        print(txt or "(没有自检输出)")
        print("-" * 70)
        lines = txt.splitlines()
        bad = [l for l in lines if "未找到" in l]
        ok = 0 if ("结果: OK" in txt and not bad) else 1
        host_ok = os.path.exists(os.path.join(work, "XJCodec32.exe"))
        print("自检退出码 = %d" % p.returncode)
        _kill_leftover(exe_name)
        if not host_ok:
            print("[NG] XJCodec32.exe 不在 exe 旁边")
        for l in bad:
            print("[NG] %s" % l)
        print("判定 = %s" % ("OK" if not ok else "有问题"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return ok


def _kill_leftover(name):
    """自检的 exe 偶尔会赖着不退（tkinter + onefile 引导），它会锁住 dist 里的文件。"""
    if os.name != "nt":
        return
    try:
        r = subprocess.run(["taskkill", "/f", "/im", name],
                           capture_output=True, text=True, timeout=20)
        out = (r.stdout or "").strip()
        if out:
            print("（清掉没退干净的进程：%s）" % out[:120])
    except Exception:
        pass


if __name__ == "__main__":
    sys.exit(main())
