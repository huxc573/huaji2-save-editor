# -*- coding: utf-8 -*-
"""一次性布局探针：量每个页签**需要**多大，跟窗口默认尺寸比。

用系统 Python 3.12（有 tkinter）。窗口全程 withdraw —— 不抢前台、不动鼠标。
量的是 winfo_reqwidth/reqheight（几何管理器按内容算的请求尺寸，跟有没有 map 无关），
所以 withdraw 下也能得到真数（tkinter-gui-layout-probe 技能里的第 ★★ 条）。

⚠ ttk::Notebook 的请求尺寸 = 页签条 + **所有页**的最大请求尺寸，
  root.winfo_reqheight() 就是「这个窗口至少要多高才不裁掉任何一页」。
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

OUT = os.path.join(HERE, "_probe_layout.txt")
BUF = []


def w(line=""):
    """每写一行就落盘一次（脚本中途挂掉也有半程证据）。"""
    BUF.append(str(line))
    try:
        with open(OUT, "w", encoding="utf-8") as fh:
            fh.write("\n".join(BUF) + "\n")
    except OSError:
        pass
    try:
        print(line)
    except Exception:
        pass


def kill_timers(root):
    try:
        for aid in root.tk.call("after", "info"):
            try:
                root.after_cancel(aid)
            except Exception:
                pass
    except Exception:
        pass


def tree(w_, depth=0, maxd=2):
    """递归打印子控件的请求尺寸（只到 maxd 层，够用）。"""
    if depth > maxd:
        return
    for c in w_.winfo_children():
        try:
            txt = c.cget("text")
        except Exception:
            txt = ""
        w("%s%s %-14s req=%5dx%-5d %s"
          % ("  " * (depth + 1), c.__class__.__name__, c.winfo_class(),
             c.winfo_reqwidth(), c.winfo_reqheight(),
             ("«%s»" % txt[:22]) if txt else ""))
        tree(c, depth + 1, maxd)


def main():
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()                     # ★ 永不 map
    import huaji2_save_editor

    app = huaji2_save_editor.App(root, save_path=None)
    kill_timers(root)
    root.update_idletasks()
    root.update()

    w("=" * 78)
    w("窗口默认 geometry = 1220x800（huaji2_save_editor.py 里 root.geometry）")
    w("根窗口请求尺寸 req = %dx%d" % (root.winfo_reqwidth(),
                                       root.winfo_reqheight()))
    w("Notebook 请求尺寸 req = %dx%d" % (app.nb.winfo_reqwidth(),
                                          app.nb.winfo_reqheight()))
    w("=" * 78)

    # 页签条高度 = nb 请求高 - 最大页请求高
    n = app.nb.index("end")
    pages = []
    for i in range(n):
        name = app.nb.tab(i, "text")
        fr = root.nametowidget(app.nb.tabs()[i])
        pages.append((i, name, fr))
        w("[%d] %-16s req=%5dx%-5d" % (i, name, fr.winfo_reqwidth(),
                                        fr.winfo_reqheight()))
    chrome_h = app.nb.winfo_reqheight() - max(p[2].winfo_reqheight()
                                              for p in pages)
    chrome_w = app.nb.winfo_reqwidth() - max(p[2].winfo_reqwidth()
                                             for p in pages)
    w("")
    w("页签条+边框 占高 = %d px，占宽 = %d px" % (chrome_h, chrome_w))
    w("→ 各页**可用**高度 = 800 - %d = %d px" % (chrome_h, 800 - chrome_h))
    w("→ 各页**可用**宽度 = 1220 - %d = %d px" % (chrome_w, 1220 - chrome_w))
    w("")
    w("超出可用空间的页（会被裁）：")
    bad = 0
    for i, name, fr in pages:
        hi = fr.winfo_reqheight() > 800 - chrome_h
        wi = fr.winfo_reqwidth() > 1220 - chrome_w
        if hi or wi:
            bad += 1
            w("   ! [%d] %-16s %s%s req=%dx%d" % (
                i, name, "太高 " if hi else "", "太宽" if wi else "",
                fr.winfo_reqwidth(), fr.winfo_reqheight()))
    if not bad:
        w("   （无）")
    w("")

    # ---------------- 角色页细看
    w("=" * 78)
    w("角色页 / 属性 —— 逐层请求尺寸")
    app.nb.select(0)
    for i, name, fr in pages:
        if "角色" in name:
            app.nb.select(i)
    root.update_idletasks()
    root.update()
    tree(app.tab_actor, 0, 1)
    w("")
    w("-- 角色页 关键控件 --")
    for nm, wid in (("tv_actor", app.tv_actor),
                    ("_actor_entry_parent(基础字段)",
                     root.nametowidget(app._actor_entry_parent)),
                    ("tv_actor_skills", app.tv_actor_skills),
                    ("txt_actor_skill_desc", app.txt_actor_skill_desc),
                    ("txt_actor(概览)", app.txt_actor)):
        w("   %-28s req=%5dx%-5d" % (nm, wid.winfo_reqwidth(),
                                      wid.winfo_reqheight()))
    w("")
    w("-- 角色页 右栏 上下分栏 --")
    vp = app.tv_actor_skills.master          # 技能区 LabelFrame
    skf = vp
    w("   技能 LabelFrame req=%dx%d" % (skf.winfo_reqwidth(),
                                        skf.winfo_reqheight()))
    ovf = app.txt_actor.master.master
    w("   概览 LabelFrame req=%dx%d" % (ovf.winfo_reqwidth(),
                                        ovf.winfo_reqheight()))
    w("   父 Panedwindow(vp) req=%dx%d" % (vp.master.winfo_reqwidth(),
                                           vp.master.winfo_reqheight()))
    # 技能区各子控件
    for c in skf.winfo_children():
        try:
            t = c.cget("text")
        except Exception:
            t = ""
        w("     - %-14s req=%5dx%-5d %s" % (c.winfo_class(),
                                            c.winfo_reqwidth(),
                                            c.winfo_reqheight(),
                                            ("«%s»" % t[:20]) if t else ""))
    w("")
    # ttk.Panedwindow 的 pane 支持哪些选项？
    cl = vp.master
    for opt in ("minsize", "weight", "pad", "sticky"):
        try:
            cl.pane(0, **{opt: 200})
            w("   pane(0, %s=200) -> OK" % opt)
        except Exception as e:
            w("   pane(0, %s=200) -> %s" % (opt, e))
    w("")

    # ---------------- 召唤兽页细看
    w("=" * 78)
    w("召唤兽页 —— 关键控件请求尺寸")
    for i, name, fr in pages:
        if "召唤兽" in name:
            app.nb.select(i)
    root.update_idletasks()
    root.update()
    for nm, wid in (("tv_babies", app.tv_babies), ("tv_baby", app.tv_baby),
                    ("tv_baby_skills", app.tv_baby_skills),
                    ("txt_baby_skill_desc", app.txt_baby_skill_desc),
                    ("txt_baby", app.txt_baby)):
        w("   %-24s req=%5dx%-5d" % (nm, wid.winfo_reqwidth(),
                                      wid.winfo_reqheight()))
    w("   召唤兽页 整页 req=%dx%d" % (app.tab_baby.winfo_reqwidth(),
                                      app.tab_baby.winfo_reqheight()))

    w("")
    w("-- 角色页 / 召唤兽页 内容最大宽度对比（会不会把窗口撑宽） --")
    w("   角色页 reqwidth = %d" % app.tab_actor.winfo_reqwidth())
    w("   召唤兽页 reqwidth = %d" % app.tab_baby.winfo_reqwidth())

    # ---------------- 超宽页逐行诊断：到底是哪一行宽
    w("")
    w("=" * 78)
    w("超宽页诊断：找出 reqwidth 最大的那一行（横向滚动条能兜住的就不算问题）")
    for i, name, fr in pages:
        if fr.winfo_reqwidth() <= 1216:
            continue
        w("")
        w("[%d] %s  整页 req=%dx%d" % (i, name, fr.winfo_reqwidth(),
                                       fr.winfo_reqheight()))
        rows = []
        for c in fr.winfo_children():
            try:
                t = c.cget("text")
            except Exception:
                t = ""
            rows.append((c.winfo_reqwidth(), c.winfo_class(),
                         ("«%s»" % str(t)[:18]) if t else ""))
        rows.sort(reverse=True)
        for rw, cls, t in rows[:6]:
            w("      %5d px  %-14s %s" % (rw, cls, t))

    root.destroy()
    w("")
    w("==== 完 ====")
    return 0


if __name__ == "__main__":
    sys.exit(main())
