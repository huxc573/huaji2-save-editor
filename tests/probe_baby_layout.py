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

# ---- 「进阶」两个按钮（2026-10-08 新加，并入预设按钮那行）
def _find_btn(w, want):
    for ch in w.winfo_children():
        try:
            if ch.winfo_class() == "TButton" and ch.cget("text") == want:
                return ch
        except Exception:
            pass
        hit = _find_btn(ch, want)
        if hit is not None:
            return hit
    return None


_bp = _find_btn(f, "进阶")
_bf = _find_btn(f, "进阶并拉满")
print("\n--- 「进阶」按钮 ---")
if _bp is None or _bf is None:
    print("  ❌ 没找到（进阶=%r 进阶并拉满=%r）" % (_bp, _bf))
else:
    row = _bp.master
    print("  在「%s」那一行；进阶 w=%d、进阶并拉满 w=%d（合计 %d）"
          % (row.winfo_name(), _bp.winfo_width(), _bf.winfo_width(),
             _bp.winfo_reqwidth() + _bf.winfo_reqwidth()))
    print("  该行 req=%d ；页内容宽=%d ⇒ %s" % (
        row.winfo_reqwidth(), f.winfo_width() - 16,
        "放不下、会被裁" if row.winfo_reqwidth() > f.winfo_width() - 16
        else "放得下（余 %d）" % (f.winfo_width() - 16 - row.winfo_reqwidth())))
    print("  映射可见: %s / %s" % (_bp.winfo_ismapped(), _bf.winfo_ismapped()))

# ---- 角色行（角色下拉 + 新增/出战/放生/恢复模板名/重置加点）----
def _dump_actor_row(tag):
    _br = _find_btn(f, "重置加点")
    print("\n--- 「重置加点」按钮（在角色行）· %s ---" % tag)
    if _br is None:
        print("  ❌ 没找到")
        return
    _row = _br.master
    _page_w = f.winfo_width()
    print("  在「%s」那一行；自身 x=%d w=%d (右边缘 %d) ；页可用宽=%d ⇒ %s"
          % (_row.winfo_name(), _br.winfo_x(), _br.winfo_width(),
             _br.winfo_x() + _br.winfo_width(), _page_w - 16,
             "露出来了" if _br.winfo_x() + _br.winfo_width() <= _page_w - 16
             else "被挤出可视区、看不见！"))
    print("  该行 req=%d ；实际 %d ；映射可见=%s"
          % (_row.winfo_reqwidth(), _row.winfo_width(), _br.winfo_ismapped()))
    _sib = []
    for _c in _row.winfo_children():
        _t = ""
        try:
            _t = _c.cget("text")
        except Exception:
            pass
        _sib.append((_c.winfo_class(), _c.winfo_x(), _c.winfo_width(), _t))
    print("  行内按 x 排（找被挤到页外/叠在一起的）：")
    for _s in sorted(_sib, key=lambda z: z[1]):
        print("      x=%-4d w=%-4d %-10s %s" % (_s[1], _s[2], _s[0], _s[3]))


_dump_actor_row("默认")

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

def _spill2(w):
    bad = []
    for ch in w.winfo_children():
        if not ch.winfo_ismapped():
            continue
        if (ch.winfo_y() + ch.winfo_height() > w.winfo_height() + 2
                or ch.winfo_x() + ch.winfo_width() > w.winfo_width() + 2):
            bad.append((ch.winfo_class(), ch.winfo_name(),
                        ch.winfo_width(), ch.winfo_height(),
                        w.winfo_width(), w.winfo_height(),
                        w.winfo_height() - (ch.winfo_y() + ch.winfo_height())))
        bad.extend(_spill2(ch))
    return bad


# ---- 默认尺寸（1220x800）先量一遍：川开起来看到的就是这个 ----
print("\n--- 默认 1220x800 ---")
for _s in _spill2(f):
    print("      溢出 %-12s %-12s %dx%d > parent %dx%d（差 %d）" % _s)

# ---- 川的窗口比默认窄（截图那把约 1080x733）：再复核一遍关键行 ----
root.geometry("1080x733")
root.update()
print("\n--- 1080x733（川截图那个尺寸）---")
_dump_actor_row("1080")
print("  页 %dx%d ；一览表容器 w=%d（列需求 %d）" % (
    f.winfo_width(), f.winfo_height(), bw.winfo_width(),
    sum(tv.column(c, "width") for c in tv["columns"])))
print("  改字段行 req=%d（可用 %d）" % (
    pick.winfo_reqwidth() if pick else -1, f.winfo_width() - 16))
_over = [(c.winfo_name(), c.winfo_reqwidth(), c.winfo_width())
         for c in f.winfo_children() if c.winfo_reqwidth() > c.winfo_width() + 2]
print("  请求宽 > 实际宽的控件（横向会被裁）: %r" % (_over,))
# 纵向：pack 先来先分地盘，超出页高的那些（最后 pack 的）会被挤出去/压成 0 高
_bot = f.winfo_height()
_vover = [(c.winfo_name(), c.winfo_y() + c.winfo_height(), _bot)
          for c in f.winfo_children()
          if c.winfo_y() + c.winfo_height() > _bot + 2 or c.winfo_height() <= 1]
print("  内容底边 > 页高 的控件（纵向会被裁）: %r" % (_vover,))
print("  页内容总高 %d ；页高 %d ⇒ %s" % (
    sum(c.winfo_reqheight() for c in f.winfo_children()), _bot,
    "够" if sum(c.winfo_reqheight() for c in f.winfo_children()) <= _bot
    else "不够（最后 pack 的会被切，看下面递归结果）"))


def _spill(w, top=None):
    """递归找「底边/右边超出自己 parent」的控件 —— 那才是真被切的。"""
    bad = []
    for ch in w.winfo_children():
        if not ch.winfo_ismapped():
            continue
        if (ch.winfo_y() + ch.winfo_height() > w.winfo_height() + 2
                or ch.winfo_x() + ch.winfo_width() > w.winfo_width() + 2):
            bad.append((ch.winfo_class(), ch.winfo_name(),
                        ch.winfo_x(), ch.winfo_y(),
                        ch.winfo_width(), ch.winfo_height(),
                        "parent %dx%d" % (w.winfo_width(), w.winfo_height())))
        bad.extend(_spill(ch))
    return bad


_sp = _spill(f)
print("  递归溢出（真被切）共 %d 个：" % len(_sp))
for _s in _sp[:12]:
    print("      %-12s %-10s x=%-4d y=%-4d %dx%d  >  %s" % _s)

sys.stdout.flush()
root.destroy()
os._exit(0)
