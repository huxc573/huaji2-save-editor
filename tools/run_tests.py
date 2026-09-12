# -*- coding: utf-8 -*-
"""一键跑全部回归测试，最后给个总表。

用法：
    python tools/run_tests.py            # 跑全部
    python tools/run_tests.py marshal    # 只跑名字里含 marshal 的

为什么不用一串 shell 命令：本工作区路径含 `!` `【】[]`，
PowerShell 里 `&&`、中文、`!` 都容易被吃掉，串起来经常跑不动。
"""
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PY = sys.executable

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
    ("db_csv", ["tools/test_db_csv.py"]),
    ("smoke", ["tools/smoke.py"]),
    ("save_layer", ["tools/test_save_layer.py"]),
    ("verify_all", ["tools/verify_all.py"]),
    ("dist", ["tools/test_dist.py"]),
]

want = [a.lower() for a in sys.argv[1:]]
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
print("失败项 = %d，%s" % (bad, "全部通过" if not bad else "请看上面的详情"))
sys.exit(1 if bad else 0)
