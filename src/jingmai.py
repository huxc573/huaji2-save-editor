# -*- coding: utf-8 -*-
"""经脉：角色的 `@attr.@经脉`（`Game_JMGroup`）—— 10 个阶位的
`Game_Jingmai`，规则全在 `script00_00000020.rb` 8615~8845。

每个阶位三个状态，顺序不能跳（游戏 `Window_Meridians#update_btns`）：

    1. 打通  `open(slot)`        → @enabled = true
             游戏里要交「天材地宝」(物品 140) 且 lv == 阶下标、等级够
             `item.data[:limit]`、上一阶已打通。
    2. 领悟  `learn(slot, item)`  → 吃掉精气物品，把它的点数 / 属性 / 技能
             整个拷进这一阶，并写 @seed。
             物品按阶分：Ⅰ~Ⅲ 圣者(141)、Ⅳ~Ⅵ 战神(142)、Ⅶ~Ⅸ 仙人(143)、
             X 本源(144)；Ⅳ~Ⅵ 还得先拜师（`id == 142 and sect_id == 0` 直接拦）。
    3. 萃取  `up(slot, v)`        → @progress 累积到 1 就 result=1（萃化完成）；
             极小概率 result=2（走火入魔）—— 那一下会把 points / attributes
             随机乘上负系数，属性直接变负。

**只有 result != 0 的阶才算「生效」**（`Game_JMGroup#have` = enabled 且
result != 0）：点数加到 `attr.体质/魔力/…`，属性加到 `气血上限/物理攻击/…`。
所以「打通但没领悟精气」的阶是空的 —— 这一条在界面上必须讲清楚。

⚠ 改完 points / attributes 一定要把 `@save_points` / `@save_attributes` 置
  nil（`Game_JMGroup#points/attributes` 拿它们当缓存，不失效的话游戏读到的
  还是旧值）。`refresh` 就是干这事的（顺带重算 @grade），见 `_touch()`。

⚠ 工具不凭空造精气：那要照 `def 圣者精气/战神精气/仙人精气` 现生一份，
  再塞进 `@type/@points/@attributes/@skills/@seed` 五处 —— 少一样游戏里就是
  空壳或崩。要经脉收益就用真正的精气物品在游戏里领悟（或先「打通」）。
"""
import marshal_ruby as M
from game import ensure_ivar, get_int, int_node, set_ivar
from save import _deref, ivar

#: 阶位数量（`Game_JMGroup#initialize` 写死 10）。
JM_SLOTS = 10
#: 阶位罗马数字（`Window_Meridians#show_info` 的 `slot`）。
JM_SLOT_CN = ("Ⅰ", "Ⅱ", "Ⅲ", "Ⅳ", "Ⅴ", "Ⅵ", "Ⅶ", "Ⅷ", "Ⅸ", "Ⅹ")
#: 精气类型（`@type` 是符号）。`@index / 3` 决定该交哪件物品。
JM_TYPES = ("圣者精气", "战神精气", "仙人精气", "本源精气")
#: `@result`：0 还在萃取 / 1 萃化完成 / 2 走火入魔。
JM_RESULT_CN = {0: "萃取中", 1: "萃化完成", 2: "走火入魔"}
#: 仙人精气的远古技能名（`Game_Jingmai.skill_name`，与 `Skills` 表的名字不同）。
JM_REMOTE_SKILLS = {81: "玉碎九渊", 89: "风霜碎影", 70: "天绅倒悬",
                    82: "有凤来仪", 85: "玉井天池", 59: "秋江夜泊",
                    91: "长河落日", 98: "雾里看花", 97: "月溉寒泉",
                    93: "七星落雁", 99: "叠翠浮青", 124: "墨染青舟",
                    130: "乾天一气", 135: "醉渔唱晚", 126: "青莲剑歌"}
