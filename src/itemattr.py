# -*- coding: utf-8 -*-
"""游戏里"运行时才生成内容"的物品 —— 也就是存档物件里的 `@attr`（脚本里叫 `item.data`）。

例如孵化蛋：使用时会读 `item.data[:data][:id]` 来决定孵出哪只召唤兽，
而**这个 id 是游戏在发给你的时候现抽的**（脚本 `Game_Party#孵化蛋`）。

我们按 Data 模板"凭空造"一个物品时，`@attr` 只能是空 Hash；游戏一用就
`undefined method '[]' for nil:NilClass`（`item.data[:data]` 是 nil）。
所以这个模块把脚本里那十几个生成规则**照抄**成 Python：加这类物品时顺手生成
一份合法内容，或者干脆从存档里已有的同种物品整个复制过来（更保险）。

⚠ 两条**必须照抄**的东西（2026-10-04 逐条对齐 V2.201，见下）：

1. **`type` 是中文符号**（`:孵化蛋` / `:魔兽要诀` / `:宝石`…）。游戏的分发是
   `case (item.data and item.data[:type])` —— 写英文名（早期工具写的
   `:baby_egg` / `:navigation_flag`）游戏**一律不认**：物品浮窗不显示运行时那段，
   用的时候还可能 NoMethodError。实测真档里游戏写的是 `导航旗`，工具写过的那件
   就是 `navigation_flag`。
2. **数值范围也要照 V2.201**，尝鲜版那套差得远（蛋池、元宵数值、指南书 lv 表、
   精铁/天眼珠范围、要诀池…全都不同）。

生成规则来源：脚本 `class Game_Party` 的
`孵化蛋 / 神兽蛋 / 鬼谷子 / 进阶石 / 制造指南书 / 百炼精铁 / 魔兽要诀 /
上古锻造图策 / 天眼珠 / 人参果 / 真知棒 / 宝石 / 元宵 / 导航旗 / 礼盒` 等方法
（`script00_00000020.rb` 第 15448~16048 行），蛋池另见 `Item#draw_item`
的 `case item.id`（第 78092~78100 行）与摊位生成（第 40017~40036 行）。

生成器签名：`fn(item_id, rnd) -> (type符号, item.data 里除 :type 之外的整份内容)`。
返回值第二项的**形状由游戏决定**：多数是 `{"data": {...}}`，
少数如 `礼盒` 是 `{"list": [...]}`（没有 `data` 那一层）。
"""
import random

from tables import baby_aptitude as _BA


# --------------------------------------------------------------------------
# 节点用的"符号"占位（game 会把它转成 SymbolNode）
# --------------------------------------------------------------------------
class Sym(object):
    __slots__ = ("name",)

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return ":%s" % self.name


def _rng(rnd, *ranges):
    """游戏里的 `rand(21..23, 25..63)`：先等概率挑一个区间，再在区间里抽。"""
    pools = [list(range(a, b + 1)) for a, b in ranges]
    pool = pools[rnd.randrange(len(pools))]
    return rnd.choice(pool)


# ==========================================================================
# 孵化蛋：兽池全部按 `$baby` 真值算，不再用尝鲜版的硬编码号段
# ==========================================================================
#: 开蛋池（脚本 `def 孵化蛋` 与摊位生成 110..112 用的同一份 list）
EGG_LIST_RANGES = ((21, 23), (25, 134), (310, 354), (400, 433))
EGG_LIST_EXCLUDE = (336, 337, 416, 418, 419, 420, 421, 423)
#: 三档：脚本按 `$baby[i][:allow_lv]` 落在 `(0..55) / (56..125) / (126..160)` 里筛
EGG_TIERS = ((0, 55), (56, 125), (126, 160))
#: 真值拿不到时（尝鲜版的 `SPECIES` 没这些字段）才走的老号段
EGG_TIERS_LEGACY = (((21, 23), (25, 63)),
                    ((64, 95), (127, 134)),
                    ((96, 126),))
