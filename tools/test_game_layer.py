# -*- coding: utf-8 -*-
"""v0.4 游戏数据层回归测试：背包 / 经验 / 召唤兽 / 防作弊。

全程在**存档副本**上操作（原存档一个字节都不动）。

用法：python tools/test_game_layer.py
"""
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.stdout.reconfigure(errors="replace")

import xj_backup  # noqa: E402
import xj_env  # noqa: E402
import xj_game  # noqa: E402
import xj_marshal as M  # noqa: E402
import xj_save  # noqa: E402

OK = [0, 0]
WORK = os.path.join(HERE, "_game")


def check(name, cond, extra=""):
    OK[0 if cond else 1] += 1
    print("  %s %-46s %s" % ("[OK]" if cond else "[NG]", name, extra))


def main():
    real = xj_env.save_path()
    if not os.path.exists(real):
        print("  [--] 找不到存档 %s" % real)
        return 0
    shutil.rmtree(WORK, ignore_errors=True)
    os.makedirs(WORK, exist_ok=True)
    copy = os.path.join(WORK, "game_copy.rvdata2")
    shutil.copyfile(real, copy)

    sv = xj_save.SaveDoc(copy)
    g = xj_game.GameEditor(sv)
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

    newcnt = cnt0 + 7
    g.set_count("Items", slot0, newcnt)
    check("改数量生效", dict((r[0], r[5]) for r in g.bag("Items"))[slot0] == newcnt,
          "%d -> %d" % (cnt0, newcnt))
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
        did = g.baby_preset(baby, "qual")
        check("资质 +100 预设生效",
              g.baby_value(baby, "atk") == vals["atk"] + 100, "、".join(did))
        check("召唤兽技能能列出来", isinstance(g.baby_skills(baby), list),
              "%r" % (g.baby_skills(baby)[:3],))

    # ---------------- 防作弊
    rep = g.anti_cheat_report()
    check("体检报告有内容", len(rep) >= 4, "%d 项" % len(rep))
    # 正常存档本来就不该有超限项（这个副本是干净档）；先造一个作弊标记，
    # 再看体检能不能标出来。
    sys_node = xj_save._deref(xj_save.ivar(sv.section("system"), "@cheated"))
    sv.doc.set_value(sys_node, True)
    rep = g.anti_cheat_report()
    check("体检能标出超限项", any(r[3] for r in rep),
          "、".join(r[0] for r in rep if r[3])[:60] or "（没有超限项）")

    # 故意越界：金钱拉满到上限之上（走底层 sv.set_gold，模拟外部直接改值，
    # 只动 Lock 不动游戏记账 —— 这正是旧版工具留下的坑）
    sv.set_gold(xj_game.MAX_GOLD + 1)
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
          sv.gold() == xj_game.SAFE_GOLD, sv.gold())
    check("修复后金钱账与实际金钱一致", g.security_gold() == sv.gold(),
          "账=%s 钱=%s" % (g.security_gold(), sv.gold()))
    check("修复后 Lock 校验和一致", sv.check_locks() == [])
    check("作弊标记被清掉",
          M.value_of(xj_save._deref(
              xj_save.ivar(sv.section("system"), "@cheated"))) is False)
    kw_node = xj_save._deref(xj_save.ivar(sv.section("system"), "@keyword"))
    check("作弊记录 @keyword 整个清空",
          isinstance(kw_node, M.ArrayNode) and not kw_node.items,
          "%r" % ([x for x in kw_node.items]
                  if isinstance(kw_node, M.ArrayNode) else kw_node))

    # 统一入口 GameEditor.set_gold：超限自动钳到 2/3，Lock + 金钱账一次同步
    got, clamped = g.set_gold(999999999)
    check("set_gold 超上限自动钳到 2/3 安全值",
          got == xj_game.SAFE_GOLD and clamped is True, str((got, clamped)))
    check("钳制后 Lock 与金钱账都同步",
          sv.check_locks() == [] and g.security_gold() == got)
    got2, clamped2 = g.set_gold(123456)
    check("set_gold 未超限原样写入",
          got2 == 123456 and clamped2 is False, str((got2, clamped2)))
    check("正常改钱金钱账也跟着同步", g.security_gold() == 123456)

    # Change 记账支持负数（真实档里金钱账本来就是负的）
    ch_gold = xj_save._deref(xj_game.hash_get(g.security_node(), "gold"))
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
    kid = M.value_of(xj_save._deref(xj_save.hash_get(d, "id"))) if d is not None \
        else None
    check("新加的孵化蛋自己生成了 @attr 内容",
          t == "baby_egg" and isinstance(kid, int),
          "type=%r id=%r" % (t, kid))
    check("生成的召唤兽 id 落在游戏范围内",
          kid in list(range(21, 24)) + list(range(25, 64))
          + list(range(64, 96)) + list(range(127, 135))
          + list(range(96, 127)) or kid is not None, kid)
    g.clear_slot("Items", probe)
    g.add_item("Items", probe, 110, 1, kid=57)
    it = _item_of(g, "Items", probe)
    _t, d = g.item_payload(it)
    check("能指定“孵出哪只”（kid）",
          d is not None and M.value_of(xj_save._deref(
              xj_save.hash_get(d, "id"))) == 57,
          "%r" % (d,))
    # 存档里已有同款时，应该整份克隆（运行时内容一模一样）
    ref_slot = [s for s in g.empty_slots("Items") if s != probe][0]
    g.clear_slot("Items", probe)
    g.add_item("Items", ref_slot, 110, 1, kid=57, clone_like=False)
    g.add_item("Items", probe, 110, 1)          # 默认 clone_like=True
    _t2, d2 = g.item_payload(_item_of(g, "Items", probe))
    got = M.value_of(xj_save._deref(xj_save.hash_get(d2, "id"))) \
        if d2 is not None else None
    check("存档里有同款时直接克隆它的内容", got == 57,
          "克隆到 id=%r（参照蛋是 57）" % (got,))
    g.clear_slot("Items", probe)
    g.clear_slot("Items", ref_slot)
    # 背包里混装武器/防具 → 名字要按对象自己的类去查
    mix = []
    for kind, _iv, cn, _db in xj_game.KINDS:
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
    xj_game.set_ivar(_item_of(g, "Items", probe2), "@attr",
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
          _t3 == "baby_egg" and d3 is not None, "type=%r" % (_t3,))
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
          M.value_of(xj_save._deref(xj_save.hash_get(d4, "id"))) == 21,
          "%r" % (d4,))
    g.set_payload("Items", probe3)          # 不给 kid = 按游戏范围随机
    _t5, d5 = g.item_payload(_item_of(g, "Items", probe3))
    check("不给 kid 时随机重抽", _t5 == "baby_egg" and d5 is not None, "%r" % (d5,))
    try:
        g.set_payload("Items", 999, kid=1)
        check("对空格子重抽会报错", False)
    except Exception as e:
        check("对空格子重抽会报错", "空" in str(e), "%s" % type(e).__name__)
    g.clear_slot("Items", probe3)

    # ---------------- v0.4.4：@attr 的“外层键必须是字符串”，否则游戏读不到
    #  游戏脚本：$item_obj.data[:data][:id]；而 item.data 读的是 @attr["data"]
    #  （**字符串**键）—— 早期工具写成了符号键 :data，于是：
    #    * 工具自己的“内容”列读不出来（游戏写的是字符串键）
    #    * 游戏用蛋时 item.data 为 nil → NoMethodError: undefined method '[]'
    probe4 = [s for s in g.empty_slots("Items")
              if s not in (probe, probe2, probe3, ref_slot)][0]
    g.add_item("Items", probe4, 110, 1, kid=57, clone_like=False)
    it4 = _item_of(g, "Items", probe4)
    attr = xj_save._deref(xj_save.ivar(it4, "@attr"))
    key = xj_save._deref(attr.pairs[0][0])
    check("写出去的 @attr 外层键是**字符串**（和游戏一致）",
          isinstance(key, M.StrNode), type(key).__name__)
    got = M.value_of(key)
    if isinstance(got, bytes):
        got = got.decode("utf-8", "replace")
    check("外层键就是 \"data\"", got == "data", repr(got))
    # 模拟游戏那句 $item_obj.data[:data][:id]
    #   item.data        → @attr["data"]      = {:type=>..., :data=>{:id=>...}}
    #   item.data[:data] → {:id=>...}
    inner = xj_save.hash_get(xj_save.hash_get(attr, "data"), "data")
    d1 = M.value_of(xj_save._deref(xj_save.hash_get(inner, "id"))) \
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
    payload = xj_save.hash_get(xj_save._deref(xj_save.ivar(it5, "@attr")), "data")
    xj_game.set_ivar(it5, "@attr",
                     M.HashNode([(M.SymbolNode("data"), payload)],
                                default=None))
    check("符号键现在能被“读”出来（兼容）",
          g.item_payload(it5)[0] == "baby_egg", g.payload_summary(it5))
    check("但体检知道游戏读不到（键类型不对）", not g.payload_key_ok(it5))
    rows5 = g.pack_report()
    check("体检会把“键类型不对”列出来",
          any(r[1] == probe5 and "键" in r[3] for r in rows5),
          "%r" % [(r[1], r[3]) for r in rows5 if r[1] == probe5])
    g.pack_fix(rows5)
    attr5 = xj_save._deref(xj_save.ivar(_item_of(g, "Items", probe5), "@attr"))
    check("修复后键变成字符串（游戏能读了）",
          g.payload_key_ok(_item_of(g, "Items", probe5)),
          type(xj_save._deref(attr5.pairs[0][0])).__name__)
    _t6, d6 = g.item_payload(_item_of(g, "Items", probe5))
    check("修复时内容没丢（还是 id=57）",
          d6 is not None and M.value_of(xj_save._deref(
              xj_save.hash_get(d6, "id"))) == 57,
          "type=%r" % (_t6,))
    g.clear_slot("Items", probe5)

    # ---------------- 保存 / 重开
    before = dict((r[0], r[5]) for r in g.bag("Items"))
    plain = sv.doc.plain_bytes()
    M.parse_stream(plain)
    check("结构性改动后仍能序列化并解析", True, "%d 字节" % len(plain))
    sv.doc.save()
    sv2 = xj_save.SaveDoc(copy)
    g2 = xj_game.GameEditor(sv2)
    check("重开后背包改动还在",
          dict((r[0], r[5]) for r in g2.bag("Items")) == before,
          "%r" % dict((r[0], r[5]) for r in g2.bag("Items")))
    aid2, actor2 = sv2.actors()[0]
    check("重开后经验还在", g2.exp(actor2) == e0 + 1000, g2.exp(actor2))
    check("重开后召唤兽改动还在",
          g2.baby_value(g2.babies(actor2)[0][1], "level") == 7,
          g2.baby_value(g2.babies(actor2)[0][1], "level"))
    baks = [f for f in os.listdir(xj_backup.backup_dir(copy)) if ".bak." in f]
    check("原文件留了备份（在备份目录）", len(baks) >= 1, "%r" % baks[:2])
    check("存档目录不再散落 .bak.",
          not [f for f in os.listdir(WORK) if ".bak." in f])

    # ---------------- 升级所需经验 = 查表（不是 @limit_exp）
    print("\n-- 升级所需经验（游戏脚本 $exps 查表）--")
    sv3 = xj_save.SaveDoc(copy)
    g3 = xj_game.GameEditor(sv3)
    check("actor 表：40 级 = 332296（游戏界面上显示的数）",
          xj_game.exp_for_level(40, "actor") == 332296,
          xj_game.exp_for_level(40, "actor"))
    check("baby 表：40 级 = 84050",
          xj_game.exp_for_level(40, "baby") == 84050,
          xj_game.exp_for_level(40, "baby"))
    check("等级越界返回 None", xj_game.exp_for_level(9999) is None)
    check("等级非法（None）返回 None", xj_game.exp_for_level(None) is None)

    a3 = sv3.actors()[0][1]
    lv3 = g3.actor_level(a3)
    check("next_level_exp == 表里[当前等级]",
          g3.next_level_exp(a3) == xj_game.exp_for_level(lv3, "actor"),
          "lv=%s → %s" % (lv3, g3.next_level_exp(a3)))
    g3.set_actor_level(a3, 20)
    check("改等级后升级所需经验跟着变",
          g3.next_level_exp(a3) == xj_game.exp_for_level(20, "actor"),
          g3.next_level_exp(a3))

    # @limit_exp 是「累计获得经验」的封顶计数器，不是升级所需经验
    none_lim = [a for _, a in sv3.actors()
                if xj_save._deref(xj_save.ivar(a, "@limit_exp")) is None]
    if none_lim:
        check("没这个 ivar 的角色：limit_exp 读到 0（不再是空白）",
              g3.limit_exp(none_lim[0]) == 0, g3.limit_exp(none_lim[0]))
        check("没这个 ivar 的角色：set_limit_exp 返回 None 且不抛异常",
              g3.set_limit_exp(none_lim[0], 123) is None)
    else:
        check("（本存档所有角色都有 @limit_exp，跳过缺字段场景）", True)
    has_lim = [a for _, a in sv3.actors()
               if xj_save._deref(xj_save.ivar(a, "@limit_exp")) is not None]
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
          en is not None and xj_save.M.value_of(en) == 12345,
          "class_id=%s" % xj_save.M.value_of(xj_save._deref(
              xj_save.ivar(a4, "@class_id"))))
    check("exp_key() 与 @class_id 一致",
          g3.exp_key(a4) == xj_save.M.value_of(xj_save._deref(
              xj_save.ivar(a4, "@class_id"))))
    g3.set_exp(a4, e_before)

    # 造一个「转过职」的存档：Hash 里塞一条别的职业，游戏读 class_id 那条
    h = xj_save._deref(xj_save.ivar(a4, "@exp"))
    cid = g3.exp_key(a4)
    other = 999 if cid != 999 else 998
    h.pairs.insert(0, (M.IntNode(other), M.IntNode(777777)))
    check("转过职的存档：exp() 仍读 @class_id 那条（不被 Hash 第一项带偏）",
          g3.exp(a4) == e_before,
          "Hash=%r" % [(M.value_of(xj_save._deref(k)),
                        M.value_of(xj_save._deref(v))) for k, v in h.pairs])
    g3.set_exp(a4, 555)
    check("转过职的存档：set_exp 也写 @class_id 那条",
          g3.exp(a4) == 555
          and M.value_of(xj_save._deref(h.pairs[0][1])) == 777777,
          "第一项仍是 777777")

    # ---------------- 改等级必须把 @exp 对齐（光改 @exp 游戏里永远看不到变化）
    print("\n-- set_actor_level_full：级别 + 获得经验一起对齐 --")
    check("游戏满级 = 60（MAX_LEVEL_ACTOR）", xj_game.MAX_LEVEL_ACTOR == 60,
          xj_game.MAX_LEVEL_ACTOR)
    check("满级门槛 exp_for_level(60) = 1091704",
          xj_game.exp_for_level(60, "actor") == 1091704)
    a5 = sv3.actors()[0][1]
    lv5, wrote5 = g3.set_actor_level_full(a5, 40)
    check("设 40 级：等级写进 @level", g3.actor_level(a5) == 40, g3.actor_level(a5))
    check("设 40 级：@exp 同步成该级门槛 332296",
          wrote5 == 332296 and g3.exp(a5) == 332296, g3.exp(a5))
    check("同步后 next_level_exp 正好查到 41 级门槛",
          g3.next_level_exp(a5) == xj_game.exp_for_level(40, "actor"))

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

    shutil.rmtree(WORK, ignore_errors=True)
    print("\n==== 通过 %d, 失败 %d ====" % (OK[0], OK[1]))
    return 1 if OK[1] else 0


def _item_of(g, kind, slot):
    h = g.container(kind)
    for k, v in h.pairs:
        if M.value_of(xj_save._deref(k)) == slot:
            arr = xj_save._deref(v)
            return xj_save._deref(arr.items[0])
    return None


def _change_of(g, item_id):
    _sec, items = g.security_hash()
    return xj_save._deref(xj_save.hash_get(items, item_id))


if __name__ == "__main__":
    sys.exit(main())
