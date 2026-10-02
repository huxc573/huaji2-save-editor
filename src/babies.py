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

from tables import baby_aptitude
import datatables
import fieldnames
import marshal_ruby as M
from game import (get_int, int_node, nil_node, set_ivar, str_node)
from save import _deref, ivar

#: 五行的合法值。唯一来源在 `fieldnames.BABY_FIVE`（`game.py` 校验也要用）。
FIVE = fieldnames.BABY_FIVE
GOD_POOLS = ("神兽资质", "神兽资质2", "神兽资质3")

#: 游戏 `Game_Baby#learn_skill` 里「升级学技能」的上限（带 `must=true` 可绕过）。
#: ⚠ 工具**不再**据此截断：存档里写 13 个以上是合法的 ——
#:   读取端（`Game_Baby#skills` / `usable_skills` / 宠物面板 4 列网格都逐个画）
#:   压根没有数量限制，卡 12 的只有「游戏主动教技能」那一条路径。
#:   这个数只用来在界面上提示「已超过游戏学习上限」。
GAME_LEARN_LIMIT = 12


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
        self._skill_ids = None

    # ------------------------------------------------------------------ 数据表
    def actor_table(self):
        if self._actors is None:
            try:
                _r, items = datatables.load("Actors")
                self._actors = dict((i, n) for i, n in items)
            except Exception:
                self._actors = {}
        return self._actors

    def actor_node(self, baby_id):
        return self.actor_table().get(int(baby_id))

    def name_of(self, baby_id):
        """召唤兽名。读不到 `Data\\Actors`（工具没放在游戏里 / 版本不符）时
        退回内置名字表 —— 一览表里至少还认得出是哪只，不再是满屏空。
        """
        n = self.actor_node(baby_id)
        if n is not None:
            nm = datatables.s(n, "@name") or ""
            if nm:
                return nm
        try:
            return datatables.name_map("Actors").get(int(baby_id), "") or ""
        except (TypeError, ValueError):
            return ""

    def data_key(self, baby_id):
        """Data\\Actors 的 @note 里的 `data = :池名`（没有就 None）。"""
        n = self.actor_node(baby_id)
        if n is None:
            return None
        note = datatables.s(n, "@note") or ""
        import re
        m = re.search(r"data\s*=\s*:([^\s|\r\n]+)", note)
        return m.group(1) if m else None

    def config(self, baby_id):
        """`$baby` 里的配置（type/allow_lv/六项资质上限/成长/寿命）。"""
        return baby_aptitude.config_of(int(baby_id), self.data_key(baby_id))

    def is_god(self, baby_id):
        cfg = self.config(baby_id)
        return bool(cfg) and cfg.get("type") == "神兽"

    def class_skill_ids(self, class_id):
        """某个职业（= Data\\Classes[id]）的全部学习技能 id。

        走 `datatables.class_learnings()`：读不到游戏目录时退回**内置表**，
        不然召唤兽技能克隆会以为这个职业一个技能都没有。
        """
        try:
            return sorted(set(sid for _lv, sid
                              in datatables.class_learnings(int(class_id))))
        except (TypeError, ValueError):
            return []

    def known_names(self):
        """游戏认识的召唤兽名字（Data\\Actors 里所有能当召唤兽的名字）。

        读不到 `Data\\Actors` 时退回内置名字表 —— 这份表只用来判断"名字对不对"，
        内置表的覆盖面和游戏目录是同一份，够用。
        """
        if self._names is None:
            self._names = {}
            src = {}
            for i, node in self.actor_table().items():
                nm = datatables.s(node, "@name") or ""
                if nm:
                    src[i] = nm
            if not src:
                try:
                    src = dict(datatables.name_map("Actors"))
                except Exception:
                    src = {}
            for i, nm in src.items():
                if nm:
                    self._names.setdefault(nm, []).append(i)
        return self._names

    def is_baby_entry(self, baby_id):
        """这个 id 在 `Data\\Actors` 里是不是**一只召唤兽**（而不是玩家角色/坐骑/空占位）。

        ⚠ **不能只靠 id 区间判**（2026-10-03 修正）。我一开始按脚本里的
        `135..170` 当神兽区，结果**漏了 171~254 整整 30 只**（超级神虎(壬寅)、
        小精灵、小仙女、泡泡灵仙系列、雪人…，川从 CSV 里发现的）。
        实际分段（实测 `csv/Actors_角色.csv`）：

        ==========  ==================================  ==============
        id 区间内容                       数量        归属
        ==========  ==================================  ==============
        1~20         玩家角色（李修远/ 秦媚儿 …）        **不是**召唤兽
        21~134       普通召唤兽                       114 只
        135~170      神兽                             36 只
        171~254      神兽 / 小孩 / 泡泡灵仙系列         30 只
        255          `--坐骑--`（分隔标记）            **不是**
        256~309      坐骑（汗血宝马/ 镇塔之灵 …）      **不是**召唤兽
        355~399      空占位（`@class_id = 1`、无名字）    **不是**
        310~354      普通召唤兽                       45 只
        400~433      普通召唤兽                       34 只
        ==========  ==================================  ==============

        ⇒ 真实召唤兽 = **259 只**。

        判据（三条同时满足，缺一不可）：
          1. **有名字**（空名的是 `Data\\Actors` 里的空占位）；
          2. **不是玩家角色**（1~20，李修远/ 秦媚儿…）；
          3. **不是坐骑**（255 是 `--坐骑--` 分隔标记，256 起是坐骑）。
        坐骑和召唤兽在游戏里是**两套东西**（坐骑是另一种道具），
        混进「新增召唤兽」会加错，所以这里明确排除。
        """
        i = int(baby_id)
        if i < 21:                      # 玩家角色
            return False
        if i ==255 or 256 <= i <= 309:  # 坐骑（含 255 的分隔标记）
            return False
        node = self.actor_node(i)
        if node is None:
            return False
        name = (datatables.s(node, "@name") or "").strip()
        return bool(name)

    def candidates(self):
        """全部可以加的召唤兽：[{id, name, type, pool, allow_lv, atk, hp, grow, life}]。"""
        out = []
        for i in sorted(self.actor_table()):
            # ⚠ 先按 Actors 表实证筛掉「不是召唤兽」的条目（玩家角色/坐骑/空占位）。
            # 这一步以前是靠 `config()` 查不到就跳过 —— 漏掉了 171~254 整整 30 只。
            if not self.is_baby_entry(i):
                continue
            cfg = self.config(i)
            if not cfg or cfg.get("type") not in ("普通", "神兽"):
                continue
            nm = self.name_of(i)
            if not nm:
                continue
            out.append({
                "id": i, "name": nm, "type": cfg.get("type"),
                "pool": self.data_key(i) or "",
                # `inferred=True` 表示资质是**按 id 区间估的**，不是游戏真值
                # （V2.201 的 `$baby` 表运行时才生成，静态拿不到 —— 见
                #  tables/baby_aptitude.py 的说明）。界面据此提示用户。
                "inferred": bool(cfg.get("inferred")),
                "allow_lv": cfg.get("allow_lv", 0),
                "atk": cfg.get("atk"), "def": cfg.get("def"),
                "hp": cfg.get("hp"), "mp": cfg.get("mp"),
                "agi": cfg.get("agi"), "eva": cfg.get("eva"),
                "grow": cfg.get("grow"), "life": cfg.get("life"),
            })
        return out

    # ------------------------------------------------------------------ 造一只
    def build(self, actor, baby_id, mutation=False, rnd=None, five=None):
        """按游戏规则造一只召唤兽（**不**挂到角色上），返回节点。

        `actor` 是主人（Game_Actor 节点）—— 5 维/潜能用的等级是**召唤兽自己**
        的等级（= Data\\Actors 模板的 `@initial_level`），游戏里
        `Game_Baby_Attr.new(self)` 的 `master.level` 就是这个值，跟主人等级无关。

        `five` = 指定五行（金木水火土）；`None` 时按游戏原样**随机抽**
        （`$baby` 表里 `five = proc{ ['金','木','水','火','土'].sample }`）。
        """
        baby_id = int(baby_id)
        if five is not None:
            five = str(five).strip()
            if five not in FIVE:
                raise ValueError("五行只能是 %s（给的是 %r）" % ("、".join(FIVE), five))
        info = self.actor_node(baby_id)
        if info is None:
            raise ValueError("Data\\Actors 里没有 id=%d（不是召唤兽？）" % baby_id)
        cfg = self.config(baby_id)
        if not cfg:
            raise ValueError("$baby 表里没有 id=%d 的配置（加不了）" % baby_id)
        rnd = rnd or random.Random()
        god = cfg.get("type") == "神兽"
        scale = 1.0 if (god or not mutation) else 0.66
        # 召唤兽自己的初始等级（游戏里 @level = actor.initial_level）
        level = max(1, get_int(ivar(info, "@initial_level"), 1))

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
        # ⚠ 这个五维 dict 以前也叫 `five`，2026-09-27 给 build 加了同名参数
        #   `five`（五行）→ 参数被这个局部变量覆盖，`str_node(five)` 拿到个 dict
        #   直接报 `'dict' object has no attribute 'encode'`。
        #   所以五维改名 `wudi`，`five` 这个词只留给五行。
        if god:
            wudi = {k: 20 + level for k in ("体质", "法力", "力量", "耐力", "敏捷")}
        else:
            wudi = {k: 10 + level + _int_rand(rnd, 11)
                    for k in ("体质", "法力", "力量", "耐力", "敏捷")}
        wudi["潜能"] = level * 5
        loyalty = 100.0

        # ---- 属性（满血满蓝）
        mhp = int(round(wudi["体质"] * grow * 6 + hpq * level // 1000))
        mmp = int(round(wudi["法力"] * grow * 3 + mpq * level // 500))
        a_atk = int(round(level * atk * (14 + 10 * grow) / 7500.0
                          + wudi["力量"] * grow))
        a_def = int(round(level * dfn * (9.4 + 6 * grow) / 7500.0
                          + wudi["耐力"] * grow * 4 / 3.0))
        a_agi = int(round(wudi["敏捷"] * agi / 1000.0))
        a_mat = int(round(wudi["体质"] * 0.3 + wudi["法力"] * 0.7
                          + wudi["力量"] * 0.4 + wudi["耐力"] * 0.2))
        mhp = max(1, mhp)
        mmp = max(1, mmp)

        # ---- 身份
        name = self.name_of(baby_id)
        face = datatables.s(info, "@face_name") or ""
        face_i = get_int(ivar(info, "@face_index"), 0)
        char = datatables.s(info, "@character_name") or ""
        char_i = get_int(ivar(info, "@character_index"), 0)
        nick = datatables.s(info, "@nickname") or ""
        class_id = get_int(ivar(info, "@class_id"), baby_id)
        equips = _deref(ivar(info, "@equips"))

        # ---- 技能：神兽 = 该职业全部技能；普通 = 每条 40% 概率
        # ⚠ 只有「普通」会走 `learn_skill`（那里卡 12）；神兽是 `@skills += learnings`，不卡。
        if god:
            skills = list(self.class_skill_ids(class_id))
        else:
            skills = [s for s in self.class_skill_ids(class_id)
                      if rnd.random() < 0.4][:GAME_LEARN_LIMIT]

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
            ("@five", str_node(five if five is not None else rnd.choice(FIVE))),
            ("@life", M.SymbolNode("infinite") if life is None else int_node(life)),
            ("@loyalty", _float(loyalty)),
            ("@体质", int_node(wudi["体质"])),
            ("@法力", int_node(wudi["法力"])),
            ("@力量", int_node(wudi["力量"])),
            ("@耐力", int_node(wudi["耐力"])),
            ("@敏捷", int_node(wudi["敏捷"])),
            ("@潜能", int_node(wudi["潜能"])),
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

    def add(self, actor, baby_id, mutation=False, active=False, rnd=None, five=None):
        """给角色加一只召唤兽。返回新节点。`five` 见 `build`。"""
        node = self.build(actor, baby_id, mutation=mutation, rnd=rnd, five=five)
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
        # ⚠ 不截断：卡 12 的只有游戏里「升级学技能」那条路径，读取端没有数量限制。
        #   （13 个以上能不能在战斗中正常用，得川实机验证 —— 界面上会给提示。）
        ids = [int(s) for s in ids]
        set_ivar(baby, "@skills", M.ArrayNode([int_node(s) for s in ids]))
        self.doc.mark_structural()
        return ids

    def learn(self, baby, skill_id):
        ids = self.skills(baby)
        if int(skill_id) in ids:
            return ids
        ids.append(int(skill_id))
        return self.set_skills(baby, ids)

    def forget(self, baby, skill_id):
        ids = [s for s in self.skills(baby) if s != int(skill_id)]
        return self.set_skills(baby, ids)

    def clear_skills(self, baby):
        return self.set_skills(baby, [])

    # ------------------------------------------------------------------ 技能克隆
    def valid_skill_ids(self):
        """{技能 id: 名字}（Data\\Skills 表，带缓存）。

        走 `datatables.name_map()`（读不到游戏目录会退回内置名字表），拿不到就是空字典。
        """
        if self._skill_ids is None:
            try:
                self._skill_ids = dict(datatables.name_map("Skills"))
            except Exception:
                self._skill_ids = {}
        return self._skill_ids

    def all_babies(self):
        """整份存档里**所有角色**的召唤兽（克隆时挑来源用）。

        返回 [{actor, actor_id, actor_name, index, baby, name, tpl, skills}]。
        """
        out = []
        if not self.sv:
            return out
        for aid, actor in self.sv.actors():
            try:
                rows = self.g.babies(actor)
            except Exception:
                continue
            for i, b in rows:
                if b is None:
                    continue
                out.append({
                    "actor": actor, "actor_id": aid,
                    "actor_name": self.sv.actor_name(actor) or "",
                    "index": i, "baby": b,
                    "name": self.display_name(b),
                    "tpl": self.template_name(b),
                    "skills": self.skills(b),
                })
        return out

    def clone_skills(self, dst, src, replace=False):
        """把 `src` 的技能复制给 `dst`。

        `replace=True`  → 覆盖：dst 的技能改成和 src 一模一样；
        `replace=False` → 合并：只补 src 有、dst 没有的（**不设数量上限**）。

        返回 {'ids': 最终技能, 'added': 新增个数, 'bad': 被丢掉的无效 id,
              'replace': 是否覆盖}。
        """
        if dst is None or src is None:
            raise ValueError("要先选好「克隆给谁」和「从哪只克隆」")
        if dst is src:
            raise ValueError("来源和目标不能是同一只")

        known = self.valid_skill_ids()
        raw = [s for s in self.skills(src) if s > 0]
        # 存档里可能混着 Data\Skills 已经没有的 id：照抄过去游戏会取不到技能
        bad = [s for s in raw if known and s not in known]
        src_ids = [s for s in raw if not known or s in known]

        if replace:
            ids = list(src_ids)
        else:
            ids = [s for s in self.skills(dst) if s > 0]
            before = list(ids)
            for s in src_ids:
                if s not in ids:
                    ids.append(s)
        self.set_skills(dst, ids)
        return {
            "ids": list(ids),
            "added": len(ids) if replace else len(ids) - len(before),
            "bad": bad, "replace": bool(replace),
        }

    # ------------------------------------------------------------------ 名字
    def display_name(self, baby):
        a = _deref(ivar(baby, "@attr"))
        if isinstance(a, M.ObjNode):
            v = datatables.s(a, "@name")
            if v:
                return v
        return datatables.s(baby, "@name") or "?"

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
