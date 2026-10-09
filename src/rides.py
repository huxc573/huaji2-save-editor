# -*- coding: utf-8 -*-
"""坐骑：读 / 改 / 增 / 删 / 乘骑 / 出战。

游戏侧一匹坐骑就是一个 `Game_Ride < Game_Battler` 对象，存在**角色的**
`@rides` 数组里；另外两个引用字段：

    @ride   = 乘骑中的那匹（影响移动速度、立绘，`actor.ride = sel`）
    @ride2  = 出战的那匹（战斗里替你上，`actor.ride2 = sel`）

规则全部照 `Game_Ride`（`script00_00000020.rb` 11649~12026）：

    def max_level            = 9              # 阶，写死 9
    def exp_for_level(level) = $exps[:ride][level-1]     # 见 tables/exp.RIDE_EXP
    def skill_max            = [3, 4, 6][@quality]       # 0 普通 / 1 靓仔 / 2 神骑
    def init_skills          # 471~482 里随机抽（5% 概率抽 483~486）
    def level_up             # 每次升级 @seeds[:skills][1] += 1，到 4/8（神骑 3/6/9）阶再抽技能
    def change_level(level)  = clamp(1..9)
    def get_max_data         = {atk/def/hp/mp/agi: 9999}  # 硬顶（游戏内到不了）
    def markup(type)         = 资质 × 坐骑阶 × (atk/def/mp 0.01 / hp 0.05 / agi 0.005)

**五资质不是属性值**：它的作用是 `markup`（= 资质 × 坐骑阶 × 系数），**加给
这匹统驭的召唤兽**（`Game_Baby#mhp/atk/def/agi` 里的 `r.attr.markup`）；
面板（`Window_Ride#draw`）画的也只是这 5 个数与它们的加成。坐骑自己的 `@param_plus[6]` = 移速 × 1000
（蛋的 `data[:speed]`，品质 > 0 时再乘 1.0~1.5 / 1.5~2.0）。

⚠ 「造一匹新坐骑」走**克隆**：拿存档里已有的一匹当模板，改字段后塞进
  `@rides`。理由 —— `Game_Ride` 的 ivar 有 46 个（其中 4 个是自引用链接：
  `@result.@battler` / `@color_ex.@master` / `@attr.@master` / `@attr.@name`
  → 坐骑自己，`@master` → 主人），手写模板漏一个就是进游戏崩。克隆能保证
  结构跟游戏当前版本**逐字一致**。存档里一匹坐骑都没有时明确报错，让人
  先用坐骑蛋蛋（物品 148）开一匹 —— 见 `add()`。
"""
import random
import re

import datatables
import marshal_ruby as M
from game import (get_int, int_node, nil_node, set_ivar, str_node)
from save import _deref, ivar

#: 坐骑满阶（`Game_Ride#max_level` 写死 9）。
RIDE_MAX_LEVEL = 9
#: 五资质的**代码硬顶**（`Game_Ride_Attr#get_max_data` 都是 9999）。
#: ⚠ 游戏内到不了这个数，见下面的 `RIDE_ATTR_RANGE`。
RIDE_ATTR_MAX = 9999
#: 五资质的**出生区间**（`Game_Ride_Attr#initialize`，按品质）：
#: 普通 500~1500 / 靓仔 800~1800 / 神骑 1000~2000。
#: ⚠ 游戏里坐骑资质**只有出生随机这一条来源** —— `level_up` 只动等级与技能、
#:   「喂养」只加灵气、没有任何加资质的道具 ⇒ 单只坐骑的资质永远 ≤ 本档上限。
#:   所以「拉满」按这里给，不按 9999。
RIDE_ATTR_RANGE = ((500, 1500), (800, 1800), (1000, 2000))
#: 品质：0 普通 / 1 靓仔 / 2 神骑（`rand_average([920,80,1])`）。
RIDE_QUALITY = ("普通", "靓仔", "神骑")
#: 各品质的技能上限（`Game_Ride#skill_max`）。
RIDE_SKILL_MAX = (3, 4, 6)
#: 技能池（`init_skills` / `level_up`）：主池 471~482，稀有的 483~486。
RIDE_SKILL_MAIN = tuple(range(471, 483))
RIDE_SKILL_RARE = (483, 484, 485, 486)
#: 学技能的阶（`level_up` 的 `arr`）：普通/靓仔 4·8 阶，神骑 3·6·9 阶。
RIDE_SKILL_LEVELS = ((4, 8), (4, 8), (3, 6, 9))
#: 五资质（`Game_Ride_Attr` 的 ivar 名 → 中文）。
RIDE_ATTR_KEYS = (("atk", "攻击资质"), ("def", "防御资质"), ("hp", "体力资质"),
                  ("mp", "法力资质"), ("agi", "速度资质"))
