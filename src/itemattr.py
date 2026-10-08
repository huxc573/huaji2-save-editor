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


class IntHash(dict):
    """键要写成**整数**的 Hash（`_plain_node` 里 dict 默认写成符号键）。

    战神精气的 `skill: {技能id => {val:, max:}}`、仙人精气的
    `skills: {技能id => …}` 都是整数键 —— 用符号键游戏读不出来。
    """


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


def _weighted(rnd, weights):
    """游戏里的 `rand_average([920,80,1])`：按权重抽**下标**。"""
    total = sum(weights)
    r = rnd.randrange(total)
    acc = 0
    for i, w in enumerate(weights):
        acc += w
        if r < acc:
            return i
    return len(weights) - 1


# ==========================================================================
# 「重抽管理」窗口能挑的取值 —— 全部来自脚本，不是估的
# ==========================================================================
#: 元宵的 7 档资质（下标就是 `data[:type]`）；名字与 `game.payload_summary` 同一口径
YUANXIAO_NAMES = ("攻击资质", "防御资质", "体力资质", "法力资质",
                  "速度资质", "躲闪资质", "成长")
#: 元宵每档能涨多少（下标同 `YUANXIAO_NAMES`）—— **唯一来源**：
#: `_yuanxiao` 的随机区间、`data[:max]` 上限表、界面「数值」的取值范围都读它。
#: 成长那档是浮点，其余是整数（脚本里 `rand(0.01..0.02)` / `rand(4..8)`…）。
YUANXIAO_RANGES = ((4, 8), (4, 8), (20, 40), (10, 20), (4, 8), (4, 8),
                   (0.01, 0.02))
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
    """元宵：只让**一项**资质涨，其余为 0；上限表照脚本写死。

    `over` 认两个键：`type`（涨哪项资质，下标同 `YUANXIAO_NAMES`）、
    `value`（**这一项涨多少**）。不给 `value` 就按 `YUANXIAO_RANGES[type]`
    随机；给了就夹到该档区间里（界面的「数值」默认填的就是区间上限，
    2026-10-07 川：默认抽最大范围）。
    """
    over = over or {}
    k = over.get("type")
    k = rnd.randrange(7) if k is None else max(0, min(int(k), 6))
    lo, hi = YUANXIAO_RANGES[k]
    v = over.get("value")
    if v is None:
        v = round(rnd.uniform(lo, hi), 4) if k == 6 else rnd.randint(lo, hi)
    elif k == 6:
        v = round(max(0.0, min(float(v), float(hi))), 4)
    else:
        v = max(0, min(int(v), int(hi)))
    value = {"atk": 0, "def": 0, "hp": 0, "mp": 0, "agi": 0, "eva": 0,
             "grow": 0.0}
    keys = ("atk", "def", "hp", "mp", "agi", "eva", "grow")
    value[keys[k]] = v
    return ("元宵", {"data": {"type": k, "value": value,
                              "max": [hi2 for _lo2, hi2 in YUANXIAO_RANGES]}})


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


# ---------------------------------------------------------------- 坐骑蛋蛋
#: 坐骑蛋蛋(148) 能开出的 8 只坐骑 —— 脚本 `rand(*256..263)` 等概率抽一个。
#: 名字/移速区间取自 `Data\Actors` 的 256~263 与其 `@class_id` 指向的
#: `Data\Classes` 备注 `speed = a..b`（脚本 `坐骑蛋蛋` 里正是读备注算的）。
#: ⚠ 下标就是 `data[:id] - 256`（物品栏角标 `arr[@item.data[:data][:id]-256]`
#:   就是这 8 个字：龟/葫/马/羊/兽/狼/鹤/鹿）。
RIDE_IDS = (256, 257, 258, 259, 260, 261, 262, 263)
RIDE_NAMES = ("神气小龟", "宝贝葫芦", "汗血宝马", "欢喜羊羊",
              "魔力斗兽", "披甲战狼", "闲云野鹤", "云魅仙鹿")
#: 每只坐骑的移速加成区间（照 `Data\Classes` 备注，**别按 class id 排序**）
RIDE_SPEED_RANGE = ((0.020, 0.035), (0.070, 0.085), (0.070, 0.095),
                    (0.020, 0.035), (0.030, 0.045), (0.040, 0.055),
                    (0.070, 0.095), (0.065, 0.085))