#: `@points` 的名字空间（脚本 `圣者精气` 的 `group`）
JM_POINT_NAMES = ("体质", "魔力", "力量", "耐力", "敏捷")
#: `@attributes` 的名字空间（`Game_Jingmai#init` 那条注释列的就是这七个）
JM_ATTR_NAMES = ("气血上限", "法力上限", "物理攻击", "物理防御", "灵力",
                 "法术防御", "速度")
#: 属性 → 满值（两张家族表里同名取大的那个）
JM_ATTR_FULL = {"气血上限": 200, "法力上限": 100, "物理攻击": 50,
                "物理防御": 100, "灵力": 50, "法术防御": 100, "速度": 50}
#: 五维点数的满值（`圣者精气` 每项恒 50）
JM_POINT_FULL = 50
#: 一阶里 `@points` / `@attributes` 最多几项。
#: ⚠ 不是随便定的：`refresh_grade` 用 `[0, 10, 30, 60][项数]`、`[0, 20, 40][项数]`
#:   查表，多一项就 `nil`，`nil + 数` 在游戏里直接崩（2026-10-26 川：「我怎么能
#:   无限加？」）。游戏自己产出也最多 3 项（圣者 `+1` → 1~3、战神/仙人 0~2）。
MAX_PAIRS = 3

def _type_cn(sym):
    """符号名 → 中文（`'战神精气'`）；空值给空串。"""
    if not sym:
        return ""
    s = str(sym)
    return s.lstrip(":") if s.startswith(":") else s


def _num(node, default=0):
    """读 Int / Float 节点的数值（`5` / `0.25`）。"""
    v = M.value_of(_deref(node))
    try:
        return default if v is None else float(v) if isinstance(v, float) \
            else int(v)
    except (TypeError, ValueError):
        return default


def _num_node(old, value):
    """按 `old` 的类型写一个新数值节点（Int 保持 Int、Float 保持 Float）。

    ⚠ 别一律写 Int：`@progress` 是 Float，写成 `i` 之后 Ruby 侧
      `obj.progress = 1` 虽然能跑，但和游戏自己的写入口径不一致
      （存盘再读会变成 Integer，下次 `up` 里 `[obj.progress, 1].min`
      照样能算 —— 只是没必要留个不一致）。属性/点数的满值本来就是 Int。
    """
    if isinstance(_deref(old), M.FloatNode):
        v = float(value)
        return M.FloatNode(v, b"")
    return int_node(int(round(float(value))))


