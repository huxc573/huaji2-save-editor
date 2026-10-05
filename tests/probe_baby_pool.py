# -*- coding: utf-8 -*-
"""探针：小精灵(181) 的资质池到底取到哪个 pool。

背景：gui_quick「新召唤兽资质 = 神兽资质3 定值」NG（atk 得 2100 而非 2400）。
查 data_key(181) 是否读到 Data\\Actors 的 `data = :神兽资质3`。
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "src"))

import paths                                   # noqa: E402
import datatables                              # noqa: E402
import tables.baby_aptitude as BA              # noqa: E402


def main():
    gd = paths.find_game_dir()
    print("游戏目录 =", gd)
    try:
        _r, items = datatables.load("Actors")
        d = dict(items)
    except Exception as e:
        print("读 Actors 失败：", e)
        return 1
    print("Actors 条目 =", len(d))
    for bid in (181, 182, 150, 25):
        n = d.get(bid)
        if n is None:
            print("  id=%s 不在表里" % bid)
            continue
        note = datatables.s(n, "@note") or ""
        import re
        m = re.search(r"data\s*=\s*:([^\s|\r\n]+)", note)
        key = m.group(1) if m else None
        print("  id=%-4s name=%-8s data_key=%r  note=%r" % (
            bid, datatables.s(n, "@name"), key, note[:160]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
