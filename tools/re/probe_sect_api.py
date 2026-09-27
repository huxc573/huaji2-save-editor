# -*- coding: utf-8 -*-
"""验证新语义层：actor_sect_id / actor_sect_name / sect_skills /
actor_class_learnings / off_sect_skills （只读副本）。"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "src"))
import save, game
from tables import sect

copy = os.path.join(HERE, "probe_save.rvdata2")
sv = save.SaveDoc(copy)
g = game.GameEditor(sv)

print("%-8s %-4s %-6s %-6s %-12s %s" % ("角色", "sect", "门派", "本门派", "职业自带", "非本门派技能"))
print("-" * 84)
for aid, a in sv.actors():
    off = g.off_sect_skills(a)
    print("%-8s %-4s %-6s %-6s %-12s %s" % (
        sv.actor_name(a), g.actor_sect_id(a), g.actor_sect_name(a),
        len(g.sect_skills(a)), g.actor_class_learnings(a),
        "、".join("#%d %s" % (i, n or "?") for i, n in off) or "（无）"))

# 门派筛选逻辑（等价于 SkillPicker.sect_filter）
print("\n== 门派筛选：各门派能列出的技能 ==")
names = g.valid_skill_ids()
for sid in sect.SECT_ORDER:
    nm = sect.sect_name(sid)
    ids = sect.sect_skill_ids(sid)
    print("  %-6s %2d 个  %s" % (nm, len(ids),
          "、".join(names.get(i, "?") for i in ids[:4]) + ("…" if len(ids) > 4 else "")))
