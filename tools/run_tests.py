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
PY = sys.executable
sys.path.insert(0, os.path.join(ROOT, "src"))


def _real_save_fingerprint():
    """玩家真实存档的 (路径, 大小, mtime, sha1)。

    ⚠ 为什么要这个：测试/冒烟脚本如果实例化 GUI 时传 save_path=None，
    App 会 _guess_save() 找到**真档**并排队 after(200, load)。
    脚本随后 load(副本) 也会被那个回调顶掉，于是 apply_actor() 改的是
    真档、一保存就写坏玩家存档（2026-09-14 真发生过一次）。
    所以整套回归跑完必须核对真档没被动过；被动过就直接报失败。
    """
    try:
        import xj_env
        p = xj_env.save_path()
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
    ("roundtrip", ["tools/test_roundtrip.py"]),
    ("semantic", ["tools/test_semantic_equal.py"]),
    ("game_layer", ["tools/test_game_layer.py"]),
    ("backup", ["tools/test_backup.py"]),
    ("baby", ["tools/test_baby.py"]),
    ("gui", ["tests/test_gui.py"]),
    ("gui_quick", ["tests/test_gui_quick.py"]),
    ("actor_tab", ["tools/_smoke_actor_tab.py"]),
    ("db_csv", ["tools/test_db_csv.py"]),
    ("smoke", ["tools/smoke.py"]),
    ("save_layer", ["tools/test_save_layer.py"]),
    ("save_files", ["tests/test_save_files.py"]),
    ("verify_all", ["tools/verify_all.py"]),
    ("dist", ["tools/test_dist.py"]),
]

want = [a.lower() for a in sys.argv[1:]]
save_before = _real_save_fingerprint()
rows = []
bad = 0
for name, argv in TESTS:
    if want and not any(w in name.lower() for w in want):
        continue
    p = subprocess.run([PY] + argv, cwd=ROOT, capture_output=True)
    txt = ((p.stdout or b"") + (p.stderr or b"")).decode("utf-8", "replace")
    n_ok = len(re.findall(r"\[OK\]", txt))
    n_ng = len(re.findall(r"\[NG\]", txt))
    m = re.search(r"(?:通过|全部通过)\s*=?\s*(\d+)", txt)
    summary = m.group(0).strip() if m else ""
    if p.returncode or n_ng:
        bad += 1
    rows.append((name, p.returncode, n_ok, n_ng, summary))
    # 失败的话把详情打出来，方便直接看
    if p.returncode or n_ng:
        print("=" * 70)
        print("### %s 失败，完整输出：" % name)
        print(txt)

print("=" * 70)
print("%-12s %8s %6s %6s  %s" % ("测试", "退出码", "OK", "NG", "摘要"))
for name, rc, ok, ng, s in rows:
    print("%-12s %8d %6d %6d  %s" % (name, rc, ok, ng, s))
print("=" * 70)

# 真档指纹校验：测试跑完不许动玩家存档一个字节
save_after = _real_save_fingerprint()
if save_before and save_after and save_before != save_after:
    bad += 1
    print("!!! 玩家真实存档被测试改动了，必须排查 !!!")
    print("    之前：%r" % (save_before,))
    print("    之后：%r" % (save_after,))
elif save_before:
    print("真实存档未被改动（sha1 %s…）" % save_before[3][:12])

print("失败项 = %d，%s" % (bad, "全部通过" if not bad else "请看上面的详情"))
sys.exit(1 if bad else 0)
