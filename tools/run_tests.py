# -*- coding: utf-8 -*-
"""一键跑全部回归测试，最后给个总表。

用法：
    python tools/run_tests.py            # 跑全部
    python tools/run_tests.py marshal    # 只跑名字里含 marshal 的

为什么不用一串 shell 命令：本工作区路径含 `!` `【】[]`，
PowerShell 里 `&&`、中文、`!` 都容易被吃掉，串起来经常跑不动。
"""
import hashlib
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
# ⚠ 用 XJ_PY 可以换解释器跑（和 tools/build.py 一个约定）：
# 界面相关的组需要带 tkinter 的解释器（managed 3.13 没有，见下面「跳过」那段）。
PY = os.environ.get("XJ_PY") or sys.executable
sys.path.insert(0, os.path.join(ROOT, "src"))


def _game_running():
    """游戏（Game.exe）现在跑着吗？True / False / None（问不出来）。

    ⚠ 为什么要在意：玩家开着游戏时，**游戏自己**会随时存盘（换地图、手动存档），
    真实存档的指纹自然会变 —— 那不是测试写坏的。指纹校验必须能区分这两种情况，
    否则每次开着游戏跑回归都会误报「存档被测试改动了」。
    """
    try:
        p = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Game.exe"],
                           capture_output=True, timeout=15)
        out = (p.stdout or b"").decode("utf-8", "replace")
        return "Game.exe" in out
    except Exception:
        return None


def _real_save_fingerprint():
    """玩家真实存档的 (路径, 大小, mtime, sha1)。

    ⚠ 为什么要这个：测试/冒烟脚本如果实例化 GUI 时传 save_path=None，
    App 会 _guess_save() 找到**真档**并排队 after(200, load)。
    脚本随后 load(副本) 也会被那个回调顶掉，于是 apply_actor() 改的是
    真档、一保存就写坏玩家存档（2026-09-14 真发生过一次）。
    所以整套回归跑完必须核对真档没被动过；被动过就直接报失败。
    """
    try:
        import paths
        p = paths.save_path()
    except Exception:
        return None
    if not p or not os.path.exists(p):
        return None
    h = hashlib.sha1()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    st = os.stat(p)
    return (p, st.st_size, st.st_mtime_ns, h.hexdigest())

TESTS = [
    ("marshal", ["tests/test_marshal.py"]),
    ("codec", ["tests/test_codec.py"]),
    ("model", ["tests/test_model.py"]),
    ("roundtrip", ["tests/test_roundtrip.py"]),
    ("semantic", ["tests/test_semantic_equal.py"]),
    ("game_layer", ["tests/test_game_layer.py"]),
    ("backup", ["tests/test_backup.py"]),
    ("baby", ["tests/test_baby.py"]),
    ("gui", ["tests/test_gui.py"]),
    ("gui_quick", ["tests/test_gui_quick.py"]),
    ("actor_tab", ["tests/test_actor_tab.py"]),
    ("db_embed", ["tests/test_db_embed.py"]),
    ("bundle_db", ["tests/test_bundle_db_table.py"]),
    ("db_csv", ["tests/test_db_csv.py"]),
    ("smoke", ["tests/smoke.py"]),
    ("save_layer", ["tests/test_save_layer.py"]),
    ("save_files", ["tests/test_save_files.py"]),
    ("verify_all", ["tests/verify_all.py"]),
    ("dist", ["tests/test_dist.py"]),
]

want = [a.lower() for a in sys.argv[1:]]
save_before = _real_save_fingerprint()
rows = []
bad = 0
skipped = []          # [(组名, 原因)] —— 整组一项都没跑
for name, argv in TESTS:
    if want and not any(w in name.lower() for w in want):
        continue
    p = subprocess.run([PY] + argv, cwd=ROOT, capture_output=True)
    txt = ((p.stdout or b"") + (p.stderr or b"")).decode("utf-8", "replace")
    n_ok = len(re.findall(r"\[OK\]", txt))
    n_ng = len(re.findall(r"\[NG\]", txt))
    m = re.search(r"(?:通过|全部通过)\s*=?\s*(\d+)", txt)
    summary = m.group(0).strip() if m else ""
    # ⚠ 退出码 0 ≠ 真的跑了。两种「优雅跳过」都必须标出来，否则就是「看着全绿，
    #    其实一项没跑」—— 2026-09-20 被 tkinter 那个坑过一次（没有 tkinter 的
    #    解释器会让 GUI 组整组静默跳过）；夹具缺失（夹具目录 _plain 是空的）
    #    是同一种形态，用 [SKIP] 自报。
    reason = None
    if re.search(r"没有图形环境，跳过", txt):
        reason = "没有 tkinter（一项都没跑）"
    m2 = re.search(r"^\[SKIP\]\s*(.+)$", txt, re.M)
    if m2:
        reason = m2.group(1).strip()
    if reason:
        skipped.append((name, reason))
    if p.returncode or n_ng:
        bad += 1
    rows.append((name, p.returncode, n_ok, n_ng, reason, summary))
    # 失败的话把详情打出来，方便直接看
    if p.returncode or n_ng:
        print("=" * 70)
        print("### %s 失败，完整输出：" % name)
        print(txt)

print("=" * 70)
print("%-12s %8s %6s %6s  %s" % ("测试", "退出码", "OK", "NG", "摘要"))
for name, rc, ok, ng, reason, s in rows:
    note = ("跳过：" + reason) if reason else s
    print("%-12s %8d %6d %6d  %s" % (name, rc, ok, ng, note))
print("=" * 70)

if skipped:
    print("!!! 这些组一项都没跑（退出码 0 但没验证任何东西）：")
    for name, reason in skipped:
        print("      %-12s %s" % (name, reason))
    if any("tkinter" in r for _, r in skipped):
        print("    界面相关的组请换带 tkinter 的解释器重跑，例如："
              "XJ_PY=D:/Dev/Python/Env/Python312/python.exe python tools/run_tests.py")
    if any("_plain" in r for _, r in skipped):
        print("    夹具缺失的组请先跑： python tools/re/decrypt_all.py")

# 真档指纹校验：测试跑完不许动玩家存档一个字节
save_after = _real_save_fingerprint()
if save_before and save_after and save_before != save_after:
    if _game_running():
        # 游戏开着 → 它自己会存盘，指纹变是正常的，不算失败（但要说清楚）
        print("⚠ 真实存档指纹变了，但 Game.exe 正在运行 —— 多半是**游戏自己**存的档：")
        print("    之前：%r" % (save_before,))
        print("    之后：%r" % (save_after,))
        print("    想确认就关掉游戏再跑一遍；那时还变，才是测试/脚本的问题。")
    else:
        bad += 1
        print("!!! 玩家真实存档被测试改动了，必须排查 !!!")
        print("    之前：%r" % (save_before,))
        print("    之后：%r" % (save_after,))
elif save_before:
    print("真实存档未被改动（sha1 %s…）" % save_before[3][:12])

print("失败项 = %d，%s" % (bad, "全部通过" if not bad else "请看上面的详情"))
sys.exit(1 if bad else 0)
