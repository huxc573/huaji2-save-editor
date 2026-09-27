# -*- coding: utf-8 -*-
"""探针：看 Data\\Classes / Skills 的结构，判断「门派」到底对应什么。"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "src"))
import paths, datatables

g = paths.find_game_dir()
print("game =", g)
print("=" * 70)

# ---- Classes
_r, classes = datatables.load("Classes")
print("Classes 共 %d 条" % len(classes))
for i, node in classes[:8]:
    ivars = [n for n, _ in node.ivars] if hasattr(node, "ivars") else []
    print("\n[id=%s] ivars=%s" % (i, ivars))
    print("   name=%r" % (datatables.s(node, "@name"),))
    for k in ("@name", "@note", "@learnings"):
        print("   %s = %r" % (k, datatables.ivars(node, [k]) if False else datatables.ivar(node, k)))
        break
    print("   learnings =", datatables.fmt_learnings(datatables.ivar(node, "@learnings")))
    print("   note = %r" % (datatables.s(node, "@note"),))

print("\n" + "=" * 70)
# ---- Skills 前几条
_r, skills = datatables.load("Skills")
print("Skills 共 %d 条" % len(skills))
for i, node in skills[:6]:
    iv = [n for n, _ in node.ivars] if hasattr(node, "ivars") else []
    print("\n[skill id=%s] ivars=%s" % (i, iv))
    for k in ("@name", "@description", "@stype", "@element", "@note", "@mp_cost", "@skill_type"):
        v = datatables.ivar(node, k)
        if v is not None:
            print("   %s = %r" % (k, datatables.s(node, k) if k in ("@name", "@description", "@note") else datatables.val(node, k)))