#: 品质：`rand_average([920,80,1])` → 0 普通 / 1 靓仔 / 2 神骑
RIDE_QUALITY_NAMES = ("普通", "靓仔", "神骑")
RIDE_QUALITY_WEIGHT = (920, 80, 1)
#: 品质 > 0 时移速再乘一段倍率（品质 1 / 品质 2）
RIDE_QUALITY_MULT = ((1.0, 1.5), (1.5, 2.0))


def ride_rows():
    """重抽管理「封印坐骑」候选 `[(id, 名字, 说明)]`（说明＝该坐骑移速区间）。

    ⚠ 坐骑 id(256~263) 在 `Data\\Actors` 里**有名字，但不是召唤兽**
      （`is_baby_entry()` 判否）—— 所以不能用召唤兽候选表去筛，否则
      要「封印坐骑」时会得到 0 项（2026-10-08 川报「封印坐骑是空的」）。
    """
    out = []
    for i, rid in enumerate(RIDE_IDS):
        lo, hi = RIDE_SPEED_RANGE[i]
        out.append((rid, RIDE_NAMES[i],
                    "移速 +%.1f%%~+%.1f%%" % (lo * 100, hi * 100)))
    return out


def ride_best_id():
    """默认「封印坐骑」＝**移速上限最高**的那只（并列取先出现的，即 258）。

    「默认取最大值」这条口径（2026-10-07 川）在离散项上的落点：坐骑没有绝对
    强弱，但移速区间上限能排序 —— 取上限最高的那个当默认值。
    """
    best, bid = -1.0, RIDE_IDS[0]
    for i, rid in enumerate(RIDE_IDS):
        if RIDE_SPEED_RANGE[i][1] > best:
            best, bid = RIDE_SPEED_RANGE[i][1], rid
    return bid


def ride_speed_rng(rid, quality):
    """坐骑蛋蛋「移速」的取值范围 `(下限, 上限)` —— 跟着所选坐骑与品质现算。

    游戏侧 `Game_Party#坐骑蛋蛋` 就是「该坐骑区间 `rand` 一个，品质 > 0 再乘
    一段倍率」；所以这里的区间也这么合成（品质神骑时上限 = 9.5% × 2.0）。
    """
    i = RIDE_IDS.index(rid) if rid in RIDE_IDS else 0
    lo, hi = RIDE_SPEED_RANGE[i]
    q = int(quality or 0)
    if q > 0:
        a, b = RIDE_QUALITY_MULT[min(q, 2) - 1]
        lo, hi = lo * a, hi * b
    return (round(lo, 4), round(hi, 4))


def _ride_egg(_item_id, rnd, over=None):
    """坐骑蛋蛋(148) —— 脚本 `Game_Party#坐骑蛋蛋`。

    内容形状照脚本写死：`{data: {id:, type:, seed:, speed:}}`（**键序也一样**）。
    ⚠ 这件东西**必须**有运行时内容：公共事件 24「WITH_[孵化蛋]」拿到它就直接
      `d = $item_obj.data[:data]` 再 `add_ride(d)` —— `@attr` 空的话
      `nil[:data]` 当场 NoMethodError（2026-10-08 川报「用了卡死」，日志实证）。
    """
    over = over or {}
    rid = over.get("id")
    rid = rnd.choice(RIDE_IDS) if rid is None else int(rid)
    i = RIDE_IDS.index(rid) if rid in RIDE_IDS else 0
    q = over.get("type")
    q = _weighted(rnd, RIDE_QUALITY_WEIGHT) if q is None \
        else max(0, min(int(q), 2))
    lo, hi = RIDE_SPEED_RANGE[i]
    # 移速可以**直接指定**（重抽管理把它做成可编辑字段）——给了就照写。
    got = over.get("speed")
    if got is None:
        speed = round(rnd.uniform(lo, hi), 4)
        if q > 0:
            a, b = RIDE_QUALITY_MULT[q - 1]
            speed = round(speed * rnd.uniform(a, b), 4)
    else:
        speed = round(float(got), 4)
    seed = over.get("seed")
    seed = rnd.randrange(0, 2 ** 31) if seed is None else int(seed)
    return ("坐骑蛋蛋", {"data": {"id": RIDE_IDS[i], "type": q,
                                  "seed": seed, "speed": speed}})


# ==========================================================================
# 2026-10-08 补齐：`Game_Party#special?` 里剩下的、**能静态复刻**的家族
# ==========================================================================
# 之前的表漏了 19 个 id —— 加进背包时工具不写 `@attr`（`need=False`），
# 游戏侧 `item.data` 为 nil，看起来"没事"，但其中一部分游戏侧直接读
# `item.data[:data]`（角标/浮窗），还有一部分加了内容才可用。
# 这一批照脚本 `script00_00000020.rb` 第 15535~16134 行逐条抄。

