# -*- coding: utf-8 -*-
"""探针 2b：直接解密 System.rvdata2 找 @skill_types（门派？）。"""
import os, sys, collections
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "src"))
import paths, datatables, codec
import marshal_ruby as M

g = paths.find_game_dir()
print("game =", g)

# ---- 直接解密 System
src = os.path.join(g, "Data", "System.rvdata2")
out = os.path.join(HERE, "System.plain")
codec.decrypt_file(src, out)
objs = M.parse_stream(open(out, "rb").read())
root = objs[-1]["node"]
print("System root =", type(root).__name__)
st = datatables.ivar(root, "@skill_types")
print("\n@skill_types =", [datatables.s(x) for x in st.items] if st else None)
for k in ("@elements", "@weapon_types", "@armor_types", "@class_battle"):
    v = datatables.ivar(root, k)
    if v is not None and hasattr(v, "items"):
        print("%s = %s" % (k, [datatables.s(x) for x in v.items]))
ivs = [n for n, _ in root.ivars]
print("\nSystem ivars 全部:", ivs)
print("含 '派'/'门'/'职' 的:", [n for n in ivs if any(c in n for c in ("派", "门", "职"))])

# ---- Skills 按 stype_id
_r, skills = datatables.load("Skills")
types = [datatables.s(x) for x in st.items] if st else []
grp = collections.defaultdict(list)
for i, node in skills:
    grp[datatables.val(node, "@stype_id")].append((i, datatables.s(node, "@name")))
print("\nSkills 按 @stype_id 分组（类型名来自 System.@skill_types）：")
for k in sorted(grp, key=lambda x: (x is None, x)):
    tn = types[k] if isinstance(k, int) and 0 <= k < len(types) else "?"
    lst = grp[k]
    print("  stype_id=%-3s [%s] n=%d  %s" % (k, tn, len(lst), "、".join(n for _, n in lst[:8])))

# ---- Classes 名字 + 各自学技能数
_r, classes = datatables.load("Classes")
named = [(i, datatables.s(node, "@name")) for i, node in classes if datatables.s(node, "@name")]
print("\nClasses 有名字 %d 条，前 80：" % len(named))
print("  ", "、".join("%s:%s" % (i, n) for i, n in named[:80]))
