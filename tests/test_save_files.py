# -*- coding: utf-8 -*-
"""批量存档层测试：`save_files()` / `fix_save_file()`（含 AutoSave）。

重点回归一个**真实踩过的坑**：
    把 `false` 写成整数 `0` —— Ruby 里 `0` 是**真值**，
    于是 `if $game_system.cheated` 照样成立，游戏 20 分钟后继续“惩罚”，
    25 分钟后弹「存档异常」退出。所以修复后必须是 Marshal 的 `F`。

全程在 tools/_smoke/savefiles 下的临时目录里做，真存档一个字节都不动。

用法：python tools/test_save_files.py
输出：tools/_save_files.txt
"""
import io
import os
import shutil
import sys

sys.stdout.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))

import xj_env    # noqa: E402
import xj_edit   # noqa: E402
import xj_game   # noqa: E402
import xj_marshal as M  # noqa: E402
import xj_save   # noqa: E402

WORK = os.path.join(ROOT, "tools", "_smoke", "savefiles")
LOG = os.path.join(ROOT, "tools", "_save_files.txt")
L = []
OK = [0, 0]


def check(name, cond, extra=""):
    L.append("%-48s %s %s" % (name, "[OK]" if cond else "[NG]", extra))
    OK[0 if cond else 1] += 1


def cheat_node(sv):
    return xj_save._deref(xj_save.ivar(sv.section("system"), "@cheated"))


def cheat_value(sv):
    return M.value_of(cheat_node(sv))


def raw_cheated_bytes(path):
    """明文里 `@cheated` 那个值占的字节（用来确认写的是 `F` 而不是 `i0`）。"""
    doc = xj_save.SaveDoc(path)
    n = cheat_node(doc)
    return doc.doc.engine.buf[n.start:n.end]


def make_tree():
    """造一个像游戏目录一样的临时目录：主存档 + AutoSave 两个。"""
    if os.path.isdir(WORK):
        shutil.rmtree(WORK, ignore_errors=True)
    os.makedirs(os.path.join(WORK, "AutoSave"))
    src = xj_env.save_path()
    main = os.path.join(WORK, "save.rvdata2")
    shutil.copyfile(src, main)
    for nm in ("save00.rvdata2", "save01.rvdata2"):
        shutil.copyfile(src, os.path.join(WORK, "AutoSave", nm))
    return main


main = make_tree()
auto_dir = os.path.join(WORK, "AutoSave")
p_main, p_a0, p_a1 = (main,
                      os.path.join(auto_dir, "save00.rvdata2"),
                      os.path.join(auto_dir, "save01.rvdata2"))

# ---------------------------------------------------------------- save_files
paths = xj_game.save_files(main)
names = sorted(os.path.basename(p) for p in paths)
check("save_files 找到主存档", os.path.abspath(main) in [os.path.abspath(p)
                                                         for p in paths])
check("save_files 带上 AutoSave", len(paths) == 3, "%d 个：%s" % (len(paths), names))
check("AutoSave 里的两个都在", all(os.path.abspath(p) in
                                   [os.path.abspath(x) for x in paths]
                                   for p in (p_a0, p_a1)))

# ------------------------------------------------- 把三份都改成“作弊”状态
for p in (p_main, p_a0, p_a1):
    d = xj_save.SaveDoc(p)
    d.doc.set_value(cheat_node(d), 134700)      # 游戏就是这么记的（帧数）
    d.save(backup=False)
d = xj_save.SaveDoc(p_main)
check("模拟出作弊标记", not xj_game.is_ruby_false(cheat_value(d)),
      "%r" % (cheat_value(d),))

# ------------------------------------------------------------- dry-run 不改盘
before = io.open(p_main, "rb").read()
bad, done, over = xj_game.fix_save_file(p_main, dry_run=True)
after = io.open(p_main, "rb").read()
check("dry-run 能报出问题", bad and over and done == [],
      "over=%s" % ([r[0] for r in over],))
check("dry-run 不写盘", before == after)

# ---------------------------------------------------------------- 真的修一遍
bad, done, over = xj_game.fix_save_file(p_main)
check("修完报告的条目里有作弊标记", bad and over)
check("确实动了手", len(done) >= 1, "%s" % (done,))
d = xj_save.SaveDoc(p_main)
check("修完 @cheated 是 Ruby false", cheat_value(d) is False,
      "%r" % (cheat_value(d),))
