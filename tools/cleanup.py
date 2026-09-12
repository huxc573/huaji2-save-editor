# -*- coding: utf-8 -*-
"""清理：删掉逆向过程中产生的临时垃圾（不动游戏文件、不动源码）。

用法：python tools/cleanup.py [--dry]
"""
import os
import shutil
import sys

sys.stdout.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GAME = os.path.dirname(os.path.dirname(ROOT))
DRY = "--dry" in sys.argv

# 1) 明确要删的文件
FILES = [
    os.path.join(ROOT, "src", "xj_state.txt"),      # 旧的"密钥状态"实验，已废弃
    os.path.join(GAME, "0"), os.path.join(GAME, "1"),   # main.dll 的 init_key 落的垃圾
    os.path.join(GAME, "qqeat"), os.path.join(GAME, "xjy.11"),
    os.path.join(ROOT, "0"), os.path.join(ROOT, "1"),
    os.path.join(ROOT, "qqeat"), os.path.join(ROOT, "xjy.11"),
]
# 2) 要删的目录（体积大、随时可再生成）
DIRS = [
    os.path.join(ROOT, "tools", "_smoke"),
    os.path.join(ROOT, "tools", "_brute_tmp"),
]

n = 0
for p in FILES:
    if os.path.exists(p):
        print("%s %s" % ("[dry]" if DRY else "[del]", p))
        if not DRY:
            try:
                os.remove(p)
            except OSError as e:
                print("   失败:", e)
                continue
        n += 1
for p in DIRS:
    if os.path.isdir(p):
        print("%s %s" % ("[dry]" if DRY else "[del]", p))
        if not DRY:
            shutil.rmtree(p, ignore_errors=True)
        n += 1

# 3) 清掉 __pycache__
for base, dirs, files in os.walk(ROOT):
    for d in list(dirs):
        if d == "__pycache__":
            p = os.path.join(base, d)
            print("%s %s" % ("[dry]" if DRY else "[del]", p))
            if not DRY:
                shutil.rmtree(p, ignore_errors=True)
            n += 1
            dirs.remove(d)

print("共处理 %d 项" % n)
