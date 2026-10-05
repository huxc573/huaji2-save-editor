# -*- coding: utf-8 -*-
"""一次性探针：技能管理器（独立窗口）的筛选 × 选中语义（**只碰副本存档**）。

钉住这几件事，将来改 `SkillManager` 时一眼能看出有没有走样：

* 筛选三档（搜索 / 归属 / 状态）各剩多少行；
* 「归属」下拉 = 表里真实分段名（13 个 `===xxx===`）＋ 3 个固定项，且**分段行
  不进列表**（列出来会被"全选→学会选中"写进存档）；
* 说明里补上了跟游戏浮窗同口径的附加行（`消耗：N点魔法` / `伤害 = …`）；
* 「全选 / 反选 / 全不选」**只作用当前筛选出来的行**（不是整张表）；
* 筛选后批量「学会 / 忘掉」只动筛出来的那些；
* 「复制给…」的目标清单是**同类型的其他**目标（排除自己），落地用的是
  `learn_many` 语义 = 追加去重、不动目标原有技能；
* 主界面「已学一览」：`fill()` 重建后按 iid 保住选中（否则"搜索→再忘掉"会落空）；
* 关窗后 `app._skill_win` 置回 None。

用系统 Python 3.12（有 tkinter）。窗口全程 withdraw —— 不抢前台、不动鼠标。
"""
import io
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import paths
REAL = os.path.join(paths.find_game_dir(), "save.rvdata2")
COPY = os.path.join(ROOT, "_tmp", "probe_skillmgr.rvdata2")


def kill_timers(root):
    try:
        for aid in root.tk.call("after", "info"):
            try:
                root.after_cancel(aid)
            except Exception:
                pass
    except Exception:
        pass


def rows(w):
    return [w.sid_of(i) for i in w.tv.get_children()]


