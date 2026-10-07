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

生成器签名：`fn(item_id, rnd, over=None) -> (type符号, item.data 里除 :type 之外的整份内容)`。
返回值第二项的**形状由游戏决定**：多数是 `{"data": {...}}`，
少数如 `礼盒` 是 `{"list": [...]}`（没有 `data` 那一层）。

`over` 是"用户指定值"（2026-10-07 加，给「重抽管理」窗口用）：给了就**优先用它**
——不传就是老行为（按游戏规则随机）。`payload_spec()` 报出这件东西**哪些字段
可以在界面上挑**（蛋→召唤兽池、要诀→技能池、元宵→资质…），界面照它渲染控件。
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


def _pool_of(ranges):
    """把 `_rng` 用的区间列表摊成**有序去重**的 id 列表（界面候选/校验用）。"""
    out = set()
    for a, b in ranges:
        out.update(range(a, b + 1))
    return sorted(out)


# ==========================================================================
# 「重抽管理」窗口能挑的取值 —— 全部来自脚本，不是估的
# ==========================================================================
#: 元宵的 7 档资质（下标就是 `data[:type]`）；名字与 `game.payload_summary` 同一口径
YUANXIAO_NAMES = ("攻击资质", "防御资质", "体力资质", "法力资质",
                  "速度资质", "躲闪资质", "成长")
#: 人参果的 5 档属性（下标就是 `data[:type]`）
GINSENG_NAMES = ("体质", "魔力", "力量", "耐力", "敏捷")
#: 鬼谷子的 10 个阵法（脚本 `def 鬼谷子` 里那份 list）
FORMATION_NAMES = ("天覆阵", "地载阵", "风扬阵", "云垂阵", "龙飞阵",
                   "虎翼阵", "鸟翔阵", "蛇蟠阵", "鹰啸阵", "雷绝阵")
#: 上古锻造图策的 3 个部位（`eid`；名字照 `game.payload_summary`）
ATLAS_PARTS = ((1, "护腕"), (2, "项圈"), (3, "铠甲"))
#: 魔兽要诀四档的抽取区间（**唯一来源**：随机生成与界面候选都读它）
BOOK_RANGES = {
    "魔兽要诀": ((20, 54), (113, 116), (121, 121)),
    "高级魔兽要诀": ((70, 99), (55, 59), (117, 120), (122, 124),
                     (101, 108), (132, 133), (137, 138)),
    "超级魔兽要诀": ((800, 834),),
    "特殊魔兽要诀": ((109, 112), (125, 131), (134, 136), (15, 15)),
}
#: 制造指南书 / 百炼精铁 / 天眼珠 / 图策的档位（脚本里 `rand` 的取值集合）
GUIDE_LVS = (50, 60, 70, 80)
IRON_LVS = tuple(range(50, 161, 10))
BEAD_LVS = tuple(range(5, 176, 10))
ATLAS_LVS = tuple(range(5, 86, 10))


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


def _baby_egg(item_id, rnd, over=None):
    """初级/中级/高级孵化蛋（110/111/112）——脚本 `def 孵化蛋`（i = 0..2）。

    脚本还会写 `mutation: rand < 0.08 && i < 3`（i 就是 0..2，后半恒真）。
    """
    over = over or {}
    i = item_id - 110
    kid = over.get("id")
    if kid is None:
        pool = _tier_pool(i)
        kid = rnd.choice(pool) if pool else _rng(rnd, *EGG_TIERS_LEGACY[i])
    mut = over.get("mutation")
    if mut is None:
        mut = rnd.random() < 0.08
    return ("孵化蛋", {"data": {"id": int(kid), "mutation": bool(mut)}})


def _god_egg(item_id, rnd, over=None):
    """神兽孵化蛋(113) / 普通神兽蛋(221) / 生肖神兽蛋(222) / 珍藏(223) / 传说(244)。

    `113` 是 `孵化蛋(i=3)` 走的那支（会写 `mutation: false`），
    其余由 `神兽蛋` 或礼包直接给，不带 `mutation` 键。
    """
    over = over or {}
    kid = over.get("id")
    if kid is None:
        pool = egg_pool(item_id)
        kid = rnd.choice(pool) if pool else _rng(rnd, GOD_ID_RANGE)
    payload = {"id": int(kid)}
    if item_id == 113:
        mut = over.get("mutation")
        payload["mutation"] = False if mut is None else bool(mut)
    return ("孵化蛋", {"data": payload})