#: 内丹 id 池（脚本 `def 内丹`：高级 `[*331..344]` / 低级 `[*351..372]`）
DAN_HIGH_RANGE = (331, 344)
DAN_LOW_RANGE = (351, 372)
#: 天材地宝的档位上限表（脚本 `def 天材地宝` 的 `lvs`）与抽档权重
TIANCAI_LVS = (40, 55, 70, 85, 100, 115, 130, 145, 155, 160)
TIANCAI_WEIGHTS = (80, 15, 5)
#: 灵饰指南书 / 元灵晶石共用等级（脚本 `6.times.map{|i| 60 + i * 20 }`）
LINGSHI_LVS = (60, 80, 100, 120, 140, 160)
#: 灵饰指南书的图样编号（脚本 `rand(10..13)`）
LINGSHI_ID_RANGE = (10, 13)
#: 上古技能残卷的门派（脚本 `$sects.keys.reject{|i| i == 0 }`）
SECT_IDS = tuple(range(1, 13))
#: 仙人精气的远古技能池（脚本 `def 仙人精气` 里那份 list）
XIANREN_SKILLS = (81, 89, 70, 82, 85, 59, 91, 98, 97, 93, 99, 124, 130,
                  135, 126)
#: 符文的随机技能池（脚本 `rand(551..574)`）
FUWEN_SKILL_RANGE = (551, 574)
#: 角色的等级上限（脚本 `Config::Game::MAX_LEVEL_ACTOR = 155`）
MAX_LEVEL_ACTOR = 155
#: 「无级别点化石」写死的技能＝无级别限制（脚本 `$skills[:E_无级别限制]`）
DIANHUA_SKILL = 156
#: 圣者精气的五项属性（脚本 `group`）
SHENGZHE_ATTRS = ("体质", "魔力", "力量", "耐力", "敏捷")
#: 战神精气的十二门派 → 技能（脚本 `skills` 表）
ZHANSHEN_SKILLS = {
    1: (186, 181, 189), 2: (198, 192, 201), 3: (205, 211, 209),
    4: (215, 220, 221), 5: (229, 227, 234), 6: (236, 243, 245),
    7: (252, 247, 255), 8: (260, 263, 267), 9: (272, 277, 278),
    10: (280, 286, 289), 11: (291, 295, 300), 12: (305, 304, 310),
}
#: 战神精气每个技能的数值（脚本 `sdata`）：技能 → (值区间表, 上限表)。
#: 区间是 `(下限, 上限, 是否整数)` —— `rand(0.1..0.2)` 浮点、`rand(1..2)` 整数。
ZHANSHEN_SDATA = {
    186: (((0.10, 0.20, False),), (0.20,)),
    181: (((0.20, 0.40, False), (10, 35, True)), (0.40, 35)),
    189: (((1, 2, True),), (2,)),
    198: (((2, 3, True), (20, 40, True)), (3, 40)),
    192: (((0.30, 0.50, False),), (0.50,)),
    205: (((0.05, 0.15, False), (1, 2, True)), (0.15, 2)),
    209: (((0.10, 0.25, False),), (0.25,)),
    215: (((0.02, 0.05, False),), (0.05,)),
    220: (((0.03, 0.075, False),), (0.075,)),
    221: (((0.20, 0.35, False),), (0.35,)),
    229: (((1, 2, True), (25, 50, True)), (2, 50)),
    227: (((0.30, 0.50, False),), (0.50,)),
    234: (((1, 2, True), (1, 2, True)), (2, 2)),
    243: (((0.15, 0.35, False),), (0.35,)),
    260: (((0.15, 0.30, False), (0.05, 0.30, False)), (0.30, 0.30)),
    263: (((0.15, 0.30, False),), (0.30,)),
    280: (((0.50, 2.50, False), (50, 150, True)), (2.50, 150)),
    300: (((0.15, 0.30, False),), (0.30,)),
    305: (((0.15, 0.30, False),), (0.30,)),
    304: (((0.30, 0.50, False),), (0.50,)),
    310: (((0.70, 1.00, False),), (1.0,)),
}
#: 战神精气的五项属性（脚本 `group`）：(名字, 下限, 上限, 满值)
ZHANSHEN_ATTRS = (("气血上限", 20, 200, 200), ("法力上限", 20, 100, 100),
                  ("物理攻击", 1, 30, 30), ("灵力", 1, 30, 30),
                  ("速度", 1, 30, 30))
