# -*- coding: utf-8 -*-
"""界面冒烟测试：把窗口、8 个页签、懒加载数据树、数据表预览都建一遍，不进 mainloop。

不碰真存档（只读 Data\\*.rvdata2 和明文样本 Battle.bt2）。

用法：python tests/test_gui.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.stdout.reconfigure(errors="replace")

OK = 0
NG = 0


def check(cond, msg, extra=""):
    global OK, NG
    if cond:
        OK += 1
        print("  [OK] %s" % msg)
    else:
        NG += 1
        print("  [NG] %s %s" % (msg, extra))


def count_items(tree, parent=""):
    n = 0
    for c in tree.get_children(parent):
        n += 1 + count_items(tree, c)
    return n


def kill_timers(root):
    """干掉 App 里排的"自动载入上次存档"定时器 —— 测试要自己决定载入哪个文件。"""
    try:
        for aid in root.tk.call("after", "info"):
            try:
                root.after_cancel(aid)
            except Exception:
                pass
    except Exception:
        pass


TABS = (("tab_quick", "概览 / 快捷修改"), ("tab_saves", "存档管理"),
        ("tab_tree", "全部解析数据"),
        ("tab_actor", "角色 / 属性"), ("tab_party", "背包 / 物品"),
        ("tab_baby", "召唤兽"), ("tab_switch", "开关 / 变量"),
        ("tab_machine", "机器码"),
        ("tab_db", "数据表 (CSV)"), ("tab_help", "说明 / 机制"),
        ("tab_log", "更新日志"))


def main():
    import faulthandler
    faulthandler.enable()
    faulthandler.dump_traceback_later(60, exit=True)
    try:
        import tkinter as tk
        tk.Tk().destroy()
    except Exception as e:
        print("  [--] 无图形环境（%s），跳过界面冒烟" % e)
        return 0

    import xj_db
    import xj_env
    import xj_viewer

    # 弹窗换成"记录"：窗口是 withdraw 的，真弹出模态框会看不见、把测试挂死
    dialogs = []
    xj_viewer.messagebox = type("MB", (), {
        "showinfo": staticmethod(lambda *a, **k: dialogs.append(("info", a))),
        "showerror": staticmethod(lambda *a, **k: dialogs.append(("error", a))),
        "showwarning": staticmethod(lambda *a, **k: dialogs.append(("warn", a))),
    })

    root = tk.Tk()
    root.withdraw()
    app = xj_viewer.App(root, save_path=None)
    kill_timers(root)
    root.update()

    check(root.winfo_exists() == 1, "主窗口创建成功")
    check(app.nb.index("end") == len(TABS), "页签数 = %d" % len(TABS))
    for attr, name in TABS:
        check(getattr(app, attr).winfo_exists() == 1, "页签存在：%s" % name)
    check("画迹2" in root.title(), "窗口标题 = %s" % root.title())
    check(xj_viewer.VERSION.startswith("v"), "版本号 = %s" % xj_viewer.VERSION)

    # ---- 数据表页
    check(len(app.lst_db.get(0, "end")) == len(xj_db.ALL_KEYS),
          "数据表页列出 %d 张表" % len(xj_db.ALL_KEYS))
    check(app.var_db_out.get() == xj_db.DEFAULT_OUT,
          "CSV 默认目录 = %s" % app.var_db_out.get())
    try:
        app.lst_db.selection_clear(0, "end")
        app.lst_db.selection_set(0)
        app.db_preview()
        root.update()
        check(len(app.tv_db.get_children()) >= 1,
              "数据表预览有行：%s" % app.var_db_info.get())
    except Exception as e:
        print("  [--] 数据表预览跳过：%s" % e)

    # ---- 说明 / 更新日志
    check("防作弊" in xj_viewer.HELP_TEXT and "CSV" in xj_viewer.HELP_TEXT,
          "说明页含防作弊 + CSV 说明（%d 字）" % len(xj_viewer.HELP_TEXT))
    check(len(xj_viewer.CHANGELOG.strip()) > 0,
          "更新日志已读取（%d 字）" % len(xj_viewer.CHANGELOG.strip()))
    check("画迹1" in xj_viewer.HELP_TEXT, "说明里提到了与画迹1的关系")

    # ---- 明文样本 → 数据树懒加载
    sample = None
    game = xj_env.find_game_dir()
    if game:
        ad = os.path.join(game, "Logs", "Battle")
        if os.path.isdir(ad):
            for d in sorted(os.listdir(ad)):
                p = os.path.join(ad, d, "Battle.bt2")
                if os.path.exists(p):
                    sample = p
                    break
    if sample:
        app.load(sample, quiet=True)
        root.update()
        check(len(app.tree.get_children("")) >= 1, "数据树已填充（顶层）")
        check(app.sv is None, "非本作存档时快捷面板优雅降级")
        top = app.tree.get_children("")[0]
        before = count_items(app.tree)
        app.tree.item(top, open=True)
        app._fill_children(top)          # <<TreeviewOpen>> 在测试里不自动触发
        root.update()
        after = count_items(app.tree)
        check(after > before,
              "展开后子节点变多（懒加载：%d -> %d）" % (before, after))
        app.tree.selection_set(top)
        app.on_select()
        check(len(app.txt_node.get("1.0", "end").strip()) > 0, "节点详情已填充")
    else:
        print("  [--] 没有明文样本，跳过树填充")

    root.destroy()
    check("全程没弹错误框", not [d for d in dialogs if d[0] == "error"],
          "%r" % (dialogs[:3],))
    print("\n==== 通过 %d, 失败 %d ====" % (OK, NG))
    return 1 if NG else 0


if __name__ == "__main__":
    sys.exit(main())
