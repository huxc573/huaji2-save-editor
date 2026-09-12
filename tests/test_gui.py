# -*- coding: utf-8 -*-
"""界面冒烟测试：把窗口和三个页签都建一遍，不进入 mainloop。

用法： python tests/test_gui.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.stdout.reconfigure(errors="replace")

OK = 0
NG = 0


def check(cond, msg):
    global OK, NG
    if cond:
        OK += 1
        print("  [OK] %s" % msg)
    else:
        NG += 1
        print("  [NG] %s" % msg)


def main():
    try:
        import tkinter as tk
    except Exception as e:
        print("  [--] 没有 tkinter：%s" % e)
        return
    try:
        tk.Tk().destroy()
    except Exception as e:
        print("  [--] 无图形环境（%s），跳过界面冒烟" % e)
        return

    import xj_viewer  # noqa: E402
    app = xj_viewer.App()
    app.update()
    check(app.winfo_exists() == 1, "主窗口创建成功")
    check(app.tab_over.winfo_exists() == 1, "概览页存在")
    check(app.tab_tree.winfo_exists() == 1, "数据树页存在")
    check(app.tab_help.winfo_exists() == 1, "说明页存在")
    check("游戏目录" in app.txt_over.get("1.0", "end"), "概览页已填环境信息")

    # 打开一个明文样本，验证树能建起来
    import xj_env  # noqa: E402
    game = xj_env.find_game_dir()
    sample = None
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
        app.update()
        check(len(app.tree.get_children("")) >= 1, "数据树已填充")
        n = count_items(app.tree)
        check(n > 10, "树节点数 = %d" % n)
    else:
        print("  [--] 没有明文样本，跳过树填充")

    app.destroy()
    print("\n==== 通过 %d, 失败 %d ====" % (OK, NG))
    sys.exit(1 if NG else 0)


def count_items(tree, parent=""):
    n = 0
    for c in tree.get_children(parent):
        n += 1 + count_items(tree, c)
    return n


if __name__ == "__main__":
    main()