#: 仙人精气的五项属性（脚本 `group`）
XIANREN_ATTRS = (("物理攻击", 1, 50, 50), ("物理防御", 1, 100, 100),
                 ("灵力", 1, 50, 50), ("法术防御", 1, 100, 100),
                 ("速度", 1, 50, 50))
#: 符文随机词条的五项属性（脚本 `[:体质,:魔力,:力量,:耐力,:敏捷]`）
FUWEN_ATTR_KEYS = ("体质", "魔力", "力量", "耐力", "敏捷")


def _seed30(rnd):
    """脚本里的 `(rand * 1E30).to_i` —— 各类精气/树苗的随机标记。

    30 位整数超出 Fixnum，写出时走大整数编码（`marshal_ruby` 已支持）。
    """
    return int(rnd.random() * 1E30)


def _pick_attrs(rnd, table, weights):
    """脚本里 `group.shuffle.first(rand_average(w))`：按权重定个数，再乱序取。

    返回 `[[属性符号, 值, 满值], …]`（值在各自区间里抽）。
    """
    pool = list(table)
    rnd.shuffle(pool)
    out = []
    for name, lo, hi, full in pool[:_weighted(rnd, weights)]:
        out.append([Sym(name), rnd.randint(lo, hi), full])
    return out


def _ruyi(_item_id, rnd, over=None):
    """如意丹（脚本 `def 如意丹`）—— 结构与人参果一模一样，只是 type 不同。"""
    over = over or {}
    ty = over.get("type")
    ty = rnd.randrange(5) if ty is None else max(0, min(int(ty), 4))
    pt = over.get("point")
    pt = rnd.randint(1, 5) if pt is None else max(1, min(int(pt), 5))
    return ("如意丹", {"data": {"type": ty, "point": pt, "max": 5}})


def _qiankun(_item_id, rnd, over=None):
    """乾坤袋（脚本 `def 乾坤袋`）：`{max: 容量, data: {}}`。

    ⚠ `data` 是**空 Hash**（跟 `max` 平级，游戏读 `item.data[:data].length`
      当已用量），这一层不能省。
    ⚠ 字段直接叫 `max`（容量），不叫"页数" —— 否则界面回填时读不到现值。
    """
    over = over or {}
    mx = over.get("max")
    mx = 20 if mx is None else max(1, int(mx))
    return ("乾坤袋", {"max": mx, "data": {}})


def _neidan(item_id, rnd, over=None):
    """内丹（脚本 `def 内丹`）：134 高级（331~344）/ 133 低级（351~372）。"""
    over = over or {}
    hi = int(item_id) == 134
    lo, top = DAN_HIGH_RANGE if hi else DAN_LOW_RANGE
    iid = over.get("id")
    iid = rnd.randint(lo, top) if iid is None else max(lo, min(int(iid), top))
    return ("高级内丹" if hi else "低级内丹", {"data": {"id": iid}})


def _tiancai(_item_id, rnd, over=None):
    """天材地宝（脚本 `def 天材地宝`）：档位 `lv` 与上限 `limit` 联动。"""
    over = over or {}
    lv = over.get("lv")
    lv = _weighted(rnd, TIANCAI_WEIGHTS) if lv is None else int(lv)
    lv = max(0, min(lv, len(TIANCAI_LVS) - 1))
    return ("天材地宝", {"data": {"lv": lv, "limit": TIANCAI_LVS[lv],
                                  "noup": bool(over.get("noup", False))}})


def _shengzhe(_item_id, rnd, over=None):
    """圣者精气（脚本 `def 圣者精气`）：1~3 项属性，各带 50 上限。

    ⚠ 它的属性值是**三档区间**里按权重挑一段再抽（`[1..20, 10..35,
      20..50][rand_average([35,30,25])]`），比战神/仙人精气的单区间多一层。
    """
    pool = list(SHENGZHE_ATTRS)
    rnd.shuffle(pool)
    point = []
    for name in pool[:_weighted(rnd, (75, 20, 5)) + 1]:
        lo, hi = ((1, 20), (10, 35), (20, 50))[_weighted(rnd, (35, 30, 25))]
        point.append([Sym(name), rnd.randint(lo, hi), 50])
    return ("圣者精气", {"point": point, "seed": _seed30(rnd)})


