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
    check("体检能标出超限项", any(r[3] for r in rep),
          "、".join(r[0] for r in rep if r[3])[:60] or "（没有超限项）")

    # 故意越界：存银拉满到上限之上
    sv.set_gold(xj_game.MAX_GOLD + 1)
    sv.set_gold(xj_game.MAX_GOLD + 1)
    rep2 = g.anti_cheat_report()
    check("存银超限能被检出",
          any(r[0] == "存银" and r[3] for r in rep2))
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
    check("修复后存银回到上限内", sv.gold() <= xj_game.MAX_GOLD, sv.gold())
    check("作弊标记被清掉",
          M.value_of(xj_save._deref(
              xj_save.ivar(sv.section("system"), "@cheated"))) is False)

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
    baks = [f for f in os.listdir(WORK) if ".bak." in f]
    check("原文件留了备份", len(baks) >= 1, "%r" % baks[:2])

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
