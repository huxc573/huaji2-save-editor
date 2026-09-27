# -*- coding: utf-8 -*-
"""一次性探针：验证召唤兽「五行」的 读 / 改 / 新增（**只碰副本存档**）。

覆盖 2026-09-27 新增的 `@attr.@five`：
  · 字段表里有没有「五行」这一行、值是不是 金木水火土
  · 「改字段」那行的值控件会不会切换（数字输入框 ↔ 只读下拉）
  · 改值走 GUI 路径能不能**真的写进盘**（不是只 mark_dirty）
  · 非法值（「风」）会不会被挡、且**不会**把存档标脏
  · 非五行字段仍按数字解析（没被字符串分支带歪）
  · `babies.add(five=...)`：指定写死 / 不指定随机 / 非法报错
  · 「新增召唤兽」对话框里的五行下拉：默认「随机」、选「火」能落地

用系统 Python 3.12（有 tkinter）。窗口全程 withdraw / 屏外 / 全透明 —— 不抢前台、不动鼠标。

    XJ_PY=<py312> python tests/probe_five.py

⚠ 踩过的坑（2026-09-23 记过一次，这里同样适用）：`Doc.save()` 写盘后会
  `parse_stream` **重新解析**，之前拿到的节点引用全部失效 → 每次保存后必须
  重新取 `app.g.babies(a)` / `current_actor()`，否则会伪造出「改不动」的假 NG。
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
COPY = os.path.join(ROOT, "_tmp", "probe_five.rvdata2")

OK = [0, 0]
MSGS = []


def check(name, cond, extra=""):
    OK[0 if cond else 1] += 1
    print("  %s %-54s %s" % ("[OK]" if cond else "[NG]", name, extra))


def sha1(p):
    if not os.path.exists(p):
        return "-"
    h = hashlib.sha1()
    with open(p, "rb") as fp:
        for blk in iter(lambda: fp.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()[:12]


def kill_timers(root):
    """把 App 挂的 after 定时器全取消 —— 免得它们在本探针里乱跑。"""
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
    """假 messagebox：记下每条弹窗，`askyesno` 统一回「是」。"""

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
        return self._rec("ask", t, m, **k)

    def askokcancel(self, t, m, **k):
        return self._rec("ask", t, m, **k)


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

    huaji2_save_editor.messagebox = FakeMB()
    # 探针不测备份链路（test_backup.py 管），别往「存档管理」里真写文件
    huaji2_save_editor.backup.auto_backup_once = lambda _p: None

    app = huaji2_save_editor.App(root, save_path=COPY)   # ★ 传副本，别让它自己猜
    kill_timers(root)
    app.cancel_auto_load()
    app.load(COPY)
    kill_timers(root)
    root.update_idletasks()

    p = getattr(app.doc, "path", None) if app.doc else None
    assert p and os.path.abspath(p) == os.path.abspath(COPY), \
        "doc.path 不是副本！%r" % (p,)
    print("doc.path = %s" % p)

    # 切到召唤兽页
    for i in range(app.nb.index("end")):
        if app.nb.tab(i, "text") == "召唤兽":
            app.nb.select(i)
    root.update_idletasks()
    kill_timers(root)

    a = app._baby_actor()
    print("角色 = %s，召唤兽 %d 只"
          % (app.sv.actor_name(a), len(app.g.babies(a))))

    def pick_baby(i=0):
        """选中第 i 只并返回它的节点（**每次保存后都要重取**）。"""
        kids = app.tv_babies.get_children()
        if i >= len(kids):
            return None
        app.tv_babies.selection_set(kids[i])
        app.on_baby_select()
        root.update_idletasks()
        kill_timers(root)
        return app._baby()

    def read_five(baby):
        return app.g.baby_value(baby, "five")

    b0 = pick_baby(0)
    if b0 is None:
        print("这只角色没有召唤兽，跳过")
        root.destroy()
        return 0

    # ---------------- A. 字段表
    print("\n-- A. 「改字段」清单")
    kids = app.tv_baby.get_children()
    check("清单里有 b_five 这一行", "b_five" in kids, "、".join(kids[:6]) + " …")
    vals = app.tv_baby.item("b_five", "values") if "b_five" in kids else ()
    check("行标签 = 五行", len(vals) > 0 and vals[0] == "五行", "%r" % (vals,))
    v0 = read_five(b0)
    check("读出来的值 ∈ 金木水火土",
          v0 in ("金", "木", "水", "火", "土"), repr(v0))
    check("值是字符串（Marshal String，不是符号/数字）",
          isinstance(v0, str), type(v0).__name__)

    # ---------------- B. 值控件切换
    print("\n-- B. 值控件（数字输入框 ↔ 只读下拉）")
    mgr = lambda w: w.winfo_manager()
    baby0 = pick_baby(0)
    app.tv_baby.selection_set("b_grow")
    app.baby_pick()
    root.update_idletasks()
    check("普通字段 → 显示数字输入框", mgr(app.ent_baby_val) == "grid",
          "ent=%r" % mgr(app.ent_baby_val))
    check("普通字段 → 下拉收起", mgr(app.cb_baby_val) == "",
          "cb=%r" % mgr(app.cb_baby_val))
    app.tv_baby.selection_set("b_five")
    app.baby_pick()
    root.update_idletasks()
    check("选中五行 → 下拉出现", mgr(app.cb_baby_val) == "grid",
          "cb=%r" % mgr(app.cb_baby_val))
    check("选中五行 → 数字框收起", mgr(app.ent_baby_val) == "",
          "ent=%r" % mgr(app.ent_baby_val))
    cvals = list(app.cb_baby_val.cget("values"))
    check("下拉只能选 金木水火土（顺序一致）",
          cvals == ["金", "木", "水", "火", "土"], "、".join(cvals))
    check("下拉里显示的就是当前值", app.var_baby_val.get() == read_five(baby0),
          "%r vs %r" % (app.var_baby_val.get(), read_five(baby0)))
    # 切回数字字段：这时 var 里塞的是数字，readonly 下拉必须**容忍**（不抛异常）
    app.tv_baby.selection_set("b_atk")
    try:
        app.baby_pick()
        swapped = True
    except Exception as e:                                    # pragma: no cover
        swapped = False
        print("     切换异常：%r" % (e,))
    root.update_idletasks()
    check("切回数字字段不炸（readonly 下拉容忍列表外的值）", swapped)
    check("切回后数字框回来了", mgr(app.ent_baby_val) == "grid")

    # ---------------- C. 改值：GUI 路径要真写进盘
    print("\n-- C. 改五行（GUI 路径）")
    new_five = "土" if read_five(b0) != "土" else "水"
    b0 = pick_baby(0)
    app.tv_baby.selection_set("b_five")
    app.baby_pick()
    app.doc.dirty = False                     # 只清「未保存」标记
    MSGS[:] = []
    app.var_baby_val.set(new_five)
    app.apply_baby()
    root.update_idletasks()
    kill_timers(root)
    check("改值没弹错误框", not [m for m in MSGS if m[0] == "error"],
          "、".join(m[1] for m in MSGS))
    check("改完立刻标脏（保存不再说「没有改动」）", app.doc.dirty)
    b0 = pick_baby(0)                         # ★ apply_baby 里 load_baby 过，重取
    check("内存里已经是新五行", read_five(b0) == new_five, repr(read_five(b0)))

    MSGS[:] = []
    app.save_save()
    root.update_idletasks()
    kill_timers(root)
    check("保存没有说「没有改动」",
          not any("没有改动" in m[2] for m in MSGS if m[0] == "info"),
          "、".join(m[1] for m in MSGS))
    check("保存后 dirty 归零", not app.doc.dirty)
    # ★ 保存 = 重新解析，节点全换 → 整个 doc 重开一遍读盘校验
    import save as save_mod
    import game as game_mod
    import marshal_ruby as M
    sv2 = save_mod.SaveDoc(COPY)
    g2 = game_mod.GameEditor(sv2)
    a2 = sv2.actors()[0][1]
    disk = g2.baby_value(g2.babies(a2)[0][1], "five")
    check("盘上读回来 = 新五行（真的写进去了）", disk == new_five, repr(disk))

    # ---------------- D. 非法值被挡 + 不弄脏存档
    print("\n-- D. 非法五行")
    b0 = pick_baby(0)
    try:
        app.g.set_baby(b0, "five", "风")
        raised = False
    except ValueError:
        raised = True
    check("set_baby('风') 抛 ValueError", raised)
    app.doc.dirty = False
    MSGS[:] = []
    app.var_baby_val.set("风")
    app.apply_baby()
    root.update_idletasks()
    kill_timers(root)
    check("GUI 里填「风」→ 弹「修改失败」",
          any(m[0] == "error" for m in MSGS),
          "、".join("%s: %s" % (m[1], m[2].split("\n")[0]) for m in MSGS))
    check("非法值**不会**把存档标脏", not app.doc.dirty)
    b0 = pick_baby(0)
    check("非法值没写进去", read_five(b0) == new_five, repr(read_five(b0)))

    # ---------------- E. 非五行字段没被带歪
    print("\n-- E. 其它字段仍按数字解析")
    b0 = pick_baby(0)
    app.tv_baby.selection_set("b_grow")
    app.baby_pick()
    app.var_baby_val.set("1.95")
    MSGS[:] = []
    app.apply_baby()
    root.update_idletasks()
    kill_timers(root)
    b0 = pick_baby(0)
    check("成长 1.95 走 float 分支",
          abs(app.g.baby_value(b0, "grow") - 1.95) < 1e-6,
          repr(app.g.baby_value(b0, "grow")))
    app.tv_baby.selection_set("b_体质")
    app.baby_pick()
    app.var_baby_val.set("0x20")
    app.apply_baby()
    root.update_idletasks()
    kill_timers(root)
    b0 = pick_baby(0)
    check("体质 0x20 走 int(raw,0) 分支 = 32",
          app.g.baby_value(b0, "体质") == 32, repr(app.g.baby_value(b0, "体质")))
    check("改完数字字段，五行没被顺带改掉",
          read_five(b0) == new_five, repr(read_five(b0)))

    # ---------------- F. babies.add(five=...)
    print("\n-- F. 新增召唤兽的五行")
    B = app.babies_ed()
    # ★ C 里 save 过了 → doc 重解析，开头拿的 `a` 已经是**悬空节点**，必须重取。
    #   否则 add 写进旧数组，而下面读的也是旧数组 —— 自己跟自己一致，看不出错。
    av = app._baby_actor()
    n0 = len(app.g.babies(av))
    nb = B.add(av, 181, five="金")
    check("add(five='金') → 就是金", app.g.baby_value(nb, "five") == "金",
          repr(app.g.baby_value(nb, "five")))
    nb2 = B.add(av, 181)
    check("add() 不指定 → 在五元组里随机",
          app.g.baby_value(nb2, "five") in ("金", "木", "水", "火", "土"),
          repr(app.g.baby_value(nb2, "five")))
    check("新增了两只（读的是活着的角色节点）",
          len(app.g.babies(app._baby_actor())) == n0 + 2,
          "%d -> %d" % (n0, len(app.g.babies(app._baby_actor()))))
    try:
        B.add(av, 181, five="风")
        raised = False
    except ValueError:
        raised = True
    check("add(five='风') 抛 ValueError", raised)
    # @five 节点类型（必须是 String，游戏按 sample 的字符串比）
    attr = app.g.baby_attr(nb)
    node = save_mod._deref(save_mod.ivar(attr, "@five"))
    check("@five 节点是 StrNode", isinstance(node, M.StrNode),
          type(node).__name__)

    # ---------------- G. 「新增召唤兽」对话框
    print("\n-- G. 新增对话框里的五行下拉")
    root.deiconify()
    try:
        root.attributes("-alpha", 0.0)
    except Exception:
        pass
    root.geometry("+6000+6000")
    root.update()
    kill_timers(root)
    dialog_win = None
    try:
        app.baby_add_dialog()
        root.update()
        kill_timers(root)
        for w in root.winfo_children():
            if w.winfo_class() == "Toplevel" and \
                    w.winfo_exists() and w.title() == "新增召唤兽":
                dialog_win = w
        check("打开了「新增召唤兽」对话框", dialog_win is not None)
    except Exception as e:
        check("打开了「新增召唤兽」对话框", False, repr(e))
    if dialog_win is not None:
        ws = walk(dialog_win)
        cbs = [w for w in ws
               if w.winfo_class() == "TCombobox"
               and "随机" in list(w.cget("values"))]
        check("对话框里有五行下拉（含「随机」）", len(cbs) == 1,
              "%d 个 TCombobox 带「随机」" % len(cbs))
        if cbs:
            cb = cbs[0]
            check("下拉默认 = 随机", cb.get() == "随机", repr(cb.get()))
            check("下拉可选 = 随机 + 金木水火土",
                  list(cb.cget("values")) == ["随机", "金", "木", "水", "火", "土"],
                  "、".join(cb.cget("values")))
            check("下拉没被窗口裁掉（req 宽 %d ≤ 窗宽 %d）"
                  % (cb.winfo_reqwidth(), dialog_win.winfo_width()),
                  cb.winfo_reqwidth() <= max(40, dialog_win.winfo_width()))
            add_btns = [w for w in ws if w.winfo_class() == "TButton"
                        and w.cget("text") == "加这只"]
            check("对话框里有「加这只」", len(add_btns) == 1)
            n1 = len(app.g.babies(app._baby_actor()))
            cb.set("火")
            if add_btns:
                MSGS[:] = []
                add_btns[0].invoke()
                root.update()
                kill_timers(root)
                root.update_idletasks()
                av2 = app._baby_actor()          # ★ 重取（同 F）
                check("加完数量 +1", len(app.g.babies(av2)) == n1 + 1,
                      "%d -> %d" % (n1, len(app.g.babies(av2))))
                last = app.g.babies(av2)[-1][1]
                check("新加那只五行 = 火（对话框选的值落地了）",
                      app.g.baby_value(last, "five") == "火",
                      repr(app.g.baby_value(last, "five")))
                check("对话框已关", not dialog_win.winfo_exists())
    try:
        root.destroy()
    except Exception:
        pass

    # ---------------- H. 真档没被动
    print("\n-- H. 真档")
    sha_after = sha1(REAL)
    check("真档没被动过", sha_before == sha_after,
          "%s -> %s（不等＝游戏自己存盘了，先怀疑 Game.exe）"
          % (sha_before, sha_after))

    print("\n========== 五行探针：%d OK / %d NG ==========" % (OK[0], OK[1]))
    return 1 if OK[1] else 0


if __name__ == "__main__":
    sys.exit(main())
