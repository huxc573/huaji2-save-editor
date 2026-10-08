# -*- coding: utf-8 -*-
"""一次性探针：**改角色门派**（只碰副本存档）—— 查证结论 + 已做入口的验收。

先查可行性（A/B/C 段，纯语义层），再验已实现的界面入口（D/E 段）：
角色页左栏「门派技能」那一行加了「**转门派**」按钮 → 点它把当前角色的门派
改成下拉里选的那个（只写 `@sect_id`，走 `GameEditor.set_actor_sect()`）。

要回答的问题：门派到底存在哪、改了会不会带出别的问题、游戏会不会崩。

查证结论（本探针会锁住）：
  · 门派**只存一个整数** `@sect_id`（游戏脚本 5484 `attr_accessor`，初值 0 见 5512），
    `$sects[id] = {name:, skills:[{id:,lv:,max:}]}` —— 全脚本只有 11 处读它，
    没有任何一处**写**它（换门派是事件脚本干的）→ 工具写它是「照游戏自己的机制办」。
  · `@sect_data`（`:门派` 攒次数 / `:辅助` 6 项 / `:修炼` 8 项）**与门派无关**：
    辅助/修炼的键每个门派都一模一样，只是数值。改门派**不用动它**。
  · `@skills` 也**不用动**：`Game_Actor#learn_skill`(6017) 只 push+排序、从不清理，
    换门派后旧门派技能会留着（真档李修远：五庄观却有女儿村/普陀山技能）。
  · 作弊检测 `$jiance`(29455) 只看 等级/召唤兽等级/金钱/仓库页 → **不查门派、不查技能**。
  · ⚠ 唯一的红线：`$sects[actor.sect_id]` 是**普通 Hash，没有 default** ——
    写 14/负数这种不存在的 id，游戏一开菜单就 `nil[:name]` 崩。
  ⚠ 2026-10-04 起表是 `0`、`1..13`、**`20`**（九黎城）—— **不连号**，
  所以实现只能**查表**校验（写 13 现在是合法的「凌波城」，越界例子改用 14）。

用系统 Python 3.12（有 tkinter）。窗口全程 withdraw —— 不抢前台、不动鼠标。

    XJ_PY=<py312> python tests/probe_sect_change.py

⚠ 老坑：`Doc.save()` 写盘后会重新解析整棵树 → 保存之后的读写都要重新取节点。
"""
import hashlib
import io
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import paths                                                      # noqa: E402
REAL = os.path.join(paths.find_game_dir(), "save.rvdata2")
COPY = os.path.join(ROOT, "_tmp", "probe_sect_change.rvdata2")

OK = [0, 0]
MSGS = []


def check(name, cond, extra=""):
    OK[0 if cond else 1] += 1
    print("  %s %-56s %s" % ("[OK]" if cond else "[NG]", name, extra))