# ---------------------------------------------------------------- 阵法 / 进阶
def _formation(_item_id, rnd, over=None):
    over = over or {}
    key = over.get("key")
    if key is None:
        key = rnd.choice(FORMATION_NAMES)
    return ("鬼谷子", {"data": {"key": Sym(str(key))}})


def _promote_stone(_item_id, _rnd, over=None):
    over = over or {}
    iid = over.get("id")
    cnt = over.get("count")
    return ("进阶石", {"data": {"id": 0 if iid is None else int(iid),
                                "count": 0 if cnt is None else int(cnt)}})


# ---------------------------------------------------------------- 装备类产出
def _guide_book(_item_id, rnd, over=None):
    """制造指南书：`r = rand(2)`；武器 (`:w`) 1..18 / lv 50~80，防具 (`:a`) 1..7 / lv 50~80。"""
    over = over or {}
    t = over.get("type")
    if t not in ("w", "a"):
        t = "w" if rnd.randrange(2) == 0 else "a"
    hi = 18 if t == "w" else 7
    iid = over.get("id")
    iid = rnd.randint(1, hi) if iid is None else max(1, min(int(iid), hi))
    lv = over.get("lv")
    lv = rnd.choice(GUIDE_LVS) if lv is None else int(lv)
    return ("制造指南书", {"data": {"type": Sym(t), "id": iid, "lv": lv}})


def _iron(_item_id, rnd, over=None):
    over = over or {}
    lv = over.get("lv")
    return ("百炼精铁", {"data": {"lv": rnd.randint(5, 16) * 10
                                  if lv is None else int(lv)}})


def _atlas(_item_id, rnd, over=None):
    over = over or {}
    eid = over.get("eid")
    eid = rnd.randint(1, 3) if eid is None else max(1, min(int(eid), 3))
    lv = over.get("lv")
    lv = rnd.randrange(9) * 10 + 5 if lv is None else int(lv)
    return ("上古锻造图策", {"data": {"type": Sym("a"), "id": 8,
                                     "eid": eid, "lv": lv}})


def _god_eye_bead(_item_id, rnd, over=None):
    over = over or {}
    lv = over.get("lv")
    return ("天眼珠", {"data": {"lv": rnd.randint(0, 17) * 10 + 5
                                if lv is None else int(lv)}})


# ---------------------------------------------------------------- 技能书
def _skill_book(_item_id, rnd, over=None):
    """魔兽要诀：`rand(20..54, 113..116, 121..121)`。"""
    over = over or {}
    kid = over.get("id")
    return ("魔兽要诀", {"data": {"id": _rng(rnd, *BOOK_RANGES["魔兽要诀"])
                                  if kid is None else int(kid)}})


def _skill_book_hi(_item_id, rnd, over=None):
    """高级魔兽要诀：`rand(70..99, 55..59, 117..120, 122..124, 101..108, 132..133, 137..138)`。"""
    over = over or {}
    kid = over.get("id")
    return ("高级魔兽要诀", {"data": {"id": _rng(rnd, *BOOK_RANGES["高级魔兽要诀"])
                                      if kid is None else int(kid)}})


def _skill_book_super(_item_id, rnd, over=None):
    """超级魔兽要诀：`rand(800..834)`。"""
    over = over or {}
    kid = over.get("id")
    return ("超级魔兽要诀", {"data": {"id": rnd.randint(800, 834)
                                      if kid is None else int(kid)}})


def _skill_book_special(_item_id, rnd, over=None):
    """特级魔兽要诀 —— 备注里 `icon = "特殊魔兽要诀"`，走特殊那支：
    `rand(109..112, 125..131, 134..136, 15)`。"""
    over = over or {}
    kid = over.get("id")
    return ("特殊魔兽要诀", {"data": {"id": _rng(rnd, *BOOK_RANGES["特殊魔兽要诀"])
                                      if kid is None else int(kid)}})


