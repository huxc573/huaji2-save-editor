# -*- coding: utf-8 -*-
"""进阶按钮端到端探针（**只碰副本存档**，窗口 withdraw、不抢前台不动鼠标）。

覆盖 2026-10-08 川报「用工具新增的召唤兽，进游戏用圣兽之心后资质/成长都没突破，
原本里面进阶过的就突破了」——结论是游戏侧进阶**只抬上限、不动数字**：

    promote=(v) -> @promote = v
    get_max_*   -> $baby[:_max][promote ? :"类型_p" : 类型]
    get_atk     -> [@atk, get_max_atk].min
    面板（blob:78735）画 "#{value} / #{max_value}"，value 已 min

本探针从界面点按钮走完整链路：进阶 / 进阶并拉满 / 改字段夹值提示 / 跳过不可进阶。

    XJ_PY=<py312> python tests/probe_promote.py

⚠ 老坑：`Doc.save()` 写盘后整棵树重解析 → 之前抓的节点全失效。本探针 save 之后
  一律重新 `app.sv.actors()` / `app.g.babies()` 取节点。
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

import paths                                                       # noqa: E402

REAL = os.path.join(paths.find_game_dir(), "save.rvdata2")
COPY = os.path.join(ROOT, "_tmp", "probe_promote.rvdata2")

OK = [0, 0]
MSGS = []


def check(name, cond, extra=""):
    OK[0 if cond else 1] += 1
    print("  %s %-52s %s" % ("[OK]" if cond else "[NG]", name, extra))


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


def find_btn(w, want):
    for ch in w.winfo_children():
        try:
            if ch.winfo_class() == "TButton" and ch.cget("text") == want:
                return ch
        except Exception:
            pass
        hit = find_btn(ch, want)
        if hit is not None:
            return hit
    return None


Z = ("atk", "def", "hpq", "mpq", "agi", "eva", "grow")


def vals(app, b):
    return [app.g.baby_value(b, k) for k in Z]


def main():
    import tkinter as tk

    sha_before = sha1(REAL)
    if not os.path.exists(REAL):
        print("找不到存档 %s，跳过" % REAL)
        return 0
    os.makedirs(os.path.dirname(COPY), exist_ok=True)
    shutil.copy2(REAL, COPY)                     # ★ 只动副本
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
    assert os.path.abspath(app.doc.path) == os.path.abspath(COPY), \
        "doc.path 不是副本！%r" % (app.doc.path,)

    for i in range(app.nb.index("end")):
        if app.nb.tab(i, "text") == "召唤兽":
            app.nb.select(i)
    root.update()
    kill_timers(root)

    bd = app.babies_ed()
    print("\n-- 按钮在不在 --")
    b_p = find_btn(app.tab_baby, "进阶")
    b_f = find_btn(app.tab_baby, "进阶并拉满")
    check("「进阶」按钮建出来了", b_p is not None)
    check("「进阶并拉满」按钮建出来了", b_f is not None)
    check("两个按钮都挂上了悬停提示",
          b_p is not None and b_f is not None
          and "<Enter>" in b_p.bind() and "<Enter>" in b_f.bind())
    if b_p is None or b_f is None:
        root.destroy()
        return 1

    # ---- 样本：**现造一只「可进阶且未进阶」的神兽**
    # ⚠ 别指望真档里剩一只没进阶的 —— 川那把 10 只全是已进阶（2026-10-08 实测），
    #   拿它当样本的话「上限换到 *_p / 突破未进阶上限」两条断言根本没法成立。
    baby = None
    for c in bd.candidates():
        if c["type"] == "神兽" and bd.can_promote_id(c["id"]):
            try:
                baby = bd.add(app._baby_actor(), c["id"])
                break
            except Exception:
                baby = None
    check("造出了「可进阶且未进阶」的样本",
          baby is not None and not bd.promote_of(baby),
          bd.display_name(baby) if baby is not None else "没造出来")
    if baby is None:
        root.destroy()
        return 1
    app.refresh_panels()
    root.update()
    k = [k2 for k2, b2 in app.baby_rows if b2 is baby][0]
    app.tv_babies.selection_set("bb%d" % k)
    app.on_baby_select()
    root.update()
    name = bd.display_name(baby)
    before = vals(app, baby)
    cap_b = bd.max_attr(baby)
    print("\n-- 样本：%s（未进阶=%s）--" % (name, not bd.promote_of(baby)))
    print("   进阶前  数值=%r" % (before,))
    print("   进阶前  上限=%r" % (cap_b,))

    print("\n-- 点「进阶」：只抬上限，不动数字 --")
    b_p.invoke()
    root.update()
    check("promote 置上了", bd.promote_of(baby))
    check("六项资质 + 成长**一个都没变**", vals(app, baby) == before,
          "%r" % (vals(app, baby),))
    cap_a = bd.max_attr(baby)
    check("上限换到 *_p", cap_a is not cap_b and cap_a["grow"] > cap_b["grow"],
          "grow 上限 %s -> %s" % (cap_b["grow"], cap_a["grow"]))
    check("状态栏报了进阶", "进阶" in app.var_status.get(), app.var_status.get())
    check("没弹错误框", not [m for m in MSGS if m[0] == "error"],
          "%r" % ([m for m in MSGS if m[0] == "error"][:1],))

    print("\n-- 点「进阶并拉满」：写到进阶后的上限 --")
    b_f.invoke()
    root.update()
    cap_a2 = bd.max_attr(baby)
    got = vals(app, baby)
    want = [cap_a2["atk"], cap_a2["def"], cap_a2["hp"], cap_a2["mp"],
            cap_a2["agi"], cap_a2["eva"], cap_a2["grow"]]
    check("7 项全部 == 进阶后上限", [float(x) for x in got] == [float(x) for x in want],
          "%r" % (got,))
    check("确实突破了未进阶上限", got[0] > cap_b["atk"] and got[6] > cap_b["grow"],
          "atk %s>%s、grow %s>%s" % (got[0], cap_b["atk"], got[6], cap_b["grow"]))
    check("状态栏报了拉满", "拉满" in app.var_status.get(), app.var_status.get())
    print("   进阶后  数值=%r" % (got,))

    print("\n-- 幂等：再点一次「进阶并拉满」 --")
    b_f.invoke()
    root.update()
    check("数值不变", vals(app, baby) == got, app.var_status.get())
    check("状态栏说明本来就进阶过",
          "本来就进阶过" in app.var_status.get(), app.var_status.get())

    print("\n-- 「改字段」写超上限：照写 + 提示按上限显示 --")
    # 2026-10-08 反过来：**不夹**。上限管"游戏里能涨到多少"，存档里超限值合法
    # （游戏面板画 min(值, 上限) 并标红）。夹住会把老档的超限值拉低。
    app.tv_baby.selection_set("b_atk")
    app.baby_pick()
    app.var_baby_val.set("9999")
    app.apply_baby()
    root.update()
    check("落盘值就是填的 9999（不夹）",
          app.g.baby_value(baby, "atk") == 9999,
          "%s" % (app.g.baby_value(baby, "atk"),))
    check("baby_over_cap 标出 atk 超限",
          app.g.baby_over_cap(baby).get("atk") == (9999, cap_a2["atk"]),
          "%r" % (app.g.baby_over_cap(baby),))
    check("状态栏提示超限 + 指向「进阶」",
          "超过当前上限" in app.var_status.get()
          and "进阶" in app.var_status.get(), app.var_status.get())

    print("\n-- 图鉴里没有进阶立绘的：跳过不写 --")
    nc = None
    for c in bd.candidates():
        if not bd.can_promote_id(c["id"]):
            try:
                nc = bd.add(app._baby_actor(), c["id"])
                break
            except Exception:
                nc = None
    check("造出了不可进阶的样本", nc is not None,
          bd.display_name(nc) if nc is not None else "没造出来")
    if nc is not None:
        app.refresh_panels()
        root.update()
        _k = [k2 for k2, b2 in app.baby_rows if b2 is nc]
        if _k:
            app.tv_babies.selection_set("bb%d" % _k[0])
            app.on_baby_select()
            root.update()
            b_p.invoke()
            root.update()
            check("没写 @promote", not bd.promote_of(nc))
            check("状态栏报了跳过", "跳过" in app.var_status.get(),
                  app.var_status.get())
        else:
            check("新加的不可进阶宠物出现在列表里", False, "列表里找不到")

    print("\n-- 落盘 + 重开 --")
    app.save_save()
    root.update()
    kill_timers(root)
    import save as S
    import game as G
    import babies as B
    sv2 = S.SaveDoc(COPY)
    g2 = G.GameEditor(sv2)
    bd2 = B.Babies(g2)
    hit = [(i, b) for i, b in g2.babies(sv2.actors()[0][1])
           if bd2.display_name(b) == name and bd2.promote_of(b)]
    check("重开后 promote 还在", bool(hit), "%d 只同名且已进阶" % len(hit))
    check("重开后超限值（atk 9999）还在",
          bool(hit) and max(g2.baby_value(b, "atk") for _i, b in hit) == 9999,
          "%r" % ([g2.baby_value(b, "atk") for _i, b in hit],))

    root.destroy()
    print("\n真档 sha1[:12] = %s（与开始时%s）"
          % (sha1(REAL), "一致" if sha1(REAL) == sha_before else "**不一致**"))
    check("真档没被动过", sha1(REAL) == sha_before)
    print("\n==== 通过 %d, 失败 %d ====" % (OK[0], OK[1]))
    return 1 if OK[1] else 0


if __name__ == "__main__":
    sys.exit(main())