def main():
    import tkinter as tk
    os.makedirs(os.path.dirname(COPY), exist_ok=True)
    shutil.copy2(REAL, COPY)                    # 只动副本
    root = tk.Tk()
    root.withdraw()
    import huaji2_save_editor as H
    from tables import sect

    app = H.App(root, save_path=COPY)           # ★ 传副本路径，绝不让它自己猜
    kill_timers(root)
    app.cancel_auto_load()
    app.load(COPY)
    kill_timers(root)
    root.update_idletasks()

    p = getattr(app.doc, "path", None) if app.doc else None
    assert p and os.path.abspath(p) == os.path.abspath(COPY), \
        "doc.path 不是副本！%r" % (p,)
    print("doc.path =", p)

    # ---- 主界面「已学一览」：fill 保住选中 -------------------------------
    app.tv_actor.selection_set(app.tv_actor.get_children()[0])
    app.load_actor()
    root.update()
    kill_timers(root)
    a = app.current_actor()
    base = list(app.g.actor_skills(a))
    print("\n== 角色 %s：已学 %d 个 %r"
          % (app.sv.actor_name(a), len(base), base))
    app.skp_actor.var_search.set("")
    app.skp_actor.fill()
    root.update()
    kids = app.tv_actor_skills.get_children()
    print("  一览(已学) %d 行；自动选中 = %r"
          % (len(kids), app.skp_actor.sel_ids()))
    want = kids[-1]                             # 故意选**最后一行**（不是第 0 行）
    app.tv_actor_skills.selection_set(want)
    sid_want = int(want[2:])
    app.skp_actor.var_search.set(str(sid_want))
    app.skp_actor.fill()
    root.update()
    print("  搜索 '%d' 重建后，选中 = %r（应含 %d）"
          % (sid_want, app.skp_actor.sel_ids(), sid_want))
    app.skp_actor.var_search.set("")
    app.skp_actor.fill()
    root.update()
    print("  清空搜索再重建后，选中 = %r（应还是 [%d]）"
          % (app.skp_actor.sel_ids(), sid_want))

    # ---- 技能管理器 ------------------------------------------------------
    w = app.open_skill_manager("actor")
    root.update()
    kill_timers(root)
    print("\n== 技能管理器 ==")
    print("  标题 =", w.title_text())
    print("  表头 =", tuple(w.tv["columns"]))
    named = [i for i in w.meta if w.meta[i][0]]
    print("  默认列出有名字的技能 %d / %d（含 %d 个分段行没列）"
          % (len(rows(w)), len(named), len(set(w.groups.values()))))

    print("\n-- 筛选矩阵（行数）--")
    w.var_kw.set("")
    for own in (H.OWN_ALL, H.OWN_SECT, H.OWN_NA):
        w.var_own.set(own)
        cells = []
        for st in (H.ST_ALL, H.ST_HAVE, H.ST_NONE):
            w.var_st.set(st)
            w.refill()
            cells.append("%s=%d" % (st, len(rows(w))))
        print("  %-6s %s" % (own, "  ".join(cells)))
    w.var_own.set(H.OWN_ALL)
    w.var_st.set(H.ST_ALL)
    w.refill()

    print("\n-- 搜索规则 --")
    probe = [("#%d" % base[0] if base else "#1", "『#id』精确 id"),
             (str(base[0]) if base else "1", "纯数字 = id 或名字/描述含这串"),
             (" ".join(w.meta[base[0]][0]) if base else "",
              "名字逐字空格 AND"),
             ((w.meta[base[0]][1] or "")[:2] if base else "",
              "说明正文里的词")]
    for kw, tag in probe:
        if not kw:
            continue
        w.var_kw.set(kw)
        w.refill()
        r = rows(w)
        print("  %-26s 命中 %3d  %r" % (tag, len(r), r[:6]))
    w.var_kw.set("")
    w.refill()

    print("\n-- 全选 / 反选 / 全不选（只作用当前筛选）--")
    before = list(app.g.actor_skills(a))
    fresh = [i for i in sorted(w.meta) if w.meta[i][0] and i not in before]
    if fresh:
        kw = "#%d" % fresh[0]
        w.var_kw.set(kw)
        w.refill()
        n = len(rows(w))
        for tag, mode in (("全选", "all"), ("反选", "invert")):
            w.select(mode)
            print("  筛 '%s' 共 %d 行 → %s：已选 %d  %s"
                  % (kw, n, tag, len(w.sel_sids()), w.var_sel.get()))
        w.select("invert")
        print("  再反选一次：已选 %d（应回 %d）" % (len(w.sel_sids()), n))
        w.select("none")
        print("  全不选：已选 %d" % len(w.sel_sids()))

        print("\n-- 筛选后批量（只动筛出来的）--")
        w.var_kw.set(kw)
        w.refill()
        w.select("all")
        w.do_learn()
        root.update()
        after = list(app.g.actor_skills(a))
        print("  学会 '#%d'（筛 1 行）→ %r  (%d -> %d)"
              % (fresh[0], after, len(before), len(after)))
        w.do_forget()
        root.update()
        print("  忘掉选中 → %r（应回 %r）" % (app.g.actor_skills(a), before))
        w.var_kw.set("")
        w.refill()

    print("\n-- 归属 / 状态筛选名实相符 --")
    w.var_st.set(H.ST_NONE)
    w.var_own.set(H.OWN_NA)
    w.refill()
    bad = [i for i in rows(w) if sect.sect_of_skill(i) is not None]
    print("  未学 + 无归属：%d 行，其中门派技能 %d 个（应为 0）"
          % (len(rows(w)), len(bad)))
    w.var_st.set(H.ST_ALL)
    w.var_own.set(H.OWN_SECT)
    w.refill()
    bad2 = [i for i in rows(w) if sect.sect_of_skill(i) is None]
    print("  门派技能：%d 行，其中无归属 %d 个（应为 0）"
          % (len(rows(w)), len(bad2)))
    w.var_own.set(H.OWN_ALL)
    w.refill()

    # ---- 分段归属（2026-10-04 川：「归属不是有很多吗？」）-----------------
    # 技能表里作者用 `===锻造技能===` 这种行把技能分了 13 段。它们**不是技能**
    # （列出来会被"全选→学会选中"写进存档），只用来当归属。
    print("\n-- 分段归属（表里的 `===xxx===`）--")
    _secs = sorted(set(w.groups.values()))
    _ov = [str(v) for v in w.cb_own.cget("values")]
    print("  归属下拉 %d 项 = %r …" % (len(_ov), _ov[:5]))
    print("  分段名 %d 个：%r" % (len(_secs), _secs))
    print("  每个分段都在下拉里 =", all(s in _ov for s in _secs))
    print("  固定项都在下拉里 =",
          all(x in _ov for x in (H.OWN_ALL, H.OWN_SECT, H.OWN_NA)))
    print("  列表里混进的分段行（应为 0）= %d"
          % sum(1 for i in rows(w) if H._SEC_RE.match(w.meta[i][0].strip())))
    print("  有名字的技能 %d = 列表 %d + 分段行 %d"
          % (len([i for i in w.meta if w.meta[i][0]]), len(rows(w)),
             len(_secs)))
    for sec in _secs[:3]:
        w.var_own.set(sec)
        w.refill()
        r = rows(w)
        print("  筛「%s」→ %3d 行，归属取值 %r（应只有它自己）"
              % (sec, len(r), sorted(set(w.own_text(i) for i in r))[:3]))
    w.var_own.set(H.OWN_ALL)
    w.refill()

    # ---- 说明里的附加行（消耗 / 伤害 / 目标数…）--------------------------
    print("\n-- 说明里的附加行（跟游戏浮窗一个口径）--")
    _cost = [i for i in sorted(w.meta) if "消耗：" in w.meta[i][1]]
    _eq = [i for i in sorted(w.meta) if " = " in w.meta[i][1]]
    print("  带「消耗：」的技能 %d 个，例：%r" % (len(_cost), _cost[:6]))
    print("  带「xx = ...」附加行的 %d 个，例：%r" % (len(_eq), _eq[:6]))
    if _cost:
        print("  样例 #%d %s：" % (_cost[0], w.meta[_cost[0]][0]))
        for ln in w.meta[_cost[0]][1].split("\n")[-4:]:
            print("      |", ln)

    # ---- 复制给… ---------------------------------------------------------
    # ⚠ 不真的把对话框点开（它 `grab_set()`，会抢输入）；只钉两件会走样的事：
    #   目标清单的范围，以及按钮落地用的 learn_many 语义。
    print("\n-- 复制给…（目标清单 + 追加去重）--")
    w.win.update_idletasks()
    print("  窗口 geometry = %s，内容需求 = %dx%d（期望宽 ≈750）"
          % (w.win.geometry().split("+")[0],
             w.win.winfo_reqwidth(), w.win.winfo_reqheight()))
    print("  按钮存在 =", hasattr(w, "do_copy_to"))
    a_tgt = w._copy_targets(a)
    print("  角色侧目标数 = %d，含自己 = %s（应为 False）"
          % (len(a_tgt), any(x is a for _i, x in a_tgt)))
    w.key = "baby"
    bb = app.babies_ed().all_babies()
    if bb:
        src_b = bb[0]["baby"]
        b_tgt = w._copy_targets(src_b)
        print("  召唤兽侧目标数 = %d，含来源 = %s（应为 False）"
              % (len(b_tgt), any(r["baby"] is src_b for r in b_tgt)))
    w.key = "actor"

    if a_tgt:
        _aid, tgt = a_tgt[0]
        give = list(app.g.actor_skills(a))
        before_t = list(app.g.actor_skills(tgt))
        added, already = app.g.actor_learn_many(tgt, give)
        after_t = list(app.g.actor_skills(tgt))
        # ⚠ 角色的 `@skills` 永远升序（`actor_set_skills` 里 `sorted`），所以
        #   这里只钉"无重复 + 并集正确"，不钉"追加在后"（那是召唤兽侧的性质）。
        ok = (len(after_t) == len(set(after_t))
              and set(after_t) == set(before_t) | set(give)
              and after_t == sorted(after_t))
        print("  复制「%s」的 %d 个技能给「%s」→ 新增 %d，本来就会 %d"
              % (app.sv.actor_name(a), len(give), app.sv.actor_name(tgt),
                 len(added), len(already)))
        print("  目标 %d → %d 个；无重复、并集正确、升序 = %s（应 True）"
              % (len(before_t), len(after_t), ok))
        app.g.actor_set_skills(tgt, before_t)          # 还原
        root.update()

    # ---- 关窗 ------------------------------------------------------------
    w.close()
    root.update()
    print("\n关窗后 app._skill_win = %r （应为 None）"
          % (getattr(app, "_skill_win", "缺属性"),))
    # 再开一次不该复用旧窗
    w2 = app.open_skill_manager("actor")
    root.update()
    print("再开一次：窗口存在=%s，是同一个=%s"
          % (w2.win.winfo_exists(), w2 is w))
    w2.close()
    root.update()
    print("关掉后又开：召唤兽侧 =", app.open_skill_manager("baby") is not None)
    app._skill_win.close()
    root.update()

    print("\n[探针跑完] 真实存档未动（只碰了 %s）" % os.path.basename(COPY))
    return 0


if __name__ == "__main__":
    sys.exit(main())
