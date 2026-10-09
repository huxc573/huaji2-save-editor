# -*- coding: utf-8 -*-
"""v0.4 游戏数据层回归测试：背包 / 经验 / 召唤兽 / 防作弊。

全程在**存档副本**上操作（原存档一个字节都不动）。

用法：python tests/test_game_layer.py
"""
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.stdout.reconfigure(errors="replace")

import backup  # noqa: E402
import datatables  # noqa: E402
import paths  # noqa: E402
import game  # noqa: E402
import itemattr  # noqa: E402
import marshal_ruby as M  # noqa: E402
import rides  # noqa: E402
import save  # noqa: E402

OK = [0, 0]
WORK = os.path.join(HERE, "_game")


def check(name, cond, extra=""):
    OK[0 if cond else 1] += 1
    print("  %s %-46s %s" % ("[OK]" if cond else "[NG]", name, extra))


def main():
    real = paths.save_path()
    if not os.path.exists(real):
        print("  [--] 找不到存档 %s" % real)
        return 0
    shutil.rmtree(WORK, ignore_errors=True)
    os.makedirs(WORK, exist_ok=True)
    copy = os.path.join(WORK, "game_copy.rvdata2")
    shutil.copyfile(real, copy)

    sv = save.SaveDoc(copy)
    g = game.GameEditor(sv)
    print("存档副本 = %s" % copy)

    # ---------------- 背包
    rows = g.bag("Items")
    check("背包能列出物品", len(rows) >= 1, "%d 件" % len(rows))
    check("背包分 4 页（每页 20 格）",
          all(0 <= p <= 3 and 0 <= i < 20 for _s, p, i, _a, _b, _c in rows),
          "槽号 %s" % [r[0] for r in rows[:6]])
    check("物品名字取得对", all("?" not in r[4] or r[3] < 0 for r in rows),
          "、".join("%s×%d" % (r[4], r[5]) for r in rows[:4]))
    empty = g.empty_slots("Items")
    check("空槽能算出来", len(empty) == 4 * 20 - len(rows),
          "%d 个空槽" % len(empty))

    slot0, _p, _i, iid0, name0, cnt0 = rows[0]
    # 数量校验同步：先看游戏记的数
    sec0 = g.security_total(iid0)
    check("物品计数校验读得出来", sec0 is not None,
          "id=%d 游戏记录 %s" % (iid0, sec0))
    if sec0 is not None:
        total0 = g.item_counts().get(iid0, 0)
        check("计数校验 == 实际持有数（AES 解密对得上）", sec0 == total0,
              "游戏记录 %d / 背包实际 %d" % (sec0, total0))

    # ⚠ 期望值要按**夹取后**的值比：真档第 1 格的数量会随存档漂移，
    #   一旦 `cnt0 + 7` 越过该物品的上限（多数是 `MAX_ITEM=99`），
    #   `set_count` 会夹到上限 —— 2026-10-08 真档那格涨到 97 时就假红过
    #   （97 + 7 = 104 被夹成 99）。
    want_cnt = min(cnt0 + 7, g.stack_limit(_item_of(g, "Items", slot0)))
    newcnt = cnt0 + 7
    g.set_count("Items", slot0, newcnt)
    check("改数量生效",
          dict((r[0], r[5]) for r in g.bag("Items"))[slot0] == want_cnt,
          "%d -> %d（上限 %d）" % (cnt0, newcnt, want_cnt))
    if sec0 is not None:
        check("改数量后计数校验跟着 +7", g.security_total(iid0) == sec0 + 7,
              "%s -> %s" % (sec0, g.security_total(iid0)))

    # 加物品到空槽
    add_slot = empty[-1]
    tpl_id = 1
    g.add_item("Items", add_slot, tpl_id, 3)
    got = [r for r in g.bag("Items") if r[0] == add_slot]
    check("加物品成功", len(got) == 1 and got[0][3] == tpl_id and got[0][5] == 3,
          "%r" % (got[0] if got else None,))
    check("加物品后文档标记为结构性改动", sv.doc.structural is True)
    check("加物品后自动补了计数校验条目",
          g.security_total(tpl_id) == g.item_counts().get(tpl_id, 0),
          "security[%d] = %s（实际 %s）" % (tpl_id, g.security_total(tpl_id),
                                             g.item_counts().get(tpl_id)))
    if got:
        check("新物品名字来自 Data 表", got[0][4] == g.item_name("Items", tpl_id),
              got[0][4])
        item_node = _item_of(g, "Items", add_slot)
        names = [k for k, _v in item_node.ivars]
        check("新物品补齐了游戏自加的 ivar",
              all(x in names for x in ("@result_note", "@attr", "@update",
                                       "@new", "@transaction_code")),
              "%d 个 ivar" % len(names))

    # 清空格子
    g.clear_slot("Items", add_slot)
    check("清空格子生效", not [r for r in g.bag("Items") if r[0] == add_slot])
    check("清空后计数校验回到 0", g.security_total(tpl_id) == 0,
          "security[%d] = %s" % (tpl_id, g.security_total(tpl_id)))

    # ---------------- 经验
    aid, actor = sv.actors()[0]
    e0 = g.exp(actor)
    g.add_exp(actor, 1000)
    check("加经验生效", g.exp(actor) == e0 + 1000, "%s -> %s" % (e0, g.exp(actor)))
    l0 = g.limit_exp(actor)
    g.set_limit_exp(actor, l0 + 1)
    check("升级所需经验可改", g.limit_exp(actor) == l0 + 1,
          "%s -> %s" % (l0, g.limit_exp(actor)))

    # ---------------- 召唤兽
    babys = g.babies(actor)
    check("列出召唤兽", len(babys) >= 1,
          "、".join(g.baby_name(b) for _i, b in babys))
    if babys:
        bi, baby = babys[0]
        vals = dict((k, g.baby_value(baby, k))
                    for k, _l, _p, _t in g.BABY_FIELDS)
        check("召唤兽字段读得出来",
              all(vals[k] is not None for k in
                  ("level", "hp", "mp", "loyalty", "life", "atk", "体质")),
              "等级=%s 忠诚=%s 攻击资质=%s 体质=%s"
              % (vals["level"], vals["loyalty"], vals["atk"], vals["体质"]))
        g.set_baby(baby, "level", 7)
        check("改召唤兽等级生效", g.baby_value(baby, "level") == 7)
        g.set_baby(baby, "loyalty", 100.0)
        check("改忠诚（小数）生效", g.baby_value(baby, "loyalty") == 100.0)
        # ⚠ 2026-10-08 改：资质**不再夹上限**。上限（`$baby[:_max]`）管的是游戏里
        #   能涨到多少，存档里超限值合法 —— 游戏面板画 `min(值, 上限)` 并标红
        #   （实测川的档：涂山雪存 2100、上限 2000、面板红字 2000）。夹住反而会把
        #   老档的超限值**拉低**。所以这儿期望就是纯加法。
        _cap = (g.baby_max_attr(baby) or {}).get("atk")
        _want = vals["atk"] + 100
        did = g.baby_preset(baby, "qual")
        check("资质 +100 预设生效（超上限照写）",
              g.baby_value(baby, "atk") == _want,
              "、".join(did) or "上限 %s" % _cap)
        check("超上限的项能被 baby_over_cap 标出来",
              (not g.baby_over_cap(baby)) if _want <= (_cap or 0)
              else ("atk" in g.baby_over_cap(baby)),
              "%r（上限 %s）" % (g.baby_over_cap(baby), _cap))
        check("召唤兽技能能列出来", isinstance(g.baby_skills(baby), list),
              "%r" % (g.baby_skills(baby)[:3],))

    # ---------------- 防作弊
    rep = g.anti_cheat_report()
    check("体检报告有内容", len(rep) >= 4, "%d 项" % len(rep))
    # 正常存档本来就不该有超限项（这个副本是干净档）；先造一个作弊标记，
    # 再看体检能不能标出来。
    sys_node = save._deref(save.ivar(sv.section("system"), "@cheated"))
    # ⚠ V2.201（内测版）没有 @cheated 节点 —— 原来这里直接 set_value(None, True)
    # 会抛 AttributeError，让**整组**测试在 143 行就早退（后面所有段都跑不到，
    # 包括 actor_exp_fill 那组）。加守卫跳过这一小段。
    if sys_node is None:
        print("  （内测版没有 @cheated 节点，跳过「造作弊标记 + 检出」这段）")
    else:
        sv.doc.set_value(sys_node, True)
        rep = g.anti_cheat_report()
        check("体检能标出超限项", any(r[3] for r in rep),
              "、".join(r[0] for r in rep if r[3])[:60] or "（没有超限项）")

    # 故意越界：金钱拉满到上限之上（走底层 sv.set_gold，模拟外部直接改值，
    # 只动 Lock 不动游戏记账 —— 这正是旧版工具留下的坑）
    sv.set_gold(game.MAX_GOLD + 1)
    rep2 = g.anti_cheat_report()
    check("金钱超限能被检出",
          any(r[0] == "金钱" and r[3] for r in rep2))
    check("金钱记账不一致能被检出",
          any(r[0].startswith("金钱记账") and r[3] for r in rep2))
    # 故意做一个计数器不一致
    if sec0 is not None:
        g._set_security_total(_change_of(g, iid0), sec0 + 5)   # 只动计数
        rep3 = g.anti_cheat_report()
        check("计数不一致能被检出",
              any("计数校验" in r[0] and r[3] for r in rep3))
    done = g.fix_anti_cheat()
    rep4 = g.anti_cheat_report()
    check("一键修复后没有超限项", not any(r[3] for r in rep4),
          "；".join(r[0] for r in rep4 if r[3])[:80] or "、".join(done)[:60])
    check("修复后金钱 = 上限 5/6 安全值（不贴上限）",
          sv.gold() == game.SAFE_GOLD, sv.gold())
    check("修复后金钱账与实际金钱一致", g.security_gold() == sv.gold(),
          "账=%s 钱=%s" % (g.security_gold(), sv.gold()))
    check("修复后 Lock 校验和一致", sv.check_locks() == [])
    check("作弊标记被清掉",
          M.value_of(save._deref(
              save.ivar(sv.section("system"), "@cheated"))) is False)
    kw_node = save._deref(save.ivar(sv.section("system"), "@keyword"))
    check("作弊记录 @keyword 整个清空",
          isinstance(kw_node, M.ArrayNode) and not kw_node.items,
          "%r" % ([x for x in kw_node.items]
                  if isinstance(kw_node, M.ArrayNode) else kw_node))

    # 统一入口 GameEditor.set_gold：超限自动钳到 2/3，Lock + 金钱账一次同步
    got, clamped = g.set_gold(999999999)
    check("set_gold 超上限自动钳到 2/3 安全值",
          got == game.SAFE_GOLD and clamped is True, str((got, clamped)))
    check("钳制后 Lock 与金钱账都同步",
          sv.check_locks() == [] and g.security_gold() == got)
    got2, clamped2 = g.set_gold(123456)
    check("set_gold 未超限原样写入",
          got2 == 123456 and clamped2 is False, str((got2, clamped2)))
    check("正常改钱金钱账也跟着同步", g.security_gold() == 123456)

    # Change 记账支持负数（真实档里金钱账本来就是负的）
    ch_gold = save._deref(game.hash_get(g.security_node(), "gold"))
    g._change_set(ch_gold, -987654321)
    check("Change 负数记账读写往返", g.change_value(ch_gold) == -987654321,
          str(g.change_value(ch_gold)))
    g.sync_gold_security()
    check("负数乱账能被 sync_gold_security 对齐",
          g.security_gold() == sv.gold())

    # 五类账一次性对齐
    summary = g.resync_all_security()
    check("resync_all_security 返回 (账名, 条数) 列表",
          isinstance(summary, list)
          and all(cn in ("金钱", "物品计数", "变量", "人气", "贡献")
                  and isinstance(n, int) for cn, n in summary),
          repr(summary))
    check("全量对齐后体检无记账类异常",
          not any(r[3] for r in g.anti_cheat_report()))

    # ---------------- v0.5：机器码
    now, err, ids, ok = g.machine_status()
    check("能读到本机机器码", bool(now) and not err, "%s（%s）" % (now, err))
    check("存档里有机器码记录", len(ids) >= 1, "、".join(ids) or "（空）")
    check("本机机器码在存档记录里", ok, "本机 %s / 存档 %s" % (now, ids))
    added = g.add_machine_id("999999999")
    check("能追加机器码", "999999999" in added and now in added,
          "、".join(added))
    added2 = g.add_machine_id("999999999")
    check("重复追加不会变多", len(added2) == len(added), "、".join(added2))
    rows_m = [r for r in g.anti_cheat_report() if "机器码" in r[0]]
    check("体检里有机器码一项", len(rows_m) == 1,
          rows_m[0][0][:40] if rows_m else "")
    only = g.set_machine_ids(["888888888"])
    check("能整组替换机器码", only == ["888888888"] 
          or only == ["888888888"][:len(only)], "%r" % (only,))
    # ⚠ 回归钉子（2026-10-04 川）：机器码换成别人的码之后，**自动修复不许把
    #   本机码塞回来** —— 原来 `fix_anti_cheat` 里有一段「本机码不在档就追加」，
    #   于是「替换 → 保存 → 重载」本机真实机器码又冒出来了。
    g.fix_anti_cheat(clamp=False, clear_flag=False)
    check("自动修复不会把本机码塞回存档", g.machine_ids() == ["888888888"],
          "%r" % (g.machine_ids(),))
    rows_m2 = [r for r in g.anti_cheat_report() if "机器码" in r[0]]
    check("机器码不在档也不算问题项", bool(rows_m2) and not rows_m2[0][3],
          repr(rows_m2[0][:4]) if rows_m2 else "没这项")
    g.set_machine_ids(ids)                     # 恢复成原来的
    check("机器码能恢复原样", g.machine_ids() == ids, "%r" % g.machine_ids())

    # ---------------- v0.5：模板表 / 换物品 / 批量 / 体检
    tpl = g.templates("Items", limit=10)
    check("能列出物品模板", len(tpl) >= 5, "%r" % (tpl[:2],))
    check("模板搜索能用", all("草" in t[1] or "草" in t[2]
                            for t in g.templates("Items", keyword="草")),
          "、".join(t[1] for t in g.templates("Items", keyword="草", limit=4)))
    tpl_id = tpl[1][0] if tpl[1][0] not in [r[3] for r in g.bag("Items")] \
        else [t[0] for t in tpl if t[0] not in [r[3] for r in g.bag("Items")]][0]
    free1 = g.empty_slots("Items")[0]
    g.set_item("Items", free1, tpl_id, 3)
    check("set_item 能往空格放东西", g.slot_info("Items", free1) == (tpl_id, 3),
          "%r" % (g.slot_info("Items", free1),))
    other = [t[0] for t in tpl if t[0] != tpl_id][0]
    g.set_item("Items", free1, other, 2)
    check("set_item 能把格子换掉", g.slot_info("Items", free1) == (other, 2),
          "%r" % (g.slot_info("Items", free1),))
    check("换物品后计数校验同步了",
          g.security_total(other) == g.item_counts().get(other, 0),
          "记录 %s / 实际 %s"
          % (g.security_total(other), g.item_counts().get(other, 0)))
    n = g.set_all_counts("Items", 7, 0)
    check("批量改本页数量能跑",
          all(c == 7 for _s, p, _i, _id, _nm, c in g.bag("Items", 0)),
          "改了 %d 格" % n)
    bad = g.pack_report()
    check("背包体检能跑", isinstance(bad, list), "%d 项" % len(bad))
    if bad:
        done_bad = g.pack_fix(bad)
        after = g.pack_report()
        check("一键修复后没有异常格子", not after,
              "修了 %d 项，还剩 %d 项" % (len(done_bad), len(after)))
        check("修完计数校验仍对齐",
              not [r for r in g.security_rows() if r[2] != r[3]],
              "%r" % [r for r in g.security_rows() if r[2] != r[3]][:2])

    # ---------------- v0.4.2：运行时内容（孵化蛋那种）+ 装备名字
    need, nm110 = g.item_needs_payload("Items", 110)
    check("认得出“孵化蛋”是运行时内容物品", need and "孵化蛋" in nm110, nm110)
    need2, nm2 = g.item_needs_payload("Items", 3)
    check("普通药草不算运行时内容", not need2, nm2)
    probe = g.empty_slots("Items")[0]
    g.add_item("Items", probe, 110, 1)
    it = _item_of(g, "Items", probe)
    t, d = g.item_payload(it)
    kid = M.value_of(save._deref(save.hash_get(d, "id"))) if d is not None \
        else None
    check("新加的孵化蛋自己生成了 @attr 内容",
          t == "孵化蛋" and isinstance(kid, int),
          "type=%r id=%r" % (t, kid))
    # ⚠ 必须是**游戏写的中文符号**：游戏按 `case item.data[:type]` 分发，
    #   早期工具写的 `:baby_egg` 游戏一律不认（浮窗不显示、用的时候还可能报错）。
    _pool0 = itemattr.egg_pool(110)
    check("写的 type 是游戏符号（:孵化蛋，不是 :baby_egg）", t == "孵化蛋", t)
    check("初级孵化蛋的兽池 = 真值三档第 0 档（allow_lv 0..55）",
          bool(_pool0) and all(
              itemattr._BA.SPECIES[i]["allow_lv"] <= 55 for i in _pool0),
          "%d 只，例 %s" % (len(_pool0), _pool0[:6]))
    check("生成的召唤兽 id 落在该档兽池里", kid in _pool0,
          "id=%r 池=%d 只" % (kid, len(_pool0)))
    g.clear_slot("Items", probe)
    g.add_item("Items", probe, 110, 1, kid=57)
    it = _item_of(g, "Items", probe)
    _t, d = g.item_payload(it)
    check("能指定“孵出哪只”（kid）",
          d is not None and M.value_of(save._deref(
              save.hash_get(d, "id"))) == 57,
          "%r" % (d,))
    # 存档里已有同款时，应该整份克隆（运行时内容一模一样）
    ref_slot = [s for s in g.empty_slots("Items") if s != probe][0]
    g.clear_slot("Items", probe)
    g.add_item("Items", ref_slot, 110, 1, kid=57, clone_like=False)
    g.add_item("Items", probe, 110, 1)          # 默认 clone_like=True
    _t2, d2 = g.item_payload(_item_of(g, "Items", probe))
    got = M.value_of(save._deref(save.hash_get(d2, "id"))) \
        if d2 is not None else None
    check("存档里有同款时直接克隆它的内容", got == 57,
          "克隆到 id=%r（参照蛋是 57）" % (got,))
    g.clear_slot("Items", probe)
    g.clear_slot("Items", ref_slot)
    # 背包里混装武器/防具 → 名字要按对象自己的类去查
    mix = []
    for kind, _iv, cn, _db in game.KINDS:
        for r in g.bag(kind):
            it2 = _item_of(g, kind, r[0])
            cls = getattr(it2, "cls", "")
            if cls in ("RPG::Weapon", "RPG::Armor"):
                mix.append((kind, r, cls))
    if mix:
        kind, r, cls = mix[0]
        check("混在背包里的%s也有名字" % ("武器" if "Weapon" in cls else "防具"),
              r[4] and r[4] != "?", "槽 %d %s → %r" % (r[0], cls, r[4]))
    else:
        check("背包里没有武器/防具可测（跳过）", True)

    # “以前版本加进来的坏蛋”：@attr 被清空 → 体检要能查出、一键修复要能补
    probe2 = [s for s in g.empty_slots("Items")
              if s not in (probe, ref_slot)][0]
    g.add_item("Items", probe2, 110, 1, kid=57, clone_like=False)
    game.set_ivar(_item_of(g, "Items", probe2), "@attr",
                     M.HashNode([], default=None))
    _t0, d0 = g.item_payload(_item_of(g, "Items", probe2))
    check("把内容清空后确实变成“空的”", _t0 is None, "%r" % (_t0,))
    rows_bad = g.pack_report()
    check("@attr 空的蛋能被体检查出",
          any(e.get("payload") for *_x, e in rows_bad),
          "%d 项问题" % len(rows_bad))
    g.pack_fix(rows_bad)
    _t3, d3 = g.item_payload(_item_of(g, "Items", probe2))
    check("一键修复能把运行时内容补回来",
          _t3 == "孵化蛋" and d3 is not None, "type=%r" % (_t3,))
    g.clear_slot("Items", probe2)

    # ---------------- v0.4.3：重抽 / 指定内容 + 内容摘要
    probe3 = [s for s in g.empty_slots("Items")
              if s not in (probe, probe2, ref_slot)][0]
    g.add_item("Items", probe3, 110, 1, kid=57, clone_like=False)
    it3 = _item_of(g, "Items", probe3)
    check("内容摘要能写出来（蛋→召唤兽）",
          "蛋→" in g.payload_summary(it3), g.payload_summary(it3))
    g.set_payload("Items", probe3, kid=21)
    _t4, d4 = g.item_payload(_item_of(g, "Items", probe3))
    check("重抽/指定内容生效（kid=21）",
          M.value_of(save._deref(save.hash_get(d4, "id"))) == 21,
          "%r" % (d4,))
    g.set_payload("Items", probe3)          # 不给 kid = 按游戏范围随机
    _t5, d5 = g.item_payload(_item_of(g, "Items", probe3))
    check("不给 kid 时随机重抽", _t5 == "孵化蛋" and d5 is not None, "%r" % (d5,))
    try:
        g.set_payload("Items", 999, kid=1)
        check("对空格子重抽会报错", False)
    except Exception as e:
        check("对空格子重抽会报错", "空" in str(e), "%s" % type(e).__name__)
    g.clear_slot("Items", probe3)

    # ---------------- 2026-10-08：补齐 `special?` 里剩下能静态复刻的家族
    #  `Game_Party#special?` 有 40 来个 id 要求 `item.data` 有内容，工具原
    #  先只覆盖一半。没覆盖的那些「加进背包」时不写 `@attr` —— 数据为 nil
    #  游戏会自己填，但角标/浮窗那几处是**直接读** `item.data[:data]` 的，
    #  所以能照脚本抄的就抄一份（不能抄的不写，见 107）。
    print("\n== 2026-10-08 补齐家族：内丹 / 点化石 / 如意丹 / 精气 …")
    _new18 = ((131, "如意丹"), (224, "点化石"), (123, "乾坤袋"),
              (133, "低级内丹"), (134, "高级内丹"), (140, "天材地宝"),
              (141, "圣者精气"), (142, "战神精气"), (143, "仙人精气"),
              (144, "本源精气"), (150, "灵饰指南书"), (151, "元灵晶石"),
              (157, "蟠桃"), (159, "符文"), (160, "上古技能残卷"),
              (276, "银票"), (277, "提神泪"), (280, "摇钱树树苗"))
    _names = datatables.name_map("Items")
    _miss = [i for i, _t in _new18 if not g.item_needs_payload("Items", i)[0]]
    check("18 个家族都认得出是运行时内容物品", not _miss, "漏 %r" % (_miss,))
    # ⚠ 名字撞车：225「十个点化石」、158「符文碎片」都不需要内容；107
    #   「点化石」的内容来自运行期 TemplateManager，静态抄不出来 ⇒ 三个都 False。
    _notneed = [i for i in (107, 158, 225)
                if g.item_needs_payload("Items", i)[0]]
    check("名字撞车的 107/158/225 不被误认", not _notneed, "%r" % (_notneed,))
    _slots18, _bad18 = [], []
    for _iid, _want in _new18:
        _s = [s for s in g.empty_slots("Items") if s not in _slots18][0]
        _slots18.append(_s)
        g.add_item("Items", _s, _iid, 1, clone_like=False)
        _tt, _dd = g.item_payload(_item_of(g, "Items", _s))
        if _tt != _want or _dd is None:
            _bad18.append((_iid, _tt))
    check("18 个家族写出来的 type 与脚本一致", not _bad18, "%r" % (_bad18,))
    _spec_bad = [i for i, t in _new18
                 if itemattr.payload_spec(_names.get(i, ""), i)[0] != t]
    check("18 个家族在重抽管理里都报得出家族名", not _spec_bad,
          "%r" % (_spec_bad,))
    _sum_bad = [g.payload_summary(_item_of(g, "Items", _s))
                for _s in _slots18
                if not g.payload_summary(_item_of(g, "Items", _s))
                or "None" in g.payload_summary(_item_of(g, "Items", _s))
                or g.payload_summary(_item_of(g, "Items", _s)) == "?"]
    check("18 个家族的摘要都能读出来", not _sum_bad, "%r" % (_sum_bad,))
    # 乾坤袋的 `data` 是**空 Hash**（跟 max 平级）—— 别当成"内容本体"，
    # 不然摘要与界面读不到 max（2026-10-08 自己踩到）。
    _qz = _slots18[_new18.index((123, "乾坤袋"))]
    _tq, _dq = g.item_payload(_item_of(g, "Items", _qz))
    check("乾坤袋的 max 平级读得到（空 data 不吞内容）",
          M.value_of(save._deref(save.hash_get(_dq, "max"))) == 20,
          g.payload_summary(_item_of(g, "Items", _qz)))
    # 战神精气的 skill 是**整数键** Hash（写成符号键游戏读不出来）
    _zsp = _slots18[_new18.index((142, "战神精气"))]
    _tz, _dz = g.item_payload(_item_of(g, "Items", _zsp))
    _hv = save._deref(save.hash_get(_dz, "skill"))
    _k0 = save._deref(_hv.pairs[0][0]) if isinstance(_hv, M.HashNode) \
        and _hv.pairs else None
    check("战神精气的 skill 用整数键", isinstance(_k0, M.IntNode), "%r" % (_k0,))
    # 精气的 seed 是 30 位大整数（Fixnum 装不下 ⇒ 必须走大整数编码）
    _byp = _slots18[_new18.index((144, "本源精气"))]
    _tb, _db = g.item_payload(_item_of(g, "Items", _byp))
    _sd = M.value_of(save._deref(save.hash_get(_db, "seed")))
    check("精气的 seed 是大整数（>2^63）",
          isinstance(_sd, int) and _sd > 2 ** 63, "%r" % (_sd,))
    # 提神泪：界面回填的是**存值** ⇒ 生成器不能再除一次 2.2（会越改越小）
    check("提神泪按存值原样写入（不二次缩水）",
          itemattr.build("提神泪", 277, over={"value": 500})[1]["value"] == 500)
    for _s in _slots18:
        g.clear_slot("Items", _s)

    # ---------------- 2026-10-07：抽选带范围、默认最大范围（元宵）
    #  川：重抽要能指定具体数值，范围照游戏脚本，默认填上限（成长 0.02）。
    _t, _flds = itemattr.payload_spec("元宵", 104)
    _vf = [f for f in _flds if f["key"] == "value"]
    check("元宵能挑「涨哪项资质」+「数值」两项",
          _t == "元宵" and len(_flds) == 2 and bool(_vf),
          "%r" % (_flds,))
    check("「数值」范围跟着资质走（成长那档 0.01~0.02）",
          bool(_vf) and tuple(_vf[0].get("rng_by_type") or ())[-1] == (0.01, 0.02),
          "%r" % (_vf[0].get("rng_by_type") if _vf else None,))
    _d = itemattr.build("元宵", 104, over={"type": 6, "value": 0.02})[1]["data"]
    check("指定 0.02 → 只有成长项是 0.02，其余全 0",
          abs(_d["value"]["grow"] - 0.02) < 1e-9
          and all(_d["value"][k] == 0
                  for k in ("atk", "def", "hp", "mp", "agi", "eva")),
          "%r" % (_d["value"],))
    check("上限表由 YUANXIAO_RANGES 生成",
          _d["max"] == [8, 8, 40, 20, 8, 8, 0.02], "%r" % (_d["max"],))
    check("越界会被夹回（攻击资质 999 → 8）",
          itemattr.build("元宵", 104,
                         over={"type": 0, "value": 999})[1]["data"]["value"]["atk"]
          == 8)
    check("不给数值时仍按游戏区间随机",
          itemattr.build("元宵", 104, over={"type": 6})[1]["data"]["value"]["grow"]
          != 0.0)
    probe5 = [s for s in g.empty_slots("Items")
              if s not in (probe, probe2, probe3, ref_slot)][0]
    try:
        g.add_item("Items", probe5, 104, 1, clone_like=False)
        g.set_payload("Items", probe5, over={"type": 6, "value": 0.02}, force=True)
        _sum = g.payload_summary(_item_of(g, "Items", probe5))
        check("走存档这条路也一样（摘要是「成长 0.02/0.02」）",
              "成长 0.02/0.02" in _sum, _sum)
    except Exception as e:
        check("走存档这条路也一样（摘要是「成长 0.02/0.02」）", False,
              "%s: %s" % (type(e).__name__, e))
    g.clear_slot("Items", probe5)

    # ---------------- v0.4.4：@attr 的“外层键必须是字符串”，否则游戏读不到
    #  游戏脚本：$item_obj.data[:data][:id]；而 item.data 读的是 @attr["data"]
    #  （**字符串**键）—— 早期工具写成了符号键 :data，于是：
    #    * 工具自己的“内容”列读不出来（游戏写的是字符串键）
    #    * 游戏用蛋时 item.data 为 nil → NoMethodError: undefined method '[]'
    probe4 = [s for s in g.empty_slots("Items")
              if s not in (probe, probe2, probe3, ref_slot)][0]
    g.add_item("Items", probe4, 110, 1, kid=57, clone_like=False)
    it4 = _item_of(g, "Items", probe4)
    attr = save._deref(save.ivar(it4, "@attr"))
    key = save._deref(attr.pairs[0][0])
    check("写出去的 @attr 外层键是**字符串**（和游戏一致）",
          isinstance(key, M.StrNode), type(key).__name__)
    got = M.value_of(key)
    if isinstance(got, bytes):
        got = got.decode("utf-8", "replace")
    check("外层键就是 \"data\"", got == "data", repr(got))
    # 模拟游戏那句 $item_obj.data[:data][:id]
    #   item.data        → @attr["data"]      = {:type=>..., :data=>{:id=>...}}
    #   item.data[:data] → {:id=>...}
    inner = save.hash_get(save.hash_get(attr, "data"), "data")
    d1 = M.value_of(save._deref(save.hash_get(inner, "id"))) \
        if inner is not None else None
    check("按游戏的方式读得到 id=57（这句以前会 nil 报错）", d1 == 57,
          "读到 %r" % (d1,))
    g.clear_slot("Items", probe4)

    # ---------------- 老版本工具写成了**符号键**：体检要挑出来、修复要改成字符串键
    probe5 = [s for s in g.empty_slots("Items")
              if s not in (probe, probe2, probe3, probe4, ref_slot)][0]
    g.add_item("Items", probe5, 110, 1, kid=57, clone_like=False)
    it5 = _item_of(g, "Items", probe5)
    # 手动把键换回符号（模拟 v0.4.2/0.4.3 写出来的老数据）
    payload = save.hash_get(save._deref(save.ivar(it5, "@attr")), "data")
    game.set_ivar(it5, "@attr",
                     M.HashNode([(M.SymbolNode("data"), payload)],
                                default=None))
    check("符号键现在能被“读”出来（兼容）",
          g.item_payload(it5)[0] == "孵化蛋", g.payload_summary(it5))
    check("但体检知道游戏读不到（键类型不对）", not g.payload_key_ok(it5))
    rows5 = g.pack_report()
    check("体检会把“键类型不对”列出来",
          any(r[1] == probe5 and "键" in r[3] for r in rows5),
          "%r" % [(r[1], r[3]) for r in rows5 if r[1] == probe5])
    g.pack_fix(rows5)
    attr5 = save._deref(save.ivar(_item_of(g, "Items", probe5), "@attr"))
    check("修复后键变成字符串（游戏能读了）",
          g.payload_key_ok(_item_of(g, "Items", probe5)),
          type(save._deref(attr5.pairs[0][0])).__name__)
    _t6, d6 = g.item_payload(_item_of(g, "Items", probe5))
    check("修复时内容没丢（还是 id=57）",
          d6 is not None and M.value_of(save._deref(
              save.hash_get(d6, "id"))) == 57,
          "type=%r" % (_t6,))
    g.clear_slot("Items", probe5)

    # ---------------- 2026-10-04：全部生成器对齐 V2.201 的**中文符号**
    #  游戏是 `case item.data[:type]` 分发，工具以前写的是英文名（`:导航旗` →
    #  `:navigation_flag`）⇒ 游戏浮窗不显示、使用逻辑也进不去。实测真档里
    #  游戏写的是 `导航旗`、而工具写过的那件是 `navigation_flag`。
    want = {
        110: "孵化蛋", 113: "孵化蛋", 221: "孵化蛋",
        235: "礼盒", 94: "导航旗",
        66: "魔兽要诀", 67: "高级魔兽要诀",
        152: "特殊魔兽要诀", 161: "超级魔兽要诀",
        135: "激进元宵丹", 104: "元宵", 90: "人参果",
        91: "真知棒", 92: "超级真知棒", 93: "鬼谷子",
        68: "制造指南书", 69: "百炼精铁", 70: "上古锻造图策",
        71: "天眼珠", 73: "宝石",
        148: "坐骑蛋蛋",
    }
    free = list(g.empty_slots("Items"))
    bad_sym = []
    for iid in sorted(want):
        if not free:
            break
        slot = free.pop(0)
        nm = g.item_needs_payload("Items", iid)[1]
        g.add_item("Items", slot, iid, 1, clone_like=False)
        got, _d = g.item_payload(_item_of(g, "Items", slot))
        if got != want[iid]:
            bad_sym.append("#%d %s → %r（应 %r）" % (iid, nm, got, want[iid]))
        g.clear_slot("Items", slot)
    check("每件运行时物品写的 type 都是游戏的中文符号",
          not bad_sym, "；".join(bad_sym) or "%d 件全对" % len(want))
    check("旧英文 type（:baby_egg）仍读得出来（兼容老存档）",
          g._PAYLOAD_KINDS.get("baby_egg") == "egg")
    # 兽池：三档互不重叠，且神兽池照脚本取 135..170 ∩ type2
    tiers = [set(itemattr.egg_pool(110 + k)) for k in range(3)]
    check("孵化蛋三档兽池互不重叠",
          not (tiers[0] & tiers[1]) and not (tiers[1] & tiers[2])
          and not (tiers[0] & tiers[2]),
          "三档 %d/%d/%d 只" % tuple(len(x) for x in tiers))
    _gods = set(itemattr.egg_pool(113))
    check("神兽孵化蛋兽池 = 135..170 ∩ (神兽资质 ∪ 神兽资质2)",
          _gods and all(135 <= i <= 170 for i in _gods)
          and _gods == set(itemattr.egg_pool(221)) | set(itemattr.egg_pool(222)),
          "%d 只（普通 %d + 生肖 %d）"
          % (len(_gods), len(itemattr.egg_pool(221)),
             len(itemattr.egg_pool(222))))
    # ---------------- 2026-10-08：坐骑蛋蛋(148) 必须带内容（川报「用了卡死」）
    #  公共事件 24「WITH_[孵化蛋]」拿到它就 `d = $item_obj.data[:data]` 再
    #  `add_ride(d)`；@attr 空 ⇒ nil[:data] 当场 NoMethodError（游戏日志实证）。
    check("认得出坐骑蛋蛋要运行时内容",
          g.item_needs_payload("Items", 148)[0])
    slots = list(g.empty_slots("Items"))
    rslot = slots.pop(0)
    g.add_item("Items", rslot, 148, 1, clone_like=False)
    rit = _item_of(g, "Items", rslot)
    rt, rd = g.item_payload(rit)
    rid = save.M.value_of(save._deref(save.hash_get(rd, "id")))
    rq = save.M.value_of(save._deref(save.hash_get(rd, "type")))
    rsp = save.M.value_of(save._deref(save.hash_get(rd, "speed")))
    rseed = save.M.value_of(save._deref(save.hash_get(rd, "seed")))
    check("新加的坐骑蛋蛋写好了 data[:data]（不再是一用就崩）",
          rt == "坐骑蛋蛋" and rid in itemattr.RIDE_IDS
          and rq in (0, 1, 2) and isinstance(rsp, float)
          and isinstance(rseed, int),
          "type=%r id=%r 品质=%r 移速=%r seed=%r"
          % (rt, rid, rq, rsp, rseed))
    _i = itemattr.RIDE_IDS.index(rid)
    _lo, _hi = itemattr.RIDE_SPEED_RANGE[_i]
    _cap = _hi * (itemattr.RIDE_QUALITY_MULT[rq - 1][1] if rq else 1.0)
    check("移速在该坐骑的区间内（品质再乘倍率）",
          _lo - 1e-9 <= rsp <= _cap + 1e-9,
          "%s %s 区间 %s~%s 倍率上限 %s ⇒ 实得 %s"
          % (rid, itemattr.RIDE_NAMES[_i], _lo, _hi, _cap, rsp))
    check("摘要按游戏浮窗口径解出坐骑名",
          "坐骑→" in g.payload_summary(rit)
          and itemattr.RIDE_NAMES[_i] in g.payload_summary(rit),
          g.payload_summary(rit))
    _spec_t, _spec_f = itemattr.payload_spec("坐骑蛋蛋", 148)
    check("重抽管理能挑坐骑 / 品质 / 移速",
          _spec_t == "坐骑蛋蛋"
          and [f["key"] for f in _spec_f] == ["id", "type", "speed"],
          "%r" % (_spec_f,))
    # 2026-10-08 川报：界面「封印坐骑」候选 0 项 —— 坐骑不是召唤兽，
    # kind 必须是 "ride"（界面走 itemattr.ride_rows()，不走召唤兽表）。
    check("「封印坐骑」字段走 ride 候选（8 只，名字＝Actors 表）",
          _spec_f[0]["kind"] == "ride"
          and len(itemattr.ride_rows()) == 8
          and [r[1] for r in itemattr.ride_rows()] == list(itemattr.RIDE_NAMES)
          and datatables.name_map("Actors").get(258) == "汗血宝马",
          "%r" % (itemattr.ride_rows()[:2],))
    # 2026-10-08 川：每项默认取最大 —— 坐骑取移速上限最高的、品质神骑、
    #   移速＝该组合的上限（跟着坐骑+品质现算）。
    check("默认最大值：坐骑 best＝移速上限最高那只（258）",
          _spec_f[0].get("best") == itemattr.ride_best_id() == 258,
          "%r" % (_spec_f[0].get("best"),))
    check("默认最大值：品质 best＝神骑(2)", _spec_f[1].get("best") == 2,
          "%r" % (_spec_f[1].get("best"),))
    check("移速区间跟着坐骑+品质现算（汗血宝马+神骑 → 0.105~0.19）",
          itemattr.ride_speed_rng(258, 2) == (0.105, 0.19)
          and itemattr.ride_speed_rng(258, 0) == (0.07, 0.095),
          "%r / %r" % (itemattr.ride_speed_rng(258, 2),
                       itemattr.ride_speed_rng(258, 0)))
    g.set_payload("Items", rslot, over={"id": 258, "type": 2, "speed": 0.19},
                  force=True)
    _r3, _d3 = g.item_payload(_item_of(g, "Items", rslot))
    check("移速可以直接指定（over['speed'] 照写）",
          abs(save.M.value_of(save._deref(save.hash_get(_d3, "speed")))
              - 0.19) < 1e-9,
          g.payload_summary(_item_of(g, "Items", rslot)))
    g.set_payload("Items", rslot, over={"id": 258, "type": 2}, force=True)
    rt2, rd2 = g.item_payload(_item_of(g, "Items", rslot))
    check("指定坐骑/品质后写的就是指定的",
          save.M.value_of(save._deref(save.hash_get(rd2, "id"))) == 258
          and save.M.value_of(save._deref(save.hash_get(rd2, "type"))) == 2,
          "%r" % (g.payload_summary(_item_of(g, "Items", rslot)),))
    g.clear_slot("Items", rslot)

    # ---------------- 保存 / 重开
    before = dict((r[0], r[5]) for r in g.bag("Items"))
    plain = sv.doc.plain_bytes()
    M.parse_stream(plain)
    check("结构性改动后仍能序列化并解析", True, "%d 字节" % len(plain))
    sv.doc.save()
    sv2 = save.SaveDoc(copy)
    g2 = game.GameEditor(sv2)
    check("重开后背包改动还在",
          dict((r[0], r[5]) for r in g2.bag("Items")) == before,
          "%r" % dict((r[0], r[5]) for r in g2.bag("Items")))
    aid2, actor2 = sv2.actors()[0]
    check("重开后经验还在", g2.exp(actor2) == e0 + 1000, g2.exp(actor2))
    check("重开后召唤兽改动还在",
          g2.baby_value(g2.babies(actor2)[0][1], "level") == 7,
          g2.baby_value(g2.babies(actor2)[0][1], "level"))
    baks = [f for f in os.listdir(backup.backup_dir(copy)) if ".bak." in f]
    check("原文件留了备份（在备份目录）", len(baks) >= 1, "%r" % baks[:2])
    check("存档目录不再散落 .bak.",
          not [f for f in os.listdir(WORK) if ".bak." in f])

    # ---------------- 升级所需经验 = 查表（不是 @limit_exp）
    print("\n-- 升级所需经验（游戏脚本 $exps 查表）--")
    sv3 = save.SaveDoc(copy)
    g3 = game.GameEditor(sv3)
    check("actor 表：40 级 = 332296（游戏界面上显示的数）",
          game.exp_for_level(40, "actor") == 332296,
          game.exp_for_level(40, "actor"))
    check("baby 表：40 级 = 84050",
          game.exp_for_level(40, "baby") == 84050,
          game.exp_for_level(40, "baby"))
    check("等级越界返回 None", game.exp_for_level(9999) is None)
    check("等级非法（None）返回 None", game.exp_for_level(None) is None)

    a3 = sv3.actors()[0][1]
    lv3 = g3.actor_level(a3)
    check("next_level_exp == 表里[当前等级]",
          g3.next_level_exp(a3) == game.exp_for_level(lv3, "actor"),
          "lv=%s → %s" % (lv3, g3.next_level_exp(a3)))
    g3.set_actor_level(a3, 20)
    check("改等级后升级所需经验跟着变",
          g3.next_level_exp(a3) == game.exp_for_level(20, "actor"),
          g3.next_level_exp(a3))

    # @limit_exp 是「累计获得经验」的封顶计数器，不是升级所需经验
    none_lim = [a for _, a in sv3.actors()
                if save._deref(save.ivar(a, "@limit_exp")) is None]
    if none_lim:
        check("没这个 ivar 的角色：limit_exp 读到 0（不再是空白）",
              g3.limit_exp(none_lim[0]) == 0, g3.limit_exp(none_lim[0]))
        check("没这个 ivar 的角色：set_limit_exp 返回 None 且不抛异常",
              g3.set_limit_exp(none_lim[0], 123) is None)
    else:
        check("（本存档所有角色都有 @limit_exp，跳过缺字段场景）", True)
    has_lim = [a for _, a in sv3.actors()
               if save._deref(save.ivar(a, "@limit_exp")) is not None]
    if has_lim:
        check("有这个 ivar 的角色：能正常写入",
              g3.set_limit_exp(has_lim[0], 7) == 7 and g3.limit_exp(has_lim[0]) == 7)

    # ---------------- 累计获得经验 = 经验封顶开关
    print("\n-- 累计获得经验（@limit_exp = 游戏的经验封顶开关）--")
    check("封顶线 = 202123741", g3.LIMIT_EXP_MAX == 202123741, g3.LIMIT_EXP_MAX)
    lim_actor = has_lim[0] if has_lim else None
    if lim_actor is not None:
        # 超线 = 游戏再也不发经验 → 必须拒收（以前工具让它写进去，等于把角色改废）
        check("拒绝写入超线值（返回 False，且没写进去）",
              g3.set_limit_exp(lim_actor, 999999999) is False
              and g3.limit_exp(lim_actor) != 999999999,
              "现值 %s" % g3.limit_exp(lim_actor))
        check("拒绝写入负数", g3.set_limit_exp(lim_actor, -1) is False)
        check("刚好等于封顶线是允许的",
              g3.set_limit_exp(lim_actor, g3.LIMIT_EXP_MAX) == g3.LIMIT_EXP_MAX)
        check("刚过线 → limit_exp_on() = False（游戏不再发经验）",
              g3.set_limit_exp(lim_actor, g3.LIMIT_EXP_MAX + 1) is False
              or g3.limit_exp_on(lim_actor) is False,
              "现值 %s" % g3.limit_exp(lim_actor))
        check("线内时 limit_exp_on() = True",
              g3.set_limit_exp(lim_actor, g3.LIMIT_EXP_MAX - 1) is not None
              and g3.limit_exp_on(lim_actor) is True)
        check("额度提示：线内还剩多少",
              g3.limit_exp_room(lim_actor) == 1, g3.limit_exp_room(lim_actor))
    else:
        check("（本存档没有带 @limit_exp 的角色，跳过封顶用例）", True)

    if none_lim:
        check("没这个 ivar 的角色不会被判封顶",
              g3.limit_exp_on(none_lim[0]) is True)

    # 清零：把顶着上限的角色全清掉
    if lim_actor is not None:
        g3.set_limit_exp(lim_actor, g3.LIMIT_EXP_MAX)
        done = g3.reset_limit_exp()
        check("「清零」把超线角色清成 0（游戏重新发经验）",
              g3.limit_exp(lim_actor) == 0 and g3.limit_exp_on(lim_actor) is True
              and any(n == sv3.actor_name(lim_actor) for n, _v in done),
              "%r" % (done,))

    # ---------------- 获得经验写对格子（@exp 是「职业id → 经验」的 Hash）
    print("\n-- 获得经验（@exp[@class_id]，不是 Hash 第一项）--")
    a4 = sv3.actors()[0][1]
    e_before = g3.exp(a4)
    g3.set_exp(a4, 12345)
    check("改获得经验写进了 @exp[@class_id]", g3.exp(a4) == 12345, g3.exp(a4))
    en = g3.exp_node(a4)
    check("写的是 class_id 对应的那个节点",
          en is not None and save.M.value_of(en) == 12345,
          "class_id=%s" % save.M.value_of(save._deref(
              save.ivar(a4, "@class_id"))))
    check("exp_key() 与 @class_id 一致",
          g3.exp_key(a4) == save.M.value_of(save._deref(
              save.ivar(a4, "@class_id"))))
    g3.set_exp(a4, e_before)

    # 造一个「转过职」的存档：Hash 里塞一条别的职业，游戏读 class_id 那条
    h = save._deref(save.ivar(a4, "@exp"))
    cid = g3.exp_key(a4)
    other = 999 if cid != 999 else 998
    h.pairs.insert(0, (M.IntNode(other), M.IntNode(777777)))
    check("转过职的存档：exp() 仍读 @class_id 那条（不被 Hash 第一项带偏）",
          g3.exp(a4) == e_before,
          "Hash=%r" % [(M.value_of(save._deref(k)),
                        M.value_of(save._deref(v))) for k, v in h.pairs])
    g3.set_exp(a4, 555)
    check("转过职的存档：set_exp 也写 @class_id 那条",
          g3.exp(a4) == 555
          and M.value_of(save._deref(h.pairs[0][1])) == 777777,
          "第一项仍是 777777")

    # ---------------- 改等级必须把 @exp 对齐（光改 @exp 游戏里永远看不到变化）
    print("\n-- set_actor_level_full：级别 + 获得经验一起对齐 --")
    check("游戏满级 = 60（MAX_LEVEL_ACTOR）", game.MAX_LEVEL_ACTOR == 60,
          game.MAX_LEVEL_ACTOR)
    check("满级门槛 exp_for_level(60) = 1091704",
          game.exp_for_level(60, "actor") == 1091704)
    a5 = sv3.actors()[0][1]
    lv5, wrote5 = g3.set_actor_level_full(a5, 40)
    check("设 40 级：等级写进 @level", g3.actor_level(a5) == 40, g3.actor_level(a5))
    check("设 40 级：@exp 同步成该级门槛 332296",
          wrote5 == 332296 and g3.exp(a5) == 332296, g3.exp(a5))
    check("同步后 next_level_exp 正好查到 41 级门槛",
          g3.next_level_exp(a5) == game.exp_for_level(40, "actor"))

    lv6, _w = g3.set_actor_level_full(a5, 60)
    check("设 60 级：等级夹到满级", lv6 == 60 and g3.actor_level(a5) == 60)
    check("设 60 级：@exp = 1091704（不是 0，也不是原值）",
          g3.exp(a5) == 1091704, g3.exp(a5))
    check("满级后 sync_exp_to_level 仍取得到门槛", 
          g3.sync_exp_to_level(a5, 60) == 1091704)

    lv7, _w = g3.set_actor_level_full(a5, 999)
    check("等级超上限被夹到 60", lv7 == 60 and g3.actor_level(a5) == 60)
    lv8, _w = g3.set_actor_level_full(a5, -5)
    check("等级为负被夹到 1", lv8 == 1 and g3.actor_level(a5) == 1)
    check("1 级的 @exp = 110（表的第 1 项）", g3.exp(a5) == 110, g3.exp(a5))

    _lv9, wrote9 = g3.set_actor_level_full(a5, 30, sync_exp=False)
    check("sync_exp=False 时不碰 @exp",
          wrote9 is None and g3.exp(a5) == 110, g3.exp(a5))

    # 显式写的 @exp 要能盖过等级同步（界面上先设等级再写 exp 的顺序依赖这个）
    g3.set_actor_level_full(a5, 20)
    g3.set_exp(a5, 777)
    check("等级同步后再显式 set_exp 能盖过它",
          g3.exp(a5) == 777 and g3.actor_level(a5) == 20)

    # ---------------- 改等级必须连带补潜能/五维（照抄 `Game_Actor_Attr#level_up`）
    # 2026-09-20：这里原来写 `ivar(attr_node, k[1:])`（把 `@` 去掉）→ 精确比对永远失配
    # → 这段逻辑**从来没生效过**（真档实测：点「满级」后仍是 潜能 0 / 五维 79）。
    print("\n-- _apply_level_delta：改等级补潜能/五维 --")
    FIVE = ("@体质", "@法力", "@力量", "@耐力", "@敏捷")
    g3.set_actor_level_full(a5, 60)
    g3.set_actor_level_full(a5, 20)          # 降级 = 洗点
    check("降级 → 洗点：潜能清零", g3._actor_attr_int(a5, "@潜能") == 0,
          g3._actor_attr_int(a5, "@潜能"))
    check("降级 → 洗点：五维清零",
          [g3._actor_attr_int(a5, k) for k in FIVE] == [0] * 5,
          [g3._actor_attr_int(a5, k) for k in FIVE])
    g3.set_actor_level_full(a5, 60)          # 20 → 60 = +40 级
    check("升 40 级补 200 点潜能（+5/级）",
          g3._actor_attr_int(a5, "@潜能") == 40 * 5,
          g3._actor_attr_int(a5, "@潜能"))
    check("升 40 级补 40 点五维（+1/级）",
          [g3._actor_attr_int(a5, k) for k in FIVE] == [40] * 5,
          [g3._actor_attr_int(a5, k) for k in FIVE])

    # ---------------- `actor_exp_full` = 界面「一键满级」（2026-09-20 新增）
    print("\n-- actor_exp_full：等级 + 获得经验一起拉满 --")
    g3.set_actor_level_full(a5, 10)
    lvf, wrotef = g3.actor_exp_full(a5)
    check("actor_exp_full → 等级 60 + @exp = 满级门槛",
          lvf == game.MAX_LEVEL_ACTOR and g3.actor_level(a5) == lvf
          and wrotef == game.exp_for_level(game.MAX_LEVEL_ACTOR, "actor")
          and g3.exp(a5) == wrotef,
          "%r / %r" % (lvf, wrotef))

    # ---------------- `actor_exp_fill` = 界面「经验拉满」（2026-10-03 新增）
    # 只写 @exp、**不动等级** —— 回游戏自己点「升级」（一次一级）。
    print("\n-- actor_exp_fill：只写经验、等级不动 --")
    # 2026-10-07 川：5000 万只够点到 79 级 ⇒ 50 亿 → **30 亿**。
    # ⚠ 30 亿落地会写成**大整数 'l'**（本作 32 位 Ruby 1.8，Fixnum 只到 2**30-1）
    #   —— 这是**正确**形态，游戏读 'l' 永远精确。上一轮误按 2**31-1 取 80%，
    #   17.18 亿被塞进 4 字节 'i'，加载端 `INT2FIX` 挤成 -429,496,731（川截图）。
    #   ⚠ 而且 17.18 亿本来就不够：89 级 → 155 级要 19.95 亿。
    check("ACTOR_EXP_FILL = 30 亿", game.ACTOR_EXP_FILL == 3000000000,
          game.ACTOR_EXP_FILL)
    check("ACTOR_EXP_FILL 够升满 89→155（需 19.95 亿）",
          game.ACTOR_EXP_FILL > 1995193706, game.ACTOR_EXP_FILL)
    check("Fixnum 边界 = 2**30-1；越界一律走大整数 'l'",
          M.FIXNUM_MAX == 2 ** 30 - 1 and M.FIXNUM_MIN == -(2 ** 30)
          and M.fits_fixnum(2 ** 30 - 1)
          and not M.fits_fixnum(2 ** 30)
          and not M.fits_fixnum(3000000000)
          and M.encode_integer(2 ** 30 - 1)[:1] == b'i'
          and M.encode_integer(2 ** 30)[:1] == b'l'
          and M.encode_integer(3000000000)[:1] == b'l',
          "MAX=%d" % M.FIXNUM_MAX)
    check("BABY_EXP_FILL 与角色页同源", game.BABY_EXP_FILL == game.ACTOR_EXP_FILL,
          game.BABY_EXP_FILL)

    # ---- 回归：'i' → 'l' 跨界必须升级为**整档重写** ----------------------
    # 踩过（2026-10-07）：盘上 @exp 是 4 字节 'i'，改成装不下 Fixnum 的值，
    # 判据若拿 `fits_fixnum(旧值)` 去比就会误判"没跨界"、走就地补丁 ——
    # 写出 'l' 却按 'i' 的编号排 ⇒ 全档 '@N' 集体错位一格（召唤兽名字被读成
    # 大整数）。哨兵 =「首宠 @attr.@name 仍能解析成字符串」。
    # ⚠ 序列化按**节点类型**定形态（BignumNode 永远写 'l'），所以只能拿盘上
    #   本来就是 'i' 的节点造跨界，不能靠"先写个小值"把类型转回来。
    _cross = os.path.join(WORK, "cross.rvdata2")
    shutil.copyfile(real, _cross)
    _sv = save.SaveDoc(_cross)
    _g = game.GameEditor(_sv)
    _hit = None
    for _ai, _ac in _sv.actors():
        _cands = [_g.exp_node(_ac)]
        _cands += [_g._exp_node(bb) for _bi, bb in _g.babies(_ac)]
        for _nd in _cands:
            if _nd is not None and _sv.doc.raw[_nd.start:_nd.end][:1] == b'i':
                _hit = _nd
                break
        if _hit is not None:
            break
    if _hit is None:
        print("  [--] 全档没有 'i' 的经验节点，跳过 i→l 跨界用例")
    else:
        _sv.doc.set_value(_hit, 3000000000)          # i → l
        check("'i'→'l' 跨界 → structural（整档重写，不是就地补丁）",
              _sv.doc.structural is True, "structural=%s" % _sv.doc.structural)
        _sv.save()
        _sv2 = save.SaveDoc(_cross)                  # ⚠ 存完必须重取节点
        _g2 = game.GameEditor(_sv2)
        _a2 = _sv2.actors()[0][1]
        _n2 = _g2.exp_node(_a2)
        check("@exp 落盘为大整数 'l'",
              _sv2.doc.raw[_n2.start:_n2.end][:1] == b'l',
              _sv2.doc.raw[_n2.start:_n2.end][:1])
        _bl = list(_g2.babies(_a2))
        if _bl:
            _nm = save._deref(save.ivar(_g2.baby_attr(_bl[0][1]), "@name"))
            check("全档 '@N' 没错位（首宠 @attr.@name 仍是字符串）",
                  isinstance(_nm, M.StrNode), type(_nm).__name__)

    g3.set_actor_level_full(a5, 25)
    lv_before = g3.actor_level(a5)
    wf = g3.actor_exp_fill(a5)
    check("actor_exp_fill → @exp = ACTOR_EXP_FILL",
          wf == game.ACTOR_EXP_FILL and g3.exp(a5) == game.ACTOR_EXP_FILL,
          "%r / %r" % (wf, g3.exp(a5)))
    check("actor_exp_fill 不动等级",
          g3.actor_level(a5) == lv_before == 25,
          "before=%r after=%r" % (lv_before, g3.actor_level(a5)))

    # ---------------- 角色技能 @skills（2026-09-20；角色没有 12 个上限）
    print("\n-- 角色技能：@skills 读写 --")
    sv5 = save.SaveDoc(copy)
    g5 = game.GameEditor(sv5)
    aid5, a6 = sv5.actors()[0]
    base = g5.actor_skills(a6)
    check("能读到角色已有技能",
          isinstance(base, list) and len(base) > 0, "%d 个" % len(base))
    check("与 SaveDoc.skills() 读到的一致", base == sv5.skills(a6))
    valid = g5.valid_skill_ids()
    check("Data\\Skills 能读到有效技能表", len(valid) > 0,
          "%d 个" % len(valid))
    fresh = [i for i in sorted(valid) if i not in base]
    check("有足够新技能 id 做用例", len(fresh) >= 20, len(fresh))
    for s in fresh[:20]:
        g5.actor_learn_skill(a6, s)
    after = g5.actor_skills(a6)
    check("角色技能没有数量上限（学 20 个全在，不像召唤兽卡 12）",
          len(after) == len(base) + 20, len(after))
    check("写入后保持升序（游戏 learn_skill 会 sort!）",
          after == sorted(after))
    check("重复学同一个不会重复加",
          g5.actor_learn_skill(a6, fresh[0]) == after)
    check("学已学过的技能数量不变",
          len(g5.actor_learn_skill(a6, base[0])) == len(after))
    n1 = len(g5.actor_forget_skill(a6, fresh[0]))
    check("忘掉一个技能", n1 == len(after) - 1, n1)
    check("忘掉不存在的 id 不报错、数量不变",
          len(g5.actor_forget_skill(a6, 999999)) == n1)
    expect = g5.actor_skills(a6)
    sv5.save()
    sv6 = save.SaveDoc(copy)
    g6 = game.GameEditor(sv6)
    a7 = dict(sv6.actors())[aid5]
    check("保存重开后技能还在", g6.actor_skills(a7) == expect,
          "%r" % (g6.actor_skills(a7)[:6],))
    check("其它角色技能没被连累",
          all(len(g6.actor_skills(x)) > 0 for _i, x in sv6.actors()[1:]),
          "%r" % ([len(g6.actor_skills(x)) for _i, x in sv6.actors()[1:]],))
    g6.actor_clear_skills(a7)
    check("清空技能 = 空数组", g6.actor_skills(a7) == [])
    check("改技能会标记结构性改动（保存走整档重写）",
          g6.doc.structural is True)
    g6.actor_set_skills(a7, base)
    check("整份写回原技能（去重升序）",
          g6.actor_skills(a7) == sorted(set(base)))

    # ---------------- 门派 @sect_id（2026-09-20；门派不是 Data 表，是脚本 $sects）
    print("\n-- 门派：@sect_id / 门派技能表 --")
    from tables import sect
    # 2026-10-04：按真实 `$sects` 补齐 —— **14 个门派**（0 无门派 + 1..13 + 20 九黎城），
    # id **不连号**；每个门派 10 个 + 1 个 index 10 的「上古××」秘技（凌波城 12 个）。
    check("门派表 15 项（无门派 + 14 门派；id 不连号：…13、20）",
          len(sect.SECTS) == 15 and 13 in sect.SECTS and 20 in sect.SECTS
          and 14 not in sect.SECTS, len(sect.SECTS))
    check("无门派没有技能", sect.sect_skill_ids(0) == ())
    check("每个正式门派 ≥10 个技能（含 index 10 的秘技）",
          all(len(sect.sect_skill_ids(s)) >= 10
              for s in sect.SECT_ORDER if s != 0),
          [len(sect.sect_skill_ids(s)) for s in sect.SECT_ORDER])
    check("门派名字 -> id 能反查", sect.SECT_NAME_TO_ID.get("五庄观") == 1)
    check("两个新门派在表里（凌波城 13 / 九黎城 20）、10 号已改名「阴曹地府」",
          sect.SECT_NAME_TO_ID.get("凌波城") == 13
          and sect.SECT_NAME_TO_ID.get("九黎城") == 20
          and sect.sect_name(10) == "阴曹地府", sect.sect_name(10))
    check("技能能反查门派（181 -> 1 五庄观）",
          sect.sect_of_skill(181) == 1)
    check("新门派的技能也能反查（713 -> 13 凌波城 / 701 -> 20 九黎城）",
          sect.sect_of_skill(713) == 13 and sect.sect_of_skill(701) == 20,
          "%r / %r" % (sect.sect_of_skill(713), sect.sect_of_skill(701)))
    check("职业自带的 #9 不属于任何门派（别把职业技能算成门派技能）",
          sect.sect_of_skill(9) is None)

    sid0 = g6.actor_sect_id(a7)
    check("能读到角色 @sect_id", isinstance(sid0, int), sid0)
    check("门派名字对得上表", g6.actor_sect_name(a7) == sect.sect_name(sid0))
    sect_ids = g6.sect_skills(a7)
    check("sect_skills 与门派表一致", sect_ids == list(sect.sect_skill_ids(sid0)))
    cls_ids = g6.actor_class_learnings(a7)
    check("职业自带技能非空（至少 #9）", 9 in cls_ids, cls_ids)
    # ⚠ 别再断言「真实存档里没有非本门派技能」—— 2026-09-20 被真档打脸：
    # 游戏**支持换门派**（`@sect_id` 是 attr_accessor，由剧情事件的脚本直接写），
    # 而 `Game_Actor#learn_skill` 只 push + 排序、**从不清理**换门派前的技能。
    # 实测李修远（门派五庄观）身上就留着 247/253/254 三个普陀山技能。
    # 所以这里只验**结构不变量**（不依赖存档现状），现状改成打印信息。
    bad = []
    for _i, x in sv6.actors():
        sk = set(g6.actor_skills(x))
        off = set(i for i, _n in g6.off_sect_skills(x))
        sset = set(g6.sect_skills(x))
        if not off <= sk or (off & sset):
            bad.append((sv6.actor_name(x), sorted(off - sk), sorted(off & sset)))
    check("off_sect_skills 恒 ⊆ @skills 且与本门派技能不相交", not bad, bad)
    _info = [(sv6.actor_name(x), [i for i, _n in g6.off_sect_skills(x)])
             for _i, x in sv6.actors() if g6.off_sect_skills(x)]
    print("  （信息，不作断言）真档里带非本门派技能的角色：%r" % (_info,))

    # 塞一个别的门派的技能进去 → 必须被认出来。用**增量**断言，不依赖存档现状。
    off_before = set(i for i, _n in g6.off_sect_skills(a7))
    others = [s for s in sect.sect_skill_ids(12 if sid0 != 12 else 1)
              if s not in g6.actor_skills(a7) and s not in cls_ids]
    check("有可用的「别的门派」技能可选", bool(others), others[:3])
    if others:
        g6.actor_learn_skill(a7, others[0])
        off_after = set(i for i, _n in g6.off_sect_skills(a7))
        check("塞进别的门派技能后能被标出来（增量）",
              off_after - off_before == set([others[0]]),
              "%r → %r" % (sorted(off_before), sorted(off_after)))
        g6.actor_forget_skill(a7, others[0])
        _now = set(i for i, _n in g6.off_sect_skills(a7))
        check("删掉后回到原样（增量）", _now == off_before, sorted(_now))
    # 老角色没 @sect_id 的话不能炸
    bare = M.ObjNode("Game_Actor")
    bare.ivars = [("@class_id", game.int_node(1))]
    check("没有 @sect_id 字段的角色返回 None 而不是抛异常",
          g6.actor_sect_id(bare) is None
          and g6.actor_sect_name(bare) is None
          and g6.sect_skills(bare) == [])
    check("表里没有的门派 id 也不会炸",
          sect.sect_name(999) is None
          and sect.sect_skill_ids(999) == ()
          and sect.sect_of_skill(999999) is None)

    # ---------------- 2026-10-08：仓库 / 搬格对调 / 复制 / 整理 --------------
    # ⚠ 单开一份副本：前面几段改的是同一份 sv，这段要干净的初始状态。
    copyS = os.path.join(WORK, "game_slots.rvdata2")
    shutil.copyfile(real, copyS)
    svS = save.SaveDoc(copyS)
    gS = game.GameEditor(svS)

    def snapS(kind="pack"):
        return dict((s, (iid, cnt)) for s, _p, _i, iid, _n, cnt in gS.bag(kind))

    pkS, whS = snapS("pack"), snapS("warehouse")
    check("仓库容器读得出来（形状与背包一致）",
          isinstance(gS.warehouse_hash(), M.HashNode),
          "%d 件 / 已开 %d 页" % (len(whS), gS.warehouse_page()))
    check("仓库页数 = 已开页数（夹在 1~%d）" % game.MAX_WAREHOUSE_PAGES,
          1 <= gS.page_count("warehouse") <= game.MAX_WAREHOUSE_PAGES,
          gS.page_count("warehouse"))
    check("背包页数恒为 4（跟仓库不是一套）",
          gS.page_count("pack") == 4, gS.page_count("pack"))
    check("老 KINDS 的 @weapons / @armors 仍是空容器（真值 0 对）",
          len(gS.container("Weapons").pairs) == 0
          and len(gS.container("Armors").pairs) == 0)
    check("_db_of 把 pack/warehouse 都映到 Items 表",
          game.GameEditor._db_of("pack") == "Items"
          and game.GameEditor._db_of("warehouse") == "Items")
    slotsS = sorted(pkS)
    check("背包至少 2 格（够测对调）", len(slotsS) >= 2, len(slotsS))

    if len(slotsS) >= 2:
        sa, sb = slotsS[0], slotsS[1]
        ia, ib = pkS[sa][0], pkS[sb][0]
        gS.move_slots("pack", [sa], target=sb)
        now = snapS()
        check("单格对调：源格内容换到目标格", now[sb][0] == ia,
              "槽 %d → %d" % (sa, sb))
        check("单格对调：目标格原来的换回源格", now[sa][0] == ib)
        check("对调后每格数量跟着走",
              now[sb][1] == pkS[sa][1] and now[sa][1] == pkS[sb][1])
        check("对调不增减格子数", len(now) == len(pkS), len(now))
        gS.move_slots("pack", [sa], target=sb)
        check("再对调一次回到原样（幂等）", snapS() == pkS)

    # 整理：受控场景。挑一个**本来空的**背包页（真档第 3 页是空的）
    blank = None
    for _p in range(gS.page_count("pack")):
        if not gS.bag("pack", _p):
            blank = _p
            break
    check("找得到一个空的背包页（受控测整理）", blank is not None, blank)
    mergeable = None
    for s, _p, _i, iid, _nm, _c in gS.bag("pack"):
        if gS.stack_key(gS._item_node("pack", s)) is not None:
            mergeable = iid
            break
    check("背包里找得到可合并的道具（同类合并才有意义）",
          mergeable is not None, "id=%s" % mergeable)

    if blank is not None and mergeable is not None:
        s0 = gS.slot_key(blank, 0)
        s2 = gS.slot_key(blank, 2)
        s3 = gS.slot_key(blank, 3)
        other = 2 if mergeable != 2 else 3
        gS.set_item("pack", s0, mergeable, count=5)
        gS.set_item("pack", s2, mergeable, count=3)
        gS.set_item("pack", s3, other, count=7)
        mv, mg = gS.arrange("pack", blank, compact=True, merge=False)
        now = snapS()
        check("紧凑排列：中间的空格被消掉（槽 %d 三格连排）" % s0,
              [now.get(s0 + i, (None,))[0] for i in range(3)]
              == [mergeable, mergeable, other],
              [now.get(s0 + i, (None, 0))[0] for i in range(3)])
        check("紧凑排列：搬了 2 格、没合并", (mv, mg) == (2, 0), (mv, mg))
        check("紧凑排列：腾空的格子变空", s3 not in now, sorted(now)[:4])
        mv, mg = gS.arrange("pack", blank, compact=True, merge=True)
        now = snapS()
        check("同类合并：5 + 3 叠成一格 8", now.get(s0, (None, 0)) == (mergeable, 8),
              now.get(s0))
        check("同类合并：另一格补上来（%s 落到槽 %d）" % (other, s0 + 1),
              now.get(s0 + 1, (None,))[0] == other, now.get(s0 + 1))
        check("同类合并：合并 1 格、紧凑 1 格", (mv, mg) == (1, 1), (mv, mg))
        check("整理后不超每格上限",
              all(gS.stack_limit(gS._item_node("pack", s)) >= c
                  for s, (_i2, c) in now.items()))
        # 武器/防具不可叠：stack_key 必须是 None、上限 1（整理不去合并它们）
        n_non = 0
        for s, _p, _i, _iid, _nm, _c in gS.bag("pack"):
            nd = gS._item_node("pack", s)
            if getattr(save._deref(nd), "cls", "") != "RPG::Item":
                n_non += 1
                if not (gS.stack_key(nd) is None and gS.stack_limit(nd) == 1):
                    check("武器/防具不可叠（stack_key=None、上限 1）", False,
                          "槽 %d" % s)
                    break
        else:
            check("武器/防具不可叠（stack_key=None、上限 1）", True,
                  "本档背包里有 %d 件武器/防具" % n_non)

        # 复制：进空格 ⇒ 持有数 +N；进有货格 ⇒ 必须被拒
        free = list(gS.empty_slots("pack", blank))[:2]
        check("整理后那一页还有空格可复制", len(free) >= 2, free)
        if len(free) >= 2:
            sid = mergeable
            cnt_s = snapS()[s0][1]
            before_cnt = gS.item_counts().get(sid, 0)
            before_sec = gS.security_total(sid)
            gS.move_slots("pack", [s0], target=free[0], copy=True)
            now = snapS()
            check("复制进了空格", now.get(free[0], (None,))[0] == sid,
                  "槽 %d" % free[0])
            check("源格还在（复制 ≠ 搬走）", now.get(s0, (None,))[0] == sid)
            check("持有数 +%d" % cnt_s,
                  gS.item_counts().get(sid, 0) == before_cnt + cnt_s,
                  "%d -> %d" % (before_cnt, gS.item_counts().get(sid, 0)))
            if before_sec is not None:
                check("记账 security[:items] 跟着 +%d" % cnt_s,
                      gS.security_total(sid) == before_sec + cnt_s,
                      "%s -> %s" % (before_sec, gS.security_total(sid)))
            else:
                print("  [--] 本档 security[:items] 里没有这件东西的账"
                      "（V2.201 常见），跳过记账断言")
            try:
                gS.move_slots("pack", [s0], target=s0 + 1, copy=True)
                check("复制进有货格被拒", False, "居然通过了")
            except ValueError:
                check("复制进有货格被拒", True)

        # 跨容器：背包 → 仓库（保序、总数不变）
        wsrc = [s for s in (s0, s0 + 1) if s in snapS()][:1]
        if wsrc and gS.page_count("warehouse") >= 1:
            s1 = wsrc[0]
            tot_before = gS.item_counts()
            wid = snapS()[s1][0]
            _n, used = gS.move_slots("pack", [s1], dst="warehouse", target=0)
            check("跨容器搬运：仓库第 1 格有货", snapS("warehouse").get(0, (None,))[0] == wid,
                  "槽号 %s" % used)
            check("跨容器搬运：背包那一格空了", s1 not in snapS())
            check("跨容器搬运：总持有数不变", gS.item_counts() == tot_before)
            check("跨容器搬运：不落在仓库页数之外",
                  all(s < gS.page_count("warehouse") * game.PACK_PAGE_SIZE
                      for s in used))

    # 落盘重开：仓库与背包内容都要一致（整档重写别坏结构）
    want_pk, want_wh = snapS("pack"), snapS("warehouse")
    pages_before = [len(gS.bag("pack", p)) for p in range(4)]
    svS.doc.save()
    svT = save.SaveDoc(copyS)
    gT = game.GameEditor(svT)
    now_pk = dict((s, (iid, cnt)) for s, _p, _i, iid, _n, cnt in gT.bag("pack"))
    now_wh = dict((s, (iid, cnt))
                  for s, _p, _i, iid, _n, cnt in gT.bag("warehouse"))
    check("重开后背包一致", now_pk == want_pk, "%d 格" % len(now_pk))
    check("重开后仓库一致", now_wh == want_wh, "%d 格" % len(now_wh))
    check("重开后每页件数不变",
          [len(gT.bag("pack", p)) for p in range(4)] == pages_before)

    # ---------------- 2026-10-08：修炼（`@sect_data[:修炼]`，8 项）----------
    # 机制（V2.201 脚本实测）：游戏**只在战斗结算**读 `[:lv]`，
    # 升级不改任何属性；`A_*` = 人物修炼、`B_*` = 召唤兽修炼（都在角色身上）。
    aX = svT.actors()[0][1]
    rowsX = gT.practice(aX)
    check("修炼读到 8 项", len(rowsX) == 8, len(rowsX))
    check("A 组（人物）在前 4 项",
          [r["key"] for r in rowsX[:4]] ==
          ["A_攻击", "A_法术", "A_防御", "A_法防"],
          [r["key"] for r in rowsX[:4]])
    check("B 组（召唤兽）在后 4 项",
          [r["key"] for r in rowsX[4:]] ==
          ["B_攻击", "B_法术", "B_防御", "B_法防"],
          [r["key"] for r in rowsX[4:]])
    check("need = (lv² + 3lv + 11) × 10",
          all(r["need"] == (r["lv"] * r["lv"] + r["lv"] * 3 + 11) * 10
              for r in rowsX))
    check("分组读：A / B 各 4 项",
          len(gT.practice(aX, "A")) == 4 and len(gT.practice(aX, "B")) == 4)
    check("两组的说明文字对得上",
          gT.practice(aX, "A")[0]["group_cn"] == "人物修炼"
          and gT.practice(aX, "B")[0]["group_cn"] == "召唤兽修炼")

    lvX = gT.actor_level(aX)
    check("角色 %d 级 ⇒ 上限 20" % lvX, gT.practice_max(aX) == 20, lvX)

    orderX = dict((r["key"], (r["lv"], r["exp"])) for r in gT.practice(aX))
    check("设等级 20 生效", gT.practice_set(aX, "A_攻击", lv=20, exp=0)
          == (20, 0))
    check("lv=99 被夹到 20", gT.practice_set(aX, "A_法术", lv=99)[0] == 20)
    check("lv=-3 被夹到 0", gT.practice_set(aX, "A_防御", lv=-3)[0] == 0)
    check("本级满经验 = 门槛 - 1（0 级 109、20 级 4709）",
          gT.practice_full_exp(0) == 109 and gT.practice_full_exp(20) == 4709,
          (gT.practice_full_exp(0), gT.practice_full_exp(20)))
    nX = gT.practice_next_exp(5)
    check("exp 超门槛被夹到 %d（门槛 -1）" % (nX - 1),
          gT.practice_set(aX, "A_法防", lv=5, exp=99999)[1] == nX - 1)
    check("只传 exp 时等级不动",
          gT.practice_set(aX, "B_法术", exp=50)[0] == orderX["B_法术"][0])
    check("只传 lv 时经验不动",
          gT.practice_set(aX, "B_攻击", lv=9)[1] == orderX["B_攻击"][1])
    try:
        gT.practice_set(aX, "C_攻击", lv=1)
        check("不存在的修炼项被拒", False, "居然通过了")
    except KeyError:
        check("不存在的修炼项被拒", True)

    atrX = list(svT.attr_items(aX))
    check("B 组一键满级改 4 项",
          gT.practice_set_group(aX, "B", lv=20, exp=0) == 4)
    check("B 组全 20 级 / 0 经验",
          all(r["lv"] == 20 and r["exp"] == 0 for r in gT.practice(aX, "B")))
    check("A 组清零改 4 项",
          gT.practice_set_group(aX, "A", lv=0, exp=0) == 4)
    check("A 组全 0 级", all(r["lv"] == 0 for r in gT.practice(aX, "A")))
    check("改修炼**不动属性**（@attr 原样）",
          list(svT.attr_items(aX)) == atrX)

    # ---- 全员拉满（2026-10-08 川）：所有角色 × 8 项按**游戏规则**拉满 ----
    # ⚠ 不是一律 25（那是上一版）：<90 级 → 20、≥90 级 → 25，逐人取上限；
    #   想无视规则全给 25 要显式传 `lv=25`。
    pairsX = [(a, game.get_int(game.ivar(a, "@actor_id"), -1))
              for _i, a in svT.actors()]
    frogX = [a for a, _aid in pairsX if _aid in game.PRACTICE_SKIP_IDS]
    frogX_before = {}
    if frogX:
        try:
            frogX_before = dict((r["key"], (r["lv"], r["exp"]))
                                for r in gT.practice(frogX[0]))
        except KeyError:
            frogX_before = {}
    atrX2 = dict((game.get_int(game.ivar(a, "@actor_id"), -1),
                  list(svT.attr_items(a))) for a, _aid in pairsX)
    check("跳过名单 = (6,)（巨小蛙）", game.PRACTICE_SKIP_IDS == (6,),
          game.PRACTICE_SKIP_IDS)
    nXa, nXi, skipX = gT.practice_set_everyone()
    check("全员拉满跳过名单里的角色", skipX == ["巨小蛙"], skipX)
    check("改了 %d 人（总 %d 人）" % (len(pairsX) - 1, len(pairsX)),
          nXa == len(pairsX) - 1 and len(pairsX) >= 2, (nXa, len(pairsX)))
    check("记了 %d 项（8 × 人数）" % ((len(pairsX) - 1) * 8),
          nXi == (len(pairsX) - 1) * 8, nXi)
    badX, seenX = [], {}
    for a, _aid in pairsX:
        if _aid in game.PRACTICE_SKIP_IDS:
            continue
        want = gT.practice_max(a)
        wexp = gT.practice_full_exp(want)
        seenX[want] = seenX.get(want, 0) + 1
        badX += ["%s=%s/%s(应%d/%d)" % (r["key"], r["lv"], r["exp"], want, wexp)
                 for r in gT.practice(a)
                 if r["lv"] != want or r["exp"] != wexp]
    check("除跳过的，所有人 8 项 = **各自规则上限** / 本级满经验",
          not badX, badX[:4])
    if game.get_int(game.ivar(aX, "@actor_id"), -1) not in game.PRACTICE_SKIP_IDS:
        check("<90 级角色（aX = %d 级）拉出来是 20" % gT.actor_level(aX),
              seenX.get(game.PRACTICE_LV_BELOW_90, 0) >= 1, seenX)
    if frogX and frogX_before:
        got = {}
        try:
            got = dict((r["key"], (r["lv"], r["exp"]))
                       for r in gT.practice(frogX[0]))
        except KeyError:
            got = None
        check("跳过的角色原样未动", got == frogX_before, got)
    check("全员拉满也不动属性",
          all(list(svT.attr_items(a)) == atrX2[_aid] for a, _aid in pairsX))
    check("全员拉满幂等",
          gT.practice_set_everyone()[:2] == (nXa, nXi))
    # 想无视规则、一律 25 ⇒ 显式传 `lv=25`（那时才走 clamp=False）
    _n25a, _n25i, _s25 = gT.practice_set_everyone(lv=25)
    check("显式 lv=25 仍能无视规则全给 25（经验同样满）",
          _s25 == skipX and all(
              r["lv"] == 25 and r["exp"] == gT.practice_full_exp(25)
              for a, _aid in pairsX
              if _aid not in game.PRACTICE_SKIP_IDS
              for r in gT.practice(a)), _s25)
    gT.practice_set_everyone()                      # 复位回规则上限
    check("clamp=False 也只给到 25（不是无限）",
          gT.practice_set(aX, "B_攻击", lv=99, exp=0, clamp=False)[0] == 25)
    check("clamp=True 仍按规则夹到 20",
          gT.practice_set(aX, "B_攻击", lv=99, exp=0)[0] == 20)
    check("groups=['A'] 只动 A 组",
          gT.practice_set_everyone(groups=["A"])[1] == (len(pairsX) - 1) * 4)

    # 上限跟着角色等级走：≥90 级 → 25
    gT.sv.set_actor_field(aX, "@level", 90)
    check("90 级 ⇒ 上限 25", gT.practice_max(aX) == 25)
    check("90 级能写到 25", gT.practice_set(aX, "A_攻击", lv=25)[0] == 25)
    gT.sv.set_actor_field(aX, "@level", lvX)
    check("退回 %d 级 ⇒ 上限又变 20" % lvX, gT.practice_max(aX) == 20)

    wantX = dict((r["key"], (r["lv"], r["exp"])) for r in gT.practice(aX))
    svT.doc.save()
    svY = save.SaveDoc(copyS)
    gY = game.GameEditor(svY)
    aY = svY.actors()[0][1]
    check("落盘重开后 8 项一致",
          dict((r["key"], (r["lv"], r["exp"])) for r in gY.practice(aY))
          == wantX, "%r" % wantX)

    # ================= 坐骑（2026-10-08 川：独立页签 + 增删改 / 乘骑出战）
    # ⚠ 必须**重新**建一份 SaveDoc：前面第 676 行的 `sv.doc.save()` 之后
    #   `sv.contents` / `sv.header` 还指着旧那棵树（`Doc.save` 会把
    #   `doc.objects` 换成重解析出来的新对象），继续用 `sv` 读到的节点
    #   根本不在 `doc.objects` 里 ⇒ 改上去的东西下次保存全丢（本轮实测踩到）。
    #   界面侧没这个问题：`save_save()` 存完就是 `save.SaveDoc(doc=self.doc)`。
    print("\n---- 坐骑（2026-10-08 川：独立页签 + 增删改 / 乘骑出战）----")
    sv = save.SaveDoc(copy)
    g = game.GameEditor(sv)
    rds = rides.Rides(g)
    aR = sv.actors()[0][1]
    rowsR = rds.of(aR)
    check("坐骑能列出来", len(rowsR) >= 1, "%d 匹" % len(rowsR))
    if rowsR:
        r0 = rowsR[0][1]
        i0 = rds.info(r0)
        check("坐骑字段齐全（名字/品质/阶/灵气/五资质/移速/技能）",
              all(k in i0 for k in ("name", "quality_cn", "level", "exp", "atk",
                                    "def", "hp", "mp", "agi", "speed", "skills")),
              "%s/%s/%s阶" % (i0["name"], i0["quality_cn"], i0["level"]))
        check("阶上限是 9（游戏 Game_Ride#max_level 写死）",
              i0["max_level"] == 9 == rides.RIDE_MAX_LEVEL)
        check("灵气表照 $exps[:ride]（1→2 要 500、8→9 要 10000）",
              rides.next_exp(1) == 500 and rides.next_exp(8) == 10000,
              "%s / %s" % (rides.next_exp(1), rides.next_exp(8)))
        check("「本级满灵气」= 门槛 − 1（9 阶 = 14999）",
              rides.full_exp(1) == 499 and rides.full_exp(9) == 14999)
        check("技能上限按品质（普通 3 / 靓仔 4 / 神骑 6）",
              (rides.skill_max(0), rides.skill_max(1), rides.skill_max(2))
              == (3, 4, 6))
        # 改字段
        rds.set_level(r0, 99)
        check("改阶会被夹到 9（照游戏 change_level）", rds.info(r0)["level"] == 9)
        rds.set_level(r0, 0)
        check("改阶下界是 1", rds.info(r0)["level"] == 1)
        rds.set_level(r0, 7)
        rds.set_exp(r0, rides.full_exp(7))
        check("灵气写到「本级满」", rds.info(r0)["exp"] == rides.full_exp(7))
        rds.set_attr(r0, "atk", 99999)
        check("资质夹到 9999（Game_Ride_Attr#get_max_data）",
              rds.info(r0)["atk"] == 9999)
        rds.set_speed(r0, 0.095)
        check("移速写进 @param_plus[6]（×1000）",
              abs(rds.info(r0)["speed"] - 0.095) < 1e-9
              and rides.RIDE_SPEED_MUL == 1000,
              "%r" % rds.info(r0)["speed"])
        rds.set_quality(r0, 0)
        check("品质能改（神骑 → 普通）", rds.info(r0)["quality_cn"] == "普通")
        rds.set_quality(r0, 2)
        check("品质回到神骑", rds.info(r0)["quality_cn"] == "神骑")
        rds.set_nickname(r0, "测试昵称")
        check("昵称能改", rds.info(r0)["nickname"] == "测试昵称")
        # 技能：按品质截断
        got = rds.set_skills(r0, [471, 472, 473, 474, 475, 476, 477, 478])
        check("技能按品质上限截断（神骑 6）", got == [471, 472, 473, 474, 475, 476],
              "%r" % got)
        check("技能去重", rds.set_skills(r0, [471, 471, 472]) == [471, 472])
        # 乘骑 / 出战
        rds.set_riding(aR, 0)
        check("能设「乘骑中」", rds.index_of(aR, rds.riding(aR)) == 0)
        rds.set_fighting(aR, 0)
        check("能设「出战」", rds.index_of(aR, rds.fighting(aR)) == 0)
        check("状态列显示「乘战」", rds.bike_state(aR, rds.riding(aR)) == "乘战")
        rds.clear_riding(aR)
        check("能取消乘骑", rds.riding(aR) is None)

        # ---- 克隆新增
        n_before = len(rds.of(aR))
        new = rds.add(aR, ride_id=258, quality=2, level=9,
                      exp=rides.full_exp(9), speed=0.19,
                      skills=[471, 472, 473, 474, 475, 476])
        check("新增后 +1 匹", len(rds.of(aR)) == n_before + 1)
        ni = rds.info(new)
        check("新匹照参数写（神骑 / 9 阶 / 满灵气 / 移速 19%）",
              ni["quality"] == 2 and ni["level"] == 9
              and ni["exp"] == rides.full_exp(9) and abs(ni["speed"] - 0.19) < 1e-9,
              "%s/%s阶/%s" % (ni["quality_cn"], ni["level"], ni["speed"]))
        check("新匹自引用指回自己（@attr.@master 是这匹）",
              save._deref(save.ivar(rds.attr_node(new), "@master")) is new)
        check("新匹 @master 指回主人",
              save._deref(save.ivar(new, "@master")) is aR)
        check("新匹没有进入乘骑位（已有一匹乘着时不抢）",
              rds.index_of(aR, rds.riding(aR)) < 0)
        # 拉满（⚠ 只管数值：技能一个字都不动 —— 2026-10-09 川
        #   「你拉满，改我原本的技能干嘛？？」）
        sk_before = rds.skills(rds.of(aR)[0][1])
        rds.max_out(aR, 0)
        m0 = rds.info(rds.of(aR)[0][1])
        check("拉满：神骑 / 9 阶 / 满灵气 / 资质取神骑档上限",
              m0["quality"] == 2 and m0["level"] == 9
              and m0["exp"] == rides.full_exp(9)
              and m0["atk"] == m0["def"] == m0["hp"] == m0["mp"] == m0["agi"]
              == rides.RIDE_ATTR_RANGE[2][1], "%r" % m0)
        check("拉满不动技能（原样保留，不重配）",
              sk_before and m0["skills"] == sk_before,
              "%r → %r" % (sk_before, m0["skills"]))
        # 全员拉满（2026-10-09 川：「顺便加个全员拉满按钮」）—— 跨角色
        _n_all = rds.count_all()
        _got_all = rds.max_out_all()
        _bad_all = [(ai, i) for ai, a in sv.actors()
                    for i, r in rds.of(a)
                    if not (rds.info(r)["quality"] == 2
                            and rds.info(r)["level"] == 9
                            and rds.info(r)["atk"]
                            == rides.RIDE_ATTR_RANGE[2][1])]
        check("全员拉满：跨角色、匹数对、全到神骑/9 阶/资质上限",
              _got_all == _n_all and _n_all > 0 and not _bad_all,
              "改了 %d / 共 %d，没拉满的 %r"
              % (_got_all, _n_all, _bad_all))
        # 落盘 → 重解析
        wantR = dict((i, rds.info(r)) for i, r in rds.of(aR))
        sv.doc.save()
        # ⚠ 存完必须重开（见本节开头那条）：旧 SaveDoc 的 contents 是旧树
        sv = save.SaveDoc(copy)
        g = game.GameEditor(sv)
        rdsR = rides.Rides(g)
        aRR = sv.actors()[0][1]
        gotR = dict((i, rdsR.info(r)) for i, r in rdsR.of(aRR))
        check("落盘重开后坐骑数一致", len(gotR) == len(wantR),
              "%d vs %d" % (len(gotR), len(wantR)))
        check("落盘重开后每匹字段一致",
              all(gotR[i]["level"] == wantR[i]["level"]
                  and gotR[i]["exp"] == wantR[i]["exp"]
                  and gotR[i]["quality"] == wantR[i]["quality"]
                  and gotR[i]["atk"] == wantR[i]["atk"]
                  and gotR[i]["skills"] == wantR[i]["skills"]
                  and gotR[i]["nickname"] == wantR[i]["nickname"]
                  for i in wantR if i in gotR))
        # 删
        rdsR.remove(aRR, 0)
        check("放生后 -1 匹", len(rdsR.of(aRR)) == len(wantR) - 1)

    # ---- 坐骑技能批量学 / 忘 / 清空（2026-10-09 川：「要做成召唤兽那样」）----
    svS = save.SaveDoc(copy)
    gS = game.GameEditor(svS)
    rdsS = rides.Rides(gS)
    aS = svS.actors()[0][1]
    if rdsS.of(aS):
        r0S = rdsS.of(aS)[0][1]
        i0S = rdsS.info(r0S)
        capS = rides.skill_max(i0S["quality"])
        pool = [s for s, _n, _r in rdsS.skill_pool()]
        check("坐骑技能池 = 471~486 共 16 个",
              pool == list(range(471, 487)) and len(pool) == 16,
              "%d 个" % len(pool))
        curS = set(rdsS.skills(r0S))
        added, already, over = rdsS.learn_many(r0S, pool)
        gotS = rdsS.skills(r0S)
        check("批量学按品质上限截断（超的原样报回、不静默丢）",
              len(gotS) <= capS
              and set(already) == set(pool) & curS
              and set(over) == set(pool) - set(gotS),
              "%d 个 ≤ 上限 %d，超出 %d" % (len(gotS), capS, len(over)))
        dropS, missS = rdsS.forget_many(r0S, gotS[:2] + [9999])
        check("批量忘（不在身上的原样报回）",
              len(dropS) == min(2, len(gotS)) and missS == [9999],
              "%s / %s" % (dropS, missS))
        rdsS.clear_skills(r0S)
        check("清空技能", rdsS.skills(r0S) == [])
        svS.doc.save()
        svS2 = save.SaveDoc(copy)
        rdsS2 = rides.Rides(game.GameEditor(svS2))
        check("坐骑技能清空能落盘、重开一致",
              rdsS2.skills(rdsS2.of(svS2.actors()[0][1])[0][1]) == [])

    shutil.rmtree(WORK, ignore_errors=True)
    print("\n==== 通过 %d, 失败 %d ====" % (OK[0], OK[1]))
    return 1 if OK[1] else 0


def _item_of(g, kind, slot):
    h = g.container(kind)
    for k, v in h.pairs:
        if M.value_of(save._deref(k)) == slot:
            arr = save._deref(v)
            return save._deref(arr.items[0])
    return None


def _change_of(g, item_id):
    _sec, items = g.security_hash()
    return save._deref(save.hash_get(items, item_id))


if __name__ == "__main__":
    sys.exit(main())
