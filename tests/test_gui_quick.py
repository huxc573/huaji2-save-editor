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

import xj_marshal   # noqa: E402
import xj_save      # noqa: E402

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


def kill_timers(root):
    try:
        for aid in root.tk.call("after", "info"):
            try:
                root.after_cancel(aid)
            except Exception:
                pass
    except Exception:
        pass


def main():
    open(LOG, "w", encoding="utf-8").close()
    import faulthandler
    faulthandler.enable()
    faulthandler.dump_traceback_later(60, exit=True)
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

    import xj_db
    import xj_env
    import xj_save
    import xj_viewer

    # 把弹窗换成"记录"，避免模态框把测试挂住
    dialogs = []
    xj_viewer.messagebox = type("MB", (), {
        "showinfo": staticmethod(lambda *a, **k: dialogs.append(("info", a))),
        "showerror": staticmethod(lambda *a, **k: dialogs.append(("error", a))),
        "showwarning": staticmethod(lambda *a, **k: dialogs.append(("warn", a))),
    })
    say("已把弹窗替换为记录模式")

    os.makedirs(WORK, exist_ok=True)
    real = xj_env.save_path()
    if not os.path.exists(real):
        say("找不到存档 %s，跳过" % real)
        return 0
    copy = os.path.join(WORK, "gui_copy.rvdata2")
    shutil.copyfile(real, copy)
    say("存档副本 = %s" % copy)

    last_txt = xj_viewer.LAST_TXT
    backup_last = None
    if os.path.exists(last_txt):
        backup_last = open(last_txt, encoding="utf-8").read()

    app = None
    try:
        say("创建窗口…")
        app = xj_viewer.App(root, save_path=None)
        kill_timers(root)
        root.update()
        say("窗口创建完成（%d 个页签）" % app.nb.index("end"))
        check("11 个页签都建好", app.nb.index("end") == 11,
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
        check("概览文本已填充", "存银" in app.txt_info.get("1.0", "end"))

        say("改金钱…")
        app.var_gold.set("7654321")
        app.apply_quick()
        root.update()
        check("界面改金钱 @value 生效", app.sv.gold() == 7654321,
              "%r" % app.sv.gold())
        check("界面改金钱 校验同步", app.sv.check_locks() == [])
        check("标签同步刷新", app.var_gold.get() == "7654321")
        check("已标记为脏（保存按钮会亮）", app.doc.dirty is True)

        # ---------------- 角色 / 属性
        kids = app.tv_actor.get_children()
        check("角色列表已填充", len(kids) >= 1, "角色数=%d" % len(kids))
        if kids:
            say("改角色…")
            app.tv_actor.selection_set(kids[0])
            app.load_actor()
            root.update()
            aid, a = app.sv.actors()[0]
            lv = app.actor_vars["@level"].get()
            try:
                app.actor_vars["@level"].set(str(int(lv) + 3))
            except ValueError:
                app.actor_vars["@level"].set("9")
            k0 = xj_save.SaveDoc.ATTR_FIELDS[0]
            av0 = dict(app.sv.attr_items(a)).get(k0)
            if isinstance(av0, int):
                app.attr_vars[k0].set(str(av0 + 10))
            app.apply_actor()
            root.update()
            check("界面改角色等级生效",
                  str(app.sv.actor_field(a, "@level"))
                  == app.actor_vars["@level"].get(),
                  "%s -> %s" % (lv, app.actor_vars["@level"].get()))
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

        # ---------------- 背包 / 物品
        check("背包页 20 格都建好了", len(app.tv_pack.get_children()) == 20,
              "%d 行" % len(app.tv_pack.get_children()))
        filled = [r for r in app.tv_pack.get_children()
                  if app.tv_pack.item(r, "values")[2] != "（空）"]
        check("背包里看到东西了", len(filled) >= 1, "%d 格有货" % len(filled))
        check("队伍信息已填充", "存银" in app.var_party.get(),
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
              d is not None and xj_marshal.value_of(
                  xj_save._deref(xj_save.hash_get(d, "id"))) == 21,
              app.g.payload_summary(app.g._item_node("Items", egg_slot)))
        app.var_bag_kid.set("")


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
        newb = [x for _i, x in app.baby_rows if app.g.baby_name(x) == "小精灵"][0]
        check("新召唤兽资质 = 神兽资质3 定值",
              [app.g.baby_value(newb, k)
               for k in ("atk", "def", "hpq", "mpq", "agi", "eva")]
              == [2400, 2400, 7500, 4800, 2100, 2100],
              app.g.baby_value(newb, "atk"))
        check("新召唤兽自带技能（神兽 = 全学）",
              len(app.babies_ed().skills(newb)) > 0,
              "%d 个" % len(app.babies_ed().skills(newb)))
        app.tv_babies.selection_set("bb%d" % app.baby_rows[-1][0])
        app.on_baby_select()
        root.update()
        check("选中新那只后名字显示出来",
              app.var_baby_name.get() == "小精灵", app.var_baby_name.get())
        say("改技能…")
        app.babies_ed().clear_skills(app._baby())
        app.load_baby()
        app.fill_skill_templates()
        app.var_skill_pick.set("#45 高级必杀"
                               if "#45 高级必杀" in app.cb_skill["values"]
                               else app.cb_skill["values"][0])
        app.baby_skill_add()
        root.update()
        check("界面「学会技能」生效",
              len(app.babies_ed().skills(app._baby())) == 1,
              app.babies_ed().skills(app._baby()))
        app.tv_baby_skills.selection_set("sk%d" % app.babies_ed().skills(app._baby())[0])
        app.baby_skill_del()
        root.update()
        check("界面「忘掉选中」生效",
              app.babies_ed().skills(app._baby()) == [],
              app.babies_ed().skills(app._baby()))
        say("改名 / 出战 / 放生…")
        app.var_baby_name.set("我的小精灵")
        app.baby_rename()
        root.update()
        check("界面「改显示名」生效（不在名字表里会先弹确认）",
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
        app.baby_add_dialog()          # 打开「新增召唤兽」窗口（不点确定，只建得起来）
        root.update()
        opened = [w for w in root.winfo_children()
                  if isinstance(w, app.tk.Toplevel)]
        check("「新增召唤兽」窗口能打开",
              any(w.winfo_exists() for w in opened), "%d 个窗口" % len(opened))
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
              xj_save.M.value_of(
                  xj_save._deref(xj_save.ivar(app.sv.section("system"),
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
        real_dlg = xj_viewer.EditDialog
        real_wait = root.wait_window
        xj_viewer.EditDialog = FakeDialog
        root.wait_window = lambda w=None: None
        try:
            app.tv_va.selection_set("v0")
            app.va_edit()
            root.update()
            check("界面改变量生效", app.sv.get_variable(0) == 314,
                  "%r" % app.sv.get_variable(0))
            check("变量表格同步刷新",
                  int(app.tv_va.item("v0", "values")[1]) == 314)
        finally:
            xj_viewer.EditDialog = real_dlg
            root.wait_window = real_wait

        # ---------------- 防作弊：破坏 → 一键修复
        say("破坏并一键修复防作弊校验…")
        lock, vn = app.sv.gold_node()
        mn = xj_save._deref(xj_save.ivar(lock, "@master"))
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
        idx = xj_db.ALL_KEYS.index("Items")
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
        check("全部导出 8 张表", n_csv >= len(xj_db.DEFAULT_KEYS),
              "%d 个 csv" % n_csv)

        # ---------------- 保存 / 重开
        say("保存（走界面自己的保存流程）…")
        app.save_save()
        root.update()
        check("保存后仍能重新解析", len(app.doc.objects) == 2)
        check("保存后面板重建成功", app.sv is not None)
        check("保存后金钱仍是 7654321", app.sv and app.sv.gold() == 7654321,
              "%r" % (app.sv.gold() if app.sv else None))
        baks = [x for x in os.listdir(WORK) if ".bak." in x]
        check("原文件留了备份", len(baks) >= 1, "%r" % baks[:2])

        say("重新打开副本…")
        app.load(copy, quiet=True)
        root.update()
        check("重开后金钱还在", app.sv.gold() == 7654321, "%r" % app.sv.gold())
        check("重开后校验仍正常", app.sv.check_locks() == [])
        check("重开后角色等级还在",
              str(app.sv.actor_field(app.sv.actors()[0][1], "@level"))
              == app.actor_vars["@level"].get())

        say("打开一个非存档明文文件（Battle.bt2）…")
        sample = None
        game = xj_env.find_game_dir()
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
        app.saves_backup()
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
        app.saves_backup()
        root.update()
        app.saves_backup()
        root.update()
        n_before_clean = len(app.save_rows)
        app.saves_delete_old()
        root.update()
        check("界面「删除非最新」只留一份",
              n_before_clean >= 2 and len(app.save_rows) == 1,
              "%d -> %d" % (n_before_clean, len(app.save_rows)))
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
