# -*- coding: utf-8 -*-
"""召唤兽功能回归测试：新增 / 删除 / 出战 / 技能 / 改名（全程在**副本**上跑）。

用法：python tests/test_baby.py
"""
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.stdout.reconfigure(errors="replace")

import babies        # noqa: E402
import paths         # noqa: E402
import game        # noqa: E402
import marshal_ruby as M  # noqa: E402
import save        # noqa: E402

OK = [0, 0]
WORK = os.path.join(HERE, "_baby")


def check(name, cond, extra=""):
    OK[0 if cond else 1] += 1
    print("  %s %-48s %s" % ("[OK]" if cond else "[NG]", name, extra))


def main():
    real = paths.save_path()
    if not os.path.exists(real):
        print("找不到存档 %s，跳过" % real)
        return 0
    shutil.rmtree(WORK, ignore_errors=True)
    os.makedirs(WORK, exist_ok=True)
    path = os.path.join(WORK, "copy.rvdata2")
    shutil.copyfile(real, path)

    sv = save.SaveDoc(path)
    g = game.GameEditor(sv)
    B = babies.Babies(g)

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
    # ---------------- 「经验拉满」（2026-09-20；「满级(65)」预设已去掉）
    # 为什么不能只写 @exp：召唤兽靠经验确实会自己连升（Game_Baby#change_exp 7014
    # 的 `level_up while`），但卡「主人等级 + 5」，所以顶不到 65（详见 baby_exp_full）。
    lv0 = g.baby_value(b, "level")
    pot0 = g.baby_value(b, "潜能")
    lv, wrote = g.baby_exp_full(b)
    check("baby_exp_full → 等级 = %d" % game.MAX_LEVEL_BABY,
          lv == game.MAX_LEVEL_BABY and g.baby_value(b, "level") == lv,
          g.baby_value(b, "level"))
    check("baby_exp_full → @exp = 满级门槛",
          wrote == game.exp_for_level(game.MAX_LEVEL_BABY, "baby")
          and g.baby_value(b, "exp") == wrote,
          "%r / %r" % (wrote, g.baby_value(b, "exp")))
    check("等级涨了潜能跟着补（+5/级；_apply_level_delta 修好后才有）",
          g.baby_value(b, "潜能") == pot0 + (lv - lv0) * 5,
          "%r → %r" % (pot0, g.baby_value(b, "潜能")))
    check("baby_preset('expfull') 走的是同一条路",
          g.baby_preset(b, "expfull") != []
          and g.baby_value(b, "level") == game.MAX_LEVEL_BABY)
    check("气血/魔法 > 0（算过满血）",
          g.baby_value(b, "hp") > 0 and g.baby_value(b, "mp") > 0,
          "%s / %s" % (g.baby_value(b, "hp"), g.baby_value(b, "mp")))
    check("神兽自带该职业全部技能（不截断）",
          B.skills(b) == B.class_skill_ids(181) and B.skills(b),
          "%d 个" % len(B.skills(b)))

    # ---------------- 五行（`@attr.@five`，2026-09-27 新增）
    # 存档里是 **Marshal String**（不是符号、不是数字）：游戏 `Window_Demon#five_calc`
    # 拿它和另一只比「相生 / 相克」，比不到就是「无」。所以值只能是 金木水火土，
    # 写别的字游戏读不到（等于没吃五行）→ set_baby 必须挡住。
    check("baby_field_type('five') == 'str'",
          game.GameEditor.baby_field_type("five") == "str",
          game.GameEditor.baby_field_type("five"))
    check("BABY_FIELDS 里五行是 String 类型",
          ("five", "五行", "@attr.@five", "str") in game.GameEditor.BABY_FIELDS)
    check("召唤兽自带五行（在五元组里）", g.baby_value(b, "five") in babies.FIVE,
          repr(g.baby_value(b, "five")))
    check("读出来是字符串（Marshal String）",
          isinstance(g.baby_value(b, "five"), str),
          type(g.baby_value(b, "five")).__name__)
    g.set_baby(b, "five", "火")
    check("改五行生效", g.baby_value(b, "five") == "火",
          repr(g.baby_value(b, "five")))
    try:
        g.set_baby(b, "five", "风")
        check("非法五行被挡（ValueError）", False, "居然写进去了：%r"
              % (g.baby_value(b, "five"),))
    except ValueError:
        check("非法五行被挡（ValueError）", True, "ValueError")
    check("非法值没写进去", g.baby_value(b, "five") == "火",
          repr(g.baby_value(b, "five")))

    # ---------------- 重置潜力/属性（宠物版洗点，2026-09-20 新增）
    # 游戏里没有宠物洗点；工具侧语义 = **守恒洗点**（五维和 + 潜能 一分不变），
    # 推导见 game.baby_reset_attr。神兽应洗出精确的 20+等级（与 initialize 一致）。
    T0 = (sum(g.baby_value(b, k) for k in ("体质", "法力", "力量", "耐力", "敏捷"))
          + g.baby_value(b, "潜能"))
    lv_b = g.baby_value(b, "level")
    r = g.baby_reset_attr(b)
    five_r = [g.baby_value(b, k) for k in ("体质", "法力", "力量", "耐力", "敏捷")]
    check("宠物洗点：潜能 = 等级*5", g.baby_value(b, "潜能") == lv_b * 5,
          "%r vs %r" % (g.baby_value(b, "潜能"), lv_b * 5))
    check("宠物洗点：五维 = 20+等级（神兽精确还原）",
          five_r == [20 + lv_b] * 5, "%r（等级 %s）" % (five_r, lv_b))
    check("宠物洗点守恒：五维和 + 潜能 一点没变",
          sum(five_r) + g.baby_value(b, "潜能") == T0,
          "%r vs %r" % (sum(five_r) + g.baby_value(b, "潜能"), T0))
    # `@xx_temp` 在 **@attr** 上（不是 Game_Baby 上）→ 得先弄脏再洗，才测得出东西
    _a_b = g.baby_attr(b)
    for _k in ("体质", "法力", "力量", "耐力", "敏捷"):
        _n = save._deref(save.ivar(_a_b, "@%s_temp" % _k))
        if _n is not None:
            g.doc.set_value(_n, 7)
    g.baby_reset_attr(b)
    _temps = [M.value_of(_deref_attr(_a_b, "@%s_temp" % k))
              for k in ("体质", "法力", "力量", "耐力", "敏捷")]
    check("宠物洗点把 @xx_temp 归零", _temps == [0] * 5, "%r" % (_temps,))
    check("宠物洗点是幂等的（再洗一次不变）", g.baby_reset_attr(b) == r, "%r" % (r,))
    check("出战那只没被抢走", B.active_index(actor) == active0,
          "%d / %d" % (active0, B.active_index(actor)))
    check("@master 指回主人",
          save._deref(save.ivar(b, "@master")) is actor, "ok")

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
    # 普通召唤兽：出生那次 rand(11) 掷点没写进存档、不可还原 → 只保证守恒
    T2 = (sum(g.baby_value(b2, k) for k in ("体质", "法力", "力量", "耐力", "敏捷"))
          + g.baby_value(b2, "潜能"))
    lv2 = g.baby_value(b2, "level")
    g.baby_reset_attr(b2)
    two = [g.baby_value(b2, k) for k in ("体质", "法力", "力量", "耐力", "敏捷")]
    check("普通召唤兽洗点同样守恒 + 潜能=等级*5",
          sum(two) + g.baby_value(b2, "潜能") == T2
          and g.baby_value(b2, "潜能") == lv2 * 5,
          "五维=%r 潜能=%r T=%r" % (two, g.baby_value(b2, "潜能"), T2))

    # ---------------- 新加的能存下去、重开还在
    sv.doc.save()
    sv2 = save.SaveDoc(path)
    g2 = game.GameEditor(sv2)
    B2 = babies.Babies(g2)
    a2nd = sv2.actors()[0][1]
    rows = B2.g.babies(a2nd)
    names = [B2.display_name(x) for _i, x in rows]
    check("保存重开后新召唤兽还在",
          "小精灵" in names and "大海龟" in names, "、".join(names))
    check("重开后资质没变",
          [g2.baby_value(x, "atk") for _i, x in rows if B2.display_name(x) == "小精灵"]
          == [2400])
    check("重开后五行还在（String 节点原样写回）",
          [g2.baby_value(x, "five") for _i, x in rows
           if B2.display_name(x) == "小精灵"] == ["火"],
          repr([g2.baby_value(x, "five") for _i, x in rows]))

    # ---------------- 技能增删
    B2.clear_skills(rows[-1][1])
    check("清空技能", B2.skills(rows[-1][1]) == [])
    B2.learn(rows[-1][1], 45)
    B2.learn(rows[-1][1], 88)
    check("学会技能", B2.skills(rows[-1][1]) == [45, 88], B2.skills(rows[-1][1]))
    B2.forget(rows[-1][1], 45)
    check("忘掉技能", B2.skills(rows[-1][1]) == [88], B2.skills(rows[-1][1]))

    # ---------------- 解除 12 上限（2026-09-20：工具不再截断）
    # 卡 12 的只有游戏里「升级学技能」那条路径（Game_Baby#learn_skill）；
    # 读取端（Game_Baby#skills）压根没有数量限制，存档里 13 个以上是合法的。
    B2.clear_skills(rows[-1][1])
    many = sorted(B2.valid_skill_ids())[:babies.GAME_LEARN_LIMIT + 1]
    if len(many) > babies.GAME_LEARN_LIMIT:
        B2.set_skills(rows[-1][1], many)
        check("set_skills 不再截断（写 13 个就是 13 个）",
              B2.skills(rows[-1][1]) == many,
              "%d 个" % len(B2.skills(rows[-1][1])))
        B2.set_skills(rows[-1][1], many[:babies.GAME_LEARN_LIMIT])
        B2.learn(rows[-1][1], many[-1])
        check("learn 能加到第 13 个（不再丢弃）",
              B2.skills(rows[-1][1]) == many,
              "%d 个" % len(B2.skills(rows[-1][1])))
    else:
        check("set_skills 不再截断（写 13 个就是 13 个）", True, "技能表不够多，跳过")
    B2.clear_skills(rows[-1][1])

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
    sv3 = save.SaveDoc(path)
    B3 = babies.Babies(game.GameEditor(sv3))
    a3 = sv3.actors()[0][1]
    names3 = [B3.display_name(x) for _i, x in B3.g.babies(a3)]
    check("删完保存重开也没问题", "大海龟" not in names3 and "小精灵" in names3,
          "、".join(names3))

    # ---------------- 技能克隆
    rows3 = B3.g.babies(a3)
    if len(rows3) < 2:
        B3.add(a3, 21)                       # 不够两只，先补一只普通召唤兽
        rows3 = B3.g.babies(a3)
    dst = rows3[-1][1]
    src = rows3[0][1]
    src_ids = B3.skills(src)
    if not src_ids:
        B3.set_skills(src, [45, 88, 91])     # 普通召唤兽可能一个技能都没抽到
        src_ids = B3.skills(src)
    check("来源有技能可以克隆", len(src_ids) > 0, "%d 个：%s" % (len(src_ids), src_ids))

    B3.set_skills(dst, [88])
    # 合并克隆不设上限：dst 原有的 88 留下，来源里有、dst 里没有的全部补进来。
    want = 1 + len(set(s for s in src_ids if s != 88))
    res = B3.clone_skills(dst, src)
    check("合并克隆：保留目标原有的 88", B3.skills(dst)[:1] == [88], B3.skills(dst))
    check("合并克隆：来源技能全补进来（无上限）", len(B3.skills(dst)) == want,
          "%d（期望 %d）" % (len(B3.skills(dst)), want))
    check("合并克隆：added 计数对得上", res["added"] == want - 1, res["added"])
    # 界面（baby_skill_clone）按这几个键取结果；2026-09-20 去掉 dropped 时
    # 界面那条 `res["dropped"]` 差点漏改（幸好扫了一遍），契约冻结在这。
    check("clone_skills 的返回键固定", set(res) == {"ids", "added", "bad", "replace"},
          "%r" % (sorted(res),))

    res2 = B3.clone_skills(dst, src, replace=True)
    check("覆盖克隆：和来源一模一样（不截断）",
          B3.skills(dst) == src_ids, B3.skills(dst))
    check("覆盖克隆：返回 replace 标记", res2["replace"] is True)

    # 存档里夹带 Data\Skills 没有的 id → 不能照抄过去
    # ⚠ 这里仍然**直接改数组**而不是 set_skills：2026-09-20 起 set_skills 不再
    #   截断，但直接改数组才是「存档里真的夹带了一个无效 id」的现场，
    #   而且不依赖 set_skills 的过滤行为，用例意图更纯。
    bad_arr = _deref_attr(src, "@skills")
    if isinstance(bad_arr, M.ArrayNode):
        bad_arr.items = [babies.int_node(s) for s in (src_ids + [99999])]
        B3.doc.mark_structural()
        check("造出了「来源夹带无效 id」的存档（13 项）",
              len(B3.skills(src)) == len(src_ids) + 1,
              "%d" % len(B3.skills(src)))
    res3 = B3.clone_skills(dst, src, replace=True)
    check("无效技能 id 被挡下来",
          99999 not in B3.skills(dst) and res3["bad"] == [99999],
          "bad=%s" % res3["bad"])
    B3.set_skills(src, src_ids)

    # 2026-09-20 解除 12 上限：来源有 13 个技能 → 覆盖克隆应原样写 13 个过去，
    # 不再有「写满 12、剩下的报 dropped」这回事（clone_skills 已无 dropped 键）。
    # ⚠ 直接改数组造「异常旧档有 13 个」的现场。
    valid = sorted(B3.valid_skill_ids())[:babies.GAME_LEARN_LIMIT + 1]
    src_arr = _deref_attr(src, "@skills")
    if len(valid) > babies.GAME_LEARN_LIMIT and isinstance(src_arr, M.ArrayNode):
        src_arr.items = [babies.int_node(s) for s in valid]
        B3.doc.mark_structural()
        res4 = B3.clone_skills(dst, src, replace=True)
        check("解除 12 上限：13 个技能全部写过去",
              B3.skills(dst) == valid and "dropped" not in res4,
              "%d 个：%s" % (len(B3.skills(dst)), B3.skills(dst)))
        B3.set_skills(src, src_ids)
    else:
        check("解除 12 上限：13 个技能全部写过去", True, "技能表不够多，跳过")

    # 来源可以是别的角色身上的召唤兽
    allb = B3.all_babies()
    check("能列出整档所有召唤兽（跨角色）",
          len(allb) >= len(rows3) and all(r["baby"] is not None for r in allb),
          "%d 只 / %d 个角色" % (len(allb), len({r["actor_id"] for r in allb})))
    check("列表里带角色名和模板名", all(r["actor_name"] and r["tpl"] for r in allb),
          "%s / %s" % (allb[0]["actor_name"], allb[0]["tpl"]))
    try:
        B3.clone_skills(dst, dst)
        check("自己克隆给自己会报错", False, "居然没报错")
    except ValueError:
        check("自己克隆给自己会报错", True, "ValueError")

    B3.set_skills(dst, [45, 88])
    B3.doc.save()
    sv4 = save.SaveDoc(path)
    B4 = babies.Babies(game.GameEditor(sv4))
    a4 = sv4.actors()[0][1]
    got4 = [B4.skills(x) for _i, x in B4.g.babies(a4)]
    check("克隆完保存重开技能还在", [45, 88] in got4, got4)

    # ---------------- 五行：新增时指定 / 不指定 / 非法（`babies.add(five=...)`）
    # ⚠ 曾经的真 bug（2026-09-27 探针抳到）：build() 里五维 dict 也叫 `five`，
    #   把同名参数覆盖掉了 → `str_node(five)` 拿到 dict 报
    #   `'dict' object has no attribute 'encode'`。五维已改名 `wudi`，这里锁住。
    n5 = len(B4.g.babies(a4))
    x5 = B4.add(a4, 187, five="水")
    check("add(five='水') → 指定生效", B4.g.baby_value(x5, "five") == "水",
          repr(B4.g.baby_value(x5, "five")))
    _nd5 = B4.g.baby_attr(x5)
    _node5 = save._deref(save.ivar(_nd5, "@five"))
    check("落盘的是 Marshal String（StrNode）", isinstance(_node5, M.StrNode),
          type(_node5).__name__)
    xr = B4.add(a4, 187)
    check("add() 不指定 → 随机在五元组里",
          B4.g.baby_value(xr, "five") in babies.FIVE,
          repr(B4.g.baby_value(xr, "five")))
    try:
        B4.add(a4, 187, five="风")
        check("add(five='风') 被挡（ValueError）", False, "居然加上了")
    except ValueError:
        check("add(five='风') 被挡（ValueError）", True, "ValueError")
    check("被挡那次没真加进去", len(B4.g.babies(a4)) == n5 + 2,
          "%d -> %d" % (n5, len(B4.g.babies(a4))))
    # 五维没被五行带歪（build 里改名后仍算对）
    check("指定五行的新宠，五维/潜能照旧算",
          B4.g.baby_value(x5, "体质") == 20 + B4.g.baby_value(x5, "level")
          and B4.g.baby_value(x5, "潜能") == 5 * B4.g.baby_value(x5, "level"),
          "体质=%r 潜能=%r" % (B4.g.baby_value(x5, "体质"),
                              B4.g.baby_value(x5, "潜能")))

    # ---------------- 全员忠诚满（2026-09-27：一次改所有角色所有召唤兽）
    # 游戏规则（脚本 6501-6517 / 38271 / 38395）：
    #   上限 `Config::Game::MAX_BABY_LOYALTY = 100`（add/dec_loyalty 里 limit 到它）
    #   参战门槛 `Config::Baby::ALLOW_LOYALTY = 60`（`is_loyalty?`），**不是 100**
    #   作用只有「能不能参战」这一个；`$jiance` 反作弊只查等级/金钱/仓库页，不查忠诚
    check("忠诚常量：上限 100、门槛 60",
          game.MAX_BABY_LOYALTY == 100 and game.BABY_ALLOW_LOYALTY == 60,
          "%s / %s" % (game.MAX_BABY_LOYALTY, game.BABY_ALLOW_LOYALTY))
    check("字段标签里写的是门槛 60（曾经错写成 100）",
          "<60 不能参战" in dict((k, lb) for k, lb, _p, _t
                                 in game.GameEditor.BABY_FIELDS)["loyalty"],
          dict((k, lb) for k, lb, _p, _t
               in game.GameEditor.BABY_FIELDS)["loyalty"])

    def rows_now():
        out = []
        for _aid, _a in B4.g.sv.actors():
            for _i, _x in B4.g.babies(_a):
                out.append((_aid, _x))
        return out

    _r = rows_now()
    for _aid, _x in _r[:2]:                       # 压低两只（可能跨角色）
        B4.g.set_baby(_x, "loyalty", 11)
    _exp = [(_aid, _x) for _aid, _x in rows_now()
            if abs(float(B4.g.baby_value(_x, "loyalty")) - 100.0) > 1e-9]
    _exp_actors = len(set(_aid for _aid, _x in _exp))
    _snap = dict((id(_x), [B4.g.baby_value(_x, k)
                           for k in ("体质", "潜能", "level", "grow", "five")])
                 for _aid, _x in rows_now())
    _touched, _na = B4.g.set_loyalty_all()
    check("set_loyalty_all：只改「低于上限」的那些只", _touched == len(_exp),
          "%d vs %d" % (_touched, len(_exp)))
    check("set_loyalty_all：涉及角色数对得上", _na == _exp_actors,
          "%d vs %d" % (_na, _exp_actors))
    check("全档所有召唤兽忠诚都到上限",
          all(abs(float(B4.g.baby_value(_x, "loyalty")) - 100.0) < 1e-9
              for _aid, _x in rows_now()),
          "共 %d 只" % len(rows_now()))
    check("幂等：再来一次返回 (0, 0)", B4.g.set_loyalty_all() == (0, 0),
          "%r" % (B4.g.set_loyalty_all(),))
    check("只动忠诚（五维/潜能/等级/成长/五行 全没变）",
          all([B4.g.baby_value(_x, k)
               for k in ("体质", "潜能", "level", "grow", "five")]
              == _snap.get(id(_x)) for _aid, _x in rows_now()))

    shutil.rmtree(WORK, ignore_errors=True)
    print("\n==== 通过 %d, 失败 %d ====" % (OK[0], OK[1]))
    return 1 if OK[1] else 0


def _deref_attr(baby, name):
    return save._deref(save.ivar(baby, name))


if __name__ == "__main__":
    sys.exit(main())
