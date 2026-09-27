# -*- coding: utf-8 -*-
"""一次性探针：dump 指定地图的事件指令（看 code=355 脚本长什么样）。"""
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
os.makedirs(WORK, exist_ok=True)

TARGET = sys.argv[1] if len(sys.argv) > 1 else "Map113.rvdata2"

src = os.path.join(DATA, TARGET)
out = os.path.join(WORK, TARGET + ".bin")
codec.decrypt_file(src, out)
objs = M.parse_stream(open(out, "rb").read())
root = objs[-1]["node"]

STAT = {}


def text_of(n):
    n = datatables.deref(n)
    if n is None:
        return None
    if n.__class__.__name__ == "StrNode":
        try:
            return n.str()
        except Exception:
            return None
    return None


def walk(n, depth=0):
    n = datatables.deref(n)
    if n is None or depth > 18:
        return
    cls = n.__class__.__name__
    if cls == "ArrayNode":
        for it in n.items:
            walk(it, depth + 1)
        return
    iv = getattr(n, "ivars", None)
    if iv:
        pairs = iv.items() if hasattr(iv, "items") else iv
        code = None
        for k, v in pairs:
            if str(getattr(k, "name", k)) == "@code":
                code = datatables.val(v)
        if code is not None:
            STAT[code] = STAT.get(code, 0) + 1
            if code in (355, 655, 111, 117):
                t = ""
                for k, v in pairs:
                    if str(getattr(k, "name", k)) == "@parameters":
                        v2 = datatables.deref(v)
                        if v2 is not None and v2.__class__.__name__ == "ArrayNode":
                            for p in v2.items:
                                tt = text_of(p)
                                if tt:
                                    t += tt + "\n"
                if t.strip():
                    print("[code %d] %s" % (code, t.strip()[:200]))
        for _k, v in pairs:
            walk(v, depth + 1)


walk(root)
print("\n各 code 出现次数（前 20）：")
for c, n in sorted(STAT.items(), key=lambda x: -x[1])[:20]:
    print("   code %-5d %d 次" % (c, n))
shutil.rmtree(WORK, ignore_errors=True)
