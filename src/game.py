# -*- coding: utf-8 -*-
"""游戏内容编辑层：金钱 / 背包 / 经验 / 召唤兽 / 防作弊体检。

层级：doctree.py（文档树） → save.py（存档语义） → **game.py（本文）**。

和 `save.SaveDoc` 的分工：
  * `save` 管**存档骨架**（分区、Lock、开关变量、角色基础字段）；
  * 这里管**游戏玩法数据**（背包 4 页×20 格、召唤兽资质、经验、以及游戏的
    `Lock` 校验和 与 `Change` 物品计数校验）。

⚠⚠ **内测版 V2.201 与尝鲜版的防作弊机制差别很大**（2026-10-03 按脚本实测），
   下面第1 类**在 V2.201 里根本不存在**：

1. ~~**周期检查**（`$jiance`，尝鲜版脚本 29455 行起每 300 帧一次）~~ ——
   ⚠ **V2.201 脚本里 `cheated` / `作弊` / `$jiance` 三个关键词全部搜不到**，
   存档里也没有 `@cheated` / `@keyword` 字段、`$game_system.security` 是**空的**。
   ⇒ V2.201 **没有周期检查、没有作弊标记、没有物品记账校验**。
   但**上限常量还在**（`Config::Game`，脚本第 38273-38292 行），只是不再用来判作弊：

   | 常量 | 尝鲜版 | **V2.201** |
   | --- | --- | --- |
   | `MAX_LEVEL_ACTOR` | 60 | **155** |
   | `MAX_LEVEL_BABY` | 65 | **165** |
   | `MAX_GOLD` | 30,000,000 | **9,999,999,999** |
   | `MAX_WAREHOUSE` | [0, 3] | **[0, 12]** |
   | `MAX_BABY_LIFE` | 12000 | **14000** |

   ⇒ 工具的「体检」在 V2.201 上仍按这些上限**提示超限**（有用：超了游戏也不正常），
   但**不再说「会被判作弊」**。上限值已按 V2.201 改到 `fieldnames`。

2. **Lock 校验和**（**两个版本都有**，V2.201 脚本第 867 行）：
   `get_encryption(v) = v * 91 + 45 + seed / 800`（seed = `$game_system.seeds[:shield]`），
   金钱等关键数值被它包着。游戏读的时候会验算，不一致就报错。
   ⇒ 本模块改金钱时自动重算 `@master`。**这是 V2.201 仅存的防作弊**。

3. **物品计数校验**（尝鲜版才有）：游戏给物品记"累计获得数量"，
   存在 `$game_system.security[:items][id]`（`Change` 对象，逐位数字 AES-ECB 加密）。
   ⚠ **V2.201 的 security 是空 HashNode，没这套账** —— 改背包不会被逮到。
   下面的同步逻辑在 V2.201 上是**无害的空操作**，保留是为了两个版本共用一套代码。
"""
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import aes  # noqa: E402
from tables import exp  # noqa: E402   # 升级经验表（游戏脚本里的 $exps，tools/gen_exp_table.py 生成）
import marshal_ruby as M  # noqa: E402
import fieldnames  # noqa: E402
import itemattr  # noqa: E402
from tables import sect  # noqa: E402   # 门派表（游戏脚本里的 $sects，tools/gen_sect_table.py 生成）
from tables import sect_appellation  # noqa: E402   # 门派称谓表（拜师事件里抠的，tools/gen_sect_appellation.py 生成）
from save import _deref, _as_str, ivar, hash_get, hash_put_pairs  # noqa: E402
from tables import baby_aptitude  # noqa: E402   # $baby 表：各池生成值 + 资质硬上限

# 游戏里的上限（**V2.201 实测值**，全部来自脚本 `Config::Game`，见 fieldnames 里的对照表）
MAX_LEVEL_ACTOR = fieldnames.MAX_LEVEL_ACTOR
MAX_LEVEL_BABY = fieldnames.MAX_LEVEL_BABY
MAX_GOLD = fieldnames.MAX_GOLD
# 改金钱一旦超过上限，不压到"贴着上限"，而是压到上限的 5/6：
# 离判定线留出余量，游戏里再正常获得金钱也不会一脚踩过线。
# ⚠ V2.201 的 MAX_GOLD 是 9,999,999,999（尝鲜版 30,000,000）⇒ SAFE_GOLD 约 83 亿。
#   V2.201 实际已无`$jiance` 判作弊（见模块文档），留余量只是为了别贴死上限。
SAFE_GOLD = MAX_GOLD * 5 // 6       # 留 1/6 安全余量
# 「经验拉满」（角色页 / 召唤兽页按钮）写的 @exp 值。
# 演进：2026-10-03 定 5000 万 → 10-07 川「才升到 80 就不够了」→ 50 亿 → 30 亿。
# 用意：等级**不动**，把经验给足，玩家回游戏自己点「升级」（一次一级）。
# ⚠⚠ 30 亿**本身没错**，错的是编码：游戏对 @exp **没有数值上限**，但本作是
#   32 位 Ruby 1.8，Fixnum 只到 **2**30-1 = 1,073,741,823（≈10.74 亿），
#   超过必须落成**大整数 'l'**（`marshal_ruby.encode_integer` 会自动切）。
#   上一轮 `FIXNUM_MAX` 写成 2**31-1，害得 17.18 亿被塞进 4 字节 'i'，
#   加载端 `INT2FIX` 一挤就变成 -429,496,731（川截图）。
# ⚠ 顺带纠正上一轮的"取 2**31-1 的 80% = 17.18 亿"—— **双重错**：
#   ① 编码错（见上）；② 就算编码对了也**不够**：89 级 → 155 级要 **19.95 亿**
#   （89-135 需 4.02 亿、136-154 翻倍后需 15.93 亿，`tables/exp.py` 求和；
#   1→155 累计 20.72 亿）。30 亿升满还剩约 10 亿。
# ⚠ 内测版 V2.201 脚本里 **没有** $jiance / cheated（见 anti_cheat_report 注释），
#   所以"经验给太多被判作弊"这一版不成立。`@limit_exp`（累计获得经验上限
#   202123741）是**另一个**字段，只卡打怪获得的经验，跟这里写 @exp 无关。
ACTOR_EXP_FILL = 3000000000
# 「经验拉满」（召唤兽页按钮）写的 @exp 值 —— 和角色页同源（同一个数）。
# ⚠ 召唤兽和人物**不一样**：`Game_Baby#change_exp`(11277) 里有
#   `level_up(must) while ...` 升级循环，所以写完经验**下一场战斗结算时自己连升**
#   （顶到「主人等级+10」与 MAX_LEVEL_BABY）。等级不变只是"写的那一刻"不变。
#   （召唤兽 1→165 累计只要 1.07 亿，30 亿纯属"给够"。）
BABY_EXP_FILL = 3000000000
MAX_ITEM = fieldnames.MAX_ITEM
#: 仓库页号上限。**V2.201 是 12**（`Config::Game::MAX_WAREHOUSE = [0, 12]`），
#: 尝鲜版只有 3 —— 沿用旧值会把合法的 4~12 页当成超限去"修"。
MAX_WAREHOUSE_PAGE = fieldnames.MAX_WAREHOUSE
MAX_BABY_LIFE = fieldnames.MAX_BABY_LIFE
MAX_BABY_LOYALTY = fieldnames.MAX_BABY_LOYALTY
#: 低于它不能参战（`Config::Baby::ALLOW_LOYALTY`）—— 和 100 那个上限是两回事
BABY_ALLOW_LOYALTY = fieldnames.BABY_ALLOW_LOYALTY
#: 召唤兽五行的全部合法值（唯一来源 `fieldnames.BABY_FIVE`）
BABY_FIVE = fieldnames.BABY_FIVE
MAX_PACK_PAGE = fieldnames.PACK_PAGES
PACK_PAGE_SIZE = fieldnames.PACK_PAGE_SIZE

KINDS = (("Items", "@items", "道具", "Items"),
         ("Weapons", "@weapons", "武器", "Weapons"),
         ("Armors", "@armors", "防具", "Armors"))

#: 「位置」= 背包 / 仓库（2026-10-08 川：背包可切换成仓库）。
#:
#: ⚠ 探针实测（`!tmp/probe_warehouse.py`，真档副本）：**背包只有一个容器** ——
#:   `@items` 这个 `Hash{槽号 => [对象, 数量]}` 里**混装**道具/武器/防具，游戏自己按
#:   `is_a?(RPG::Item/Weapon/Armor)` 分流（脚本 `def weapons; @items.sort.select{…}`）。
#:   上面 `KINDS` 里的 `@weapons`/`@armors` 是**遗留空容器**（真档 0 对）
#:   ⇒ 界面的「种类」不能再切容器，只能对 `@items` 做**类过滤**（`CLASS_ONLY`）。
#:   仓库＝`$game_party.hash[:warehouse]`，形状与背包装的一模一样，页数看
#:   `hash[:warehouse_page]`（**已开页数**，上限 12 + 会员 3/5）。
SRCS = (("pack", "背包"), ("warehouse", "仓库"))

#: 「筛选」＝按物件类过滤（键 → 中文）。
CLASS_ONLY = (("all", "全部"), ("item", "道具"),
              ("weapon", "武器"), ("armor", "防具"))
_CLS_ONLY = {"RPG::Item": "item", "RPG::Weapon": "weapon", "RPG::Armor": "armor"}

#: 每格数量上限，照游戏 `Game_Party#max_item_number`（script00:14440）——
#: 默认 `Config::Game::MAX_ITEM`（99），下面这些 id 是特例。
MAX_ITEM_BY_ID = {2: 9999, 3: 9999,        # 包子 / 佛手
                  115: 9999, 116: 9999,     # 金锭 / 仙丹
                  63: 999, 273: 999,        # 飞行符 / 天眼通符
                  145: 500,
                  146: 999, 147: 999,       # 锻造灵石 / 锻造晶石
                  158: 9999}

#: 仓库页数上限（工具不判会员，按脚本 `max_warehouse` 的最大值 12+3+5=20 兜着）。
MAX_WAREHOUSE_PAGES = 20

# --------------------------------------------------------------------------
# 修炼（`Game_Actor#@sect_data[:修炼]`，8 项）
#
# 2026-10-08 逐条对过内测版 V2.201 脚本（`script00_00000020.rb`）与尝鲜版
# （`0000_000015.rb`），**两版差别不小**，别照抄尝鲜版：
#   * 8 项**全在人物身上**：`A_*` = 人物修炼、`B_*` = 召唤兽修炼。
#     召唤兽对象自己**没有** `@sect_data` —— 战斗里走
#     `宝宝.master.sect_data[:修炼][:B_攻击][:lv]`（`master` 是主人＝人物）。
#   * **升级不改属性**：`@attr`（体质/力量那套加点）与修炼毫无关系。
#     全部 17 处引用都在**战斗结算**里实时读 `[:lv]` ⇒ 改等级立即生效，
#     不用重算任何字段（`exp` 只是"距离下一级的进度"，与战斗无关）。
#   * 上限：`level < 90 ? 20 : Config::Game::MAX_XIULIAN_LEVEL`（**25**）。
#     ⚠ 战斗读 lv 时**不校验上限** ⇒ 写 25 也照生效，只是游戏界面显示「25/20」。
#   * 门槛：`practice_next_level_exp(lv) = (lv² + 3lv + 11) × 10`
#     （0→1 要 110 点，20→21 要 4710 点；每次点修炼只 +10 点、一次只升 1 级）。
#   * 每级加成（`v` = 结算前伤害，`chance` = 封印几率）：
#       攻击/防御/法术/法防：伤害 / 减伤  `±(v*0.02 + 5) * lv`
#       攻击：命中 `目标闪避 -= 0.005 * lv`（即每级 +0.5% 命中）
#       法术：抗封 `chance -= lv * 0.02`；治疗 `回复 += 基础回复 * lv * 0.02`
#       法防：封印命中 `chance += lv * 0.012`
# --------------------------------------------------------------------------
#: 组内 4 项的顺序（和游戏「修炼」界面两栏的排布一致）
PRACTICE_NAMES = ("攻击", "法术", "防御", "法防")
#: 两组：A = 人物修炼、B = 召唤兽修炼
PRACTICE_GROUPS = (("A", "人物修炼"), ("B", "召唤兽修炼"))
#: 每项的战斗作用（给界面当说明用，系数都从脚本里抄的）
PRACTICE_DESC = {
    "攻击": "物理伤害 +2%/级（另加 5 点/级），命中 +0.5%/级",
    "法术": "法术伤害与治疗量 +2%/级，被封印几率 -2%/级",
    "防御": "受到的物理伤害 -2%/级（再减 5 点/级）",
    "法防": "受到的法术伤害 -2%/级（再减 5 点/级），封印命中 +1.2%/级",
}
#: 修炼等级上限（角色 ≥90 级时；<90 级只有 20）
PRACTICE_MAX_LV = 25
PRACTICE_LV_BELOW_90 = 20
#: 「全员拉满」跳过的角色 —— 按 **模板 id**（`@actor_id`）判，不按名字：
#  id 6 = 巨小蛙（2026-10-08 川指定）。真档里它是 60 级的剧情角色，跟 5 个
#  主力（89 级）不是一路，拉满会把它顶到 25 级。按 id 判才不怕改名/重名。
PRACTICE_SKIP_IDS = (6,)


# --------------------------------------------------------------------------
# 节点小工具
# --------------------------------------------------------------------------
def clone_node(node):
    """深拷贝一棵子树（把 '@N' 链接全部展开成独立副本，再重新解析）。"""
    data = M.serialize(node, table=None)
    return M.parse_stream(b"\x04\x08" + data)[-1]["node"]


def int_node(value):
    return M.IntNode(int(value))


def str_node(text):
    """带 `:E => true` 的字符串（游戏里字符串都是这么存的）。"""
    inner = M.StrNode(text.encode("utf-8"))
    wrap = M.IVarNode()
    wrap.inner = inner
    wrap.ivars = [("E", M.BoolNode(True))]
    return wrap


def hex_str_node(hexstr):
    """`Change.@value` 里那种"二进制编码的十六进制串"。"""
    inner = M.StrNode(hexstr.encode("ascii"))
    wrap = M.IVarNode()
    wrap.inner = inner
    wrap.ivars = [("E", M.BoolNode(True))]
    return wrap


def nil_node():
    return M.NilNode()


def exp_for_level(level, kind="actor"):
    """升到下一级所需的经验 —— **查表**（游戏脚本里的 `$exps`），不是公式算的。

    游戏脚本：
        def exp_for_level(lv)  = $exps[:actor][lv - 1]
        def next_level_exp     = exp_for_level(@level + 1) == $exps[:actor][@level]
    所以**下标就是当前等级**：40 级 → `ACTOR_EXP[40]`（= 332296，和游戏里显示的一致）。

    ⚠ 别拿 `@limit_exp` 当升级所需经验，那是「累计获得经验」的计数器。

    kind: "actor"（角色）/ "baby"（召唤兽）。越界（满级 / 等级异常）返回 None。
    """
    tbl = exp.BABY_EXP if kind == "baby" else exp.ACTOR_EXP
    try:
        lv = int(level)
    except (TypeError, ValueError):
        return None
    if lv < 0 or lv >= len(tbl):
        return None
    return tbl[lv]


def get_int(node, default=0):
    v = M.value_of(_deref(node))
    try:
        return default if v is None else int(v)
    except (TypeError, ValueError):
        # 寿命这种字段可能是符号 `:infinite`（神兽永生）
        return default


def get_float(node, default=0.0):
    v = M.value_of(_deref(node))
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def is_ruby_false(value):
    """这个值在 Ruby 里算不算“假”？

    Ruby 只有 `false` 和 `nil` 是假值 —— **整数 0 是真值**。
    所以判断 `@cheated` 这类开关时不能只写 `bool(value)`：
    曾经把 false 写成整数 0，游戏 `if $game_system.cheated` 照样成立，
    20 分钟后还是开始惩罚（画面转圈），25 分钟后弹「存档异常」退出。
    """
    return value is False or value is None


def set_ivar(obj, name, node):
    """替换对象的某个 ivar 的值节点（保持位置）。

    ⚠ **传进来的值若是 `'@N'` 链接，必须先展开成对象再存**：链接里记的是
    **解析那一刻**的编号，一旦周围对象增删（编号整体重排）就会指到别的对象上。
    2026-10-04 的翻车：`babies.set_active()` 传了 `@babys[index]`（常常就是个
    `'@N'` 链接）→ 写回去的 `@baby` 变成**整个数组**，游戏进图第一帧
    `Game_Party#battle_members` 的 `b.exist?` 直接
    `NoMethodError: undefined method 'exist?' for #<Array>`。
    展开后拿到的是**对象本身**，序列化器按对象身份发链接，不会再错位。

    ⚠ 这里**只展开 `'@N'` 链接**，不走 `_deref`（`_deref` 还会顺手拆掉
    `I "…" { :E => true }` 那层编码包装 —— 那是 Ruby 1.9 非 ASCII 字符串的
    UTF-8 标记，拆了游戏读出来就是乱码，`hex_str_node()` 那种值尤其碰不得）。
    """
    obj = _deref(obj)
    _n = 0
    while isinstance(node, M.LinkNode) and node.target is not None and _n < 8:
        node = node.target
        _n += 1
    for i, (k, _v) in enumerate(obj.ivars):
        if k == name:
            obj.ivars[i] = (k, node)
            return True
    return False


def ensure_ivar(obj, name, node):
    """替换**或追加**对象的 ivar（追加到末尾），返回是否成功。

    `set_ivar` 只认已有的键 —— 老档里的召唤兽**普遍没有** `@attr.@promote`
    （`Game_Baby_Attr#initialize` 压根不写它，只有用进阶道具时才 `attr.promote = true`
    追加到末尾）。要让「进阶」按钮真的写进去，就得能追加。

    追加的是**符号名 + 标量值**（不新增对象），所以 `@N` 的对象编号不会挪位。
    顺序也跟游戏一致：落在 `@attr` 的最后一个 ivar。
    """
    obj = _deref(obj)
    if obj is None:
        return False
    iv = getattr(obj, "ivars", None)
    if iv is None:
        return False
    if set_ivar(obj, name, node):
        return True
    iv.append((name, node))
    return True