def _zhanshen(_item_id, rnd, over=None):
    """战神精气（脚本 `def 战神精气`）：门派 + 门派技能 + 技能数值 + 属性。"""
    over = over or {}
    sect = over.get("sect")
    sect = rnd.choice(sorted(ZHANSHEN_SKILLS)) if sect is None else int(sect)
    if sect not in ZHANSHEN_SKILLS:
        sect = sorted(ZHANSHEN_SKILLS)[0]
    sid = over.get("skill")
    sid = rnd.choice(ZHANSHEN_SKILLS[sect]) if sid is None else int(sid)
    specs, maxes = ZHANSHEN_SDATA.get(sid, ((), ()))
    val = []
    for lo, hi, is_int in specs:
        val.append(rnd.randint(int(lo), int(hi)) if is_int
                   else round(rnd.uniform(lo, hi), 4))
    return ("战神精气", {"sect": sect,
                         "skill": IntHash({sid: {"val": val,
                                                 "max": list(maxes)}}),
                         "attributes": _pick_attrs(rnd, ZHANSHEN_ATTRS,
                                                   (70, 25, 5)),
                         "seed": _seed30(rnd)})


def _xianren(_item_id, rnd, over=None):
    """仙人精气（脚本 `def 仙人精气`）：一个远古技能 + 若干属性。

    ⚠ 技能的 `val`/`max` 是**空数组**（脚本写死），别照着别的家族填数。
    """
    over = over or {}
    sid = over.get("id")
    sid = rnd.choice(XIANREN_SKILLS) if sid is None else int(sid)
    return ("仙人精气", {"skills": IntHash({sid: {"val": [], "max": []}}),
                         "attributes": _pick_attrs(rnd, XIANREN_ATTRS,
                                                   (70, 25, 5)),
                         "seed": _seed30(rnd)})


def _benyuan(_item_id, rnd, over=None):
    """本源（脚本 `def 本源精气`）—— 只有个随机 seed，最省事的一件。"""
    return ("本源精气", {"seed": _seed30(rnd)})


def _lingshi_book(_item_id, rnd, over=None):
    """灵饰指南书（脚本 `def 灵饰指南书`）。⚠ `type` 是符号 `:a`。"""
    over = over or {}
    lo, top = LINGSHI_ID_RANGE
    iid = over.get("id")
    iid = rnd.randint(lo, top) if iid is None else max(lo, min(int(iid), top))
    lv = over.get("lv")
    lv = rnd.choice(LINGSHI_LVS) if lv is None else int(lv)
    return ("灵饰指南书", {"data": {"type": Sym("a"), "id": iid, "lv": lv}})


def _lingstone(_item_id, rnd, over=None):
    """元灵晶石（脚本 `def 元灵晶石`）。"""
    over = over or {}
    lv = over.get("lv")
    lv = rnd.choice(LINGSHI_LVS) if lv is None else int(lv)
    return ("元灵晶石", {"data": {"lv": lv}})


def _peach(_item_id, rnd, over=None):
    """蟠桃（脚本 `def 蟠桃`）：`year = rand(1..66) * 100`。

    ⚠ 脚本还会把物品名改成「×年蟠桃」——生成器只写 `@attr`、改不了物品名，
      所以工具加出来的仍叫「蟠桃」。不影响使用（游戏只读 `data[:year]`）。
    """
    over = over or {}
    year = over.get("year")
    year = rnd.randint(1, 66) * 100 if year is None else int(year)
    return ("蟠桃", {"year": year})


def _fuwen(_item_id, rnd, over=None):
    """符文（脚本 `def 符文`）：等级 / 星 / 词条 / 附带技能 / 时效。"""
    over = over or {}
    powers = []
    for _ in range(rnd.randint(1, 3)):
        i = rnd.randrange(9)
        if i <= 4:
            powers.append({"k": Sym(FUWEN_ATTR_KEYS[i]), "v": rnd.randint(1, 10)})
        elif i == 5:
            powers.append({"k": Sym("fixed"), "v": rnd.randint(50, 600)})
        elif i == 6:
            powers.append({"k": Sym("eva"),
                           "v": round(rnd.uniform(0.01, 0.03), 4)})
        elif i == 7:
            powers.append({"k": Sym("cri"),
                           "v": round(rnd.uniform(0.01, 0.03), 4)})
        else:
            powers.append({"k": Sym("cri_dmg"),
                           "v": round(rnd.uniform(0.01, 0.10), 4)})
    lo, top = FUWEN_SKILL_RANGE
    skill = rnd.randrange(lo, top + 1) if rnd.random() < 0.25 else None
    lv = over.get("lv")
    lv = rnd.randint(1, MAX_LEVEL_ACTOR) if lv is None else int(lv)
    star = over.get("star")
    star = _weighted(rnd, (70, 20, 10)) + 1 if star is None else int(star)
    return ("符文", {"data": {
        "lv": lv, "star": star, "powers": powers, "skill": skill,
        "mode": {"time": [Sym("turn")], "curr": 0,
                 "max": rnd.randint(3, 10), "disappear": True}}})


