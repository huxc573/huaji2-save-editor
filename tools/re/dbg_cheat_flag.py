# -*- coding: utf-8 -*-
"""查一下 @cheated 清掉之后到底变成了什么值（为什么 `is False` 不成立）。"""
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))

import doctree
import save
import game

def info(tag, sv):
    n = save._deref(save.ivar(sv.section("system"), "@cheated"))
    v = save.M.value_of(n)
    print("[%s] type=%s repr=%r  is False=%s  bool=%s"
          % (tag, type(n).__name__, v, v is False, bool(v)))
    return v

root = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "..", "..", "..", ".."))
save = os.path.join(root, "save.rvdata2")
tmp = tempfile.mkdtemp(prefix="dbgcheat_")
copy = os.path.join(tmp, "save.rvdata2")
shutil.copyfile(save, copy)

print("源文件：%s" % save)
doc = save.SaveDoc(copy)
sv = doc
g = game.GameEditor(sv)
info("载入原值", sv)

# 1) 模拟游戏标记作弊
node = save._deref(save.ivar(sv.section("system"), "@cheated"))
doc.set_value(node, 134700)
info("设成 134700", sv)
print("  report:", [r for r in g.anti_cheat_report() if "作弊标记" in r[0]])

# 2) 走 clear_cheat_flag
print("clear_cheat_flag ->", g.clear_cheat_flag())
info("清标记后", sv)

# 3) 走 fix_anti_cheat（guard_autofix 用的就是它）
doc.set_value(node, 134700)
print("fix_anti_cheat ->", g.fix_anti_cheat())
info("fix_anti_cheat 后", sv)

# 4) 存盘再读回来看看
doc.doc.save(copy, backup=False)
doc2 = save.SaveDoc(copy)
info("存盘后重读", doc2)
shutil.rmtree(tmp, ignore_errors=True)