#: `Game_Ride#markup` 里各资质的系数（估算加成时用）。
RIDE_ATTR_RATE = {"atk": 0.01, "def": 0.01, "mp": 0.01, "hp": 0.05, "agi": 0.005}
#: 移速（`@param_plus[6]`）的存放倍率：`(speed * 1000).to_i`。
RIDE_SPEED_MUL = 1000

#: `Data\Actors[id]` 的 @note 里坐骑立绘名的写法（`battler = "坐骑-汗血宝马"`）。
#: ⚠ 备注里的值常带引号，存进存档的是**不带引号**的那个名字（真档实测
#:   `@battler_dir_` = `坐骑-汗血宝马`），所以两头都要剥。
_BATTLER_NOTE = re.compile(r"""battler\s*=\s*['"]?([^'"\s|\r\n]+)['"]?""")


class RidesError(Exception):
    """坐骑操作的用户级错误（界面直接显示这句）。"""


def exp_for_level(level):
    """升到 `level` 阶需要的**总**灵气（`$exps[:ride][level-1]`）；越界给 None。"""
    from tables import exp
    try:
        lv = int(level)
    except (TypeError, ValueError):
        return None
    if lv < 1 or lv > len(exp.RIDE_EXP):
        return None
    return exp.RIDE_EXP[lv - 1]


def next_exp(level):
    """在 `level` 阶，再升一阶需要的灵气（= `exp_for_level(level + 1)`）。"""
    return exp_for_level(int(level) + 1)


def full_exp(level):
    """`level` 阶的「本级满灵气」= 门槛 − 1（凑到门槛游戏就自己升阶了）。

    与「修炼」那边的口径一致（`game.practice_full_exp`）：游戏 `level_up?`
    是 `exp >= next_level_exp`，所以不升阶时 exp 的最大值就是门槛 − 1。
    9 阶封顶后再攒也没意义，返回 `exp_for_level(10) - 1`（15000 − 1）。
    """
    n = next_exp(level)
    return None if n is None else n - 1


def skill_max(quality):
    """这个品质能带几个技能（0 普通 / 1 靓仔 / 2 神骑）。"""
    q = 0 if quality is None else max(0, min(2, int(quality)))
    return RIDE_SKILL_MAX[q]


