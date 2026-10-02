# -*- coding: utf-8 -*-
r"""发行包自检：**该有的东西一个都不能少**（对应画迹1 v1.4.0 修的那个坑）。

把 `dist` 里的 exe 单独拷进临时目录，分两种情形各跑一次官方自检：

  A) 只拷 exe（模拟「别人只下了主程序，漏掉 XJCodec32.exe」）
  B) exe + XJCodec32.exe（完整）

宿主 `XJCodec32.exe` **不在** onefile 里（`codec.host_candidates()` 是在 exe 所在
目录找它的），所以少了下它就是「打开失败 / 缺少依赖」，整个工具都用不了 ——
这正是 `pack_zip()` 把三个文件打成一个 zip、`RELEASE_ASSETS` 只挂一个附件的原因。

发版前跑一次：

    python tools/check_pack.py

期望：A 组 `32 位宿主: 未找到` + `结果: NG`；B 组 `结果: OK`。

⚠ 存档用副本（先拷进临时目录），绝不碰真档。
⚠ 必须跑**拷进临时目录的那份** exe：跑 `dist\` 里那份会把 `selftest_result.txt` /
  `last_save.txt` 写回 `dist\`，下次测试就摸到真档了。
"""
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

import paths  # noqa: E402

DIST = os.path.join(ROOT, "dist")
EXE = os.path.join(DIST, "画迹2内测版存档工具.exe")
HOST = os.path.join(DIST, "XJCodec32.exe")
TMPROOT = os.path.join(os.environ.get("TEMP", "."), "xj_pack")


def kill_tree(pid):
    subprocess.run(["taskkill", "/f", "/t", "/pid", str(pid)],
                   capture_output=True)


def run_case(tag, with_host, game, save):
    tmp = os.path.join(TMPROOT, tag)
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)
    exe2 = os.path.join(tmp, os.path.basename(EXE))
    shutil.copy2(EXE, exe2)
    if with_host:
        shutil.copy2(HOST, os.path.join(tmp, "XJCodec32.exe"))
    save_copy = os.path.join(tmp, "save_copy.rvdata2")
    shutil.copy2(save, save_copy)

    env = dict(os.environ)
    for k in ("PYTHONHOME", "PYTHONPATH", "PYTHONSTARTUP",
              "PYTHONEXECUTABLE", "VIRTUAL_ENV"):
        env.pop(k, None)
    env["XJ_SELFTEST"] = "1"
    env["XJ_GAME"] = game
    env["XJ_SAVE"] = save_copy

    log = os.path.join(tmp, "stdout.log")
    with open(log, "wb") as fh:
        p = subprocess.Popen([exe2], cwd=tmp, env=env,
                             stdout=fh, stderr=subprocess.STDOUT)
        res = os.path.join(tmp, "selftest_result.txt")
        deadline = time.time() + 90
        while time.time() < deadline:
            if os.path.exists(res) or p.poll() is not None:
                break
            time.sleep(0.5)
        killed = p.poll() is None
        if killed:
            kill_tree(p.pid)
            try:
                p.wait(timeout=20)
            except Exception:
                pass
    print("\n" + "=" * 70)
    print("[%s] 拷贝进临时目录的 = %s" % (
        tag, "exe + XJCodec32.exe" if with_host else "**只有 exe**"))
    print("    exe 退出码 %s%s" % (p.returncode, "（我们 taskkill 的）"
                                  if killed else ""))
    got = []
    for name in ("selftest_result.txt", "error.log"):
        f = os.path.join(tmp, name)
        if os.path.exists(f):
            print("  --- %s ---" % name)
            print(open(f, encoding="utf-8", errors="replace").read().strip())
            got.append(name)
        else:
            print("  --- %s --- (没有)" % name)
    # 控制台输出只在**没有结果文件**时才看（打包引导的噪音很多，而且 exe 是
    # --windowed 启动的、中文按 GBK 落盘，直接 dump 出来就是一屏乱码）
    if not got:
        txt = open(log, "rb").read().decode("gbk", "replace").strip()
        if txt:
            print("  --- 控制台输出（前 8 行）---")
            print("\n".join(txt.splitlines()[:8]))
    return tmp, "\n".join(
        open(os.path.join(tmp, n), encoding="utf-8", errors="replace").read()
        for n in got), got


def main():
    if not os.path.exists(EXE):
        print("[NG] 没有 %s，先跑 python tools/build.py" % EXE)
        return 1
    game = paths.find_game_dir()
    if not game:
        print("[NG] 找不到游戏目录")
        return 1
    save = os.path.join(game, "save.rvdata2")
    print("游戏目录 = %s" % game)
    print("真档     = %s（只读，拷副本给自检）" % save)
    print("exe      = %s（%.1f MB，%s）"
          % (EXE, os.path.getsize(EXE) / 1048576.0,
             time.strftime("%Y-%m-%d %H:%M",
                           time.localtime(os.path.getmtime(EXE)))))
    _, a_txt, a_got = run_case("A_nohost", False, game, save)
    _, b_txt, b_got = run_case("B_withhost", True, game, save)
    shutil.rmtree(TMPROOT, ignore_errors=True)

    # ------------------------------------------------------------------
    # 判定：两种情形都必须是"预想中的那样"，否则就是发行包有洞
    # ------------------------------------------------------------------
    print("\n" + "=" * 70)
    bad = []

    def check(name, ok, extra=""):
        print("  [%s] %s %s" % ("OK" if ok else "NG", name, extra))
        if not ok:
            bad.append(name)

    check("A 组（只拷 exe）能写出自检结果文件", bool(a_txt))
    check("A 组报「32 位宿主: 未找到」", "32 位宿主: 未找到" in a_txt)
    check("A 组结果 = NG（少了宿主就是用不了）", "结果: NG" in a_txt)
    check("B 组（exe + 宿主）结果 = OK", "结果: OK" in b_txt)
    check("B 组找到宿主（不是「未找到」）", "32 位宿主: 未找到" not in b_txt)
    check("两组都没落 error.log", "error.log" not in a_got + b_got)
    if bad:
        print("\n===== 发行包自检：有失败（%d 项）=====" % len(bad))
        for n in bad:
            print("  -", n)
        return 1
    print("\n===== 发行包自检：通过（发到 Release 上的是单个 zip，不会漏下宿主）=====")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")
    sys.exit(main())
