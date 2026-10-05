# -*- coding: utf-8 -*-
"""召唤兽页布局探针：实测各控件几何，比截图可靠（Tk 的 PrintWindow 常返回全白）。

2026-10-04 川截图反馈「界面排版还需要优化」——根因是一览表的 parent 写错、
被 `pack(side="left")` 抢走整页左边缘。这个探针用来复核修完后的上下关系。

用法：XJ_PY=<py312> python tests/probe_baby_layout.py
⚠ 必须用带 tkinter 的系统 Py3.12；窗口按 alpha=0 建（会映射、几何才准，但看不见）。
⚠ 全程只碰**真档的副本**。
"""
import io
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import tkinter as tk            # noqa: E402
import paths                    # noqa: E402
import huaji2_save_editor as P  # noqa: E402


class _FakeMB(object):
    """弹窗会把探针挂死（messagebox 阻塞）——全部换掉，只打印。"""
    @staticmethod
    def showinfo(*a, **k):
        print("    [弹窗 info] %r" % (a[:2],))

    @staticmethod
    def showwarning(*a, **k):
        print("    [弹窗 warning] %r" % (a[:2],))

    @staticmethod
    def showerror(*a, **k):
        print("    [弹窗 error] %r" % (a[:2],))

    @staticmethod
    def askyesno(*a, **k):
        print("    [弹窗 ask] %r" % (a[:2],))
        return False


P.messagebox = _FakeMB

src = paths.save_path()
tmp = os.path.join(tempfile.gettempdir(), "xj_layout_probe.rvdata2")
shutil.copy2(src, tmp)

root = tk.Tk()
root.attributes("-alpha", 0.0)
app = P.App(root, save_path=tmp)
app.cancel_auto_load()
app.load(tmp)
root.update()
app.nb.select(app.tab_baby)
root.update()

f = app.tab_baby
print("窗口 %dx%d ；召唤兽页 %dx%d" % (
    root.winfo_width(), root.winfo_height(), f.winfo_width(), f.winfo_height()))

print("\n--- 页 frame 的直接子控件（= pack 顺序）---")
for ch in f.winfo_children():
    print("  %-12s %-10s x=%-4d y=%-4d w=%-5d h=%-4d  req=%dx%d" % (
        ch.winfo_name(), ch.winfo_class(), ch.winfo_x(), ch.winfo_y(),
        ch.winfo_width(), ch.winfo_height(),
        ch.winfo_reqwidth(), ch.winfo_reqheight()))

tv = app.tv_babies
bw = tv.master
print("\n--- 一览表 ---")
print("  列宽合计 %d ；容器 bw 宽 %d ；页宽 %d" % (
    sum(tv.column(c, "width") for c in tv["columns"]),
    bw.winfo_width(), f.winfo_width()))
print("  bw 内容: %s" % [(c.winfo_class(), c.winfo_name())
                        for c in bw.winfo_children()])
print("  tv_babies 屏幕 y=%d  x=%d  w=%d h=%d" % (
    tv.winfo_rooty(), tv.winfo_rootx(), tv.winfo_width(), tv.winfo_height()))

tb = app.tv_baby
print("\n--- 字段表（改字段下面那张）---")
print("  tv_baby   屏幕 y=%d  x=%d  w=%d h=%d  master=%s" % (
    tb.winfo_rooty(), tb.winfo_rootx(), tb.winfo_width(), tb.winfo_height(),
    tb.master.winfo_name()))
print("  常用区 master=%s 宽 %d" % (tb.master.master.winfo_name(),
                                    tb.master.master.winfo_width()))

pick = None
for ch in f.winfo_children():
    for sub in ch.winfo_children():
        try:
            if sub.winfo_class() == "TLabel" and sub.cget("text") == "改字段：":
                pick = ch
        except Exception:
            pass
if pick is not None:
    print("\n--- 「改字段」行 ---")
    print("  req=%d ；页内容宽=%d ⇒ %s" % (
        pick.winfo_reqwidth(), f.winfo_width() - 16,
        "放不下、会被裁" if pick.winfo_reqwidth() > f.winfo_width() - 16
        else "放得下"))
    print("  行内控件: %s" % [c.winfo_class() for c in pick.winfo_children()])

mid = tb.master.master
print("\n--- mid（字段表 | 常用 + 详细信息）---")
for ch in mid.winfo_children():
    print("  %-10s x=%-4d y=%-4d w=%-5d h=%-5d req=%dx%d" % (
        ch.winfo_name(), ch.winfo_x(), ch.winfo_y(),
        ch.winfo_width(), ch.winfo_height(),
        ch.winfo_reqwidth(), ch.winfo_reqheight()))
    for sub in ch.winfo_children():
        txt = ""
        try:
            if sub.winfo_class() in ("TLabelFrame", "TLabel"):
                txt = sub.cget("text")
        except Exception:
            pass
        print("      %-12s x=%-4d y=%-4d w=%-5d h=%-5d req=%dx%d  %s" % (
            sub.winfo_class(), sub.winfo_x(), sub.winfo_y(),
            sub.winfo_width(), sub.winfo_height(),
            sub.winfo_reqwidth(), sub.winfo_reqheight(), txt))

print("\n--- 结论 ---")
print("  ✅ 一览表在字段表上方: %s" % (tv.winfo_rooty() < tb.winfo_rooty()))
print("  ✅ 一览表贴左（不是被挤到右栏）: %s" % (tv.winfo_rootx() < f.winfo_rootx() + 40))
print("  ✅ 竖滚动条与表格同 frame: %s" % any(
    c is not tv for c in bw.winfo_children()))

# ---- 川的窗口比默认窄（截图那把约 1080x733）：再复核一遍关键行 ----
root.geometry("1080x733")
root.update()
print("\n--- 1080x733（川截图那个尺寸）---")
print("  页 %dx%d ；一览表容器 w=%d（列需求 %d）" % (
    f.winfo_width(), f.winfo_height(), bw.winfo_width(),
    sum(tv.column(c, "width") for c in tv["columns"])))
print("  改字段行 req=%d（可用 %d）" % (
    pick.winfo_reqwidth() if pick else -1, f.winfo_width() - 16))
_over = [(c.winfo_name(), c.winfo_reqwidth(), c.winfo_width())
         for c in f.winfo_children() if c.winfo_reqwidth() > c.winfo_width() + 2]
print("  请求宽 > 实际宽的控件（会被裁）: %r" % (_over,))

sys.stdout.flush()
root.destroy()
os._exit(0)
