# -*- coding: utf-8 -*-
"""GUI 实操测试：真的建窗口、加载存档、点"应用/保存"，再重新打开验证。

* 全程在**副本**上操作（原存档一个字节都不动）；
* 所有弹窗都被替换成"记录"，测试不会卡在模态对话框上；
* 每步即时写日志，卡住也能看到卡在哪一步。

用法：python tests/test_gui_quick.py
日志：tools/_gui_quick.txt
"""
import os
import shutil
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))

import marshal_ruby   # noqa: E402
import save      # noqa: E402
import datatables  # noqa: E402

LOG = os.path.join(ROOT, "tools", "_gui_quick.txt")
WORK = os.path.join(ROOT, "tools", "_gui")
OK = [0, 0]
T0 = time.time()


def say(msg):
    """即时落盘 + 打屏，卡住也能知道卡在哪一步。"""
    line = "[%6.2fs] %s" % (time.time() - T0, msg)
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass
    try:
        print(line)
    except Exception:
        pass


def check(name, cond, extra=""):
    OK[0 if cond else 1] += 1
    say("%-46s %s %s" % (name, "[OK]" if cond else "[NG]", extra))


class FakeDialog(object):
    """顶掉 EditDialog：不弹模态、不进 mainloop，直接把"用户输入"摆在 result 上。

    注意 va_edit() 里还会调 root.wait_window(dlg)，所以测试里得把
    root.wait_window 也顶掉（Tk 的 wait_window 拿的是 dlg._w，假对象没有）。
    """

    value = 314

    def __init__(self, master, cur, ntype):
        self.cur = cur
        self.ntype = ntype
        self.result = self.value


class FakeNoteDialog(object):
    """顶掉 NoteDialog：不弹窗，直接给 result（编辑备注、备份后填备注都用它）。"""

    def __init__(self, master, cur="", **kw):
        self.cur = cur
        self.result = "测试备注"


def kill_timers(root):
    try:
        for aid in root.tk.call("after", "info"):
            try:
                root.after_cancel(aid)
            except Exception:
                pass
    except Exception:
        pass


def walk(w, out=None):
    """递归收集全部子孙控件（找按钮用）。"""
    out = [] if out is None else out
    for c in w.winfo_children():
        out.append(c)
        walk(c, out)
    return out


