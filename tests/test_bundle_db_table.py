# -*- coding: utf-8 -*-
"""打包版实测：把 exe 放到一个「游戏目录里没有可用的 Data 表」的地方跑。

这条就是「资源忘了打包进 exe」那个坑的看门狗（画迹1 同类测试修的就是它）：

  1. **内置名字表真被打进 exe 了** —— 沙箱里 `Data\\Skills.rvdata2` 是坏的、
     其余 Data 表压根没有，自检里技能名还得是「牛刀小试」而不是 `?`；
  2. **读不到 Data 表只降级、不崩** —— 自检整体 `结果: OK`、没有 error.log；
  3. 顺带钉住「读的是沙箱副本，不是真档」。

⚠ 必须跑**沙箱里那份** exe（`codec.app_dir()` = exe 所在目录，跑 dist 里那份
  会把 `selftest_result.txt` / `last_save.txt` 写回 dist，下次测试就摸到真档了）。

用法：python tests/test_bundle_db_table.py      （要 Py3.12：只是要 tkinter 之外的一致环境）
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)
sys.stdout.reconfigure(errors="replace")

import paths  # noqa: E402

DIST = os.path.join(ROOT, "dist")
EXE_NAME = "画迹2内测版存档工具.exe"
HOST_NAME = "XJCodec32.exe"
BAD = ("PYTHONHOME", "PYTHONPATH", "PYTHONSTARTUP", "PYTHONEXECUTABLE",
       "VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT")

FAILS = []
N_OK = 0


def check(name, ok, extra=""):
    """⚠ 必须打 `[OK]` / `[NG]`：`tools/run_tests.py` 是按这两个标记数项的，
    打成别的字样会显示成「0 项」—— 那就是"看着全绿其实一项没跑"。"""
    global N_OK
    if ok:
        N_OK += 1
    print("  [%s] %s %s" % ("OK" if ok else "NG", name, extra))
    if not ok:
        FAILS.append(name)


def main():
    print("== 环境 ==")
    game = paths.find_game_dir()
    exe = os.path.join(DIST, EXE_NAME)
    host = os.path.join(DIST, HOST_NAME)
    if not game:
        print("[SKIP] 找不到游戏目录")
        return 0
    for p in (exe, host):
        if not os.path.exists(p):
            print("[SKIP] 缺少 %s（先跑 python tools/build.py）" % p)
            return 0
    save = os.path.join(game, "save.rvdata2")
    main_dll = os.path.join(game, "System", "main.dll")
    for p in (save, main_dll):
        if not os.path.exists(p):
            print("[SKIP] 缺少 %s" % p)
            return 0

    # ------------------------------------------------------------------
    # 沙箱：既当「程序目录」又当「游戏目录」
    # ------------------------------------------------------------------
    dst = os.path.join(tempfile.gettempdir(), "xj_bundle_nodb")
    if os.path.isdir(dst):
        shutil.rmtree(dst, ignore_errors=True)
    os.makedirs(os.path.join(dst, "Data"))
    os.makedirs(os.path.join(dst, "System"))
    # 1) 程序那部分：整套 dist（exe + 宿主 + 说明），去掉上次留下的状态文件
    for n in os.listdir(DIST):
        s = os.path.join(DIST, n)
        if os.path.isfile(s) and n not in ("selftest_result.txt", "error.log",
                                           "last_save.txt"):
            shutil.copyfile(s, os.path.join(dst, n))
        elif os.path.isdir(s) and n.lower() == "dll":
            shutil.copytree(s, os.path.join(dst, "dll"))
    # 2) 游戏那部分：够 is_game_dir 认 + 能解存档
    shutil.copyfile(os.path.join(game, "Game.exe"), os.path.join(dst, "Game.exe"))
    shutil.copyfile(os.path.join(game, "Game.ini"), os.path.join(dst, "Game.ini"))
    shutil.copyfile(main_dll, os.path.join(dst, "System", "main.dll"))
    save_copy = os.path.join(dst, "save.rvdata2")
    shutil.copyfile(save, save_copy)
    # 3) Data 表：一张坏的、其余没有 —— 老做法这里名字全会变 `?`
    bad_bytes = b"\xff" * 64
    with open(os.path.join(dst, "Data", "Skills.rvdata2"), "wb") as f:
        f.write(bad_bytes)
    for n in ("last_save.txt", "selftest_result.txt", "error.log"):
        p = os.path.join(dst, n)
        if os.path.exists(p):
            os.unlink(p)
    print("沙箱（Data 里只有一张坏掉的 Skills.rvdata2）:", dst)

    # 沙箱自证：这份坏文件本身确实是"读不出来"的
    import marshal_ruby as M
    try:
        M.parse_stream(bad_bytes)
        check("沙箱里的坏 Skills.rvdata2 真能读坏（否则这条测试没意义）", False)
    except Exception as e:
        check("沙箱里的坏 Skills.rvdata2 真能读坏（否则这条测试没意义）", True,
              type(e).__name__)

    # ------------------------------------------------------------------
    # 跑沙箱里那份 exe
    # ------------------------------------------------------------------
    env = dict(os.environ)
    env["XJ_SELFTEST"] = "1"
    env["XJ_GAME"] = dst
    env["XJ_SAVE"] = save_copy
    for k in BAD:
        env.pop(k, None)
    exe2 = os.path.join(dst, os.path.basename(exe))
    with open(os.path.join(dst, "stdout.log"), "wb") as fh:
        proc = subprocess.Popen([exe2, save_copy], cwd=dst, env=env,
                                stdout=fh, stderr=subprocess.STDOUT)
        res = os.path.join(dst, "selftest_result.txt")
        deadline = time.time() + 180
        while time.time() < deadline:
            if os.path.exists(res) or proc.poll() is not None:
                break
            time.sleep(0.5)
        killed = proc.poll() is None
        subprocess.run(["taskkill", "/f", "/t", "/pid", str(proc.pid)],
                       capture_output=True)
    txt = ""
    if os.path.exists(res):
        txt = open(res, encoding="utf-8", errors="replace").read()
    for ln in txt.splitlines():
        if any(k in ln for k in ("32 位宿主", "游戏目录", "存档:", "名字表",
                                 "技能名自检", "召唤兽 ", "结果:")):
            print("   " + ln)

    # ------------------------------------------------------------------
    # 断言
    # ------------------------------------------------------------------
    check("打包版生成了 selftest_result.txt", bool(txt), "(没退干净：%s)"
          % ("是" if killed else "否"))
    check("自检整体结果 = OK", "结果: OK" in txt)
    check("宿主来自沙箱", os.path.join("xj_bundle_nodb", HOST_NAME) in txt
          or "32 位宿主: 未找到" not in txt)
    check("读的是沙箱存档（不是真档）", "xj_bundle_nodb" in txt)
    # 核心：名字来自内置表（老做法这里全是 `?`）
    check("名字表来源 = 内置表", "名字表: 内置表" in txt)
    check("技能 9 = 牛刀小试（内置表）", "技能名自检: 9=牛刀小试" in txt)
    check("技能 1 = 攻击（内置表）", "1=攻击" in txt)
    check("没退化成 `?`", "技能名自检: 9=? " not in txt
          and not txt.count("技能名自检: 9=?/"))
    # ⚠ 不写死召唤兽名字：跑的是真档的副本，玩家练级/改名都会变
    check("召唤兽名出得来（不是「无」）",
          "召唤兽 = " in txt and "召唤兽 = 无" not in txt)
    check("没有 error.log", not os.path.exists(os.path.join(dst, "error.log")))

    print()
    if FAILS:
        print("==== 通过 %d, 失败 %d ====" % (N_OK, len(FAILS)))
        print("===== 打包版·无 Data 表测试：有失败（%d 项）=====" % len(FAILS))
        for f in FAILS:
            print("  -", f)
        print("（沙箱留在 %s，stdout.log 也在里面）" % dst)
        return 1
    print("==== 通过 %d, 失败 0 ====" % N_OK)
    print("===== 打包版·无 Data 表测试：通过 =====")
    shutil.rmtree(dst, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
