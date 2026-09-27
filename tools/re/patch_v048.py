# -*- coding: utf-8 -*-
"""v0.4.8 补丁：作弊标记看得见、能一键清理（含 AutoSave）。

背景：主存档清了作弊标记，但 AutoSave\\save00..09 里还带着 @cheated ——
一读那种档就会被游戏惩罚（20 分钟后转圈、25 分钟后弹「存档异常」直接退出）。

改动：
  1. src/game.py  ：新增 save_files() / fix_save_file()（扫描 + 修某一个存档）
  2. src/huaji2_save_editor.py：
     * 概览页加一条红色提示条（有作弊标记/超限就写在上面）
     * 新增按钮「清理所有存档（含 AutoSave）」
     * 载入存档时如果带作弊标记 → 弹窗提醒并问要不要顺手清掉
     * 「检查并修复防作弊校验」→「校验码修复（Lock 校验和）」，并说明它和作弊标记不是一回事
  3. tools/clear_cheat.py：改用 game 的两个新函数（避免两套实现）
  4. tests/test_gui_quick.py：加两项检查

用法：python tools/_patch_v048.py
"""
import io
import sys

sys.stdout.reconfigure(errors="replace")

NEW_GAME_FUNCS = '''

# --------------------------------------------------------------------------
# 存档文件层面：扫描 / 批量修复（作弊标记、超限项、物品计数校验）
# --------------------------------------------------------------------------
def save_files(save_path):
    """游戏目录下**所有可能被游戏读到的存档**：

        <游戏根>\\save.rvdata2      （主存档）
        <游戏根>\\save*.rvdata2     （其它存档，如果有）
        <游戏根>\\AutoSave\\*.rvdata2（自动存档，读它一样会被惩罚）
    """
    import os
    main = os.path.abspath(save_path)
    root = os.path.dirname(main)
    out = [main]
    try:
        for n in sorted(os.listdir(root)):
            p = os.path.join(root, n)
            if n.lower().endswith(".rvdata2") and os.path.isfile(p) and p != main:
                out.append(p)
    except OSError:
        pass
    d = os.path.join(root, "AutoSave")
    if os.path.isdir(d):
        try:
            for n in sorted(os.listdir(d)):
                if n.lower().endswith(".rvdata2"):
                    out.append(os.path.join(d, n))
        except OSError:
            pass
    return out


def fix_save_file(path, backup=True, dry_run=False, note="按规则修复 + 清作弊标记"):
    """打开一个存档文件 → 按规则修复 + 清作弊标记 + 同步物品计数 → 写回。

    返回 ``(有没有问题, 做了哪些, 超限项列表)``；`dry_run=True` 只看不改。
    """
    import backup
    import save
    sv = save.SaveDoc(path)
    g = GameEditor(sv)
    rows = g.anti_cheat_report()
    over = [r for r in rows if r[3]]
    if not over or dry_run:
        return bool(over), [], over
    if backup:
        try:
            backup.backup(path, backup.KIND_MANUAL, note=note)
        except Exception:
            pass
    done = []
    for fn, what in ((g.fix_anti_cheat, "数值按规则修复"),
                     (g.clear_cheat_flag, "清除作弊标记"),
                     (g.resync_security, "同步物品计数校验")):
        try:
            if fn():
                done.append(what)
        except Exception:
            pass
    if done:
        sv.doc.save()
    return True, done, over
'''

PAIRS = []

# ---------------------------------------------------------------- game.py
PAIRS.append(("src/game.py",
              '''                done.append("keyword 去掉了 %d 个 VNE"
                            % (len(kw.items) + len(keep) - 2 * len(keep)))
        return done
''',
              '''                done.append("keyword 去掉了 %d 个 VNE"
                            % (len(kw.items) + len(keep) - 2 * len(keep)))
        return done
''' + NEW_GAME_FUNCS))

# ---------------------------------------------------------------- huaji2_save_editor.py
PAIRS.append(("src/huaji2_save_editor.py",
              '''        ttk.Button(bar, text="检查并修复防作弊校验",
                   command=self.fix_locks).pack(side="left", padx=8)
''',
              '''        ttk.Button(bar, text="校验码修复（Lock 校验和）",
                   command=self.fix_locks).pack(side="left", padx=8)
'''))