def main():
    open(LOG, "w", encoding="utf-8").close()
    import faulthandler
    faulthandler.enable()
    # ⚠ 看门狗：本组空载约 36s；游戏（Game.exe）在跑时磁盘被占，实测会超过 60s
    #   → 60s 会假红（2026-09-27 连吃两次）。180s 仍然能抓住真的死循环/挂死。
    faulthandler.dump_traceback_later(180, exit=True)
    try:
        import tkinter as tk
        # 探针 root 直接留用：先建一个再销毁会让 ttk 抛
        # "can't invoke event command: application has been destroyed"
        root = tk.Tk()
        root.withdraw()
        root.update()
    except Exception as e:
        say("没有图形环境，跳过：%s" % e)
        return 0

    import backup
    import datatables
    import paths
    import game
    import save
    from tables import sect
    import huaji2_save_editor

    # 把弹窗换成"记录"，避免模态框把测试挂住
    dialogs = []
    huaji2_save_editor.messagebox = type("MB", (), {
        "showinfo": staticmethod(lambda *a, **k: dialogs.append(("info", a))),
        "showerror": staticmethod(lambda *a, **k: dialogs.append(("error", a))),
        "showwarning": staticmethod(lambda *a, **k: dialogs.append(("warn", a))),
    })
    say("已把弹窗替换为记录模式")

    os.makedirs(WORK, exist_ok=True)
    real = paths.save_path()
    if not os.path.exists(real):
        say("找不到存档 %s，跳过" % real)
        return 0
    copy = os.path.join(WORK, "gui_copy.rvdata2")
    shutil.copyfile(real, copy)
    say("存档副本 = %s" % copy)

    last_txt = huaji2_save_editor.LAST_TXT
    backup_last = None
    if os.path.exists(last_txt):
        backup_last = open(last_txt, encoding="utf-8").read()

    app = None
    try:
        say("创建窗口…")
        app = huaji2_save_editor.App(root, save_path=None)
        kill_timers(root)
        root.update()
        say("窗口创建完成（%d 个页签）" % app.nb.index("end"))
        check("10 个页签都建好（开关/变量页已移到快捷修改）", app.nb.index("end") == 10,
              "%d 个：%s" % (app.nb.index("end"),
                              [app.nb.tab(i, "text") for i in range(app.nb.index("end"))]))

        say("加载存档副本…")
        app.load(copy, quiet=True)
        root.update()
        say("加载完成 doc=%s sv=%s" % (app.doc is not None, app.sv is not None))
        check("加载存档成功", app.doc is not None)
        check("拿到 SaveDoc", app.sv is not None,
              "校验标签=%s" % app.var_lock.get())
        if app.sv is None:
            raise SystemExit(1)
        gold0 = app.sv.gold()
        nsw, nva = app.sv.counts()
        say("原金钱=%r 开关=%d 变量=%d" % (gold0, nsw, nva))

        # ---------------- 概览 / 快捷修改
        check("金钱显示在界面上", app.var_gold.get() == str(gold0),
              "var_gold=%r" % app.var_gold.get())
        check("步数显示在界面上", app.var_steps.get().strip() != "",
              "步数=%s" % app.var_steps.get())
        check("防作弊校验提示正常", "正常" in app.var_lock.get(),
              app.var_lock.get())
        check("概览文本已填充", "金钱" in app.txt_info.get("1.0", "end"))
        check("概览页有作弊/超限提示条", "作弊" in app.var_cheat.get()
              or "超限" in app.var_cheat.get() or "正常" in app.var_cheat.get(),
              app.var_cheat.get()[:60])
        # 手动把 @cheated 打回“作弊”状态（模拟游戏判过作弊的存档），
        # 验证「载入就提醒 + 顺手清掉」这条链路真的通。
        # ⚠ V2.201（内测版）没有 @cheated 节点 —— 原来这里直接 set_value(None)
        # 会 AttributeError，让**整组**早退（后面召唤兽等段全跑不到）。加守卫跳过。
        sysnode = app.sv.section("system")
        ch_node = save._deref(save.ivar(sysnode, "@cheated"))
        if ch_node is None:
            print("  （内测版没有 @cheated 节点，跳过「作弊标记」这段）")
        else:
            app.doc.set_value(ch_node, 134700)
            n_over = app.guard_check()
            check("体检能把作弊标记报出来", n_over >= 1,
                  app.var_cheat.get()[:60])
            warned = app.warn_cheat_after_load()
            root.update()
            ch_now = save.M.value_of(save._deref(
                save.ivar(app.sv.section("system"), "@cheated")))
            check("载入带作弊标记的存档会提醒并顺手清掉",
                  warned is True and ch_now is False,
                  "warned=%r 清完=%r" % (warned, ch_now))

        say("改金钱…")
        app.var_gold.set("7654321")
        app.apply_quick()
        root.update()
        check("界面改金钱 @value 生效", app.sv.gold() == 7654321,
              "%r" % app.sv.gold())
        check("界面改金钱 校验同步", app.sv.check_locks() == [])
        check("界面改金钱 游戏记账同步", app.g.security_gold() == 7654321,
              "%r" % app.g.security_gold())
        check("标签同步刷新", app.var_gold.get() == "7654321")
        check("已标记为脏（保存按钮会亮）", app.doc.dirty is True)

        # 超过 MAX_GOLD → 自动压到 SAFE_GOLD（上限的 5/6），记账同步
        # ⚠ 上限**取 game 的常量**，别写死尝鲜版的 30,000,000/25,000,000
        #   （内测版 MAX_GOLD = 9,999,999,999，硬编码会让这条恒红）。
        say("改金钱超过上限…")
        app.var_gold.set(str(game.MAX_GOLD * 2))
        app.apply_quick()
        root.update()
        check("金钱超限自动压到 SAFE_GOLD（上限 5/6）", app.sv.gold() == game.SAFE_GOLD,
              app.sv.gold())
        check("输入框显示钳制后的值", app.var_gold.get() == str(game.SAFE_GOLD))
        check("钳制后 Lock+记账仍同步",
              app.sv.check_locks() == [] and app.g.security_gold() == game.SAFE_GOLD)
        app.var_gold.set("7654321")
        app.apply_quick()
        root.update()

        # ---- 祈福池储备（2026-10-04 从「没用的控件」加回，补了说明）
        say("祈福池储备…")
        check("概览有 4 个祈福池储备输入",
              sorted(app.var_bless) == ["actor_hp_pool", "actor_mp_pool",
                                        "baby_hp_pool", "baby_mp_pool"],
              "%r" % sorted(app.var_bless))
        pool = dict((k, v) for k, _cn, v in app.g.blessing_rows())
        check("祈福池 4 个框回填的是语义层的值",
              all(app.var_bless[k].get() == str(pool[k]) for k in app.var_bless),
              "%r" % (pool,))
        app.var_bless["actor_hp_pool"].set("12345")
        app.apply_quick()
        root.update()
        pool2 = dict((k, v) for k, _cn, v in app.g.blessing_rows())
        check("祈福池储备改完能写进存档",
              pool2["actor_hp_pool"] == 12345 and app.sv.check_locks() == [],
              "%r" % (pool2["actor_hp_pool"],))
        app.var_bless["actor_hp_pool"].set(str(pool["actor_hp_pool"]))
        app.apply_quick()
        root.update()

        # ---------------- 角色 / 属性
        kids = app.tv_actor.get_children()
        check("角色列表已填充", len(kids) >= 1, "角色数=%d" % len(kids))
        check("角色列表最前面新增「序」列，门派列还在名字后面",
              list(app.tv_actor["columns"])[:2] == ["no", "id"]
              and list(app.tv_actor["columns"])[3] == "sect"
              and app.tv_actor.heading("no", "text") == "序"
              and app.tv_actor.heading("sect", "text") == "门派",
              "%r" % (app.tv_actor["columns"],))
        check("角色列表的序号是 1 起、门派列都有值",
              [int(app.tv_actor.item(k, "values")[0]) for k in kids]
              == list(range(1, len(kids) + 1))
              and all(app.tv_actor.item(k, "values")[3] for k in kids),
              "%r" % [app.tv_actor.item(k, "values")[:4] for k in kids])
        if kids:
            say("改角色…")
            app.tv_actor.selection_set(kids[0])
            app.load_actor()
            root.update()
            aid, a = app.sv.actors()[0]
            # ⚠ 2026-09-20：等级行改成**只读展示**（川要求：看得见、但不可改）。
            # 可写的「@level」不再存在，改成只读的「#level」。
            check("角色页的等级是只读行（#level，不是可写的 @level）",
                  "@level" not in app.actor_vars
                  and "#level" in app.actor_vars,
                  "%r" % list(app.actor_vars))
            check("只读等级行读得出存档里的等级",
                  app.actor_vars["#level"].get()
                  == str(app.sv.actor_field(a, "@level")),
                  "%r vs %r" % (app.actor_vars["#level"].get(),
                                app.sv.actor_field(a, "@level")))
            hp0 = app.sv.actor_field(a, "@hp")
            try:
                hp_new = str(int(hp0) + 100)
            except (TypeError, ValueError):
                hp_new = "100"
            app.actor_vars["@hp"].set(hp_new)
            k0 = save.SaveDoc.ATTR_FIELDS[0]
            av0 = dict(app.sv.attr_items(a)).get(k0)
            if isinstance(av0, int):
                app.attr_vars[k0].set(str(av0 + 10))
            app.apply_actor()
            root.update()
            check("界面改角色气血生效",
                  str(app.sv.actor_field(a, "@hp")) == hp_new,
                  "%s -> %s" % (hp0, app.sv.actor_field(a, "@hp")))
            if isinstance(av0, int):
                check("界面改中文属性生效",
                      dict(app.sv.attr_items(a)).get(k0) == av0 + 10,
                      "%s: %s -> %s" % (k0, av0, av0 + 10))
            check("角色详情已填充", "名字" in app.txt_actor.get("1.0", "end"))

            say("用「属性全 +10」预设…")
            app.tv_actor.selection_set(kids[0])
            app.load_actor()
            app.actor_preset("attr")
            root.update()
            check("预设按钮生效",
                  dict(app.sv.attr_items(a)).get(k0) == av0 + 20,
                  "%s = %s" % (k0, dict(app.sv.attr_items(a)).get(k0)))

            # 2026-09-20：新增「重置潜力/属性」= 洗点（游戏里「拜师」那一下，
            # 脚本 Game_Actor_Attr#reset_point：五维=20+等级-1、潜能=等级*5）
            say("用「重置潜力/属性」预设（洗点）…")
            lv_a = app.g.actor_level(a)
            app.actor_preset("reset_attr")
            root.update()
            _f = [dict(app.sv.attr_items(a)).get(k)
                  for k in ("@体质", "@法力", "@力量", "@耐力", "@敏捷")]
            check("洗点后五维全 = 20+等级-1",
                  _f == [20 + lv_a - 1] * 5, "%r（等级 %s）" % (_f, lv_a))
            check("洗点后潜能 = 等级*5",
                  dict(app.sv.attr_items(a)).get("@潜能") == lv_a * 5,
                  "%r vs %r" % (dict(app.sv.attr_items(a)).get("@潜能"),
                                lv_a * 5))

            # ---- 角色技能可视化编辑（2026-09-20 新增）
            # 2026-10-04 改版：主界面技能区 = 已学一览 + 忘掉选中 + 技能管理…
            #   学 / 忘 / 全选 / 反选 全在技能管理器窗口里。
            say("角色技能：一览 + 技能管理器…")
            app.tv_actor.selection_set(kids[0])
            app.load_actor()
            root.update()
            check("角色技能一览建得起来（序 / id / 名字三列）",
                  tuple(app.tv_actor_skills["columns"]) == ("no", "id", "name"),
                  "%r" % (app.tv_actor_skills["columns"],))
            rows_a = [int(app.tv_actor_skills.item(r, "values")[1])
                      for r in app.tv_actor_skills.get_children()]
            check("角色技能一览 = 存档里的 @skills",
                  rows_a == app.g.actor_skills(a), "%r" % (rows_a,))
            check("一览只剩已学的那一份（「全部技能」下拉已删）",
                  set(app.skp_actor.choices) == set(app.g.actor_skills(a)),
                  "%d 个" % len(app.skp_actor.choices))
            _kids_sk = app.tv_actor_skills.get_children()
            if _kids_sk:
                app.tv_actor_skills.selection_set(_kids_sk[0])
                app.skp_actor.show_desc()
            _askd = app.txt_actor_skill_desc.get("1.0", "end").strip()
            check("选中一览某行后说明框有内容", len(_askd) > 5, _askd[:46])
            base_sk = list(app.g.actor_skills(a))
            names_a = app.skp_actor.names()
            fresh = [i for i in sorted(names_a) if i not in base_sk]
            check("有没学过的技能可以拿来测", len(fresh) >= 1, len(fresh))
            if fresh:
                wa = app.open_skill_manager("actor")
                root.update()
                check("技能管理器窗口开得起来",
                      wa is not None and wa.win.winfo_exists())
                check("管理器默认列出全部有名字的技能（分段行除外）",
                      len(wa.tv.get_children())
                      == len([i for i in names_a if names_a[i]
                              and not datatables.section_of(names_a[i])]),
                      "%d 个" % len(wa.tv.get_children()))
                _ov = [str(v) for v in wa.cb_own.cget("values")]
                check("归属下拉列出了表里的分段名 + 3 个固定项",
                      len(_ov) > 8 and "全部" in _ov
                      and "门派技能" in _ov and "无归属" in _ov,
                      "%r" % (_ov[:6],))
                # `#id` 才是精确 id；纯数字会命中"名字/描述里含这串数字"的一堆
                # （id 1 这种几乎命中半张表），只验"至少含 id 本身"。
                wa.var_kw.set("#%d" % fresh[0])
                wa.refill()
                _v = [wa.sid_of(i) for i in wa.tv.get_children()]
                check("搜索「#id」= 精确技能 id", _v == [fresh[0]],
                      "%r" % (_v[:4],))
                wa.var_kw.set(str(fresh[0]))
                wa.refill()
                check("纯数字搜索至少包含 id 本身",
                      fresh[0] in [wa.sid_of(i) for i in wa.tv.get_children()])
                wa.var_kw.set("#%d" % fresh[0])
                wa.refill()
                wa.select("all")
                check("「全选」只作用于当前筛选结果（1 条）",
                      wa.sel_sids() == [fresh[0]], wa.var_sel.get())
                wa.do_learn()
                root.update()
                check("管理器「学会选中」生效",
                      fresh[0] in app.g.actor_skills(a),
                      app.g.actor_skills(a))
                now_a = [app.tv_actor_skills.item(r, "values")[1]
                         for r in app.tv_actor_skills.get_children()]
                check("学会后主界面一览跟着刷新", str(fresh[0]) in now_a,
                      "%r" % (now_a[:4],))
                check("角色技能不受召唤兽那 12 个上限限制",
                      len(app.g.actor_skills(a)) == len(base_sk) + 1,
                      "%d -> %d" % (len(base_sk), len(app.g.actor_skills(a))))
                wa.select("none")
                check("「全不选」清空选中", not wa.sel_sids(),
                      wa.var_sel.get())
                wa.select("all")
                wa.select("invert")
                check("「反选」= 全选变全不选", not wa.sel_sids(),
                      wa.var_sel.get())
                wa.select("invert")
                check("再反选一次回到全选", len(wa.sel_sids()) == len(_v),
                      wa.var_sel.get())
                wa.do_forget()
                root.update()
                check("管理器「忘掉选中」生效",
                      fresh[0] not in app.g.actor_skills(a),
                      app.g.actor_skills(a))
                wa.close()
                root.update()
                check("关掉管理器后 app 不再引用它", app._skill_win is None)
                # 主界面「忘掉选中」：多选一次忘一批
                app.g.actor_learn_many(a, fresh[:2])
                app.load_actor()
                root.update()
                app.tv_actor_skills.selection_set(["sk%d" % s
                                                   for s in fresh[:2]])
                _pick = app.skp_actor.sel_ids()
                app.actor_skill_del()
                root.update()
                check("主界面「忘掉选中」一次忘掉多选的一批",
                      len(_pick) == 2
                      and all(s not in app.g.actor_skills(a) for s in _pick),
                      "%r -> %r" % (_pick, app.g.actor_skills(a)))
            n_before = len(app.g.actor_skills(a))
            app.actor_skill_clear()          # 测试里 confirm 默认放行
            root.update()
            check("界面「清空」生效", app.g.actor_skills(a) == [],
                  "%d -> %r" % (n_before, app.g.actor_skills(a)))
            check("清空后技能一览也空了",
                  not app.tv_actor_skills.get_children(),
                  "%r" % (app.tv_actor_skills.get_children(),))
            check("改技能会标记成结构性改动（保存走整档重写）",
                  app.doc.structural is True)
            # 还原，后面还要拿这个角色验别的
            app.g.actor_set_skills(a, base_sk)
            app.load_actor()
            root.update()
            check("技能写回原样", app.g.actor_skills(a) == sorted(set(base_sk)),
                  app.g.actor_skills(a))

            # ---- 门派下拉（2026-09-20；门派不是 Data 表，是脚本 $sects）
            say("角色页：门派下拉 + 门派技能清单…")
            check("角色页有「门派」下拉（cb_actor_sect）",
                  getattr(app, "cb_actor_sect", None) is not None)
            check("门派下拉搬到了左栏「门派技能」里",
                  str(app.cb_actor_sect).startswith(str(app.lf_learn)),
                  "%r" % (str(app.cb_actor_sect),))
            check("召唤兽页**没有**门派下拉（召唤兽没门派）",
                  getattr(app, "cb_baby_sect", None) is None)
            vals = list(app.cb_actor_sect["values"])
            check("门派下拉 = 15 项（无门派 + 14 门派；「全部技能」仍然没有）",
                  len(vals) == 15
                  and "全部技能" not in vals and "无门派" in vals
                  and "凌波城" in vals and "九黎城" in vals,
                  "%r" % (vals,))
            check("门派下拉里的名字都来自 sect（含 0 无门派）",
                  set(vals) == set(sect.sect_name(s) for s in sect.SECTS),
                  "%r" % (vals,))

            sid_a = app.g.actor_sect_id(a)
            sname_a = app.g.actor_sect_name(a)
            # ⚠ 这里原来还算了个 `want`（本门派技能）只为下面当搜索关键词 —— 已删：
            #   第一个角色可能无门派 → 空集 → IndexError（见下面搜索框那段）。
            # ⚠ 川 2026-09-20 改：门派下拉从右边技能区搬到左栏「门派技能」
            #   （两处都按门派筛等于重复）。右边一览恢复成「全部技能」。
            # 右下一览 = 这个角色**已学**的技能（和门派下拉无关）
            _have_a = set(app.g.actor_skills(a))
            app.var_actor_sect.set(sname_a)
            app.skp_actor.fill()
            check("右下一览 = 已学技能（不受门派下拉影响）",
                  set(app.skp_actor.choices) == _have_a,
                  "%d 个" % len(app.skp_actor.choices))
            app.var_actor_sect.set("摸鱼门")
            app.skp_actor.fill()
            check("认不出的门派名也不影响右下一览",
                  set(app.skp_actor.choices) == _have_a,
                  "%d 个" % len(app.skp_actor.choices))
            # 左栏「门派技能」清单跟着门派下拉走
            app.var_actor_sect.set(sname_a)
            app.rebuild_learn_grid()
            root.update()
            check("左栏「门派技能」清单 = 该门派的技能",
                  sorted(app._learn_sids)
                  == sorted(sect.sect_skill_ids(sid_a)),
                  "%r" % (app._learn_sids,))
            check("门派技能清单里每个技能都带悬停介绍",
                  len([w for w in app.learn_grid.winfo_children()
                       if w.winfo_class() == "TCheckbutton"
                       and w.bind("<Enter>")]) == len(app._learn_sids),
                  "%d 个框" % len(app.learn_grid.winfo_children()))
            # 没选门派（空串）→ 列不出清单，只给提示
            app.var_actor_sect.set("")
            app.rebuild_learn_grid()
            root.update()
            check("没选门派时清单清空并给提示",
                  app._learn_sids == [] and "门派" in app.var_learn_note.get(),
                  app.var_learn_note.get())
            app.var_actor_sect.set(sname_a)
            app.rebuild_learn_grid()
            root.update()
            # 「一键学习」：一个都不勾 = 学满当前门派
            _before = set(app.g.actor_skills(a))
            if set(app._learn_sids) - _before:
                app.actor_learn_checked()
                root.update()
                check("「一键学习」不勾任何框 = 学满当前门派",
                      set(app._learn_sids) <= set(app.g.actor_skills(a)),
                      "%r" % (app.g.actor_skills(a),))
                app.g.actor_set_skills(a, sorted(_before))   # 还原，后面还要用
                app.load_actor()
                root.update()
            # 技能一览的搜索框仍然独立可用
            # ⚠ 别拿「本门派技能」当关键词：真档里第一个角色可能**没有门派**
            #   （2026-09-27 真档就是：李修远 @sect_id=0）→ `want` 是空集，
            #   `sorted(want)[0]` 直接 IndexError（测试自己脆，不是功能坏了）。
            # 搜索框只筛「已学」那一份（全部技能的搜索在管理器里）
            _have_a = sorted(app.g.actor_skills(a))
            if _have_a:
                _kw = (names_a.get(_have_a[0], "") or str(_have_a[0]))[:1]
                app.var_actor_skill_search.set(" ")
                app.skp_actor.fill()
                _n_all = len(app.skp_actor.choices)
                app.var_actor_skill_search.set(_kw)
                app.skp_actor.fill()
                _c = app.skp_actor.choices
                check("技能一览的搜索框能用（只筛已学那一份）",
                      set(_c) <= set(_have_a) and len(_c) <= _n_all,
                      "%r（%d/%d）" % (_c[:3], len(_c), _n_all))
                app.var_actor_skill_search.set("")
                app.skp_actor.fill()
                check("清掉关键词后恢复全部已学",
                      set(app.skp_actor.choices) == set(_have_a),
                      "%d 个" % len(app.skp_actor.choices))

            # 换角色 → 门派下拉自动跟着切
            if len(kids) >= 2:
                app.tv_actor.selection_set(kids[1])
                app.load_actor()
                root.update()
                oth = app.current_actor()
                if app.g.sect_skills(oth):
                    check("换角色后门派下拉自动切到该角色的门派",
                          app.var_actor_sect.get() == app.g.actor_sect_name(oth),
                          "%r" % (app.var_actor_sect.get(),))
                app.tv_actor.selection_set(kids[0])
                app.load_actor()
                root.update()
                # ⚠ 2026-09-27：无门派角色现在也同步成「无门派」（下拉里有了这一项），
                #   所以期望值是**门派名**本身 —— 原来写 `sect_skills(a)` 非空才期望
                #   门派名、否则期望空串，那是下拉还没有「无门派」时的老约定。
                if sname_a in huaji2_save_editor.sect_choice_labels():
                    check("切回原角色后门派又跟着回来（无门派也会同步成「无门派」）",
                          app.var_actor_sect.get() == sname_a,
                          "%r" % (app.var_actor_sect.get(),))
            # 属性概览里看得见门派
            _ov = app.txt_actor.get("1.0", "end")
            check("属性概览里写了门派", "门派：" in _ov and sname_a in _ov,
                  [l for l in _ov.splitlines() if "门派" in l][:1])

        # ---------------- 背包 / 物品
        check("背包页 20 格都建好了", len(app.tv_pack.get_children()) == 20,
              "%d 行" % len(app.tv_pack.get_children()))
        filled = [r for r in app.tv_pack.get_children()
                  if app.tv_pack.item(r, "values")[2] != "（空）"]
        check("背包里看到东西了", len(filled) >= 1, "%d 格有货" % len(filled))
        # ---- 背包格子搜索（2026-10-04 川：「背包格子同理」）
        if filled:
            _pk_nm = app.tv_pack.item(filled[0], "values")[3]
            app.var_pack_kw.set(_pk_nm)
            app.fill_party()
            root.update()
            _pk_hit = list(app.tv_pack.get_children())
            _pk_ok = all(any(_pk_nm in str(v)
                             for v in app.tv_pack.item(r, "values"))
                         for r in _pk_hit)
            check("背包格子搜索：只列命中的格子、不再列空格子",
                  bool(_pk_hit) and len(_pk_hit) <= len(filled) and _pk_ok,
                  "搜「%s」→ %d 行（原来 %d 格有货）"
                  % (_pk_nm, len(_pk_hit), len(filled)))
            app.var_pack_kw.set("绝无此物XYZ")
            app.fill_party()
            root.update()
            check("背包格子搜索：搜不到就一行不列",
                  len(app.tv_pack.get_children()) == 0,
                  "%d 行" % len(app.tv_pack.get_children()))
            app.pack_kw_clear()
            root.update()
            check("清空背包搜索 → 20 格（含空格子）都回来",
                  len(app.tv_pack.get_children()) == 20,
                  "%d 行" % len(app.tv_pack.get_children()))
        check("队伍信息已填充", "金钱" in app.var_party.get(),
              app.var_party.get())
        if filled:
            say("改背包数量…")
            slot = int(app.tv_pack.item(filled[0], "values")[0])
            iid = "s%d" % slot
            app.tv_pack.selection_set(iid)
            old = int(app.tv_pack.item(filled[0], "values")[4])
            app.var_bag_cnt.set(str(old + 2))
            app.bag_set_count()
            root.update()
            now = dict((r[0], r[5]) for r in app.g.bag("Items"))
            check("界面改物品数量生效", now.get(slot) == old + 2,
                  "%d -> %s" % (old, now.get(slot)))
            # 只看刚改的这件：存档里本来就可能有别的不一致（游戏自己用道具时
            # 不一定会把 Change 一起更新），那一项不归这次操作管。
            slot_ids = [r[3] for r in app.g.bag("Items") if r[0] == slot]
            row0 = [r for r in app.g.security_rows()
                    if slot_ids and r[0] == slot_ids[0]]
            check("改数量后计数校验同步",
                  not row0 or row0[0][2] == row0[0][3],
                  "%r" % (row0[:1],))
        say("往空格加一件物品…")
        free = app.g.empty_slots("Items")[0]
        # 空格可能在别的翻页上：先切到那一页，列里才有这个格子
        if free // 20 != app.var_bag_page.get():
            app.var_bag_page.set(free // 20)
            app.fill_party()
            root.update()
        app.var_bag_id.set("1")
        app.var_bag_cnt.set("3")
        app.tv_pack.selection_set("s%d" % free)
        app.bag_add()
        root.update()
        got = [r for r in app.g.bag("Items") if r[0] == free]
        check("界面加物品生效", len(got) == 1 and got[0][3] == 1 and got[0][5] == 3,
              "%r" % (got[0] if got else None,))
        app.tv_pack.selection_set("s%d" % free)
        app.bag_clear()
        root.update()
        check("界面清空格子生效",
              not [r for r in app.g.bag("Items") if r[0] == free])
        if app.var_bag_page.get() != 0:      # 切回第 1 页，后面的用例按第 1 页写的
            app.var_bag_page.set(0)
            app.fill_party()
            root.update()

        # ---------------- v0.5：模板列表 / 写进格子 / 批量 / 体检
        check("模板列表已填充（画迹1 那种右栏）",
              len(app.tv_tpl.get_children()) >= 5,
              "%d 个模板" % len(app.tv_tpl.get_children()))
        _tn = [app.tv_tpl.item(i, "values")
               for i in app.tv_tpl.get_children()]
        check("模板列表滤掉了空名行与分段行（不再有 `#49` 这种）",
              all(nm.strip() and not datatables.section_of(nm)
                  for _i, nm, *_ in _tn),
              "%r" % ([r[1] for r in _tn if not r[1].strip()][:3],))
        check("模板列表多了一列「类别」（`===药品===` 那一层）",
              all(len(r) == 3 for r in _tn) and any(r[2] for r in _tn),
              "%r" % (_tn[0],))
        _tids = [int(r[0]) for r in _tn]
        check("模板 id 全是真物品（空占位 1/49/50 已不在）",
              1 not in _tids and 49 not in _tids and 50 not in _tids,
              "%d 个" % len(_tids))
        app.var_tpl_kw.set("草")
        app.fill_templates()
        root.update()
        n_kw = len(app.tv_tpl.get_children())
        names = [app.tv_tpl.item(i, "values")[1] for i in app.tv_tpl.get_children()]
        hit_kw = app.g.templates("Items", keyword="草")
        check("模板搜索能过滤",
              0 < n_kw < 300 and len(hit_kw) == n_kw
              and all(("草" in nm or "草" in de) for _i, nm, de in hit_kw),
              "%d 个：%s" % (n_kw, "、".join(names[:4])))
        app.var_tpl_kw.set("")
        app.fill_templates()
        root.update()
        say("把模板写进空格子…")
        free2 = app.g.empty_slots("Items")[0]
        # ⚠ 和上面「往空格加一件物品」同一个坑：`empty_slots()` 是**全局**槽号，
        #   而 `tv_pack` 只有当前页那 20 格。第 1 页装满时第一个空格会落到第 2 页，
        #   不切页就 `selection_set("s28")` → TclError: Item s28 not found
        #   （2026-09-20 真档第 1 页刚好 20/20 满，暴露出这处漏切页）。
        if free2 // 20 != app.var_bag_page.get():
            app.var_bag_page.set(free2 // 20)
            app.fill_party()
            root.update()
        tid = int(app.tv_tpl.item(app.tv_tpl.get_children()[0], "values")[0])
        app.tv_tpl.selection_set("t%d" % tid)
        app.var_bag_cnt.set("5")
        app.tv_pack.selection_set("s%d" % free2)
        app.bag_use_template()
        root.update()
        got2 = app.g.slot_info("Items", free2)
        check("双击模板写进格子生效", got2 == (tid, 5), "%r（模板 id=%d）"
              % (got2, tid))
        app.tv_pack.selection_set("s%d" % free2)
        app.bag_pick()
        root.update()
        check("选中格子会把 id/数量填到输入框",
              app.var_bag_id.get() == str(tid) and app.var_bag_cnt.get() == "5",
              "%s / %s" % (app.var_bag_id.get(), app.var_bag_cnt.get()))
        # ⚠ free2 可能落在别的翻页上（上面为它切过去了）→ 切回第 1 页：
        #   下面的「批量改本页」按第 1 页写（`set_all_counts(..., 0)`），
        #   不切回来的话改的是没显示的那一页，断言必然失败。
        if app.var_bag_page.get() != 0:
            app.var_bag_page.set(0)
            app.fill_party()
            root.update()
        n_all = app.g.set_all_counts("Items", 9, 0)
        app.fill_party()
        root.update()
        check("批量改本页数量生效",
              all(int(app.tv_pack.item(r, "values")[4] or 9) == 9
                  for r in app.tv_pack.get_children()
                  if app.tv_pack.item(r, "values")[2] != "（空）"),
              "改了 %d 格" % n_all)
        bad_before = app.g.pack_report()
        done_fix = app.g.pack_fix(bad_before)
        root.update()
        check("背包体检 + 一键修复能跑通",
              not app.g.pack_report(),
              "修了 %d 项，原来 %d 项" % (len(done_fix), len(bad_before)))
        check("修完计数校验仍对齐",
              all(r[2] == r[3] for r in app.g.security_rows()),
              "%r" % [r for r in app.g.security_rows() if r[2] != r[3]][:2])

        # ---------------- v0.5：机器码
        say("读机器码…")
        app.machine_show()
        root.update()
        now_m, err_m, ids_m, ok_m = app.g.machine_status()
        check("界面显示机器码", "机器码" in app.var_machine.get(),
              app.var_machine.get().replace("\n", " | ")[:90])
        check("本机机器码已在存档记录里", ok_m, "本机 %s / 存档 %s"
              % (now_m, ids_m))
        app.machine_fill_local()
        root.update()
        check("「用本机机器码填上」写进输入框",
              app.var_machine_id.get() == str(now_m), app.var_machine_id.get())
        app.var_machine_id.set("123456789")
        app.machine_add()
        root.update()
        check("「加入存档」生效", "123456789" in app.g.machine_ids(),
              "、".join(app.g.machine_ids()))
        app.var_machine_id.set("123456789")
        app.machine_set()
        root.update()
        check("「直接替换」只留一个", app.g.machine_ids() == ["123456789"],
              "%r" % (app.g.machine_ids(),))
        app.var_machine_id.set(str(now_m))
        app.machine_set()
        root.update()
        check("机器码能改回本机", app.g.machine_ids() == [str(now_m)],
              "%r" % (app.g.machine_ids(),))
        say("机器码页（照画迹1：读本机 / 读存档 / 改）…")
        check("机器码页建得起来", hasattr(app, "tab_machine")
              and hasattr(app, "txt_machine"),
              app.nb.tab(app.tab_machine, "text"))
        app.machine_fill_local()
        root.update()
        check("「读取本机机器码」能用", app.var_machine_id.get() == str(now_m),
              app.var_machine_id.get())
        app.machine_fill_saved()
        root.update()
        check("「读存档里第一个」能用",
              app.var_machine_id.get() in app.g.machine_ids(),
              "%s / %s" % (app.var_machine_id.get(), app.g.machine_ids()))
        app.var_machine_id.set(str(now_m))
        app.machine_use_local()
        root.update()
        check("「用本机机器码替换」后本机在档",
              app.g.machine_ids() == [str(now_m)],
              "%r" % (app.g.machine_ids(),))
        check("操作记录里有东西", "读取本机" in app.txt_machine.get("1.0", "end"),
              app.txt_machine.get("1.0", "end").splitlines()[:1])
        say("背包“内容”列 + 重抽内容…")
        egg_slot = None
        for r in app.g.bag("Items"):
            need, _nm = app.g.item_needs_payload("Items", r[3])
            if need and "孵化蛋" in (r[4] or ""):
                egg_slot = r[0]
                break
        if egg_slot is None:
            egg_slot = app.g.empty_slots("Items")[0]
            app.g.add_item("Items", egg_slot, 110, 1, clone_like=False)
            app.mark_dirty()
        app.var_bag_page.set(egg_slot // 20)
        app.fill_party()
        root.update()
        app.tv_pack.selection_set("s%d" % egg_slot)     # 刷完再选（刷新会清选中）
        vals = app.tv_pack.item("s%d" % egg_slot, "values")
        check("背包出现“内容”列且蛋类有内容摘要",
              len(vals) == 6 and ("蛋→" in str(vals[5]) or vals[5] == ""),
              "%r" % (vals,))
        app.var_bag_kid.set("21")
        app.bag_reroll()
        root.update()
        _t, d = app.g.item_payload(app.g._item_node("Items", egg_slot))
        check("「重抽/指定内容」生效（指定 21）",
              d is not None and marshal_ruby.value_of(
                  save._deref(save.hash_get(d, "id"))) == 21,
              app.g.payload_summary(app.g._item_node("Items", egg_slot)))
        app.var_bag_kid.set("")

        # ---- 2026-10-07 川：抽选带范围、默认最大范围（元宵的成长＝0.02）------
        say("重抽管理：「数值」默认取上限…")
        _yx = [s for s in app.g.empty_slots("Items")
               if s != egg_slot][0]
        app.g.add_item("Items", _yx, 104, 1, clone_like=False)
        app.mark_dirty()
        app.var_bag_page.set(_yx // 20)
        app.fill_party()
        root.update()
        app.tv_pack.selection_set("s%d" % _yx)
        _w = app.open_payload_manager()
        root.update()
        check("背包里选中的元宵 → 重抽管理认得出「元宵」家族",
              _w is not None and "元宵" in _w.groups,
              "%r" % (list(_w.groups) if _w is not None else None,))
        if _w is not None and "元宵" in _w.groups:
            _w.fam = "元宵"
            _w._sync_fields()
            check("「元宵」家族能挑两个字段（资质 + 数值）",
                  len(_w.groups["元宵"]["fields"]) == 2,
                  "%r" % (_w.groups["元宵"]["fields"],))
            _w.var_field.set("涨哪项资质")
            _w.show_field()
            _go = [c for c in _w.tv.get_children()
                   if str(_w.tv.item(c, "values")[1]) == "成长"]
            if _go:
                _w.tv.selection_set(_go[0])
                root.update()
                _w.on_cand()               # <<TreeviewSelect>> 是排队的，直接调保险
            check("挑「成长」→「数值」默认＝该档上限 0.02",
                  abs(float(_w.picked["元宵"].get("value") or 0) - 0.02) < 1e-9,
                  "%r" % (_w.picked["元宵"],))
            _w.var_field.set("数值")
            _w.show_field()
            check("数值框回填 0.02、提示写着 0.01 ~ 0.02",
                  _w.var_int.get() == "0.02" and "0.01 ~ 0.02" in
                  _w.var_int_note.get(),
                  "%s / %s" % (_w.var_int.get(), _w.var_int_note.get()))
            _w.apply()
            root.update()
            _sum2 = app.g.payload_summary(app.g._item_node("Items", _yx))
            check("「应用选中的内容」写出来的就是成长 0.02/0.02",
                  "成长 0.02/0.02" in _sum2, _sum2)
            _w.close()
            root.update()
        app.g.clear_slot("Items", _yx)


        # ---------------- 召唤兽
        check("召唤兽页列出角色", len(app.cb_baby_actor["values"]) >= 1,
              "%r" % (app.cb_baby_actor["values"],))
        check("召唤兽列表已填充", len(app.tv_baby.get_children()) >= 5,
              "%d 个字段" % len(app.tv_baby.get_children()))
        if app.tv_baby.get_children():
            say("改召唤兽等级…")
            app.tv_baby.selection_set(app.tv_baby.get_children()[0])
            app.baby_pick()
            b = app._baby()
            old_lv = app.g.baby_value(b, "level")
            app.g.set_baby(b, "level", old_lv + 1)
            app.load_baby()
            root.update()
            check("界面改召唤兽生效",
                  app.g.baby_value(app._baby(), "level") == old_lv + 1,
                  "%s -> %s" % (old_lv, app.g.baby_value(app._baby(), "level")))
            app.baby_preset("loyalty")
            root.update()
            check("召唤兽预设生效",
                  app.g.baby_value(app._baby(), "loyalty") == 100.0,
                  app.g.baby_value(app._baby(), "loyalty"))
            # 2026-09-20：「满级(65)」按钮去掉；
            # 2026-10-03 起分为「一键满级」（等级+经验一起写）和「经验拉满」（只给经验）。
            _bg = app._baby()
            app.baby_preset("expfull")
            root.update()
            check("召唤兽「一键满级」把等级顶到 %d" % game.MAX_LEVEL_BABY,
                  app.g.baby_value(_bg, "level") == game.MAX_LEVEL_BABY,
                  app.g.baby_value(_bg, "level"))
            # 2026-10-03：召唤兽页新增「经验拉满」（只写 @exp，等级不动）。
            _bg2 = app._baby()
            _lv_before = app.g.baby_value(_bg2, "level")
            app.baby_preset("expfill")
            root.update()
            check("召唤兽「经验拉满」只写经验、等级不动",
                  app.g.baby_value(_bg2, "level") == _lv_before
                  and app.g.baby_value(_bg2, "exp") == game.BABY_EXP_FILL,
                  "lv=%s exp=%s"
                  % (app.g.baby_value(_bg2, "level"),
                     app.g.baby_value(_bg2, "exp")))

        # ---------------- v0.4.6：召唤兽补全（列表 / 新增 / 技能 / 出战 / 改名 / 放生）
        say("召唤兽补全（新增小孩 / 技能 / 出战 / 改名 / 放生）…")
        dlg_mark2 = len(dialogs)
        check("召唤兽一览表建得起来",
              hasattr(app, "tv_babies") and len(app.tv_babies.get_children()) >= 1,
              "%d 只" % len(app.tv_babies.get_children()))
        n0 = len(app.baby_rows)
        a0 = app._baby_actor()
        app._quick_add(a0, 181)                 # 小精灵（神兽资质3）
        root.update()
        check("界面「新增召唤兽」能加小孩（小精灵）",
              len(app.baby_rows) == n0 + 1
              and any(app.g.baby_name(x) == "小精灵" for _i, x in app.baby_rows),
              "%d -> %d：%s" % (n0, len(app.baby_rows),
                               [app.g.baby_name(x) for _i, x in app.baby_rows]))
        # ⚠ 取**最后一只**：真档里本来就可能有一只同名的「小精灵」，
        #   `[0]` 会取到旧档那只（资质是旧值）⇒ 假 NG。
        newb = [x for _i, x in app.baby_rows
                if app.g.baby_name(x) == "小精灵"][-1]
        _p3 = app.babies_ed().config(181)      # 期望值从真值表取，别硬编码
        check("新召唤兽资质 = 神兽资质3 定值",
              [app.g.baby_value(newb, k)
               for k in ("atk", "def", "hpq", "mpq", "agi", "eva")]
              == [_p3["atk"], _p3["def"], _p3["hp"], _p3["mp"],
                  _p3["agi"], _p3["eva"]],
              app.g.baby_value(newb, "atk"))
        check("新召唤兽自带技能（神兽 = 全学）",
              len(app.babies_ed().skills(newb)) > 0,
              "%d 个" % len(app.babies_ed().skills(newb)))
        # ⚠ v0.5.4 界面改版后：技能一览只剩 id / 名字两列，描述挪进只读 Text
        # （表格里塞描述列会被挤到看不全）。2026-09-20 又在最前面加了「序」列。
        # 断言必须跟着改 —— 老断言从 v0.5.4 起就一直挂着没更新，之前跑测试用的是
        # 没 tkinter 的解释器、GUI 组被整组跳过，所以一直没暴露（2026-09-20 发现并修）。
        check("技能一览是 序 / id / 名字三列",
              tuple(app.tv_baby_skills["columns"]) == ("no", "id", "name"),
              "%r" % (app.tv_baby_skills["columns"],))
        rows_sk = [app.tv_baby_skills.item(i, "values")
                   for i in app.tv_baby_skills.get_children()]
        check("技能行里有名字、序号从 1 起",
              bool(rows_sk) and all(r[2] for r in rows_sk)
              and [int(r[0]) for r in rows_sk] == list(range(1, len(rows_sk) + 1)),
              "%r" % (rows_sk[:1],))
        _skd = app.txt_baby_skill_desc.get("1.0", "end").strip()
        check("说明框有内容", len(_skd) > 5, _skd[:46])
        app.tv_babies.selection_set("bb%d" % app.baby_rows[-1][0])
        app.on_baby_select()
        root.update()
        check("选中新那只后名字显示出来",
              app.var_baby_name.get() == "小精灵", app.var_baby_name.get())
        # 改字段「应用」后，选中的应该还是原来那一行（以前会跳回第一行）
        # ⚠ 2026-09-20：字段表里的「等级」行已去掉（等级只由「一键满级」写），
        # 老断言用的 iid "b_level" 不再存在，改用 "b_hp"。
        check("召唤兽字段表里不再有「等级」行",
              "b_level" not in app.tv_baby.get_children(),
              "%r" % (app.tv_baby.get_children(),))
        app.tv_baby.selection_set("b_hp")
        app.baby_pick()
        old_hp2 = int(app.var_baby_val.get())
        app.var_baby_val.set(str(old_hp2 + 1))
        app.apply_baby()
        root.update()
        check("「应用」后选中的还是那一行",
              app.tv_baby.selection() == ("b_hp",)
              and app.var_baby_key.get() == "hp",
              "%r / %r" % (app.tv_baby.selection(), app.var_baby_key.get()))
        check("「应用」真的改了值",
              app.g.baby_value(app._baby(), "hp") == old_hp2 + 1,
              "%s -> %s" % (old_hp2, app.g.baby_value(app._baby(), "hp")))
        # ---- 五行（@attr.@five，2026-09-27 新增）：字段表有一行、值控件切下拉、
        # 下拉外的值被挡住。探针 tests/probe_five.py 验过全链路，这里锁住界面契约。
        say("召唤兽五行（下拉改值）…")
        check("字段表里有「五行」行",
              "b_five" in app.tv_baby.get_children()
              and app.tv_baby.item("b_five", "values")[0] == "五行",
              "%r" % (app.tv_baby.item("b_five", "values"),))
        app.tv_baby.selection_set("b_grow")
        app.baby_pick()
        root.update()
        check("普通字段的值控件 = 数字输入框",
              app.ent_baby_val.winfo_manager() == "grid"
              and app.cb_baby_val.winfo_manager() == "",
              "ent=%r cb=%r" % (app.ent_baby_val.winfo_manager(),
                                app.cb_baby_val.winfo_manager()))
        app.tv_baby.selection_set("b_five")
        app.baby_pick()
        root.update()
        check("五行字段的值控件 = 只读下拉（金木水火土）",
              app.cb_baby_val.winfo_manager() == "grid"
              and app.ent_baby_val.winfo_manager() == ""
              and list(app.cb_baby_val.cget("values"))
              == ["金", "木", "水", "火", "土"],
              "%r" % (list(app.cb_baby_val.cget("values")),))
        _f0 = app.g.baby_value(app._baby(), "five")
        _f1 = "土" if _f0 != "土" else "水"
        app.var_baby_val.set(_f1)
        app.apply_baby()
        root.update()
        check("下拉改五行生效（真写进去）",
              app.g.baby_value(app._baby(), "five") == _f1,
              "%r -> %r" % (_f0, app.g.baby_value(app._baby(), "five")))
        _nerr = len([d for d in dialogs if d[0] == "error"])
        app.var_baby_val.set("风")
        app.apply_baby()
        root.update()
        check("下拉外的值被挡（弹「修改失败」且没写进去）",
              len([d for d in dialogs if d[0] == "error"]) == _nerr + 1
              and app.g.baby_value(app._baby(), "five") == _f1,
              "%r" % (app.g.baby_value(app._baby(), "five"),))
        # ---- 一览表的「五行」列（2026-09-27：加在「成长」左边）
        check("一览表有「五行」列，紧贴「成长」左边",
              tuple(app.tv_babies["columns"])[:6]
              == ("no", "name", "tpl", "lv", "five", "grow"),
              "、".join(app.tv_babies["columns"]))
        _rb = app.tv_babies.get_children()[0]
        _bb = app.baby_rows[0][1]
        _rowv = app.tv_babies.item(_rb, "values")
        check("「五行」列填的是存档真值、列数没错位",
              len(_rowv) == len(app.tv_babies["columns"])
              and _rowv[4] == app.g.baby_value(_bb, "five"),
              "%r / %r" % (_rowv[4], app.g.baby_value(_bb, "five")))
        # ---- 召唤兽页布局（2026-10-04 川截图「排版还要优化」后补的自检）----
        # ⚠ 踩过的坑：`tv_babies = ttk.Treeview(f, ...)` 的 parent 是整页 `f`，却
        #   又 `pack(side="left")` —— Tk 的 `pack()` 只认控件自己的 parent，于是
        #   一览表抢走整页左边缘，把横滚动条 / 改字段行 / 字段表全挤成右边一条。
        #   判据用 `pack_slaves()`（按 pack 顺序返回），不依赖窗口有没有 mapped。
        _bw = app.tv_babies.master
        _mid = app.tv_baby.master.master
        check("一览表与竖滚动条同框（parent 该是 bw，不是整页）",
              _bw is not app.tab_baby
              and any(c.winfo_class() == "TScrollbar"
                      for c in _bw.winfo_children()),
              "parent=%s 内容=%r" % (
                  _bw.winfo_name(), [c.winfo_class() for c in _bw.winfo_children()]))
        _order = app.tab_baby.pack_slaves()
        check("一览表容器排在字段表容器之前（在上面，不是被挤成左右两栏）",
              _bw in _order and _mid in _order
              and _order.index(_bw) < _order.index(_mid),
              "%d vs %d" % (_order.index(_bw) if _bw in _order else -1,
                            _order.index(_mid) if _mid in _order else -1))
        # ---- 召唤兽一览搜索（2026-10-04 川：「已有召唤兽的搜索」）
        _keep_b = app._baby()
        _n_b = len(app.tv_babies.get_children())
        app.var_baby_kw.set("绝无此兽XYZ")
        app.fill_baby_list()
        root.update()
        check("召唤兽搜索：搜不到就一行不列",
              len(app.tv_babies.get_children()) == 0,
              "%d 行" % len(app.tv_babies.get_children()))
        app.var_baby_kw.set("")
        app.baby_kw_clear()
        root.update()
        check("清空召唤兽搜索 → 全列回来",
              len(app.tv_babies.get_children()) == _n_b,
              "%d -> %d" % (_n_b, len(app.tv_babies.get_children())))
        _nm_b = app.g.baby_name(app.baby_rows[0][1])
        app.var_baby_kw.set(_nm_b)
        app.fill_baby_list()
        root.update()
        check("召唤兽搜索：按名字命中（第 1 只「%s」）" % _nm_b,
              bool(app.tv_babies.get_children())
              and app.tv_babies.get_children()[0]
              == "bb%d" % app.baby_rows[0][0],
              "%r" % (app.tv_babies.get_children()[:3],))
        # 序号也能搜（1 起）
        app.var_baby_kw.set("%d" % (app.baby_rows[0][0] + 1))
        app.fill_baby_list()
        root.update()
        check("召唤兽搜索：序号也能搜（%d）" % (app.baby_rows[0][0] + 1),
              "bb%d" % app.baby_rows[0][0]
              in app.tv_babies.get_children(),
              "%r" % (app.tv_babies.get_children()[:3],))
        app.baby_kw_clear()
        root.update()
        if _keep_b is not None:            # 把选中还原回去，别影响后面几段
            app.refresh_baby_list_keep(_keep_b)
            root.update()
        # ---- 进阶 / 资质上限（2026-10-08 川报「用圣兽之心后资质/成长没突破」）--
        # 游戏侧（blob:10251 / 10277 / 78735）：
        #   promote=(v) -> `@promote = v`（**一个资质数字都不动**）
        #   get_max_*   -> `$baby[:_max][promote ? :"类型_p" : 类型]`
        #   get_atk     -> `[@atk, get_max_atk].min`；面板画 "value / max_value"
        # ⇒ 川的「进阶前 / 进阶后」两张图数值一模一样不是 bug，是设计；
        #   上限才从 神兽 1900/…/1.6 抬到 神兽_p 2000/…/1.8。工具加了两个按钮。
        say("进阶 / 资质上限…")
        _btns2 = [w.cget("text") for w in walk(app.tab_baby)
                  if w.winfo_class() == "TButton"]
        check("召唤兽页有「进阶」和「进阶并拉满」",
              "进阶" in _btns2 and "进阶并拉满" in _btns2, "%r" % (_btns2,))
        _bp = [w for w in walk(app.tab_baby)
               if w.winfo_class() == "TButton" and w.cget("text") == "进阶"]
        _bf = [w for w in walk(app.tab_baby)
               if w.winfo_class() == "TButton" and w.cget("text") == "进阶并拉满"]
        _nc = _nn = None      # 本段临时加的样本，收尾要放掉（见下）
        _n_rows0 = len(app.baby_rows)
        _bd = app.babies_ed()
        if _bp and _bf:
            _nc = None       # 现造一只「可进阶且未进阶」的，真档可能全进阶过了
            for _c in _bd.candidates():
                if _c["type"] == "神兽" and _bd.can_promote_id(_c["id"]):
                    try:
                        _nc = _bd.add(app._baby_actor(), _c["id"])
                        break
                    except Exception:
                        _nc = None
            app.refresh_panels()
            root.update()
            _zi = ("atk", "def", "hpq", "mpq", "agi", "eva", "grow")
            _kk = [k for k, b in app.baby_rows if b is _nc]
            check("造出了可进阶未进阶的样本", bool(_kk), str(_nc is not None))
            if _kk:
                app.tv_babies.selection_set("bb%d" % _kk[0])
                app.on_baby_select()
                root.update()
                _v0 = [app.g.baby_value(_nc, k) for k in _zi]
                _cap0 = _bd.max_attr(_nc)
                _bp[0].invoke()
                root.update()
                check("「进阶」置上 @promote，且**数字一个没动**",
                      _bd.promote_of(_nc)
                      and [app.g.baby_value(_nc, k) for k in _zi] == _v0,
                      "%r" % ([app.g.baby_value(_nc, k) for k in _zi],))
                check("「进阶」把上限换到 *_p",
                      _bd.max_attr(_nc) is not _cap0
                      and _bd.max_attr(_nc)["grow"] > _cap0["grow"],
                      "grow %s -> %s" % (_cap0["grow"], _bd.max_attr(_nc)["grow"]))
                _bf[0].invoke()
                root.update()
                _cap1 = _bd.max_attr(_nc)
                _v1 = [app.g.baby_value(_nc, k) for k in _zi]
                check("「进阶并拉满」把 7 项写到进阶后上限",
                      [float(x) for x in _v1] == [
                          float(_cap1[x]) for x in
                          ("atk", "def", "hp", "mp", "agi", "eva", "grow")],
                      "%r" % (_v1,))
                check("拉满后确实超过未进阶上限（真·突破）",
                      _v1[0] > _cap0["atk"] and _v1[6] > _cap0["grow"],
                      "atk %s>%s grow %s>%s"
                      % (_v1[0], _cap0["atk"], _v1[6], _cap0["grow"]))
                # 改字段写超上限 → **照写不误** + 提示「游戏里按上限显示」
                # （2026-10-08 反过来：夹住会把老档本来就超限的值拉低）
                app.tv_baby.selection_set("b_atk")
                app.baby_pick()
                app.var_baby_val.set("9999")
                app.apply_baby()
                root.update()
                check("改字段写超上限：照写 + 提示按上限显示",
                      app.g.baby_value(_nc, "atk") == 9999
                      and app.g.baby_over_cap(_nc).get("atk")
                      == (9999, _cap1["atk"])
                      and "超过当前上限" in app.var_status.get(),
                      "%s / %s" % (app.g.baby_value(_nc, "atk"),
                                   app.var_status.get()))
                # 图鉴里没有进阶形象的不能硬写（游戏取 nil 当立绘名会崩）
                for _c in _bd.candidates():
                    if not _bd.can_promote_id(_c["id"]):
                        try:
                            _nn = _bd.add(app._baby_actor(), _c["id"])
                            break
                        except Exception:
                            _nn = None
                if _nn is not None:
                    app.refresh_panels()
                    root.update()
                    _kk2 = [k for k, b in app.baby_rows if b is _nn]
                    app.tv_babies.selection_set("bb%d" % _kk2[0])
                    app.on_baby_select()
                    root.update()
                    _bp[0].invoke()
                    root.update()
                    check("图鉴无进阶形象的：跳过不写",
                          not _bd.promote_of(_nn) and "跳过" in app.var_status.get(),
                          "%s / %s" % (_bd.display_name(_nn), app.var_status.get()))
        # ⚠ 收尾：把本段临时加的样本**放掉**。它们落在列表末尾，留着会让后面
        #   「设为出战」那条 `active_index(a0) == app.baby_rows[-1][0]` 指错行
        #   （2026-10-08 实测：加完就 NG 了）。倒序删 —— `remove` 是
        #   `items.pop(index)`，正序删会让后面所有索引前移、删错对象。
        _tmp_ix = sorted([k for k, b in app.baby_rows if b is _nc or b is _nn],
                         reverse=True)
        for _ix in _tmp_ix:
            _bd.remove(app._baby_actor(), _ix)
        if _tmp_ix:
            app.refresh_panels()
            root.update()
        check("临时样本已放掉（列表只数回到原样）",
              len(app.baby_rows) == _n_rows0,
              "原 %d 只、加 %d 只、删 %d 只、现在 %d 行"
              % (_n_rows0, (1 if _nc else 0) + (1 if _nn else 0),
                 len(_tmp_ix), len(app.baby_rows)))
        if _keep_b is not None:
            app.refresh_baby_list_keep(_keep_b)
            root.update()

        # ---- 全员状态拉满（2026-10-03：合并「回满气血/魔法」+「全员忠诚满」）
        say("全员状态拉满…")
        _btns = [w.cget("text") for w in walk(app.tab_baby)
                 if w.winfo_class() == "TButton"]
        check("按钮叫「全员状态拉满」，老名字已消失",
              "全员状态拉满" in _btns
              and "全员忠诚满" not in _btns
              and "回满气血/魔法" not in _btns,
              "、".join(t2 for t2 in _btns if "状态" in t2 or "忠诚" in t2
                        or "气血" in t2) or "（没有）")
        _rows = [(aid, x) for aid, a2 in app.sv.actors()
                 for _i, x in app.g.babies(a2)]
        # 先压低一只的气血、魔法、愤怒、忠诚，造出现场
        _tag = _rows[0][1]
        app.g.set_baby(_tag, "hp", 1)
        app.g.set_baby(_tag, "mp", 1)
        app.g.set_baby(_tag, "tp", 0)
        app.g.set_baby(_tag, "loyalty", 3)
        _low = [_x for _aid, _x in _rows
                if abs(float(app.g.baby_value(_x, "loyalty")) - 100.0) > 1e-9]
        _nerr = len([d for d in dialogs if d[0] == "error"])
        _sel_before = app.tv_babies.selection()
        app.baby_preset("state_all")
        root.update()
        _rows2 = [(aid, x) for aid, a2 in app.sv.actors()
                  for _i, x in app.g.babies(a2)]
        _left = [app.g.baby_value(_x, "loyalty") for _aid, _x in _rows2
                 if abs(float(app.g.baby_value(_x, "loyalty")) - 100.0) > 1e-9]
        check("点一下 → 全档 %d 只召唤兽忠诚都到上限" % len(_rows2), not _left,
              "%r" % (_left[:5],))
        _low_hp = [app.g.baby_value(_x, "hp") for _aid, _x in _rows2
                   if float(app.g.baby_value(_x, "hp")) < 90000]
        check("点一下 → 全档召唤兽气血/魔法/愤怒全回满",
              not _low_hp, "%r" % (_low_hp[:5],))
        check("点一下 → 没弹错误框、标了脏",
              len([d for d in dialogs if d[0] == "error"]) == _nerr
              and app.doc.dirty, "%d 只原来低于上限" % len(_low))
        check("再点一下是幂等的（返回 (0, 0, 0)）",
              app.g.set_state_all() == (0, 0, 0),
              "%r" % (app.g.set_state_all(),))
        # ⚠ 2026-09-27 踩过：refresh_panels() 会把一览表选中重置成第一行，
        #   于是「接着操作当前选中那只」全落到第一只头上。锁住这条。
        check("点一下 → 一览表选中没被跳回第一行",
              app.tv_babies.selection() == _sel_before,
              "%r -> %r" % (_sel_before, app.tv_babies.selection()))
        # ---- 宠物「重置潜力/属性」（洗点，2026-09-20 新增；语义见 game.baby_reset_attr）
        say("宠物「重置潜力/属性」（洗点）…")
        _lv_b = app.g.baby_value(app._baby(), "level")
        _T_b = (sum(app.g.baby_value(app._baby(), k)
                    for k in ("体质", "法力", "力量", "耐力", "敏捷"))
                + app.g.baby_value(app._baby(), "潜能"))
        app.baby_preset("reset_attr")
        root.update()
        _five_b = [app.g.baby_value(app._baby(), k)
                   for k in ("体质", "法力", "力量", "耐力", "敏捷")]
        check("宠物洗点：五维 = 20+等级（神兽精确还原）",
              _five_b == [20 + _lv_b] * 5, "%r（等级 %s）" % (_five_b, _lv_b))
        check("宠物洗点：潜能 = 等级*5",
              app.g.baby_value(app._baby(), "潜能") == _lv_b * 5,
              app.g.baby_value(app._baby(), "潜能"))
        check("宠物洗点守恒（五维和 + 潜能 一点没变）",
              sum(_five_b) + app.g.baby_value(app._baby(), "潜能") == _T_b,
              "%r vs %r" % (sum(_five_b) + app.g.baby_value(app._baby(), "潜能"),
                            _T_b))
        say("改技能（走技能管理器：多选 + 全选/反选）…")
        app.babies_ed().clear_skills(app._baby())
        app.load_baby()
        app.skp_baby.fill()
        _d0 = app.txt_baby_skill_desc.get("1.0", "end").strip()
        check("清空技能后说明框跟着空", _d0 == "", "%r" % _d0[:46])
        wb = app.open_skill_manager("baby")
        root.update()
        check("召唤兽技能管理器开得起来",
              wb is not None and wb.win.winfo_exists())
        # ⚠ 技能 id 按版本会飘（尝鲜版「高级必杀」= 45，内测版 = 81）⇒ 查表拿。
        _hit = [s for s in wb.meta if wb.meta[s][0] == "高级必杀"]
        wb.var_kw.set("高级必杀")
        wb.refill()
        _vb = [wb.sid_of(i) for i in wb.tv.get_children()]
        check("管理器按名字搜索生效（含 高级必杀 #%s）"
              % (_hit[0] if _hit else "?"),
              bool(_hit) and _hit[0] in _vb, "%r" % (_vb[:5],))
        wb.select("all")
        check("全选后已选计数跟着变", "已选" in wb.var_sel.get(),
              wb.var_sel.get())
        wb.do_learn()
        root.update()
        check("管理器「学会选中」生效",
              len(app.babies_ed().skills(app._baby())) == len(_vb),
              "%r" % (app.babies_ed().skills(app._baby()),))
        # ---- 「已学」列 = 勾选框那种表示（2026-10-04 川：像人物学门派技能那样）
        _iid0 = wb.tv.get_children()[0]
        _sid0 = wb.sid_of(_iid0)
        check("「已学」列用勾选框字形（■＝已学 / □＝未学）",
              wb.tv.item(_iid0, "values")[0] == "\u25a0",
              "%r" % (wb.tv.item(_iid0, "values")[0],))
        wb.toggle_one(_sid0)
        root.update()
        check("点「已学」格子 → 那一行当场忘掉、字形变 □",
              _sid0 not in app.babies_ed().skills(app._baby())
              and wb.tv.item(_iid0, "values")[0] == "\u25a1",
              "%r / %r" % (app.babies_ed().skills(app._baby()),
                           wb.tv.item(_iid0, "values")[0]))
        wb.toggle_one(_sid0)
        root.update()
        check("再点一次 → 又学会（来回切不用按按钮）",
              _sid0 in app.babies_ed().skills(app._baby())
              and wb.tv.item(_iid0, "values")[0] == "\u25a0",
              "%r" % (wb.tv.item(_iid0, "values")[0],))
        # 真·鼠标点那一列（走 on_click 的 identify_column / identify_row）
        _yy = None
        for _cand in (30, 40, 50, 60, 80):
            if wb.tv.identify_row(_cand):
                _yy = _cand
                break
        if _yy is None:
            check("能定位到列表行（x=20 落在「已学」列）", False,
                  "identify_row 全空（窗口没几何？）")
        else:
            check("x=20 落在第 1 列（「已学」）",
                  wb.tv.identify_column(20) == "#1",
                  wb.tv.identify_column(20))
            _rid = wb.tv.identify_row(_yy)
            _tsid = wb.sid_of(_rid)
            _had = _tsid in app.babies_ed().skills(app._baby())
            wb.tv.event_generate("<Button-1>", x=20, y=_yy)
            root.update()
            check("鼠标点「已学」列＝当场切换那一行（不用先选中）",
                  (_tsid in app.babies_ed().skills(app._baby())) != _had,
                  "#%d 原来已学=%r" % (_tsid, _had))
            if _tsid in app.babies_ed().skills(app._baby()):
                wb.toggle_one(_tsid)        # 还原，别干扰下面
                root.update()
        wb.do_forget()
        root.update()
        check("管理器「忘掉选中」生效",
              app.babies_ed().skills(app._baby()) == [],
              app.babies_ed().skills(app._baby()))
        # 空格 = 逐条反相（2026-10-04 川：「技能管理增加空格键切换学会/忘记」）
        wb.select("all")
        wb.toggle_selected()
        root.update()
        check("管理器空格键：选中的（全未学）一次全学会",
              sorted(app.babies_ed().skills(app._baby())) == sorted(_vb),
              "%r vs %r" % (sorted(app.babies_ed().skills(app._baby())),
                            sorted(_vb)))
        wb.toggle_selected()
        root.update()
        check("管理器空格键：再按一次（全已学）一次全忘掉",
              app.babies_ed().skills(app._baby()) == [],
              app.babies_ed().skills(app._baby()))
        wb.close()
        root.update()
        # 主界面一览：多选 → 「忘掉选中」一次一批
        _bd = app.babies_ed()
        _bd.learn(app._baby(), 45)
        _bd.learn(app._baby(), 88)
        app.load_baby()
        root.update()
        app.tv_baby_skills.selection_set(["sk45", "sk88"])
        app.baby_skill_del()
        root.update()
        check("主界面「忘掉选中」一次忘一批（多选）",
              app.babies_ed().skills(app._baby()) == [],
              app.babies_ed().skills(app._baby()))
        say("改名 / 出战 / 放生…")
        app.var_baby_name.set("我的小精灵")
        app.baby_rename()
        root.update()
        check("界面「改显示名」生效（显示名不查名字表、不弹确认）",
              app.g.baby_name(app._baby()) == "我的小精灵",
              app.g.baby_name(app._baby()))
        app.baby_restore_name()
        root.update()
        check("界面「恢复模板名」生效",
              app.g.baby_name(app._baby()) == "小精灵", app.g.baby_name(app._baby()))
        app.baby_set_active()
        root.update()
        check("界面「设为出战」生效",
              app.babies_ed().active_index(a0) == app.baby_rows[-1][0],
              app.babies_ed().active_index(a0))
        n1 = len(app.baby_rows)
        app.baby_delete()
        root.update()
        check("界面「放生」生效", len(app.baby_rows) == n1 - 1,
              "%d -> %d" % (n1, len(app.baby_rows)))
        check("删掉出战那只后自动换人出战",
              app.babies_ed().active_index(a0) == 0,
              app.babies_ed().active_index(a0))
        # ---- 多选删除（2026-10-04 川：「召唤兽不能多选删除」）----------------
        # ⚠ 必须**倒序**删：`Babies.remove` 内部是 `items.pop(index)`，正序删会
        #   让后面所有索引一起前移、接着按原索引删就删错对象。这里特意选
        #   **不相邻**的两只（第 1 与第 3），删完剩下必须含"中间那只"——
        #   正序删会把这个结果做错（这正是本段要钉的坑）。
        say("召唤兽多选删除…")
        _cid = save.M.value_of(save._deref(
            save.ivar(app.baby_rows[0][1], "@actor_id")))
        _m0 = len(app.baby_rows)
        for _ in range(3):
            app.babies_ed().add(a0, _cid)
        app.fill_baby_list()
        root.update()
        check("多选删除前先塞进 3 只临时召唤兽",
              len(app.baby_rows) == _m0 + 3,
              "%d -> %d" % (_m0, len(app.baby_rows)))
        _bb = app.tv_babies.get_children()
        _keep = app.baby_rows[1][1]                 # 中间那只：必须活下来
        app.tv_babies.selection_set([_bb[0], _bb[2]])
        root.update()
        check("召唤兽列表能多选（selectmode=extended）",
              len(app.tv_babies.selection()) == 2,
              "%r" % (app.tv_babies.selection(),))
        app.baby_delete()
        root.update()
        check("界面「放生」多选一次删一批",
              len(app.baby_rows) == _m0 + 1,
              "%d -> %d" % (_m0 + 3, len(app.baby_rows)))
        check("多选删的是选中的那两只（中间那只没被误删）",
              any(x is _keep for _i, x in app.baby_rows),
              "剩 %d 只" % len(app.baby_rows))
        app.baby_add_dialog()          # 打开「新增召唤兽」窗口（不点确定，只建得起来）
        root.update()
        opened = [w for w in root.winfo_children()
                  if isinstance(w, app.tk.Toplevel)]
        check("「新增召唤兽」窗口能打开",
              any(w.winfo_exists() for w in opened), "%d 个窗口" % len(opened))
        _dlg = [w for w in opened if w.winfo_exists()
                and w.title() == "新增召唤兽"]
        if _dlg:
            _ws = walk(_dlg[0])
            _tv = [w for w in _ws if w.winfo_class() == "Treeview"]
            _ab = [w for w in _ws if w.winfo_class() == "TButton"
                   and "加" in str(w.cget("text"))]
            check("「新增召唤兽」列表能多选（selectmode=extended）",
                  bool(_tv) and str(_tv[0].cget("selectmode")) == "extended",
                  str(_tv[0].cget("selectmode")) if _tv else "（没有列表）")
            check("筛选复选框已改名「神兽」",
                  any(w.winfo_class() == "TCheckbutton"
                      and str(w.cget("text")) == "神兽" for w in _ws),
                  "、".join(str(w.cget("text")) for w in _ws
                            if w.winfo_class() == "TCheckbutton"))
            if _tv and _ab:
                _kids = _tv[0].get_children()
                _tv[0].selection_set(_kids[:2])
                root.update()
                # ⚠ 文字变长后必须重算贴字 padding（refit_btn）——
                #   还挂着短文字的负 padding 就会被裁，这里拿一个新按钮当基准
                _ref = app.ttk.Button(_dlg[0], text="加选中的 2 只")
                _ref.update_idletasks()
                check("选中 2 项 → 按钮变「加选中的 2 只」（且没被裁）",
                      str(_ab[0].cget("text")) == "加选中的 2 只"
                      and _ab[0].winfo_reqwidth()
                      >= _ref.winfo_reqwidth() - 1,
                      "%s / %dpx（基准 %dpx）"
                      % (_ab[0].cget("text"), _ab[0].winfo_reqwidth(),
                         _ref.winfo_reqwidth()))
                _ref.destroy()
                _tv[0].selection_set(_kids[:1])
                root.update()
                check("选回 1 项 → 按钮变回「加这只」",
                      str(_ab[0].cget("text")) == "加这只",
                      str(_ab[0].cget("text")))
            # ⚠ 2026-10-07 川报「筛选神兽报错」：`bd` 是 Babies 实例，
            #   `bd.GOD_TYPES` 是 AttributeError（常量在**模块**上），而且
            #   `and` short-circuit 让它只在勾选时才炸。炸的那一刻 refill 已经
            #   把行全删了 → 列表变空。所以这里同时钉「不空」+「只剩神兽档」。
            _cbg = [w for w in _ws if w.winfo_class() == "TCheckbutton"
                    and str(w.cget("text")) == "神兽"]
            if _cbg and _tv:
                _cbg[0].invoke()               # 勾上「神兽」
                root.update()
                _k2 = _tv[0].get_children()
                _ty2 = set(str(_tv[0].item(c, "values")[2]) for c in _k2)
                check("勾「神兽」后列表重筛（不空且只剩神兽/泡泡灵仙）",
                      bool(_k2) and _ty2 and
                      _ty2 <= {"神兽", "泡泡灵仙"},
                      "%d 行，类型=%s" % (len(_k2), sorted(_ty2)))
                _cbg[0].invoke()
                root.update()
                check("取消「神兽」后列表全回来",
                      len(_tv[0].get_children()) > len(_k2),
                      "%d → %d" % (len(_k2), len(_tv[0].get_children())))
        for w in opened:               # 关掉，别把 grab 留着
            try:
                w.grab_release()
            except Exception:
                pass
            w.destroy()
        root.update()
        del dialogs[dlg_mark2:]        # 这一段自造的弹框不算数

        # ---------------- 防作弊体检
        say("防作弊体检…")
        n_bad = app.guard_check()
        root.update()
        check("体检能跑并列出条目",
              len(app.tv_guard.get_children()) >= 4,
              "%d 项，超限 %s" % (len(app.tv_guard.get_children()), n_bad))
        check("体检结果与报告一致",
              n_bad == len([r for r in app.g.anti_cheat_report() if r[3]]),
              "%s" % n_bad)
        app.guard_clear()
        root.update()
        check("清除作弊标记生效",
              save.M.value_of(
                  save._deref(save.ivar(app.sv.section("system"),
                                              "@cheated"))) is False)
        app.guard_resync()
        root.update()
        check("同步计数校验后全部对得上",
              all(r[2] == r[3] for r in app.g.security_rows()))

        # ---------------- 开关 / 变量
        check("开关表已填充", len(app.tv_sw.get_children()) == nsw,
              "%d / %d" % (len(app.tv_sw.get_children()), nsw))
        check("变量表已填充", len(app.tv_va.get_children()) == nva,
              "%d / %d" % (len(app.tv_va.get_children()), nva))
        check("开关带中文注释",
              any(app.tv_sw.item(c, "values")[2] for c in app.tv_sw.get_children()),
              "%r" % [app.tv_sw.item(c, "values")[2]
                      for c in app.tv_sw.get_children()])
        check("变量带中文注释",
              any(app.tv_va.item(c, "values")[2] for c in app.tv_va.get_children()),
              "%r" % [app.tv_va.item(c, "values")[2]
                      for c in app.tv_va.get_children()])
        say("点开关（双击切换）…")
        sw0 = app.sv.get_switch(0)
        app.tv_sw.selection_set("s0")
        app.sw_toggle()
        root.update()
        check("界面切换开关生效", app.sv.get_switch(0) is (not sw0),
              "%s -> %s" % (sw0, app.sv.get_switch(0)))
        check("开关表格同步刷新",
              app.tv_sw.item("s0", "values")[1] == ("开" if not sw0 else "关"))

        say("改变量（用假对话框，不弹模态）…")
        real_dlg = huaji2_save_editor.EditDialog
        real_wait = root.wait_window
        huaji2_save_editor.EditDialog = FakeDialog
        root.wait_window = lambda w=None: None
        try:
            app.tv_va.selection_set("v0")
            app.va_edit()
            root.update()
            check("界面改变量生效", app.sv.get_variable(0) == 314,
                  "%r" % app.sv.get_variable(0))
            # ⚠ 值列在源值是 nil 时是字符串 "None"（真档的 `@variables` 会整体消失），
            # 直接 int() 会抛 ValueError 把后半段断言全带崩 ⇒ 先转字符串再比。
            _va_cell = app.tv_va.item("v0", "values")[1]
            check("变量表格同步刷新", str(_va_cell).strip() == "314",
                  "%r" % (_va_cell,))
        finally:
            huaji2_save_editor.EditDialog = real_dlg
            root.wait_window = real_wait

        # ---------------- 防作弊：破坏 → 一键修复
        say("破坏并一键修复防作弊校验…")
        lock, vn = app.sv.gold_node()
        mn = save._deref(save.ivar(lock, "@master"))
        app.sv.doc.set_value(mn, 1)
        app.doc.dirty = True
        app.fill_info()
        root.update()
        check("破坏后能检出", len(app.sv.check_locks()) == 1)
        check("界面提示不一致", "不一致" in app.var_lock.get(), app.var_lock.get())
        app.fix_locks()
        root.update()
        check("一键修复生效", app.sv.check_locks() == [] and
              "正常" in app.var_lock.get())

        # ---------------- 数据表 / CSV
        say("数据表预览 + 导出 CSV…")
        app.lst_db.selection_clear(0, "end")
        idx = datatables.ALL_KEYS.index("Items")
        app.lst_db.selection_set(idx)
        app.db_preview()
        root.update()
        check("Items 预览有行", len(app.tv_db.get_children()) >= 1,
              app.var_db_info.get())
        check("预览列名是中文", app.tv_db.heading("c1", "text") == "名称",
              "c1 = %s" % app.tv_db.heading("c1", "text"))
        csv_dir = os.path.join(WORK, "csv")
        app.var_db_out.set(csv_dir)
        app.db_export_selected()
        root.update()
        f = os.path.join(csv_dir, "Items_物品.csv")
        check("导出选中表生成 CSV", os.path.exists(f), f)
        if os.path.exists(f):
            txt = open(f, encoding="utf-8-sig").read()
            check("CSV 有表头 + 内容",
                  "ID,名称" in txt.splitlines()[0] and "说明" in txt.splitlines()[0],
                  txt.splitlines()[0][:60])
        say("全部导出（8 张表，稍等）…")
        app.lst_db.selection_clear(0, "end")
        app.db_export_all()
        root.update()
        n_csv = len([x for x in os.listdir(csv_dir) if x.endswith(".csv")])
        check("全部导出 8 张表", n_csv >= len(datatables.DEFAULT_KEYS),
              "%d 个 csv" % n_csv)

        # ---------------- 保存 / 重开
        say("保存（走界面自己的保存流程）…")
        app.save_save()
        root.update()
        check("保存后仍能重新解析", len(app.doc.objects) == 2)
        check("保存后面板重建成功", app.sv is not None)
        check("保存后金钱仍是 7654321", app.sv and app.sv.gold() == 7654321,
              "%r" % (app.sv.gold() if app.sv else None))
        baks = [x for x in os.listdir(backup.backup_dir(copy))
                if ".bak." in x]
        check("原文件留了备份（在备份目录）", len(baks) >= 1, "%r" % baks[:2])
        check("存档目录不再散落 .bak.",
              not [x for x in os.listdir(WORK) if ".bak." in x])

        say("重新打开副本…")
        app.load(copy, quiet=True)
        root.update()
        check("重开后金钱还在", app.sv.gold() == 7654321, "%r" % app.sv.gold())
        check("重开后校验仍正常", app.sv.check_locks() == [])
        check("重开后角色等级还在（等级只读展示，从存档读）",
              app.sv.actor_field(app.sv.actors()[0][1], "@level") is not None
              and ("级别：%s" % app.sv.actor_field(app.sv.actors()[0][1],
                                                   "@level"))
              in app.txt_actor.get("1.0", "end"))

        say("打开一个非存档明文文件（Battle.bt2）…")
        sample = None
        game = paths.find_game_dir()
        if game:
            ad = os.path.join(game, "Logs", "Battle")
            if os.path.isdir(ad):
                for d in sorted(os.listdir(ad)):
                    p = os.path.join(ad, d, "Battle.bt2")
                    if os.path.exists(p):
                        sample = p
                        break
        if sample:
            app.load(sample, quiet=True)
            root.update()
            check("打开非存档文件不崩（面板优雅降级）", app.sv is None)
            check("数据树仍可用", len(app.tree.get_children("")) >= 1)
            # ⚠ 验「非存档文件不许走存档管理」：老版本只看 `self.doc`，「立即备份」
            #   会把那个文件复制到它旁边、还建出 `.huaji2-save-editor` 备份目录。
            #   2026-09-27 查实：游戏目录 `Logs\Battle\<旧日志>\` 里被这么堆了
            #   177 份垃圾备份（从 09-13 攒到今天），文件本身还被写坏过。
            _junk = os.path.join(os.path.dirname(sample), ".huaji2-save-editor")
            _had = os.path.isdir(_junk)
            _mark = len(dialogs)
            app.saves_backup()
            root.update()
            check("非存档文件 → 「立即备份」被拦下、不在它旁边建备份目录",
                  os.path.isdir(_junk) == _had and len(dialogs) > _mark,
                  "备份目录存在=%s，弹框+%d" % (os.path.isdir(_junk),
                                            len(dialogs) - _mark))
            # ⚠ 这一段的 app 必须切回副本：否则后面整段「存档管理」会继续在
            #   游戏目录里那份 Battle.bt2 上操作（建备份、写坏文件、扫描它旁边）。
            app.load(copy, quiet=True)
            root.update()
            check("马上切回副本（别让备份段跑到游戏目录里乱写）",
                  app.doc is not None
                  and os.path.abspath(app.doc.path) == os.path.abspath(copy),
                  app.doc.path if app.doc else "(no doc)")
        else:
            say("（没有 Battle.bt2 样本，跳过）")

        # ---------------- v0.4.4：存档管理（放最后，免得它重载存档打断前面的状态）
        say("存档管理页（备份 / 恢复选中 / 恢复最新 / 删除 / 删除非最新）…")
        dlg_mark = len(dialogs)      # 本段会故意把存档改坏，产生的弹框段末清掉
        check("存档管理页建得起来",
              hasattr(app, "tab_saves") and hasattr(app, "tv_saves"),
              app.nb.tab(app.tab_saves, "text"))
        app.saves_refresh()
        root.update()
        n0 = len(app.save_rows)
        # 立即备份后会弹窗填备注（测试里换成假 NoteDialog，不弹模态）
        real_note_dlg0 = huaji2_save_editor.NoteDialog
        real_wait0 = root.wait_window
        huaji2_save_editor.NoteDialog = FakeNoteDialog
        root.wait_window = lambda w=None: None
        try:
            app.saves_backup()
        finally:
            huaji2_save_editor.NoteDialog = real_note_dlg0
            root.wait_window = real_wait0
        root.update()
        p = app.doc.path if app.doc else copy   # 恢复/撤销都拿文件本身比对
        check("界面「立即备份」生成一份", len(app.save_rows) == n0 + 1,
              "%d -> %d" % (n0, len(app.save_rows)))
        check("列表里有文件名和时间",
              bool(app.tv_saves.item("b0", "values")[3])
              and bool(app.tv_saves.item("b0", "values")[0]),
              "%r" % (app.tv_saves.item("b0", "values")[:2],))
        before = open(p, "rb").read()
        with open(p, "wb") as f:                 # 先把存档“改坏”
            f.write(b"broken" + before[:200])
        app.tv_saves.selection_set("b0")
        app.saves_restore()
        root.update()
        check("界面「恢复选中」恢复成功",
              open(p, "rb").read() == before,
              "%d 字节（备份 %d）" % (os.path.getsize(p), len(before)))
        check("恢复不再额外多留一份备份",
              not any(r["kind"] == "before-restore" for r in app.save_rows),
              "%r" % [r["kind"] for r in app.save_rows][:4])
        with open(p, "wb") as f:                 # 再改坏一次，用「恢复最新」换回来
            f.write(b"broken2" + before[:200])
        app.saves_restore_newest()
        root.update()
        check("界面「恢复最新」能换回上一次修改前",
              open(p, "rb").read() == before, "%d 字节" % os.path.getsize(p))
        with open(p, "wb") as f:                 # 收回原样
            f.write(before)
        app.load(p, quiet=True)
        root.update()
        n_before_del = len(app.save_rows)
        app.tv_saves.selection_set("b0")
        app.saves_delete()
        root.update()
        check("界面「删除选中」生效", len(app.save_rows) == n_before_del - 1,
              "%d -> %d" % (n_before_del, len(app.save_rows)))
        # 备注编辑：用假 NoteDialog（不弹模态）→ 写进备份旁的 .txt
        # （新环境第一次跑备份目录是空的，可能被删空：先补一份，保证有 b0 可选）
        real_note_dlg = huaji2_save_editor.NoteDialog
        real_wait2 = root.wait_window
        huaji2_save_editor.NoteDialog = FakeNoteDialog
        root.wait_window = lambda w=None: None
        try:
            if not app.save_rows:
                app.saves_backup()
                root.update()
            app.tv_saves.selection_set("b0")
            app.saves_edit_note()
            root.update()
            r0 = app.save_rows[0]
            check("界面「编辑备注」生效（写进 .txt）",
                  r0["note"] == "测试备注"
                  and os.path.exists(r0["path"] + ".txt"),
                  "%r" % r0["note"])
        finally:
            huaji2_save_editor.NoteDialog = real_note_dlg
            root.wait_window = real_wait2
        # 再备份两份（备份后填备注，测试里也是假 NoteDialog）
        huaji2_save_editor.NoteDialog = FakeNoteDialog
        root.wait_window = lambda w=None: None
        try:
            app.saves_backup()
            root.update()
            app.saves_backup()
            root.update()
        finally:
            huaji2_save_editor.NoteDialog = real_note_dlg
            root.wait_window = real_wait2
        # ⚠ 到这儿通常还躺着「保存前自动备份」那类自动档（save_save 一定会留一份），
        #   而「删除非最新」的契约是**自动档只留最新一份、手动档一份不动**。
        #   先按契约验一次「只清自动档」，再把自动档清干净 —— 否则下一步那条
        #   "全手动就不删"的断言会误判成"它删了手动档"。
        if any(r["kind"] != "manual" for r in app.save_rows):
            _n_manual = sum(1 for r in app.save_rows if r["kind"] == "manual")
            _n_before = len(app.save_rows)
            app.saves_delete_old()
            root.update()
            check("界面「删除非最新」只清自动档、手动档一份不少",
                  sum(1 for r in app.save_rows if r["kind"] == "manual")
                  == _n_manual and len(app.save_rows) <= _n_manual + 1,
                  "%d -> %d（手动 %d 份）" % (_n_before, len(app.save_rows),
                                              _n_manual))
        for _ in range(20):                      # 清掉剩下的自动档
            _auto = [i for i, r in enumerate(app.save_rows)
                     if r["kind"] != "manual"]
            if not _auto:
                break
            app.tv_saves.selection_set("b%d" % _auto[0])
            app.saves_delete()
            root.update()
        n_before_clean = len(app.save_rows)
        app.saves_delete_old()
        root.update()
        check("界面「删除非最新」不碰手动备份（全是手动档就不删）",
              n_before_clean >= 2 and len(app.save_rows) == n_before_clean
              and all(r["kind"] == "manual" for r in app.save_rows),
              "%d -> %d　档别 %r" % (n_before_clean, len(app.save_rows),
                                    [r["kind"] for r in app.save_rows]))
        # 删除无备注：手工造一份没备注的，验证只删没备注的、留带备注的
        backup.backup(p, backup.KIND_MANUAL)     # 这份不带备注
        app.saves_refresh()
        root.update()
        n_with_note = sum(1 for r in app.save_rows if r["note"])
        app.saves_delete_no_note()
        root.update()
        check("界面「删除无备注」只删没备注的",
              len(app.save_rows) == n_with_note
              and all(r["note"] for r in app.save_rows)
              and n_with_note >= 1,
              "%d 份带备注 -> 剩 %d" % (n_with_note, len(app.save_rows)))
        check("备份目录就在存档旁边",
              os.path.isdir(os.path.join(os.path.dirname(p),
                                         ".huaji2-save-editor")),
              os.path.dirname(p))
        del dialogs[dlg_mark:]       # 本段自造的弹框（含故意的“打开失败”）不算数

        check("全程没弹出错误框", not [d for d in dialogs if d[0] == "error"],
              "%r" % (dialogs[:2],))
    except SystemExit:
        pass
    except Exception:
        OK[1] += 1
        say("[NG] 抛异常：\n" + traceback.format_exc())
    finally:
        if app is not None:
            try:
                app.root.destroy()
            except Exception:
                pass
        try:
            if backup_last is not None:
                open(last_txt, "w", encoding="utf-8").write(backup_last)
            elif os.path.exists(last_txt):
                os.remove(last_txt)
        except OSError:
            pass
        shutil.rmtree(WORK, ignore_errors=True)

    say("==== 通过 %d, 失败 %d ====" % (OK[0], OK[1]))
    return 1 if OK[1] else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")
    sys.exit(main())