#: 神兽池：id 落在 `(135..170)` 且 `$baby[id][:type2]` 属于这两池
GOD_ID_RANGE = (135, 170)
GOD_POOL_NAMES = ("神兽资质", "神兽资质2")
#: 珍藏 / 传说神兽蛋的兽池（脚本 `Item#draw_item` 的 `when 223 / when 244` 写死）
TREASURE_IDS = tuple(range(179, 187))
LEGEND_IDS = tuple(range(200, 205))

_CACHE = {}


def _pool_map():
    """`{资质池名: [召唤兽 id, ...]}` —— 从 `$baby` 真值的 `type2` 反推。

    V2.201 的 `Data\\Actors` 备注里**一条 `data = :池名` 都没有**，
    所以只能这样反推（尝鲜版反过来，备注里有 45 条）。
    """
    if "pools" not in _CACHE:
        out = {}
        for i, cfg in _BA.SPECIES.items():
            t2 = cfg.get("type2")
            if t2:
                out.setdefault(t2, []).append(i)
        for v in out.values():
            v.sort()
        _CACHE["pools"] = out
    return _CACHE["pools"]


def _egg_list():
    ids = []
    for a, b in EGG_LIST_RANGES:
        ids.extend(range(a, b + 1))
    return [i for i in ids if i not in EGG_LIST_EXCLUDE]


def _tier_pool(tier):
    """第 `tier` 档（0/1/2）能孵出的 id：`list` 里 `allow_lv` 落在该区间的。"""
    key = ("tier", tier)
    if key not in _CACHE:
        lo, hi = EGG_TIERS[tier]
        out = []
        for i in _egg_list():
            lv = (_BA.SPECIES.get(i) or {}).get("allow_lv")
            if lv is not None and lo <= lv <= hi:
                out.append(i)
        _CACHE[key] = out
    return _CACHE[key]


def _god_pool(names):
    pools = _pool_map()
    out = set()
    for n in names:
        out.update(i for i in pools.get(n, ())
                   if GOD_ID_RANGE[0] <= i <= GOD_ID_RANGE[1])
    return sorted(out)


def egg_pool(item_id):
    """某个蛋类物品的可孵 id 列表（空列表 = 拿不到真值，调用方自己回退）。

    物品 id 与兽池的对应照脚本：`110~112` 走三档、`113` 走两池并集、
    `221/222` 分别走单池、`223/244` 是写死的珍藏/传说池。
    """
    if item_id in (110, 111, 112):
        return _tier_pool(item_id - 110)
    if item_id == 113:
        return _god_pool(GOD_POOL_NAMES)
    if item_id == 221:
        return _god_pool(("神兽资质",))
    if item_id == 222:
        return _god_pool(("神兽资质2",))
    if item_id == 223:
        return list(TREASURE_IDS)
    if item_id == 244:
        return list(LEGEND_IDS)
    return []


def _baby_egg(item_id, rnd):
    """初级/中级/高级孵化蛋（110/111/112）——脚本 `def 孵化蛋`（i = 0..2）。

    脚本还会写 `mutation: rand < 0.08 && i < 3`（i 就是 0..2，后半恒真）。
    """
    i = item_id - 110
    pool = _tier_pool(i)
    kid = rnd.choice(pool) if pool else _rng(rnd, *EGG_TIERS_LEGACY[i])
    return ("孵化蛋", {"data": {"id": kid,
                                "mutation": rnd.random() < 0.08}})


def _god_egg(item_id, rnd):
    """神兽孵化蛋(113) / 普通神兽蛋(221) / 生肖神兽蛋(222) / 珍藏(223) / 传说(244)。

    `113` 是 `孵化蛋(i=3)` 走的那支（会写 `mutation: false`），
    其余由 `神兽蛋` 或礼包直接给，不带 `mutation` 键。
    """
    pool = egg_pool(item_id)
    if not pool:                      # 连真值都没有才瞎抽一只神兽号段
        kid = _rng(rnd, GOD_ID_RANGE)
    else:
        kid = rnd.choice(pool)
    payload = {"id": kid}
    if item_id == 113:
        payload["mutation"] = False
    return ("孵化蛋", {"data": payload})


