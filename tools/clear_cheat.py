# -*- coding: utf-8 -*-
"""给存档“清作弊标记 + 同步物品计数校验”（命令行版，等价于界面上的两个按钮）。

为什么要它：游戏把 `@cheated` 记下来后，20 分钟就开始“惩罚”（画面转圈/缩放），
而那段代码在战斗里会碰到已经 dispose 的 `$game_player.sprite` →
`Script '0000' line 29491: RGSSError: disposed sprite` 直接崩。
清掉标记 + 把物品计数对齐，游戏就不会再判定作弊。

用法：
    python tools/clear_cheat.py              # 直接修本机存档（会先自动备份）
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


def main():
    argv = [a for a in sys.argv[1:] if not a.startswith("-")]
    dry = "--dry-run" in sys.argv
    path = argv[0] if argv else xj_env.save_path()
    if not os.path.exists(path):
        print("找不到存档：%s" % path)
        return 1
    print("存档：%s%s" % (path, "（只看不改）" if dry else ""))

    sv = xj_save.SaveDoc(path)
    g = xj_game.GameEditor(sv)

    def report():
        rows = g.anti_cheat_report()
        over = [r for r in rows if r[3]]
        print("  体检：%d 项，其中 %d 项有问题" % (len(rows), len(over)))
        for r in over:
            print("    · %s：当前 %s（上限 %s）" % (r[0], r[1], r[2]))

    print("\n修改前：")
    report()
    if dry:
        return 0

    bak = xj_backup.backup(path, xj_backup.KIND_MANUAL,
                           note="clear_cheat.py 动手前")
    print("\n已备份：%s" % os.path.basename(bak))

    done = []
    for fn, what in ((g.fix_anti_cheat, "数值按规则修复"),
                     (g.clear_cheat_flag, "清除作弊标记"),
                     (g.resync_security, "同步物品计数校验")):
        try:
            r = fn()
            if r:
                done.append(what)
                print("  ✓ %s：%s" % (what, r if not isinstance(r, list)
                                     else "、".join(map(str, r))))
            else:
                print("  - %s：没有要处理的" % what)
        except Exception as e:
            print("  ✗ %s 出错：%s" % (what, e))
    if not done:
        print("\n没有需要改的，未写盘。")
        return 0

    sv.doc.save()
    print("\n已写回：%s" % path)

    sv2 = xj_save.SaveDoc(path)
    g2 = xj_game.GameEditor(sv2)
    rows = g2.anti_cheat_report()
    over = [r for r in rows if r[3]]
    print("\n修改后：体检 %d 项，有问题 %d 项" % (len(rows), len(over)))
    for r in over:
        print("    · 仍未处理：%s：当前 %s（上限 %s）" % (r[0], r[1], r[2]))
    print("\n记得：游戏里**重新读一次档**（惩罚计时器在内存里，不跟存档走）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