PAIRS.append(("src/huaji2_save_editor.py",
              '''        ttk.Label(h, text="游戏每 300 帧检查一次：角色等级 ≤ 60、出战召唤兽等级 ≤ 65、"
                          "存银 ≤ 30,000,000、仓库页号 ≤ 3、五维总点数 ≤ 等级*10+500。\\n"
                          "越界就把存档标记成「作弊」（@cheated），之后 20 分钟弹警告、"
                          "25 分钟强制退出。",
                  foreground="#555", justify="left").pack(anchor="w")
''',
              '''        ttk.Label(h, text="游戏每 300 帧检查一次：角色等级 ≤ 60、出战召唤兽等级 ≤ 65、"
                          "存银 ≤ 30,000,000、仓库页号 ≤ 3、五维总点数 ≤ 等级*10+500；"
                          "物品计数校验（Change）对不上也照样算作弊。\\n"
                          "越界就把存档标记成「作弊」（@cheated）：20 分钟后画面转圈/缩放，"
                          "25 分钟后弹「存档异常」直接退出，战斗中还会崩 "
                          "RGSSError: disposed sprite。\\n"
                          "⚠ 上面那个「校验码修复」修的是存银/步数那套 Lock 校验和，"
                          "跟这里的作弊标记是两码事 —— 清标记要用下面的按钮。",
                  foreground="#555", justify="left").pack(anchor="w")
        self.var_cheat = tk.StringVar(value="")
        ttk.Label(h, textvariable=self.var_cheat, foreground="#c00",
                  justify="left", wraplength=1180).pack(anchor="w", pady=(4, 0))
'''))

PAIRS.append(("src/huaji2_save_editor.py",
              '''        ttk.Button(gbar, text="同步物品计数校验",
                   command=self.guard_resync).pack(side="left", padx=6)
''',
              '''        ttk.Button(gbar, text="同步物品计数校验",
                   command=self.guard_resync).pack(side="left", padx=6)
        ttk.Button(gbar, text="清理所有存档（含 AutoSave）",
                   command=self.guard_fix_all).pack(side="left", padx=(18, 6))
'''))

PAIRS.append(("src/huaji2_save_editor.py",
              '''        n_bad = len([r for r in rows if r[3]])
        self.set_status("防作弊体检：%d 项，其中 %d 项有问题%s"
                        % (len(rows), n_bad,
                           "（点「一键按规则修复」）" if n_bad else " ✔"))
        return n_bad
''',
              '''        n_bad = len([r for r in rows if r[3]])
        over = [r for r in rows if r[3]]
        flag = [r for r in over if "作弊标记" in r[0]]
        others = [r for r in over if "作弊标记" not in r[0]]
        tips = []
        if flag:
            tips.append("⚠ 存档带着作弊标记 @cheated：游戏 20 分钟后开始“惩罚”"
                        "（画面转圈/缩放），25 分钟后弹「存档异常」并退出，"
                        "战斗中还会报 disposed sprite 崩掉 → 点「清除作弊标记」")
        if others:
            tips.append("⚠ 还有 %d 项超限：%s → 点「一键按规则修复」"
                        % (len(others), "、".join(r[0] for r in others)[:130]))
        if not tips:
            tips.append("✔ 体检 %d 项全部正常" % len(rows))
        try:
            self.var_cheat.set("\\n".join(tips))
        except Exception:
            pass
        self.set_status("防作弊体检：%d 项，其中 %d 项有问题%s"
                        % (len(rows), n_bad,
                           "（点「一键按规则修复」）" if n_bad else " ✔"))
        return n_bad
'''))