# ---------------------------------------------------------------- 阵法 / 进阶
def _formation(_item_id, rnd):
    keys = [Sym("天覆阵"), Sym("地载阵"), Sym("风扬阵"), Sym("云垂阵"),
            Sym("龙飞阵"), Sym("虎翼阵"), Sym("鸟翔阵"), Sym("蛇蟠阵"),
            Sym("鹰啸阵"), Sym("雷绝阵")]
    return ("鬼谷子", {"data": {"key": rnd.choice(keys)}})


def _promote_stone(_item_id, _rnd):
    return ("进阶石", {"data": {"id": 0, "count": 0}})


# ---------------------------------------------------------------- 装备类产出
def _guide_book(_item_id, rnd):
    """制造指南书：`r = rand(2)`；武器 (`:w`) 1..18 / lv 50~80，防具 (`:a`) 1..7 / lv 50~80。"""
    if rnd.randrange(2) == 0:
        return ("制造指南书", {"data": {"type": Sym("w"),
                                       "id": rnd.randint(1, 18),
                                       "lv": rnd.choice([50, 60, 70, 80])}})
    return ("制造指南书", {"data": {"type": Sym("a"),
                                   "id": rnd.randint(1, 7),
                                   "lv": rnd.choice([50, 60, 70, 80])}})


def _iron(_item_id, rnd):
    return ("百炼精铁", {"data": {"lv": rnd.randint(5, 16) * 10}})


def _atlas(_item_id, rnd):
    return ("上古锻造图策", {"data": {"type": Sym("a"), "id": 8,
                                     "eid": rnd.randint(1, 3),
                                     "lv": rnd.randrange(9) * 10 + 5}})


def _god_eye_bead(_item_id, rnd):
    return ("天眼珠", {"data": {"lv": rnd.randint(0, 17) * 10 + 5}})


# ---------------------------------------------------------------- 技能书
def _skill_book(_item_id, rnd):
    """魔兽要诀：`rand(20..54, 113..116, 121..121)`。"""
    return ("魔兽要诀", {"data": {"id": _rng(rnd, (20, 54), (113, 116), (121, 121))}})


def _skill_book_hi(_item_id, rnd):
    """高级魔兽要诀：`rand(70..99, 55..59, 117..120, 122..124, 101..108, 132..133, 137..138)`。"""
    return ("高级魔兽要诀", {"data": {"id": _rng(rnd, (70, 99), (55, 59), (117, 120),
                                                  (122, 124), (101, 108),
                                                  (132, 133), (137, 138))}})


def _skill_book_super(_item_id, rnd):
    """超级魔兽要诀：`rand(800..834)`。"""
    return ("超级魔兽要诀", {"data": {"id": rnd.randint(800, 834)}})


def _skill_book_special(_item_id, rnd):
    """特级魔兽要诀 —— 备注里 `icon = "特殊魔兽要诀"`，走特殊那支：
    `rand(109..112, 125..131, 134..136, 15)`。"""
    return ("特殊魔兽要诀", {"data": {"id": _rng(rnd, (109, 112), (125, 131),
                                                  (134, 136), (15, 15))}})


# ---------------------------------------------------------------- 变身棒
def _real_stick(item_id, rnd):
    """真知棒(91) / 超级真知棒(92)。

    超级那支：`id1 = rand(135..175)`、`id2 = rand(55..59, 70..99)`。
    普通那支脚本要读「该召唤兽所属门派的可学技能」再抽 `id2`
    （`c.learnings.select{...}`），**静态算不出来** ⇒ 用脚本自己的兜底
    `rand(20..54)`；`id1` 也从 `[21~134, 310~354, 400~433] - [416]` 直接抽
    （脚本里那 1% 的"稀有"分支靠 `$baby_types[:稀有]`，那是运行期外部数据）。
    """
    if item_id == 92:
        id1 = rnd.randint(135, 175)
        id2 = _rng(rnd, (55, 59), (70, 99))
    else:
        id1 = _rng(rnd, (21, 134), (310, 354), (400, 433))
        while id1 == 416:                      # 脚本把 416 剔掉了
            id1 = _rng(rnd, (21, 134), (310, 354), (400, 433))
        id2 = rnd.randint(20, 54)
    return ("超级真知棒" if item_id == 92 else "真知棒",
            {"data": {"id": id1, "sid": id2, "time": 0}})