def sha1(p):
    if not os.path.exists(p):
        return "-"
    h = hashlib.sha1()
    with open(p, "rb") as fp:
        for blk in iter(lambda: fp.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()[:12]


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
    out = [] if out is None else out
    for c in w.winfo_children():
        out.append(c)
        walk(c, out)
    return out


class FakeMB(object):
    #: askyesno / askokcancel 的返回值 —— 探针按需拨（转门派要能「点是」）
    answer = False

    def _rec(self, kind, title, msg, **_k):
        MSGS.append((kind, title, msg))
        return True

    def showinfo(self, t, m, **k):
        return self._rec("info", t, m, **k)

    def showwarning(self, t, m, **k):
        return self._rec("warn", t, m, **k)

    def showerror(self, t, m, **k):
        return self._rec("error", t, m, **k)

    def askyesno(self, t, m, **k):
        self._rec("ask", t, m, **k)
        return self.answer

    def askokcancel(self, t, m, **k):
        self._rec("ask", t, m, **k)
        return self.answer


def main():
    import tkinter as tk

    sha_before = sha1(REAL)
    if not os.path.exists(REAL):
        print("找不到存档 %s，跳过" % REAL)
        return 0
    os.makedirs(os.path.dirname(COPY), exist_ok=True)
    shutil.copy2(REAL, COPY)                       # ★ 只动副本
    print("真档 sha1[:12] = %s（只读，全程不碰）" % sha_before)

    root = tk.Tk()
    root.withdraw()
    import huaji2_save_editor                                     # noqa: E402

    MB = FakeMB()
    huaji2_save_editor.messagebox = MB
    huaji2_save_editor.backup.auto_backup_once = lambda _p: None

    app = huaji2_save_editor.App(root, save_path=COPY)
    kill_timers(root)
    app.cancel_auto_load()
    app.load(COPY)
    kill_timers(root)
    root.update_idletasks()
    p = getattr(app.doc, "path", None) if app.doc else None
    assert p and os.path.abspath(p) == os.path.abspath(COPY), \
        "doc.path 不是副本！%r" % (p,)

    for i in range(app.nb.index("end")):
        if app.nb.tab(i, "text") == "角色":
            app.nb.select(i)
    root.update_idletasks()
    kill_timers(root)

    import marshal_ruby as M
    import save as save_mod
    import game as game_mod
    from save import _deref, ivar
    from tables import sect
    from tables import sect_appellation as SA

    def sd_snap(a):
        """`@sect_data` 的纯 Python 快照（含嵌套的 :lv / :exp）。"""
        def conv(n):
            n = _deref(n)
            if isinstance(n, M.HashNode):
                return dict((M.value_of(_deref(k)), conv(v)) for k, v in n.pairs)
            return M.value_of(n)
        return conv(ivar(a, "@sect_data"))

    def actor_snap(a):
        return (app.sv.actor_name(a), app.g.actor_level(a),
                app.g.point_num(a), tuple(app.g.actor_skills(a)), sd_snap(a))

    # ---------------- A. 门派表 / 读取端
    print("\n-- A. 门派表（工具侧）")
    check("门派共 15 项（0 无门派 + 14 个门派；id 不连号 …13、20）",
          len(sect.SECTS) == 15, "%d 项" % len(sect.SECTS))
    bad = [sid for sid, (_nm, ids) in sect.SECTS.items() if sid and len(ids) < 10]
    check("每个门派 ≥10 个技能（无门派 0 个）",
          not bad and len(sect.SECTS[0][1]) == 0, "%r" % (bad,))
    total = sum(len(ids) for _nm, ids in sect.SECTS.values())
    check("SKILL_TO_SECT 覆盖全部 %d 个门派技能" % total,
          len(sect.SKILL_TO_SECT) == total, len(sect.SKILL_TO_SECT))
    check("越界 id 工具认得出（14 → 名字 None、技能空；13 现在是凌波城）",
          sect.sect_name(14) is None and sect.sect_skill_ids(14) == ()
          and sect.sect_name(13) == "凌波城",
          "%r / %r" % (sect.sect_name(14), sect.sect_skill_ids(14)))
    labels = huaji2_save_editor.sect_choice_labels()
    check("界面的门派下拉是 15 项、**含**「无门派」与两个新门派",
          len(labels) == 15 and "无门派" in labels and "凌波城" in labels
          and "九黎城" in labels, "%d 项" % len(labels))
    check("门派称谓表 12 项（从拜师事件里抠的，不是拼出来的）",
          len(SA.SECT_APPELLATION) == 12
          and SA.sect_appellation(12) == "东海龙宫弟子"
          and SA.sect_appellation(0) is None,
          "%d 项，龙宫 → %s" % (len(SA.SECT_APPELLATION),
                               SA.sect_appellation(12)))

    # ---------------- B. 真档现状（只读）
    print("\n-- B. 真档现状（只读，锁住证据）")
    rows = list(app.sv.actors())
    sids = [app.g.actor_sect_id(a) for _aid, a in rows]
    print("     %s" % "、".join(
        "%s=%s(%s)" % (app.sv.actor_name(a), app.g.actor_sect_id(a),
                       app.g.actor_sect_name(a)) for _aid, a in rows))
    check("至少一个角色有门派（@sect_id != 0）", any(s for s in sids), sids)
    off_all = []
    for _aid, a in rows:
        off_all.append((app.sv.actor_name(a), app.g.off_sect_skills(a)))
    n_off = sum(len(o) for _n, o in off_all)
    if n_off:
        check("真档里存在「非本门派、非职业自带」的技能（游戏不清理 → 合法状态）",
              n_off > 0,
              "共 %d 个：%s" % (n_off, [(n, len(o)) for n, o in off_all if o]))
    else:
        # ⚠ 不把「真档干不干净」当断言：川会玩、会拿工具清技能
        #   （260927 22:5x 这版就是：李修远已经只剩 3 个天生技能）→
        #   这条锁证据的检查改成信息，前置状态由 C 段自己造。
        print("     [--] 真档现在很干净（没有非本门派技能）→ 这条留给 C 段自造")
    keys = sorted(sd_snap(rows[0][1]).keys())
    check("@sect_data 结构 = 门派/辅助/修炼 三个键", keys == ["修炼", "辅助", "门派"],
          "、".join(keys))

    # ---------------- C. 写入路径（副本）：只动 @sect_id
    print("\n-- C. 写 @sect_id（副本）")
    with_sect = [r for r in rows if app.g.actor_sect_id(r[1])]
    tgt_aid, tgt = with_sect[0] if with_sect else rows[0]
    old_sid = app.g.actor_sect_id(tgt)
    # ⚠ 不依赖真档正好留着旧门派技能（川会玩、会清）→ 自己先把前置状态造出来：
    #   给目标角色学一个旧门派技能，这样切门派后才能验「旧技能变成非本门派」。
    old_pool = [s for s in sect.sect_skill_ids(old_sid)
                if s not in set(app.g.actor_class_learnings(tgt))]
    if old_pool:
        app.g.actor_learn_skill(tgt, old_pool[0])
    old_snap = actor_snap(tgt)
    new_sid = 11 if old_sid != 11 else 3
    print("     拿「%s」开刀：@sect_id %s(%s) → %s(%s)"
          % (app.sv.actor_name(tgt), old_sid, app.g.actor_sect_name(tgt),
             new_sid, sect.sect_name(new_sid)))
    app.sv.set_actor_field(tgt, "@sect_id", new_sid)
    check("写完立刻读回 = 新门派 id", app.g.actor_sect_id(tgt) == new_sid,
          app.g.actor_sect_id(tgt))
    check("门派名跟着变", app.g.actor_sect_name(tgt) == sect.sect_name(new_sid),
          app.g.actor_sect_name(tgt))
    check("本门派技能清单 = 新门派那一串（10~12 个，含 index 10 秘技）",
          tuple(app.g.sect_skills(tgt)) == sect.sect_skill_ids(new_sid),
          len(app.g.sect_skills(tgt)))
    now = actor_snap(tgt)
    check("@skills **一个都没变**（游戏也不清理旧门派技能）",
          now[3] == old_snap[3], "%d 个" % len(now[3]))
    check("@sect_data **完全没变**（门派/辅助/修炼）", now[4] == old_snap[4])
    check("名字/等级/五维总点数也没变", now[:3] == old_snap[:3],
          "%s Lv%s 点数%s" % now[:3])
    # 只改门派 → 旧门派技能成了「非本门派」，新门派技能一个都没学
    # 只改门派 → 角色身上那些**旧门派技能**成了「非本门派」，新门派技能一个都没学
    # ⚠ 必须只看 TA **实际有**的旧门派技能（真档里可能已经一个都没了 → 上面已补了一个）
    off_now = set(s for s, _nm in app.g.off_sect_skills(tgt))
    old_mine = ((set(sect.sect_skill_ids(old_sid))
                 - set(app.g.actor_class_learnings(tgt)))
                & set(app.g.actor_skills(tgt)))
    new_got = set(sect.sect_skill_ids(new_sid)) & set(app.g.actor_skills(tgt))
    check("旧门派技能全变成「非本门派」；新门派技能一个都还没学（正常状态）",
          bool(old_mine) and old_mine <= off_now and not new_got,
          "旧 %d 个都在 / 新门派已学 %d 个" % (len(old_mine & off_now), len(new_got)))

    app.sv.set_actor_field(tgt, "@sect_id", 0)
    check("能手写 0 = 无门派（名字「无门派」、清单空）",
          app.g.actor_sect_id(tgt) == 0 and app.g.actor_sect_name(tgt) == "无门派"
          and app.g.sect_skills(tgt) == [], app.g.actor_sect_name(tgt))

    # 越界值：工具照写 → 游戏会崩（证明实现必须校验。⚠ 14 才是越界的 ——
    # 13 现在是合法门派「凌波城」，别拿它当反例）
    app.sv.set_actor_field(tgt, "@sect_id", 14)
    check("⚠ 写 14 工具**照写不拦**（读端认不出）→ 实现必须查表校验",
          app.g.actor_sect_id(tgt) == 14 and app.g.actor_sect_name(tgt) is None,
          "@sect_id=%s 名字=%r" % (app.g.actor_sect_id(tgt),
                                   app.g.actor_sect_name(tgt)))
    app.sv.set_actor_field(tgt, "@sect_id", old_sid)
    check("改回原值 → 一切复原（可逆）", actor_snap(tgt) == old_snap,
          app.g.actor_sect_name(tgt))

    # ---------------- D. 界面：门派行的现状 + 下拉的既有语义
    print("\n-- D. 界面（角色页左栏「门派技能」）")
    # 属性文本由 `load_actor()` 写，而它读的是**列表里选中的那一行** → 先选中
    app.tv_actor.selection_set("a%d" % tgt_aid)
    app.load_actor()
    root.update_idletasks()
    kill_timers(root)
    txt = app.txt_actor.get("1.0", "end")
    line = [l for l in txt.splitlines() if l.startswith("门派：")]
    check("属性文本里有「门派：…（@sect_id=…）」一行", len(line) == 1,
          line[0][:60] if line else "(没有)")
    lf = app.lf_learn
    btns = [w.cget("text") for w in walk(lf) if w.winfo_class() == "TButton"]
    check("门派行按钮 = 「一键学习」+「转门派」+「清空门派」",
          btns == ["一键学习", "转门派", "清空门派"], "、".join(btns))
    check("下拉 15 项、含「无门派」（2026-09-27 放进去；2026-10-04 补到 14 门派）",
          "无门派" in huaji2_save_editor.sect_choice_labels()
          and len(huaji2_save_editor.sect_choice_labels()) == 15,
          "%d 项" % len(huaji2_save_editor.sect_choice_labels()))
    # 下拉不是「跟随每次刷新」而是「只在换角色时切」
    var = app.var_actor_sect
    var.set("龙宫")
    app.rebuild_learn_grid()
    root.update_idletasks()
    kill_timers(root)
    check("下拉切到别的门派 → 清单换成那一串（只是看，不改存档）",
          list(getattr(app, "_learn_sids", []))
          == list(sect.sect_skill_ids(sect.SECT_NAME_TO_ID["龙宫"])),
          len(app._learn_sids))
    app.load_actor()
    root.update_idletasks()
    kill_timers(root)
    check("⚠ 刷新面板**不会**把下拉抢回去（手动看的门派还在）",
          var.get() == "龙宫", var.get())

    # ---------------- E. 界面点「转门派」
    print("\n-- E. 界面点「转门派」")
    app.sv.set_actor_field(tgt, "@sect_id", old_sid)
    app.load_actor()
    var.set(sect.sect_name(new_sid))
    app.doc.dirty = False
    MB.answer = False
    MSGS[:] = []
    app.actor_set_sect()                       # 确认框回「否」→ 应该什么都不改
    root.update_idletasks()
    kill_timers(root)
    check("确认框点「否」→ 门派没变、也没标脏",
          app.g.actor_sect_id(tgt) == old_sid and not app.doc.dirty,
          "%s / dirty=%s" % (app.g.actor_sect_id(tgt), app.doc.dirty))
    check("确认框问的是「改门派」", any(m[1] == "改门派" for m in MSGS),
          "、".join(m[1] for m in MSGS))

    MB.answer = True
    MSGS[:] = []
    app.actor_set_sect()                       # 同意 → 写 @sect_id
    root.update_idletasks()
    kill_timers(root)
    check("点「是」→ @sect_id 写成下拉那个门派",
          app.g.actor_sect_id(tgt) == new_sid, app.g.actor_sect_id(tgt))
    check("→ 没弹错误框", not [m for m in MSGS if m[0] == "error"],
          "、".join(m[1] for m in MSGS))
    check("→ 标脏（保存不再说「没有改动」）", app.doc.dirty)
    st = app.var_status.get() if hasattr(app, "var_status") else ""
    check("→ 状态栏说了改成哪个门派", sect.sect_name(new_sid) in st, st[:60])
    cell = app.tv_actor.item("a%d" % tgt_aid, "values")[3]
    check("→ 角色列表「门派」列跟着变", cell == sect.sect_name(new_sid), cell)
    line3 = [l for l in app.txt_actor.get("1.0", "end").splitlines()
             if l.startswith("门派：")]
    check("→ 属性文本那行显示新门派",
          bool(line3) and sect.sect_name(new_sid) in line3[0],
          line3[0][:60] if line3 else "(没有)")
    check("→ 下拉停在用户选的那个门派（没被抢回旧门派）",
          var.get() == sect.sect_name(new_sid), var.get())
    check("→ 只改了 @sect_id（技能/等级/五维没动）",
          actor_snap(tgt)[1:4] == old_snap[1:4], "%d 个技能" % len(actor_snap(tgt)[3]))
    app.doc.dirty = False
    MSGS[:] = []
    app.actor_set_sect()                       # 同一个门派再点一次
    root.update_idletasks()
    kill_timers(root)
    check("同一个门派再点一次 → 只提示「无需改动」、不标脏",
          (not app.doc.dirty) and "无需" in (app.var_status.get() or ""),
          (app.var_status.get() or "")[:50])

    try:
        # ⚠ 14 才是越界值（13 现在是合法门派「凌波城」）
        app.g.set_actor_sect(tgt, 14)
        _raised = False
    except ValueError:
        _raised = True
    check("⚠ set_actor_sect(14) 抛 ValueError、存档里也没被写坏",
          _raised and app.g.actor_sect_id(tgt) == new_sid,
          "抛异常=%s / @sect_id=%s" % (_raised, app.g.actor_sect_id(tgt)))

    # ---------------- E2. 界面点「清空门派」（写 @sect_id = 0）
    print("\n-- E2. 界面点「清空门派」")
    app.sv.set_actor_field(tgt, "@sect_id", new_sid)
    app.load_actor()
    root.update_idletasks()
    kill_timers(root)
    MB.answer = False
    MSGS[:] = []
    app.doc.dirty = False
    app.actor_clear_sect()
    root.update_idletasks()
    kill_timers(root)
    check("「清空门派」确认框点「否」→ 门派没变、也没标脏",
          app.g.actor_sect_id(tgt) == new_sid and not app.doc.dirty,
          "%s / dirty=%s" % (app.g.actor_sect_id(tgt), app.doc.dirty))
    check("确认框标题 =「清空门派」", any(m[1] == "清空门派" for m in MSGS),
          "、".join(m[1] for m in MSGS))
    check("⚠ 确认框正文写明了代价（快捷技能栏/门派技能页会不可用）",
          any("快捷技能栏" in m[2] for m in MSGS if m[0] == "ask"))
    MB.answer = True
    MSGS[:] = []
    app.doc.dirty = False
    app.actor_clear_sect()
    root.update_idletasks()
    kill_timers(root)
    check("点「是」→ @sect_id 变成 0", app.g.actor_sect_id(tgt) == 0,
          app.g.actor_sect_id(tgt))
    check("→ 标脏", app.doc.dirty)
    check("→ 下拉同步成「无门派」（不再是空串）",
          var.get() == "无门派", repr(var.get()))
    check("→ 左栏清单收起 + 提示「这个角色没有门派」",
          list(getattr(app, "_learn_sids", [1])) == []
          and "没有门派" in app.var_learn_note.get(),
          app.var_learn_note.get()[:48])
    innate2 = set(app.g.actor_class_learnings(tgt))
    check("→ @skills 被重置成职业天生技能（游戏 clear_skills + init_skills）",
          set(actor_snap(tgt)[3]) == innate2 and bool(innate2),
          "%d 个 → %d 个：%s" % (len(old_snap[3]), len(actor_snap(tgt)[3]),
                                 "、".join("#%d" % s for s in sorted(innate2))))
    check("→ 等级/五维/@sect_data 仍然没动（只动门派 + 技能）",
          actor_snap(tgt)[1:3] == old_snap[1:3] and actor_snap(tgt)[4] == old_snap[4],
          "Lv%s / @sect_data 一致" % actor_snap(tgt)[1])
    line4 = [l for l in app.txt_actor.get("1.0", "end").splitlines()
             if l.startswith("门派：")]
    check("→ 属性文本那行 = 无门派",
          bool(line4) and "无门派" in line4[0],
          line4[0][:60] if line4 else "(没有)")
    MSGS[:] = []
    app.doc.dirty = False
    app.actor_clear_sect()
    root.update_idletasks()
    kill_timers(root)
    check("已无门派且技能只剩天生 → 只提示「无需改动」、连确认框都不弹",
          (not app.doc.dirty) and "无需" in (app.var_status.get() or "")
          and not MSGS, (app.var_status.get() or "")[:50])
    # 已无门派、但技能里还挂着非天生（真档的仙灵儿就是这种）→ 仍要能清
    extra_sid = [s for s in sect.sect_skill_ids(new_sid) if s not in innate2][0]
    app.g.actor_learn_skill(tgt, extra_sid)
    app.load_actor()
    root.update_idletasks()
    kill_timers(root)
    app.doc.dirty = False
    MSGS[:] = []
    app.actor_clear_sect()
    root.update_idletasks()
    kill_timers(root)
    check("已无门派但技能里还有门派技能 → 再点一次能清掉",
          app.g.actor_sect_id(tgt) == 0
          and set(app.g.actor_skills(tgt)) == innate2 and app.doc.dirty,
          "%d 个技能" % len(app.g.actor_skills(tgt)))

    # ---------------- E3. 称谓（@appellations）：2026-09-27 川报「不回收/不转换」
    print("\n-- E3. 界面：称谓跟着门派走")
    app.sv.set_actor_field(tgt, "@sect_id", new_sid)
    app.g.set_actor_appellations(tgt, ["五庄观弟子", "内测人员"], 0)
    app.load_actor()
    root.update_idletasks()
    kill_timers(root)
    line5 = [l for l in app.txt_actor.get("1.0", "end").splitlines()
             if l.startswith("称谓：")]
    check("属性文本里有「称谓：」这一行", bool(line5),
          line5[0][:60] if line5 else "(没有)")
    check("称谓和门派对不上 → 行里直接提醒（川报的就是这个）",
          bool(line5) and "不是当前门派的" in line5[0],
          line5[0][:75] if line5 else "(没有)")
    MSGS[:] = []
    app.doc.dirty = False
    MB.answer = True
    # ⚠ 下拉要显式选到目标门派 —— `load_actor_skills` 只在**换角色**时同步
    #   （同一个角色改了 @sect_id 不会再同步，免得抢掉用户手选的门派）。
    var.set(sect.sect_name(new_sid))
    app.actor_set_sect()
    root.update_idletasks()
    kill_timers(root)
    want_ap = app.g.sect_appellation_name(new_sid)
    names_ap, idx_ap = app.g.actor_appellations(tgt)
    check("点「转门派」→ 回收旧门派称谓、发新门派那个",
          "五庄观弟子" not in names_ap and want_ap in names_ap,
          "%s" % (names_ap,))
    check("→ 非门派称谓（内测人员）不被误删", "内测人员" in names_ap, "%s" % (names_ap,))
    check("→ 原显示的就是门派称谓 → 下标跟到新称谓上",
          0 <= idx_ap < len(names_ap) and names_ap[idx_ap] == want_ap,
          "idx=%s %s" % (idx_ap, names_ap))
    check("→ 确认框里写了称谓怎么变",
          any("称谓" in m[2] for m in MSGS if m[0] == "ask"),
          "、".join(m[2].replace("\n", " / ") for m in MSGS if m[0] == "ask")[:70])
    MSGS[:] = []
    app.doc.dirty = False
    app.actor_clear_sect()
    root.update_idletasks()
    kill_timers(root)
    names_ap2, idx_ap2 = app.g.actor_appellations(tgt)
    check("「清空门派」→ 门派称谓也回收、下标打成 -1",
          not app.g.sect_appellations_of(tgt) and idx_ap2 == -1,
          "%s idx=%s" % (names_ap2, idx_ap2))
    check("→ 通用称谓（内测人员）还在，只是不显示",
          "内测人员" in names_ap2, "%s" % (names_ap2,))
    # 已无门派、只剩通用称谓 → 再点一次不该白弹框
    MSGS[:] = []
    app.doc.dirty = False
    app.actor_clear_sect()
    root.update_idletasks()
    kill_timers(root)
    check("已无门派 + 没有门派称谓 → 只说「无需改动」、不弹框",
          (not app.doc.dirty) and not MSGS and "无需" in (app.var_status.get() or ""),
          (app.var_status.get() or "")[:50])
    # 真档里就有这种：门派对、称谓错（秦媚儿：女儿村 却挂着「地府弟子」）
    app.sv.set_actor_field(tgt, "@sect_id", new_sid)
    app.g.set_actor_appellations(tgt, ["地府弟子"], 0)
    app.load_actor()
    root.update_idletasks()
    kill_timers(root)
    app.doc.dirty = False
    MSGS[:] = []
    var.set(sect.sect_name(new_sid))       # 同上：下拉要显式选（不靠自动同步）
    app.actor_set_sect()
    root.update_idletasks()
    kill_timers(root)
    check("门派对、称谓错 → 点「转门派」也能对齐（没被「无需改动」挡掉）",
          app.g.actor_appellations(tgt) == ([want_ap], 0) and app.doc.dirty,
          "%r" % (app.g.actor_appellations(tgt),))

    # ---------------- E4. 下拉选「无门派」+「转门派」= 只改门派、技能不动
    #   川 260927 22:5x 定：「无门派不清技能，清空门派才清技能」→ 两路拆开。
    print("\n-- E4. 下拉选「无门派」+「转门派」：只改门派")
    app.sv.set_actor_field(tgt, "@sect_id", new_sid)
    app.g.set_actor_appellations(tgt, [app.g.sect_appellation_name(new_sid)], 0)
    app.g.actor_set_skills(tgt, sorted(set(app.g.actor_skills(tgt)) | {extra_sid}))
    app.load_actor()
    root.update_idletasks()
    kill_timers(root)
    sk_before = tuple(app.g.actor_skills(tgt))
    var.set("无门派")
    app.doc.dirty = False
    MSGS[:] = []
    MB.answer = True
    app.actor_set_sect()
    root.update_idletasks()
    kill_timers(root)
    check("下拉选「无门派」+「转门派」→ @sect_id = 0、标脏",
          app.g.actor_sect_id(tgt) == 0 and app.doc.dirty,
          "@sect_id=%s" % app.g.actor_sect_id(tgt))
    check("→ **技能一个不动**（清技能只归「清空门派」）",
          tuple(app.g.actor_skills(tgt)) == sk_before,
          "%d 个技能（清空门派那条路会只剩 %d 个天生）"
          % (len(app.g.actor_skills(tgt)), len(innate2)))
    check("→ 弹的是「改门派」框（不再借「清空门派」的框）",
          any(m[1] == "改门派" for m in MSGS if m[0] == "ask")
          and not any(m[1] == "清空门派" for m in MSGS if m[0] == "ask"),
          "、".join(m[1] for m in MSGS if m[0] == "ask"))
    _t4 = " ".join(m[2] for m in MSGS if m[0] == "ask")
    check("→ 确认框写明「技能一个不动」+ 指路「清空门派」",
          "技能一个不动" in _t4 and "清空门派" in _t4,
          _t4.replace("\n", " / ")[:90])
    check("→ 称谓也跟着回收（无门派 → 只回收、不补）",
          not app.g.sect_appellations_of(tgt),
          "%r" % (app.g.actor_appellations(tgt),))

    # 布局：门派行在窄窗下会不会被裁（左栏竖向 pack，先来先分）
    app.sv.set_actor_field(tgt, "@sect_id", old_sid)
    app.load_actor()
    root.deiconify()
    try:
        root.attributes("-alpha", 0.0)
    except Exception:
        pass
    srow = app.cb_actor_sect.master
    clip = []
    for geo in ("1220x800", "1180x757", "1080x757"):
        root.geometry(geo + "+6000+6000")
        root.update()
        root.update_idletasks()
        ok = srow.winfo_width() >= srow.winfo_reqwidth() - 2
        if not ok:
            clip.append(geo)
        print("     %-9s 门派行 %4d/%-4d  %s"
              % (geo, srow.winfo_width(), srow.winfo_reqwidth(),
                 "OK" if ok else "← 被裁"))
    check("门派行（三个按钮）在 1220/1180/1080 下都没被裁",
          not clip, "被裁: %r" % (clip,))

    # ---------------- F. 存盘 + 重开
    print("\n-- F. 写盘 + 重开（真写进去一次）")
    app.sv.set_actor_field(tgt, "@sect_id", new_sid)
    app.mark_dirty()
    skills_at_save = tuple(app.g.actor_skills(tgt))
    MSGS[:] = []
    app.save_save()
    root.update_idletasks()
    kill_timers(root)
    check("保存没说「没有改动」",
          not any("没有改动" in m[2] for m in MSGS if m[0] == "info"),
          "、".join(m[1] for m in MSGS))
    sv2 = save_mod.SaveDoc(COPY)
    g2 = game_mod.GameEditor(sv2)
    rows2 = list(sv2.actors())
    same_name = [a for aid, a in rows2 if sv2.actor_name(a) == old_snap[0]]
    check("盘上读回来：这个角色的 @sect_id = 新值",
          bool(same_name) and g2.actor_sect_id(same_name[0]) == new_sid,
          g2.actor_sect_id(same_name[0]) if same_name else "(没找到角色)")
    if same_name:
        snap2 = (sv2.actor_name(same_name[0]), g2.actor_level(same_name[0]),
                 g2.point_num(same_name[0]), tuple(g2.actor_skills(same_name[0])),
                 sd_snap(same_name[0]))
        check("盘上读回来：五维/@sect_data 一致、技能 = 存盘时那份（已被重置过）",
              snap2[1:3] == old_snap[1:3] and snap2[4] == old_snap[4]
              and snap2[3] == skills_at_save,
              "%d 个技能" % len(snap2[3]))

    try:
        root.destroy()
    except Exception:
        pass

    print("\n-- G. 真档")
    sha_after = sha1(REAL)
    check("真档没被动过", sha_before == sha_after, "%s -> %s" % (sha_before, sha_after))

    print("\n========== 探针：%d OK / %d NG ==========" % (OK[0], OK[1]))
    return 1 if OK[1] else 0


if __name__ == "__main__":
    sys.exit(main())