def _canjuan(_item_id, rnd, over=None):
    """上古技能残卷（脚本 `def 上古技能残卷`）：`id` 就是门派。"""
    over = over or {}
    sid = over.get("id")
    sid = rnd.choice(SECT_IDS) if sid is None else max(1, min(int(sid), 12))
    return ("上古技能残卷", {"data": {"id": sid}})


def _yinhang(_item_id, rnd, over=None):
    """银票（脚本 `def 银票`）：金额平时由调用方给，这里自己定一个。"""
    over = over or {}
    gold = over.get("gold")
    gold = rnd.randint(1000, 1000000) if gold is None else max(0, int(gold))
    return ("银票", {"gold": gold, "from": None, "tag": Sym("system")})


def _tishenlei(_item_id, rnd, over=None):
    """提神泪（脚本 `def 提神泪`）：`data[:value]` 就是浮窗显示的恢复点数。

    ⚠ 脚本里函数收的是**疲劳量**、存的是 `max(量 ÷ 2.2, 1)` —— 那是游戏发奖
      时做的换算。工具直接写**存值**（界面显示多少就填多少），不然界面回填
      现值、生成器再除一次，会越改越小。
    """
    over = over or {}
    v = over.get("value")
    v = rnd.randint(45, 2200) if v is None else max(1, int(v))
    return ("提神泪", {"value": v})


def _qian_tree(_item_id, rnd, over=None):
    """摇钱树树苗（脚本 `def 摇钱树树苗`）—— 只有个随机 seed。"""
    return ("摇钱树树苗", {"seed": _seed30(rnd)})


def _dianhua(_item_id, rnd, over=None):
    """点化石（脚本 `def 点化石`）—— 只做 224「无级别点化石」。

    ⚠ 107「点化石」的内容来自运行期 `TemplateManager`（附加状态/法术追加
      模板），静态抄不出来 ⇒ 它**不进 BUILDERS**：工具不给它写 `@attr`，
      游戏侧 `item.data` 为 nil 时 `special?` 会自己填（`return item if
      item.data` 不命中），反而安全。⚠ 千万别给它写个空 Hash —— 空 Hash 是
      真值，会提前 return，内容就永远填不上（2026-10-08 坐骑蛋蛋那个坑）。
    """
    return ("点化石", {"data": {"type": 3, "id": DIANHUA_SKILL}})


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
    ("坐骑蛋蛋", _ride_egg),              # 148（公共事件 24 直接读 data[:data]）
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
    # ---- 2026-10-08 补齐：`special?` 里剩下能静态复刻的那批 ----
    # ⚠ 这几条的第三项是**物品 id 白名单**。名字会撞车 ——「点化石」也含于
    #   225「十个点化石」、「符文」也含于 158「符文碎片」，光按名字匹配会把
    #   不需要运行时内容的那件也一起认下来（写错内容比不写更糟）。
    ("如意丹", _ruyi, (131,)),
    ("点化石", _dianhua, (224,)),        # 107 走运行期模板，故意不做
    ("乾坤袋", _qiankun, (123,)),
    ("内丹", _neidan, (133, 134)),
    ("天材地宝", _tiancai, (140,)),
    ("圣者精气", _shengzhe, (141,)),
    ("战神精气", _zhanshen, (142,)),
    ("仙人精气", _xianren, (143,)),
    ("本源", _benyuan, (144,)),          # 物品名就叫「本源」，不是「本源精气」
    ("灵饰指南书", _lingshi_book, (150,)),
    ("元灵晶石", _lingstone, (151,)),
    ("蟠桃", _peach, (157,)),
    ("符文", _fuwen, (159,)),
    ("上古技能残卷", _canjuan, (160,)),
    ("银票", _yinhang, (276,)),
    ("提神泪", _tishenlei, (277,)),
    ("摇钱树树苗", _qian_tree, (280,)),
)

#: 这些"家族"的物品是游戏运行时才填内容的；补不上就得靠"克隆存档里同款"
NEEDS_PAYLOAD_HINT = tuple(row[0] for row in BUILDERS)