# ---------------------------------------------------------------- 杂项
def _ginseng(_item_id, rnd):
    return ("人参果", {"data": {"type": rnd.randrange(5),
                                "point": rnd.randint(1, 5), "max": 5}})


def _stone(_item_id, _rnd):
    """宝石（光芒石/黑宝石…）：脚本 `def 石头` 写死 `{lv: 1}`。"""
    return ("宝石", {"data": {"lv": 1}})


def _yuanxiao(_item_id, rnd):
    """元宵：只让**一项**资质涨，其余为 0；上限表照脚本写死。"""
    ranges = ((4, 8), (4, 8), (20, 40), (10, 20), (4, 8), (4, 8))
    k = rnd.randrange(7)
    value = {"atk": 0, "def": 0, "hp": 0, "mp": 0, "agi": 0, "eva": 0,
             "grow": 0.0}
    keys = ("atk", "def", "hp", "mp", "agi", "eva", "grow")
    if k == 6:
        value["grow"] = round(rnd.uniform(0.01, 0.02), 4)
    else:
        a, b = ranges[k]
        value[keys[k]] = rnd.randint(a, b)
    return ("元宵", {"data": {"type": k, "value": value,
                              "max": [8, 8, 40, 20, 8, 8, 0.02]}})


def _yuanxiao_dan(_item_id, rnd):
    """激进元宵丹（135）：`def 激进元宵丹(item, max=10)` → `{max: 10}`。"""
    return ("激进元宵丹", {"data": {"max": 10}})


def _navigation_flag(item_id, rnd):
    """导航旗：`count ||= (item.id == 275 ? 40 : 140)`（**没有 id 键**）。"""
    return ("导航旗", {"data": {"count": 40 if item_id == 275 else 140}})


def _gift_box(_item_id, _rnd):
    """五彩导航旗盒（235）—— `def 礼盒(item, list=[])`，内容是 `{list: [...]}`。

    内含建邺/长安/朱紫/傲来/长寿五面导航旗（见物品说明）。
    ⚠ 盒子里那面旗的**可用次数由开盒时现给**（说明写 600 次，脚本默认 140），
    静态补不出来 —— 这里只保证盒子本身是合法的。
    """
    return ("礼盒", {"list": [[94, 1], [95, 1], [96, 1], [97, 1], [98, 1]]})


# 名字里含这些词 → 用对应生成器（**从上往下匹配**，特例在前）
BUILDERS = (
    ("超级真知棒", _real_stick),
    ("真知棒", _real_stick),
    ("高级魔兽要诀", _skill_book_hi),
    ("超级魔兽要诀", _skill_book_super),
    ("特级魔兽要诀", _skill_book_special),
    ("魔兽要诀", _skill_book),
    ("神兽孵化蛋", _god_egg),
    ("神兽蛋", _god_egg),                 # 221/222/223/244
    ("孵化蛋", _baby_egg),                # 110/111/112
    ("五彩导航旗盒", _gift_box),          # 必须排在「导航旗」前面
    ("导航旗", _navigation_flag),
    ("鬼谷子", _formation),
    ("进阶石", _promote_stone),
    ("制造指南书", _guide_book),
    ("百炼精铁", _iron),
    ("上古锻造图策", _atlas),
    ("天眼珠", _god_eye_bead),
    ("人参果", _ginseng),
    ("激进元宵丹", _yuanxiao_dan),        # 必须排在「元宵」前面
    ("元宵", _yuanxiao),
    # 七种宝石（脚本 `def 石头`，item.id - 73）
    ("光芒石", _stone), ("黑宝石", _stone), ("红玛瑙", _stone),
    ("舍利子", _stone), ("太阳石", _stone), ("月亮石", _stone),
    ("神秘石", _stone),
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


def build(name, item_id, rnd=None):
    """生成 `(type符号, 内容字典)`；不认识这件东西就返回 None。

    `type符号` 就是游戏写的中文符号，可以**直接写进 `@attr["data"][:type]`**。
    """
    fn = builder_for(name)
    if fn is None:
        return None
    return fn(int(item_id), rnd or random.Random())


def needs_payload(name):
    """这件东西是不是"运行时才有内容"的那类。"""
    return builder_for(name) is not None
