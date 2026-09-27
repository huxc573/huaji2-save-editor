# -*- coding: utf-8 -*-
"""探针 3：只读副本，看每个角色的 @sect_id / @skills，并验证是否都属于其门派。"""
import os, sys, shutil, re
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "src"))
import paths, save, game, datatables

G = paths.find_game_dir()
real = os.path.join(G, "save.rvdata2")
copy = os.path.join(HERE, "probe_save.rvdata2")
shutil.copy2(real, copy)                      # 只动副本
print("real =", real, "size", os.path.getsize(real))
print("copy =", copy)

sv = save.SaveDoc(copy)
g = game.GameEditor(sv)
print("doc.path =", getattr(sv.doc, "path", None))

# ---- 从脚本里的 $sects 抽门派表（直接用解析结果，避免手抄）
sects = {
    0: ("无门派", []),
    1: ("五庄观", [181,182,183,184,185,186,187,188,189,190]),
    2: ("化生寺", [192,193,194,195,196,197,198,199,200,201]),
    3: ("大唐官府", [203,204,205,206,207,208,209,210,211,212]),
    4: ("天宫", [214,215,216,217,218,219,220,221,222,223]),
    5: ("女儿村", [225,226,227,228,229,230,231,232,233,234]),
    6: ("方寸山", [236,237,238,239,240,241,242,243,244,245]),
    7: ("普陀山", [247,248,249,250,251,252,253,254,255,256]),
    8: ("狮驼岭", [258,259,260,261,262,263,264,265,266,267]),
    9: ("盘丝洞", [269,270,271,272,273,274,275,276,277,278]),
    10: ("地府", [280,281,282,283,284,285,286,287,288,289]),
    11: ("魔王寨", [291,292,293,294,295,296,297,298,299,300]),
    12: ("龙宫", [302,303,304,305,306,307,308,309,310,311]),
}
names = g.valid_skill_ids()

print("\n%-10s %-8s %-4s %s" % ("角色", "门派", "sect", "@skills"))
print("-" * 78)
for aid, a in sv.actors():
    an = sv.actor_name(a)
    ivs = dict(a.ivars)
    sect_node = ivs.get("@sect_id")
    sect = save.M.value_of(save._deref(sect_node)) if sect_node is not None else None
    sd = ivs.get("@sect_data")
    skills = g.actor_skills(a)
    slabel = ("%s" % sects[sect][0]) if sect in sects else ("?%r" % sect)
    print("%-10s %-8s %-4s %s" % (an, slabel, sect, skills))
    if sd is not None:
        # @sect_data 里 :门派 的进度
        try:
            h = datatables.deref(sd)
            print("           @sect_data keys =", [k for k, _ in h.ivars][:8] if hasattr(h, "ivars") else type(h).__name__)
        except Exception as e:
            print("           sect_data?", e)
    if sect in sects and sects[sect][1]:
        allowed = set(sects[sect][1])
        extra = [s for s in skills if s not in allowed]
        if extra:
            print("           ⚠ 不属于本门派的技能 id:", extra,
                  "→", [(s, names.get(s)) for s in extra])