def builder_for(name, item_id=None):
    """按物品名字找生成器（找不到返回 None）。

    BUILDERS 的条目是 `(名字片段, 生成器)` 或 `(名字片段, 生成器, ids)`。
    带 `ids` 的只在 `item_id` 落在白名单里才认 —— 挡名字撞车：「点化石」
    也含于 225「十个点化石」、「符文」也含于 158「符文碎片」，这两件不需要
    运行时内容，别顺手给它们也写一份（写错内容比留空更糟）。
    ⚠ `item_id` 没给（老的调用点）时按老规矩只认名字。
    """
    name = name or ""
    for row in BUILDERS:
        key, fn = row[0], row[1]
        if key not in name:
            continue
        if len(row) > 2 and item_id is not None and int(item_id) not in row[2]:
            continue
        return fn
    return None


def build(name, item_id, rnd=None, over=None):
    """生成 `(type符号, 内容字典)`；不认识这件东西就返回 None。

    `type符号` 就是游戏写的中文符号，可以**直接写进 `@attr["data"][:type]`**。
    `over` = 用户指定的字段值（`{"id": 45, "mutation": True}` 这种），
    给了就优先用它，其余字段照游戏规则随机/固定。
    """
    fn = builder_for(name, item_id)
    if fn is None:
        return None
    return fn(int(item_id), rnd or random.Random(), over)


def needs_payload(name, item_id=None):
    """这件东西是不是"运行时才有内容"的那类。"""
    return builder_for(name, item_id) is not None