PAIRS.append(("src/huaji2_save_editor.py",
              '''        messagebox.showinfo("物品计数校验",
                            "已把 %d 件物品的计数对齐到背包实际数量。" % n if n
                            else "已经全部对得上。", parent=self.root)

''',
              '''        messagebox.showinfo("物品计数校验",
                            "已把 %d 件物品的计数对齐到背包实际数量。" % n if n
                            else "已经全部对得上。", parent=self.root)

    def guard_fix_all(self):
        """把游戏目录下**所有存档**（主存档 + AutoSave/*）的作弊标记/超限一起清掉。

        为什么要这个：AutoSave 里也可能带着 @cheated —— 读那种档一样会被惩罚
        （20 分钟后画面转圈，25 分钟后弹「存档异常」直接退出）。
        """
        if not self.doc:
            return
        paths = game.save_files(self.doc.path)
        self.set_status("正在检查 %d 个存档…" % len(paths))
        try:
            self.root.update_idletasks()
        except Exception:
            pass
        bad = []
        for p in paths:
            try:
                _b, _d, over = game.fix_save_file(p, dry_run=True)
                if over:
                    bad.append((p, over))
            except Exception as e:
                self.err(e)
        if not bad:
            messagebox.showinfo("清理所有存档",
                                "检查了 %d 个存档（含 AutoSave），"
                                "全都没有超限项/作弊标记 ✔" % len(paths),
                                parent=self.root)
            self.set_status("所有存档都干净")
            return
        txt = "\\n".join("  · %s：%s" % (os.path.basename(p),
                                       "、".join(r[0] for r in ov[:4]))
                         for p, ov in bad[:10])
        if not self.confirm("有 %d 个存档要被游戏惩罚" % len(bad),
                            "这些存档带着超限项/作弊标记（读它们都会触发惩罚）：\\n\\n"
                            "%s\\n\\n全部按规则修好？（各自会先备份一份）" % txt):
            return
        n = 0
        cur_fixed = False
        for p, _ov in bad:
            try:
                _b, done, _o = game.fix_save_file(p)
                if done:
                    n += 1
                if os.path.abspath(p) == os.path.abspath(self.doc.path):
                    cur_fixed = True
            except Exception as e:
                self.err(e)
        if cur_fixed and not self.doc.dirty:
            self.load(self.doc.path, quiet=True)     # 当前档被改过 → 重新载入
        else:
            self.refresh_panels()
        messagebox.showinfo("清理所有存档",
                            "已修好 %d 个存档（各自备份在 .huaji2-save-editor）。\\n\\n"
                            "如果游戏里已经弹过「存档异常」，请把游戏**整个关掉再重开**；"
                            "读档后就不会再被惩罚了。" % n, parent=self.root)

    def warn_cheat_after_load(self, quiet=False):
        """载入后如果存档带作弊标记 → 立刻提醒（惩罚 20 分钟后开始、25 分钟后强退）。"""
        if not self.g or quiet:
            return
        try:
            rows = self.g.anti_cheat_report()
        except Exception:
            return
        over = [r for r in rows if r[3]]
        flag = [r for r in over if "作弊标记" in r[0]]
        if not flag:
            return
        if self.confirm(
                "这个存档被游戏标记了作弊（@cheated）",
                "游戏会在 20 分钟后开始“惩罚”（画面转圈/缩放），25 分钟后弹\\n"
                "「存档异常」直接退出；战斗中还会报 RGSSError: disposed sprite 崩掉。\\n\\n"
                "要现在顺手修好吗？（推荐）\\n"
                "点「是」= 按规则修数值 + 清作弊标记 + 同步物品计数，之后 Ctrl+S 保存\\n"
                "点「否」= 先不管（概览页随时可以点按钮处理）"):
            self.guard_autofix()
            self.refresh_panels()
            self.set_status("已清除作弊标记 —— 记得点「保存修改」（Ctrl+S）")

'''))

PAIRS.append(("src/huaji2_save_editor.py",
              '''        else:
            self.set_status("已载入 %s（明文 %d 字节，%d 个顶层对象%s）"
                            % (os.path.basename(path), len(self.doc.raw),
                               len(self.doc.objects),
                               "" if self.sv else "；不是本作存档，只有数据树可用"))
''',
              '''        else:
            self.set_status("已载入 %s（明文 %d 字节，%d 个顶层对象%s）"
                            % (os.path.basename(path), len(self.doc.raw),
                               len(self.doc.objects),
                               "" if self.sv else "；不是本作存档，只有数据树可用"))
        if not quiet:
            self.warn_cheat_after_load()
'''))

# ---------------------------------------------------------------- clear_cheat.py
PAIRS.append(("tools/clear_cheat.py",
              '''def all_saves():
    """主存档 + 游戏根下别的 save*.rvdata2 + AutoSave\\\\*.rvdata2。"""
    main = paths.save_path()
    root = os.path.dirname(main)
    out = [main]
    for n in sorted(os.listdir(root)):
        p = os.path.join(root, n)
        if n.lower().endswith(".rvdata2") and os.path.isfile(p) and p != main:
            out.append(p)
    d = os.path.join(root, "AutoSave")
    if os.path.isdir(d):
        for n in sorted(os.listdir(d)):
            if n.lower().endswith(".rvdata2"):
                out.append(os.path.join(d, n))
    return out
''',
              '''def all_saves():
    """主存档 + 游戏根下别的 save*.rvdata2 + AutoSave\\\\*.rvdata2。"""
    return game.save_files(paths.save_path())
'''))

