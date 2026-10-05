# -*- coding: utf-8 -*-
"""探针：四个自定义子窗口的 居中 / Esc 关闭，以及「新增召唤兽」多选。

只碰**副本**存档，真档 sha1 必须不变。根窗口挪到屏外（+6000+6000）——
拿得到真实坐标，又不抢前台、不动鼠标。

    XJ_PY=<py312> python tests/probe_dialog_ux.py

⚠ 两个必须记住的点（2026-10-03 实测）：
  · `event_generate("<Escape>")` 测的是**焦点**不是绑定 —— Esc 是键盘事件，
    Tk 只把它投给「当前焦点所在窗口」。对话框刚开时焦点还在主窗口上，
    所以 `esc_close()` 里必须 `win.focus_set()`（Tk 内部焦点，不抢系统前台）；
    调用方要指定焦点（搜索框/文本框）时，把 widget.focus_set() 写在它之后。
  · `winfo_rootx()` 报的是**客户区**，`geometry("+x+y")` 定的是**外框** ——
    两者差一个标题栏/边框（本机 dx=8 dy=31），所以断言要拿主窗口量出的
    同一个差值校正期望值，否则会伪造出「没居中」的假 NG。
"""
import hashlib
import io
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import tkinter as tk                                          # noqa: E402
import paths                                                  # noqa: E402
import huaji2_save_editor as H                                # noqa: E402

WORK = os.path.join(ROOT, "_tmp", "probe_dialog_ux")
OK = [0, 0]


def check(name, cond, extra=""):
    OK[0 if cond else 1] += 1
    print("  %s %-48s %s" % ("[OK]" if cond else "[NG]", name, extra))
    return cond


def sha1(p):
    h = hashlib.sha1()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def walk(w, out=None):
    if out is None:
        out = []
    for c in w.winfo_children():
        out.append(c)
        walk(c, out)
    return out


def toplevels(root):
    return [w for w in root.winfo_children()
            if isinstance(w, tk.Toplevel) and w.winfo_exists()]


def find_win(root, prefix):
    for w in toplevels(root):
        try:
            if w.title().startswith(prefix):
                return w
        except Exception:
            pass
    return None


def kill_all(root):
    """把还开着的子窗口关掉（免得 grab 叠着影响下一段）。"""
    for w in toplevels(root):
        try:
            w.grab_release()
        except Exception:
            pass
        try:
            w.destroy()
        except Exception:
            pass
    root.update()


def frame_delta(root):
    """外框差：geometry(+x+y) 定外框，winfo_rootx 报客户区。"""
    m = re.search(r"\+(-?\d+)\+(-?\d+)", root.geometry())
    if not m:
        return 0, 0
    return (root.winfo_rootx() - int(m.group(1)),
            root.winfo_rooty() - int(m.group(2)))


def center_gap(win, root, dx, dy, y_ratio=3):
    """返回 (水平偏差, 竖直偏差)：实际 - 期望（期望含外框差校正）。"""
    win.update_idletasks()
    ww, wh = win.winfo_width(), win.winfo_height()
    if ww <= 1:
        ww = win.winfo_reqwidth()
    if wh <= 1:
        wh = win.winfo_reqheight()
    exp_x = root.winfo_rootx() + (root.winfo_width() - ww) // 2 + dx
    exp_y = root.winfo_rooty() + (root.winfo_height() - wh) // y_ratio + dy
    return win.winfo_rootx() - exp_x, win.winfo_rooty() - exp_y


def check_center(win, root, dx, dy, tag):
    gx, gy = center_gap(win, root, dx, dy)
    check("%s 水平居中（偏差 %dpx）" % (tag, gx), abs(gx) <= 2)
    check("%s 竖直落在上方 1/3（偏差 %dpx）" % (tag, gy), abs(gy) <= 2)
    rx, ry = root.winfo_rootx(), root.winfo_rooty()
    wx, wy = win.winfo_rootx(), win.winfo_rooty()
    check("%s 落在主窗口范围内（不是屏幕左上角）" % tag,
          rx <= wx <= rx + root.winfo_width()
          and ry <= wy <= ry + root.winfo_height())


def esc(win, root, tag):
    """Esc 检查：绑定必查；「按下去真能关」只在 Tk 有焦点窗口时查。

    ⚠ 本进程没被激活时 Tk 的 focusPtr 是空的，键盘事件**根本投不出去**
    （不是代码问题）—— 那种情况只报跳过，不当失败。
    """
    check("%s Esc 已绑定" % tag, bool(win.bind("<Escape>")), "")
    fg = root.focus_get()
    if fg is None:
        print("  [跳过] %s Esc 行为：本进程没被激活，Tk 收不到键盘事件"
              % tag)
        return
    check("%s 焦点在对话框里（%s）" % (tag, fg), str(fg).startswith(str(win)))
    win.event_generate("<Escape>", when="now")
    root.update()
    try:
        gone = not win.winfo_exists()
    except Exception:
        gone = True
    check("%s Esc 能关掉" % tag, gone)