def _skill_help(sid, val):
    """技能数值 → 人话（`Game_Jingmai.skill_help`，逐条照抄）。

    `val` 是那一项的数组（`[0.15]` / `[0.2, 35]` 这种）。缺项时不显示效果，
    只给名字 —— 别拿 0 顶上去（会显示成「伤害 + 0%」，比不显示更误导）。
    """
    def g(i, default=0.0):
        try:
            return float(val[i])
        except (IndexError, TypeError, ValueError):
            return default

    def pct(i, nd=2):
        return round(g(i) * 100, nd)

    if sid == 186:
        return "伤害 + %s%%" % pct(0)
    if sid == 181:
        return "回复量 + 自身等级*%s+%s" % (round(g(0), 2), g(1))
    if sid == 189:
        return "持续回合 + %s" % g(0)
    if sid == 198:
        return "回复量 + 自身等级*%s+%s" % (round(g(0), 2), g(1))
    if sid == 192:
        return "伤害 + %s%%" % pct(0)
    if sid == 201:
        return "所有目标都会附加增益状态"
    if sid == 205:
        return "物理伤害 + %s%%, 回合数 + %s" % (pct(0), g(1))
    if sid == 211:
        return "附带溅射效果"
    if sid == 209:
        return "伤害 + %s%%且不耗蓝" % pct(0)
    if sid == 215:
        return "额外造成目标当前气血 %s%% 的伤害" % pct(0)
    if sid == 220:
        return "最大伤害 + %s%%" % pct(0)
    if sid == 221:
        return "%s%%概率不会休息" % pct(0)
    if sid == 229:
        return "伤害 + 自身等级*%s+%s" % (g(0), g(1))
    if sid == 227:
        return "%s%%概率目标 + 1" % pct(0)
    if sid == 234:
        return "目标数 + %s, 持续回合 + %s" % (g(0), g(1))
    if sid == 236:
        return "目标数上限提升至 7"
    if sid == 243:
        return "使用封印技能 %s%% 概率目标 + 1" % pct(0)
    if sid == 245:
        return "取消降低物理防御的 DEBUFF"
    if sid in (252, 277, 291):
        return "目标数 + 1"
    if sid == 247:
        return "附加状态前会将目标应用一次<自在心法>效果"
    if sid == 255:
        return "额外附加伤害反弹效果"
    if sid == 260:
        return "伤害系数 + %s%%, %s%%概率目标 + 1" % (pct(0), pct(1))
    if sid in (263, 300, 304, 305):
        return "伤害系数 + %s%%" % pct(0)
    if sid in (267, 286):
        return "额外附加天魔解体状态"
    if sid == 272:
        return "会对使用者附加<一苇渡江>状态"
    if sid == 278:
        return "额外附加<金刚护体>状态"
    if sid == 280:
        return "伤害 + 自身等级*%s+%s" % (round(g(0), 2), g(1))
    if sid == 289:
        return "无视隐身并且破除目标隐身效果"
    if sid == 295:
        return "召唤出来的灵兽属性提升至召唤者的 120%"
    if sid == 310:
        return "最大伤害 + %s%%" % pct(0)
    return ""


class JingmaiError(Exception):
    """经脉操作的用户级错误（界面直接显示这句）。"""


