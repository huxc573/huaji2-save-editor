# -*- coding: utf-8 -*-
"""一次性探针：把**每个**物品生成器都跑一遍，看写出去的 `@attr` 长什么样。

钉住 2026-10-04 那次对齐（`src/itemattr.py` 照 V2.201 脚本重写）：

* `:type` 必须是**游戏的中文符号**（`:孵化蛋` / `:导航旗` / `:宝石`…），
  写英文名（`:baby_egg`）游戏浮窗与使用逻辑都认不出；
* 孵化蛋的兽池按 `$baby` 真值算（`allow_lv` 三档 + `type2` 神兽池），
  不再用尝鲜版硬编码号段；
* 每件物品都真的写进存档副本、再读回来（端到端，不是只调函数）。

只动存档副本，真档一个字节都不动。managed 3.13 也能跑。
"""
import io
import os
import random
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import paths                                   # noqa: E402
import game                                    # noqa: E402
import save as save_mod                        # noqa: E402
from save import _deref, hash_get              # noqa: E402
import marshal_ruby as M                       # noqa: E402
import itemattr                                # noqa: E402

WORK = os.path.join(HERE, "_payload")

#: (物品 id, 只检查这几项都成立)
ITEMS = (110, 111, 112, 113, 221, 222, 223, 244,  # 蛋
         235, 94, 275,                            # 礼盒 / 导航旗
         66, 67, 152, 161,                        # 四种要诀
         135, 104, 90,                            # 元宵丹 / 元宵 / 人参果
         91, 92, 93, 68, 69, 70, 71, 73)          # 真知棒 / 阵法 / 装备产出


def _item_of(g, kind, slot):
    """按格子号取物品节点（照 test_game_layer 里的同名辅助）。"""
    for k, v in g.container(kind).pairs:
        if M.value_of(_deref(k)) == slot:
            arr = _deref(v)
            return _deref(arr.items[0])
    return None


def main():
    real = paths.save_path()
    shutil.rmtree(WORK, ignore_errors=True)
    os.makedirs(WORK, exist_ok=True)
    copy = os.path.join(WORK, "payload_copy.rvdata2")
    shutil.copyfile(real, copy)
    sv = save_mod.SaveDoc(copy)
    g = game.GameEditor(sv)
    print("存档副本 = %s\n" % copy)

    bad = 0
    used = []
    for iid in ITEMS:
        slots = [s for s in g.empty_slots("Items") if s not in used]
        slot = slots[0]
        used.append(slot)
        nm = g.item_needs_payload("Items", iid)[1]
        try:
            g.add_item("Items", slot, iid, 1, clone_like=False)
        except Exception as e:                       # noqa: BLE001
            print("  [NG] #%-4d %-12s 加不进去：%s" % (iid, nm, e))
            bad += 1
            continue
        it = _item_of(g, "Items", slot)
        t, d = g.item_payload(it)
        want = itemattr.build(nm, iid, rnd=random.Random(7))[0]
        ok = (t == want)
        inner_id = None
        if isinstance(d, M.HashNode):
            inner_id = M.value_of(_deref(hash_get(d, "id")))
        print("  %s #%-4d %-12s → :%-8s %s" %
              ("[OK]" if ok else "[NG]", iid, nm, t, g.payload_summary(it)))
        if not ok:
            bad += 1
        # 蛋类必须能孵出合法召唤兽 id
        if iid in (110, 111, 112, 113, 221, 222, 223, 244):
            pool = itemattr.egg_pool(iid)
            if not pool:
                print("       [NG] 兽池是空的")
                bad += 1
            elif inner_id not in pool:
                print("       [NG] 孵出 id=%r 不在兽池（%d 只）里"
                      % (inner_id, len(pool)))
                bad += 1
            else:
                print("       [OK] id=%s 落在兽池（%d 只）里" % (inner_id, len(pool)))

    # 三档蛋池互不重叠、且都在脚本的 list 里
    print("\n== 三档蛋池")
    seen = set()
    for k in range(3):
        pool = itemattr.egg_pool(110 + k)
        lo, hi = itemattr.EGG_TIERS[k]
        lvs = sorted({itemattr._BA.SPECIES[i]["allow_lv"] for i in pool})
        dup = seen & set(pool)
        print("  第 %d 档 (allow_lv %d..%d)：%3d 只，allow_lv=%s，与前档重复 %d"
              % (k, lo, hi, len(pool), lvs, len(dup)))
        if dup:
            bad += 1
        seen |= set(pool)
    print("  三档合计 %d 只（互不重叠）" % len(seen))

    print("\n== 神兽池")
    for iid, tag in ((113, "神兽孵化蛋(并集)"), (221, "普通神兽蛋"),
                     (222, "生肖神兽蛋"), (223, "珍藏神兽蛋"),
                     (244, "传说神兽蛋")):
        pool = itemattr.egg_pool(iid)
        print("  %-16s %2d 只：%s" % (tag, len(pool), pool))
        if not pool:
            bad += 1

    print("\n[汇总] 异常 %d 项（应 0）" % bad)
    print("[探针跑完] 只动了副本 %s" % copy)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