check("明文里写的是 F（不是 i0）", raw_cheated_bytes(p_main) == b"F",
      "%r" % (raw_cheated_bytes(p_main),))
check("体检报告也干净了",
      not [r for r in xj_game.GameEditor(d).anti_cheat_report() if r[3]])

# 修不改“本来就对”的存档：AutoSave 还没修，先确认它们仍然被判定有问题
bad0, _d0, over0 = xj_game.fix_save_file(p_a0, dry_run=True)
check("AutoSave 也带着标记（读它一样会被惩罚）", bad0 and over0,
      "%s" % ([r[0] for r in over0],))
n_before = xj_game.fix_save_file(p_a1, dry_run=True)[0]
for p in (p_a0, p_a1):
    xj_game.fix_save_file(p)
check("批量修完 AutoSave 也干净",
      xj_game.fix_save_file(p_a0, dry_run=True)[0] is False
      and xj_game.fix_save_file(p_a1, dry_run=True)[0] is False,
      "p_a1 修之前有标记 = %r" % n_before)

# ------------------------------------------------------ 编码回归（bypass 场景）
doc = xj_save.SaveDoc(p_main)
node = cheat_node(doc)
check("假值必须编码成 F", xj_edit.encode_scalar(node, False) == b"F",
      "%r" % (xj_edit.encode_scalar(node, False),))
check("真值必须编码成 T", xj_edit.encode_scalar(node, True) == b"T",
      "%r" % (xj_edit.encode_scalar(node, True),))
inode = M.IntNode(134700)
check("IntNode 存 False 也要写成 F",
      xj_edit.encode_scalar(inode, False) == b"F",
      "%r" % (xj_edit.encode_scalar(inode, False),))
check("IntNode 存 True 也要写成 T",
      xj_edit.encode_scalar(inode, True) == b"T",
      "%r" % (xj_edit.encode_scalar(inode, True),))
check("IntNode 存数字还是数字",
      xj_edit.encode_scalar(inode, 7) == M.encode_integer(7))
check("is_ruby_false 认 false / nil，不认 0",
      xj_game.is_ruby_false(False) and xj_game.is_ruby_false(None)
      and not xj_game.is_ruby_false(0))

# --------------------------------------------- 手工塞一个“i0”（老版本写出来的）
doc = xj_save.SaveDoc(p_main)
node = cheat_node(doc)
doc.doc.engine.replace_range(node.start, node.end, b"i\x00")   # 整数 0
doc.save(backup=False)
d = xj_save.SaveDoc(p_main)
check("识别出老的 i0 写法", d is not None and
      isinstance(cheat_node(d), M.IntNode) and cheat_value(d) == 0,
      "%r / %r" % (type(cheat_node(d)).__name__, cheat_value(d)))
check("体检把 i0 当问题（Ruby 里 0 是真值）",
      bool([r for r in xj_game.GameEditor(d).anti_cheat_report() if r[3]]),
      "%s" % [r for r in xj_game.GameEditor(d).anti_cheat_report()
               if "作弊标记" in r[0]])
bad, done, _o = xj_game.fix_save_file(p_main)
d2 = xj_save.SaveDoc(p_main)
check("再修一次就变回真 false",
      cheat_value(d2) is False and raw_cheated_bytes(p_main) == b"F",
      "%r / %r" % (cheat_value(d2), raw_cheated_bytes(p_main)))

# ---------------------------------------------------------------- 收尾
n = 0
for fn in sorted(os.listdir(os.path.join(WORK, ".huaji2-save-editor"))):
    if fn.endswith(".rvdata2"):
        n += 1
check("备份文件都落在了 .huaji2-save-editor", n >= 2, "%d 个备份" % n)
n_auto = 0
auto_bak = os.path.join(auto_dir, ".huaji2-save-editor")
if os.path.isdir(auto_bak):
    n_auto = len([f for f in os.listdir(auto_bak) if f.endswith(".rvdata2")])
check("AutoSave 的备份也在（各自目录下）", n_auto >= 2, "%d 个" % n_auto)

shutil.rmtree(WORK, ignore_errors=True)

L.append("")
L.append("==== 通过 %d, 失败 %d ====" % (OK[0], OK[1]))
open(LOG, "w", encoding="utf-8").write("\n".join(L) + "\n")
print("\n".join(L))
sys.exit(1 if OK[1] else 0)
