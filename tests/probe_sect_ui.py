# -*- coding: utf-8 -*-
"""一次性探针：验证角色页的「门派」下拉 + 左栏「门派技能」清单（**只碰副本存档**）。

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
COPY = os.path.join(ROOT, "_tmp", "probe_gui_save.rvdata2")


def kill_timers(root):
    try:
        for aid in root.tk.call("after", "info"):
            try:
                root.after_cancel(aid)
            except Exception:
                pass
    except Exception:
        pass


def main():
    import tkinter as tk
    os.makedirs(os.path.dirname(COPY), exist_ok=True)
    shutil.copy2(REAL, COPY)                    # 只动副本
    root = tk.Tk()
    root.withdraw()
    import huaji2_save_editor
    from tables import sect

    app = huaji2_save_editor.App(root, save_path=COPY)   # ★ 传副本路径，绝不让它自己猜
    kill_timers(root)
    app.cancel_auto_load()
    app.load(COPY)                              # 明确载入副本（load 会先撤掉排队回调）
    kill_timers(root)
    root.update_idletasks()

    # 三条红线之一：确认 doc 指的是副本
    p = getattr(app.doc, "path", None) if app.doc else None
    assert p and os.path.abspath(p) == os.path.abspath(COPY), \
        "doc.path 不是副本！%r" % (p,)
    print("doc.path =", p)

    # 切到角色页
    for i in range(app.nb.index("end")):
        if "角色" in app.nb.tab(i, "text"):
            app.nb.select(i)
    root.update_idletasks(); root.update()
    kill_timers(root)

    cb_sect = getattr(app, "cb_actor_sect", None)
    var_sect = getattr(app, "var_actor_sect", None)
    print("cb_actor_sect =", cb_sect)
    print("  选项 =", cb_sect["values"] if cb_sect else None)
    print("  var_actor_sect 初值 =", var_sect.get() if var_sect else None)

    rows = app.tv_actor.get_children()
    print("\n角色行数 =", len(rows))
    for r in rows:
        app.tv_actor.selection_set(r)
        app.load_actor()
        kill_timers(root)
        root.update_idletasks()
        a = app.current_actor()
        print("  %-8s 界面门派=%-6s 存档=%s/%s  下拉可选 %d 个"
              % (app.sv.actor_name(a),
                 var_sect.get() if var_sect else "-",
                 app.g.actor_sect_id(a), app.g.actor_sect_name(a),
                 len(app.skp_actor.choices)))

    # —— 手动切门派：右边一览不变，左栏「门派技能」清单跟着换
    print("\n== 手动切「门派」（当前角色 %s）=="
          % app.sv.actor_name(app.current_actor()))
    for label in ("", "五庄观", "龙宫", "不存在的门派"):
        var_sect.set(label)
        app.skp_actor.fill()
        app.rebuild_learn_grid()
        root.update_idletasks()
        print("  %-8s -> 右下一览(已学) %3d 个；左栏清单 %2d 个：%s"
              % (label or "（未选）", len(app.skp_actor.choices),
                 len(app._learn_sids),
                 "、".join("#%d" % s for s in app._learn_sids[:3])))

    # —— 右栏搜索仍然独立可用
    var_sect.set("五庄观")
    app.var_actor_skill_search.set("炼")
    app.skp_actor.fill()
    print("  搜索「炼」（只筛已学那一份） ->", app.skp_actor.choices[:3],
          "（共 %d 个）" % len(app.skp_actor.choices))
    app.var_actor_skill_search.set("")

    # —— 召唤兽页不该有门派下拉
    print("\ncb_baby_sect =", getattr(app, "cb_baby_sect", None),
          "（应为 None）")

    # —— 各块请求尺寸（门派下拉搬进左栏后，页宽/页高有没有超）
    kill_timers(root)
    root.update_idletasks()
    print("\n角色页 req = %dx%d（可用 1216x772）"
          % (app.tab_actor.winfo_reqwidth(), app.tab_actor.winfo_reqheight()))
    print("各 LabelFrame req =")

    def _walk(w):
        for c in w.winfo_children():
            if c.winfo_class() == "TLabelframe":
                print("  %-26s %4d x %4d"
                      % (c.cget("text")[:24], c.winfo_reqwidth(),
                         c.winfo_reqheight()))
            _walk(c)

    _walk(app.tab_actor)

    # —— 屏外真实布局体检：左栏够不够高（不够先被裁的是它最后 pack 的
    #    「门派技能」清单；2026-09-20 就这样把「一键学习」按钮裁没了）。
    #    窗口挪到屏幕外 + 全透明 —— 不抢前台、看不见。
    def _find_pw(w):
        for c in w.winfo_children():
            if c.winfo_class() == "TPanedwindow":
                return c
            r = _find_pw(c)
            if r is not None:
                return r
        return None

    root.deiconify()
    try:
        root.attributes("-alpha", 0.0)
    except Exception:
        pass
    print("\n屏外真实布局（左栏 实际/请求）=")
    for geo in ("1080x757", "1216x772"):
        root.geometry(geo + "+6000+6000")
        root.update()
        root.update_idletasks()
        mid = _find_pw(app.tab_actor)
        pane0 = mid.nametowidget(mid.panes()[0])
        lf = app.lf_learn
        print("  %-9s 左栏 %3d/%-3d  门派技能 %3d/%-3d  清单 %3d/%-3d  %s"
              % (geo, pane0.winfo_height(), pane0.winfo_reqheight(),
                 lf.winfo_height(), lf.winfo_reqheight(),
                 app.learn_grid.winfo_height(), app.learn_grid.winfo_reqheight(),
                 "OK" if lf.winfo_height() >= lf.winfo_reqheight() - 2
                 else "← 被裁"))
    root.destroy()
    return 0


if __name__ == "__main__":
    sys.exit(main())
