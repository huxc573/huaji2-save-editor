# -*- coding: utf-8 -*-
"""游戏里"运行时才生成内容"的物品 —— 也就是存档物件里的 `@attr`（脚本里叫 `item.data`）。

例如孵化蛋：使用时会读 `item.data[:data][:id]` 来决定孵出哪只召唤兽，
而**这个 id 是游戏在发给你的时候现抽的**（脚本 `Game_Party#孵化蛋`）：

    def 孵化蛋(item)
      i = item.id - 110
      item.data = { type: :baby_egg, data: { id: [ rand(21..23, 25..63), ... ][i] } }
    end

我们按 Data 模板"凭空造"一个物品时，`@attr` 只能是空 Hash；游戏一用就
`undefined method '[]' for nil:NilClass`（`item.data[:data]` 是 nil）。
所以这个模块把脚本里那十几个生成规则**照抄**成 Python：加这类物品时顺手生成
一份合法内容，或者干脆从存档里已有的同种物品整个复制过来（更保险）。

生成规则来源：`Data\\Scripts.rvdata2` 里 `class Game_Party` 的
`孵化蛋 / 神兽蛋 / 鬼谷子 / 进阶石 / 制造指南书 / 百炼精铁 / 魔兽要诀 /
上古锻造图策 / 天眼珠 / 人参果 / 真知棒 / 石头 / 元宵 / 导航旗` 等方法。
"""
import random

# --------------------------------------------------------------------------
# 节点用的"符号"占位（xj_game 会把它转成 SymbolNode）
# --------------------------------------------------------------------------
class Sym(object):
    __slots__ = ("name",)

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return ":%s" % self.name


# 名字 → 生成器（**顺序有讲究**：长/特殊名字要排在前面）
#   生成器签名：(item_id, rnd, ctx) -> (type字符串, data字典)
def _rng(rnd, *ranges):
    """游戏里的 `rand(21..23, 25..63)`：从多个闭区间里等概率抽一个值。"""
    pools = [list(range(a, b + 1)) for a, b in ranges]
    pool = pools[rnd.randrange(len(pools))]
    return rnd.choice(pool)


def _babies(ctx, note, rnd):
    """按备注里的 `data = :神兽资质` 挑召唤兽（从 Data\\Actors 里读）。"""
    ids = ctx().get(note) if ctx else None
    if not ids:
        return None
    return rnd.choice(ids)


# ---------------------------------------------------------------- 孵化蛋
def _baby_egg(item_id, rnd, ctx):
    i = item_id - 110
    if 0 <= i <= 2:
        kid = [_rng(rnd, (21, 23), (25, 63)),
               _rng(rnd, (64, 95), (127, 134)),
               _rng(rnd, (96, 126))][i]
    else:                       # 神兽孵化蛋（113+）：从 神兽资质 / 神兽资质2 里抽
        kid = (_babies(ctx, "神兽资质", rnd) or _babies(ctx, "神兽资质2", rnd)
               or _rng(rnd, (21, 23), (25, 63)))
    return ("baby_egg", {"id": kid})


def _god_egg(item_id, rnd, ctx):
    """神兽孵化蛋（113/114）取 神兽资质 ∪ 神兽资质2；神兽蛋（221/222）分别取。"""
    note = None if 113 <= item_id <= 114 else (
        "神兽资质" if item_id <= 221 else "神兽资质2")
    ids = []
    if ctx:
        m = ctx()
        if note is None:
            ids = list(m.get("神兽资质", [])) + list(m.get("神兽资质2", []))
        else:
            ids = list(m.get(note, []))
    kid = rnd.choice(ids) if ids else _rng(rnd, (64, 95), (127, 134))
    return ("baby_egg", {"id": kid})


# ---------------------------------------------------------------- 阵型 / 进阶
def _formation(_item_id, rnd, _ctx):
    keys = [Sym("天覆阵"), Sym("地载阵"), Sym("风扬阵"), Sym("云垂阵"), Sym("龙飞阵")]
    return ("formation", {"key": rnd.choice(keys)})


def _promote_stone(_item_id, _rnd, _ctx):
    return ("promote_stone", {"id": 0, "count": 0})