# ==========================================================================
# 「重抽管理」窗口用：这件东西的内容里，哪些字段可以挑
# ==========================================================================
def payload_spec(name, item_id):
    """`(type符号, [字段, ...])`；不是"运行时内容"类物品返回 `(None, [])`。

    字段是 dict：

        {"key": 内容里的键, "label": 界面上的名字,
         "kind": "actor" | "ride" | "skill" | "choice" | "int" | "num",
         "pool": [可选 id]（actor/ride/skill 用；None＝全部）,
         "choices": [(值, 显示名)]（choice 用）,
         "best": 默认值（可选；离散项的「取最大」落点 —— 没给就退回现值、
                 再退回第一个候选）,
         "rng": (下限, 上限)（int/num 用；界面默认填**上限**，清空＝按规则随机）,
         "rng_fn": f(已挑值 dict) -> (下限, 上限)（int/num 用；区间要**现算**时
                   用它 —— 坐骑移速跟着「坐骑 + 品质」走，见 `ride_speed_rng`）,
         "depends_on": 另一个字段的 key（int/num 可选）,
         "rng_by_type": [(下限, 上限), …]（配 `depends_on` 用：区间随那个字段
                        的取值现算 —— 元宵的「数值」就是跟着「涨哪项资质」走的）}

    ⚠ 这里报出来的**必须是脚本真值**：挑不动的（`进阶石` 的固定 0、`礼盒` 的
      固定五面旗）就不给字段，界面显示「只能按游戏规则重抽」。
    """
    fn = builder_for(name, item_id)
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
    if fn is _ride_egg:
        # 移速是「坐骑 + 品质」派生出来的，区间现算（`rng_fn`），默认填上限。
        # ⚠ kind 必须是 "ride"：坐骑在 Actors 表里但不是召唤兽，走 "actor"
        #   会被召唤兽候选表筛掉（候选 0 项）。
        return "坐骑蛋蛋", [
            {"key": "id", "label": "封印坐骑", "kind": "ride",
             "pool": list(RIDE_IDS), "best": ride_best_id()},
            {"key": "type", "label": "品质", "kind": "choice",
             "choices": [(i, n) for i, n in enumerate(RIDE_QUALITY_NAMES)],
             "best": 2},                       # 默认「神骑」（权重 1/1001 那档）
            {"key": "speed", "label": "移速", "kind": "num",
             "rng_deps": ("id", "type"),       # 区间跟着这两项现算
             "rng_fn": lambda cur: ride_speed_rng(cur.get("id"),
                                                  cur.get("type"))}]
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
        return "元宵", [
            {"key": "type", "label": "涨哪项资质", "kind": "choice",
             "choices": [(i, n) for i, n in enumerate(YUANXIAO_NAMES)]},
            # 涨多少：区间**跟着资质走**（攻/防/速 4~8、体力 20~40、成长 0.01~0.02…），
            # 所以带 `depends_on` + `rng_by_type` 让界面按当前挑的资质现算；
            # 界面默认填区间上限（2026-10-07 川：默认抽最大范围）。
            {"key": "value", "label": "数值", "kind": "num",
             "depends_on": "type", "rng_by_type": YUANXIAO_RANGES}]
    if fn is _yuanxiao_dan:
        return "激进元宵丹", [{"key": "max", "label": "可食用上限",
                               "kind": "int", "rng": (0, 100)}]
    if fn is _navigation_flag:
        return "导航旗", [{"key": "count", "label": "可用次数", "kind": "int",
                           "rng": (1, 600)}]
    if fn is _gift_box:
        return "礼盒", []
    # ---- 2026-10-08 补齐的那批 ----
    if fn is _ruyi:
        return "如意丹", [
            {"key": "type", "label": "属性", "kind": "choice",
             "choices": [(i, n) for i, n in enumerate(GINSENG_NAMES)]},
            {"key": "point", "label": "点数", "kind": "int", "rng": (1, 5)}]
    if fn is _qiankun:
        return "乾坤袋", [{"key": "max", "label": "容量", "kind": "int",
                           "rng": (20, 200)}]
    if fn is _neidan:
        hi = int(item_id) == 134
        lo, top = DAN_HIGH_RANGE if hi else DAN_LOW_RANGE
        return ("高级内丹" if hi else "低级内丹"), [
            {"key": "id", "label": "内丹", "kind": "skill",
             "pool": list(range(lo, top + 1))}]
    if fn is _tiancai:
        return "天材地宝", [
            {"key": "lv", "label": "档位", "kind": "choice",
             "choices": [(i, "%d 档（上限%d）" % (i, v))
                         for i, v in enumerate(TIANCAI_LVS)]},
            {"key": "noup", "label": "已满级", "kind": "choice",
             "choices": [(False, "否"), (True, "是")]}]
    if fn is _shengzhe:
        # ⚠ 它的 `point` 是「几项属性」的**列表**（1~3 项、每项各带区间），
        #   不是单个值 ⇒ 没法做成一个下拉，只能整份重抽。
        return "圣者精气", []
    if fn is _zhanshen:
        # ⚠ 只给「门派」：「门派技能」跟着门派走（每派 3 个），做成两个独立
        #   下拉就能选出「五庄观 + 龙宫技能」这种不合法组合。
        return "战神精气", [
            {"key": "sect", "label": "门派", "kind": "choice",
             "choices": [(k, "门派 %d" % k) for k in sorted(ZHANSHEN_SKILLS)]}]
    if fn is _xianren:
        return "仙人精气", [{"key": "id", "label": "远古技能", "kind": "skill",
                             "pool": list(XIANREN_SKILLS)}]
    if fn is _benyuan:
        # ⚠ 家族名跟写档的 type 符号保持一致（物品名是「本源」、type 是
        #   `:本源精气`），省得界面上两个名字对不上。
        return "本源精气", []
    if fn is _lingshi_book:
        return "灵饰指南书", [
            {"key": "id", "label": "图样编号", "kind": "int",
             "rng": LINGSHI_ID_RANGE},
            {"key": "lv", "label": "等级", "kind": "choice",
             "choices": [(v, str(v)) for v in LINGSHI_LVS]}]
    if fn is _lingstone:
        return "元灵晶石", [{"key": "lv", "label": "等级", "kind": "choice",
                             "choices": [(v, str(v)) for v in LINGSHI_LVS]}]
    if fn is _peach:
        return "蟠桃", [{"key": "year", "label": "年份", "kind": "int",
                         "rng": (100, 6600)}]
    if fn is _fuwen:
        return "符文", [
            {"key": "lv", "label": "等级", "kind": "int",
             "rng": (1, MAX_LEVEL_ACTOR)},
            {"key": "star", "label": "星级", "kind": "int", "rng": (1, 3)}]
    if fn is _canjuan:
        return "上古技能残卷", [{"key": "id", "label": "门派", "kind": "choice",
                                 "choices": [(k, "门派 %d" % k)
                                             for k in SECT_IDS]}]
    if fn is _yinhang:
        return "银票", [{"key": "gold", "label": "金额", "kind": "int",
                         "rng": (0, 100000000)}]
    if fn is _tishenlei:
        return "提神泪", [{"key": "value", "label": "恢复疲劳", "kind": "int",
                           "rng": (1, 2200)}]
    if fn is _dianhua:
        return "点化石", []           # 224 的内容是写死的，没得挑
    if fn is _qian_tree:
        return "摇钱树树苗", []
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
