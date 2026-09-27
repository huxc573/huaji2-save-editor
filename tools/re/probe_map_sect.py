# -*- coding: utf-8 -*-
"""一次性探针：在所有地图 / 战斗事件里找门派相关脚本指令。

⚠ Data 下的表都是**加密**的（`codec.decrypt_file` 解到临时目录再解析）。
⚠ 游戏路径含 `[尝鲜版]` → 不能用 glob（会把 [] 当字符类），只能 os.listdir。
"""
import io
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import codec
import datatables
import paths
import marshal_ruby as M

GD = paths.find_game_dir()
DATA = os.path.join(GD, "Data")
WORK = os.path.join(HERE, "_plain_scan")
if os.path.isdir(WORK):
    shutil.rmtree(WORK, ignore_errors=True)
os.makedirs(WORK, exist_ok=True)


def node_texts(n, out, depth=0):
    n = datatables.deref(n)
    if n is None or depth > 16:
        return
    cls = n.__class__.__name__
    if cls == "StrNode":
        try:
            out.append(n.str())
        except Exception:
            pass
        return
    if cls == "ArrayNode":
        for it in n.items:
            node_texts(it, out, depth + 1)
        return
    if cls == "HashNode":
        for _k, v in n.pairs:
            node_texts(v, out, depth + 1)
        return
    iv = getattr(n, "ivars", None)
    if iv:
        pairs = iv.items() if hasattr(iv, "items") else iv
        for _k, v in pairs:
            node_texts(v, out, depth + 1)


KEYS = ("attr", "reset_point", "潜能", "拜")
names = [n for n in os.listdir(DATA)
         if n.startswith("Map") and n.endswith(".rvdata2")]
names.sort()
names.append("Troops.rvdata2")
print("要扫 %d 个文件" % len(names))

total = 0
for base in names:
    src = os.path.join(DATA, base)
    out = os.path.join(WORK, base + ".bin")
    try:
        codec.decrypt_file(src, out)
        objs = M.parse_stream(open(out, "rb").read())
        texts = []
        node_texts(objs[-1]["node"], texts)
    except Exception as e:
        print("  !! %s 失败：%s" % (base, e))
        continue
    for t in texts:
        if not t:
            continue
        for k in KEYS:
            if k in t:
                for ln in t.split("\n"):
                    if k in ln:
                        print("[%s] %s" % (base, ln.strip()[:150]))
                        total += 1
                break
print("\n总命中 =", total)
shutil.rmtree(WORK, ignore_errors=True)
