# -*- coding: utf-8 -*-
"""一次性探针：门派技能勾选框「勾选 = 学会 / 取消 = 忘掉」到底有没有落盘。

起因（2026-09-23 川反馈）：门派技能勾选/取消勾选之后点保存，提示「没有改动」。
旧实现里勾选框只是「一键学习」的输入（勾了不点按钮 = 零效果），已学的还是
disabled、压根没法取消勾选 → 保存当然说没改动。

⚠ 踩过的坑（2026-09-23）：`Doc.save()` 写盘后会 `parse_stream` **重新解析**，
   之前拿到的节点引用全部失效 → 探针里必须每次保存后重新 `current_actor()`，
   否则会伪造出「删不掉 / 一键学习没写进去」这类假 NG。

    XJ_PY=<py312> python tests/probe_sect_dirty.py
"""
import io
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import paths                                                     # noqa: E402

WORK = os.path.join(ROOT, "_tmp", "probe_sect_dirty")
MSGS = []
BAD = [0]


def check(name, cond, extra=""):
    if not cond:
        BAD[0] += 1
    print("  [%s] %s%s" % ("OK" if cond else "NG", name,
                           ("  " + extra) if extra else ""))


def main():
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    root.update()

    import huaji2_save_editor as H

    H.messagebox = type("MB", (), {
        "showinfo": staticmethod(lambda *a, **k: MSGS.append(("info", a))),
        "showerror": staticmethod(lambda *a, **k: MSGS.append(("error", a))),
        "showwarning": staticmethod(lambda *a, **k: MSGS.append(("warn", a))),
        "askyesno": staticmethod(lambda *a, **k: MSGS.append(("ask", a)) or True),
    })

    os.makedirs(WORK, exist_ok=True)
    copy = os.path.join(WORK, "copy.rvdata2")
    shutil.copyfile(paths.save_path(), copy)

    app = H.App(root, save_path=copy)
    root.update()
    app.load(copy, quiet=True)
    root.update()
    assert os.path.abspath(app.doc.path).lower() == os.path.abspath(copy).lower()

    # ---- 工具：读真值一律现取节点（保存后旧节点会失效）
    def cur():
        return app.current_actor()

    def sk(a=None):
        a = a if a is not None else cur()
        return list(app.g.actor_skills(a)) if a is not None else []

    def click(sid, on):
        """模拟真点：先摆好 IntVar，再叫回调（就是 Checkbutton 的 command）。"""
        app.learn_vars[sid].set(1 if on else 0)
        app.actor_toggle_sect_skill(sid)
        root.update()

    def save():
        MSGS[:] = []
        app.save_save()
        root.update()
        return MSGS[:1]

    def saved_ok(ms):
        return bool(ms) and ms[0][0] == "info" and "没有改动" not in ms[0][1][1]

    for iid in app.tv_actor.get_children():
        app.tv_actor.selection_set(iid)
        app.load_actor()
        root.update()
        if app.g.sect_skills(cur()):
            break
    print("角色 = %s（%s）" % (app.sv.actor_name(cur()), app.var_actor_sect.get()))

    boxes = [w for w in app.learn_grid.winfo_children()
             if w.winfo_class() == "TCheckbutton"]
    sids = list(app._learn_sids)
    known = set(sk())
    fresh = [s for s in sids if s not in known]
    print("  清单 %d 个；已学 %d 个；未学 %r" % (len(sids), len(known), fresh[:3]))

    # ---- 1) 勾选框反映存档真值（已学 = 勾上），且不再 disabled
    check("已学的框是勾上的", all(app.learn_vars[s].get() == 1
                                  for s in sids if s in known),
          "%r" % [(s, app.learn_vars[s].get()) for s in sids][:3])
    check("已学的框不再 disabled（能取消勾选）",
          not any(w.instate(("disabled",)) for w in boxes),
          "%d 个框" % len(boxes))
    check("勾选框挂的是真回调（不是纯输入）",
          bool(boxes) and all(w.cget("command") for w in boxes))

    # ---- 2) 勾一个未学的 → 立刻学会 + 标 dirty + 保存能写
    if not fresh:
        # 该角色本门派已学满 → 先取消一个造出「未学」（顺便验证取消方向）
        print("  （本门派已学满，先取消 #%d 造一个未学）" % sids[0])
        click(sids[0], False)
        check("已学满时取消勾选 → 立刻从 @skills 删掉", sids[0] not in sk(),
              "%r" % (sk(),))
        check("已学满时取消勾选 → doc.dirty = True", app.doc.dirty)
        fresh = [sids[0]]

    one = fresh[0]
    click(one, True)
    check("勾选 → 立刻写进 @skills", one in sk(), "#%d → %r" % (one, sk()))
    check("勾选 → doc.dirty = True", app.doc.dirty,
          "structural=%s" % app.doc.structural)
    ms = save()
    check("勾选后点保存 = 真的写盘（不再说「没有改动」）", saved_ok(ms),
          "%r" % (ms,))
    check("保存后 dirty 归零", not app.doc.dirty)
    check("保存后勾选框仍是勾上的（保存会重建面板）",
          app.learn_vars.get(one) is not None
          and app.learn_vars[one].get() == 1
          and one in sk())

    # ---- 3) 再取消勾选 → 立刻忘掉 + 标 dirty + 保存能写
    click(one, False)
    check("取消勾选 → 立刻从 @skills 删掉", one not in sk(), "#%d → %r" % (one, sk()))
    check("取消勾选 → doc.dirty = True", app.doc.dirty)
    ms = save()
    check("取消勾选后点保存 = 真的写盘", saved_ok(ms), "%r" % (ms,))
    check("保存后这个技能确实不在档里了", one not in sk())
    click(one, True)                     # 复原

    # ---- 4) 已学的取消勾选 = 忘掉（这是新增能力）
    learnt = [s for s in sids if s in set(sk())]
    if learnt:
        click(learnt[0], False)
        check("已学的取消勾选 → 忘掉", learnt[0] not in sk(), "#%d" % learnt[0])
        click(learnt[0], True)
        check("再勾回来 → 学会", learnt[0] in sk(), "#%d" % learnt[0])
    else:
        check("有已学技能可测", False, "本门派一个都没学")

    # ---- 5) 「一键学习」= 学满本门派
    app.g.actor_clear_skills(cur())
    app.load_actor()
    root.update()
    check("清空 @skills 成功", sk() == [], "%r" % (sk(),))
    app.actor_learn_checked()
    root.update()
    check("一键学习 → 学满本门派", set(sids) <= set(sk()), "%r" % (sk(),))
    check("一键学习后勾选框全部打上",
          all(app.learn_vars[s].get() == 1 for s in list(app._learn_sids)))
    check("一键学习 → doc.dirty = True", app.doc.dirty)
    ms = save()
    check("一键学习后保存 = 真的写盘", saved_ok(ms), "%r" % (ms,))
    check("一键学习落盘后 @skills 仍是满的", set(sids) <= set(sk()), "%r" % (sk(),))

    # ---- 6) 切角色来回，勾选状态跟存档走（不会被清 0）
    kids = app.tv_actor.get_children()
    if len(kids) >= 2:
        for iid in kids[:2]:
            app.tv_actor.selection_set(iid)
            app.load_actor()
            root.update()
        app.tv_actor.selection_set(kids[0])
        app.load_actor()
        root.update()
        sids2 = list(app._learn_sids)
        kn2 = set(sk())
        check("换角色回来，勾选状态仍 = 存档真值",
              all(app.learn_vars[s].get() == (1 if s in kn2 else 0) for s in sids2),
              "%r" % [(s, app.learn_vars[s].get()) for s in sids2][:4])

    print("\n==== 问题 %d 项 ====" % BAD[0])
    root.destroy()
    shutil.rmtree(WORK, ignore_errors=True)
    return 1 if BAD[0] else 0


if __name__ == "__main__":
    sys.exit(main())