# ---------------------------------------------------------------- 变身棒
def _real_stick(item_id, rnd, over=None):
    """真知棒(91) / 超级真知棒(92)。

    超级那支：`id1 = rand(135..175)`、`id2 = rand(55..59, 70..99)`。
    普通那支脚本要读「该召唤兽所属门派的可学技能」再抽 `id2`
    （`c.learnings.select{...}`），**静态算不出来** ⇒ 用脚本自己的兜底
    `rand(20..54)`；`id1` 也从 `[21~134, 310~354, 400~433] - [416]` 直接抽
    （脚本里那 1% 的"稀有"分支靠 `$baby_types[:稀有]`，那是运行期外部数据）。
    """
    over = over or {}
    id1 = over.get("id")
    id2 = over.get("sid")
    if item_id == 92:
        if id1 is None:
            id1 = rnd.randint(135, 175)
        if id2 is None:
            id2 = _rng(rnd, (55, 59), (70, 99))
    else:
        if id1 is None:
            id1 = _rng(rnd, (21, 134), (310, 354), (400, 433))
            while id1 == 416:                      # 脚本把 416 剔掉了
                id1 = _rng(rnd, (21, 134), (310, 354), (400, 433))
        if id2 is None:
            id2 = rnd.randint(20, 54)
    return ("超级真知棒" if item_id == 92 else "真知棒",
            {"data": {"id": int(id1), "sid": int(id2), "time": 0}})


# ---------------------------------------------------------------- 杂项
def _ginseng(_item_id, rnd, over=None):
    over = over or {}
    ty = over.get("type")
    ty = rnd.randrange(5) if ty is None else max(0, min(int(ty), 4))
    pt = over.get("point")
    pt = rnd.randint(1, 5) if pt is None else max(1, min(int(pt), 5))
    return ("人参果", {"data": {"type": ty, "point": pt, "max": 5}})


def _stone(_item_id, _rnd, over=None):
    """宝石（光芒石/黑宝石…）：脚本 `def 石头` 写死 `{lv: 1}`。"""
    over = over or {}
    lv = over.get("lv")
    return ("宝石", {"data": {"lv": 1 if lv is None else max(1, int(lv))}})


def _yuanxiao(_item_id, rnd, over=None):
    """元宵：只让**一项**资质涨，其余为 0；上限表照脚本写死。"""
    over = over or {}
    ranges = ((4, 8), (4, 8), (20, 40), (10, 20), (4, 8), (4, 8))
    k = over.get("type")
    k = rnd.randrange(7) if k is None else max(0, min(int(k), 6))
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


def _yuanxiao_dan(_item_id, rnd, over=None):
    """激进元宵丹（135）：`def 激进元宵丹(item, max=10)` → `{max: 10}`。"""
    over = over or {}
    mx = over.get("max")
    return ("激进元宵丹", {"data": {"max": 10 if mx is None else int(mx)}})


def _navigation_flag(item_id, rnd, over=None):
    """导航旗：`count ||= (item.id == 275 ? 40 : 140)`（**没有 id 键**）。"""
    over = over or {}
    cnt = over.get("count")
    return ("导航旗", {"data": {"count": (40 if item_id == 275 else 140)
                                if cnt is None else max(1, int(cnt))}})


def _gift_box(_item_id, _rnd, over=None):
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


def build(name, item_id, rnd=None, over=None):
    """生成 `(type符号, 内容字典)`；不认识这件东西就返回 None。

    `type符号` 就是游戏写的中文符号，可以**直接写进 `@attr["data"][:type]`**。
    `over` = 用户指定的字段值（`{"id": 45, "mutation": True}` 这种），
    给了就优先用它，其余字段照游戏规则随机/固定。
    """
    fn = builder_for(name)
    if fn is None:
        return None
    return fn(int(item_id), rnd or random.Random(), over)


def needs_payload(name):
    """这件东西是不是"运行时才有内容"的那类。"""
    return builder_for(name) is not None


