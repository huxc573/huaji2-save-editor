# -*- coding: utf-8 -*-
"""一次性探针：**真存档里**物品的 `@attr` 到底长什么样（只读）。

要回答的问题：游戏自己写进存档的运行时内容，`@attr` 的外层键是字符串还是
符号、内层 `type` 用的是**中文还是英文**符号 —— 工具生成时该照抄哪个。

* 只读真档（不保存、不改），managed 3.13 也能跑（不需要 tkinter）。
"""
import io
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import paths                                   # noqa: E402
import save as save_mod                        # noqa: E402
from save import _deref, ivar                  # noqa: E402
import marshal_ruby as M                       # noqa: E402

#: 三张物品表都在 `party` 分区里（`Items` / `Weapons` / `Armors` 只是逻辑名）
CONTAINERS = (("party", "@items"), ("party", "@weapons"), ("party", "@armors"))


def _fmt_key(k):
    k = _deref(k)
    if isinstance(k, M.StrNode):
        return "str:%s" % k.data.decode("utf-8", "replace")
    if isinstance(k, M.SymbolNode):
        return "sym:%s" % k.name
    return repr(k)


def _fmt_val(v):
    v = _deref(v)
    if v is None:
        return "nil"
    if isinstance(v, M.HashNode):
        return "{%s}" % ", ".join("%s=>%s" % (_fmt_key(k), _fmt_val(x))
                                  for k, x in v.pairs)
    if isinstance(v, M.ArrayNode):
        return "[%s]" % ", ".join(_fmt_val(x) for x in v.items)
    if isinstance(v, M.StrNode):
        return repr(v.data.decode("utf-8", "replace"))
    return repr(M.value_of(v))


def main():
    game = paths.find_game_dir()
    print("游戏目录 =", game)
    path = paths.save_path(game)
    print("真档     =", path)
    doc = save_mod.SaveDoc(path)

    keys = Counter()
    types = Counter()
    total = 0
    shown = 0
    for sec, iv in CONTAINERS:
        try:
            node = _deref(ivar(doc.section(sec), iv))
        except KeyError:
            print("  （没有分区 %s）" % sec)
            continue
        if not isinstance(node, M.HashNode):
            continue
        for _k, v in node.pairs:
            arr = _deref(v)
            if not isinstance(arr, M.ArrayNode) or not arr.items:
                continue
            it = _deref(arr.items[0])
            if it is None:
                continue
            total += 1
            a = _deref(ivar(it, "@attr"))
            if a is None:
                continue
            if isinstance(a, M.HashNode) and a.pairs:
                keys[_fmt_key(a.pairs[0][0])] += 1
                inner = _deref(a.pairs[0][1])
                if isinstance(inner, M.HashNode) and inner.pairs:
                    for kk, vv in inner.pairs:
                        if _fmt_key(kk) == "sym:type":
                            types[_fmt_val(vv)] += 1
                            break
            if shown < 8:
                print("  槽 %s 物品 #%s → @attr = %s"
                      % (_k, M.value_of(ivar(it, "@id")), _fmt_val(a)))
                shown += 1

    print("\n物品总数 = %d" % total)
    print("@attr 外层键分布 =", dict(keys))
    print("内层 type 分布   =", dict(types))
    print("\n[判据] 若上面全是 `sym:中文`，说明游戏写的是中文符号；"
          "工具写英文名游戏就认不出。")
    print("[探针跑完] 只读，没保存、没改真档")
    return 0


if __name__ == "__main__":
    sys.exit(main())
