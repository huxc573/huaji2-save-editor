# -*- coding: utf-8 -*-
"""探针 2：找「门派」到底存在哪。"""
import os, sys, collections
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "src"))
import paths, datatables

g = paths.find_game_dir()
print("game =", g)

# ---- System.@skill_types
_r, items = datatables.load("System")
sysnode = items[0][1] if items else None
if sysnode is not None:
    st = datatables.ivar(sysnode, "@skill_types")
    print("\nSystem.@skill_types =", [datatables.s(x) for x in st.items] if st else None)
    ew = datatables.ivar(sysnode, "@elements")
    print("System.@elements =", [datatables.s(x) for x in ew.items] if ew else None)
    ivs = [n for n, _ in sysnode.ivars]
    print("System ivars(含'派'/'门'/'职'/'class'):",
          [n for n in ivs if any(c in n for c in ("派", "门", "职", "class"))])

# ---- Skills: 按 @stype_id 分组
_r, skills = datatables.load("Skills")
grp = collections.defaultdict(list)
for i, node in skills:
    st = datatables.val(node, "@stype_id")
    grp[st].append((i, datatables.s(node, "@name")))
print("\nSkills 按 @stype_id 分组：")
for k in sorted(grp, key=lambda x: (x is None, x)):
    lst = grp[k]
    names = "、".join(n for _, n in lst[:6])
    print("  stype_id=%s  n=%d  e.g. %s" % (k, len(lst), names))

# ---- Classes: 看有没有「门派」字段；看 @name 全集
_r, classes = datatables.load("Classes")
names = [(i, datatables.s(node, "@name")) for i, node in classes if datatables.s(node, "@name")]
print("\nClasses 里有名字的 %d 条：" % len(names))
print("  ", "、".join(n for _, n in names[:60]))

# ---- 找出含「门派」字样的表
for key in ("Skills", "Actors", "Classes", "States", "Weapons", "Armors", "Items", "Enemies", "Troops"):
    try:
        _r, its = datatables.load(key)
    except Exception as e:
        print("load %s fail: %s" % (key, e)); continue
    hits = []
    for i, node in its:
        if not hasattr(node, "ivars"):
            continue
        for n, v in node.ivars:
            try:
                s = datatables.s(v)
            except Exception:
                s = None
            if s and ("门派" in s or "门 派" in s):
                hits.append((i, n, s[:40]))
    if hits:
        print("\n[%s] 含「门派」的字段 %d 处，前 10：" % (key, len(hits)))
        for h in hits[:10]:
            print("   ", h)