# ==========================================================================
# 「重抽管理」窗口用：这件东西的内容里，哪些字段可以挑
# ==========================================================================
def payload_spec(name, item_id):
    """`(type符号, [字段, ...])`；不是"运行时内容"类物品返回 `(None, [])`。

    字段是 dict：

        {"key": 内容里的键, "label": 界面上的名字,
         "kind": "actor" | "skill" | "choice" | "int",
         "pool": [可选 id]（actor/skill 用；None＝全部）,
         "choices": [(值, 显示名)]（choice 用）,
         "rng": (下限, 上限)（int 用）}

    ⚠ 这里报出来的**必须是脚本真值**：挑不动的（`进阶石` 的固定 0、`礼盒` 的
      固定五面旗）就不给字段，界面显示「只能按游戏规则重抽」。
    """
    fn = builder_for(name)
    if fn is None:
        return None, []
    if fn in (_baby_egg, _god_egg):
        pool = egg_pool(item_id)
        fields = [{"key": "id", "label": "孵出召唤兽", "kind": "actor",
                   "pool": pool or None}]
        if item_id in (110, 111, 112, 113):     # 只有这几支会写 mutation
            fields.append({"key": "mutation", "label": "变异", "kind": "choice",
                           "choices": [(True, "是"), (False, "否")]})
        return "孵化蛋", fields
    if fn in (_skill_book, _skill_book_hi, _skill_book_super,
              _skill_book_special):
        book = _book_kind(name)
        return book, [{"key": "id", "label": "开出的技能", "kind": "skill",
                       "pool": _pool_of(BOOK_RANGES[book])}]
    if fn is _real_stick:
        return ("超级真知棒" if int(item_id) == 92 else "真知棒"), [
            {"key": "id", "label": "变身目标", "kind": "actor", "pool": None},
            {"key": "sid", "label": "附带技能", "kind": "skill", "pool": None}]
    if fn is _formation:
        return "鬼谷子", [{"key": "key", "label": "阵法", "kind": "choice",
                           "choices": [(n, n) for n in FORMATION_NAMES]}]
    if fn is _promote_stone:
        return "进阶石", [{"key": "id", "label": "已进阶对象", "kind": "actor",
                           "pool": None},
                          {"key": "count", "label": "进度", "kind": "int",
                           "rng": (0, 50)}]
    if fn is _guide_book:
        return "制造指南书", [
            {"key": "type", "label": "类别", "kind": "choice",
             "choices": [("w", "武器"), ("a", "防具")]},
            {"key": "id", "label": "图样编号", "kind": "int", "rng": (1, 18)},
            {"key": "lv", "label": "等级", "kind": "choice",
             "choices": [(v, str(v)) for v in GUIDE_LVS]}]
    if fn is _iron:
        return "百炼精铁", [{"key": "lv", "label": "等级", "kind": "choice",
                             "choices": [(v, str(v)) for v in IRON_LVS]}]
    if fn is _atlas:
        return "上古锻造图策", [
            {"key": "eid", "label": "部位", "kind": "choice",
             "choices": [(v, n) for v, n in ATLAS_PARTS]},
            {"key": "lv", "label": "等级", "kind": "choice",
             "choices": [(v, str(v)) for v in ATLAS_LVS]}]
    if fn is _god_eye_bead:
        return "天眼珠", [{"key": "lv", "label": "等级", "kind": "choice",
                           "choices": [(v, str(v)) for v in BEAD_LVS]}]
    if fn is _ginseng:
        return "人参果", [
            {"key": "type", "label": "属性", "kind": "choice",
             "choices": [(i, n) for i, n in enumerate(GINSENG_NAMES)]},
            {"key": "point", "label": "点数", "kind": "int", "rng": (1, 5)}]
    if fn is _stone:
        return "宝石", [{"key": "lv", "label": "等级", "kind": "int",
                         "rng": (1, 15)}]
    if fn is _yuanxiao:
        return "元宵", [{"key": "type", "label": "涨哪项资质", "kind": "choice",
                         "choices": [(i, n) for i, n in
                                     enumerate(YUANXIAO_NAMES)]}]
    if fn is _yuanxiao_dan:
        return "激进元宵丹", [{"key": "max", "label": "可食用上限",
                               "kind": "int", "rng": (0, 100)}]
    if fn is _navigation_flag:
        return "导航旗", [{"key": "count", "label": "可用次数", "kind": "int",
                           "rng": (1, 600)}]
    if fn is _gift_box:
        return "礼盒", []
    return None, []


def _book_kind(name):
    """要诀的四档 —— 返回值同时是 `BOOK_RANGES` 的键**和**游戏写的 type 符号。

    ⚠ 物品名是 `特级魔兽要诀`，游戏写的 type 符号却是 `特殊魔兽要诀`
      （脚本 `_skill_book_special` 那一支），两者别混。
    """
    name = name or ""
    if "高级魔兽要诀" in name:
        return "高级魔兽要诀"
    if "超级魔兽要诀" in name:
        return "超级魔兽要诀"
    if "特级魔兽要诀" in name:
        return "特殊魔兽要诀"
    return "魔兽要诀"