class Rides(object):
    """针对一份 SaveDoc 的坐骑操作。用法同 `babies.Babies`。"""

    def __init__(self, g):
        self.g = g
        self.doc = g.doc
        self.sv = g.sv
        self._names = None

    # ------------------------------------------------------------------ 数据表
    def name_of(self, ride_id):
        """`Data\\Actors[id]` 里坐骑的名字（读不到退回内置名字表）。"""
        try:
            _r, items = datatables.load("Actors")
            for i, n in items:
                if int(i) == int(ride_id):
                    nm = datatables.s(n, "@name") or ""
                    if nm:
                        return nm
                    break
        except Exception:                            # noqa: BLE001
            pass
        try:
            return datatables.name_map("Actors").get(int(ride_id), "") or ""
        except (TypeError, ValueError):
            return ""

    def template_node(self, ride_id):
        """`Data\\Actors[id]` 节点（取 `@class_id` / `@initial_level` / 立绘备注）。"""
        try:
            _r, items = datatables.load("Actors")
            for i, n in items:
                if int(i) == int(ride_id):
                    return n
        except Exception:                            # noqa: BLE001
            pass
        return None

    def class_id_of(self, ride_id):
        n = self.template_node(ride_id)
        v = get_int(datatables.s(n, "@class_id") if n is not None else None, 0) \
            if n is not None else 0
        if v:
            return v
        # 读不到 Data 表时退回「id - 256 偏移」的经验：真档实测 class_id = id + 2
        return int(ride_id) + 2

    def battler_dir_of(self, ride_id):
        """`Game_Ride#update_battler_dir` = `read_note('battler') or name`。"""
        n = self.template_node(ride_id)
        if n is not None:
            note = datatables.s(n, "@note") or ""
            m = _BATTLER_NOTE.search(note)
            if m:
                return m.group(1)
        return self.name_of(ride_id)

    def skill_names(self):
        """坐骑技能池的名字 `{id: 名字}`（471~486）。"""
        try:
            names = datatables.name_map("Skills")
        except Exception:                            # noqa: BLE001
            names = {}
        out = {}
        for sid in RIDE_SKILL_MAIN + RIDE_SKILL_RARE:
            nm = names.get(sid, "")
            out[sid] = nm or ("技能 %d" % sid)
        return out

    def skill_pool(self):
        """技能池 `[(id, 名字, 稀有)]`（471~482 普通 / 483~486 稀有）。"""
        names = self.skill_names()
        out = [(s, names[s], False) for s in RIDE_SKILL_MAIN]
        out += [(s, names[s], True) for s in RIDE_SKILL_RARE]
        return out

    # ------------------------------------------------------------------ 读
    def of(self, actor):
        """这个角色的坐骑 `[(下标, Game_Ride 节点), ...]`（按数组顺序）。"""
        arr = _deref(ivar(actor, "@rides"))
        out = []
        if isinstance(arr, M.ArrayNode):
            for i, b in enumerate(arr.items):
                bb = _deref(b)
                if isinstance(bb, M.ObjNode):
                    out.append((i, bb))
        return out

    def count(self, actor):
        return len(self.of(actor))

    def count_all(self):
        """全存档坐骑总数（给状态行 / 界面提示用）。"""
        return sum(len(self.of(a)) for _i, a in self.sv.actors())

    def riding(self, actor):
        r = _deref(ivar(actor, "@ride"))
        return r if isinstance(r, M.ObjNode) else None

    def fighting(self, actor):
        r = _deref(ivar(actor, "@ride2"))
        return r if isinstance(r, M.ObjNode) else None

    def index_of(self, actor, node):
        """这匹坐骑在 `@rides` 里的下标；-1 = 不在这个角色身上。"""
        if node is None:
            return -1
        for i, b in self.of(actor):
            if b is node:
                return i
        return -1

    def bike_state(self, actor, node):
        """`"乘"` / `"战"` / `"乘战"` / `""` —— 一览表「状态」列用。"""
        s = ""
        if self.riding(actor) is node:
            s += "乘"
        if self.fighting(actor) is node:
            s += "战"
        return s

    def name(self, ride):
        """坐骑名（`@name`，没有就 Com 模板名）。"""
        v = M.value_of(_deref(ivar(ride, "@name")))
        if isinstance(v, bytes):
            v = v.decode("utf-8", "replace")
        if v:
            return v
        return self.name_of(get_int(ivar(ride, "@actor_id"), 0)) or "?"

    def nickname(self, ride):
        v = M.value_of(_deref(ivar(ride, "@nickname")))
        if isinstance(v, bytes):
            v = v.decode("utf-8", "replace")
        return v or ""

    def attr_node(self, ride):
        a = _deref(ivar(ride, "@attr"))
        return a if isinstance(a, M.ObjNode) else None

    def attr_value(self, ride, key):
        a = self.attr_node(ride)
        if a is None:
            return None
        return get_int(ivar(a, "@" + key), 0)

    def speed(self, ride):
        """移速加成（浮点，0.19 = +19%）。存在 `@param_plus[6]` 里 ×1000。"""
        arr = _deref(ivar(ride, "@param_plus"))
        if not isinstance(arr, M.ArrayNode) or len(arr.items) <= 6:
            return 0.0
        return get_int(arr.items[6], 0) / float(RIDE_SPEED_MUL)

    def skills(self, ride):
        """技能 id 列表（按存档顺序）。"""
        arr = _deref(ivar(ride, "@skills"))
        if not isinstance(arr, M.ArrayNode):
            return []
        out = []
        for n in arr.items:
            v = M.value_of(_deref(n))
            if isinstance(v, int):
                out.append(v)
        return out

    def info(self, ride):
        """一览表一行要的所有字段。"""
        q = get_int(ivar(ride, "@quality"), 0)
        lv = get_int(ivar(ride, "@level"), 1)
        rid = get_int(ivar(ride, "@actor_id"), 0)
        return {
            "ride_id": rid,
            "template": self.name_of(rid),
            "name": self.name(ride),
            "nickname": self.nickname(ride),
            "quality": q,
            "quality_cn": RIDE_QUALITY[q] if 0 <= q < 3 else str(q),
            "level": lv,
            "max_level": RIDE_MAX_LEVEL,
            "exp": get_int(self._exp_value(ride), 0),
            "next_exp": next_exp(lv),
            "full_exp": full_exp(lv),
            "atk": self.attr_value(ride, "atk"),
            "def": self.attr_value(ride, "def"),
            "hp": self.attr_value(ride, "hp"),
            "mp": self.attr_value(ride, "mp"),
            "agi": self.attr_value(ride, "agi"),
            "speed": self.speed(ride),
            "skills": self.skills(ride),
            "skill_max": skill_max(q),
            "class_id": get_int(ivar(ride, "@class_id"), 0),
        }

    def _exp_value(self, ride):
        """`@exp[@class_id]`（游戏 `Game_Ride#exp` 就读这一个键）。"""
        h = _deref(ivar(ride, "@exp"))
        cid = get_int(ivar(ride, "@class_id"), 0)
        if not isinstance(h, M.HashNode):
            return None
        for k, v in h.pairs:
            kv = M.value_of(_deref(k))
            if isinstance(kv, int) and kv == cid:
                return v
        # 键对不上（换过模板）时退回第一项，免得显示成 0
        return h.pairs[0][1] if h.pairs else None

    # ------------------------------------------------------------------ 改
    def _set_int(self, ride, name, value, lo=None, hi=None):
        node = _deref(ivar(ride, name))
        if node is None:
            raise RidesError("这匹坐骑没有 %s 字段" % name)
        v = int(value)
        if lo is not None:
            v = max(lo, v)
        if hi is not None:
            v = min(hi, v)
        self.doc.set_value(node, v)
        return v

    def set_level(self, ride, value):
        """改阶（1~9，照游戏 `change_level` 的夹法）。灵气不动。"""
        return self._set_int(ride, "@level", value, 1, RIDE_MAX_LEVEL)

    def set_exp(self, ride, value):
        """改灵气（≥ 下一阶门槛时，游戏面板会显示「可进阶」）。

        ⚠ 游戏读的是 `@exp[@class_id]`（`Game_Ride#exp`），不是数组下标 ——
          所以必须按键找那一项，换过模板（class_id 变了）时按新键写。
        """
        h = _deref(ivar(ride, "@exp"))
        if not isinstance(h, M.HashNode):
            raise RidesError("这匹坐骑没有 @exp 字段")
        cid = get_int(ivar(ride, "@class_id"), 0)
        v = max(0, int(value))
        for k, node in h.pairs:
            if M.value_of(_deref(k)) == cid:
                self.doc.set_value(_deref(node), v)
                return v
        # 没有这一项（`@exp` 是空的 / 键对不上）：按游戏 `init_exp` 补一项
        h.pairs.append((int_node(cid), int_node(v)))
        self.doc.mark_structural()
        return v

    def set_attr(self, ride, key, value):
        """改五资质之一（0~9999）。"""
        a = self.attr_node(ride)
        if a is None:
            raise RidesError("这匹坐骑没有 @attr")
        node = _deref(ivar(a, "@" + key))
        if node is None:
            raise RidesError("@attr 里没有 @%s" % key)
        v = max(0, min(RIDE_ATTR_MAX, int(value)))
        self.doc.set_value(node, v)
        return v

    def set_speed(self, ride, speed):
        """改移速加成（浮点：0.19 = +19%）。写进 `@param_plus[6]`。"""
        arr = _deref(ivar(ride, "@param_plus"))
        if not isinstance(arr, M.ArrayNode) or len(arr.items) <= 6:
            raise RidesError("这匹坐骑没有 @param_plus[6]（移速）")
        v = max(0, int(round(float(speed) * RIDE_SPEED_MUL)))
        self.doc.set_value(_deref(arr.items[6]), v)
        return v

    def set_quality(self, ride, value):
        """改品质（0 普通 / 1 靓仔 / 2 神骑）。**不动**移速与已学技能。"""
        return self._set_int(ride, "@quality", value, 0, 2)

    def set_name(self, ride, text):
        """改名（`@name`；`@nickname` 是另一个字段，见 `set_nickname`）。"""
        node = _deref(ivar(ride, "@name"))
        if node is None:
            raise RidesError("这匹坐骑没有 @name")
        self.doc.set_value(node, str(text))

    def set_nickname(self, ride, text):
        node = _deref(ivar(ride, "@nickname"))
        if node is None:
            raise RidesError("这匹坐骑没有 @nickname")
        self.doc.set_value(node, str(text))

    def set_skills(self, ride, ids):
        """整组替换技能（按品质截到上限）。返回实际写入的列表。"""
        arr = _deref(ivar(ride, "@skills"))
        if not isinstance(arr, M.ArrayNode):
            raise RidesError("这匹坐骑没有 @skills")
        cap = skill_max(get_int(ivar(ride, "@quality"), 0))
        want, seen = [], set()
        for s in ids:
            s = int(s)
            if s not in seen:
                seen.add(s)
                want.append(s)
        want = want[:cap]
        arr.items = [int_node(s) for s in want]
        self.doc.mark_structural()
        return want

    def learn_many(self, ride, ids):
        """批量学：返回 `(真写进去的, 本来就会的, 超出上限没写的)`。

        ⚠ 上限是**游戏规则**（`Game_Ride#skill_max`：普通 3 / 靓仔 4 /
          神骑 6）。超了的**不写**、原样报回去，让界面明说漏了几个 ——
          直接截断会让人以为「点过了就都学会了」。
        """
        cur = self.skills(ride)
        cap = skill_max(get_int(ivar(ride, "@quality"), 0))
        already, fresh = [], []
        for s in ids:
            s = int(s)
            if s in cur or s in fresh:
                already.append(s)
            else:
                fresh.append(s)
        added = fresh[:max(0, cap - len(cur))]
        over = fresh[len(added):]
        if added:
            self.set_skills(ride, cur + added)
        return added, already, over

    def forget_many(self, ride, ids):
        """批量忘：返回 `(真忘掉的, 本来就没学的)`。"""
        cur = self.skills(ride)
        drop = [int(s) for s in ids if int(s) in cur]
        missing = [int(s) for s in ids if int(s) not in cur]
        if drop:
            self.set_skills(ride, [s for s in cur if s not in set(drop)])
        return drop, missing

    def clear_skills(self, ride):
        """把这匹的技能全忘掉。"""
        return self.set_skills(ride, [])

    # ------------------------------------------------------------------ 乘骑 / 出战
    def _by_index(self, actor, index):
        arr = _deref(ivar(actor, "@rides"))
        if not isinstance(arr, M.ArrayNode) or not (0 <= index < len(arr.items)):
            raise RidesError("没有第 %d 匹坐骑" % (index + 1))
        return arr, arr.items[index]

    def set_riding(self, actor, index):
        arr, node = self._by_index(actor, index)
        set_ivar(actor, "@ride", node)
        self.doc.mark_structural()
        return _deref(node)

    def clear_riding(self, actor):
        set_ivar(actor, "@ride", nil_node())
        self.doc.mark_structural()

    def set_fighting(self, actor, index):
        arr, node = self._by_index(actor, index)
        set_ivar(actor, "@ride2", node)
        self.doc.mark_structural()
        return _deref(node)

    def clear_fighting(self, actor):
        set_ivar(actor, "@ride2", nil_node())
        self.doc.mark_structural()

    # ------------------------------------------------------------------ 删 / 增
    def remove(self, actor, index):
        """放生：从 `@rides` 里删掉，顺手把乘骑 / 出战引用清干净。"""
        arr, node = self._by_index(actor, index)
        gone = _deref(node)
        arr.items.pop(index)
        if self.riding(actor) is gone:
            set_ivar(actor, "@ride", nil_node())
        if self.fighting(actor) is gone:
            set_ivar(actor, "@ride2", nil_node())
        self.doc.mark_structural()
        return gone

    def donor(self, prefer_actor=None):
        """找一匹现成的坐骑当**模板**（优先同一个角色身上的）。"""
        if prefer_actor is not None:
            rows = self.of(prefer_actor)
            if rows:
                return rows[0][1]
        for _i, a in self.sv.actors():
            rows = self.of(a)
            if rows:
                return rows[0][1]
        return None

    # ------------------------------------------------------------------ 克隆
    @staticmethod
    def _clone(node, memo, pending):
        """按对象身份深拷一棵子树；`@N` 链接稍后统一重定向。

        `pending` 里放 `(新 LinkNode, 老 target)`，全部拷完再 `memo` 查表
        重定向 —— 这样「链接指向子树内」的（`@attr.@name` → 坐骑自己的名字）
        指向副本，「指向子树外」的（`@master` → 主人）保持原对象。
        """
        if node is None:
            return None
        key = id(node)
        if key in memo:
            return memo[key]
        if isinstance(node, M.LinkNode):
            new = M.LinkNode(node.index)
            memo[key] = new
            pending.append((new, node.target))
            return new
        if isinstance(node, M.NilNode):
            new = M.NilNode()
        elif isinstance(node, M.BoolNode):
            new = M.BoolNode(node.value)
        elif isinstance(node, M.IntNode):
            new = M.IntNode(node.value)
        elif isinstance(node, M.BignumNode):
            new = M.BignumNode(node.value)
        elif isinstance(node, M.FloatNode):
            new = M.FloatNode(node.value, node.raw)
        elif isinstance(node, M.SymbolNode):
            new = M.SymbolNode(node.name)
        elif isinstance(node, M.StrNode):
            new = M.StrNode(node.data, cls=node.cls)
        elif isinstance(node, M.IVarNode):
            new = M.IVarNode()
            memo[key] = new
            new.inner = Rides._clone(node.inner, memo, pending)
            new.ivars = [(k, Rides._clone(v, memo, pending))
                         for k, v in node.ivars]
            return new
        elif isinstance(node, M.ArrayNode):
            new = M.ArrayNode([], cls=node.cls)
            memo[key] = new
            new.items = [Rides._clone(x, memo, pending) for x in node.items]
            return new
        elif isinstance(node, M.HashNode):
            new = M.HashNode([], default=None, cls=node.cls)
            memo[key] = new
            new.pairs = [(Rides._clone(k, memo, pending),
                          Rides._clone(v, memo, pending)) for k, v in node.pairs]
            new.default = (Rides._clone(node.default, memo, pending)
                           if node.default is not None else None)
            return new
        elif isinstance(node, M.ObjNode):
            new = M.ObjNode(node.cls)
        else:
            raise RidesError("坐骑模板里有不认识的节点 %r" % type(node).__name__)
        memo[key] = new
        if isinstance(new, (M.ObjNode,)):
            new.ivars = [(k, Rides._clone(v, memo, pending))
                         for k, v in node.ivars]
        return new

    def build(self, actor, ride_id=None, quality=2, level=None, exp=None,
              speed=None, skills=None, rng=None):
        """造一匹新坐骑（**不挂到角色上**），返回节点。

        `ride_id=None` = 抄模板那匹的 id；`level=None` = 模板的
        `Data\\Actors.initial_level`（游戏 `setup` 就是取这个）。
        `speed=None` = 按该坐骑 + 品质的移速区间随机一个（同坐骑蛋蛋）。
        `skills=None` = 空技能表（游戏里新开出来是随机的，这里给空，
        要就直接用「技能…」或「全部拉满」）。
        """
        from itemattr import RIDE_IDS, RIDE_SPEED_RANGE
        src = self.donor(prefer_actor=actor)
        if src is None:
            raise RidesError(
                "存档里一匹坐骑都没有，克隆不出模板。\n"
                "先用「物品」页给背包加一个「坐骑蛋蛋」(148)，"
                "进游戏开一匹（或者用游戏里已有的坐骑），再回来加。")
        info = self.info(src)
        rid = int(ride_id) if ride_id else info["ride_id"]
        q = max(0, min(2, int(quality)))
        lv = RIDE_MAX_LEVEL if level is None else max(1, min(RIDE_MAX_LEVEL,
                                                             int(level)))
        rnd = rng or random.Random()

        memo, pending = {}, []
        new = self._clone(src, memo, pending)
        for link, target in pending:
            link.target = memo.get(id(target), target)

        # ---- 静态字段：模板 / 职业 / 名字 / 立绘
        name = self.name_of(rid) or info["name"]
        class_id = self.class_id_of(rid)
        self._std_set(new, "@actor_id", int_node(rid))
        self._std_set(new, "@class_id", int_node(class_id))
        self._std_set(new, "@name", str_node(name))
        self._std_set(new, "@nickname", str_node(""))
        self._std_set(new, "@battler_dir_", str_node(self.battler_dir_of(rid)))
        self._std_set(new, "@level", int_node(lv))
        self._std_set(new, "@quality", int_node(q))
        self._std_set(new, "@exp", M.HashNode([(int_node(class_id),
                                                int_node(0))]))
        self._std_set(new, "@skills", M.ArrayNode(
            [int_node(s) for s in (skills or [])][:skill_max(q)]))
        self._std_set(new, "@controls", M.ArrayNode([]))
        self._std_set(new, "@master", actor)          # 指回主人（发 @N）
        self._std_set(new, "@battler_name", str_node(""))

        # ---- 移速 + 五资质：照游戏 `setup` / `Game_Ride_Attr#initialize`
        if speed is None:
            i = RIDE_IDS.index(rid) if rid in RIDE_IDS else 0
            lo, hi = RIDE_SPEED_RANGE[i]
            if q > 0:                                  # 品质 > 0 再乘一段
                mlo, mhi = ((1.0, 1.5), (1.5, 2.0))[q - 1]
                lo, hi = lo * mlo, hi * mhi
            speed = rnd.uniform(lo, hi)
        self.set_speed(new, speed)

        a = self.attr_node(new)
        if a is not None:
            lo_hi = RIDE_ATTR_RANGE[q]
            for k, _cn in RIDE_ATTR_KEYS:
                node = _deref(ivar(a, "@" + k))
                if node is not None:
                    self.doc.set_value(node, rnd.randint(*lo_hi))
        if exp is not None:
            self.set_exp(new, exp)
        # 自引用链接：`@result.@battler` / `@color_ex.@master` / `@attr.@master`
        # 都指着模板那匹，克隆时已被重定向到 `memo` 里的副本 —— 这里再校一遍，
        # 确保它们指向**这匹新的**；`@attr.@name` 保持指向坐骑自己的名字串。
        self._relink_self(new, actor)
        return new

    def _std_set(self, obj, name, node):
        obj2 = _deref(obj)
        for i, (k, _v) in enumerate(obj2.ivars):
            if k == name:
                obj2.ivars[i] = (k, node)
                return
        obj2.ivars.append((name, node))

    def _relink_self(self, ride, actor):
        """把自引用改回**对象本身**（不是 `'@N'` 链接）。

        ⚠ 照 `babies.build` 的做法：直接存对象引用，序列化器按对象身份发
          `@N`。存 `LinkNode` 的危险在于链接里记的是**解析那一刻**的编号，
          周围对象一增删就指错（`set_ivar` 的注释里记着 2026-10-04 那次翻车）。
        """
        self._std_set(_deref(ivar(ride, "@result")), "@battler", ride)
        self._std_set(_deref(ivar(ride, "@color_ex")), "@master", ride)
        attr = self.attr_node(ride)
        if attr is not None:
            self._std_set(attr, "@master", ride)
            # `@attr.@name` 在游戏里就是 `@master.name` 那个 String 对象
            self._std_set(attr, "@name", ivar(ride, "@name"))
        self._std_set(ride, "@master", actor)

    def add(self, actor, ride_id=None, quality=2, level=None, exp=None,
            speed=None, skills=None, rng=None):
        """给角色加一匹坐骑（克隆模板 + 改字段）。返回新节点。

        ⚠ **不自动设乘骑 / 出战** —— 新加一匹就静悄悄把「骑着的」换掉太突兀，
          要骑就点一下「乘骑」（`set_riding`）。
        """
        node = self.build(actor, ride_id=ride_id, quality=quality, level=level,
                          exp=exp, speed=speed, skills=skills, rng=rng)
        arr = _deref(ivar(actor, "@rides"))
        if not isinstance(arr, M.ArrayNode):
            raise RidesError("这个角色没有 @rides（不是可编辑的角色？）")
        arr.items.append(node)
        self.doc.mark_structural()
        return node

    # ------------------------------------------------------------------ 一键
    def max_out(self, actor, index):
        """把第 `index` 匹拉满 —— **全按游戏内规则能给到的最大值**：

        神骑 + 9 阶 + 本级满灵气 + 五资质取神骑档出生上限（`RIDE_ATTR_RANGE`
        的 2000；9999 只是代码硬顶，游戏里到不了）
        + 移速取该坐骑神骑档上限 + 技能填满。
        """
        from itemattr import RIDE_IDS, RIDE_SPEED_RANGE
        _arr, node = self._by_index(actor, index)
        ride = _deref(node)
        rid = get_int(ivar(ride, "@actor_id"), 0)
        self.set_quality(ride, 2)
        self.set_level(ride, RIDE_MAX_LEVEL)
        self.set_exp(ride, full_exp(RIDE_MAX_LEVEL))
        for k, _cn in RIDE_ATTR_KEYS:
            self.set_attr(ride, k, RIDE_ATTR_RANGE[2][1])
        i = RIDE_IDS.index(rid) if rid in RIDE_IDS else 0
        self.set_speed(ride, RIDE_SPEED_RANGE[i][1] * 2.0)
        self.set_skills(ride, list(RIDE_SKILL_MAIN)[:skill_max(2)])
        return ride

    def max_out_many(self, actor, indexes):
        """按升序下标整批拉满（界面里「全部拉满」）。返回改了匹数。"""
        n = 0
        for i in sorted(set(int(x) for x in indexes)):
            self.max_out(actor, i)
            n += 1
        return n