class Jingmai(object):
    """针对一份 SaveDoc 的经脉操作。用法同 `rides.Rides`。"""

    def __init__(self, g):
        self.g = g
        self.doc = g.doc
        self.sv = g.sv
        self._names = None

    # ------------------------------------------------------------------ 读
    def group(self, actor):
        """角色的 `Game_JMGroup`（`@attr.@经脉`）；没有就抛。"""
        attr = _deref(ivar(actor, "@attr"))
        if not isinstance(attr, M.ObjNode):
            raise JingmaiError("这个角色没有 @attr（属性对象）")
        jm = _deref(ivar(attr, "@经脉"))
        if not isinstance(jm, M.ObjNode):
            raise JingmaiError("这个角色没有经脉数据（老存档？）")
        return jm

    def of(self, actor):
        """`[(阶下标, Game_Jingmai 节点), ...]`。"""
        arr = _deref(ivar(self.group(actor), "@data"))
        out = []
        if isinstance(arr, M.ArrayNode):
            for i, n in enumerate(arr.items):
                nn = _deref(n)
                if isinstance(nn, M.ObjNode):
                    out.append((i, nn))
        return out

    def node(self, actor, slot):
        """第 `slot` 阶的节点（0 起）；越界抛。"""
        for i, n in self.of(actor):
            if i == int(slot):
                return n
        raise JingmaiError("没有第 %d 阶经脉" % (int(slot) + 1))

    def _pairs(self, ji, iv):
        """`@points` / `@attributes` → `[(名字, 当前值, 满值, 原数组节点)]`。"""
        arr = _deref(ivar(ji, "@" + iv))
        out = []
        if not isinstance(arr, M.ArrayNode):
            return out
        for row in arr.items:
            r = _deref(row)
            if not isinstance(r, M.ArrayNode) or len(r.items) < 3:
                continue
            out.append((_type_cn(M.value_of(_deref(r.items[0]))),
                        _num(r.items[1]), _num(r.items[2]), r))
        return out

    def _skills(self, ji):
        """`@skills` → `[(技能id, 名字, 效果)]`。"""
        return [(sid, nm, help_) for sid, nm, help_, _v, _m in
                self.skill_rows_of(ji)]

    def skill_rows_of(self, ji):
        """`@skills` → `[(技能id, 名字, 效果, [数值…], [上限…])]`（编辑用）。"""
        h = _deref(ivar(ji, "@skills"))
        out = []
        if not isinstance(h, M.HashNode):
            return out
        names = self.skill_names()
        for k, v in h.pairs:
            sid = get_int(k, 0)
            vv = _deref(v)
            val, mx = [], []
            if isinstance(vv, M.HashNode):
                for k2, v2 in vv.pairs:
                    key = M.value_of(_deref(k2))
                    a = _deref(v2)
                    lst = [_num(x) for x in a.items] \
                        if isinstance(a, M.ArrayNode) else []
                    if key == "val":
                        val = lst
                    elif key == "max":
                        mx = lst
            out.append((sid, names.get(sid) or ("技能 %d" % sid),
                        _skill_help(sid, val), val, mx))
        return out

    def skill_names(self):
        """技能 id → 名字（远古技能优先用 `Game_Jingmai.skill_name` 那份）。"""
        if self._names is not None:
            return self._names
        names = {}
        try:
            import datatables
            names = dict(datatables.name_map("Skills"))
        except Exception:                            # noqa: BLE001
            names = {}
        names.update(JM_REMOTE_SKILLS)
        self._names = names
        return names

    def grade(self, ji):
        """`Game_Jingmai#refresh_grade` 的品阶（整数）。

        ⚠ `_pairs()` 返回 4 元组（名字, 当前, 满值, 原节点），别按 3 个解包
          —— 空数组时循环不执行，一加项就 `ValueError: too many values`。
        """
        t = _type_cn(M.value_of(_deref(ivar(ji, "@type"))))
        pts = self._pairs(ji, "points")
        ats = self._pairs(ji, "attributes")
        full = lambda rows: sum(50 for _n, c, m, _r in rows if c == m)  # noqa: E731
        if t == "圣者精气":
            g = (0, 10, 30, 60)[min(len(pts), 3)]
            g += sum(c / 10.0 * 30 for _n, c, _m, _r in pts)
            g += full(pts)
        elif t == "战神精气":
            g = (0, 20, 40)[min(len(ats), 2)]
            g += sum(c / m * 100 if m else 0 for _n, c, m, _r in ats)
            g += full(pts)
        elif t == "仙人精气":
            g = 500 + sum(c / m * 100 if m else 0 for _n, c, m, _r in ats)
            g += full(pts)
        elif t == "本源精气":
            g = 9999
        else:
            g = 0
        return int(g)

    def info(self, actor, slot):
        """一览表 / 详情要的所有字段。"""
        ji = self.node(actor, slot)
        t = _type_cn(M.value_of(_deref(ivar(ji, "@type"))))
        res = get_int(ivar(ji, "@result"), 0)
        prog = _num(ivar(ji, "@progress"), 0)
        sect = get_int(ivar(ji, "@sect"), 0)
        return {
            "slot": int(slot),
            "slot_cn": JM_SLOT_CN[int(slot)] if int(slot) < len(JM_SLOT_CN)
                       else str(int(slot) + 1),
            "enabled": bool(M.value_of(_deref(ivar(ji, "@enabled")))),
            "type": t,
            "type_cn": t or "—",
            "sect": sect,
            "sect_cn": self.sect_name(sect),
            "progress": prog,
            "progress_pct": round(prog * 100, 2),
            "result": res,
            "result_cn": JM_RESULT_CN.get(res, "结果 %d" % res),
            "grade": get_int(ivar(ji, "@grade"), 0),
            "points": [(n, c, m) for n, c, m, _r in self._pairs(ji, "points")],
            "attributes": [(n, c, m)
                           for n, c, m, _r in self._pairs(ji, "attributes")],
            "skills": [(sid, nm, h) for sid, nm, h, _v, _m in
                       self.skill_rows_of(ji)],
            "skill_rows": self.skill_rows_of(ji),
        }

    def sect_name(self, sect_id):
        """门派名（`$sects` 不连号：0、1..13、20，表见 `tables/sect`）。"""
        if not sect_id:
            return ""
        try:
            from tables import sect
            return sect.sect_name(int(sect_id)) or "门派 %d" % int(sect_id)
        except Exception:                            # noqa: BLE001
            return "门派 %d" % int(sect_id)

    def count(self, actor):
        """`(已打通, 已萃化, 走火入魔)`。"""
        on = done = bad = 0
        for _i, ji in self.of(actor):
            if M.value_of(_deref(ivar(ji, "@enabled"))):
                on += 1
            r = get_int(ivar(ji, "@result"), 0)
            if r == 1:
                done += 1
            elif r == 2:
                bad += 1
        return on, done, bad

    # ------------------------------------------------------------------ 写
    def _touch(self, actor, ji):
        """改完必备：清掉 `Game_JMGroup` 的两份缓存 + 重算 `@grade`。

        `points` / `attributes` 是**带缓存**的（`@save_points` / `@save_attributes`），
        不置 nil 的话游戏读到的还是改之前那组数。
        """
        set_ivar(ji, "@grade", int_node(self.grade(ji)))
        grp = self.group(actor)
        for k in ("@save_points", "@save_attributes"):
            ensure_ivar(grp, k, M.NilNode())
        self.doc.mark_structural()

    def set_enabled(self, actor, slot, on):
        """打通 / 取消打通（`Game_JMGroup#open` 只动 @enabled）。"""
        ji = self.node(actor, slot)
        set_ivar(ji, "@enabled", M.BoolNode(bool(on)))
        self._touch(actor, ji)
        return bool(on)

    def set_result(self, actor, slot, result):
        """改 `@result`：0 萃取中 / 1 萃化完成 / 2 走火入魔。

        result=1 时把 `@progress` 一并写满 —— 游戏显示「萃化完成」看的是
        result，但 `up` 的进度条还停在半路会让人以为没生效。
        """
        r = int(result)
        if r not in JM_RESULT_CN:
            raise JingmaiError("result 只能是 0 / 1 / 2")
        ji = self.node(actor, slot)
        if r == 1 and not M.value_of(_deref(ivar(ji, "@type"))):
            # 没领悟精气的阶本来就没有点数/属性/技能可萃 —— 硬写 result=1
            # 只会让界面显示「萃化完成」而实际什么都不加（2026-10-26）。
            raise JingmaiError("这一阶还没领悟精气 —— 没有可萃取的东西，"
                               "先打通、再用精气物品在游戏里领悟")
        set_ivar(ji, "@result", int_node(r))
        if r == 1:
            set_ivar(ji, "@progress", _num_node(ivar(ji, "@progress"), 1.0))
        self._touch(actor, ji)
        return r

    def set_progress(self, actor, slot, percent):
        """按百分比写 `@progress`（0~100；写满只到 100，不顺手改 result）。"""
        ji = self.node(actor, slot)
        v = max(0.0, min(float(percent), 100.0)) / 100.0
        set_ivar(ji, "@progress", _num_node(ivar(ji, "@progress"), v))
        self._touch(actor, ji)
        return v

    def max_values(self, actor, slot):
        """把这一阶的「点数提升 / 属性提升」全部填到满值（走火入魔的负数也一起修）。

        返回 `(改了几项, 总有几项)`。
        """
        ji = self.node(actor, slot)
        hit = tot = 0
        for iv in ("@points", "@attributes"):
            arr = _deref(ivar(ji, iv))
            if not isinstance(arr, M.ArrayNode):
                continue
            for row in arr.items:
                r = _deref(row)
                if not isinstance(r, M.ArrayNode) or len(r.items) < 3:
                    continue
                tot += 1
                cur, mx = r.items[1], r.items[2]
                if _num(cur) != _num(mx):
                    r.items[1] = _num_node(cur, _num(mx))
                    hit += 1
        if hit:
            self._touch(actor, ji)
        return hit, tot

    # -------------------------------------------------- 点数 / 属性 条目编辑
    @staticmethod
    def _sym(name):
        return M.SymbolNode(str(name))

    @staticmethod
    def _iv_of(kind):
        return "@points" if kind == "points" else "@attributes"

    def _arr(self, actor, ji, kind):
        """`@points` / `@attributes` 的数组（没有就补一个空数组）。"""
        iv = self._iv_of(kind)
        arr = _deref(ivar(ji, iv))
        if not isinstance(arr, M.ArrayNode):
            arr = M.ArrayNode([])
            ensure_ivar(ji, iv, arr)
        return arr

    def names_of(self, kind):
        """这一类的名字空间（点数＝五维、属性＝七个属性名）。"""
        return JM_POINT_NAMES if kind == "points" else JM_ATTR_NAMES

    def full_of(self, kind, name):
        """某一项的满值（界面上「上限」的默认值）。"""
        if kind == "points":
            return JM_POINT_FULL
        return JM_ATTR_FULL.get(str(name), 100)

    def set_pair(self, actor, slot, kind, index, name=None, cur=None, mx=None):
        """改第 `index` 项（`kind` = `"points"` / `"attributes"`）。

        只改传进来的那几样；名字必须是这一类认得的（写个别的符号游戏算不出来）。

        ⚠ **上限不接受外部指定**（`mx` 只为兼容老调用留着、一律忽略）：它由
          名字决定（`full_of`），换名字就跟着换；数值超过上限压回上限。
          游戏 `refresh_grade` 拿 `值 / 上限` 算品阶、`attributes()` 又把值
          原样加进面板 —— 写超了是真生效，所以必须夹紧
          （2026-10-26 川：「上限应该不可调只显示」「设置超过上限，居然也可以生效」）。
        """
        ji = self.node(actor, slot)
        arr = self._arr(actor, ji, kind)
        i = int(index)
        if not 0 <= i < len(arr.items):
            raise JingmaiError("这一阶没有第 %d 项" % (i + 1))
        r = _deref(arr.items[i])
        if not isinstance(r, M.ArrayNode) or len(r.items) < 3:
            raise JingmaiError("第 %d 项的格式不认识（不是 [名字, 数值, 上限]）"
                               % (i + 1))
        nm = _type_cn(M.value_of(_deref(r.items[0])))
        if name:
            nm = str(name)
            if nm not in self.names_of(kind):
                raise JingmaiError("「%s」不是%s认的名字（可选：%s）" % (
                    nm, "点数" if kind == "points" else "属性",
                    "、".join(self.names_of(kind))))
            r.items[0] = self._sym(nm)
        full = int(self.full_of(kind, nm))
        val = _num(r.items[1]) if cur is None else cur
        try:
            val = int(round(float(val)))
        except (TypeError, ValueError):
            val = 0
        r.items[1] = _num_node(r.items[1], max(0, min(val, full)))
        r.items[2] = _num_node(r.items[2], full)
        self._touch(actor, ji)
        return i

    def add_pair(self, actor, slot, kind, name=None, cur=None, mx=None):
        """加一项（返回新下标）。名字不给就取第一个还没用过的。

        `cur` 不给就取那一项的满值 —— 「加一条」默认是满的（跟界面其它地方
        「默认取最大」一个口径），要低自己改。`mx` 同上：忽略，上限按名字取。

        ⚠ **项数卡在 `MAX_PAIRS`（= 3）**：游戏 `refresh_grade` 里
          `[0, 10, 30, 60][@points.length]` / `[0, 20, 40][@attributes.length]`
          是按项数查表的，**多一项就下标越界 → 返回 nil → `nil + 数` 直接崩**。
          界面原来不卡，能一直加（2026-10-26 川：「我怎么能无限加？」）。
        """
        ji = self.node(actor, slot)
        arr = self._arr(actor, ji, kind)
        if len(arr.items) >= MAX_PAIRS:
            raise JingmaiError(
                "游戏里%s最多 %d 项（品阶按 1/2/3 项分档，再多会算不出品阶）"
                % ("点数" if kind == "points" else "属性", MAX_PAIRS))
        names = self.names_of(kind)
        used = set()
        for row in arr.items:
            r = _deref(row)
            if isinstance(r, M.ArrayNode) and r.items:
                used.add(_type_cn(M.value_of(_deref(r.items[0]))))
        nm = str(name or next((n for n in names if n not in used), names[0]))
        if nm not in names:
            raise JingmaiError("「%s」不是这一类认的名字" % nm)
        full = int(self.full_of(kind, nm))
        try:
            val = int(round(float(full if cur is None else cur)))
        except (TypeError, ValueError):
            val = full
        arr.items.append(M.ArrayNode([self._sym(nm),
                                      int_node(max(0, min(val, full))),
                                      int_node(full)]))
        self._touch(actor, ji)
        return len(arr.items) - 1

    def del_pair(self, actor, slot, kind, index):
        """删一项（`refresh_grade` 按项数分档，删了品阶会跟着降）。"""
        ji = self.node(actor, slot)
        arr = self._arr(actor, ji, kind)
        i = int(index)
        if not 0 <= i < len(arr.items):
            raise JingmaiError("这一阶没有第 %d 项" % (i + 1))
        del arr.items[i]
        self._touch(actor, ji)

    # ------------------------------------------------------------ 技能编辑
    def _skill_hash(self, actor, ji):
        h = _deref(ivar(ji, "@skills"))
        if not isinstance(h, M.HashNode):
            h = M.HashNode([], default=None)
            ensure_ivar(ji, "@skills", h)
        return h

    @staticmethod
    def _num_like(v, like=0):
        """按「像不像整数」写节点：`1` 用 Int，`0.15` 用 Float。"""
        try:
            f = float(v)
        except (TypeError, ValueError):
            return int_node(0)
        if isinstance(v, int) or (isinstance(v, float) and v == int(v)):
            return int_node(int(f))
        return M.FloatNode(round(f, 4), repr(round(f, 4)).encode("ascii"))

    def _skill_node(self, vals, maxes):
        """`{val: […], max: […]}`（键是符号 `:val` / `:max`）。

        ⚠ 上限（`max`）是脚本给的满值、界面上只读；**数值超上限就压回来**
          —— 否则「伤害 +120%」这种游戏产不出的组合也能写进去
          （2026-10-26 川：「设置超过上限，居然也可以生效，而不是回落到上限」）。
        """
        vals = list(vals or [])
        maxes = list(maxes or [])
        for i in range(min(len(vals), len(maxes))):
            try:
                if float(vals[i]) > float(maxes[i]):
                    vals[i] = maxes[i]
            except (TypeError, ValueError):
                pass
        return M.HashNode([
            (self._sym("val"),
             M.ArrayNode([self._num_like(v) for v in vals])),
            (self._sym("max"),
             M.ArrayNode([self._num_like(v) for v in maxes])),
        ], default=None)

    def set_skill(self, actor, slot, old_sid, new_sid, vals=None, maxes=None):
        """改这一阶的技能（换 id 时连键一起换；数值/上限按 `vals` / `maxes`）。"""
        ji = self.node(actor, slot)
        h = self._skill_hash(actor, ji)
        old_sid, new_sid = int(old_sid), int(new_sid)
        idx = None
        for i, (k, _v) in enumerate(h.pairs):
            if get_int(k, -1) == old_sid:
                idx = i
                break
        if idx is None:
            raise JingmaiError("这一阶没有技能 %d" % old_sid)
        if new_sid != old_sid:
            for i, (k, _v) in enumerate(h.pairs):
                if i != idx and get_int(k, -1) == new_sid:
                    raise JingmaiError("这一阶已经有技能 %d 了" % new_sid)
        h.pairs[idx] = (int_node(new_sid), self._skill_node(vals, maxes))
        self._touch(actor, ji)
        return new_sid

    def add_skill(self, actor, slot, sid, vals=None, maxes=None):
        """加一个技能（一个阶可以挂多个；`Game_JMGroup#skills` 会合并）。"""
        ji = self.node(actor, slot)
        h = self._skill_hash(actor, ji)
        sid = int(sid)
        for k, _v in h.pairs:
            if get_int(k, -1) == sid:
                raise JingmaiError("这一阶已经有技能 %d 了" % sid)
        h.pairs.append((int_node(sid), self._skill_node(vals, maxes)))
        self._touch(actor, ji)
        return sid

    def del_skill(self, actor, slot, sid):
        """删一个技能。"""
        ji = self.node(actor, slot)
        h = self._skill_hash(actor, ji)
        sid = int(sid)
        for i, (k, _v) in enumerate(h.pairs):
            if get_int(k, -1) == sid:
                del h.pairs[i]
                self._touch(actor, ji)
                return
        raise JingmaiError("这一阶没有技能 %d" % sid)

    def open_all(self, actor):
        """十阶全部打通（不碰精气 / 萃取）。返回新打通了几个。"""
        n = 0
        for _i, ji in self.of(actor):
            if not M.value_of(_deref(ivar(ji, "@enabled"))):
                set_ivar(ji, "@enabled", M.BoolNode(True))
                self._touch(actor, ji)
                n += 1
        return n

    def complete_all(self, actor):
        """一键全通：全部打通 + 有精气的阶萃化完成 + 数值拉满。

        返回 `{"opened":, "done":, "filled":, "empty":}`（`empty` = 打通了但
        没领悟精气的阶数 —— 那些阶本来就没有收益，界面要照实说）。
        """
        st = {"opened": 0, "done": 0, "filled": 0, "empty": 0}
        for _i, ji in self.of(actor):
            if not M.value_of(_deref(ivar(ji, "@enabled"))):
                set_ivar(ji, "@enabled", M.BoolNode(True))
                st["opened"] += 1
            has_type = bool(M.value_of(_deref(ivar(ji, "@type"))))
            if not has_type:
                st["empty"] += 1
                self._touch(actor, ji)
                continue
            if get_int(ivar(ji, "@result"), 0) != 1:
                set_ivar(ji, "@result", int_node(1))
                st["done"] += 1
            set_ivar(ji, "@progress", _num_node(ivar(ji, "@progress"), 1.0))
            for iv in ("@points", "@attributes"):
                arr = _deref(ivar(ji, iv))
                if not isinstance(arr, M.ArrayNode):
                    continue
                for row in arr.items:
                    r = _deref(row)
                    if isinstance(r, M.ArrayNode) and len(r.items) >= 3 \
                            and _num(r.items[1]) != _num(r.items[2]):
                        r.items[1] = _num_node(r.items[1], _num(r.items[2]))
                        st["filled"] += 1
            self._touch(actor, ji)
        return st

    def clear_tamper(self, actor, slot):
        """只修「走火入魔」：result 回 0，负数项翻回正数（按满值）。

        走火入魔是 `up` 里 `v[1] *= -rand(...)` 造成的，数值可能是负的；
        直接拉满等于顺手把收益顶到上限，见 `max_values`。
        """
        ji = self.node(actor, slot)
        if get_int(ivar(ji, "@result"), 0) == 2:
            set_ivar(ji, "@result", int_node(0))
        return self.max_values(actor, slot)
