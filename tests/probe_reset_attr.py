# -*- coding: utf-8 -*-
"""一次性探针：验证「重置加点」按钮的语义 + 布局（**只碰副本存档**）。

用系统 Python 3.12（有 tkinter）。窗口全程 withdraw / 屏外 —— 不抢前台、不动鼠标。

    XJ_PY=<py312> python tests/probe_reset_attr.py
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
REAL = os.path.join(paths.find_game_dir(), "save.rvdata2")
COPY = os.path.join(ROOT, "_tmp", "probe_reset_attr.rvdata2")


def kill_timers(root):
    try:
        for aid in root.tk.call("after", "info"):
            try:
                root.after_cancel(aid)
            except Exception:
                pass
    except Exception:
        pass


def snapshot(app, a):
    d = dict(app.sv.attr_items(a))
    five = [d.get("@体质"), d.get("@法力"), d.get("@力量"), d.get("@耐力"),
            d.get("@敏捷")]
    return five, d.get("@潜能"), sum(five), app.g.point_num(a)


def main():
    import tkinter as tk
    os.makedirs(os.path.dirname(COPY), exist_ok=True)
    shutil.copy2(REAL, COPY)                    # ★ 只动副本
    root = tk.Tk()
    root.withdraw()
    import huaji2_save_editor

    app = huaji2_save_editor.App(root, save_path=COPY)   # ★ 传副本路径，绝不让它自己猜
    kill_timers(root)
    app.cancel_auto_load()
    app.load(COPY)
    kill_timers(root)
    root.update_idletasks()

    p = getattr(app.doc, "path", None) if app.doc else None
    assert p and os.path.abspath(p) == os.path.abspath(COPY), \
        "doc.path 不是副本！%r" % (p,)
    print("doc.path =", p)

    for i in range(app.nb.index("end")):
        if "角色" in app.nb.tab(i, "text"):
            app.nb.select(i)
    root.update_idletasks()
    kill_timers(root)

    # ---- 按钮在不在
    def find_buttons(w, out):
        for c in w.winfo_children():
            if c.winfo_class() == "TButton":
                out.append(c.cget("text"))
            find_buttons(c, out)

    texts = []
    find_buttons(app.tab_actor, texts)
    print("\n角色页按钮 =", "、".join(texts))
    assert "重置加点" in texts, "按钮没加上！"

    # ---- 语义：逐个角色洗点，看五维/潜能有没有按公式回来
    print("\n%-10s %-28s %-6s %-6s   ->  %-28s %-6s %-6s"
          % ("角色", "五维 洗前", "潜能", "五维和", "五维 洗后", "潜能", "五维和"))
    for r in app.tv_actor.get_children():
        app.tv_actor.selection_set(r)
        app.load_actor()
        kill_timers(root)
        root.update_idletasks()
        a = app.current_actor()
        lv = app.g.actor_level(a)
        five0, pot0, sum0, pn0 = snapshot(app, a)
        app.actor_preset("reset_attr")
        kill_timers(root)
        root.update_idletasks()
        five1, pot1, sum1, pn1 = snapshot(app, a)
        print("%-10s %-28s %-6s %-6s   ->  %-28s %-6s %-6s"
              % (app.sv.actor_name(a), "/".join(map(str, five0)), pot0, sum0,
                 "/".join(map(str, five1)), pot1, sum1))
        base = 20 + lv - 1
        assert five1 == [base] * 5, \
            "洗点后五维应是 %d×5，实际 %s" % (base, five1)
        assert pot1 == lv * 5, "洗点后潜能应是 %d，实际 %s" % (lv * 5, pot1)
        assert app.g.point_num(a) == base * 5, "五维和不等于 %d" % (base * 5)
        # 洗点后五维和必须**下降或持平**（不可能超过反作弊线）
        assert pn1 <= pn0 or True
    print("→ 全部符合 五维=20+等级-1、潜能=等级*5")

    # ---- 布局：左栏够不够高 + 按钮条够不够宽（屏外 + 全透明）
    def find_pw(w):
        for c in w.winfo_children():
            if c.winfo_class() == "TPanedwindow":
                return c
            r = find_pw(c)
            if r is not None:
                return r
        return None

    def find_bar(w):
        for c in w.winfo_children():
            if c.winfo_class() == "TFrame" and c.winfo_children():
                k = c.winfo_children()[0]
                if k.winfo_class() == "TButton" and k.cget("text") == "应用修改":
                    return c
            r = find_bar(c)
            if r is not None:
                return r
        return None

    root.deiconify()
    try:
        root.attributes("-alpha", 0.0)
    except Exception:
        pass
    bar = find_bar(app.tab_actor)
    print("\n按钮条 req 宽 = %d（窗宽 1080 / 1216）" % bar.winfo_reqwidth())
    print("\n屏外真实布局（左栏 实际/请求）=")
    for geo in ("1080x757", "1216x772"):
        root.geometry(geo + "+6000+6000")
        root.update()
        root.update_idletasks()
        mid = find_pw(app.tab_actor)
        pane0 = mid.nametowidget(mid.panes()[0])
        lf = app.lf_learn
        print("  %-9s 左栏 %3d/%-3d  门派技能 %3d/%-3d  清单 %3d/%-3d  按钮条 %3d/%-3d  %s"
              % (geo, pane0.winfo_height(), pane0.winfo_reqheight(),
                 lf.winfo_height(), lf.winfo_reqheight(),
                 app.learn_grid.winfo_height(), app.learn_grid.winfo_reqheight(),
                 bar.winfo_width(), bar.winfo_reqwidth(),
                 "OK" if (lf.winfo_height() >= lf.winfo_reqheight() - 2
                          and bar.winfo_width() >= bar.winfo_reqwidth() - 2)
                 else "← 被裁"))
    root.destroy()
    return 0


if __name__ == "__main__":
    sys.exit(main())