def main():
    real = paths.save_path()
    if not os.path.exists(real):
        print("找不到存档，跳过：%s" % real)
        return 0
    before = sha1(real)
    os.makedirs(WORK, exist_ok=True)
    copy = os.path.join(WORK, "dlg.rvdata2")
    shutil.copyfile(real, copy)

    H.messagebox = type("MB", (), {
        "showinfo": staticmethod(lambda *a, **k: None),
        "showerror": staticmethod(lambda *a, **k: print("    !! 弹错:", a)),
        "showwarning": staticmethod(lambda *a, **k: None),
    })

    root = tk.Tk()
    root.geometry("1220x800+6000+6000")
    root.update()
    app = H.App(root, save_path=copy)
    root.update()
    dx, dy = frame_delta(root)
    print("主窗口 (%d, %d) 宽 %d | 外框差 dx=%d dy=%d"
          % (root.winfo_rootx(), root.winfo_rooty(), root.winfo_width(), dx, dy))

    # ---------------- A. 召唤兽技能克隆窗口
    print("\n-- A. 召唤兽技能克隆窗口")
    kids = app.tv_babies.get_children()
    if kids:
        app.tv_babies.selection_set(kids[0])
        app.on_baby_select()
    root.update()
    app.baby_skill_clone()
    root.update()
    w = find_win(root, "克隆技能 → ")
    if check("窗口建起来了", w is not None):
        check_center(w, root, dx, dy, "克隆窗")
        esc(w, root, "克隆窗")
    kill_all(root)

    # ---------------- B. 角色技能克隆窗口
    print("\n-- B. 角色技能克隆窗口")
    app.actor_skill_clone()
    root.update()
    w = find_win(root, "克隆技能 → ")
    if check("窗口建起来了", w is not None):
        check_center(w, root, dx, dy, "克隆窗")
        esc(w, root, "新增窗")
    kill_all(root)

    # ---------------- C. 新增召唤兽：多选 / 改名 / 居中 / 一次加一批
    print("\n-- C. 新增召唤兽窗口")
    a0 = app._baby_actor()
    n0 = len(app.g.babies(a0))
    app.baby_add_dialog()
    root.update()
    w = find_win(root, "新增召唤兽")
    if check("窗口建起来了", w is not None):
        check_center(w, root, dx, dy, "新增窗")
        ws = walk(w)
        cbs = [x for x in ws if x.winfo_class() == "TCheckbutton"]
        tvs = [x for x in ws if x.winfo_class() == "Treeview"]
        btn = [x for x in ws if x.winfo_class() == "TButton"
               and "加" in str(x.cget("text"))]
        check("筛选复选框文案 =「神兽」",
              [str(c.cget("text")) for c in cbs][:1] == ["神兽"],
              "、".join(str(c.cget("text")) for c in cbs))
        check("列表 selectmode = extended",
              bool(tvs) and str(tvs[0].cget("selectmode")) == "extended")
        if tvs and btn:
            rows = tvs[0].get_children()
            check("列表有货（%d 行）" % len(rows), len(rows) > 2)
            tvs[0].selection_set(rows[0])
            root.update()
            check("选中 1 项 → 按钮「加这只」",
                  str(btn[0].cget("text")) == "加这只",
                  str(btn[0].cget("text")))
            tvs[0].selection_set(rows[:3])
            root.update()
            check("选中 3 项 → 按钮「加选中的 3 只」",
                  str(btn[0].cget("text")) == "加选中的 3 只",
                  str(btn[0].cget("text")))
            # ⚠ 文字变长后必须重算贴字 padding（refit_btn），
            #   否则短文字那套负 padding 还在 → 文字被裁
            ref = app.ttk.Button(w, text="加选中的 3 只")
            ref.update_idletasks()
            check("按钮宽度没被裁（%dpx ≥ 基准 %dpx）"
                  % (btn[0].winfo_reqwidth(), ref.winfo_reqwidth()),
                  btn[0].winfo_reqwidth() >= ref.winfo_reqwidth() - 1)
            ref.destroy()
            btn[0].invoke()
            root.update()
            root.update_idletasks()
            check("点一下 → 真加进去 3 只",
                  len(app.g.babies(app._baby_actor())) == n0 + 3,
                  "%d -> %d" % (n0, len(app.g.babies(app._baby_actor()))))
            check("加完窗口自己关了", not w.winfo_exists())
    kill_all(root)

    # ---------------- D. 新增召唤兽：Esc
    print("\n-- D. 新增召唤兽窗口 Esc")
    app.baby_add_dialog()
    root.update()
    w = find_win(root, "新增召唤兽")
    if w is not None:
        esc(w, root, "新增窗")
    kill_all(root)

    # ---------------- E. 备注窗 / 改字段窗
    print("\n-- E. 备注窗 / 改字段窗")
    d = H.NoteDialog(root, "abc")
    root.update()
    if check("备注窗建起来了", bool(d.winfo_exists())):
        check_center(d, root, dx, dy, "备注窗")
        esc(d, root, "备注窗")
    d = H.EditDialog(root, 123, "i")
    root.update()
    if check("改字段窗建起来了", bool(d.winfo_exists())):
        check_center(d, root, dx, dy, "改字段窗")
        esc(d, root, "改字段窗")
    kill_all(root)

    # ---------------- F. 真档没动
    print("\n-- F. 真档")
    check("真档 sha1 未变", sha1(real) == before)

    try:
        root.destroy()
    except Exception:
        pass
    shutil.rmtree(WORK, ignore_errors=True)
    print("\n判定：%d OK / %d NG" % (OK[0], OK[1]))
    return 0 if OK[1] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
