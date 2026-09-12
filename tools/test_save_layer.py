# -*- coding: utf-8 -*-
"""语义层测试：在**副本**上改金钱 / 开关 / 变量 / 角色，验证防作弊校验仍然自洽。

用法：python tools/test_save_layer.py
输出：tools/_save_layer.txt
"""
import os
import shutil
import sys

sys.stdout.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))

import xj_env  # noqa: E402
import xj_save  # noqa: E402

LOG = os.path.join(HERE, "_save_layer.txt")
WORK = os.path.join(HERE, "_smoke")
L = []
OK = [0, 0]


def check(name, cond, extra=""):
    L.append("%-48s %s %s" % (name, "[OK]" if cond else "[NG]", extra))
    OK[0 if cond else 1] += 1


os.makedirs(WORK, exist_ok=True)
copy = os.path.join(WORK, "layer.rvdata2")
shutil.copyfile(xj_env.save_path(), copy)

s = xj_save.SaveDoc(copy)
gold0 = s.gold()
check("读到金钱", isinstance(gold0, int), "金钱=%r" % gold0)
check("原有 Lock 校验一致（说明公式复刻对了）", s.check_locks() == [],
      "不一致项=%r" % s.check_locks())
seed = s.shield_seed()
L.append("shield seed = %r  预期 master(1164) = %r  实际 = %r"
         % (seed, s.lock_master(gold0), s.lock_master(gold0)))

# 改金钱 → @master 必须同步
s.set_gold(999999)
check("改金钱后 @master 同步", s.check_locks() == [],
      "新金钱=%r" % s.gold())

# 修 Lock 之后再检查（此时应无需修改）
check("repair_locks 无事可做", s.repair_locks() == 0)

# 故意破坏 @master，再看能不能被检查出来、并被修复
lock, vnode = s.gold_node()
master = xj_save._deref(xj_save.ivar(lock, "@master"))
s.doc.set_value(master, int(xj_save.M.value_of(master)) + 1)
bad = s.check_locks()
check("破坏 @master 能被检测到", len(bad) == 1, "%r" % bad)
check("repair_locks 能修好", s.repair_locks() == 1 and s.check_locks() == [])

# 开关 / 变量
nsw, nva = s.counts()
if nsw:
    v = s.get_switch(0)
    s.set_switch(0, not v)
    check("开关 0 改写生效", s.get_switch(0) == (not v), "%r -> %r" % (v, not v))
if nva:
    v = s.get_variable(0)
    s.set_variable(0, 4242)
    check("变量 0 改写生效", s.get_variable(0) == 4242, "%r -> 4242" % v)

# 角色
actors = s.actors()
check("至少有一个角色", len(actors) >= 1, "角色 id=%r" % [i for i, _ in actors])
if actors:
    aid, a = actors[0]
    lv = s.actor_field(a, "@level")
    s.set_actor_field(a, "@level", (lv or 0) + 1)
    check("角色等级 +1",
          s.actor_field(a, "@level") == (lv or 0) + 1,
          "%r -> %r" % (lv, s.actor_field(a, "@level")))
    L.append("  #%d %s" % (aid, s.actor_summary(a)))

# 写回 → 重新打开 → 全部改动还在、校验仍然一致
s.save(backup=False)
s2 = xj_save.SaveDoc(copy)
check("写回后金钱仍为 999999", s2.gold() == 999999, "%r" % s2.gold())
check("写回后 Lock 校验仍一致", s2.check_locks() == [])
if nva:
    check("写回后变量仍为 4242", s2.get_variable(0) == 4242)
check("写回后仍能完整解析", len(s2.doc.objects) == 2)

L.append("")
L.append("==== 通过 %d, 失败 %d ====" % (OK[0], OK[1]))
open(LOG, "w", encoding="utf-8").write("\n".join(L) + "\n")
print("\n".join(L))
sys.exit(1 if OK[1] else 0)
