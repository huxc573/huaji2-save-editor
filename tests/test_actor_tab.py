# -*- coding: utf-8 -*-
"""一次性：角色页界面冒烟 —— 字段布局 / 标签是否被截断 / 概览浮窗提醒。

用系统 Python 3.12 跑（managed 3.13 没有 tkinter）。
"""
import io
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import paths  # noqa: E402
import game  # noqa: E402
from tables import sect  # noqa: E402
from tables import sect_appellation  # noqa: E402
# ⚠ 不能在模块级 import huaji2_save_editor：它 import tkinter，而没有 tkinter 的
# 解释器（managed 3.13）会在 main() 之前就 ModuleNotFoundError，
# 优雅跳过就没机会执行了。

WORK = os.path.join(HERE, "_smoke_lim")
WARNS = []
#: 桩 messagebox 的「确认框返回值」开关（True = 点「是」）
MB_STUB = {"answer": True}
BAD = [0]
CHECKED = [0]


def check(name, cond, extra=""):
    """本脚本里的通用断言。"""
    CHECKED[0] += 1
    if not cond:
        BAD[0] += 1
    print("  [%s] %s%s" % ("OK" if cond else "NG", name,
                           ("  " + extra) if extra else ""))
    return bool(cond)


def _guard_real_save(app, real):
    """死守：任何时刻 doc.path 指着真实存档就直接退出。

    冒烟测试会真的调 apply_actor()，一旦 doc 指向玩家真档，
    后续任何 save / auto_backup 都会写坏它。宁可测试跑不起来，
    也不能再动玩家的存档（2026-09-14 踩过）。
    """
    p = os.path.abspath(app.doc.path) if (app.doc and app.doc.path) else ""
    if p.lower() == os.path.abspath(real).lower():
        print("\n!!! 危险：doc 指向真实存档 %s，立刻停止 !!!" % p)
        sys.exit(9)


def _parent_class(root, widget):
    """widget 的父容器类名（tkinter 没有 winfo_parent_class，得自己查）。"""
    try:
        return root.nametowidget(widget.winfo_parent()).winfo_class()
    except Exception:
        return ""


def _ancestor_classes(root, widget):
    """widget 往上所有祖先的类名，用来确认它挂在哪个布局里。

    ⚠ 必须防自环：根的 winfo_parent() 是空串，nametowidget("") 会拿回 root
    自己 → 不设 seen 就是死循环。
    """
    out = []
    seen = set()
    try:
        p = root.nametowidget(widget.winfo_parent())
        while p is not None and str(p) not in seen:
            seen.add(str(p))
            out.append(p.winfo_class())
            par = p.winfo_parent()
            if not par:
                break
            try:
                p = root.nametowidget(par)
            except Exception:
                break
    except Exception:
        pass
    return out


