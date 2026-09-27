# -*- coding: utf-8 -*-
"""复核：手工塞一个 `i\\x00`（老版本写出来的整数 0）之后，体检到底怎么判。"""
import os
import shutil
import sys

sys.stdout.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)        # 探针产物固定在 tools\ 下，跟脚本在不在 re\ 无关
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "src"))

import paths      # noqa: E402
import game     # noqa: E402
import marshal_ruby as M  # noqa: E402
import save     # noqa: E402

WORK = os.path.join(TOOLS, "_smoke", "dbgi0")
if os.path.isdir(WORK):
    shutil.rmtree(WORK, ignore_errors=True)
os.makedirs(WORK)
p = os.path.join(WORK, "save.rvdata2")
shutil.copyfile(paths.save_path(), p)


def cheat(sv):
    return save._deref(save.ivar(sv.section("system"), "@cheated"))


def report(sv):
    return [r for r in game.GameEditor(sv).anti_cheat_report()
            if "作弊标记" in r[0]]


d = save.SaveDoc(p)
n = cheat(d)
print("原始：type=%s value=%r" % (type(n).__name__, M.value_of(n)))
print("原始报告：", report(d))

d.doc.engine.replace_range(n.start, n.end, b"i\x00")
d.save(backup=False)

d2 = save.SaveDoc(p)
n2 = cheat(d2)
v2 = M.value_of(n2)
print("塞 i00 后：type=%s value=%r  repr=%r  is False=%s"
      % (type(n2).__name__, v2, v2, v2 is False))
print("is_ruby_false ->", game.is_ruby_false(v2))
print("报告：", report(d2))
raw = d2.doc.engine.buf[n2.start:n2.end]
print("原始字节：", raw)
print("字节按 long 解码 =", M.w_long_decode(raw[1:]) if hasattr(M, "w_long_decode")
      else "(没有 w_long_decode)")
print("修一次：", game.fix_save_file(p)[1])
d3 = save.SaveDoc(p)
print("修完：type=%s value=%r" % (type(cheat(d3)).__name__, M.value_of(cheat(d3))))
shutil.rmtree(WORK, ignore_errors=True)
