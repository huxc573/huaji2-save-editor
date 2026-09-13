# -*- coding: utf-8 -*-
"""召唤兽功能回归测试：新增 / 删除 / 出战 / 技能 / 改名（全程在**副本**上跑）。

用法：python tools/test_baby.py
"""
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.stdout.reconfigure(errors="replace")

import xj_baby        # noqa: E402
import xj_env         # noqa: E402
import xj_game        # noqa: E402
import xj_marshal as M  # noqa: E402
import xj_save        # noqa: E402

OK = [0, 0]
WORK = os.path.join(HERE, "_baby")


def check(name, cond, extra=""):
    OK[0 if cond else 1] += 1
    print("  %s %-48s %s" % ("[OK]" if cond else "[NG]", name, extra))


def main():
    real = xj_env.save_path()
    if not os.path.exists(real):
        print("找不到存档 %s，跳过" % real)
        return 0
    shutil.rmtree(WORK, ignore_errors=True)
    os.makedirs(WORK, exist_ok=True)
    path = os.path.join(WORK, "copy.rvdata2")
    shutil.copyfile(real, path)

    sv = xj_save.SaveDoc(path)
    g = xj_game.GameEditor(sv)
    B = xj_baby.Babies(g)

    actor = sv.actors()[0][1]
    aid = sv.actors()[0][0]
    print("用角色 #%d %s 做实验（存档副本）" % (aid, sv.actor_name(actor)))

    # ---------------- 数据表
    cands = B.candidates()
    check("能列出可加的召唤兽", len(cands) > 100, "%d 种" % len(cands))
    kids = [c for c in cands if 181 <= c["id"] <= 187]
    check("小孩 181-187 在列表里", len(kids) == 7,
          "、".join("%s(%d)" % (c["name"], c["id"]) for c in kids))
    check("小孩属于神兽资质3 池",
          all(c["pool"] == "神兽资质3" for c in kids),
          kids[0]["pool"] if kids else "-")
    check("小孩是神兽（资质取定值）", B.is_god(181) and B.is_god(186))
    check("大海龟是普通（资质带随机）", not B.is_god(21))
    c181 = B.config(181)
    check("神兽资质3 配置正确",
          c181["atk"] == 2400 and c181["hp"] == 7500 and c181["grow"] == 1.8
          and c181["life"] == "infinite",
          "atk=%s hp=%s grow=%s life=%s" % (c181["atk"], c181["hp"],
                                            c181["grow"], c181["life"]))

    n0 = len(B.g.babies(actor))
    active0 = B.active_index(actor)

    # ---------------- 加一只小孩（小精灵）
    b = B.add(actor, 181)
    check("加完以后数量 +1", len(g.babies(actor)) == n0 + 1,
          "%d -> %d" % (n0, len(g.babies(actor))))
    check("名字 = 小精灵", B.display_name(b) == "小精灵", B.display_name(b))
    check("等级 = 模板初始等级(1)", g.baby_value(b, "level") == 1,
          g.baby_value(b, "level"))
    a = B.g.baby_attr(b)
    check("type = :神兽", M.value_of(_deref_attr(a, "@type")) == "神兽")
    check("六项资质 = 神兽资质3 定值",
          [g.baby_value(b, k) for k in ("atk", "def", "hpq", "mpq", "agi", "eva")]
          == [2400, 2400, 7500, 4800, 2100, 2100],
          [g.baby_value(b, k) for k in ("atk", "def", "hpq", "mpq", "agi", "eva")])
    check("成长 = 1.8", abs(g.baby_value(b, "grow") - 1.8) < 1e-6,
          g.baby_value(b, "grow"))
    life = M.value_of(_deref_attr(a, "@life"))
    check("寿命 = :infinite（永生）", life == "infinite", repr(life))
    check("忠诚 = 100", g.baby_value(b, "loyalty") == 100, g.baby_value(b, "loyalty"))
    check("五维 = 20+召唤兽自身等级（1 级 = 21）",
          all(g.baby_value(b, k) == 20 + g.baby_value(b, "level")
              for k in ("体质", "法力", "力量", "耐力", "敏捷")),
          g.baby_value(b, "体质"))
    check("潜能 = 召唤兽等级 * 5（1 级 = 5）",
          g.baby_value(b, "潜能") == 5 * g.baby_value(b, "level"),
          g.baby_value(b, "潜能"))
    check("气血/魔法 > 0（算过满血）",
          g.baby_value(b, "hp") > 0 and g.baby_value(b, "mp") > 0,
          "%s / %s" % (g.baby_value(b, "hp"), g.baby_value(b, "mp")))
    check("神兽自带该职业全部技能",
          B.skills(b) == B.class_skill_ids(181)[:xj_baby.MAX_SKILLS] and B.skills(b),
          "%d 个" % len(B.skills(b)))
    check("出战那只没被抢走", B.active_index(actor) == active0,
          "%d / %d" % (active0, B.active_index(actor)))
    check("@master 指回主人",
          xj_save._deref(xj_save.ivar(b, "@master")) is actor, "ok")

    # ---------------- 变异 / 普通召唤兽
    b2 = B.add(actor, 21, mutation=True)
    check("普通召唤兽也能加", B.display_name(b2) == "大海龟", B.display_name(b2))
    a2 = g.baby_attr(b2)
    check("变异标记写进去了", M.value_of(_deref_attr(b2, "@mutation")) is True)
    check("普通资质 <= 上限（变异区间 0.66）",
          0 < g.baby_value(b2, "atk") <= 960, g.baby_value(b2, "atk"))
    check("普通寿命是数字",
          isinstance(M.value_of(_deref_attr(a2, "@life")), int),
          M.value_of(_deref_attr(a2, "@life")))

    # ---------------- 新加的能存下去、重开还在
    sv.doc.save()
    sv2 = xj_save.SaveDoc(path)
    g2 = xj_game.GameEditor(sv2)
    B2 = xj_baby.Babies(g2)
    a2nd = sv2.actors()[0][1]
    rows = B2.g.babies(a2nd)
    names = [B2.display_name(x) for _i, x in rows]
    check("保存重开后新召唤兽还在",
          "小精灵" in names and "大海龟" in names, "、".join(names))
    check("重开后资质没变",
          [g2.baby_value(x, "atk") for _i, x in rows if B2.display_name(x) == "小精灵"]
          == [2400])

    # ---------------- 技能增删
    B2.clear_skills(rows[-1][1])
    check("清空技能", B2.skills(rows[-1][1]) == [])
    B2.learn(rows[-1][1], 45)
    B2.learn(rows[-1][1], 88)
    check("学会技能", B2.skills(rows[-1][1]) == [45, 88], B2.skills(rows[-1][1]))
    B2.forget(rows[-1][1], 45)
    check("忘掉技能", B2.skills(rows[-1][1]) == [88], B2.skills(rows[-1][1]))

    # ---------------- 名字
    check("名字表校验（小精灵在表里）", B2.name_ok("小精灵"))
    check("名字表校验（乱起的名字不在）", not B2.name_ok("我的爱宠123"))
    B2.set_display_name(rows[-1][1], "小丫丫")
    check("改显示名", B2.display_name(rows[-1][1]) == "小丫丫")
    B2.restore_name(rows[-1][1])
    check("恢复模板本名", B2.display_name(rows[-1][1])
          == B2.template_name(rows[-1][1]) == "大海龟", B2.display_name(rows[-1][1]))

    # ---------------- 出战 / 删除
    B2.set_active(a2nd, 0)
    check("设为出战", B2.active_index(a2nd) == 0, B2.active_index(a2nd))
    n1 = len(B2.g.babies(a2nd))
    B2.set_active(a2nd, n1 - 1)
    check("切换出战成功", B2.active_index(a2nd) == n1 - 1, B2.active_index(a2nd))
    B2.remove(a2nd, n1 - 1)
    check("删除（放生）成功", len(B2.g.babies(a2nd)) == n1 - 1,
          "%d -> %d" % (n1, len(B2.g.babies(a2nd))))
    check("删掉出战那只后会换成别的出战", B2.active_index(a2nd) == 0,
          B2.active_index(a2nd))
    sv2.doc.save()
    sv3 = xj_save.SaveDoc(path)
    B3 = xj_baby.Babies(xj_game.GameEditor(sv3))
    a3 = sv3.actors()[0][1]
    names3 = [B3.display_name(x) for _i, x in B3.g.babies(a3)]
    check("删完保存重开也没问题", "大海龟" not in names3 and "小精灵" in names3,
          "、".join(names3))

    shutil.rmtree(WORK, ignore_errors=True)
    print("\n==== 通过 %d, 失败 %d ====" % (OK[0], OK[1]))
    return 1 if OK[1] else 0


def _deref_attr(baby, name):
    return xj_save._deref(xj_save.ivar(baby, name))


if __name__ == "__main__":
    sys.exit(main())