def main():
    import faulthandler
    faulthandler.enable()
    faulthandler.dump_traceback_later(120, exit=True)
    try:
        import tkinter as tk
        from tkinter import font as tkfont
        root = tk.Tk()
        root.withdraw()
        root.update()
    except Exception as e:
        print("没有图形环境，跳过：%s" % e)
        return 0

    import huaji2_save_editor

    huaji2_save_editor.messagebox = type("MB", (), {
        "showinfo": staticmethod(lambda *a, **k: WARNS.append(("info", a))),
        "showerror": staticmethod(lambda *a, **k: WARNS.append(("error", a))),
        "showwarning": staticmethod(lambda *a, **k: WARNS.append(("warn", a))),
        # 可切换的确认框返回值（`MB_STUB["answer"]`）：验证「弹窗点否 → 什么都不写」
        "askyesno": staticmethod(lambda *a, **k: WARNS.append(("ask", a))
                                  or MB_STUB["answer"]),
    })

    os.makedirs(WORK, exist_ok=True)
    copy = os.path.join(WORK, "copy.rvdata2")
    shutil.copyfile(paths.save_path(), copy)

    # ⚠⚠ 血泪教训：App(save_path=None) 会走 _guess_save() 找到**真实存档**，
    # 并 root.after(200, load) 排队载入。冒烟脚本随后手动 load(副本)，
    # 200ms 后那个排队回调醒来把 self.doc 换回真档 —— 之后再 apply_actor()
    # 改的就是真档，一保存就把玩家存档写坏（2026-09-14 真踩过）。
    # 所以这里**必须把副本路径传进去**，让 _guess_save() 完全没机会跑。
    app = huaji2_save_editor.App(root, save_path=copy)
    root.update()
    app.load(copy, quiet=True)
    root.update()
    _guard_real_save(app, paths.save_path())

    # 双保险：断言当前 doc 指向副本，不是真实存档
    check("打开的确实是副本，不是真实存档",
          os.path.abspath(app.doc.path).lower() == os.path.abspath(copy).lower(),
          "doc.path=%s" % app.doc.path)

    # ---- 1) 标签有没有被输入框挤掉（用实际字体量像素宽）
    # 只在标签真的声明了 width= 时才可能被挤（width 单位是「字符」，
    # 一个字符的宽度对中文等宽字体不是 measure("0") —— 那个常返回 0，
    # 会把这检查变成全表假报警。这里用一个真实汉字量。）
    print("--- 1) 标签宽度检查 ---")
    f = tkfont.nametofont("TkDefaultFont")
    unit = f.measure("字")
    print("  字体=%s  一个汉字宽=%dpx" % (f.actual("family"), unit))

    LABELS = [0]      # 声明了 width= 的标签（可能为 0，见下）
    ALL_LABELS = [0]  # 遍历到的标签总数（角色页标签现在全部自适应，无 width）

    def walk(w):
        for c in w.winfo_children():
            cls = c.winfo_class()
            if cls in ("TLabel", "Label"):
                txt = c.cget("text") or ""
                ALL_LABELS[0] += 1
                try:
                    wid = int(c.cget("width") or 0)
                except (TypeError, ValueError):
                    wid = 0
                if txt and wid > 0:
                    LABELS[0] += 1
                    if wid * unit < f.measure(txt):
                        check("标签装得下 %r" % txt, False,
                              "声明宽 %d 字 ≈%dpx，需要 %dpx"
                              % (wid, wid * unit, f.measure(txt)))
            walk(c)
    walk(app.tab_actor)
    print("  遍历标签 %d 个；其中声明 width 的 %d 个，全部装得下"
          % (ALL_LABELS[0], LABELS[0]))
    # 2026-09-14 起角色页标签改成自适应（不带 width），宽度检查只剩条件兜底；
    # 递归是否走到底改用「标签总数」验证。
    check("递归确实走到底（遍历到标签）", ALL_LABELS[0] > 0,
          "%d 个" % ALL_LABELS[0])

    # ---- 2) 字段布局：累计获得经验不再给输入框；概览是左右布局的一块
    print("\n--- 2) 字段与左右布局 ---")
    check("基础字段没有 @limit_exp（改它没意义）",
          "@limit_exp" not in app.actor_vars, "%r" % list(app.actor_vars))
    check("基础字段 = 名字/等级/气血/魔法/愤怒/获得经验/升级经验",
          list(app.actor_vars) == ["@name", "#level", "@hp", "@mp", "@tp",
                                   "@exp", "#next_exp"],
          "%r" % list(app.actor_vars))
    check("等级行只读（#level 不是可写的 @level）",
          "@level" not in app.actor_vars and "#level" in app.actor_vars)
    check("只读等级行读得出存档里的等级",
          app.actor_vars["#level"].get()
          == str(app.sv.actor_field(app.current_actor(), "@level")),
          app.actor_vars["#level"].get())
    check("「改级别时同步获得经验」勾选也已移除",
          not hasattr(app, "var_sync_exp"))
    check("「属性概览」的容器挂在 PanedWindow 里（左右布局）",
          "TPanedwindow" in _ancestor_classes(root, app.txt_actor),
          "祖先=%r" % _ancestor_classes(root, app.txt_actor))
    check("概览和基础字段不是同一个父容器（确实分了左右）",
          app.txt_actor.winfo_parent() != app._actor_entry_parent,
          "概览父=%s  字段父=%s"
          % (app.txt_actor.winfo_parent(), app._actor_entry_parent))
    check("没有残留的 var_limit_tip（提示改成浮窗了）",
          not hasattr(app, "var_limit_tip"))
    check("没有残留的「清零」按钮（不在基础字段里了）",
          "清零" not in app.actor_vars)

    # ---- 3) 概览浮窗提醒
    print("\n--- 3) 属性概览 + 悬浮提醒 ---")
    for iid in app.tv_actor.get_children():
        app.tv_actor.selection_set(iid)
        app.load_actor()
        root.update()
        nm = app.actor_vars["@name"].get()
        note = getattr(app, "_actor_tip_note", "")
        body = app.txt_actor.get("1.0", "end")
        print("  %-6s 获得经验=%-12s 升级经验=%-9s 浮窗 %d 字"
              % (nm, app.actor_vars["@exp"].get(),
                 app.actor_vars["#next_exp"].get(), len(note)))
        print("        浮窗首行: %s" % note.split("\n")[0])
        check("%s 概览正文有名字" % nm, ("名字：%s" % nm) in body)
        # ⚠ 玩家的档一直在变（脚本跑的时候游戏可能正开着、刚存过档）：角色会从
        # 「普通升级进度」变成「封顶 / 满级」，所以提醒内容必须按**当前**等级与
        # 封顶状态算，不能按角色名写死。2026-09-20 就被这个坑过一次 —— 老断言
        # 写死「乐天凌 / 仙灵儿 = 普通进度」，而档里两人早涨到满级了，直接 NG。
        _a_cur = app.current_actor()
        _lvn = app.g.actor_level(_a_cur)
        _gate = not app.g.limit_exp_on(_a_cur)
        if _lvn >= game.MAX_LEVEL_ACTOR:
            _want = "已满级"
        elif _gate:
            _want = "已超过"
        else:
            _want = "还差"
        check("%s：浮窗提醒与当前状态一致（%s）" % (nm, _want), _want in note,
              note.split("\n")[0])
        check("%s：浮窗给了下一步的提示" % nm,
              "经验拉满" in note if _lvn >= game.MAX_LEVEL_ACTOR
              else "获得经验" in note)
        if nm == "乐天凌":
            check("乐天凌：概览正文的「已封顶」与真实状态一致",
                  ("已封顶" in body) == _gate, "gate=%s" % _gate)

    # ---- 4) 悬浮真能弹出浮窗（模拟 <Motion>）
    print("\n--- 4) 悬浮真的弹窗 ---")
    rid = None
    for iid in app.tv_actor.get_children():
        app.tv_actor.selection_set(iid)
        app.load_actor()
        root.update()
        if app.actor_vars["@name"].get() == "乐天凌":
            rid = iid
            break
    if rid is None:
        check("找到乐天凌", False)
    else:
        app.tv_actor.selection_set(rid)
        app.load_actor()
        root.update()
        ev = type("E", (), {"x": 10, "y": 10})()
        app._actor_tip_motion(ev)
        root.update()
        win = getattr(app, "_tip_win", None)
        txt = ""
        if win is not None:
            for c in win.winfo_children():
                txt += c.cget("text") or ""
        check("鼠标移动弹出了浮窗", win is not None)
        # 提醒内容按实际等级选（满级优先于封顶，见上面调色的那段说明）
        _want = ("已满级"
                 if app.g.actor_level(app.current_actor())
                 >= game.MAX_LEVEL_ACTOR else "已超过")
        check("浮窗里是乐天凌那段提醒", _want in txt,
              txt.split("\n")[0][:40])
        # 再动一次不该重建（防闪烁靠 _tip_key）
        first = app._tip_win
        app._actor_tip_motion(ev)
        check("同一目标上再移动不重建浮窗（防闪烁）",
              app._tip_win is first)
        app._tip_hide()
        root.update()
        check("移开后浮窗消失", getattr(app, "_tip_win", None) is None
              and getattr(app, "_tip_key", None) is None)

    # ---- 5) 「经验拉满」：等级顶到 60 + 获得经验对齐 + 潜能/五维补齐
    print("\n--- 5) 经验拉满（等级 + 获得经验 + 潜能/五维）---")
    rid5 = None
    for iid in app.tv_actor.get_children():
        app.tv_actor.selection_set(iid)
        app.load_actor()
        root.update()
        if app.actor_vars["@name"].get() == "乐天凌":
            rid5 = iid
            break
    if rid5 is None:
        check("找到乐天凌", False)
    else:
        app.tv_actor.selection_set(rid5)
        app.load_actor()
        root.update()
        a = app.current_actor()
        print("  目标角色 = %s（id=%s）" % (app.sv.actor_name(a), rid5))
        _guard_real_save(app, paths.save_path())     # 写之前再确认一次
        WARNS.clear()
        # ⚠ 玩家的真档一直在变（角色可能早满级了），所以先**用语义层压回 20 级**
        # 再点按钮 —— 否则「等级到了 60」在满级角色上永远是空断言，测不出东西。
        # 降级会洗点（_apply_level_delta 的既有语义），正好用来验证 +5 潜能/+1 五维。
        app.g.set_actor_level_full(a, 20)
        app.load_actor()
        root.update()
        pot0 = dict(app.sv.attr_items(a)).get("@潜能") or 0
        tz0 = dict(app.sv.attr_items(a)).get("@体质") or 0
        check("先把等级压回 20 级（准备测拉满）", app.g.actor_level(a) == 20,
              str(app.g.actor_level(a)))
        app.actor_preset("expfull")
        root.update()
        want_exp = game.exp_for_level(game.MAX_LEVEL_ACTOR, "actor")
        pot1 = dict(app.sv.attr_items(a)).get("@潜能") or 0
        tz1 = dict(app.sv.attr_items(a)).get("@体质") or 0
        print("  写回后：等级=%s  获得经验=%s（期望 %s）  潜能 %s→%s  体质 %s→%s"
              % (app.g.actor_level(a), app.g.exp(a), want_exp, pot0, pot1,
                 tz0, tz1))
        check("等级真的到了满级（%d）" % game.MAX_LEVEL_ACTOR,
              app.g.actor_level(a) == game.MAX_LEVEL_ACTOR)
        check("获得经验对齐到满级门槛", app.g.exp(a) == want_exp, str(app.g.exp(a)))
        check("升的 40 级补了 200 点潜能（+5/级）", pot1 - pot0 == 40 * 5,
              "%s → %s" % (pot0, pot1))
        check("升的 40 级补了 40 点五维（+1/级）", tz1 - tz0 == 40,
              "%s → %s" % (tz0, tz1))
        check("概览里的等级跟着更新",
              "级别：%d" % game.MAX_LEVEL_ACTOR in app.txt_actor.get("1.0", "end"))
        sel = app.tv_actor.selection()
        check("改完没跳回第一个角色（选中行保持）",
              bool(sel) and sel[0] == rid5,
              "选中=%s 期望=%s" % (sel[0] if sel else None, rid5))
        app.tv_actor.selection_set(rid5)
        app.load_actor()
        root.update()
        check("浮窗提醒切到「已满级」分支",
              "已满级" in getattr(app, "_actor_tip_note", ""))

    # ---- 6) 清零按钮（现在从哪调？确认还能用）
    print("\n--- 6) 清零累计获得经验 ---")
    _guard_real_save(app, paths.save_path())
    WARNS.clear()
    app.actor_reset_limit_exp()
    root.update()
    left = [(app.sv.actor_name(a), app.g.limit_exp(a))
            for _i, a in app.sv.actors()]
    check("清零后各角色累计都为 0", all(v == 0 for _n, v in left),
          "%r" % left)

    # ---- 7) 角色技能编辑区（2026-09-20 新增）
    print("\n--- 7) 角色技能编辑区 ---")
    _guard_real_save(app, paths.save_path())
    check("技能一览挂在 PanedWindow 里（和概览上下分栏）",
          "TPanedwindow" in _ancestor_classes(root, app.tv_actor_skills),
          "祖先=%r" % _ancestor_classes(root, app.tv_actor_skills))
    check("技能一览和概览不是同一个容器",
          app.tv_actor_skills.winfo_parent() != app.txt_actor.winfo_parent())
    check("SkillPicker 确实绑在这套控件上",
          app.skp_actor.tree is app.tv_actor_skills)
    check("按钮拿到的是角色版方法（不是召唤兽的）",
          app.actor_skill_add.__self__ is app
          and app.actor_skill_add.__func__ is not app.baby_skill_add.__func__)

    # 一一对上：每个角色的一览都要等于存档里的 @skills
    off = []
    for iid in app.tv_actor.get_children():
        app.tv_actor.selection_set(iid)
        app.load_actor()
        root.update()
        a = app.current_actor()
        rows = [int(app.tv_actor_skills.item(r, "values")[1])
                for r in app.tv_actor_skills.get_children()]
        if rows != app.g.actor_skills(a):
            off.append((app.sv.actor_name(a), rows, app.g.actor_skills(a)))
    check("每个角色的技能一览都等于存档 @skills", not off, "%r" % (off[:1],))

    iid0 = app.tv_actor.get_children()[0]
    app.tv_actor.selection_set(iid0)
    app.load_actor()
    root.update()
    a = app.current_actor()
    base = list(app.g.actor_skills(a))
    nm = app.skp_actor.names()
    fresh = [i for i in sorted(nm) if i not in base]
    print("  目标角色 = %s，原有技能 %d 个；候选新技能 %d 个"
          % (app.sv.actor_name(a), len(base), len(fresh)))
    if fresh:
        _guard_real_save(app, paths.save_path())
        app.var_actor_skill_pick.set("#%d %s" % (fresh[0], nm[fresh[0]]))
        app.actor_skill_add()
        root.update()
        rows = [app.tv_actor_skills.item(r, "values")[1]
                for r in app.tv_actor_skills.get_children()]
        check("界面「学会」后一览里出现了新技能", str(fresh[0]) in rows,
              "%r" % (rows[:4],))
        check("角色技能没有召唤兽那 12 个上限（学会 = +1）",
              len(app.g.actor_skills(a)) == len(base) + 1,
              "%d -> %d" % (len(base), len(app.g.actor_skills(a))))
        check("重新载入角色后技能没丢",
              fresh[0] in app.g.actor_skills(app.current_actor()))
        app.tv_actor_skills.selection_set("sk%d" % fresh[0])
        app.actor_skill_del()
        root.update()
        check("界面「忘掉」后回到原样",
              app.g.actor_skills(a) == sorted(set(base)),
              "%r" % (app.g.actor_skills(a),))
    else:
        check("有没学过的技能可用于测试", False)

    if app.tv_actor_skills.get_children():
        app.tv_actor_skills.selection_set(app.tv_actor_skills.get_children()[0])
        app.skp_actor.show_desc()
        root.update()
        d = app.txt_actor_skill_desc.get("1.0", "end").strip()
        check("选中技能行后说明框有内容", d != "", d[:44])
        check("技能一览是 序 / id / 名字三列",
              tuple(app.tv_actor_skills["columns"]) == ("no", "id", "name"))

    # 技能一览被清空时说明框也要跟着清（换到没技能的角色不该留着上一个人的说明）
    app.skp_actor.set_desc("")
    check("说明框能清空",
          app.txt_actor_skill_desc.get("1.0", "end").strip() == "")

    # ---- 8) 门派技能勾选清单 + 一键学习（2026-09-20 新增；2026-09-23 改语义）
    #   勾选框从「一键学习的输入」改成**直接开关**：勾上＝学会、取消＝忘掉，
    #   点一下立刻改写 @skills 并标 dirty。
    print("\n--- 8) 门派技能（勾上＝学会 / 取消＝忘掉）---")
    _guard_real_save(app, paths.save_path())
    WARNS.clear()
    rid8 = None
    for iid in app.tv_actor.get_children():
        app.tv_actor.selection_set(iid)
        app.load_actor()
        root.update()
        if app.g.sect_skills(app.current_actor()):
            rid8 = iid
            break
    if rid8 is None:
        check("找一个有门派的角色", False)
    else:
        app.tv_actor.selection_set(rid8)
        app.load_actor()
        root.update()
        a = app.current_actor()
        sids = list(app._learn_sids)
        print("  角色 = %s，门派 = %s，左栏 %d 个"
              % (app.sv.actor_name(a), app.var_actor_sect.get(), len(sids)))
        check("换角色后门派下拉自动站到 TA 的门派",
              app.var_actor_sect.get() == app.g.actor_sect_name(a),
              app.var_actor_sect.get())
        check("左栏列出的就是该门派的全部技能",
              sids == list(sect.sect_skill_ids(app.g.actor_sect_id(a))),
              "%d 个" % len(sids))
        boxes = [w for w in app.learn_grid.winfo_children()
                 if w.winfo_class() == "TCheckbutton"]
        check("每个技能一个勾选框", len(boxes) == len(sids),
              "%d 个框 / %d 个技能" % (len(boxes), len(sids)))
        check("勾选框都挂了悬停介绍（浮窗）",
              all(w.bind("<Enter>") for w in boxes),
              "%d / %d" % (len([w for w in boxes if w.bind("<Enter>")]),
                           len(boxes)))
        known0 = set(app.g.actor_skills(a))
        # 2026-09-23：勾选框不再是「一键学习」的输入，而是**直接开关** ——
        # 勾上＝已学（不再 disabled、「（已学）」后缀也去掉）。川反馈的
        # 「勾选/取消勾选后点保存说没改动」就出在旧语义上。
        check("勾选状态 = 存档真值（已学＝勾上）",
              all(app.learn_vars[s].get() == (1 if s in known0 else 0)
                  for s in sids),
              "%r" % [(s, app.learn_vars[s].get()) for s in sids])
        check("没有一个是禁用状态（已学的也能取消勾选）",
              not [w for w in boxes if w.instate(("disabled",))],
              "%d / %d 个禁用"
              % (len([w for w in boxes if w.instate(("disabled",))]), len(boxes)))
        check("勾选框都挂上了真回调（点一下就改写 @skills）",
              all(w.cget("command") for w in boxes))

        # 全清 → 10 个都空着
        app.g.actor_clear_skills(a)
        app.load_actor()
        root.update()
        check("清空技能后 10 个都空着",
              app.g.actor_skills(a) == []
              and len(app._learn_sids) == len(sids)
              and all(v.get() == 0 for v in app.learn_vars.values()),
              "%r" % app.g.actor_skills(a))

        # 点一个勾选框 → 立刻只学那一个（不再需要点「一键学习」）
        _guard_real_save(app, paths.save_path())
        one = app._learn_sids[0]
        app.doc.dirty = False      # 只清「未保存」标记（clear_dirty 只管窗口标题）
        app.learn_vars[one].set(1)
        app.actor_toggle_sect_skill(one)
        root.update()
        check("勾一个 → 立刻只学会那一个",
              app.g.actor_skills(a) == [one], "%r" % app.g.actor_skills(a))
        check("勾一下立刻标 dirty（保存不再说「没有改动」）", app.doc.dirty,
              "structural=%s" % app.doc.structural)

        # 再取消勾选 → 立刻忘掉
        app.learn_vars[one].set(0)
        app.actor_toggle_sect_skill(one)
        root.update()
        check("取消勾选 → 立刻忘掉", app.g.actor_skills(a) == [],
              "%r" % app.g.actor_skills(a))

        # 已学过的也能取消（旧版把它禁用了，压根点不动）
        app.g.actor_learn_skill(a, one)
        app.load_actor()
        root.update()
        app.learn_vars[one].set(0)
        app.actor_toggle_sect_skill(one)
        root.update()
        check("已学过的取消勾选 → 忘掉（新增能力）",
              one not in app.g.actor_skills(a), "%r" % app.g.actor_skills(a))

        # 「一键学习」= 把本门派没学的补齐（不再弹确认）
        app.g.actor_clear_skills(a)
        app.load_actor()
        root.update()
        _guard_real_save(app, paths.save_path())
        app.actor_learn_checked()
        root.update()
        check("「一键学习」= 补齐本门派没学的",
              app.g.actor_skills(a) == sorted(sids),
              "%r" % app.g.actor_skills(a))
        # 没选门派（空串，如无门派角色）→ 列不出清单，只给提示
        app.var_actor_sect.set("")
        app.rebuild_learn_grid()
        root.update()
        check("没选门派时清单清空并给出提示",
              app._learn_sids == [] and "门派" in app.var_learn_note.get(),
              app.var_learn_note.get())

    # ---- 9) 「重置潜力/属性」（2026-09-20 新增 = 游戏里「拜师」那一下的洗点）
    print("\n--- 9) 重置潜力/属性（洗点）---")
    _guard_real_save(app, paths.save_path())
    WARNS.clear()
    _btnw = {}

    def _collect_btn(w):
        for c in w.winfo_children():
            if c.winfo_class() == "TButton":
                _btnw.setdefault(c.cget("text"), c)
            _collect_btn(c)

    _collect_btn(app.tab_actor)
    check("角色页有「重置潜力/属性」按钮", "重置潜力/属性" in _btnw,
          "、".join(_btnw))
    # ⚠ 必须和「应用修改」**同一行**：左栏是竖向 pack，多一行就多一分被裁的风险
    #   （2026-09-20「一键学习」就是这么被裁掉的）。
    check("它和「应用修改」在同一行（不新起一行 → 不会被裁）",
          "重置潜力/属性" in _btnw and "应用修改" in _btnw
          and _btnw["重置潜力/属性"].master is _btnw["应用修改"].master)

    ATTR5 = ("@体质", "@法力", "@力量", "@耐力", "@敏捷")
    OTHERS = ("@人气", "@贡献", "@体力", "@活力")
    for iid in app.tv_actor.get_children():
        app.tv_actor.selection_set(iid)
        app.load_actor()
        root.update()
        a = app.current_actor()
        lv = app.g.actor_level(a)
        d0 = dict(app.sv.attr_items(a))
        five0 = [d0.get(k) for k in ATTR5]
        app.actor_preset("reset_attr")
        root.update()
        d1 = dict(app.sv.attr_items(a))
        five1 = [d1.get(k) for k in ATTR5]
        base, pot = 20 + lv - 1, lv * 5
        check("%s 洗点：五维→%d×5、潜能→%d"
              % (app.sv.actor_name(a), base, pot),
              five1 == [base] * 5 and d1.get("@潜能") == pot,
              "%r / 潜能 %r（洗前 %r）" % (five1, d1.get("@潜能"), five0))
        check("%s 洗点后五维和 ≤ 反作弊线（只降不升）" % app.sv.actor_name(a),
              app.g.point_num(a) <= lv * 10 + 500,
              "%s / %s" % (app.g.point_num(a), lv * 10 + 500))
        # 洗点不该碰跟加点无关的字段（游戏的 reset_point 也不碰）
        check("%s 洗点不碰 人气/贡献/体力/活力" % app.sv.actor_name(a),
              [d1.get(k) for k in OTHERS] == [d0.get(k) for k in OTHERS],
              "%r → %r" % ([d0.get(k) for k in OTHERS],
                           [d1.get(k) for k in OTHERS]))

    # ---- 10) 改门派（2026-09-27 新增：「转门派」按钮 = 只写 @sect_id）
    #   查证见 `docs/门派修改可行性.md`：门派就一个整数，`@skills`/`@sect_data`
    #   都不动（游戏里换门派也这样，learn_skill 从不清理旧技能）。
    print("\n--- 10) 改门派 ---")
    _guard_real_save(app, paths.save_path())
    WARNS.clear()
    _btnw2 = {}

    def _collect_btn2(w):
        for c in w.winfo_children():
            if c.winfo_class() == "TButton":
                _btnw2.setdefault(c.cget("text"), c)
            _collect_btn2(c)

    _collect_btn2(app.tab_actor)
    check("角色页有「转门派」按钮", "转门派" in _btnw2, "、".join(_btnw2))
    check("它和「一键学习」同一行（左栏竖向 pack，多一行就有被裁的风险）",
          "转门派" in _btnw2 and "一键学习" in _btnw2
          and _btnw2["转门派"].master is _btnw2["一键学习"].master)
    check("下拉共 13 项、含「无门派」（2026-09-27 川要求放进去）",
          len(huaji2_save_editor.sect_choice_labels()) == 13
          and "无门派" in huaji2_save_editor.sect_choice_labels(),
          "、".join(huaji2_save_editor.sect_choice_labels()[:3]) + "…")

    rid10 = None
    for iid in app.tv_actor.get_children():
        app.tv_actor.selection_set(iid)
        app.load_actor()
        root.update()
        if app.g.sect_skills(app.current_actor()):
            rid10 = iid
            break
    if rid10 is None:
        check("找一个有门派的角色", False)
    else:
        app.tv_actor.selection_set(rid10)
        app.load_actor()
        root.update()
        a = app.current_actor()
        old_id = app.g.actor_sect_id(a)
        new_id = 11 if old_id != 11 else 3
        old_sk = tuple(app.g.actor_skills(a))
        old_lv = app.g.actor_level(a)
        old_five = dict(app.sv.attr_items(a))
        app.doc.dirty = False
        app.var_actor_sect.set(sect.sect_name(new_id))
        WARNS.clear()
        app.actor_set_sect()                    # 桩 askyesno 恒 True
        root.update()
        check("点「转门派」→ @sect_id 变成下拉那个门派",
              app.g.actor_sect_id(a) == new_id,
              "%s(%s) → %s(%s)" % (old_id, sect.sect_name(old_id), new_id,
                                   sect.sect_name(new_id)))
        check("→ 标脏（保存不再说「没有改动」）", app.doc.dirty)
        check("→ 属性文本那行显示新门派",
              sect.sect_name(new_id) in app.txt_actor.get("1.0", "end"),
              sect.sect_name(new_id))
        check("→ 角色列表「门派」列跟着变",
              app.tv_actor.item(rid10, "values")[3] == sect.sect_name(new_id),
              app.tv_actor.item(rid10, "values")[3])
        check("→ 下拉停在用户选的门派上（没被抢回旧的）",
              app.var_actor_sect.get() == sect.sect_name(new_id),
              app.var_actor_sect.get())
        check("→ @skills 一个都没变（游戏也不清理旧门派技能）",
              tuple(app.g.actor_skills(a)) == old_sk, "%d 个" % len(old_sk))
        check("→ 等级/五维也没动",
              app.g.actor_level(a) == old_lv
              and dict(app.sv.attr_items(a)) == old_five, "Lv%s" % old_lv)
        check("→ 本门派技能清单换成新门派那 10 个",
              list(app._learn_sids) == list(sect.sect_skill_ids(new_id)),
              "%d 个" % len(app._learn_sids))
        app.doc.dirty = False
        WARNS.clear()
        app.actor_set_sect()                    # 同一个门派再点一次
        root.update()
        check("同一门派再点一次 → 只说「无需改动」、不标脏",
              (not app.doc.dirty) and "无需" in app.var_status.get(),
              app.var_status.get()[:50])
        try:
            app.g.set_actor_sect(a, 13)
            _raised = False
        except ValueError:
            _raised = True
        check("⚠ 越界 13 被挡下来（真写进去游戏会崩菜单）",
              _raised and app.g.actor_sect_id(a) == new_id,
              "抛 ValueError=%s" % _raised)
        check("能改回原门派（可逆）",
              app.g.set_actor_sect(a, old_id) == old_id
              and app.g.actor_sect_id(a) == old_id, str(app.g.actor_sect_id(a)))

        # ---- 10.05) 称谓（@appellations）：2026-09-27 川指出「转门派/清空门派
        #   并没有转换对应称谓或者回收称谓」。存档里 = `[[称谓...], 下标]`。
        stale_name = sect_appellation.sect_appellation(1 if old_id != 1 else 2)
        app.g.set_actor_appellations(a, [stale_name, "内测人员"], 0)
        app.load_actor()
        root.update()
        _txt10 = app.txt_actor.get("1.0", "end")
        check("属性文本里有「称谓：」那一行", "称谓：" in _txt10,
              "、".join(l for l in _txt10.split("\n") if "称谓" in l))
        check("→ 称谓和门派对不上时直接提醒（川报的就是这个）",
              "不是当前门派的" in _txt10,
              "、".join(l for l in _txt10.split("\n") if "称谓" in l)[:60])
        app.doc.dirty = False
        WARNS.clear()
        app.var_actor_sect.set(sect.sect_name(new_id))
        app.actor_set_sect()
        root.update()
        _ap, _ai = app.g.actor_appellations(a)
        _want = sect_appellation.sect_appellation(new_id)
        check("点「转门派」→ 回收旧门派称谓、发新门派那个",
              stale_name not in _ap and _want in _ap, "%s" % (_ap,))
        check("→ 非门派称谓（内测人员）不被误删", "内测人员" in _ap, "%s" % (_ap,))
        check("→ 原来显示的就是门派称谓 → 下标跟到新称谓上",
              _ap[_ai] == _want if 0 <= _ai < len(_ap) else False,
              "idx=%s %s" % (_ai, _ap))
        check("→ 标脏", app.doc.dirty)
        check("→ 确认框里写了称谓怎么变",
              any(w[0] == "ask" and "称谓" in w[1][1] for w in WARNS),
              "、".join(w[1][1].replace("\n", " / ") for w in WARNS
                        if w[0] == "ask")[:70])
        # 真档里就有这种：门派对、称谓错（秦媚儿：女儿村 却挂着「地府弟子」）
        _sid_now = app.g.actor_sect_id(a)
        app.g.set_actor_appellations(a, ["地府弟子"], 0)
        app.doc.dirty = False
        WARNS.clear()
        app.var_actor_sect.set(sect.sect_name(_sid_now))
        app.actor_set_sect()
        root.update()
        check("门派对、称谓错 → 点「转门派」也能对齐（不被「已无需改动」挡掉）",
              app.g.actor_appellations(a) == ([_want], 0) and app.doc.dirty,
              "%r" % (app.g.actor_appellations(a),))
        check("→ @sect_id 没被白写回同一个值以外的东西",
              app.g.actor_sect_id(a) == _sid_now, str(app.g.actor_sect_id(a)))
        app.g.set_actor_sect(a, old_id)        # 还原，后面 10.1 从原门派开
        app.load_actor()
        root.update()

        # ---- 10.1) 清空门派（2026-09-27）：写 @sect_id = 0 **并且**把技能重置成
        #   职业天生技能（= 游戏 `clear_skills` + `init_skills`）。
        #   ⚠ 和「转门派」是**两条不同的路**（川 260927 22:5x 定）：
        #   清技能只归这个按钮；下拉里选「无门派」+「转门派」只改门派、技能不动。
        check("「清空门派」按钮在同一行（不再多占一行高度）",
              "清空门派" in _btnw2 and "转门派" in _btnw2
              and _btnw2["清空门派"].master is _btnw2["转门派"].master,
              "、".join(_btnw2))
        check("下拉里仍然有「无门派」（0 既有按钮也可选下拉）",
              "无门派" in huaji2_save_editor.sect_choice_labels(),
              "%d 项" % len(huaji2_save_editor.sect_choice_labels()))
        app.tv_actor.selection_set(rid10)
        app.load_actor()
        root.update()
        a = app.current_actor()
        check("清空前：角色是有门派的", app.g.actor_sect_id(a) == old_id,
              str(app.g.actor_sect_id(a)))
        innate0 = set(app.g.actor_class_learnings(a))
        sk0 = tuple(app.g.actor_skills(a))
        lv0 = app.g.actor_level(a)
        five0 = dict(app.sv.attr_items(a))
        extra = [s for s in sect.sect_skill_ids(old_id) if s not in innate0]
        check("清空前：有非天生技能可清（否则这条用例没意义）",
              bool(extra) and bool(set(sk0) - innate0),
              "%d 个技能，其中非天生 %d 个" % (len(sk0), len(set(sk0) - innate0)))
        app.doc.dirty = False
        WARNS.clear()
        app.actor_clear_sect()                  # 桩 askyesno 恒 True
        root.update()
        check("点「清空门派」→ @sect_id 变成 0", app.g.actor_sect_id(a) == 0,
              "@sect_id=%s" % app.g.actor_sect_id(a))
        check("→ 标脏", app.doc.dirty)
        check("→ 属性文本显示「无门派」",
              "无门派" in app.txt_actor.get("1.0", "end"),
              "、".join(l for l in app.txt_actor.get("1.0", "end").split("\n")
                        if "门派" in l))
        check("→ 角色列表「门派」列 = 无门派",
              app.tv_actor.item(rid10, "values")[3] == "无门派",
              app.tv_actor.item(rid10, "values")[3])
        check("→ 下拉同步成「无门派」（下拉里有这一项了）",
              app.var_actor_sect.get() == "无门派",
              "%r" % app.var_actor_sect.get())
        check("→ 左栏清单收起 + 提示「这个角色没有门派」",
              list(app._learn_sids) == [] and "没有门派" in app.var_learn_note.get(),
              app.var_learn_note.get()[:40])
        check("→ @skills 被重置成职业天生技能（工具额外做的）",
              set(app.g.actor_skills(a)) == innate0,
              "%d 个 → %d 个" % (len(sk0), len(app.g.actor_skills(a))))
        check("→ 门派称谓也被回收（2026-09-27 第三轮）",
              not app.g.sect_appellations_of(a)
              and "地府弟子" not in app.g.actor_appellations(a)[0],
              "%s" % (app.g.actor_appellations(a),))
        check("→ 天生技能一个没丢",
              bool(innate0) and innate0 <= set(app.g.actor_skills(a)),
              "、".join("#%d" % s for s in sorted(innate0)))
        check("→ 非天生技能全清（门派技能 / 技能书学的都算）",
              not (set(sk0) - innate0) & set(app.g.actor_skills(a)),
              "清了 %d 个" % len(set(sk0) - innate0))
        _ask = [w for w in WARNS if w[0] == "ask"]
        _txt = _ask[0][1][1] if _ask else ""
        check("→ 确认框写明了技能怎么变 + 「游戏自己换门派不会清技能」",
              "技能" in _txt and "不会清技能" in _txt,
              _txt.replace("\n", " / ")[:80])
        check("→ 等级/五维也没动",
              app.g.actor_level(a) == lv0
              and dict(app.sv.attr_items(a)) == five0, "Lv%s" % lv0)
        app.doc.dirty = False
        WARNS.clear()
        app.actor_clear_sect()                  # 已无门派 + 只剩天生 → 再点一次
        root.update()
        check("已无门派且技能只剩天生 → 只说「无需改动」、不标脏、不弹窗",
              (not app.doc.dirty) and "无需" in app.var_status.get()
              and not WARNS, app.var_status.get()[:50])
        # 已无门派、但技能里还挂着非天生（真档里就有这种角色）→ 仍然要能清
        app.g.actor_learn_skill(a, extra[0])
        app.load_actor()
        root.update()
        app.doc.dirty = False
        WARNS.clear()
        app.actor_clear_sect()
        root.update()
        check("已经无门派但技能里还有门派技能 → 再点一次能清掉",
              app.g.actor_sect_id(a) == 0
              and set(app.g.actor_skills(a)) == innate0 and app.doc.dirty,
              "%d 个技能" % len(app.g.actor_skills(a)))
        # 下拉里选「无门派」+「转门派」= **只改门派**，技能一个不动
        # （川 260927 22:5x 定：「无门派不清技能，清空门派才清技能」→ 两路拆开）
        app.g.set_actor_sect(a, old_id)
        app.g.actor_learn_skill(a, extra[0])
        app.load_actor()
        root.update()
        app.var_actor_sect.set("无门派")
        _sk_drop = tuple(app.g.actor_skills(a))
        app.doc.dirty = False
        WARNS.clear()
        app.actor_set_sect()
        root.update()
        check("下拉选「无门派」+「转门派」→ @sect_id 变成 0",
              app.g.actor_sect_id(a) == 0 and app.doc.dirty,
              "@sect_id=%s" % app.g.actor_sect_id(a))
        check("→ **技能一个不动**（清技能只归「清空门派」）",
              tuple(app.g.actor_skills(a)) == _sk_drop,
              "%d 个技能；清空门派那条路会变成 %d 个"
              % (len(app.g.actor_skills(a)), len(innate0)))
        check("→ 弹的是「改门派」那个框（不再借「清空门派」的框）",
              any(w[0] == "ask" and w[1][0] == "改门派" for w in WARNS)
              and not any(w[0] == "ask" and w[1][0] == "清空门派" for w in WARNS),
              "、".join(w[1][0] for w in WARNS if w[0] == "ask"))
        _txt0 = " ".join(w[1][1] for w in WARNS if w[0] == "ask")
        check("→ 确认框写明「技能一个不动」+ 指路「清空门派」",
              "技能一个不动" in _txt0 and "清空门派" in _txt0,
              _txt0.replace("\n", " / ")[:90])
        check("→ 状态栏也说技能没动、要重置去点「清空门派」",
              "技能没动" in app.var_status.get()
              and "清空门派" in app.var_status.get(),
              app.var_status.get()[:60])
        # 而「清空门派」这条独立入口：仍然要把技能重置成天生技能
        app.g.set_actor_sect(a, old_id)
        app.load_actor()
        root.update()
        app.doc.dirty = False
        WARNS.clear()
        app.actor_clear_sect()
        root.update()
        check("「清空门派」仍然连技能一起重置（两条路各管各的）",
              app.g.actor_sect_id(a) == 0
              and set(app.g.actor_skills(a)) == innate0 and app.doc.dirty,
              "%d 个技能" % len(app.g.actor_skills(a)))
        # 弹窗点「否」→ 一个字都不写（技能也必须没动）
        app.g.set_actor_sect(a, old_id)
        app.load_actor()
        root.update()
        _sk_before = tuple(app.g.actor_skills(a))
        app.doc.dirty = False
        WARNS.clear()
        MB_STUB["answer"] = False
        app.actor_clear_sect()
        root.update()
        MB_STUB["answer"] = True
        check("弹窗点「否」→ 门派/技能都没动、也没标脏",
              app.g.actor_sect_id(a) == old_id and not app.doc.dirty
              and tuple(app.g.actor_skills(a)) == _sk_before,
              "@sect_id=%s dirty=%s 技能 %d 个"
              % (app.g.actor_sect_id(a), app.doc.dirty,
                 len(app.g.actor_skills(a))))
        # 清空之后还能正常转门派（下拉/按钮都还活着）
        app.doc.dirty = False
        WARNS.clear()
        app.actor_clear_sect()
        root.update()
        app.var_actor_sect.set(sect.sect_name(old_id))
        app.actor_set_sect()
        root.update()
        check("清空后还能用「转门派」转回来（技能不再回滚，只改 @sect_id）",
              app.g.actor_sect_id(a) == old_id and app.doc.dirty
              and set(app.g.actor_skills(a)) == innate0,
              "%s → %s / %d 个技能"
              % (0, app.g.actor_sect_id(a), len(app.g.actor_skills(a))))

    app.root.destroy()
    shutil.rmtree(WORK, ignore_errors=True)
    print("\n==== 检查 %d 项，问题 %d 项 ====" % (CHECKED[0], BAD[0]))
    return 1 if BAD[0] else 0


if __name__ == "__main__":
    sys.exit(main())
