# -*- coding: utf-8 -*-
"""一次性探针：「五行列 + 全员忠诚满」（**只碰副本存档**）。

覆盖 2026-09-27 的两处改动：
  · 召唤兽一览表在「成长」左边新增「五行」列（列序 / 单元格值 / 不错位）
  · 「忠诚满」→「全员忠诚满」：一次改到**所有角色**的**所有召唤兽**，
    且只动 @loyalty（五维/潜能/等级/技能不碰）；幂等；能存盘重开

顺带锁住查证结论：忠诚上限 = 100（游戏硬规定）、参战门槛 = 60（不是 100）。

用系统 Python 3.12（有 tkinter）。窗口全程 withdraw / 屏外 / 全透明 —— 不抢前台、不动鼠标。

    XJ_PY=<py312> python tests/probe_loyalty_all.py

⚠ 老坑：`Doc.save()` 写盘后会重新解析整棵树 → 之前抓的节点全部失效。
  本探针凡是在 save 之后的读写，都重新 `app.sv.actors()` / `app.g.babies()` 取一遍。
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
COPY = os.path.join(ROOT, "_tmp", "probe_loyalty_all.rvdata2")

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
    huaji2_save_editor.backup.auto_backup_once = lambda _p: None

    app = huaji2_save_editor.App(root, save_path=COPY)
    kill_timers(root)
    app.cancel_auto_load()
    app.load(COPY)
    kill_timers(root)
    root.update_idletasks()
    p = getattr(app.doc, "path", None) if app.doc else None
    assert p and os.path.abspath(p) == os.path.abspath(COPY), \
        "doc.path 不是副本！%r" % (p,)

    for i in range(app.nb.index("end")):
        if app.nb.tab(i, "text") == "召唤兽":
            app.nb.select(i)
    root.update_idletasks()
    kill_timers(root)

    import fieldnames
    import game

    def all_rows():
        """整档 (角色id, 角色节点, 宝宝下标, 宝宝节点) —— 每次现取。"""
        out = []
        for aid, a in app.sv.actors():
            for i, b in app.g.babies(a):
                out.append((aid, a, i, b))
        return out

    def low_rows():
        return [r for r in all_rows()
                if abs(float(app.g.baby_value(r[3], "loyalty")) - 100.0) > 1e-9]

    # ---------------- A. 一览表的「五行」列
    print("\n-- A. 召唤兽一览表（五行列）")
    cols = tuple(app.tv_babies["columns"])
    want = ("no", "name", "tpl", "lv", "five", "grow", "loyal", "life", "atk",
            "def", "hp", "mp", "agi", "eva", "sk", "act")
    check("列顺序 = 序/名字/模板/等级/五行/成长/忠诚…", cols == want,
          "、".join(cols))
    check("「五行」紧贴「成长」左边",
          cols.index("five") + 1 == cols.index("grow"),
          "five@%d grow@%d" % (cols.index("five"), cols.index("grow")))
    check("表头文字是「五行」",
          app.tv_babies.heading("five", "text") == "五行",
          app.tv_babies.heading("five", "text"))
    rows = app.tv_babies.get_children()
    vals = [app.tv_babies.item(r, "values") for r in rows]
    check("每行列数 = 16（元组加列时不会错位）",
          bool(vals) and all(len(v) == len(cols) for v in vals),
          "行数 %d，列数 %s" % (len(rows), sorted(set(len(v) for v in vals))))
    babies = app.baby_rows
    five_cells = [v[4] for v in vals]
    five_true = [app.g.baby_value(b, "five") for _i, b in babies]
    check("五行列的值 = 存档真值（逐行对齐）",
          five_cells == five_true and all(c in ("金", "木", "水", "火", "土")
                                          for c in five_cells),
          "%r" % (five_cells[:6],))
    check("等级列仍在（没被挤错）",
          all(str(v[3]) == str(app.g.baby_value(b, "level"))
              for v, (_i, b) in zip(vals, babies)),
          "%r" % ([v[3] for v in vals][:6],))

    # ---------------- B. 忠诚的规则（查证结论锁住）
    print("\n-- B. 忠诚的规则（来自游戏脚本）")
    check("上限常量 = 100（Config::Game::MAX_BABY_LOYALTY）",
          fieldnames.MAX_BABY_LOYALTY == 100, fieldnames.MAX_BABY_LOYALTY)
    check("参战门槛常量 = 60（Config::Baby::ALLOW_LOYALTY）",
          fieldnames.BABY_ALLOW_LOYALTY == 60, fieldnames.BABY_ALLOW_LOYALTY)
    check("字段标签里写的是 60（不是 100）",
          "<%d 不能参战" % fieldnames.BABY_ALLOW_LOYALTY
          in dict((k, lb) for k, lb, _p, _t in game.GameEditor.BABY_FIELDS)["loyalty"],
          dict((k, lb) for k, lb, _p, _t
               in game.GameEditor.BABY_FIELDS)["loyalty"])

    # ---------------- C. 全员忠诚满
    print("\n-- C. 全员忠诚满")
    tot = len(all_rows())
    n_actor = len(app.sv.actors())
    print("     全档 %d 只召唤兽 / %d 个角色" % (tot, n_actor))
    sample = [r for r in all_rows() if r[0] != all_rows()[0][0]][:2] or all_rows()
    for (_aid, _a, _i, _b) in sample[:1]:                    # 跨角色挑一只压低
        app.g.set_baby(_b, "loyalty", 30)
    for (_aid, _a, _i, _b) in all_rows()[:1]:
        app.g.set_baby(_b, "loyalty", 0)
    low0 = low_rows()
    check("造出「低于上限」的现场（含跨角色）", len(low0) >= 2,
          "%d 只低：%s" % (len(low0), [round(float(app.g.baby_value(r[3],
                                                                  "loyalty")), 2)
                                      for r in low0][:5]))
    exp_actors = len(set(r[0] for r in low0))
    # 改前的「五个维度 + 潜能 + 等级 + 技能」快照，用来证明只动忠诚
    _snap_before = {}
    for (aid, _a, _i, b) in all_rows():
        _snap_before[id(b)] = (
            [app.g.baby_value(b, k)
             for k in ("体质", "法力", "力量", "耐力", "敏捷", "潜能", "level",
                       "grow", "atk", "five")],
            tuple(app.babies_ed().skills(b)))

    MSGS[:] = []
    n, na = app.g.set_loyalty_all()
    check("set_loyalty_all 返回「改了几只」= 低的那几只", n == len(low0),
          "%d vs %d" % (n, len(low0)))
    check("set_loyalty_all 返回「涉及几个角色」", na == exp_actors,
          "%d vs %d" % (na, exp_actors))
    check("全档所有召唤兽都 = 100", not low_rows(),
          "还剩 %d 只低" % len(low_rows()))
    check("幂等：再点一次返回 (0, 0)", app.g.set_loyalty_all() == (0, 0),
          "%r" % (app.g.set_loyalty_all(),))
    _bad = []
    for (aid, _a, _i, b) in all_rows():
        now = ([app.g.baby_value(b, k)
                for k in ("体质", "法力", "力量", "耐力", "敏捷", "潜能", "level",
                          "grow", "atk", "five")],
               tuple(app.babies_ed().skills(b)))
        if now != _snap_before.get(id(b)):
            _bad.append(app.g.baby_name(b))
    check("只动了忠诚（五维/潜能/等级/成长/资质/五行/技能 全没变）", not _bad,
          "、".join(_bad) or "全部一致")

    # ---- 界面按钮
    btns = [w for w in walk(app.tab_baby) if w.winfo_class() == "TButton"]
    names = [w.cget("text") for w in btns]
    check("按钮叫「全员忠诚满」", "全员忠诚满" in names,
          "、".join(n2 for n2 in names if "忠诚" in n2) or "（没有带忠诚的按钮）")
    check("老的「忠诚满」按钮已换掉", "忠诚满" not in names)
    row = None
    for w in walk(app.tab_baby):
        if w.winfo_class() == "TFrame" and "应用" in \
                [c.cget("text") for c in w.winfo_children()
                 if c.winfo_class() == "TButton"]:
            row = w
    check("找到预设按钮所在那一行", row is not None)
    # ---- GUI 路径（先压低一只，再点）
    app.g.set_baby(all_rows()[0][3], "loyalty", 12)
    app.doc.dirty = False
    MSGS[:] = []
    app.baby_preset("loyalty_all")
    root.update_idletasks()
    kill_timers(root)
    check("GUI 点一下 → 没弹错误框", not [m for m in MSGS if m[0] == "error"],
          "、".join(m[1] for m in MSGS))
    check("GUI 点一下 → 标脏（保存不再说「没有改动」）", app.doc.dirty)
    check("GUI 点一下 → 全档都满了", not low_rows())
    import huaji2_save_editor as H
    _st = app.var_status.get() if hasattr(app, "var_status") else ""
    check("状态栏写了「全员忠诚满」", "全员忠诚" in _st, _st[:60] or "(未取到状态栏)")

    # ---- 存盘 + 重开（真写进去）
    MSGS[:] = []
    app.save_save()
    root.update_idletasks()
    kill_timers(root)
    check("保存没说「没有改动」",
          not any("没有改动" in m[2] for m in MSGS if m[0] == "info"),
          "、".join(m[1] for m in MSGS))
    import save as save_mod
    import game as game_mod
    sv2 = save_mod.SaveDoc(COPY)
    g2 = game_mod.GameEditor(sv2)
    left = []
    total2 = 0
    for _aid, a2 in sv2.actors():
        for _i, b2 in g2.babies(a2):
            total2 += 1
            if abs(float(g2.baby_value(b2, "loyalty")) - 100.0) > 1e-9:
                left.append(g2.baby_value(b2, "loyalty"))
    check("盘上读回来：%d 只全部 = 100" % total2, not left, "%r" % (left[:5],))

    # ---------------- D. 布局：按钮条会不会被裁
    print("\n-- D. 布局（屏外真实测量）")
    root.deiconify()
    try:
        root.attributes("-alpha", 0.0)
    except Exception:
        pass
    top = None
    for w in walk(app.tab_baby):
        if w.winfo_class() == "TFrame" and "新增召唤兽" in \
                [c.cget("text") for c in w.winfo_children()
                 if c.winfo_class() == "TButton"]:
            top = w
    btn = [c for c in row.winfo_children()
           if c.winfo_class() == "TButton" and c.cget("text") == "全员忠诚满"]
    for geo in ("1220x800", "1180x757", "1080x757"):
        root.geometry(geo + "+6000+6000")
        root.update()
        root.update_idletasks()
        if row is not None:
            print("     %-9s 预设行 %4d/%-4d  顶栏 %4d/%-4d   %s"
                  % (geo, row.winfo_width(), row.winfo_reqwidth(),
                     top.winfo_width() if top else -1,
                     top.winfo_reqwidth() if top else -1,
                     "OK" if row.winfo_width() >= row.winfo_reqwidth() - 2
                     else "← 预设行被裁"))
    # 这个改动加宽了多少？（临时把按钮文案改回旧版量一次，判断「1080 被裁」是不是本来就有）
    if btn:
        _now, _bnow = row.winfo_reqwidth(), btn[0].winfo_reqwidth()
        btn[0].configure(text="忠诚满")
        root.update_idletasks()
        print("     文案「全员忠诚满」行宽 %dpx / 按钮 %dpx；"
              "换回旧「忠诚满」行宽 %dpx（本次 +%dpx）"
              % (_now, _bnow, row.winfo_reqwidth(), _now - row.winfo_reqwidth()))
        btn[0].configure(text="全员忠诚满")

    try:
        root.destroy()
    except Exception:
        pass

    print("\n-- E. 真档")
    sha_after = sha1(REAL)
    check("真档没被动过", sha_before == sha_after,
          "%s -> %s" % (sha_before, sha_after))

    print("\n========== 探针：%d OK / %d NG ==========" % (OK[0], OK[1]))
    return 1 if OK[1] else 0


if __name__ == "__main__":
    sys.exit(main())