class GameEditor(object):
    """针对一份 SaveDoc 的游戏数据编辑。"""

    def __init__(self, sv):
        self.sv = sv
        self.doc = sv.doc

    # ==================================================== 金钱 / 上限
    def set_gold(self, value):
        """改金钱的统一入口（界面层都该走这里，而不是直接 sv.set_gold）。

        三件事一次做齐，缺一个都会被游戏判作弊：
          1. 超过 MAX_GOLD（9,999,999,999）→ 自动改成 SAFE_GOLD（上限的 5/6，
             留安全余量），返回 (实际写入值, 是否被钳)；
          2. sv.set_gold 同步 Lock 的 @master 校验和；
          3. sync_gold_security 把游戏的金钱账 security[:gold] 对齐 ——
             以前只做了第 2 步，游戏里一花钱/赚钱就因账实不符被记 'NE!'。
        """
        value = int(value)
        clamped = False
        if value > MAX_GOLD:
            value = SAFE_GOLD
            clamped = True
        self.sv.set_gold(value)
        self.sync_gold_security()
        return value, clamped

    def limit_gold(self):
        return get_int(ivar(self.sv.section("party"), "@limit_gold"))

    def set_limit_gold(self, value):
        node = _deref(ivar(self.sv.section("party"), "@limit_gold"))
        if node is None:
            raise KeyError("存档里没有 @limit_gold")
        self.doc.set_value(node, int(value))
        return int(value)

    def warehouse_page(self):
        h = self._hash()
        return get_int(hash_get(h, "warehouse_page"))

    def set_warehouse_page(self, value):
        h = self._hash()
        node = _deref(hash_get(h, "warehouse_page"))
        if node is None:
            raise KeyError("没有 warehouse_page")
        self.doc.set_value(node, int(value))

    # ==================================================== 祈福池
    # 祈福池窗口里 4 个储备量，存在 $game_party.hash 里（符号键）：
    # 左键物品加人物储备(actor_*)，右键加宠物储备(baby_*)。
    # 这 4 个值不在游戏防作弊检查范围内，直接写即可。
    BLESSING_KEYS = (
        ("actor_hp_pool", "角色气血储备"),
        ("actor_mp_pool", "角色魔法储备"),
        ("baby_hp_pool", "宠物气血储备"),
        ("baby_mp_pool", "宠物魔法储备"),
    )

    def blessing_rows(self):
        """祈福池 4 个储备量：[(key, 显示名, 当前值), ...]。"""
        h = self._hash()
        return [(key, cn, get_int(hash_get(h, key)))
                for key, cn in self.BLESSING_KEYS]

    def set_blessing(self, key, value):
        """改某个祈福池储备量（负数钳 0），返回实际写入值。"""
        h = self._hash()
        node = _deref(hash_get(h, key))
        if node is None:
            raise KeyError("祈福池字段不存在：%s" % key)
        value = max(0, int(value))
        self.doc.set_value(node, value)
        return value

    def _hash(self):
        """$game_party.hash（Key 是符号，这里用字符串键取）。"""
        return _deref(ivar(self.sv.section("party"), "@hash"))

    # ==================================================== 背包
    def container(self, kind="Items"):
        """返回容器 HashNode（key = 槽号，value = [对象, 数量]）。

        `kind` 可以是老的三种（`Items`/`Weapons`/`Armors`），也可以是
        `"pack"`（＝`@items`）与 `"warehouse"`（＝`hash[:warehouse]`）——
        后两个就是界面上「位置」那个下拉的两个值，语义层里形状完全一样。
        """
        if kind == "pack":
            kind = "Items"
        elif kind == "warehouse":
            node = self.warehouse_hash(create=True)
            if node is None:
                raise KeyError("存档里没有 party.hash[:warehouse]")
            return node
        for key, ivname, _cn, _db in KINDS:
            if key == kind:
                node = _deref(ivar(self.sv.section("party"), ivname))
                if isinstance(node, M.HashNode):
                    return node
                raise KeyError("存档里没有 %s" % ivname)
        raise KeyError("不认识的背包类型 %r" % kind)

    def warehouse_hash(self, create=False):
        """仓库容器 `$game_party.hash[:warehouse]`（`Hash{槽号 => [对象, 数量]}`）。

        脚本里 `def warehouse; $game_party.hash[:warehouse]; end`（15318）；
        ⚠ 它跟背包是**同一个形状**，只是**页数**看 `hash[:warehouse_page]`
        （已开页数）—— 所以工具里两边可以共用一整套读写。
        `create=True` 时（键不存在/为 nil）就地建一个空 Hash 写回去：
        游戏自己 `initialize` 里也有这一键（`warehouse: {}`，14073）。
        """
        ph = self._hash()
        if not isinstance(ph, M.HashNode):
            return None
        h = _deref(hash_get(ph, "warehouse"))
        if isinstance(h, M.HashNode):
            return h
        if not create:
            return None
        node = M.HashNode([])
        for i, (k, v) in enumerate(ph.pairs):
            if M.value_of(_deref(k)) == "warehouse":
                ph.pairs[i] = (k, node)
                break
        else:
            ph.pairs.append((str_node("warehouse"), node))
        self.doc.mark_structural()
        return node

    def page_count(self, kind="Items"):
        """这个容器有几页（1 页 = `PACK_PAGE_SIZE` 格）。

        背包恒 `MAX_PACK_PAGE`(4)；仓库看存档里的 `hash[:warehouse_page]`
        （已开页数，脚本 `get_maxpage`: `min(warehouse_page, max_warehouse)`）。
        """
        if kind != "warehouse":
            return MAX_PACK_PAGE
        n = self.warehouse_page() or 0
        return max(1, min(int(n), MAX_WAREHOUSE_PAGES))

    def item_class(self, node):
        """物件类 → 筛选键（`"item"`/`"weapon"`/`"armor"`），认不出给 `None`。"""
        return _CLS_ONLY.get(getattr(_deref(node), "cls", ""))

    def slot_key(self, page, index):
        return page * PACK_PAGE_SIZE + index

    def _pair_index(self, h, slot):
        for i, (k, _v) in enumerate(h.pairs):
            if M.value_of(_deref(k)) == slot:
                return i
        return -1

    def bag(self, kind="Items", page=None, only=None):
        """背包/仓库内容：[(槽号, 翻页, 页内格, id, 名称, 数量), ...]，空槽不列。

        page=None 表示整本，给了 page 就只看那一页。
        名称按**物件自己的类**选表（一个容器里混装着道具/武器/防具）。
        `only` 是**类过滤**（`"item"`/`"weapon"`/`"armor"`）—— 界面的「筛选」
        下拉用它；⚠ 因为它过滤的是同一个 `@items`，所以别再用老 `KINDS`
        那三个容器去切（`@weapons`/`@armors` 是 0 对的遗留字段）。
        """
        h = self.container(kind)
        out = []
        for k, v in h.pairs:
            slot = M.value_of(_deref(k))
            if not isinstance(slot, int):
                continue
            p, idx = divmod(slot, PACK_PAGE_SIZE)
            if page is not None and p != page:
                continue
            arr = _deref(v)
            if not isinstance(arr, M.ArrayNode) or not arr.items:
                continue
            item = _deref(arr.items[0])
            if only and only != "all" and self.item_class(item) != only:
                continue
            iid = get_int(ivar(item, "@id"), -1) if item is not None else -1
            nm = self.item_display_name(item, "?") if item is not None else "?"
            count = get_int(arr.items[1]) if len(arr.items) > 1 else 1
            out.append((slot, p, idx, iid, nm, count))
        out.sort()
        return out

    def templates(self, kind="Items", keyword=None, limit=500):
        """物品模板表：[(id, 名称, 说明), ...]（从 Data\\<kind>.rvdata2 读）。

        仿画迹1：右边一个可搜索的模板列表，选中后写进背包格子。

        **只列"真物品"**（2026-10-04 川：物品管理里别出现纯编号的东西）——走
        `datatables.item_map()`，它已经滤掉两类噪音：分段行（`===药品===`）和
        空名空说明的占位行（界面上会显示成 `#49`，选中还会把 id 写进背包）。
        说明里还会接上备注能翻成人话的那几行（等级 / 售价 / 使用限制…）。

        读不到游戏目录时退回**内置名字表**（只有 id/名字/说明）——列表还能用，
        只是「克隆整件物品」那条路（`make_item`）仍需要 Data，另见那里的提示。
        """
        import datatables
        kw = (keyword or "").strip().lower()
        try:
            m = datatables.item_map(self._db_of(kind))
            rows = [(i, m[i][0] or ("#%d" % i), m[i][1]) for i in sorted(m)]
        except Exception:
            rows = []
        if not rows:
            rows = datatables.builtin_rows(self._db_of(kind))
        out = []
        for i, nm, desc in rows:
            desc = (desc or "").strip().replace("\r\n", "\n")
            if kw and kw not in nm.lower() and kw not in str(i) \
                    and kw not in desc.lower():
                continue
            out.append((i, nm, desc))
            if len(out) >= limit:
                break
        return out

    def group_map(self, kind="Items"):
        """`{物品 id: 表里的段名}` —— 模板列表的「类别」列用（`===药品===` /
        `======剑=======` 那一层，口径见 `datatables.item_group()`）。"""
        import datatables
        try:
            return datatables.item_group(self._db_of(kind))
        except Exception:
            return {}

    def set_all_counts(self, kind="Items", count=99, page=None):
        """把（某一页/整本）已有的格子数量批量改成 count（仿画迹1 的批量改）。

        ⚠ 这里**不预先夹**到 `MAX_ITEM` —— 每件东西自己的上限不同
        （包子 9999、飞行符 999…），交给 `set_count` 按 `stack_limit` 夹。
        """
        count = max(0, int(count))
        n = 0
        for slot, _p, _i, iid, _nm, cur in self.bag(kind, page):
            if cur == count:
                continue
            self.set_count(kind, slot, count)
            n += 1
        return n

    def pack_report(self, kinds=None):
        """背包体检（仿画迹1 的 pack_scan_bad）。

        返回 [(kind, 槽号, 名称, 问题, 能否修, extra), ...]，extra 里带上修复要用到的
        附加信息（比如重复格子指向哪个槽）。检查项：

          * 格子号不是整数（数据坏了）
          * 值不是 `[物品, 数量]`（结构不对）
          * 只有数量没有物品对象
          * 物品 id 在 `Data\\<kind>.rvdata2` 里查不到
          * 数量是 0 / 超过单格上限 99
          * 同一件东西占了多个格子（游戏按 id 取数量，重复会算不清）
        """
        out = []
        # ⚠ 仓库（`"warehouse"`）与背包共用同一张名字表（都是 Items 那一个容器）
        #   —— `_db_of` 负责把这层差异抹平。
        kinds_all = list(KINDS) + [("warehouse", None, "仓库", "Items")]
        for key, _iv, cn, db in kinds_all:
            if kinds and key not in kinds:
                continue
            try:
                h = self.container(key)
            except KeyError:
                continue
            names = self._name_map(key)
            seen = {}
            for k, v in h.pairs:
                slot = M.value_of(_deref(k))
                if not isinstance(slot, int):
                    out.append((key, slot, cn, "格子号不是整数（%r）"
                                % (slot,), True, {}))
                    continue
                arr = _deref(v)
                if arr is None or isinstance(arr, M.NilNode):
                    continue
                if not isinstance(arr, M.ArrayNode) or not arr.items:
                    out.append((key, slot, cn, "结构不对（不是 [物品, 数量]）",
                                True, {}))
                    continue
                item = _deref(arr.items[0])
                if item is None or isinstance(item, M.NilNode):
                    out.append((key, slot, "（空）", "只有数量、没有物品对象",
                                True, {}))
                    continue
                iid = get_int(ivar(item, "@id"), -1)
                cnt = get_int(arr.items[1]) if len(arr.items) > 1 else 1
                nm = names.get(iid) or ("id=%d" % iid)
                if iid < 0 or names.get(iid) is None:
                    out.append((key, slot, nm,
                                "物品 id=%s 在 %s.rvdata2 里不存在" % (iid, db),
                                True, {"id": iid}))
                if cnt <= 0:
                    out.append((key, slot, nm, "数量是 %d" % cnt, True,
                                {"id": iid, "count": cnt}))
                else:
                    lim = self.stack_limit(item)
                    if cnt > lim:
                        out.append((key, slot, nm, "数量 %d 超过单格上限 %d"
                                    % (cnt, lim), True,
                                    {"id": iid, "count": cnt}))
                if iid in seen:
                    out.append((key, slot, nm, "和 %d 号格子重复（同一物品占两格）"
                                % seen[iid], True,
                                {"id": iid, "count": cnt, "dup_of": seen[iid]}))
                else:
                    seen[iid] = slot
                # 孵化蛋/礼包这类“运行时才填内容”的东西：@attr 空的话一用就报
                # `undefined method '[]' for nil:NilClass`
                need_pay, _nm = self.item_needs_payload(self._db_of(key), iid)
                if need_pay:
                    pt, _pd = self.item_payload(item)
                    if not pt:
                        out.append((key, slot, nm,
                                    "缺“运行时内容”（@attr 是空的）——"
                                    "游戏里一用就报 NoMethodError",
                                    True, {"id": iid, "payload": True}))
                    elif not self.payload_key_ok(item):
                        out.append((key, slot, nm,
                                    "运行时内容的键写成了符号（老版本工具的写法）"
                                    "——游戏只认字符串键 \"data\"，所以游戏里读不到",
                                    True, {"id": iid, "payload": True}))
        return out

    def pack_fix(self, rows=None):
        """按体检结果修（仿画迹1 的 pack_fix_all）：

          * 重复格子 → 把数量并到前一个格子，再清掉这一格
          * 数量 0 / 结构坏 / id 无效 → 清空那一格
          * 数量超上限 → 截断到 99
        返回 [(kind, slot, 修了什么), ...]。
        """
        rows = rows if rows is not None else self.pack_report()
        done = []
        for row in rows:
            kind, slot, name, why, _fix, extra = row
            if not isinstance(slot, int):
                continue
            if extra.get("payload"):
                it = self._item_node(kind, slot)
                if it is None:
                    continue
                before, _b = self.item_payload(it)
                self._fix_payload(it, self._db_of(kind), extra.get("id", -1))
                after, _a = self.item_payload(it)
                if after and not before:
                    self.doc.mark_structural()
                    done.append((kind, slot, "%s 补上了运行时内容（%s）"
                                 % (name, after)))
                continue
            cnt = extra.get("count")
            if extra.get("dup_of") is not None:
                keep = extra["dup_of"]
                cur = dict((s, c) for s, _p, _i, _id, _n, c in self.bag(kind))
                total = cur.get(keep, 0) + (cnt or 0)
                _it = self._item_node(kind, keep)
                _lim = self.stack_limit(_it) if _it is not None else MAX_ITEM
                if total > _lim:              # 上限就留一格（包子 9999 / 默认 99）
                    total = _lim
                self.set_count(kind, keep, total)
                self.clear_slot(kind, slot)
                done.append((kind, slot, "%s 并到 %d 号格子（现在 %d 个）"
                             % (name, keep, total)))
                continue
            if "超过" in why:
                _it = self._item_node(kind, slot)
                self.set_count(kind, slot,
                               self.stack_limit(_it) if _it is not None
                               else MAX_ITEM)
                done.append((kind, slot, "%s 数量 %s → %d"
                             % (name, cnt, MAX_ITEM)))
                continue
            if self.clear_slot(kind, slot):
                done.append((kind, slot, "%s 已清空（%s）" % (name, why)))
        if done:
            self.resync_security()
        return done

    # ==================================================== 机器码（存档绑定）
    def config_hash(self):
        """`$game_system.config`（Hash）。"""
        return _deref(ivar(self.sv.section("system"), "@config"))

    def machine_ids(self):
        """存档里记录的机器码列表（`config[:hard_disk_code]`，是个数组）。

        游戏启动时会 `include?(current)` 比对，不在里面就 msgbox “存档异常”。
        所以换机器玩的话，把新机器码加进去就行。
        """
        arr = _deref(hash_get(self.config_hash(), "hard_disk_code"))
        out = []
        if isinstance(arr, M.ArrayNode):
            for x in arr.items:
                s = _as_str(x)
                if s is not None:
                    out.append(str(s))
        return out

    def _machine_array(self, create=True):
        h = self.config_hash()
        if not isinstance(h, M.HashNode):
            raise KeyError("存档里没有 $game_system.config")
        arr = _deref(hash_get(h, "hard_disk_code"))
        if isinstance(arr, M.ArrayNode):
            return arr
        if not create:
            return None
        arr = M.ArrayNode([])
        for i, (k, v) in enumerate(h.pairs):
            if M.value_of(k) == "hard_disk_code":
                h.pairs[i] = (k, arr)
                return arr
        h.pairs.append((M.SymbolNode("hard_disk_code"), arr))
        return arr

    def set_machine_ids(self, ids):
        """整组替换（结构性改动）。"""
        arr = self._machine_array()
        arr.items = [str_node(str(x)) for x in ids if str(x).strip()]
        self.doc.mark_structural()
        return self.machine_ids()

    def add_machine_id(self, mid):
        """追加一个机器码（已存在就不动）——换机器时最安全的做法。"""
        mid = str(mid).strip()
        if not mid:
            raise ValueError("机器码是空的")
        have = self.machine_ids()
        if mid in have:
            return have
        arr = self._machine_array()
        arr.items.append(str_node(mid))
        self.doc.mark_structural()
        return self.machine_ids()

    def machine_id_now(self, refresh=False):
        """本机机器码（调 main.dll!get_hard_disk_character）。

        进程内会记住结果（起 exe 约 0.3s）；`refresh=True` 强制重读。
        """
        import codec
        return codec.try_machine_id(refresh=refresh)

    def machine_status(self, refresh=False):
        """返回 (本机机器码 或 None, 出错原因, 存档记录列表, 本机是否在档)。"""
        now, err = self.machine_id_now(refresh=refresh)
        ids = self.machine_ids()
        return now, err, ids, bool(now and now in ids)

    def empty_slots(self, kind="Items", page=None):
        """空槽号：键是整数槽号、值**有货**的才算占用（置 nil 的槽当空的）。

        和 `bag()` / 游戏 `has_vacancy?` 一致 —— 被「清空」的格子还能再装东西。
        """
        h = self.container(kind)
        used = set()
        for k, v in h.pairs:
            slot = M.value_of(_deref(k))
            if isinstance(slot, int):
                arr = _deref(v)
                if isinstance(arr, M.ArrayNode) and arr.items:
                    used.add(slot)
        pages = [page] if page is not None else range(self.page_count(kind))
        out = []
        for p in pages:
            for i in range(PACK_PAGE_SIZE):
                s = self.slot_key(p, i)
                if s not in used:
                    out.append(s)
        return out

    def _name_map(self, kind):
        import datatables
        try:
            return datatables.name_map(self._db_of(kind))
        except Exception:
            return {}

    #: 存档里的物件类名 → Data 表
    CLASS_TO_DB = {"RPG::Item": "Items", "RPG::Weapon": "Weapons",
                   "RPG::Armor": "Armors"}

    def item_display_name(self, node, fallback=None):
        """一个背包物件的显示名。

        关键：**背包里混装三种对象**（道具/武器/防具，召唤兽装备也是武器防具），
        所以不能拿容器的名字表去查 —— 得按对象自己的类选表：
        `RPG::Weapon` → Weapons.rvdata2、`RPG::Armor` → Armors.rvdata2 ……
        依次降级：类对应的表 → 对象自带的 @name → 三张表都试 → fallback。
        """
        n = _deref(node)
        if n is None:
            return fallback
        iid = get_int(ivar(n, "@id"), -1)
        cls = getattr(n, "cls", "") or ""
        keys = []
        if cls in self.CLASS_TO_DB:
            keys.append(self.CLASS_TO_DB[cls])
        keys += [k for k in ("Items", "Weapons", "Armors") if k not in keys]
        for k in keys:
            nm = self._name_map(k).get(iid)
            if nm:
                return nm
        own = _as_str(ivar(n, "@name"))
        return own or fallback

    def item_name(self, kind, item_id):
        return self._name_map(kind).get(item_id, "?")

    def _desc_map(self, kind):
        """Data 表的 {id: (名称, 完整说明)}（懒加载缓存，悬浮提示用）。

        走 `datatables.item_map()`：说明带上备注那几行（等级 / 售价 / 使用限制…），
        并且滤掉了分段行与空占位行（那些行本来也没有说明）。读不到游戏目录时
        它会退回内置表，所以这里不用再兜一次。
        """
        if not getattr(self, "_desc_cache", None):
            self._desc_cache = {}
        if kind not in self._desc_cache:
            import datatables
            m = {}
            try:
                pairs = datatables.item_map(self._db_of(kind))
            except Exception:
                pairs = {}
            for i, (nm, desc) in pairs.items():
                m[i] = (nm or ("#%d" % i), (desc or "").strip())
            self._desc_cache[kind] = m
        return self._desc_cache[kind]

    def item_description(self, node):
        """背包物件的完整说明（按对象自己的类选 Items/Weapons/Armors 表，
        选表逻辑与 item_display_name 一致；查不到再退回对象自带 @description）。"""
        n = _deref(node)
        if n is None:
            return ""
        iid = get_int(ivar(n, "@id"), -1)
        cls = getattr(n, "cls", "") or ""
        keys = []
        if cls in self.CLASS_TO_DB:
            keys.append(self.CLASS_TO_DB[cls])
        keys += [k for k in ("Items", "Weapons", "Armors") if k not in keys]
        for k in keys:
            pair = self._desc_map(k).get(iid)
            if pair and pair[1]:
                return pair[1]
        # 兜底：对象自带的 @description 也可能带字面 `\n` / 裸 `\r`
        # （表里两种写法混着用），统一过一遍 clean_desc 再显示。
        import datatables
        return datatables.clean_desc(
            _as_str(ivar(n, "@description")) or "").strip()

    def set_count(self, kind, slot, count):
        """改某一格的数量（标量改动，安全）+ 同步物品计数校验。"""
        h = self.container(kind)
        i = self._pair_index(h, slot)
        if i < 0:
            raise KeyError("第 %d 格是空的" % slot)
        arr = _deref(h.pairs[i][1])
        if not isinstance(arr, M.ArrayNode) or len(arr.items) < 2:
            raise KeyError("第 %d 格结构不对" % slot)
        item = _deref(arr.items[0])
        iid = get_int(ivar(item, "@id"), -1)
        # 上限照游戏 `max_item_number`（包子 9999 / 飞行符 999 / 默认 99）。
        count = max(0, min(int(count), self.stack_limit(item)))
        self.doc.set_value(_deref(arr.items[1]), count)
        if self._is_sec_kind(kind):
            self.sync_security_item(iid)
        return count

    def clear_slot(self, kind, slot):
        """清空格子（把值置 nil，游戏就当它空的；不需要删对象）。

        置 nil 后游戏自己的 `has_vacancy?` 就会把这个槽当空的，
        而且不减少对象个数 —— 少踩一个“编号错位”的坑。
        """
        h = self.container(kind)
        i = self._pair_index(h, slot)
        if i < 0:
            return False
        arr = _deref(h.pairs[i][1])
        iid = -1
        if isinstance(arr, M.ArrayNode) and arr.items:
            iid = get_int(ivar(_deref(arr.items[0]), "@id"), -1)
        h.pairs[i] = (h.pairs[i][0], nil_node())
        self.doc.mark_structural()
        if self._is_sec_kind(kind) and iid >= 0:
            self.sync_security_item(iid)
        return True

    def add_item(self, kind, slot, item_id, count=1, kid=None, clone_like=True,
                 db=None):
        """往空格子里加一件物品（结构性改动）。

        优先克隆**存档里同款**（带运行时内容）；没有才用 Data 模板新建。
        只允许往**空槽**加：这样不会覆盖玩家已有的东西。

        `db` ＝从哪张 Data 表取模板（默认按容器推断 → 都是 `Items`）。
        界面上「筛选」选了武器/防具时要显式传 `db="Weapons"`，否则拿武器 id
        去 Items 表里找必然找不到。
        """
        db = db or self._db_of(kind)
        h = self.container(kind)
        if self._pair_index(h, slot) >= 0:
            arr = _deref(h.pairs[self._pair_index(h, slot)][1])
            if isinstance(arr, M.ArrayNode) and arr.items:
                raise ValueError("第 %d 格已经有东西了" % slot)
        like = self.find_like(db, item_id) if clone_like else None
        node = self.make_item(db, item_id, kid=kid, like=like)
        arr = M.ArrayNode([node, int_node(count)])
        i = self._pair_index(h, slot)
        key = int_node(slot)
        if i >= 0:
            h.pairs[i] = (h.pairs[i][0], arr)
        else:
            pos = len(h.pairs)
            for j, (k, _v) in enumerate(h.pairs):
                kv = M.value_of(_deref(k))
                if isinstance(kv, int) and kv > slot:
                    pos = j
                    break
            h.pairs.insert(pos, (key, arr))
        if self._is_sec_kind(kind):
            self.sync_security_item(item_id)
        self.doc.mark_structural()
        return node

    def slot_info(self, kind, slot):
        """某一格的内容：`(物品id, 数量)`；空格/坏格返回 None。"""
        for s, _p, _i, iid, _nm, cnt in self.bag(kind):
            if s == slot:
                return (iid, cnt)
        return None

    def set_item(self, kind, slot, item_id, count=None, kid=None,
                 clone_like=True, db=None):
        """把某一格**换成**另一件物品（从 Data 模板新建对象，仿画迹1 的"写入槽位"）。

        count=None 表示沿用原来那一格的数量（原来是空的就是 1）。
        这是结构性改动（保存时会整档重写），并且会自动同步物品计数校验。
        `db` ＝模板表（默认按容器推断）。⚠ 改前先确认能造出来，别改到一半失败。
        """
        db = db or self._db_of(kind)
        old = self.slot_info(kind, slot)
        if count is None:
            count = old[1] if old else 1
        count = max(0, min(int(count), MAX_ITEM))
        try:
            self.make_item(db, item_id, kid=kid,
                           like=self.find_like(db, item_id) if clone_like
                           else None)
        except KeyError:
            raise
        if old is not None:
            self.clear_slot(kind, slot)         # 先腾空（置 nil，不删 key）
        self.add_item(kind, slot, item_id, count, kid=kid, clone_like=clone_like,
                      db=db)
        return count

    # -------------------------------------------------- 格子搬运 / 复制 / 整理
    # 2026-10-08 川要的三件事：列表拖动排序、右键「移动到 / 复制到」、快捷整理。
    # 语义层全在这儿，界面只调这些方法（别在界面里拼字节）。
    @staticmethod
    def _is_sec_kind(kind):
        """这个容器的货物算不算进 `security[:items]` 记账。

        ⚠ 仓库的货**也算**（`item_counts(include_warehouse=True)`）——
        所以背包 ↔ 仓库互搬不改变总数，但**复制**会。
        """
        return kind in ("Items", "pack", "warehouse")

    @staticmethod
    def _db_of(kind):
        """容器键 → `Data\\*.rvdata2` 表键。

        ⚠ 背包与仓库都是 `@items` 那一个容器（里面混装道具/武器/防具），
        所以它们的**模板表**永远是 `Items` —— 造物件时别拿容器键去查表。
        """
        return "Items" if kind in ("pack", "warehouse") else kind

    def _slot_node_of(self, h, slot):
        """取某槽的值节点；没有这一对返回 None（键在、值是 nil 的算"有键"）。"""
        i = self._pair_index(h, slot)
        return None if i < 0 else h.pairs[i][1]

    def _slot_alive(self, h, slot):
        """这一格有货吗（值是 `[对象, 数量]` 才算）。"""
        v = _deref(self._slot_node_of(h, slot))
        return isinstance(v, M.ArrayNode) and bool(v.items)

    def _put_slot(self, h, slot, value):
        """写回某一槽的值；没有这一对就**按槽号顺序**插进去。

        ⚠ 老档里被清空的格子**键还留着**（值是 nil）—— 那种只换值、不加键，
        免得凭空多出一对把后面的 `@N` 编号整体挪位。
        """
        i = self._pair_index(h, slot)
        if i >= 0:
            h.pairs[i] = (h.pairs[i][0], value)
            return
        pos = len(h.pairs)
        for j, (k, _v) in enumerate(h.pairs):
            kv = M.value_of(_deref(k))
            if isinstance(kv, int) and kv > slot:
                pos = j
                break
        h.pairs.insert(pos, (int_node(slot), value))

    def move_slots(self, src, slots, dst=None, target=None, copy=False):
        """把 `src` 里这些格子整格搬到 `dst` 的第 `target` 格起（或复制过去）。

        * **同容器**（`dst` 省略/相同）＝**对称互换**：源格内容按顺序落到目标格，
          目标格原来的内容按顺序回到源格 —— 单格就是「有物则交换」，
          多格保持相对顺序（列表拖动排序就是这个语义）。
        * **跨容器**（背包 ↔ 仓库）＝**找空格放**：从 `target` 起往后找够空位，
          放不下就**整批不动**并报错（绝不覆盖对面已有的东西）。
        * `copy=True` ＝复制（`clone_node` 深拷贝，`@attr` 运行时内容一起带上）；
          ⚠ 目标格**必须为空**（覆盖会静默丢东西），且复制会增加持有数 ⇒
          完事要按件同步 `security[:items]`。

        返回 `(搬运格数, 目标槽列表)`。属**结构性改动**。
        """
        slots = sorted({int(s) for s in slots})
        if not slots:
            return 0, []
        h1 = self.container(src)
        same = (dst is None) or (dst == src)
        h2 = h1 if same else self.container(dst)
        n = len(slots)
        target = int(slots[0] if target is None else target)
        if same:
            tgt = [target + i for i in range(n)]
            if copy:
                busy = [t for t in tgt if self._slot_alive(h2, t)]
                if busy:
                    raise ValueError("第 %s 格已经有东西了，复制只能进空格"
                                     % "、".join(str(b) for b in busy))
            # ⚠ 先把两边**写之前**的快照读出来：源/目标区间重叠时也不会互相踩。
            old_s = {s: self._slot_node_of(h1, s) for s in slots}
            old_t = {t: self._slot_node_of(h2, t) for t in tgt}
            for s, t in zip(slots, tgt):
                v = old_s[s]
                if v is None:
                    self._put_slot(h2, t, nil_node())
                else:
                    self._put_slot(h2, t, clone_node(v) if copy else v)
            if not copy:                       # 目标区原来的东西回到源格
                for t, s in zip(tgt, slots):
                    v = old_t[t]
                    self._put_slot(h1, s, nil_node() if v is None else v)
        else:
            limit = self.page_count(dst) * PACK_PAGE_SIZE
            free, s = [], target
            while len(free) < n and s < limit:
                if not self._slot_alive(h2, s):
                    free.append(s)
                s += 1
            if len(free) < n:
                raise ValueError(
                    "%s 从第 %d 格起只有 %d 个空位，放不下 %d 格"
                    % (dict(SRCS).get(dst, dst), target, len(free), n))
            for s, t in zip(slots, free):
                v = self._slot_node_of(h1, s)
                self._put_slot(h2, t, clone_node(v) if copy else
                               (nil_node() if v is None else v))
                if not copy:
                    self._put_slot(h1, s, nil_node())
            tgt = free
        self.doc.mark_structural()
        if copy and self._is_sec_kind(src):
            ids = set()
            for t in tgt:
                arr = _deref(self._slot_node_of(h2, t))
                if isinstance(arr, M.ArrayNode) and arr.items:
                    ids.add(get_int(ivar(_deref(arr.items[0]), "@id"), -1))
            for iid in ids:
                if iid >= 0:
                    self.sync_security_item(iid)
        return n, tgt

    def stack_limit(self, node):
        """这一格最多叠多少 —— 照游戏 `max_item_number`（script00:14440）。"""
        n = _deref(node)
        if getattr(n, "cls", "") != "RPG::Item":
            return 1                # 武器/防具：游戏那边也是 1（不叠）
        return MAX_ITEM_BY_ID.get(get_int(ivar(n, "@id"), -1), MAX_ITEM)

    def _tmpl_note(self, item_id):
        """同 id 的 Data 模板备注（物件自己没带 `@note` 时用它兜底）。

        `[single]` / `[superposition]` 这两个标记就写在备注里，
        游戏 `single?` / `superposition?`（script00:42995）读的是 `$data_items[id].note`。
        """
        m = getattr(self, "_note_cache", None)
        if m is None:
            m = {}
            try:
                import datatables
                _root, items = datatables.load("Items")
                for i, n in items:
                    m[i] = _as_str(ivar(n, "@note")) or ""
            except Exception:
                m = {}
            self._note_cache = m
        return m.get(item_id, "")

    def stack_key(self, node):
        """可堆叠「同款」的归一 key；不可堆叠返回 None（照游戏 `get_slot`，14896）。

        * 武器 / 防具、带 `[single]` 的 ⇒ 不可堆（游戏那边也是 1 件一格）
        * 带 `[superposition]` 的（按内容堆叠）⇒ **本轮不合并**：游戏合并这类
          还要把内容里的 `count` 累加（14701），工具不猜那份结构，宁可不动
        * 其余普通道具 ⇒ 同 id 即可（同 id 的 price 必然相同，游戏正是这么判的）
        """
        n = _deref(node)
        if getattr(n, "cls", "") != "RPG::Item":
            return None
        iid = get_int(ivar(n, "@id"), -1)
        note = (_as_str(ivar(n, "@note")) or "") or self._tmpl_note(iid)
        if "[single]" in note or "[superposition]" in note:
            return None
        return (iid,)

    def arrange(self, kind="Items", page=None, compact=True, merge=True):
        """整理：**紧凑排列**（消掉中间空格）+ **同类合并**（叠到每格上限）。

        只做这两件，**不发明排序** —— 游戏自带的「整理」（`arrange`，14704）是按
        `$game_system.config[:item_sort]` 那套规则排的，工具不去猜它。
        返回 `(紧凑挪了几格, 合并了几格)`。
        """
        h = self.container(kind)
        pages = [page] if page is not None else range(self.page_count(kind))
        lo, hi = min(pages) * PACK_PAGE_SIZE, (max(pages) + 1) * PACK_PAGE_SIZE
        merged = 0
        if merge:
            heads = []                  # [(key, (槽, arr))]，第一格当"主格"
            for s, _p, _i, _id, _nm, _c in self.bag(kind):
                if not (lo <= s < hi):
                    continue
                arr = _deref(self._slot_node_of(h, s))
                if not isinstance(arr, M.ArrayNode) or not arr.items:
                    continue
                key = self.stack_key(_deref(arr.items[0]))
                cnt = get_int(arr.items[1]) if len(arr.items) > 1 else 1
                hit = None
                if key is not None:
                    for k2, pair in heads:
                        if k2 == key:
                            hit = pair
                            break
                if hit is None:
                    heads.append((key, (s, arr)))
                    continue
                _s2, arr2 = hit
                limit = self.stack_limit(_deref(arr2.items[0]))
                cur = get_int(arr2.items[1]) if len(arr2.items) > 1 else 1
                take = max(0, min(int(limit) - cur, cnt))
                if take <= 0:           # 主格已满 ⇒ 这一格自己当新的主格
                    heads.append((key, (s, arr)))
                    continue
                self.doc.set_value(_deref(arr2.items[1]), cur + take)
                left = cnt - take
                if left > 0:
                    self.doc.set_value(_deref(arr.items[1]), left)
                    heads.append((key, (s, arr)))
                else:
                    self._put_slot(h, s, nil_node())
                merged += 1
        moved = 0
        if compact:
            alive = [s for s, _p, _i, _id, _nm, _c in self.bag(kind)
                     if lo <= s < hi]
            cap = hi - lo
            if len(alive) > cap:
                raise ValueError("这一段只有 %d 格，装不下 %d 件"
                                 % (cap, len(alive)))
            for tgt, s in zip(range(lo, hi), alive):
                if tgt != s:
                    self._put_slot(h, tgt, self._slot_node_of(h, s))
                    self._put_slot(h, s, nil_node())
                    moved += 1
        if moved or merged:
            self.doc.mark_structural()
        return moved, merged

    def make_item(self, kind, item_id, kid=None, like=None):
        """造一个物品对象。

        优先 `like`：**存档里已经有的同一件东西**（连 `@attr` 里的运行时内容
        一起克隆）——游戏自己发的孵化蛋/礼包里的内容就是现抽的，
        从模板凭空造会缺东西（用起来直接 NoMethodError）。
        没参照物时才用 Data 模板 + 补上游戏自加的 5 个 ivar，
        并且对“运行时才填内容”的家族（孵化蛋/礼包/图纸…）现生成一份。

        kid：孵化类物品的“孵出/开出什么”id；不给就随机（自己按游戏的范围抽）。
        """
        import datatables
        if like is not None:
            node = clone_node(like)
            self._fix_payload(node, kind, item_id, kid)
            return node
        _root, items = datatables.load(self._db_of(kind))
        tpl = None
        for i, n in items:
            if i == item_id:
                tpl = n
                break
        if tpl is None:
            raise KeyError("%s 里没有 id=%d" % (kind, item_id))
        node = clone_node(tpl)
        extra = self._extra_ivars(kind)
        have = set(k for k, _ in node.ivars)
        for k, v in extra:
            if k not in have:
                node.ivars.append((k, v))
        self._fix_payload(node, kind, item_id, kid)
        return node

    def item_payload(self, node):
        """读一个物件 `@attr` 里的运行时内容：`(type, data)`，没有则 (None, None)。

        ⚠ 第二项是"内容本体"：多数家族是 `@attr["data"][:data]`，
        但 `:礼盒` 那种没有 `data` 这一层，内容直接跟 `:type` 平级
        ⇒ 这时把外层整份 Hash 当内容返回（否则读出来是 nil）。
        """
        a = _deref(ivar(node, "@attr"))
        d = _deref(hash_get(a, "data")) if a is not None else None
        if not isinstance(d, M.HashNode):
            return None, None
        t = M.value_of(_deref(hash_get(d, "type")))
        inner = _deref(hash_get(d, "data"))
        # ⚠ 乾坤袋的 `data` 是**空 Hash**（它跟 `max` 平级，游戏读的是
        #   `item.data[:data].length`）—— 空 Hash 不能当"内容本体"，否则
        #   摘要/界面上读不到旁边的 `max`。
        if isinstance(inner, M.HashNode) and not inner.pairs:
            inner = None
        return t, (d if inner is None else inner)

    def item_needs_payload(self, kind, item_id):
        """这件东西是不是“游戏运行时才生成内容”（孵化蛋、各类礼包…）。

        ⚠ `kind` 既可能是**容器键**（`"pack"`/`"warehouse"`，界面「位置」下拉
        那条路：`set_payload` → `_fix_payload`），也可能是**表键**
        （`"Items"`/`"Weapons"`/`"Armors"`，「重抽管理」窗口那条路）——
        所以取名字表**必须过 `_db_of`**。2026-10-08 漏了这一步：传进来
        `"pack"` 时 `name_map` 查空 ⇒ `nm=""`、`need=False`，于是
        `itemattr.build("", 110, over={"id": 21})` 拿不到家族、按 id 区间
        瞎抽了一份（测试里 `bag_reroll` 指定 21 却写出了沙狸 320）。
        """
        import datatables
        nm = datatables.name_map(self._db_of(kind)).get(item_id, "")
        return itemattr.needs_payload(nm, item_id), nm

    def payload_template(self, kind, item_id):
        """从存档里任意一件**有内容**的同款物品上把 `@attr` 整份抄下来。

        ⚠ 背包和仓库都要翻 —— 同款东西可能只躺在仓库里（2026-10-08 加仓库后）。
        """
        for key in ("Items", "warehouse"):
            try:
                h = self.container(key)
            except KeyError:
                continue
            for _k, v in h.pairs:
                arr = _deref(v)
                if not isinstance(arr, M.ArrayNode) or not arr.items:
                    continue
                it = _deref(arr.items[0])
                if it is None or get_int(ivar(it, "@id"), -1) != int(item_id):
                    continue
                t, _d = self.item_payload(it)
                if t:
                    return clone_node(ivar(it, "@attr"))
        return None

    def payload_key_ok(self, node):
        """`@attr` 的外层键是不是**字符串** "data"（游戏只认这个）。

        老版本工具误写成了符号键 `:data`：工具自己能读（兼容两种），
        但游戏 `item.data` 读的是字符串键 → 读不到 → 用的时候直接报
        `undefined method '[]' for nil:NilClass`。
        """
        a = _deref(ivar(node, "@attr"))
        if not isinstance(a, M.HashNode) or not a.pairs:
            return False
        for k, _v in a.pairs:
            kk = _deref(k)
            if isinstance(kk, M.StrNode):
                return True
        return False

    def _fix_payload(self, node, kind, item_id, kid=None, force=False,
                     over=None):
        """给物品补上 `@attr`（游戏运行时才生成的那部分）。

        优先级：现成的内容（不动）→ 存档里同款的内容（整份抄）→ 按游戏
        脚本里的规则现生成（见 `itemattr`）。
        force=True 时不看“同款”，直接按规则重抽一份（「重抽管理」窗口用）。
        `over`＝用户在界面上挑好的字段值（`{"id": 45}`…），与 `kid` 合起来
        交给 `itemattr.build`，后者只覆盖它认得的键。
        """
        cur_t, cur_d = self.item_payload(node)
        if cur_t and kid is None and not force and not over:
            if self.payload_key_ok(node):
                return node            # 存档里本来就有内容，而且键类型对
            # 内容在，但键是符号（老版本工具的写法）→ 重写成字符串键，内容一个不动
            inner = M.HashNode([(self._sym("type"), self._sym(cur_t)),
                                (self._sym("data"),
                                 cur_d if cur_d is not None else nil_node())],
                               default=None)
            attr = M.HashNode([(self._str_key("data"), inner)], default=None)
            if not set_ivar(node, "@attr", attr):
                node.ivars.append(("@attr", attr))
            return node
        need, nm = self.item_needs_payload(kind, item_id)
        if not need and kid is None and not over:
            return node
        sib = None if (force or over) else self.payload_template(kind, item_id)
        if sib is not None and kid is None:
            if not set_ivar(node, "@attr", sib):
                node.ivars.append(("@attr", sib))
            return node
        # `kid`（孵化/开出的对象 id）就是 `over["id"]` —— 合成一份交给
        # itemattr.build，由各生成器自己消费它认得的键（蛋会用 id/mutation、
        # 要诀用 id、指南书用 type/id/lv…），比在这儿事后改 dict 稳。
        ov = dict(over or {})
        if kid is not None:
            ov.setdefault("id", int(kid))
        spec = itemattr.build(nm, item_id, over=ov or None)
        if spec is None:
            return node
        typ, payload = spec
        attr = M.HashNode([], default=None)
        # ⚠ 这里的**外层键必须是字符串 "data"**：游戏写的就是 `@attr["data"]`，
        # 读的时候是 `item.data[:data][:id]`。早期工具写成了符号键 :data，
        # 于是“内容列”读不出来、游戏用蛋时 `item.data` 为 nil 直接报
        # NoMethodError: undefined method '[]' for nil:NilClass。
        attr.pairs.append((self._str_key("data"),
                           self._payload_node(typ, payload)))
        if not set_ivar(node, "@attr", attr):
            node.ivars.append(("@attr", attr))
        return node

    @staticmethod
    def _str_key(text):
        """字符串键（不加 I/E 包装，和游戏写的一样）。"""
        return M.StrNode(text.encode("utf-8"))

    def set_payload(self, kind, slot, kid=None, force=True, over=None):
        """给某一格的东西重新生成/指定“运行时内容”（孵化蛋、要诀之类的）。

        kid：孵化类物品要孵出哪只（不给就按游戏范围随机抽一个）。
        over：用户挑好的字段值（`{"id": 45, "mutation": True}`…），
              给了就不看「存档里的同款」、直接按它 + 游戏规则生成
              （「重抽管理」窗口用；`kid` 等价于 `over["id"]`）。
        """
        it = self._item_node(kind, slot)
        if it is None:
            raise KeyError("第 %d 格是空的" % slot)
        iid = get_int(ivar(it, "@id"), -1)
        need, nm = self.item_needs_payload(kind, iid)
        if not need:
            raise ValueError("%s 不需要运行时内容" % (nm or ("id=%d" % iid)))
        self._fix_payload(it, kind, iid, kid=kid, force=force, over=over)
        self.doc.mark_structural()
        return self.item_payload(it)

    def payload_fields(self, node):
        """读一件物品 `@attr` 里**当前**各字段的值：`{键: 值}`（读不出返回 {}）。

        给「重抽管理」窗口做初值用：打开窗口时把每格现有的内容填进控件，
        用户不改就原样写回。
        """
        _t, d = self.item_payload(node)
        if d is None:
            return {}
        out = {}
        if not isinstance(d, M.HashNode):
            return out
        for k, v in d.pairs:
            kk = M.value_of(_deref(k))
            if isinstance(kk, bytes):
                kk = kk.decode("utf-8", "replace")
            if not isinstance(kk, str):
                continue
            vv = _deref(v)
            if isinstance(vv, (M.HashNode, M.ArrayNode)):
                continue                     # 复合值（元宵 value / 上限表）不给界面挑
            out[kk] = M.value_of(vv)
        return out

    #: 运行时内容的 `:type` → 内部家族键（用来渲染“内容”列）。
    #: **游戏写的是中文符号，工具现在也写中文**（`itemattr` 直接给游戏符号）；
    #: 下面那批英文键是**老版本工具写出来的**存档，只为读得出来而保留。
    #: 口径照游戏自己的物品浮窗（脚本 `case item.data[:type]` 那段）。
    _PAYLOAD_KINDS = {
        "孵化蛋": "egg", "baby_egg": "egg",
        "坐骑蛋蛋": "ride",
        "魔兽要诀": "book", "高级魔兽要诀": "book", "超级魔兽要诀": "book",
        "特殊魔兽要诀": "book", "低级内丹": "book", "高级内丹": "book",
        "skill_book": "book",
        "真知棒": "stick", "超级真知棒": "stick",
        "real_stick_1": "stick", "real_stick_2": "stick",
        "制造指南书": "guide", "灵饰指南书": "guide", "guide_book": "guide",
        "上古锻造图策": "atlas", "ancient_forging_atlas": "atlas",
        "百炼精铁": "iron", "iron": "iron",
        "天眼珠": "god_eye_bead", "god_eye_bead": "god_eye_bead",
        "元灵晶石": "crystal",
        "宝石": "stone", "stone": "stone",
        "人参果": "ginseng", "ginseng": "ginseng",
        "如意丹": "ruyi",
        "元宵": "yuanxiao", "yuanxiao": "yuanxiao",
        "激进元宵丹": "yuanxiao_dan",
        "进阶石": "promote", "promote_stone": "promote",
        "导航旗": "flag", "navigation_flag": "flag",
        "点化石": "dianhua",
        "鬼谷子": "formation", "formation": "formation",
        "礼盒": "gift",
        # ---- 2026-10-08 补齐的那批（type 符号 → 解释方式）----
        "乾坤袋": "qiankun",
        "天材地宝": "tiancai",
        "圣者精气": "jingqi", "战神精气": "jingqi", "仙人精气": "jingqi",
        "本源精气": "jingqi",
        "蟠桃": "peach",
        "符文": "fuwen",
        "上古技能残卷": "canjuan",
        "银票": "silver",
        "提神泪": "tishenlei",
        "摇钱树树苗": "qian_tree",
    }

    def payload_summary(self, node):
        """一句话描述物件的运行时内容（背包列表“内容”列用），空代表没有。

        id 一律解成名字（要诀→技能名、蛋→召唤兽名），不再显示 `{id:45}`
        这种裸数据；翻不动就保留原文（宁缺毋错译）。
        """
        t, d = self.item_payload(node)
        if not t:
            return ""
        kind = self._PAYLOAD_KINDS.get(t)

        def dv(key):
            return M.value_of(_deref(hash_get(d, key))) if d is not None \
                else None

        if kind == "egg":
            kid = dv("id")
            acts = self._name_map("Actors")
            s = "蛋→%s(%s)" % (acts.get(kid, "?"), kid)
            if dv("mutation"):
                s += " 变异"
            return s
        if kind == "ride":
            rid = dv("id")
            q = dv("type")
            sp = dv("speed")
            acts = self._name_map("Actors")
            qs = itemattr.RIDE_QUALITY_NAMES[q] \
                if isinstance(q, int) and 0 <= q < 3 else "?"
            s = "坐骑→%s(%s) 品质%s" % (acts.get(rid, "?"), rid, qs)
            if isinstance(sp, float):
                s += " 移速%g%%" % (round(sp * 100, 2))
            return s
        if kind == "book":
            kid = dv("id")
            sk = self._name_map("Skills")
            nm = t if not str(t).isascii() else "技能书"
            return "%s→%s(%s)" % (nm, sk.get(kid, "?"), kid)
        if kind == "stick":
            acts = self._name_map("Actors")
            sk = self._name_map("Skills")
            aid, sid = dv("id"), dv("sid")
            s = "%s→%s" % (t if not str(t).isascii() else "真知棒",
                           acts.get(aid, "?"))
            if sid is not None:
                s += "；附带技能→%s" % sk.get(sid, "?")
            return s
        if kind == "guide":
            w = dv("type") == "w"
            return "指南书→%s 等级%s" % ("武器" if w else "防具", dv("lv"))
        if kind == "atlas":
            eid = dv("eid")
            nm = ("护腕", "项圈", "铠甲")[eid - 1] if eid in (1, 2, 3) else "?"
            return "图策→%s 等级%s" % (nm, dv("lv"))
        if kind in ("iron", "god_eye_bead", "crystal", "stone"):
            label = {"iron": "精铁", "god_eye_bead": "天眼珠",
                     "crystal": "晶石", "stone": "宝石"}[kind]
            return "%s→等级%s" % (label, dv("lv"))
        if kind in ("ginseng", "ruyi"):
            names = ("体质", "魔力", "力量", "耐力", "敏捷")
            ty = dv("type")
            nm = names[ty] if isinstance(ty, int) and 0 <= ty < 5 else "?"
            label = "人参果" if kind == "ginseng" else "如意丹"
            return "%s→%s %s/%s" % (label, nm, dv("point"), dv("max"))
        if kind == "yuanxiao":
            names = ("攻击资质", "防御资质", "体力资质", "法力资质",
                     "速度资质", "躲闪资质", "成长")
            ty = dv("type")
            nm = names[ty] if isinstance(ty, int) and 0 <= ty < 7 else "?"
            val = _deref(hash_get(d, "value")) if d is not None else None
            v = "?"
            if isinstance(val, M.HashNode) and val.pairs:
                # 游戏就是按下标取第 type 个值（`d[:value].values[d[:type]]`）
                pair = val.pairs[ty] if isinstance(ty, int) and \
                    0 <= ty < len(val.pairs) else None
                if pair is not None:
                    v = M.value_of(_deref(pair[1]))
            mx = _deref(hash_get(d, "max")) if d is not None else None
            if isinstance(mx, M.ArrayNode) and isinstance(ty, int) and \
                    0 <= ty < len(mx.items):
                mx = M.value_of(_deref(mx.items[ty]))
            else:
                mx = M.value_of(mx) if mx is not None else "?"
            return "元宵→%s %s/%s" % (nm, v, mx)
        if kind == "promote":
            aid = dv("id")
            acts = self._name_map("Actors")
            who = "无" if aid == 0 else acts.get(aid, "?")
            cnt = dv("count")
            prog = "" if cnt is None else \
                (" 已充沛" if cnt == 50 else " %s/50" % cnt)
            return "进阶石→%s%s" % (who, prog)
        if kind == "flag":
            return "导航旗→剩余%s次" % dv("count")
        if kind == "dianhua":
            kid = dv("id")
            sk = self._name_map("Skills")
            return "点化石→%s" % sk.get(kid, "?")
        if kind == "yuanxiao_dan":
            return "元宵丹→可食用上限+%s" % dv("max")
        if kind == "gift":
            lst = _deref(hash_get(d, "list")) if d is not None else None
            n = len(lst.items) if isinstance(lst, M.ArrayNode) else 0
            return "礼盒→内含 %d 件" % n
        if kind == "formation":
            key = dv("key")
            return "鬼谷子→阵法·%s" % (key or "?")
        # ---- 2026-10-08 补齐的那批 ----
        if kind == "qiankun":
            return "乾坤袋→容量 %s 格" % dv("max")
        if kind == "tiancai":
            return "天材地宝→%s 档（上限 %s）" % (dv("lv"), dv("limit"))
        if kind == "jingqi":
            # 四类精气：本源只有 seed；圣者是属性点；战神/仙人各带一个技能。
            hold = "skill" if t == "战神精气" else \
                ("skills" if t == "仙人精气" else None)
            hv = _deref(hash_get(d, hold)) if (d is not None and hold) else None
            kid = None
            if isinstance(hv, M.HashNode) and hv.pairs:
                kv = M.value_of(_deref(hv.pairs[0][0]))
                kid = kv if isinstance(kv, int) else None
            if kid is not None:
                return "%s→技能·%s" % (t, self._name_map("Skills").get(kid, kid))
            pl = _deref(hash_get(d, "point")) if d is not None else None
            n = len(pl.items) if isinstance(pl, M.ArrayNode) else 0
            return "%s%s" % (t, ("→属性 %d 项" % n) if n else "")
        if kind == "peach":
            return "蟠桃→%s 年" % dv("year")
        if kind == "fuwen":
            return "符文→%s 星 等级%s" % (dv("star"), dv("lv"))
        if kind == "canjuan":
            return "上古技能残卷→门派%s" % dv("id")
        if kind == "silver":
            return "银票→%s 金" % dv("gold")
        if kind == "tishenlei":
            return "提神泪→恢复 %s" % dv("value")
        if kind == "qian_tree":
            return "摇钱树树苗"
        return "%s→%s" % (t, self._plain_text(d))

    @staticmethod
    def _plain_text(node):
        """把一小捻节点渲染成一行字（只给界面显示用）。"""
        n = _deref(node)
        if n is None or isinstance(n, M.NilNode):
            return "nil"
        if isinstance(n, M.HashNode):
            return "{" + ", ".join("%s:%s" % (GameEditor._plain_text(k),
                                                GameEditor._plain_text(v))
                                    for k, v in n.pairs) + "}"
        if isinstance(n, M.ArrayNode):
            return "[" + ", ".join(GameEditor._plain_text(x) for x in n.items) \
                + "]"
        if isinstance(n, M.SymbolNode):
            return str(n.name)
        v = M.value_of(n)
        if isinstance(v, bytes):
            return v.decode("utf-8", "replace")
        return str(v)

    @staticmethod
    def _sym(name):
        return M.SymbolNode(name)

    def _payload_node(self, typ, payload):
        """把 `(type, 内容)` 转成 `{:type => ..., <内容的键> => ...}` 节点。

        `payload` 的形状**照游戏写的那份**：多数是 `{"data": {...}}`，
        `:礼盒` 那种是 `{"list": [...]}` —— 所以不能写死一个 `:data` 层。
        `typ` 本身就是游戏的中文符号（`itemattr` 给的就是它），直接写。
        """
        pairs = [(self._sym("type"), self._sym(typ))]
        for k, v in payload.items():
            pairs.append((self._sym(k), self._plain_node(v)))
        return M.HashNode(pairs, default=None)

    def _plain_node(self, value):
        """Python 值 → Marshal 节点（只支持这几个基本类型，够用）。"""
        if isinstance(value, itemattr.Sym):
            return self._sym(value.name)
        if isinstance(value, bool):
            return M.BoolNode(value)
        if isinstance(value, int):
            return int_node(value)
        if isinstance(value, float):
            return M.FloatNode(value, repr(value).encode("ascii"))
        if isinstance(value, bytes):
            return str_node(value)
        if isinstance(value, str):
            return str_node(value)
        if isinstance(value, itemattr.IntHash):
            # 键要是**整数**的 Hash（战神精气的 `{技能id => 数值}`）—— 下面
            # 那条默认把键写成符号，游戏读不出来。
            return M.HashNode([(self._plain_node(k), self._plain_node(v))
                               for k, v in value.items()], default=None)
        if isinstance(value, dict):
            return M.HashNode([(self._sym(k), self._plain_node(v))
                               for k, v in value.items()], default=None)
        if isinstance(value, (list, tuple)):
            return M.ArrayNode([self._plain_node(x) for x in value])
        return nil_node()

    def _item_node(self, kind, slot):
        """取某个格子的物品对象节点（空返回 None）。"""
        h = self.container(kind)
        i = self._pair_index(h, slot)
        if i < 0:
            return None
        arr = _deref(h.pairs[i][1])
        if not isinstance(arr, M.ArrayNode) or not arr.items:
            return None
        return _deref(arr.items[0])

    def find_like(self, kind, item_id):
        """找一件同类的现成物件（克隆它的运行时内容用）。

        ⚠ 背包和仓库都翻 —— 同款可能只躺在仓库里。
        """
        for key in ("Items", "warehouse"):
            try:
                h = self.container(key)
            except KeyError:
                continue
            for _k, v in h.pairs:
                arr = _deref(v)
                if not isinstance(arr, M.ArrayNode) or not arr.items:
                    continue
                it = _deref(arr.items[0])
                if it is None:
                    continue
                if get_int(ivar(it, "@id"), -1) == int(item_id):
                    return it
        return None

    def _extra_ivars(self, kind):
        """存档物品比模板多的那几个 ivar，给个安全默认值。"""
        return [
            ("@result_note", M.HashNode([], default=None)),
            ("@attr", M.HashNode([], default=None)),
            ("@update", M.BoolNode(False)),
            ("@new", M.BoolNode(False)),
            ("@transaction_code",
             M.BignumNode(random.getrandbits(127) | 1)),
        ]

    # ==================================================== 记账校验（Change）
    # 游戏的 $game_system.security 是一个 Hash，一共 5 类账：
    #   :gold       单个 Change，@code='$game_party.gold' —— 账必须 == 当前金钱
    #   :items      {道具id => Change} —— 账必须 == 背包+仓库持有数
    #   :renqi      {角色id => Change} —— 账必须 == 该角色 @人气
    #   :gongxian   {角色id => Change} —— 账必须 == 该角色 @贡献
    #   :variables  {变量id => Change} —— 账必须 == $game_variables[id]
    # Change 每次数值变动都会 eval(@code) 和自己比，对不上立刻
    # `keyword << 'NE!'` + `@cheated = 帧号`。改金钱/属性后**必须把账同步**。
    def security_node(self):
        sec = _deref(ivar(self.sv.section("system"), "@security"))
        return sec if isinstance(sec, M.HashNode) else None

    def security_sub(self, key):
        """取 security 里的子表（:items / :renqi / :gongxian / :variables）。"""
        sec = self.security_node()
        if sec is None:
            return None
        n = _deref(hash_get(sec, key))
        return n if isinstance(n, M.HashNode) else None

    def security_hash(self):
        """兼容旧接口：返回 (@security 节点, items 子表)。"""
        return self.security_node(), self.security_sub("items")

    @staticmethod
    def change_value(ch):
        """解密一个 Change 的 @value；**支持负数**（首位可以是 '-'）。

        游戏的 `Change#show` 是 `load.map{ AES_ECB.decrypt }.join.to_i`，
        所以每位解出来拼成字符串再 int 即可；空数组 = 0（新建未记账）。
        """
        ch = _deref(ch)
        if not isinstance(ch, M.ObjNode):
            return None
        val = _deref(ivar(ch, "@value"))
        if not isinstance(val, M.ArrayNode):
            return None
        chars = []
        for x in val.items:
            t = aes.decrypt_token(_as_str(x))
            if t is None:
                return None
            chars.append(t)
        txt = "".join(chars)
        if not txt or txt == "-":
            return 0
        try:
            return int(txt)
        except ValueError:
            return None

    @staticmethod
    def _change_set(ch, total):
        """把 Change 的 @value 按数字重写（逐位 AES；负数带 '-' 位）。"""
        ch = _deref(ch)
        arr = M.ArrayNode([hex_str_node(aes.encrypt_digit(d))
                           for d in str(int(total))])
        if not set_ivar(ch, "@value", arr):
            ch.ivars.append(("@value", arr))

    def security_total(self, item_id):
        """游戏记录的"该物品累计获得数量"（读不出来返回 None）。"""
        items = self.security_sub("items")
        if items is None:
            return None
        ch = _deref(hash_get(items, item_id))
        return self.change_value(ch) if ch is not None else None

    def _set_security_total(self, ch, total):
        self._change_set(ch, total)

    # ---------------- 金钱账（security[:gold]）
    def security_gold(self):
        """游戏记的金钱账（读不出来返回 None；空账 = 0）。"""
        sec = self.security_node()
        if sec is None:
            return None
        ch = _deref(hash_get(sec, "gold"))
        return self.change_value(ch) if ch is not None else None

    def sync_gold_security(self):
        """把 security[:gold] 的账对齐到当前金钱。返回是否改动了。

        这是"用工具改完金钱、玩一会儿还是被判作弊"的根因：
        游戏里下一次 gain_gold 时 `Change.new(show+delta, '$game_party.gold')`
        会立刻 eval 比对，账实不符就记 'NE!'。
        """
        want = int(self.sv.gold())
        sec = self.security_node()
        if sec is None:
            return False
        ch = _deref(hash_get(sec, "gold"))
        if isinstance(ch, M.ObjNode):
            if self.change_value(ch) == want:
                return False
            self._change_set(ch, want)
            self.doc.mark_structural()
            return True
        # 老档可能没有这笔账 —— 按 init_security 的样子补一个（键是符号 :gold）
        ch = M.ObjNode("Change")
        ch.ivars = [("@code", str_node("$game_party.gold")),
                    ("@value", M.ArrayNode(
                        [hex_str_node(aes.encrypt_digit(d))
                         for d in str(want)]))]
        sec.pairs.append((M.SymbolNode("gold"), ch))
        self.doc.mark_structural()
        return True

    # ---------------- 变量账（security[:variables]）
    def security_variable_rows(self):
        """[(变量id, 记账值, 实际值), ...]（只列游戏已建账的变量）。"""
        vh = self.security_sub("variables")
        out = []
        if vh is None:
            return out
        for k, v in vh.pairs:
            vid = M.value_of(_deref(k))
            if not isinstance(vid, int):
                continue
            rec = self.change_value(v)
            want = self.sv.get_variable(vid)
            out.append((vid, rec, want if isinstance(want, int) else None))
        out.sort()
        return out

    def sync_security_variables(self):
        """把已建账的变量对齐到 $game_variables 当前值。返回改了几条。"""
        n = 0
        for _vid, ch, want in self._iter_security_changes("variables"):
            if isinstance(want, int) and self.change_value(ch) != want:
                self._change_set(ch, want)
                n += 1
        if n:
            self.doc.mark_structural()
        return n

    # ---------------- 人气 / 贡献账（security[:renqi|gongxian]）
    def _actor_attr_int(self, actor, attr_name):
        obj = _deref(ivar(actor, "@attr"))
        return get_int(ivar(obj, attr_name)) if obj is not None else None

    def security_actor_rows(self, sec_key, attr_name):
        """[(角色id, 角色名, 记账值, 实际值), ...]。"""
        h = self.security_sub(sec_key)
        out = []
        if h is None:
            return out
        actors = dict(self.sv.actors())
        for k, v in h.pairs:
            aid = M.value_of(_deref(k))
            if not isinstance(aid, int):
                continue
            a = actors.get(aid)
            want = self._actor_attr_int(a, attr_name) if a is not None else None
            out.append((aid, self.sv.actor_name(a) if a is not None
                        else ("角色%d" % aid),
                        self.change_value(v), want))
        out.sort()
        return out

    def sync_security_actors(self, sec_key, attr_name):
        """把某角色类账（人气/贡献）对齐到角色当前属性。返回改了几条。"""
        h = self.security_sub(sec_key)
        if h is None:
            return 0
        actors = dict(self.sv.actors())
        n = 0
        for k, v in h.pairs:
            aid = M.value_of(_deref(k))
            a = actors.get(aid) if isinstance(aid, int) else None
            if a is None:
                continue
            want = self._actor_attr_int(a, attr_name)
            if want is not None and self.change_value(v) != want:
                self._change_set(v, want)
                n += 1
        if n:
            self.doc.mark_structural()
        return n

    def _iter_security_changes(self, sec_key):
        """遍历某子表里的 (键值, Change节点, 实际值) —— 实际值按子表类型取。"""
        h = self.security_sub(sec_key)
        if h is None:
            return
        actors = dict(self.sv.actors())
        attr = {"renqi": "@人气", "gongxian": "@贡献"}.get(sec_key)
        for k, v in h.pairs:
            kv = M.value_of(_deref(k))
            if not isinstance(kv, int):
                continue
            if sec_key == "variables":
                want = self.sv.get_variable(kv)
                want = want if isinstance(want, int) else None
            elif attr:
                a = actors.get(kv)
                want = self._actor_attr_int(a, attr) if a is not None else None
            else:
                want = None
            yield kv, v, want

    def resync_all_security(self):
        """把 5 类账全部对齐到存档实际状态。返回 [(账名, 改了几条), ...]。"""
        out = []
        n_items = self.resync_security()
        if n_items:
            out.append(("物品计数", n_items))
        if self.sync_gold_security():
            out.append(("金钱", 1))
        n_var = self.sync_security_variables()
        if n_var:
            out.append(("变量", n_var))
        n_renqi = self.sync_security_actors("renqi", "@人气")
        if n_renqi:
            out.append(("人气", n_renqi))
        n_gx = self.sync_security_actors("gongxian", "@贡献")
        if n_gx:
            out.append(("贡献", n_gx))
        return out

    def bump_security(self, item_id, delta):
        """兼容旧接口：不再是加 delta，而是直接把计数对齐到实际总数。"""
        if not delta:
            return None
        return self.sync_security_item(item_id)

    def sync_security_item(self, item_id, create=True):
        """把某件道具的“累计获得数量”对齐到背包（+仓库）里的实际总数。

        游戏只对 `RPG::Item` 记账（`security` 里第一行就 `return` 掉了
        Weapon/Armor），而且背包里是三种对象混装的，所以这里要按类过滤。
        本来没有条目的（游戏还没给你发过这件东西），就按游戏自己的模板
        新建一个：`@code` 是它当场算期望值的 Ruby 片段。
        """
        _sec, items = self.security_hash()
        if items is None:
            return None
        total = self.item_counts().get(item_id, 0)
        ch = _deref(hash_get(items, item_id))
        if isinstance(ch, M.ObjNode):
            self._set_security_total(ch, total)
            self.doc.mark_structural()
            return total
        if not create or total <= 0:
            return None
        ch = self._make_change(item_id, total)
        pos = len(items.pairs)
        for j, (k, _v) in enumerate(items.pairs):
            kv = M.value_of(_deref(k))
            if isinstance(kv, int) and kv > item_id:
                pos = j
                break
        items.pairs.insert(pos, (int_node(item_id), ch))
        self.doc.mark_structural()
        return total

    #: 游戏建 Change 时用的那段 Ruby 片段（照抄脚本 8946 行，空白无所谓）
    CHANGE_CODE = ("proc{|i| $game_party.item_number(i) + "
                   "$game_party.item_number(i, $game_party.warehouse) "
                   "}.call(%d)")

    def _make_change(self, item_id, total):
        ch = M.ObjNode("Change")
        ch.ivars = [("@code", str_node(self.CHANGE_CODE % item_id)),
                    ("@value", M.ArrayNode(
                        [hex_str_node(aes.encrypt_digit(d))
                         for d in str(int(total))]))]
        return ch

    def item_counts(self, include_warehouse=True):
        """{道具id: 数量} —— **只算 RPG::Item**（背包里混着武器/防具）。"""
        out = {}

        def eat(h):
            if not isinstance(h, M.HashNode):
                return
            for _k, v in h.pairs:
                arr = _deref(v)
                if not isinstance(arr, M.ArrayNode) or not arr.items:
                    continue
                obj = _deref(arr.items[0])
                if obj is None or getattr(obj, "cls", "") != "RPG::Item":
                    continue
                iid = get_int(ivar(obj, "@id"), -1)
                cnt = get_int(arr.items[1]) if len(arr.items) > 1 else 1
                out[iid] = out.get(iid, 0) + cnt

        eat(self.container("Items"))
        if include_warehouse:
            eat(_deref(hash_get(self._hash(), "warehouse")))
        return out

    def resync_security(self):
        """按背包里的实际数量，把 `security[:items]` 全部对齐一遍。"""
        _sec, items = self.security_hash()
        if items is None:
            return 0
        actual = self.item_counts()
        n = 0
        for k, v in items.pairs:
            iid = M.value_of(_deref(k))
            ch = _deref(v)
            if not isinstance(iid, int) or ch is None:
                continue
            want = actual.get(iid, 0)
            cur = self.security_total(iid)
            if cur != want:
                self._set_security_total(ch, want)
                n += 1
        if n:
            self.doc.mark_structural()
        return n

    def security_rows(self):
        """[(item_id, 名称, 游戏记录数量, 背包实际数量), ...]"""
        _sec, items = self.security_hash()
        out = []
        if items is None:
            return out
        actual = self.item_counts()
        nm = self._name_map("Items")
        for k, v in items.pairs:
            iid = M.value_of(_deref(k))
            if not isinstance(iid, int):
                continue
            out.append((iid, nm.get(iid, "?"), self.security_total(iid),
                        actual.get(iid, 0)))
        out.sort()
        return out

    # ==================================================== 经验
    def exp(self, actor):
        """角色「本级经验」= `@exp[@class_id]`。

        ⚠ `@exp` 是个 Hash（**职业id → 经验**），游戏读的是 `@exp[@class_id]`，
        不是"Hash 里第一项"——这俩平时碰巧一样（没转过职的存档只有一项），
        但转职过的角色会同时留着旧职业那条，取第一项就取错了。
        """
        h = _deref(ivar(actor, "@exp"))
        if not isinstance(h, M.HashNode) or not h.pairs:
            return 0
        want = M.value_of(_deref(ivar(actor, "@class_id")))
        picked = None
        for k, v in h.pairs:
            if want is not None and M.value_of(_deref(k)) == want:
                picked = _deref(v)
                break
        if picked is None:
            picked = _deref(h.pairs[0][1])
        return M.value_of(picked) or 0

    def set_actor_level(self, actor, value):
        """改角色等级，自动触发潜能/五维调整（和召唤兽一样的规则）。"""
        old_lv = get_int(ivar(actor, "@level"), 0)
        self.sv.set_actor_field(actor, "@level", int(value))
        attr = _deref(ivar(actor, "@attr"))
        self._apply_level_delta(attr, int(value) - old_lv)

    def set_actor_level_full(self, actor, level, sync_exp=True):
        """改等级 + 把 @exp 对齐到该等级的门槛（`init_exp` 的语义）。

        为什么必须一起改：游戏升级走的是 `gain_exp` → `change_exp`，
        而 `change_exp` 里**没有**升级逻辑，等级只在玩家点「升级」按钮
        （`level_up?` 判定后调 `actor.level_up`）时才 +1。
        满级角色 gain_exp 第一行就 return，所以只改 @exp 在游戏里
        永远看不出变化 —— 等级要动，就得直接改 @level。

        返回 (等级, 是否写了 exp)；level 会被夹到 1..MAX_LEVEL_ACTOR。
        """
        lv = int(level)
        if lv < 1:
            lv = 1
        if lv > MAX_LEVEL_ACTOR:
            lv = MAX_LEVEL_ACTOR
        self.set_actor_level(actor, lv)
        wrote = None
        if sync_exp:
            wrote = self.sync_exp_to_level(actor, lv)
        return lv, wrote

    def actor_exp_full(self, actor):
        """「一键满级」：等级顶到满级 + `@exp` 对齐到满级门槛，一次到位。

        ⚠ 为什么不能**只**写 `@exp`（2026-09-20 再核了一遍脚本，结论没变）：
        `Game_Actor#change_exp`(5960) 只做 `@exp[@class_id] = [exp,0].max; refresh`
        —— **没有**升级循环。人物想升级只有两条路：
          a) 地图 HUD 的「升级」按钮（`Window_Actor#update_btns` 索引 11，
             `enabled = actor.level_up?`，点了才 `actor.level_up`，**一次一级**）；
          b) 事件指令 316（`Game_Interpreter#command_316` → `actor.change_level`）。
        战斗结算 `BattleManager.gain_exp`(1845) → `$game_party.battle_members`
        → `Game_Actor#gain_exp`(5991) → `change_exp`，到此为止，等级不动。
        （只有召唤兽 `Game_Baby#change_exp`(7001) 第 7014 行有
         `level_up while ...` 会自己连升，所以"改完经验打一场自动升级"
         **只对召唤兽成立，且只到主人+5**，见 baby_exp_full。）

        所以「拉满」= 直接给满级 + 对齐经验，返回 (等级, 写进 @exp 的值)。
        潜能/五维由 `set_actor_level` 里的 `_apply_level_delta` 一并补。
        """
        return self.set_actor_level_full(actor, MAX_LEVEL_ACTOR, sync_exp=True)

    def actor_exp_fill(self, actor):
        """「经验拉满」（角色页按钮）：只把 @exp 写到 `ACTOR_EXP_FILL`，
        **不动等级** —— 玩家回游戏自己点「升级」（一次一级）。

        和 `actor_exp_full`（界面「一键满级」）的唯一区别 = 不写 `@level`。
        用途：想自己掌握升级节奏，而不是被工具直接顶到满级；
        经验多给点，留在手里也能接着用。返回写进 @exp 的值。
        """
        return self.set_exp(actor, ACTOR_EXP_FILL)

    def set_exp(self, actor, value):
        node = self.exp_node(actor)
        if node is None:
            raise KeyError("这个角色没有 @exp")
        self.doc.set_value(node, int(value))
        return int(value)

    def sync_exp_to_level(self, actor, level):
        """把 @exp 设成 level 对应的「本级起始经验」。
        游戏里 `init_exp` 就是 `@exp[@class_id] = current_level_exp`
        （= `exp_for_level(@level)`），升级时 `exp - next_level_exp` 会减到门槛重来。
        ⚠ 游戏**只在 gain_exp 时才会动等级**（编辑器里 `level_up?` → 玩家点按钮
        → `actor.level_up`），光改 @exp 不会让等级变；而且满级角色 gain_exp
        直接 return，改 exp 完全没反应。所以「调等级」必须同时把 exp 对齐，
        否则会出现「60 级但获得经验 0」这种读出来怪怪的档。
        返回写进去的值 / None（满级或其他取不到门槛的情况）。
        """
        tbl = exp_for_level(level, "actor")
        if tbl is None:
            return None
        return self.set_exp(actor, tbl)

    def exp_node(self, actor):
        """`@exp[@class_id]` 对应的那个节点（要写值就往这儿写）。"""
        h = _deref(ivar(actor, "@exp"))
        if not isinstance(h, M.HashNode) or not h.pairs:
            return None
        want = M.value_of(_deref(ivar(actor, "@class_id")))
        for k, v in h.pairs:
            if want is not None and M.value_of(_deref(k)) == want:
                return _deref(v)
        return _deref(h.pairs[0][1])

    def exp_key(self, actor):
        h = _deref(ivar(actor, "@exp"))
        if isinstance(h, M.HashNode) and h.pairs:
            return M.value_of(_deref(h.pairs[0][0]))
        return None

    # ---------------- 「累计获得经验」= 经验封顶开关（以前叫"升级所需经验"）
    # 游戏脚本 Game_Actor#gain_exp：
    #     @limit_exp ||= 0
    #     if @limit_exp > 202123741
    #       $tip.say("体验版本, #{name}经验累计获得已达上限：202273024", 1)
    #       return          # ← 直接返回，这一级的经验一个字节都不给
    #     end
    #     @limit_exp += exp
    # 也就是说它**既是累计计数器，又是"还发不发经验"的开关**：
    # 一旦超过 202123741，再获得的经验会被**全部丢弃**（等级也涨不上去）。
    LIMIT_EXP_MAX = 202123741

    def limit_exp(self, actor):
        """累计获得经验（0 = 该角色没有这个 ivar，也就是从没拿过经验）。"""
        return get_int(ivar(actor, "@limit_exp"), 0)

    def limit_exp_on(self, actor):
        """这个角色还有没有"经验额度"（False = 封顶了，再打也不给经验）。

        游戏脚本 `Game_Actor#gain_exp` 裁判的是 **写入前** 的值：
            if @limit_exp > 202123741  → 直接 return（这一级的经验一个字节都不给）
            else @limit_exp += exp
        所以：值 ≤ 202123741 时还有额度；一旦越过这条线，**后续获得的经验全部作废**。
        """
        node = _deref(ivar(actor, "@limit_exp"))
        if node is None:
            return True                 # 没这个 ivar 的角色不会被判封顶
        return self.limit_exp(actor) <= self.LIMIT_EXP_MAX

    def limit_exp_room(self, actor):
        """还剩多少经验额度才到线（提前提醒用）。"""
        return max(0, self.LIMIT_EXP_MAX - self.limit_exp(actor))

    def set_limit_exp(self, actor, value):
        """写累计获得经验。**只允许 0..202123741**，超了游戏就再也不发经验了。

        返回：写入的值 / None（角色没有这个 ivar，跳过）/ False（输入不合法）。
        """
        v = int(value)
        if v < 0 or v > self.LIMIT_EXP_MAX:
            return False
        node = _deref(ivar(actor, "@limit_exp"))
        if node is None:
            # 没拿过经验的角色压根没这个 ivar。硬加一个属于结构性改动
            # （整档重写 + 对象链接重排），为改个计数器不值得冒这个险。
            return None
        self.doc.set_value(node, v)
        return v

    def reset_limit_exp(self):
        """把所有角色的累计获得经验清零 —— 体验版「经验已达上限」的解法。

        返回 [(角色名, 原值), …]。零值本来就没这个 ivar，不用动。
        """
        out = []
        for _aid, actor in self.sv.actors():
            node = _deref(ivar(actor, "@limit_exp"))
            if node is None:
                continue
            old = self.limit_exp(actor)
            if old == 0:
                continue
            self.doc.set_value(node, 0)
            out.append((self.sv.actor_name(actor), old))
        return out

    # ---- 升级所需经验：**查表**，不是公式
    def actor_level(self, actor):
        return get_int(ivar(actor, "@level"), 0)

    def next_level_exp(self, actor):
        """升到下一级所需的经验（游戏界面上显示的那个数）。

        游戏里 `next_level_exp = exp_for_level(@level + 1) = $exps[:actor][@level]`
        —— 是**查表**得来的，跟存档字段无关；满级或等级越界返回 None。
        """
        return exp_for_level(self.actor_level(actor), "actor")

    def baby_next_level_exp(self, baby):
        """召唤兽的升级所需经验（同一套表，用 :baby 那张）。"""
        return exp_for_level(get_int(ivar(baby, "@level"), 0), "baby")

    def add_exp(self, actor, delta):
        return self.set_exp(actor, self.exp(actor) + int(delta))

    # ==================================================== 修炼（@sect_data[:修炼]）
    # 机制与系数见模块头「修炼」那一段。这里只做**读 / 写**两件事：
    # 写走 `doc.set_value`（标量就地补丁），不新增节点 ⇒ 不用整档重写。
    def practice_max(self, actor):
        """这个角色现在能把修炼点到几级：<90 级 → 20，≥90 级 → 25。"""
        return (PRACTICE_LV_BELOW_90 if self.actor_level(actor) < 90
                else PRACTICE_MAX_LV)

    @staticmethod
    def practice_next_exp(lv):
        """升到下一级需要的**修炼经验**（游戏 `practice_next_level_exp`）。

        `(lv² + 3lv + 11) × 10`：0→1 是 110、20→21 是 4710。
        ⚠ 这是"点修炼加多少经验"的门槛，不是角色经验 —— 每次点修炼只 +10 点。
        """
        lv = max(0, int(lv))
        return (lv * lv + lv * 3 + 11) * 10

    @classmethod
    def practice_full_exp(cls, lv):
        """某等级下的**满经验**＝差 1 点就升级（`next_exp(lv) - 1`）。

        游戏 `Game_Actor#practice_add_exp` 是「`exp >= next_exp(lv)` ⇒ 减掉门槛、
        `lv += 1`（溢出保留）」，所以**没升级时 exp 的最大值就是 `next_exp-1`**
        —— 面板那个「修炼经验」条到这儿就是满的。川 2026-10-08：拉满时经验
        也要一起拉满，做到「和游戏升到那个等级满经验一致」。
        """
        return max(0, cls.practice_next_exp(lv) - 1)

    def _practice_hash(self, actor):
        """`@sect_data[:修炼]` 那个 HashNode（8 项）。

        缺了就抛 KeyError（带人话说明）—— 不现场造结构：造出来的半截 Hash
        一旦少项，游戏的 `keys[@index]` 会取到 nil 直接报错。

        ⚠⚠ **键要比的是 `M.value_of(_deref(k))`，不能 `isinstance(k, SymbolNode)`**：
          真档里 `:门派`/`:辅助` 是 `IVarNode(inner=SymbolNode)`（盘上 `I:门派`），
          而 `:A_攻击` 这 8 项也**全是 IVarNode** —— 只有 `:修炼` 自己是裸
          `SymbolNode`。少了 `_deref` 就会「读得到 8 项但每项都是 0、写不进」，
          静默无异常（2026-10-08 探针里就是这么栽的）。
        """
        sd = _deref(ivar(actor, "@sect_data"))
        if not isinstance(sd, M.HashNode):
            raise KeyError("这个角色没有 @sect_data（门派/修炼数据）")
        for k, v in sd.pairs:
            if M.value_of(_deref(k)) == "修炼":
                h = _deref(v)
                if isinstance(h, M.HashNode):
                    return h
                raise KeyError(":修炼 不是 Hash（存档结构异常）")
        raise KeyError("这个角色还没有 :修炼 数据（游戏里没开启修炼？）")

    @staticmethod
    def _practice_field(node, name):
        """修炼项（`{lv:…, exp:…}`）里的某个字段节点；没有返回 None。"""
        if not isinstance(node, M.HashNode):
            return None
        for k, v in node.pairs:
            if M.value_of(_deref(k)) == name:
                return v
        return None

    def practice(self, actor, group=None):
        """读修炼现状。

        `group` 传 `"A"` / `"B"` 只取那一组，`None` = 8 项全给（A 组在前）。
        每项：`{key, group, group_cn, name, lv, exp, need, max, desc}`
        —— `need` = 升下一级还差多少修炼经验。
        """
        h = self._practice_hash(actor)
        mx = self.practice_max(actor)
        out = []
        for g, gcn in PRACTICE_GROUPS:
            if group is not None and g != group:
                continue
            for nm in PRACTICE_NAMES:
                key = "%s_%s" % (g, nm)
                node = None
                for k, v in h.pairs:
                    if M.value_of(_deref(k)) == key:
                        node = _deref(v)
                        break
                lv = get_int(self._practice_field(node, "lv"), 0)
                exp = get_int(self._practice_field(node, "exp"), 0)
                out.append({"key": key, "group": g, "group_cn": gcn,
                            "name": nm, "lv": lv, "exp": exp, "max": mx,
                            "need": self.practice_next_exp(lv),
                            "desc": PRACTICE_DESC.get(nm, "")})
        return out

    def practice_set(self, actor, key, lv=None, exp=None, clamp=True):
        """写一项修炼（`key` 形如 `"A_攻击"`），返回 `(lv, exp)`。

        * `clamp=True`：`lv` 夹到 `0..practice_max()`（<90 级 → 20）；`exp` 夹到
          `0..(本级门槛 - 1)`（到门槛游戏就该升级了，它自己也不会停在 ≥ 门槛）。
        * `clamp=False`：等级上限放到 `PRACTICE_MAX_LV`(25)，**无视 90 级规则**
          —— 修炼窗口里**手动直接把等级填成 25** 时用它（川 2026-10-08：手动
          可以设到 25；战斗读 lv 时本来也不校验上限，只是面板显示「25/20」）。
          「全员拉满」不用它 —— 那个走默认 `clamp=True`，逐人按游戏规则拉。
        * 传 `None` = 这一项不动。
        * 只改 `[:lv]` / `[:exp]` 两个整数节点，别的一律不碰。
        """
        h = self._practice_hash(actor)
        mx = self.practice_max(actor) if clamp else PRACTICE_MAX_LV
        node = None
        for k, v in h.pairs:
            if M.value_of(_deref(k)) == key:
                node = _deref(v)
                break
        if not isinstance(node, M.HashNode):
            raise KeyError("存档里没有修炼项 %s" % key)
        n_lv = self._practice_field(node, "lv")
        n_exp = self._practice_field(node, "exp")
        if n_lv is None or n_exp is None:
            raise KeyError("修炼项 %s 结构不对（缺 lv / exp）" % key)
        out_lv = get_int(n_lv, 0) if lv is None else int(lv)
        out_lv = max(0, min(out_lv, mx))
        out_exp = get_int(n_exp, 0) if exp is None else int(exp)
        out_exp = max(0, out_exp)
        if out_lv < mx and out_exp > self.practice_next_exp(out_lv) - 1:
            out_exp = self.practice_next_exp(out_lv) - 1
        self.doc.set_value(_deref(n_lv), out_lv)
        self.doc.set_value(_deref(n_exp), out_exp)
        return out_lv, out_exp

    def practice_set_group(self, actor, group, lv=None, exp=0, clamp=True):
        """整组一起设（一键满级 / 清零），返回改了几项。

        `lv=None` = 等级保持原样，只动经验。`clamp=False` 见 `practice_set`。
        """
        n = 0
        for row in self.practice(actor, group):
            self.practice_set(actor, row["key"],
                              lv=row["lv"] if lv is None else lv, exp=exp,
                              clamp=clamp)
            n += 1
        return n

    def practice_set_everyone(self, lv=None, exp=None, groups=None,
                              skip_ids=PRACTICE_SKIP_IDS):
        """**所有角色** × 每组 4 项，等级一起拉满（经验默认也一起拉满）。

        * `lv=None`（默认）＝**按游戏规则逐人拉满**：`<90 级 → 20、≥90 级 → 25`
          （每人取自己的 `practice_max()`，走 `clamp=True`）—— 川 2026-10-08：
          「全员拉满也按游戏规则」。要**无视规则**直接全给 25，显式传 `lv=25`
          （那时走 `clamp=False`，游戏面板会显示「25/20」，战斗照吃满加成）。
        * `exp=None`（默认）＝**本级满经验** `practice_full_exp(lv)`（＝门槛-1）；
          想归零就显式传 `exp=0`。
        * `skip_ids` 里的角色整人跳过（默认 `PRACTICE_SKIP_IDS` = 巨小蛙）；
          按 `@actor_id` 判，不按名字。
        * `groups=None` = A + B 全给。没有 `@sect_data[:修炼]` 的角色**跳过不报错**
          （只有 NPC / 半截数据才会缺），人名进 `skipped`。

        返回 `(改了几人, 改了几项, 跳过的人名列表)`。
        """
        gl = [g for g, _cn in PRACTICE_GROUPS] if groups is None else list(groups)
        keys = ["%s_%s" % (g, nm) for g in gl for nm in PRACTICE_NAMES]
        skip_ids = tuple(skip_ids or ())
        skipped, n_actor, n_item = [], 0, 0
        for _aid, actor in self.sv.actors():
            if get_int(ivar(actor, "@actor_id"), -1) in skip_ids:
                skipped.append(self.sv.actor_name(actor))
                continue
            try:
                for key in keys:
                    use_lv = self.practice_max(actor) if lv is None else lv
                    use_exp = (self.practice_full_exp(use_lv)
                               if exp is None else exp)
                    self.practice_set(actor, key, lv=use_lv, exp=use_exp,
                                      clamp=(lv is None))
            except KeyError:
                skipped.append(self.sv.actor_name(actor))
                continue
            n_item += len(keys)
            n_actor += 1
        return n_actor, n_item, skipped

    # ==================================================== 角色技能（@skills）
    # 2026-09-20 加的一层：角色技能可视化编辑要用。
    # 游戏脚本里确认过的几件事（都跟召唤兽不一样，别照抄 jxbaby 的写法）：
    #   * `Game_Actor#learn_skill` 只去重 + `sort!`，**没有数量上限**
    #     （召唤兽 `Game_Baby#learn_skill` 才有 `@skills.length < 12`）；
    #   * 游戏里「实际能用」的技能 = `(@skills | added_skills | equip_skills(:skill)).sort`
    #     —— 这里只编 `@skills`（= `original_skills`），装备/升级给的技能不写回去；
    #   * `@shortcut_key_skill`（F1~F9 绑定）读的时候有
    #     `actor.skill_learn?(get_skill(id))` 守卫 → 删技能**不用**同步清理快捷键。
    def actor_skills(self, actor):
        """角色已学技能 id 列表（存档里的 `@skills`，游戏里叫 `original_skills`）。

        ⚠ 这是**原始技能**那一份，不等于游戏里实际能用的技能（还有装备/added
        两个来源，游戏运行时才并起来）。要改就改这一份。
        """
        return [int(s) for s in self.sv.skills(actor)]

    def actor_set_skills(self, actor, ids):
        """整份写 `@skills`（去重 + 升序，和游戏 `learn_skill` 的 `sort!` 对齐）。

        **角色技能没有数量上限** —— 不像 `babies.set_skills` 那样截断到 12。
        数组元素个数会变 → 必须 `mark_structural()`，保存时整档重写。
        """
        ids = sorted({int(s) for s in ids})
        arr = M.ArrayNode([int_node(s) for s in ids])
        if not set_ivar(actor, "@skills", arr):
            # set_ivar 只替换已存在的 ivar；老角色没这个字段就追加一个
            actor.ivars.append(("@skills", arr))
        self.doc.mark_structural()
        return ids

    def actor_learn_skill(self, actor, skill_id):
        """学一个技能（已经有了就原样返回，不重复加）。"""
        ids = self.actor_skills(actor)
        sid = int(skill_id)
        if sid in ids:
            return ids
        ids.append(sid)
        return self.actor_set_skills(actor, ids)

    def actor_forget_skill(self, actor, skill_id):
        """忘掉一个技能（没有这个技能也不报错）。"""
        sid = int(skill_id)
        return self.actor_set_skills(
            actor, [s for s in self.actor_skills(actor) if s != sid])

    def actor_learn_many(self, actor, skill_ids):
        """一次学一批技能，返回 `（新学会的, 本来就已经会的）`。

        ⚠ 别在循环里调 `actor_learn_skill`：`actor_set_skills` 每次都
        `mark_structural()` 并整份重写 `@skills` 数组 —— 批量只该写一次，
        写 N 次等于把整档重解析 N 遍（技能管理器一次勾几十个时会很明显）。
        """
        ids = self.actor_skills(actor)
        have = set(ids)
        want = sorted({int(s) for s in skill_ids})
        added = [s for s in want if s not in have]
        if added:
            self.actor_set_skills(actor, ids + added)
        return added, [s for s in want if s in have]

    def actor_forget_many(self, actor, skill_ids):
        """一次忘一批技能，返回 `（真正忘掉的, 本来就没有的）`。

        「本来就没有」的照常算成功（游戏 `forget_skill` 也不报错），只是
        分开返回，界面上好说清"实际动了几个"。
        """
        ids = self.actor_skills(actor)
        have = set(ids)
        want = sorted({int(s) for s in skill_ids})
        drop = [s for s in want if s in have]
        if drop:
            gone = set(drop)
            self.actor_set_skills(actor, [s for s in ids if s not in gone])
        return drop, [s for s in want if s not in have]

    def actor_clear_skills(self, actor):
        return self.actor_set_skills(actor, [])

    def valid_skill_ids(self):
        """{技能 id: 名字}（Data\\Skills 表，带缓存）—— 挑技能 / 校验用。

        走 `datatables.name_map()`：读不到游戏目录会自动退回**内置名字表**，
        所以这里不再单独兜底（原来读不到会整片空掉，技能一览全 `?`）。
        """
        if getattr(self, "_skill_ids", None) is None:
            import datatables
            try:
                self._skill_ids = dict(datatables.name_map("Skills"))
            except Exception:
                self._skill_ids = {}
        return self._skill_ids

    # ==================================================== 门派（存档 @sect_id）
    # ⚠ 门派**不是** Data 表 —— 是游戏脚本里硬编码的 `$sects`（表见 `sect`）。
    #   正常游戏里角色能学的技能 = 本门派 `skills` 那一串（10 个、凌波城 12 个，
    #   外加每个门派 index 10 那一个「上古××」秘技）：走 `Window_Actor_Skill` 的
    #   「门派」页，攒 `@sect_data[:门派][id]` 攒满 `max` 才 `learn_skill` 写进 `@skills`。
    #   辅助技能（强身术/冥想/…）和修炼只加属性，**不进 `@skills`**。
    def actor_sect_id(self, actor):
        """角色的门派 id（存档 `@sect_id`）；没这个字段返回 None。

        `0` = 无门派（`Game_Actor#setup` 里的初值，之后由事件改写）。
        """
        n = ivar(actor, "@sect_id")
        if n is None:
            return None
        v = get_int(_deref(n), -1)
        return None if v < 0 else v

    def actor_sect_name(self, actor):
        """角色门派的中文名（认不出的 id → None）。"""
        sid = self.actor_sect_id(actor)
        return sect.sect_name(sid) if sid is not None else None

    def sect_skills(self, actor):
        """该角色**本门派**的技能 id 列表（无门派 / 认不出 → 空列表）。"""
        sid = self.actor_sect_id(actor)
        return list(sect.sect_skill_ids(sid)) if sid is not None else []

    def set_actor_sect(self, actor, sect_id):
        """改角色门派：**只写 `@sect_id`**，返回写进去的 id。

        为什么只写这一个字段（2026-09-27 查过脚本，见 `docs/待解决问题.md` 的「门派修改」一节）：
          * 门派在存档里就这一个整数，脚本里读它 11 处、**一处都没写**（换门派是
            事件脚本干的）→ 写它等于照游戏自己的机制办；
          * `@sect_data`（`:门派` 攒次数 / `:辅助` / `:修炼`）**与门派无关**，不用动；
            留着旧门派的计数无害，切回去还能接着原来的进度；
          * `@skills` 也不用动：`Game_Actor#learn_skill`(6017) 只 push+sort!、
            **从不清理**，游戏里换门派后旧门派技能本来就留着；
          * `$jiance` 不查门派、不查技能 → 不算作弊。

        ⚠ 只允许 `sect.SECTS` 里有的 id（2026-10-04 起＝ `0` 无门派、
          `1..13`、**`20` 九黎城** —— **不是 0..12 连号**）：`$sects` 是
          **没有 default 的普通 Hash**，写个不存在的 id，游戏一开菜单就
          `$sects[id][:name]` → `nil[:name]` 崩（35285 / 37033 是所有角色一起画，
          所以是**全员崩菜单**）。判「认不认识」一律查表，别写区间。
          另外 `0`（无门派）会让游戏里快捷技能栏不可用、门派技能页隐藏 —— 能用，
          但那是**减功能**，界面上要不要给这个入口另说。
        """
        v = int(sect_id)
        if v not in sect.SECTS:
            raise ValueError("门派 id 只能是 %s（收到 %r）"
                             % ("/".join("%d" % k for k in sorted(sect.SECTS)),
                                sect_id))
        self.sv.set_actor_field(actor, "@sect_id", v)
        return v

    def actor_class_learnings(self, actor):
        """角色**职业自带**的技能 id（`Data\\Classes[class_id].@learnings` 里
        等级已经够的那些）—— 游戏 `init_skills` 就是照这个发技能的。

        ⚠ 门派技能不从这里来（那是「门派」页点名学会的），别把两者混一起：
          角色 `@skills` = 职业自带（如 id 9「牛刀小试」）+ 本门派技能。

        ⚠ 走 `datatables.class_learnings()`：读不到游戏目录时它退回**内置表**。
          这里要是自己吞异常返回空，「清空门派」就会把技能清光而不是重置成天生技能。
        """
        import datatables
        cid = get_int(_deref(ivar(actor, "@class_id")), 0)
        lv = self.actor_level(actor)
        cache = getattr(self, "_cls_learn_cache", None)
        if cache is None:
            cache = self._cls_learn_cache = {}
        key = (cid, lv)
        if key in cache:
            return cache[key]
        out = []
        try:
            for slv, sid in datatables.class_learnings(cid):
                if sid and slv <= lv:
                    out.append(sid)
        except Exception:
            out = []
        out = sorted(set(out))
        cache[key] = out
        return out

    def actor_reset_skills_to_class(self, actor):
        """把 `@skills` 重置成**职业自带技能**（天生技能），返回留下的 id 列表。

        就是游戏 `Game_Actor#clear_skills`(5756) + `init_skills`(5747) 的结果：
        `@skills = []` → 再按 `self.class.learnings` 里 `@level` 已经够的那些补回来。
        「清空门派」用它把角色退回「没门派、只会天生技能」的状态。

        ⚠ 这会**丢掉**所有非天生技能 —— 门派技能、技能书/剧情给的技能一视同仁。
          游戏自己换门派时**不**这么做（`learn_skill` 只 push + 排序、从不清理），
          所以界面上必须明确告知，别让人以为这是游戏行为。
        """
        keep = self.actor_class_learnings(actor)
        self.actor_set_skills(actor, keep)
        return keep

    # ---------------------------------------------------- 门派称谓（@appellations）
    # 游戏里叫「称谓」：`@appellations = [[称谓...], 下标]`，下标 -1 = 不显示任何称谓。
    # 游戏侧：5549 初始化 `[[], -1]` / 5569 add_appellation / 5574 remove_appellation
    # （顺手把下标打成 -1）/ 5576 get_appellation / 5578 set_appellation。
    # ⚠ 门派称谓（「五庄观弟子」这种）**不是表**，是拜师事件里硬编码的
    #   `add_appellation('五庄观弟子')`，12 个门派各一处 —— 见 `sect_appellation`。
    def actor_appellations(self, actor):
        """角色的称谓列表 + 当前显示下标（读不到就 `[]` / `-1`）。"""
        arr = _deref(ivar(actor, "@appellations"))
        if not isinstance(arr, M.ArrayNode) or len(arr.items) < 2:
            return [], -1
        out = []
        lst = _deref(arr.items[0])
        if isinstance(lst, M.ArrayNode):
            for it in lst.items:
                t = _as_str(it)
                if t:
                    out.append(t)
        try:
            idx = int(M.value_of(_deref(arr.items[1])))
        except (TypeError, ValueError):
            idx = -1
        return out, (idx if 0 <= idx < len(out) else -1)

    def set_actor_appellations(self, actor, names, index=-1):
        """整份写 `@appellations`（`[[称谓...], 下标]`），返回 `(names, index)`。

        ⚠ 数组元素个数会变 → `mark_structural()`（保存时整档重写）。
        """
        names = [str(n) for n in names]
        arr = M.ArrayNode([M.ArrayNode([str_node(n) for n in names]),
                           M.IntNode(int(index))])
        if not set_ivar(actor, "@appellations", arr):
            # 老档没有这个字段就追加一个（和 actor_set_skills 一个路子）
            actor.ivars.append(("@appellations", arr))
        self.doc.mark_structural()
        return names, int(index)

    def sect_appellation_name(self, sect_id):
        """某个门派的**称谓**（「五庄观弟子」这种）；无门派 / 认不出 → None。

        界面只从这里取名，别去 `tables.sect_appellation` 里翻 —— 免得两边口径不一。
        """
        return sect_appellation.sect_appellation(sect_id)

    def sect_appellations_of(self, actor):
        """角色身上那些**门派称谓**：`[(称谓, 门派 id), ...]`。"""
        names, _idx = self.actor_appellations(actor)
        out = []
        for n in names:
            sid = sect_appellation.sect_of_appellation(n)
            if sid is not None:
                out.append((n, sid))
        return out

    def set_actor_sect_appellation(self, actor, sect_id):
        """换门派时同步称谓：**回收**所有门派称谓，再按新门派补上那一个。

        返回 `(removed, added, names, index)`。
        * `sect_id` 为 0（无门派）→ 只回收、不补，下标打成 -1（游戏
          `remove_appellation` 也是把下标打成 -1）；
        * 换门派时如果原来显示的就是门派称谓 → 直接改成显示新称谓。

        ⚠ 游戏自己**只加不删**：全 Data 扫过，`add_appellation` 有调用、
          `remove_appellation` 一处调用都没有；而且游戏不让改门派
          （拜师对话写着「拜师后不可更改」）。所以「回收旧称谓」是工具额外做的，
          界面上得写明。
        """
        try:
            sid = int(sect_id or 0)
        except (TypeError, ValueError):
            sid = 0
        names, idx = self.actor_appellations(actor)
        cur = names[idx] if 0 <= idx < len(names) else None
        removed = [n for n in names
                   if sect_appellation.sect_of_appellation(n) is not None]
        kept = [n for n in names if n not in set(removed)]
        want = sect_appellation.sect_appellation(sid)
        added = []
        if want and want not in kept:
            kept.append(want)
            added.append(want)
        if cur is not None and cur not in removed:
            new_idx = kept.index(cur)
        elif want and want in kept:
            new_idx = kept.index(want)
        else:
            new_idx = -1
        # ⚠ 判「有没有变」要看**结果**，别只看 removed/added：门派称谓正好是
        #   新门派那个时（如已经是「地府弟子」再转一次地府），removed 和 added
        #   都非空但结果一模一样 —— 那种情况写下去纯属白标 structural。
        if kept == names and new_idx == idx:
            return [], [], names, idx
        self.set_actor_appellations(actor, kept, new_idx)
        return removed, added, kept, new_idx

    def off_sect_skills(self, actor):
        """角色已学、但**既不是本门派、也不是职业自带**的技能。

        ⚠ 别把它当成「改出来的」证据（2026-09-20 拿真档核过）：游戏里
        **换门派**是完全可能的 —— `@sect_id` 是 `attr_accessor`（脚本 5484，
        初值 0 见 5512），脚本里再没赋过值，也就是说它由**剧情事件的脚本**
        直接写；而 `Game_Actor#learn_skill`(6017) 只 push + 排序，**从不清理**
        换门派前学过的技能。所以玩家身上出现"非当前门派"技能是正常的
        （实测李修远：门派五庄观，`@skills` 里却留着 247/253/254 三个普陀山技能，
        而 `@sect_data[:门派]` 里根本没有它们）。
        另外剧情事件（指令 319 → `Game_Actor#learn_skill`）也能直接发技能。

        所以这里只当「不属于当前门派体系的技能」列出来给个信息，
        不下"作弊"结论。返回 [(技能 id, 名字), ...]。
        """
        allowed = set(self.sect_skills(actor)) | set(self.actor_class_learnings(actor))
        names = self.valid_skill_ids()
        return [(s, names.get(s, "")) for s in self.actor_skills(actor)
                if s not in allowed]

    # ==================================================== 召唤兽
    def babies(self, actor):
        arr = _deref(ivar(actor, "@babys"))
        out = []
        if isinstance(arr, M.ArrayNode):
            for i, b in enumerate(arr.items):
                bb = _deref(b)
                if isinstance(bb, M.ObjNode):
                    out.append((i, bb))
        return out

    def active_baby(self, actor):
        b = _deref(ivar(actor, "@baby"))
        return b if isinstance(b, M.ObjNode) else None

    def baby_name(self, baby):
        a = _deref(ivar(baby, "@attr"))
        if isinstance(a, M.ObjNode):
            n = _as_str(ivar(a, "@name"))
            if n:
                return n
        return _as_str(ivar(baby, "@name")) or "?"

    def baby_attr(self, baby):
        a = _deref(ivar(baby, "@attr"))
        return a if isinstance(a, M.ObjNode) else None

    def baby_max_attr(self, baby):
        """这只召唤兽**当前**的资质硬上限 `{atk: …, grow: …}`；读不到返回 None。

        上限跟着 `@attr.@promote` 走（未进阶 `类型` / 已进阶 `类型_p`），
        照游戏 `BabyManager.get_attr_max` 的口径。
        """
        a = self.baby_attr(baby)
        if a is None:
            return None
        t = _as_str(ivar(a, "@type")) or ""
        p = _deref(ivar(a, "@promote"))
        return baby_aptitude.max_attr(t, bool(M.value_of(p)) if p is not None else False)

    def baby_over_cap(self, baby):
        """返回**超过当前上限**的资质 `{键: (存档值, 上限)}`；空 dict = 都没超。

        超上限**不是错误**：游戏读值一律 `min(@值, 上限)`，召唤兽面板上把上限那个
        数画成**红色**（2026-10-08 川的档实测：涂山雪 atk/def 存 2100、上限 2000、
        面板红字 2000）。工具只如实提示，**不改这个数**。
        """
        cap = self.baby_max_attr(baby) or {}
        out = {}
        for k, ck in self.BABY_ZIZHI.items():
            v = self.baby_value(baby, k)
            hi = cap.get(ck)
            if v is None or hi is None:
                continue
            try:
                if float(v) > float(hi):
                    out[k] = (v, hi)
            except (TypeError, ValueError):
                continue
        return out

    def baby_promote(self, baby):
        """这只召唤兽是否已进阶（`@attr.@promote`）。"""
        a = self.baby_attr(baby)
        if a is None:
            return False
        p = _deref(ivar(a, "@promote"))
        return bool(M.value_of(p)) if p is not None else False

    #: (键, 说明, ivar 路径, 类型)
    BABY_FIELDS = (
        ("level", "等级（上限 65）", "@level", "int"),
        ("hp", "气血（HP）", "@hp", "int"),
        ("mp", "魔法（MP）", "@mp", "int"),
        ("tp", "TP", "@tp", "int"),
        ("exp", "当前经验", "@exp#", "int"),
        # ⚠ 门槛是 `Config::Baby::ALLOW_LOYALTY` = **60**，不是 100（以前写错过）。
        # 100 只是上限：`add_loyalty` / `dec_loyalty` 都 `limit(0, max_loyalty)`。
        ("loyalty", "忠诚度（<%d 不能参战）" % BABY_ALLOW_LOYALTY,
         "@attr.@loyalty", "float"),
        ("life", "寿命（上限 12000）", "@attr.@life", "int"),
        ("grow", "成长", "@attr.@grow", "float"),
        ("atk", "攻击资质", "@attr.@atk", "int"),
        ("def", "防御资质", "@attr.@def", "int"),
        ("hpq", "体力资质", "@attr.@hp", "int"),
        ("mpq", "法力资质", "@attr.@mp", "int"),
        ("agi", "速度资质", "@attr.@agi", "int"),
        ("eva", "躲闪资质", "@attr.@eva", "int"),
        # 五行（2026-09-27 新增）：炼妖合宠时和另一只比「相生 / 相克」——
        # 游戏 `Window_Demon#implement` 按生/克/无 给不同的结果概率
        # （生 60/30/7/3、克 35/35/28/2、无 50/38/8/4）。
        # ⚠ 存档里是 **String**（Marshal `"`），值只能是 fieldnames.BABY_FIVE。
        ("five", "五行", "@attr.@five", "str"),
        ("体质", "体质", "@attr.@体质", "int"),
        ("法力", "法力", "@attr.@法力", "int"),
        ("力量", "力量", "@attr.@力量", "int"),
        ("耐力", "耐力", "@attr.@耐力", "int"),
        ("敏捷", "敏捷", "@attr.@敏捷", "int"),
        ("潜能", "潜能", "@attr.@潜能", "int"),
    )

    @classmethod
    def baby_field_type(cls, key):
        """给界面用：这个字段是 `int` / `float` / `str`（五行）。认不出返回 None。"""
        for k, _label, _path, typ in cls.BABY_FIELDS:
            if k == key:
                return typ
        return None

    #: 上面字段里**属于「资质」**的那几个（键 → `baby_aptitude.ATTR_KEYS` 的名字）。
    #: 游戏里它们有硬上限，写超了 `Game_Baby_Attr#get_* = min(@值, 上限)` 直接夹住
    #: ⇒ 存档里存 2100、游戏里显示 2000，看着像"改了没效果"。
    BABY_ZIZHI = {"atk": "atk", "def": "def", "hpq": "hp", "mpq": "mp",
                  "agi": "agi", "eva": "eva", "grow": "grow"}

    def _resolve(self, baby, path):
        if path == "@exp#":
            return self._exp_node(baby)
        node = baby
        for part in path.split("."):
            node = _deref(ivar(node, part))
            if node is None:
                return None
        return node

    def _exp_node(self, baby):
        h = _deref(ivar(baby, "@exp"))
        if isinstance(h, M.HashNode) and h.pairs:
            return _deref(h.pairs[0][1])
        return None

    def baby_value(self, baby, key):
        for k, _label, path, typ in self.BABY_FIELDS:
            if k == key:
                node = self._resolve(baby, path)
                if node is None:
                    return None
                n = _deref(node)
                if typ == "str":
                    # 五行（@five）= Marshal String（StrNode.data 存的是字节）
                    return _as_str(node)
                if isinstance(n, M.SymbolNode):
                    return n.name          # 神兽的寿命是 :infinite（永生）
                return (get_float(node) if typ == "float" else get_int(node))
        return None

    def _resolve_parent(self, baby, path):
        """返回 (父节点, ivar 名)——换整个节点时用（比如把 :infinite 换成数字）。"""
        parts = path.split(".")
        node = baby
        for p in parts[:-1]:
            node = _deref(ivar(node, p))
            if node is None:
                return None, parts[-1]
        return node, parts[-1]

    def _apply_level_delta(self, attr_node, delta):
        """level 改了后，潜能/五维跟着调整（照抄游戏 `Game_Actor_Attr#level_up`）。

        游戏脚本（5371）：
            def level_up
              @体质 += 1; @法力 += 1; @力量 += 1; @耐力 += 1; @敏捷 += 1
              @潜能 += 5
            end
        降级：洗点（五维 + 潜能全清零 = 超级金柳露语义）。

        ⚠ 2026-09-20 修 bug：以前这里写的是 `ivar(attr_node, k[1:])`（把 `@` 去掉了），
        而 `save.ivar(obj, name)` 是**按名字精确比对** `k == name`（名字自带 `@`）
        —— 于是每次都返回 None 直接 continue，**这段逻辑从来没生效过**：
        点「满级」等级变了，潜能/五维一个点都没加（真档实测：60 级仍是 潜能 0 / 五维 79）。
        现在传完整名字 `@xxx`。
        """
        if delta == 0 or attr_node is None:
            return
        if delta > 0:
            for k in ("@潜能", "@体质", "@法力", "@力量", "@耐力", "@敏捷"):
                n = ivar(attr_node, k)          # ⚠ 必须带 `@`（见 docstring）
                if n is None: continue
                cur = get_int(n, 0)
                add = delta * 5 if k == "@潜能" else delta
                self.doc.set_value(n, cur + add)
        else:
            for k in ("@潜能", "@体质", "@法力", "@力量", "@耐力", "@敏捷"):
                n = ivar(attr_node, k)          # ⚠ 必须带 `@`
                if n is None: continue
                self.doc.set_value(n, 0)

    def baby_exp_full(self, baby):
        """「一键满级」：召唤兽等级顶到 65 + `@exp` 对齐 65 级门槛。

        ⚠ 召唤兽确实会**自己**升级（`Game_Baby#change_exp` 第 7014 行
        `level_up(must) while !max_level? && self.exp >= next_level_exp && ...`），
        但有两条硬天花板，光写 `@exp` 顶不到 65：
          * 第 7006 行 `!must and @level - 5 >= @master.level` → 直接拒收经验
            （`$tip.say` 提示"超出主人 5 级，无法获得经验"）；
          * 第 7014 行循环条件同样卡 `@level - 5 < @master.level`。
        也就是说经验升级最多到「主人等级 + 5」。主人不满级就顶不到 65。
        另外战斗结算走的是 `BattleManager.gain_exp`(1845)，只遍历
        `$game_party.battle_members`，**根本不发经验给召唤兽**。
        所以这里同样直接写等级 + 经验。

        返回 (等级, 写进 @exp 的值 / None)。
        """
        self.set_baby(baby, "level", MAX_LEVEL_BABY)
        wrote = None
        tbl = exp_for_level(MAX_LEVEL_BABY, "baby")
        node = self._exp_node(baby)
        if tbl is not None and node is not None:
            self.doc.set_value(node, int(tbl))
            wrote = int(tbl)
        return MAX_LEVEL_BABY, wrote

    def baby_exp_fill(self, baby):
        """「经验拉满」（召唤兽页按钮，2026-10-03 川要求）：只把 `@exp` 写到
        `BABY_EXP_FILL`，**不动等级**。

        和 `baby_exp_full`（界面「一键满级」）的唯一区别 = 不写 `@level`。
        ⚠ 但召唤兽和人物不同：`Game_Baby#change_exp`(7014) 里带升级循环
        （`level_up(must) while !max_level? && exp >= next_level_exp
          && @level - 5 < @master.level`），所以**下一场战斗结算**它自己就会连升，
        顶到「主人等级 + 5」（主人不满级就顶不到 MAX_LEVEL_BABY）。
        「等级不动」只保证写进去的那一刻不变。返回写进 @exp 的值 / None。
        """
        node = self._exp_node(baby)
        if node is None:
            return None
        self.doc.set_value(node, int(BABY_EXP_FILL))
        return int(BABY_EXP_FILL)

    def set_baby(self, baby, key, value):
        old_lv = None
        if key == "level":
            old_lv = self.baby_value(baby, "level")
        for k, _label, path, typ in self.BABY_FIELDS:
            if k != key:
                continue
            node = self._resolve(baby, path)
            if node is None:
                raise KeyError("召唤兽没有 %s（%s）" % (k, path))
            if typ == "str":
                # 五行：只能是 金木水火土（游戏 `$baby` 表的 `five` proc）
                s = str(value).strip()
                if s not in BABY_FIVE:
                    raise ValueError("五行只能是 %s（给的是 %r）"
                                     % ("、".join(BABY_FIVE), value))
                if isinstance(_deref(node), M.StrNode):
                    self.doc.set_value(node, s)
                else:
                    # 万一不是字符串节点（没见过的档）：整个换掉
                    parent, leaf = self._resolve_parent(baby, path)
                    if parent is None or not set_ivar(parent, leaf, str_node(s)):
                        raise KeyError("改不了 %s（%s）" % (k, path))
                    self.doc.mark_structural()
                return s
            if isinstance(_deref(node), M.SymbolNode):
                # 例如神兽的 @life = :infinite：整个换成数字节点
                parent, leaf = self._resolve_parent(baby, path)
                if parent is None or not set_ivar(parent, leaf, int_node(int(value))):
                    raise KeyError("改不了 %s（%s）" % (k, path))
                self.doc.mark_structural()
                return value
            # ⚠ 这里**故意不夹上限**。资质确实有游戏硬上限（`$baby[:_max]`，未进阶 /
            #   已进阶两档），但**存档里超过上限的值是合法且有意义的** —— 2026-10-08
            #   翻川的档实测：李修远那只涂山雪 `@atk/@def` 存 2100，当前上限 2000，
            #   游戏面板画 `min(值, 上限)` = **2000 并标红**（红字就是"超限了"）。
            #   上一版在这儿夹住是**错的**：老档超限值一点「资质+100」就会**被降到
            #   上限**（数字反而变小）。是否超限交给 `baby_over_cap()` 如实提示。
            if typ == "float":
                self.doc.set_value(node, float(value))
            else:
                self.doc.set_value(node, int(value))
            # level 改了 → 潜能/五维自动跟着调整
            if old_lv is not None:
                try:
                    new_lv = int(value)
                    attr = _deref(ivar(baby, "@attr"))
                    self._apply_level_delta(attr, new_lv - old_lv)
                except Exception:
                    pass
            return value
        raise KeyError("不认识的召唤兽字段 %r" % key)

    def set_loyalty_all(self):
        """一键：把**所有角色**身上的**所有召唤兽**忠诚拉到上限。返回 (几只, 几个角色)。

        游戏里忠诚只有**一个作用** —— `Game_Baby_Attr#is_loyalty?`：
            @loyalty >= Config::Baby::ALLOW_LOYALTY(60)
        决定这只能不能参战（战斗前检查、召唤兽界面的「出战」都查它）。
        **没有任何属性 / 成长 / 经验加成**；`$jiance`（反作弊）也完全不看忠诚
        （它只查角色等级、出战宠等级、金钱、仓库页），所以一次全改不会带出副作用。

        ⚠ 上限 100 是游戏硬规定：`add_loyalty` / `dec_loyalty` 里都
        `@loyalty = @loyalty.limit(0, max_loyalty)`，而 `max_loyalty` 就是
        `Config::Game::MAX_BABY_LOYALTY = 100`。写更高也没意义 —— 打完一场战斗
        结束扣 0.25 时会被**一次性夹回 100**（战斗里死了扣 2）。
        """
        touched = 0
        actors = 0
        for _aid, actor in self.sv.actors():
            hit = False
            for _i, baby in self.babies(actor):
                try:
                    cur = self.baby_value(baby, "loyalty")
                except Exception:
                    cur = None
                if cur is None:
                    continue
                try:
                    same = abs(float(cur) - float(MAX_BABY_LOYALTY)) < 1e-9
                except (TypeError, ValueError):
                    same = False
                if same:
                    continue
                try:
                    self.set_baby(baby, "loyalty", MAX_BABY_LOYALTY)
                except Exception:
                    continue
                touched += 1
                hit = True
            if hit:
                actors += 1
        return touched, actors

    def set_state_all(self):
        """「全员状态拉满」：**所有角色**身上的**所有召唤兽** ——
        气血 / 魔法 / 愤怒 回满 + 忠诚拉满。

        2026-10-03 川要求：把老的「回满气血/魔法」（只动当前选中那只）和
        「全员忠诚满」合成一个按钮。语义 = 两者取并集，一次把全体拉满。

        上限沿用旧「回满气血/魔法」预设的写法：hp/mp → 99999、tp → 200
        （游戏对召唤兽气血没有硬上限检查，战斗结算按 max_hp 夹）。
        忠诚上限 100 是游戏硬规定（`add_loyalty` 里 limit），
        详见 `set_loyalty_all`。

        返回 (改了几只, 涉及几个角色, 其中忠诚被改了几只)。
        """
        touched = 0
        actors = 0
        n_loy = 0
        for _aid, actor in self.sv.actors():
            hit = False
            for _i, baby in self.babies(actor):
                changed = False
                for k, v in (("hp", 99999), ("mp", 99999), ("tp", 200)):
                    try:
                        cur = self.baby_value(baby, k)
                    except Exception:
                        cur = None
                    if cur is None:
                        continue
                    try:
                        if float(cur) != float(v):
                            self.set_baby(baby, k, v)
                            changed = True
                    except Exception:
                        continue
                try:
                    cur = self.baby_value(baby, "loyalty")
                except Exception:
                    cur = None
                if cur is not None:
                    try:
                        same = abs(float(cur) - float(MAX_BABY_LOYALTY)) < 1e-9
                    except (TypeError, ValueError):
                        same = False
                    if not same:
                        try:
                            self.set_baby(baby, "loyalty", MAX_BABY_LOYALTY)
                            changed = True
                            n_loy += 1
                        except Exception:
                            pass
                if changed:
                    touched += 1
                    hit = True
            if hit:
                actors += 1
        return touched, actors, n_loy

    def baby_preset(self, baby, what):
        """常用预设：一键满级 / 经验拉满 / 回满 / 忠诚满 / 寿命满 / 资质 ±。

        ⚠ 没有「满级」预设了（2026-09-20 去掉）：等级不再单独改，
        要满级就用 `expfull` —— 它连着等级一起写；只想给经验用 `expfill`。
        """
        did = []
        if what == "expfull":
            lv, wrote = self.baby_exp_full(baby)
            did.append("等级→%d、经验→%s"
                       % (lv, "满级门槛" if wrote is not None else "（取不到门槛）"))
        elif what == "expfill":
            wrote = self.baby_exp_fill(baby)
            did.append("经验→%s（等级不动）"
                       % ("%d 万" % (wrote // 10000) if wrote is not None
                          else "（取不到 @exp）"))
        elif what == "heal":
            for k, v in (("hp", 99999), ("mp", 99999), ("tp", 200)):
                if self.baby_value(baby, k) is not None:
                    self.set_baby(baby, k, v)
            did.append("回满气血/魔法")
        elif what == "loyalty":
            self.set_baby(baby, "loyalty", MAX_BABY_LOYALTY)
            did.append("忠诚→%d" % MAX_BABY_LOYALTY)
        elif what == "life":
            self.set_baby(baby, "life", MAX_BABY_LIFE)
            did.append("寿命→%d" % MAX_BABY_LIFE)
        elif what in ("qual", "qual500"):
            # ⚠ 纯加法、**不夹上限**：超上限的值在存档里合法，游戏面板会把它标红
            #   并显示成上限那个数（2026-10-08 实测川的档：atk/def 存 2100、上限
            #   2000、面板红字 2000）。超没超由界面用 `baby_over_cap()` 提示。
            step = 100 if what == "qual" else 500
            for k in ("atk", "def", "hpq", "mpq", "agi", "eva"):
                v = self.baby_value(baby, k)
                if v is not None:
                    self.set_baby(baby, k, v + step)
            did.append("六项资质 +%d" % step)
        elif what == "grow":
            v = self.baby_value(baby, "grow")
            if v is not None:
                self.set_baby(baby, "grow", round(v + 0.1, 2))
                did.append("成长 +0.1")
        # ⚠ 键名是 `five10` 不是 `five`（2026-09-27 改）：`five` 现在是
        #   BABY_FIELDS 里的**字段键**（五行 `@attr.@five`）。两者虽不同命名空间
        #   （一个是预设名、一个是字段名）不冲突，但同一个 `"five"` 两种含义
        #   迟早看错，所以预设改叫 five10（＝五维各 +10）。
        elif what == "five10":
            for k in ("体质", "法力", "力量", "耐力", "敏捷"):
                v = self.baby_value(baby, k)
                if v is not None:
                    self.set_baby(baby, k, v + 10)
            did.append("五维 +10")
        elif what == "reset_attr":
            r = self.baby_reset_attr(baby)          # 洗点（宠物版，见下方定义）
            if r is None:
                did.append("没有 @attr，跳过")
            else:
                did.append("洗点：五维→%d/维、潜能→%d" % (r[0], r[1]))
        return did

    def baby_skills(self, baby):
        arr = _deref(ivar(baby, "@skills"))
        if not isinstance(arr, M.ArrayNode):
            return []
        import datatables
        try:
            nm = datatables.name_map("Skills")
        except Exception:
            nm = {}
        return [(M.value_of(_deref(x)), nm.get(M.value_of(_deref(x)), "?"))
                for x in arr.items]

    # ---- 重置加点 ＝ 游戏里「拜师」那一下的洗点
    # 照抄游戏脚本 `Game_Actor_Attr#reset_point`（0000_000015.rb:5331）：
    #     @体质..@敏捷 = 20 + @master.level - 1
    #     @潜能        = @master.level * 5
    # 整份主脚本只有**一个**调用点：Map019 门派地图「确定拜师」事件的
    # `$game_player.actor.attr.reset_point`（Map013 配套文案「拜师后属性点会自动重置」）。
    #
    # 语义是**洗点**，不是"回出厂值"：`@潜能` 是未分配点池，`apply_point` 把
    # `@xx_temp` 从潜能搬进五维 → `五维和 + 潜能` 守恒，reset_point 只是把它们
    # 整体搬回潜能。（`initialize`(5247) 是固定 `五维=20`，**不等于**本公式。）
    # 真档实证（Lv60）：仙灵儿「五维全 79 / 潜能 300」就是洗点后的样子，
    # 李修远「79/79/354/79/104 / 潜能 0」是 300 点全砸力量。
    #
    # ⚠ 五维和会**下降**（李修远 695 → 395），永远碰不到反作弊线
    #    （等级*10+500 = 1100），不会留痕迹。
    # ⚠ 只动 @attr 里这 6 个字段：装备加成是 `get_equip_attr` 现算的、不写档；
    #    @人气/@贡献/@体力/@活力 与本功能无关。
    def actor_reset_attr(self, actor):
        """把角色的五维/潜能洗回「全部来自等级自然成长」的状态。

        返回 (五维基准值, 潜能值) / None（角色没有 @attr）。
        """
        lv = self.actor_level(actor)
        attr = _deref(ivar(actor, "@attr"))
        if attr is None:
            return None
        base = 20 + lv - 1
        for k in ("@体质", "@法力", "@力量", "@耐力", "@敏捷"):
            node = _deref(ivar(attr, k))
            if node is not None:
                self.doc.set_value(node, base)
        pot = lv * 5
        node = _deref(ivar(attr, "@潜能"))
        if node is not None:
            self.doc.set_value(node, pot)
        # `@xx_temp` 是加点界面上的"预览值"（游戏 `apply_point` 后由
        # `clear_point` 归零）。真档全是 0，但存档里确实留着 —— 顺手归零，
        # 否则 `get_体质(temp=true)` 会把它加进去，界面算出来的五维比 base 高一截。
        for k in ("@体质_temp", "@法力_temp", "@力量_temp",
                  "@耐力_temp", "@敏捷_temp"):
            node = _deref(ivar(attr, k))
            if node is not None:
                self.doc.set_value(node, 0)
        return base, pot

    # ---- 重置加点（召唤兽版）＝ 洗点：把加点全搬回潜能
    # ⚠ 游戏里**没有**宠物洗点：`Game_Baby_Attr` 只有 add_point / dec_point /
    #   clear_point / apply_point（加点界面的「＋/－/取消/确定」），宠物面板 17 个
    #   按钮里没有「重置」；`reset_point` 是**角色**独有的（`Game_Actor_Attr`，
    #   全局唯一触发点是拜师事件）。`Game_Baby#setup(actor_id, reset=)` 那个
    #   reset 只是「别覆盖已改过的名字」，跟属性无关。
    #
    # 但宠物侧有一个守恒量，可以照抄角色 `reset_point` 的语义：
    #     五维和 + 潜能 = T（常数）
    #   * `apply_point`（脚本 6475）只是把点从 `@潜能` 搬进五维：`@潜能 -= temp_point_num`
    #   * `level_up`（6412）两边同加：五维各 +1、`@潜能 += 5`
    #   → 从 `initialize`（6208）那一刻起 T 就不变了。代入自然值：
    #         T = 50 + 10*等级 + R      R = 出生时 5 次 `rand(11)` 之和
    #     · 神兽：五维 = 20+等级（= 普通掷满），所以 R = 50
    #     · 普通：R ∈ [0, 50]
    #   真档实证（Lv65）：小仙灵 五维和 425 + 潜能 325 = 750；小丫丫 750 + 0 = 750
    #   —— 两只都是 750 = 50 + 10*65 + 50。
    #
    # 所以「洗回自然」= 潜能 → 等级*5，五维 → (T - 等级*5) 在 5 维间均分：
    #   * 神兽：(T-5L)/5 = 20+等级，和 `initialize` **逐字一致**（幂等：
    #     没加过点的神兽洗完一动不动）
    #   * 普通：得到「10+等级+平均掷点」—— 出生那一下随机**没写进存档、
    #     无法还原**，所以每维最多和真自然值差 ±10（这是本功能唯一的妥协）
    #   ⚠ 结果 `五维和 + 潜能` 一分不少 —— 和角色 `reset_point` 一样是
    #     「把点搬回潜能」，可以在游戏里重新分配，不白送战力。
    #   ⚠ 反作弊查不到：`$jiance`（29479）只查**角色** `point_num > 等级*10+500`，
    #     召唤兽的五维/潜能压根没有校验。
    def baby_reset_attr(self, baby):
        """把召唤兽已分配的加点全部退回潜能（五维回到自然成长量）。

        返回 (五维基准值, 潜能值) / None（这只没有 @attr）。
        """
        attr = self.baby_attr(baby)
        if attr is None:
            return None
        lv = get_int(ivar(baby, "@level"), 1)
        keys = ("@体质", "@法力", "@力量", "@耐力", "@敏捷")
        cur = [_deref(ivar(attr, k)) for k in keys]
        total = sum(get_int(n, 0) for n in cur if n is not None)
        pot_node = _deref(ivar(attr, "@潜能"))
        if pot_node is not None:
            total += get_int(pot_node, 0)

        pot = lv * 5
        body = max(0, total - pot)               # 五维该占的总量
        base, rest = divmod(body, len(keys))     # 余数补给前几维
        for i, (k, node) in enumerate(zip(keys, cur)):
            if node is not None:
                self.doc.set_value(node, base + (1 if i < rest else 0))
        if pot_node is not None:
            self.doc.set_value(pot_node, pot)
        # `@xx_temp` 是加点界面上的「预览值」（游戏 `clear_point` 归零）。
        # 不清掉的话 `get_体质(temp=true)` 会比 base 高一截，界面显示对不上。
        for k in ("@体质_temp", "@法力_temp", "@力量_temp",
                  "@耐力_temp", "@敏捷_temp"):
            node = _deref(ivar(attr, k))
            if node is not None:
                self.doc.set_value(node, 0)
        return base, pot

    # ==================================================== 坐骑（@rides）
    # 一匹坐骑 = 一个 `Game_Ride < Game_Battler` 对象，挂在**角色的** `@rides`
    # 数组里；`@ride` = 乘骑中、`@ride2` = 出战。规则见 `src/rides.py`。
    # ⚠ 这些薄封装只给界面读用；写 / 增 / 删走 `rides.Rides`（那边要维护
    #   自引用链接与 `doc.mark_structural()`，不适合在这里散着做）。
    def rides(self, actor):
        """这个角色的坐骑 `[(下标, Game_Ride 节点), ...]`。"""
        from rides import Rides
        return Rides(self).of(actor)

    def ride_count_all(self):
        from rides import Rides
        return Rides(self).count_all()

    # ==================================================== 防作弊体检
    def point_num(self, actor):
        """五维之和（游戏的反作弊就是这么算的：不含潜能）。"""
        total = 0
        for k in ("@体质", "@法力", "@力量", "@耐力", "@敏捷"):
            total += get_int(ivar(_deref(ivar(actor, "@attr")), k))
        return total

    def anti_cheat_report(self):
        """返回 [(项目, 当前, 上限, 是否超限, 说明), ...]。

        覆盖游戏的全部作弊触发点：
          ① Lock 校验和（@master）—— 两版都有；
          ② $jiance 周期检查（等级/召唤兽等级/金钱/仓库页/五维）—— **仅尝鲜版**；
          ③ Change 记账（金钱/物品/变量/人气/贡献）—— 两版都有：尝鲜版记 'NE!'，
             内测版在线版弹「ne! + 密文」并当场 exit（详见模块文档第 3 条）；
          ④ @cheated 作弊标记 + @keyword —— **仅尝鲜版**；
          ⑤ 机器码绑定（**只提示，不算问题、工具不改**，见下面第 ⑤ 段注释）。
        """
        rows = []

        def row(name, cur, limit, why):
            rows.append((name, cur, limit, cur is not None and cur > limit, why))

        def eq_row(name, cur, want, why):
            # ⚠ `cur is None`＝**这笔账还没建**（不是「账错了」）。
            #   V2.201 的 security 有 gold / renqi / gongxian / variables /
            #   achievement_point，但**物品计数**要等游戏自己发过道具才有条目；
            #   读失败（密钥不对 / 结构变了）同样返回 None —— 两种含义不同，
            #   混为一谈会一打开就报一堆假异常。
            #   所以：读不到 → 不标红（灰着），只提示"本版本无此校验"。
            if cur is None:
                rows.append((name, "本版本无此校验", "—", False, why))
            else:
                rows.append((name, cur, want, cur != want, why))

        # ① Lock 校验和
        bad_locks = self.sv.check_locks()
        rows.append(("Lock 校验和（金钱等关键数值）",
                     "不一致 %d 处" % len(bad_locks) if bad_locks else "一致",
                     "一致", bool(bad_locks),
                     ("关键数值包在 Lock 里（@master = 值*91+45+种子/800），"
                      "直接改值会对不上：%r" % (bad_locks[:3],))
                     if bad_locks else "所有 Lock 的 @master 都对得上"))

        # ② 上限检查（**V2.201 已无 `$jiance` 判作弊**，这里只提示「超出游戏常量」）
        #⚠ 措辞按内测版改过：尝鲜版超限会被周期检查判作弊、20分钟后弹窗强退；
        #   V2.201 脚本里`cheated`/`$jiance` **完全不存在**，超限只是"不正常"，
        #   不会被游戏惩罚 —— 所以别再吓唬用户。
        gold = self.sv.gold()
        row("金钱", gold, MAX_GOLD,
            "Config::Game::MAX_GOLD = %d（内测版无周期检查，超了不会被判作弊，"
            "但别贴着上限）；工具改钱超过上限会自动压到 %d" % (MAX_GOLD, SAFE_GOLD))
        row("仓库页号 warehouse_page", self.warehouse_page(), MAX_WAREHOUSE_PAGE,
            "Config::Game::MAX_WAREHOUSE = [0, %d]" % MAX_WAREHOUSE_PAGE)
        for aid, a in self.sv.actors():
            nm = self.sv.actor_name(a) or ("角色%d" % aid)
            row("%s 等级" % nm, get_int(ivar(a, "@level")), MAX_LEVEL_ACTOR,
                "Config::Game::MAX_LEVEL_ACTOR = %d" % MAX_LEVEL_ACTOR)
            pn = self.point_num(a)
            lim = get_int(ivar(a, "@level")) * 10 + 500
            rows.append(("%s 五维总点数" % nm, pn, lim, pn > lim,
                         "参考线 = 等级*10+500（体质+法力+力量+耐力+敏捷）"))
            for i, b in self.babies(a):
                row("%s 的召唤兽「%s」等级" % (nm, self.baby_name(b)),
                    get_int(ivar(b, "@level")), MAX_LEVEL_BABY,
                    "Config::Game::MAX_LEVEL_BABY = %d" % MAX_LEVEL_BABY)

        # ③ Change 记账（**两版都有**：V2.201 的 security 里 gold / variables /
        #    renqi / gongxian 都是游戏写下的真账，密钥 admin_alskmcndfj。
        #    走 eq_row：读不到当"本版本无此校验"灰着，读到就正常比对。）
        # 金钱账：最容易漏 —— 以前工具改钱不同步它，玩一会儿必被记 'NE!'
        rec_gold = self.security_gold()
        eq_row("金钱记账 security[:gold]", rec_gold, gold,
               "游戏里一花钱/赚钱就会拿这笔账和实际金钱比对，"
               "对不上立刻判作弊（改金钱时必须同步）")
        for vid, rec, want in self.security_variable_rows():
            if rec is not None and want is not None and rec != want:
                rows.append(("变量记账：$game_variables[%d]" % vid,
                             rec, want, True,
                             "游戏改变量时会逐笔核对这笔账，"
                             "修复会把账对齐到当前值 %d" % want))
        for sec_key, cn, attr in (("renqi", "人气", "@人气"),
                                  ("gongxian", "贡献", "@贡献")):
            for aid, nm, rec, want in self.security_actor_rows(sec_key, attr):
                if rec is not None and want is not None and rec != want:
                    rows.append(("%s记账：%s (角色%d)" % (cn, nm, aid),
                                 rec, want, True,
                                 "游戏加/减%s时会核对这笔账，修复会对齐到当前值 %d"
                                 % (cn, want)))
        for iid, nm, rec, act in self.security_rows():
            if rec is not None and rec != act:
                rows.append(("物品计数校验：%s (id=%d)" % (nm, iid), act, rec,
                             True,
                             "游戏记录的 %d / 背包实际 %d —— 不一致时建议点"
                             "「同步物品计数校验」（正常玩着玩着也可能不一致，"
                             "游戏自己用掉道具时不一定同步）" % (rec, act)))

        # ④ 作弊标记
        ch = M.value_of(_deref(ivar(self.sv.section("system"), "@cheated")))
        rows.append(("作弊标记 @cheated", ch, "false", not is_ruby_false(ch),
                     "非 false 表示游戏已经判定作弊："
                     "20 分钟后警告、25 分钟后强制退出"
                     + ("（注意 Ruby 里 0 也算真值 → 必须写成 false）"
                        if ch == 0 else "")))
        kw = _deref(ivar(self.sv.section("system"), "@keyword"))
        kws = [_as_str(x) for x in kw.items] if isinstance(kw, M.ArrayNode) else []
        rows.append(("作弊记录 @keyword", "、".join(kws) or "（空）", "（空）",
                     bool(kws),
                     "VNE=超限检查 / NE!=记账对不上 / 其余是内存修改器检测，"
                     "全部清掉才算干净"))

        # ⑤ 机器码 —— ⚠ **只报告，第 4 位一律 False（不算问题）**。
        #   它是「存档绑定」不是违规：不在档只是"换机器时要手动加一下"。
        #   一旦标成 True，"保存前体检"会把它列进要修的问题、自动修复时
        #   顺手把本机码写回去 ⇒ 用户手设的机器码被覆盖
        #   （2026-10-04 川：「明明点的替换保存重新载入后却还是加入了本机
        #   真实机器码」）。改机器码只走「机器码」页那几个按钮。
        now, err, ids, ok = self.machine_status()
        if err:
            rows.append(("机器码（本机）", "—", "—", False,
                         "读不到：%s" % err.splitlines()[0][:70]))
        elif not ok:
            rows.append(("机器码（本机 %s 不在存档记录里）" % now, "不在", "在", False,
                         "存档记录的机器码：%s —— 游戏在本机启动时会 include? "
                         "比对，对不上就弹「存档异常」（换机器玩就会碰到）。"
                         "要加就点「机器码」页的「加入存档」——**工具不会自动改**"
                         % ("、".join(ids) or "（空）")))
        else:
            rows.append(("机器码（本机 %s 已在存档记录里）" % now, "在", "在", False,
                         "存档记录的机器码：%s" % "、".join(ids)))
        return rows

    def fix_anti_cheat(self, clamp=True, clear_flag=True, resync=True):
        """按游戏规则把越界的东西压回上限，并（可选）清掉作弊标记。"""
        done = []
        if clamp:
            gold = self.sv.gold()
            if gold > MAX_GOLD:
                self.set_gold(SAFE_GOLD)         # 含 Lock @master + 金钱账同步
                done.append("金钱 %d → %d（上限 %d 的 2/3 安全值）"
                            % (gold, SAFE_GOLD, MAX_GOLD))
            wp = self.warehouse_page()
            if wp > MAX_WAREHOUSE_PAGE:
                self.set_warehouse_page(MAX_WAREHOUSE_PAGE)
                done.append("仓库页号 %d → %d" % (wp, MAX_WAREHOUSE_PAGE))
            for aid, a in self.sv.actors():
                lv = get_int(ivar(a, "@level"))
                if lv > MAX_LEVEL_ACTOR:
                    self.doc.set_value(_deref(ivar(a, "@level")), MAX_LEVEL_ACTOR)
                    done.append("角色%d 等级 %d → %d" % (aid, lv, MAX_LEVEL_ACTOR))
                lim = get_int(ivar(a, "@level")) * 10 + 500
                pn = self.point_num(a)
                if pn > lim:
                    over = pn - lim
                    obj = _deref(ivar(a, "@attr"))
                    for k in ("@潜能", "@敏捷", "@耐力", "@力量", "@法力",
                              "@体质"):
                        if over <= 0:
                            break
                        cur = get_int(ivar(obj, k))
                        cut = min(cur, over)
                        if cut > 0:
                            self.doc.set_value(_deref(ivar(obj, k)), cur - cut)
                            over -= cut
                    done.append("角色%d 五维超限 %d 点，已扣回" % (aid, pn - lim))
                for i, b in self.babies(a):
                    blv = get_int(ivar(b, "@level"))
                    if blv > MAX_LEVEL_BABY:
                        self.doc.set_value(_deref(ivar(b, "@level")),
                                           MAX_LEVEL_BABY)
                        done.append("召唤兽「%s」等级 %d → %d"
                                    % (self.baby_name(b), blv, MAX_LEVEL_BABY))
                    life = get_int(ivar(self.baby_attr(b), "@life"))
                    if life > MAX_BABY_LIFE:
                        self.doc.set_value(
                            _deref(ivar(self.baby_attr(b), "@life")),
                            MAX_BABY_LIFE)
                        done.append("召唤兽「%s」寿命 %d → %d"
                                    % (self.baby_name(b), life, MAX_BABY_LIFE))
        if resync:
            # 五类 Change 账全部对齐（金钱/物品/变量/人气/贡献）
            for cn, n in self.resync_all_security():
                done.append("同步了%s记账 %d 条" % (cn, n))
            # Lock 校验和（改五维/金钱可能留下的不一致，理论上入口都同步了，
            # 这里再兜底全扫一遍）
            n_lock = self.sv.repair_locks()
            if n_lock:
                done.append("重算 %d 处 Lock 校验和" % n_lock)
            # 机器码：⚠ **这里绝不自动增删**。
            #   原来写过「本机码不在档就追加」—— 结果川把机器码换成别人的码
            #   （伪装/换机器），一保存就被塞回本机真实机器码，替换白做
            #   （operation log：替换 → 存 → 重载 → 又两个）。机器码是
            #   "存档绑定"不是违规项，要不要加由人在「机器码」页拍板，
            #   自动修复只做数值/记账/标记这些真会出问题的事。
        if clear_flag:
            n = self.clear_cheat_flag()
            if n:
                done.append("已清除作弊标记（%s）" % "、".join(n))
        return done

    def clear_cheat_flag(self):
        """把 `@cheated` 置成真正的 Ruby `false`，并清空 `@keyword` 作弊记录。

        ⚠ 必须写成 Marshal 的 `F`（false），不能写成整数 0 ——
        Ruby 里 `0` 是**真值**，游戏 `if $game_system.cheated` 照样成立，
        20 分钟后还是会开始“惩罚”，25 分钟后弹「存档异常」。

        @keyword 里记的全是作弊事件，脚本里只有三处往里写：
        'VNE'（$jiance 超限）、'NE!'（Change 记账对不上）、
        SHIELD 查到的内存修改器窗口标题 —— 没有别的正常用途，整个清空。
        """
        done = []
        sysn = self.sv.section("system")
        node = _deref(ivar(sysn, "@cheated"))
        if node is not None:
            cur = M.value_of(node)
            if not is_ruby_false(cur):
                self.doc.set_value(node, False)
                done.append("@cheated: %r → false" % (cur,))
        kw = _deref(ivar(sysn, "@keyword"))
        if isinstance(kw, M.ArrayNode) and kw.items:
            old = [_as_str(x) for x in kw.items]
            kw.items = []
            self.doc.mark_structural()
            done.append("keyword 清空 %d 条（%s）"
                        % (len(old), "、".join(x or "?" for x in old)[:40]))
        return done


# --------------------------------------------------------------------------
# 存档文件层面：扫描 / 批量修复（作弊标记、超限项、物品计数校验）
# --------------------------------------------------------------------------
def save_files(save_path):
    r"""游戏目录下**所有可能被游戏读到的存档**：

        <游戏根>\save.rvdata2      （主存档）
        <游戏根>\save*.rvdata2     （其它存档，如果有）
        <游戏根>\AutoSave\*.rvdata2（自动存档，读它一样会被惩罚）
    """
    import os
    main = os.path.abspath(save_path)
    root = os.path.dirname(main)
    out = [main]
    try:
        for n in sorted(os.listdir(root)):
            p = os.path.join(root, n)
            if n.lower().endswith(".rvdata2") and os.path.isfile(p) and p != main:
                out.append(p)
    except OSError:
        pass
    d = os.path.join(root, "AutoSave")
    if os.path.isdir(d):
        try:
            for n in sorted(os.listdir(d)):
                if n.lower().endswith(".rvdata2"):
                    out.append(os.path.join(d, n))
        except OSError:
            pass
    return out


def fix_save_file(path, backup=True, dry_run=False, note="按规则修复 + 清作弊标记"):
    """打开一个存档文件 → 全量防作弊修复 → 写回。

    fix_anti_cheat 已覆盖：Lock 校验和、周期超限（金钱压到 2/3 安全值等）、
    五类 Change 记账（金钱/物品/变量/人气/贡献）、@cheated/@keyword、机器码。

    返回 ``(有没有问题, 做了哪些, 超限项列表)``；`dry_run=True` 只看不改。
    """
    # ⚠ 起别名：本函数的 backup 参数（bool）会遮蔽同名模块
    import backup as backup_mod
    import save
    sv = save.SaveDoc(path)
    g = GameEditor(sv)
    rows = g.anti_cheat_report()
    over = [r for r in rows if r[3]]
    if not over or dry_run:
        return bool(over), [], over
    if backup:
        try:
            backup_mod.backup(path, backup_mod.KIND_MANUAL, note=note)
        except Exception:
            pass
    done = []
    try:
        done = g.fix_anti_cheat()
    except Exception:
        done = []
    if done:
        sv.doc.save()
    return True, done, over
