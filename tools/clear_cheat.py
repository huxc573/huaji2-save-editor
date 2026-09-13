# -*- coding: utf-8 -*-
"""给存档“清作弊标记 + 同步物品计数校验”（命令行版，等价于界面上的两个按钮）。

为什么要它：游戏把 `@cheated` 记下来后，20 分钟就开始“惩罚”（画面转圈/缩放），
而那段代码在战斗里会碰到已经 dispose 的 `$game_player.sprite` →
`Script '0000' line 29491: RGSSError: disposed sprite` 直接崩。
清掉标记 + 把物品计数对齐，游戏就不会再判定作弊。

用法：
    python tools/clear_cheat.py              # 直接修本机存档（会先自动备份）
    python tools/clear_cheat.py --all        # 主存档 + AutoSave/*.rvdata2 一起修
    python tools/clear_cheat.py <存档路径>
    python tools/clear_cheat.py --dry-run    # 只看要改什么，不写盘
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.stdout.reconfigure(errors="replace")

import xj_backup      # noqa: E402
import xj_env         # noqa: E402
import xj_game        # noqa: E402
import xj_save        # noqa: E402


def all_saves():
    """主存档 + 游戏根下别的 save*.rvdata2 + AutoSave\\*.rvdata2。"""
    return xj_game.save_files(xj_env.save_path())


def fix_one(path, dry=False, quiet=False):
    """返回 (是否有问题, 处理了几项)。"""
    bad, done, over = xj_game.fix_save_file(path, dry_run=dry,
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


def main():
    argv = [a for a in sys.argv[1:] if not a.startswith("-")]
    dry = "--dry-run" in sys.argv
    every = "--all" in sys.argv
    paths = all_saves() if every else \
        [argv[0] if argv else xj_env.save_path()]
    print("要处理的存档：%d 个%s" % (len(paths), "（只看不改）" if dry else ""))
    n_bad = 0
    for p in paths:
        if not os.path.exists(p):
            print("  找不到：%s" % p)
            continue
        try:
            bad, _n = fix_one(p, dry=dry)
            n_bad += 1 if bad else 0
        except Exception as e:
            print("  %-24s 读不了：%s" % (os.path.basename(p), e))
    print("\n有问题的存档：%d 个" % n_bad)
    if n_bad and not dry:
        print("\n记得：游戏里**重新读一次档**（惩罚计时器在内存里，不跟存档走）；"
              "\n      如果游戏里已经弹过「存档异常」，先把游戏整个关掉再重开。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
