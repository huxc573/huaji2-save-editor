# -*- coding: utf-8 -*-
"""召唤兽：按游戏的 `Game_Baby.new` 规则**造一只新的**，以及删除 / 出战 / 技能 / 改名。

规则全部照抄游戏脚本（`Data\\Scripts.rvdata2`，行号是 v0.4.6 逆向时的）：

    class Game_Baby
      def initialize(actor_id, mutation=false)
        init_seed                    # @signature = srand；@seed / @seeds[:book]
        @mutation = mutation ? true : false
        setup(actor_id)              # 名字/立绘/职业/等级 都来自 Data\\Actors 模板
        @last_skill = Game_BaseItem.new
      end
      def setup(actor_id, reset=false)
        @actor_id = actor_id
        @name = actor.name; @nickname = actor.nickname
        init_graphics; @class_id = actor.class_id; @level = actor.initial_level
        @exp = {}; @equips = []
        @attr = Game_Baby_Attr.new(self)
        init_exp; init_skills; init_equips(actor.equips)
        clear_param_plus; recover_all
        @dyeing = (attr.type == :神兽 ? 0 : 1)
      end

    class Game_Baby_Attr
      def initialize(master)
        data = $baby[master.read_note('data') || master.id]
        case @type = data[:type]
        when :普通                            # 资质/成长/寿命 都是「上限 - 随机」
          @atk = data[:atk] - rand(201*scale).to_i   ... scale = 变异 ? 0.66 : 1
          @grow = (data[:grow] - rand(6)/100.0*scale).to_f(2)
          @life = data[:life] - rand(13)*100
          五维 = 10 + master.level + rand(11)；@潜能 = master.level*5
        when :神兽                            # 全部取定值，寿命 = :infinite（永生）
          五维 = 20 + master.level；@潜能 = master.level*5
        end
        @loyalty = 100; @five = ['金','木','水','火','土'].sample
      end

**小孩（小精灵 #181 … 小丫丫 #186、善财童子 #187）属于备注池 `神兽资质3`**，
而所有开蛋道具只抽 `:神兽资质` / `:神兽资质2`（或 id 区间）—— 正常玩法拿不到，
只能在这里直接加一只（本模块就是干这个的）。

属性公式（Game_Baby_Attr，用来给新召唤兽算满血满蓝）：

    real_mhp = 体质*grow*6 + 体力资质*主人等级/1000
    real_mmp = 法力*grow*3 + 法力资质*主人等级/500
    real_atk = 主人等级*攻击资质*(14+10*grow)/7500 + 力量*grow
    real_def = 主人等级*防御资质*(9.4+6*grow)/7500 + 耐力*grow*4/3     # 19/3 在 Ruby 里是整除
    real_agi = 敏捷*速度资质/1000

（`Game_Baby#param_base` 没被重写 → 继承 `Game_BattlerBase#param_base` 的 `0`，
所以 mhp 就等于 real_mhp，没有职业基础值。）
"""
import random

import xj_baby_data
import xj_db
import xj_marshal as M
from xj_game import (get_int, int_node, nil_node, set_ivar, str_node)
from xj_save import _deref, ivar

FIVE = ("金", "木", "水", "火", "土")
GOD_POOLS = ("神兽资质", "神兽资质2", "神兽资质3")
MAX_SKILLS = 12                 # 游戏里一召唤兽最多 12 个技能


def _int_rand(rnd, n):
    """Ruby 的 `rand(n)`（整数版）：0..n-1。"""
    return rnd.randrange(int(n)) if n > 0 else 0


def _float_rand(rnd, n):
    """Ruby 的 `rand(浮点)` → [0, n) 的浮点；游戏里随后 `.to_i()`。"""
    return int(rnd.random() * n)


def _hash(pairs, default=None):
    return M.HashNode(pairs, default=default)


def _float(value):
    v = float(value)
    return M.FloatNode(v, repr(v).encode("ascii"))