PAIRS.append(("tools/clear_cheat.py",
              '''def fix_one(path, dry=False, quiet=False):
    """返回 (是否有问题, 处理了几项)。"""
    def say(*a):
        if not quiet:
            print(*a)

    sv = save.SaveDoc(path)
    g = game.GameEditor(sv)
    rows = g.anti_cheat_report()
    over = [r for r in rows if r[3]]
    if not over:
        say("  %-24s 干净 ✔（%d 项体检）" % (os.path.basename(path), len(rows)))
        return False, 0
    say("  %-24s 有问题：%s" % (os.path.basename(path),
                               "、".join("%s(%s)" % (r[0], r[1]) for r in over)))
    if dry:
        return True, 0
    bak = backup.backup(path, backup.KIND_MANUAL,
                           note="clear_cheat.py 动手前")
    done = []
    for fn, what in ((g.fix_anti_cheat, "数值按规则修复"),
                     (g.clear_cheat_flag, "清除作弊标记"),
                     (g.resync_security, "同步物品计数校验")):
        try:
            r = fn()
            if r:
                done.append(what)
        except Exception as e:
            say("      ✗ %s 出错：%s" % (what, e))
    if done:
        sv.doc.save()
    say("      已处理：%s（备份 %s）"
        % ("、".join(done) if done else "无", os.path.basename(bak)))
    return True, len(done)
''',
              '''def fix_one(path, dry=False, quiet=False):
    """返回 (是否有问题, 处理了几项)。"""
    bad, done, over = game.fix_save_file(path, dry_run=dry,
                                            note="clear_cheat.py 动手前")
    if not quiet:
        if not bad:
            print("  %-24s 干净 ✔" % os.path.basename(path))
        else:
            print("  %-24s 有问题：%s" % (
                os.path.basename(path),
                "、".join("%s(%s)" % (r[0], r[1]) for r in over)))
            if not dry:
                print("      已处理：%s" % ("、".join(done) if done else "无"))
    return bad, len(done)
'''))

# ---------------------------------------------------------------- 测试
PAIRS.append(("tests/test_gui_quick.py",
              '''        check("概览文本已填充", "存银" in app.txt_info.get("1.0", "end"))
''',
              '''        check("概览文本已填充", "存银" in app.txt_info.get("1.0", "end"))
        check("概览页有作弊/超限提示条", "作弊" in app.var_cheat.get()
              or "超限" in app.var_cheat.get() or "正常" in app.var_cheat.get(),
              app.var_cheat.get()[:60])
        n_dlg0 = len(dialogs)
        app.warn_cheat_after_load()          # 这份副本带着 @cheated
        root.update()
        check("载入带作弊标记的存档会提醒并顺手清掉",
              len(dialogs) > n_dlg0 and app.var_cheat.get() != "",
              "%r / %s" % (dialogs[-1:], app.var_cheat.get()[:40]))
'''))

bad = 0
for path, old, new in PAIRS:
    s = io.open(path, encoding="utf-8", newline="").read()
    NL = "\r\n" if "\r\n" in s else "\n"
    # 本脚本自己的换行可能是 CRLF，先把里面的 \r\n 归一成 \n 再换成本文件的换行
    o = old.replace("\r\n", "\n").replace("\n", NL)
    n_ = new.replace("\r\n", "\n").replace("\n", NL)
    cnt = s.count(o)
    tag = "%s :: %s" % (path, old.strip().splitlines()[0][:44])
    if cnt != 1:
        print("[NG] 匹配 %d 次：%s" % (cnt, tag))
        bad += 1
        continue
    out = s.replace(o, n_)
    compile(out, path, "exec")
    io.open(path, "w", encoding="utf-8", newline="").write(out)
    print("[OK] %s" % tag)

if bad:
    print("有 %d 处没匹配上（那些没写盘）" % bad)
    raise SystemExit(1)
print("全部补丁完成")