# ---------------------------------------------------------------- 装备类产出
def _guide_book(_item_id, rnd, _ctx):
    r = rnd.randrange(2)
    if r == 0:
        return ("guide_book", {"type": Sym("w"),
                               "id": rnd.choice([1, 3, 4, 5, 6, 7, 9, 10, 11, 12]),
                               "lv": rnd.choice([0, 10, 20, 30, 40, 50, 60, 70, 80])})
    return ("guide_book", {"type": Sym("a"),
                           "id": rnd.choice([1, 2, 3, 4, 5, 6, 7]),
                           "lv": rnd.randrange(9) * 10})


def _iron(_item_id, rnd, _ctx):
    return ("iron", {"lv": rnd.randrange(17) * 10})


def _atlas(_item_id, rnd, _ctx):
    return ("ancient_forging_atlas",
            {"type": Sym("a"), "id": 8, "eid": rnd.randint(1, 3),
             "lv": rnd.randrange(9) * 10 + 5})


def _god_eye_bead(_item_id, rnd, _ctx):
    return ("god_eye_bead", {"lv": rnd.randrange(16) * 10 + 5})


# ---------------------------------------------------------------- 技能书
def _skill_book(_item_id, rnd, _ctx):
    return ("skill_book", {"id": _rng(rnd, (20, 54), (113, 116), (121, 121))})


def _skill_book_hi(_item_id, rnd, _ctx):
    return ("skill_book", {"id": _rng(rnd, (70, 99), (55, 59), (117, 120))})


# ---------------------------------------------------------------- 杂项
def _ginseng(_item_id, rnd, _ctx):
    return ("ginseng", {"type": rnd.randrange(5), "point": rnd.randint(1, 5),
                        "max": 5})


def _real_stick(_item_id, rnd, _ctx):
    return ("real_stick_1", {"id": rnd.randint(21, 120)})


def _real_stick_hi(_item_id, rnd, _ctx):
    return ("real_stick_2", {"id": rnd.randint(135, 159)})


def _stone(_item_id, rnd, _ctx):
    return ("stone", {"lv": 1})


def _yuanxiao(_item_id, rnd, _ctx):
    return ("yuanxiao", {
        "type": rnd.randrange(7),
        "value": {"atk": rnd.randint(5, 15), "def": rnd.randint(5, 15),
                  "hp": rnd.randint(40, 100), "mp": rnd.randint(10, 30),
                  "agi": rnd.randint(5, 15), "eva": rnd.randint(5, 15),
                  "grow": round(rnd.randint(1, 4) / 100.0, 2)},
        "max": [15, 15, 100, 30, 15, 15, 0.04]})


def _navigation_flag(_item_id, rnd, _ctx):
    return ("navigation_flag", {"id": 0, "count": 60})


# 名字里含这些词 → 用对应生成器（**从上往下匹配**，特例在前）
BUILDERS = (
    ("超级真知棒", _real_stick_hi),
    ("真知棒", _real_stick),
    ("高级魔兽要诀", _skill_book_hi),
    ("魔兽要诀", _skill_book),
    ("神兽孵化蛋", _god_egg),
    ("神兽蛋", _god_egg),
    ("孵化蛋", _baby_egg),
    ("鬼谷子", _formation),
    ("进阶石", _promote_stone),
    ("制造指南书", _guide_book),
    ("百炼精铁", _iron),
    ("上古锻造图策", _atlas),
    ("天眼珠", _god_eye_bead),
    ("人参果", _ginseng),
    ("元宵", _yuanxiao),
    ("导航旗", _navigation_flag),
    ("石头", _stone),
)

#: 这些"家族"的物品是游戏运行时才填内容的；补不上就得靠"克隆存档里同款"
NEEDS_PAYLOAD_HINT = tuple(n for n, _f in BUILDERS)


def builder_for(name):
    """按物品名字找生成器（找不到返回 None）。"""
    name = name or ""
    for key, fn in BUILDERS:
        if key in name:
            return fn
    return None


def build(name, item_id, ctx=None, rnd=None):
    """生成 `(type, data)`；不认识这件东西就返回 None。

    ctx：一个返回 `{备注值: [召唤兽id...]}` 的可调用对象（蛋类要用，可以传 None）。
    """
    fn = builder_for(name)
    if fn is None:
        return None
    return fn(int(item_id), rnd or random, ctx)


def needs_payload(name):
    """这件东西是不是"运行时才有内容"的那类。"""
    return builder_for(name) is not None
