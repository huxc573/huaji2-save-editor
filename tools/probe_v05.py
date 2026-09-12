# -*- coding: utf-8 -*-
"""临时探针：验证机器码 + 背包体检/模板 这几个新接口。

用法：python tools/probe_v05.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.stdout.reconfigure(errors="replace")

import xj_env          # noqa: E402
import xj_game         # noqa: E402
import xj_model        # noqa: E402
import xj_save         # noqa: E402


def main():
    doc = xj_model.Doc(xj_env.save_path())
    sv = xj_save.SaveDoc(doc=doc)
    g = xj_game.GameEditor(sv)

    print("=== 机器码 ===")
    now, err, ids, ok = g.machine_status()
    print("本机 :", now, "（错误：%s）" % err if err else "")
    print("存档 :", ids)
    print("匹配 :", ok)

    print()
    print("=== 背包体检 ===")
    rows = g.pack_report()
    print("问题 %d 项" % len(rows))
    for r in rows[:20]:
        print("   ", r)
    print("（不实际修改，只看）")

    print()
    print("=== 模板表（前 5 个 / 搜 '草'）===")
    for t in g.templates("Items", limit=5):
        print("   ", t)
    for t in g.templates("Items", keyword="草", limit=5):
        print("  搜 草:", t)
    for t in g.templates("Weapons", limit=3):
        print("   武器:", t)
    print("模板总数 Items =", len(g.templates("Items", limit=9999)))
    print("背包 =", g.bag("Items"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