class Babies(object):
    """针对一份 SaveDoc 的召唤兽操作。"""

    def __init__(self, g):
        self.g = g
        self.doc = g.doc
        self.sv = g.sv
        self._actors = None
        self._names = None

    # ------------------------------------------------------------------ 数据表
    def actor_table(self):
        if self._actors is None:
            try:
                _r, items = xj_db.load("Actors")
                self._actors = dict((i, n) for i, n in items)
            except Exception:
                self._actors = {}
        return self._actors

    def actor_node(self, baby_id):
        return self.actor_table().get(int(baby_id))

    def name_of(self, baby_id):
        n = self.actor_node(baby_id)
        return (xj_db.s(n, "@name") or "") if n is not None else ""

    def data_key(self, baby_id):
        """Data\\Actors 的 @note 里的 `data = :池名`（没有就 None）。"""
        n = self.actor_node(baby_id)
        if n is None:
            return None
        note = xj_db.s(n, "@note") or ""
        import re
        m = re.search(r"data\s*=\s*:([^\s|\r\n]+)", note)
        return m.group(1) if m else None

    def config(self, baby_id):
        """`$baby` 里的配置（type/allow_lv/六项资质上限/成长/寿命）。"""
        return xj_baby_data.config_of(int(baby_id), self.data_key(baby_id))

    def is_god(self, baby_id):
        cfg = self.config(baby_id)
        return bool(cfg) and cfg.get("type") == "神兽"

    def class_skill_ids(self, class_id):
        """某个职业（= Data\\Classes[id]）的全部学习技能 id。"""
        try:
            _r, classes = xj_db.load("Classes")
        except Exception:
            return []
        for i, node in classes:
            if i != int(class_id):
                continue
            arr = _deref(xj_db.ivar(node, "@learnings"))
            out = []
            if isinstance(arr, M.ArrayNode):
                for it in arr.items:
                    f = _deref(it)
                    sid = get_int(ivar(f, "@skill_id"), 0) if f is not None else 0
                    if sid:
                        out.append(sid)
            return out
        return []

    def known_names(self):
        """游戏认识的召唤兽名字（Data\\Actors 里所有能当召唤兽的名字）。"""
        if self._names is None:
            self._names = {}
            for i, node in self.actor_table().items():
                nm = xj_db.s(node, "@name") or ""
                if nm:
                    self._names.setdefault(nm, []).append(i)
        return self._names

    def candidates(self):
        """全部可以加的召唤兽：[{id, name, type, pool, allow_lv, atk, hp, grow, life}]。"""
        out = []
        for i in sorted(self.actor_table()):
            cfg = self.config(i)
            if not cfg or cfg.get("type") not in ("普通", "神兽"):
                continue
            nm = self.name_of(i)
            if not nm:
                continue
            out.append({
                "id": i, "name": nm, "type": cfg.get("type"),
                "pool": self.data_key(i) or "",
                "allow_lv": cfg.get("allow_lv", 0),
                "atk": cfg.get("atk"), "def": cfg.get("def"),
                "hp": cfg.get("hp"), "mp": cfg.get("mp"),
                "agi": cfg.get("agi"), "eva": cfg.get("eva"),
                "grow": cfg.get("grow"), "life": cfg.get("life"),
            })
        return out

    # ------------------------------------------------------------------ 造一只
    def build(self, actor, baby_id, mutation=False, rnd=None):
        """按游戏规则造一只召唤兽（**不**挂到角色上），返回节点。

        `actor` 是主人（Game_Actor 节点）—— 5 维、资质里的“主人等级”用它。
        """
        baby_id = int(baby_id)
        info = self.actor_node(baby_id)
        if info is None:
            raise ValueError("Data\\Actors 里没有 id=%d（不是召唤兽？）" % baby_id)
        cfg = self.config(baby_id)
        if not cfg:
            raise ValueError("$baby 表里没有 id=%d 的配置（加不了）" % baby_id)
        rnd = rnd or random.Random()
        god = cfg.get("type") == "神兽"
        scale = 1.0 if (god or not mutation) else 0.66
        mlevel = get_int(ivar(actor, "@level"), 1)

        # ---- 资质 / 成长 / 寿命 / 五维
        def zi(key, spread):
            v = cfg.get(key, 0)
            return int(v) if god else int(v) - _float_rand(rnd, spread * scale)

        atk = zi("atk", 201)
        dfn = zi("def", 201)
        hpq = zi("hp", 401)
        mpq = zi("mp", 301)
        agi = zi("agi", 201)
        eva = zi("eva", 201)
        if god:
            grow = float(cfg.get("grow", 1.0))
            life = None                     # None → :infinite（永生）
        else:
            grow = round(float(cfg.get("grow", 1.0))
                         - _int_rand(rnd, 6) / 100.0 * scale, 2)
            life = int(cfg.get("life", 10000)) - _int_rand(rnd, 13) * 100
        if god:
            five = {k: 20 + mlevel for k in ("体质", "法力", "力量", "耐力", "敏捷")}
        else:
            five = {k: 10 + mlevel + _int_rand(rnd, 11)
                    for k in ("体质", "法力", "力量", "耐力", "敏捷")}
        five["潜能"] = mlevel * 5
        loyalty = 100.0

        # ---- 属性（满血满蓝）
        mhp = int(round(five["体质"] * grow * 6 + hpq * mlevel // 1000))
        mmp = int(round(five["法力"] * grow * 3 + mpq * mlevel // 500))
        a_atk = int(round(mlevel * atk * (14 + 10 * grow) / 7500.0
                          + five["力量"] * grow))
        a_def = int(round(mlevel * dfn * (9.4 + 6 * grow) / 7500.0
                          + five["耐力"] * grow * 4 / 3.0))
        a_agi = int(round(five["敏捷"] * agi / 1000.0))
        a_mat = int(round(five["体质"] * 0.3 + five["法力"] * 0.7
                          + five["力量"] * 0.4 + five["耐力"] * 0.2))
        mhp = max(1, mhp)
        mmp = max(1, mmp)

        # ---- 身份
        name = self.name_of(baby_id)
        face = xj_db.s(info, "@face_name") or ""
        face_i = get_int(ivar(info, "@face_index"), 0)
        char = xj_db.s(info, "@character_name") or ""
        char_i = get_int(ivar(info, "@character_index"), 0)
        nick = xj_db.s(info, "@nickname") or ""
        class_id = get_int(ivar(info, "@class_id"), baby_id)
        level = max(1, get_int(ivar(info, "@initial_level"), 1))
        equips = _deref(ivar(info, "@equips"))

        # ---- 技能：神兽 = 该职业全部技能；普通 = 每条 40% 概率
        if god:
            skills = list(self.class_skill_ids(class_id))
        else:
            skills = [s for s in self.class_skill_ids(class_id)
                      if rnd.random() < 0.4]
        skills = skills[:MAX_SKILLS]

        signature = rnd.getrandbits(127)

        # ---- 组节点
        baby = M.ObjNode("Game_Baby")
        attr = M.ObjNode("Game_Baby_Attr")
        result = M.ObjNode("Game_ActionResult")
        result.ivars = [
            ("@battler", baby),                     # 自引用 → 序列化时发 @N
            ("@used", M.BoolNode(False)),
            ("@missed", M.BoolNode(False)),
            ("@evaded", M.BoolNode(False)),
            ("@critical", M.BoolNode(False)),
            ("@success", M.BoolNode(False)),
            ("@item", nil_node()),
            ("@tps", M.ArrayNode([])),
            ("@dead", M.BoolNode(False)),
            ("@hp_damage", int_node(0)),
            ("@mp_damage", int_node(0)),
            ("@tp_damage", int_node(0)),
            ("@hp_drain", int_node(0)),
            ("@mp_drain", int_node(0)),
            ("@added_states", M.ArrayNode([])),
            ("@removed_states", M.ArrayNode([])),
            ("@added_buffs", M.ArrayNode([])),
            ("@added_debuffs", M.ArrayNode([])),
            ("@removed_buffs", M.ArrayNode([])),
            ("@qugui", nil_node()),
        ]
        attr.ivars = [
            ("@master", baby),                      # 自引用
            ("@name", str_node(name)),
            ("@type", M.SymbolNode(cfg.get("type") or "普通")),
            ("@allow_lv", int_node(cfg.get("allow_lv", 0))),
            ("@atk", int_node(atk)),
            ("@def", int_node(dfn)),
            ("@hp", int_node(hpq)),
            ("@mp", int_node(mpq)),
            ("@agi", int_node(agi)),
            ("@eva", int_node(eva)),
            ("@grow", _float(grow)),
            ("@five", str_node(rnd.choice(FIVE))),
            ("@life", M.SymbolNode("infinite") if life is None else int_node(life)),
            ("@loyalty", _float(loyalty)),
            ("@体质", int_node(five["体质"])),
            ("@法力", int_node(five["法力"])),
            ("@力量", int_node(five["力量"])),
            ("@耐力", int_node(five["耐力"])),
            ("@敏捷", int_node(five["敏捷"])),
            ("@潜能", int_node(five["潜能"])),
            ("@敏捷_temp", int_node(0)),
            ("@耐力_temp", int_node(0)),
            ("@力量_temp", int_node(0)),
            ("@法力_temp", int_node(0)),
            ("@体质_temp", int_node(0)),
            ("@items", _hash([(M.SymbolNode("yuanxiao_eat_count"), int_node(0))])),
        ]

        def base_item(item_id=0):
            it = M.ObjNode("Game_BaseItem")
            it.ivars = [("@class", nil_node()), ("@item_id", int_node(item_id)),
                        ("@item", nil_node())]
            return it

        eq_slots = 4
        if isinstance(equips, M.ArrayNode) and equips.items:
            eq_slots = len(equips.items)
        baby.ivars = [
            ("@battler_name", str_node("")),
            ("@battler_hue", int_node(0)),
            ("@actions", M.ArrayNode([])),
            ("@speed", _float(0.0)),
            ("@result", result),
            ("@last_target_index", int_node(0)),
            ("@last_selected_index", int_node(0)),
            ("@guarding", M.BoolNode(False)),
            ("@sprite", nil_node()),
            ("@hue", int_node(0)),
            ("@wpal", _hash([])),
            ("@real_dead", M.BoolNode(False)),
            ("@auto_say", M.BoolNode(True)),
            ("@force_target", nil_node()),
            ("@caster", nil_node()),
            ("@no_ready", M.BoolNode(False)),
            ("@die_turn", int_node(0)),
            ("@animation_id", int_node(0)),
            ("@animation_mirror", M.BoolNode(False)),
            ("@animation_follow", M.BoolNode(True)),
            ("@animation_se", M.BoolNode(True)),
            ("@sprite_effect_type", nil_node()),
            ("@tp", int_node(0)),
            ("@mp", int_node(mmp)),
            ("@hp", int_node(mhp)),
            ("@hidden", M.BoolNode(False)),
            ("@param_plus", M.ArrayNode([int_node(0) for _ in range(8)])),
            ("@states", M.ArrayNode([])),
            ("@state_turns", _hash([])),
            ("@state_steps", _hash([])),
            ("@buffs", M.ArrayNode([int_node(0) for _ in range(8)])),
            ("@buff_turns", _hash([])),
            ("@signature", M.BignumNode(signature)),
            ("@seed", _hash([(M.SymbolNode("skills"),
                              M.BignumNode(rnd.getrandbits(31))),
                             (M.SymbolNode("baby"), M.BignumNode(signature))])),
            ("@seeds", _hash([(M.SymbolNode("book"),
                               M.ArrayNode([M.BignumNode(rnd.getrandbits(127)),
                                            int_node(0)]))])),
            ("@mutation", M.BoolNode(bool(mutation))),
            ("@actor_id", int_node(baby_id)),
            ("@name", str_node(name)),
            ("@nickname", str_node(nick)),
            ("@character_name", str_node(char)),
            ("@character_index", int_node(char_i)),
            ("@face_name", str_node(face)),
            ("@face_index", int_node(face_i)),
            ("@class_id", int_node(class_id)),
            ("@level", int_node(level)),
            ("@exp", _hash([(int_node(class_id), int_node(0))])),
            ("@equips", M.ArrayNode([base_item() for _ in range(eq_slots)])),
            ("@attr", attr),
            ("@skills", M.ArrayNode([int_node(s) for s in skills])),
            ("@battler_dir_", str_node(name)),
            ("@battler_weapon_", str_node("")),
            ("@action_input_index", int_node(0)),
            ("@dyeing", int_node(0 if god else 1)),
            ("@last_skill", base_item()),
            ("@master", actor),                     # 指回主人（序列化时发 @N）
            ("@fast_mhp", M.ArrayNode([int_node(mhp), int_node(0)])),
            ("@fast_mmp", M.ArrayNode([int_node(mmp), int_node(0)])),
            ("@fast_atk", M.ArrayNode([int_node(a_atk), int_node(0)])),
            ("@fast_def", M.ArrayNode([int_node(a_def), int_node(0)])),
            ("@fast_agi", M.ArrayNode([int_node(a_agi), int_node(0)])),
            ("@fast_mat", M.ArrayNode([int_node(a_mat), int_node(0)])),
            ("@battleing", M.BoolNode(False)),
            ("@allow_below_zero", M.BoolNode(False)),
        ]
        return baby

    def add(self, actor, baby_id, mutation=False, active=False, rnd=None):
        """给角色加一只召唤兽。返回新节点。"""
        node = self.build(actor, baby_id, mutation=mutation, rnd=rnd)
        arr = _deref(ivar(actor, "@babys"))
        if not isinstance(arr, M.ArrayNode):
            raise KeyError("这个角色没有 @babys（不是可编辑的角色？）")
        arr.items.append(node)
        if active or _deref(ivar(actor, "@baby")) is None:
            set_ivar(actor, "@baby", node)
        self.doc.mark_structural()
        return node

    # ------------------------------------------------------------------ 删 / 出战
    def remove(self, actor, index):
        arr = _deref(ivar(actor, "@babys"))
        if not isinstance(arr, M.ArrayNode) or not (0 <= index < len(arr.items)):
            raise IndexError("没有第 %d 只召唤兽" % (index + 1))
        gone = _deref(arr.items[index])
        arr.items.pop(index)
        act = _deref(ivar(actor, "@baby"))
        if act is gone:
            left = [x for x in arr.items if _deref(x) is not None]
            set_ivar(actor, "@baby", left[0] if left else nil_node())
            if left:
                self.doc.mark_structural()
        self.doc.mark_structural()
        return gone

    def set_active(self, actor, index):
        arr = _deref(ivar(actor, "@babys"))
        if not isinstance(arr, M.ArrayNode) or not (0 <= index < len(arr.items)):
            raise IndexError("没有第 %d 只召唤兽" % (index + 1))
        set_ivar(actor, "@baby", arr.items[index])
        self.doc.mark_structural()
        return _deref(arr.items[index])

    def active_index(self, actor):
        act = _deref(ivar(actor, "@baby"))
        arr = _deref(ivar(actor, "@babys"))
        if act is None or not isinstance(arr, M.ArrayNode):
            return -1
        for i, b in enumerate(arr.items):
            if _deref(b) is act:
                return i
        return -1

    # ------------------------------------------------------------------ 技能
    def skills(self, baby):
        arr = _deref(ivar(baby, "@skills"))
        if not isinstance(arr, M.ArrayNode):
            return []
        return [get_int(x, 0) for x in arr.items]

    def set_skills(self, baby, ids):
        ids = [int(s) for s in ids][:MAX_SKILLS]
        set_ivar(baby, "@skills", M.ArrayNode([int_node(s) for s in ids]))
        self.doc.mark_structural()
        return ids

    def learn(self, baby, skill_id):
        ids = self.skills(baby)
        if int(skill_id) in ids:
            return ids
        if len(ids) >= MAX_SKILLS:
            raise ValueError("技能已经 %d 个了（游戏上限），先忘掉一个" % MAX_SKILLS)
        ids.append(int(skill_id))
        return self.set_skills(baby, ids)

    def forget(self, baby, skill_id):
        ids = [s for s in self.skills(baby) if s != int(skill_id)]
        return self.set_skills(baby, ids)

    def clear_skills(self, baby):
        return self.set_skills(baby, [])

    # ------------------------------------------------------------------ 名字
    def display_name(self, baby):
        a = _deref(ivar(baby, "@attr"))
        if isinstance(a, M.ObjNode):
            v = xj_db.s(a, "@name")
            if v:
                return v
        return xj_db.s(baby, "@name") or "?"

    def template_name(self, baby):
        return self.name_of(get_int(ivar(baby, "@actor_id"), 0)) or "?"

    def name_ok(self, name):
        """名字在游戏的名字表里吗（不在表里战斗时可能取不到立绘/音效）。"""
        return name in self.known_names()

    def set_display_name(self, baby, name):
        a = _deref(ivar(baby, "@attr"))
        if not isinstance(a, M.ObjNode):
            raise KeyError("这只召唤兽没有 @attr")
        set_ivar(a, "@name", str_node(name))
        self.doc.mark_structural()
        return name

    def set_base_name(self, baby, name):
        set_ivar(baby, "@name", str_node(name))
        self.doc.mark_structural()
        return name

    def restore_name(self, baby):
        tpl = self.template_name(baby)
        self.set_display_name(baby, tpl)
        self.set_base_name(baby, tpl)
        return tpl
