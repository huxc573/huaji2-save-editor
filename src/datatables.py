# -*- coding: utf-8 -*-
"""Data\\*.rvdata2 数据表：解析 + 转 CSV。

**是的，Data 目录下的 .rvdata2 全都被加密了**（和存档同一套 main.dll 加密），
密钥是 `761205`（见 codec.KEY_DATA），本模块会自动解密 + 解析。

能转的有用的表（默认这一批；Map / System / Scripts / Tilesets / Animations 不转）：

    Items 物品 · Weapons 武器 · Armors 防具 · Skills 技能 · States 状态
    Actors 角色 · Classes 职业 · Enemies 敌人
    （可选：Troops 敌人队伍 · CommonEvents 公共事件）

CSV 用 **utf-8-sig** 编码（Excel 双击直接正常显示中文），一行一个 id，
列名是中文，值里嵌套的东西（效果 / 特性 / 伤害 / 学会技能…）会翻成人话并
**把 id 解成名字**：`@effects` 写成「HP回复 +500；解除状态[剧毒]」，
说明列会解掉 `<S:N>` 状态占位符（按备注 `state_details`，与游戏运行时一致）。
伤害列只对真有伤害的条目输出，公式翻成「攻击−目标防御+随机(0~9)」这类可读式。

用法：
    python src/datatables.py                      # 列出所有表 + 行数
    python src/datatables.py --out <目录>          # 默认那批全转
    python src/datatables.py --all --out <目录>    # 连 Troops/CommonEvents 一起转
    python src/datatables.py Items Skills --out <目录>
"""
import csv
import os
import re
import sys
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import codec  # noqa: E402
import paths  # noqa: E402
import marshal_ruby as M  # noqa: E402

DEFAULT_OUT = os.path.join(os.path.dirname(HERE), "csv")

# --------------------------------------------------------------------------
# 一些"代码 → 人话"的对照表（RGSS3 标准）
# --------------------------------------------------------------------------
PARAM_NAMES = ["最大HP", "最大MP", "攻击", "防御", "魔攻", "魔防", "敏捷", "幸运"]

EFFECT_CODES = {
    11: "HP回复", 12: "MP回复", 13: "TP增加",
    21: "附加状态", 22: "解除状态",
    31: "强化能力", 32: "弱化能力", 33: "解除强化", 34: "解除弱化",
    41: "特殊效果", 42: "成长能力", 43: "习得技能", 44: "公共事件",
}

FEATURE_CODES = {
    11: "最大HP", 12: "最大MP", 13: "攻击力", 14: "防御力", 15: "魔法攻击",
    16: "魔法防御", 17: "敏捷", 18: "幸运",
    21: "属性有效度", 22: "弱化有效度", 23: "状态有效度", 24: "状态抗性",
    25: "弱化抗性", 31: "攻击属性", 32: "攻击附加状态", 33: "攻击速度",
    34: "攻击追加次数", 35: "普通攻击次数",
    41: "装备固定", 42: "装备栏", 43: "固定装备", 44: "装备栏数",
    51: "添加技能类型", 52: "封印技能类型", 53: "添加技能", 54: "封印技能",
    55: "已学技能", 61: "普通攻击替换", 62: "战斗开始事件", 63: "属性变化",
    64: "装备变化",
}

SCOPE_NAMES = {
    0: "无", 1: "单个敌人", 2: "全体敌人", 3: "单个敌人(随机)",
    4: "单个敌人(2次)", 5: "单个敌人(3次)", 6: "单个敌人(4次)",
    7: "单个队友", 8: "全体队友", 9: "单个队友(战斗不能)", 10: "全体队友(战斗不能)",
    11: "使用者自身",
}
OCCASION_NAMES = {0: "随时", 1: "仅战斗", 2: "仅菜单", 3: "不使用"}
HIT_NAMES = {0: "必中", 1: "物理", 2: "魔法"}
ITEM_TYPE_NAMES = {1: "通常物品", 2: "关键物品"}
DAMAGE_TYPE_NAMES = {0: "无", 1: "HP伤害", 2: "MP伤害", 3: "HP回复", 4: "MP回复",
                     5: "HP吸收", 6: "MP吸收"}
TRIGGER_NAMES = {0: "无", 1: "并行公共事件", 2: "自动执行"}
RESTRICT_NAMES = {0: "无", 1: "攻击敌人", 2: "攻击我方", 3: "攻击随机", 4: "无法行动"}


# --------------------------------------------------------------------------
# 取值 / 渲染
# --------------------------------------------------------------------------
def deref(n):
    """展开 '@N' 链接和 'I'（带编码的字符串）包装。"""
    seen = 0
    while n is not None and seen < 8:
        seen += 1
        if isinstance(n, M.LinkNode) and n.target is not None:
            n = n.target
            continue
        if isinstance(n, M.IVarNode) and n.inner is not None:
            n = n.inner
            continue
        break
    return n


def b2s(v):
    if isinstance(v, bytes):
        try:
            return v.decode("utf-8")
        except UnicodeDecodeError:
            return v.decode("gbk", "replace")
    return v


def ivar(node, name, default=None):
    node = deref(node)
    if node is None or not hasattr(node, "ivars"):
        return default
    for k, v in node.ivars:
        if k == name:
            return v
    return default


def val(node, name=None):
    """取标量值；给了 name 就先取同名 ivar。"""
    if name:
        node = ivar(node, name)
    node = deref(node)
    if node is None:
        return None
    return b2s(M.value_of(node))


def s(node, name=None):
    """取值并转成字符串（None -> ''）。"""
    v = val(node, name)
    if v is None:
        return ""
    if isinstance(v, bool):
        return "是" if v else "否"
    if isinstance(v, float):
        return ("%g" % v)
    return str(v)


def clean_text(t):
    """去掉换行/制表等，CSV 里一行一格。"""
    return " ".join(str(t).replace("\r", " ").replace("\n", " ").split())


def _pct(fv):
    """比例(0.6) → 「60%」；None → 空。"""
    if fv is None:
        return ""
    v = fv * 100
    return "%d%%" % int(v) if v == int(v) else "%g%%" % v


def fmt_effects(node):
    node = deref(node)
    if not isinstance(node, M.ArrayNode):
        return ""
    out = []
    for e in node.items:
        code = val(e, "@code")
        d1 = val(e, "@data_id")
        v1 = val(e, "@value1")
        v2 = val(e, "@value2")
        try:
            fv1 = float(v1 or 0)
        except (TypeError, ValueError):
            fv1 = 0.0
        try:
            fv2 = float(v2 or 0)
        except (TypeError, ValueError):
            fv2 = 0.0
        # 取值语义是逐条对过 Data 表的（别套 VX Ace 文档）：
        #   11/12 HP/MP回复：v1=最大值比例、v2=固定值（两者可同时出现）
        #   13 TP增加：v1=固定值
        #   21/22 附加/解除状态：data_id=状态，**概率在 v1**（v2 恒 0；旧版取 v2 全显示 0%）
        #   31 强化能力：data_id=参数，v1=回合数
        #   44 公共事件：data_id=事件 id
        if code in (11, 12):
            parts = []
            if fv1:
                parts.append("%+.0f%%" % (fv1 * 100))
            if fv2:
                parts.append("%+g" % fv2)
            if parts:
                out.append("%s %s" % ("HP回复" if code == 11 else "MP回复",
                                      "/".join(parts)))
        elif code == 13:
            if v1:
                out.append("TP增加 %+g" % fv1)
        elif code == 21:
            nm = _names("States").get(d1)
            if nm and fv1 > 0:      # data_id=0 / 概率=0 都是不生效的占位条目
                rate = "" if fv1 >= 1 else " " + _pct(fv1)
                out.append("附加状态[%s]%s" % (nm, rate))
        elif code == 22:
            nm = _names("States").get(d1)
            if nm:
                out.append("解除状态[%s]" % nm)
        elif code == 31:
            pname = PARAM_NAMES[d1] if isinstance(d1, int) and 0 <= d1 < 8 else d1
            out.append("强化[%s] %g回合" % (pname, fv1))
        elif code == 42:
            pname = PARAM_NAMES[d1] if isinstance(d1, int) and 0 <= d1 < 8 else d1
            out.append("成长[%s]+%g" % (pname, fv2))
        elif code == 43:
            out.append("习得技能[%s]" % (_names("Skills").get(d1) or "#%s" % d1))
        elif code == 44:
            out.append("公共事件[%s]" % (_names("CommonEvents").get(d1) or "#%s" % d1))
        else:
            out.append("%s(data=%s)" % (EFFECT_CODES.get(code, "效果%s" % code), d1))
    return "；".join(out)


# 伤害公式的「a./b. 属性」对照（a=施放者，b=目标；顺序长的在前防误替换）
_FORMULA_TOKENS = [
    (r"a\.attr\.get_(\S+?)(?=[\s*+\-/)])", r"\1"),
    (r"a\.mhp", "最大气血"), (r"a\.hp", "气血"),
    (r"a\.atk", "攻击"), (r"a\.def", "防御"),
    (r"a\.mat", "灵力"), (r"a\.mdf", "魔防"),
    (r"a\.agi", "速度"), (r"a\.luk", "幸运"), (r"a\.level", "等级"),
    (r"b\.mhp", "目标最大气血"), (r"b\.hp", "目标气血"),
    (r"b\.atk", "目标攻击"), (r"b\.def", "目标防御"),
    (r"b\.mat", "目标灵力"), (r"b\.mdf", "目标魔防"),
]


def _read_formula(node):
    """公式原文 → 可读：去注释、rand/default/属性 token 翻译。

    `default` 是本引擎的「基础伤害」占位（尝鲜版常见，内测版技能多为空）。
    翻不动的部分原样保留 —— 宁可少翻也不错译。
    """
    t = s(node, "@formula") or ""
    t = t.split("#")[0].strip()          # `999999999 #level` 这类行尾注释
    t = re.sub(r"rand\((\d+)\.\.(\d+)\)", r"随机(\1~\2)", t)
    t = re.sub(r"rand\((\d+)\)",
               lambda m: "随机(0~%d)" % (int(m.group(1)) - 1), t)
    t = re.sub(r"\bdefault\b", "基础伤害", t)
    for pat, rep in _FORMULA_TOKENS:
        t = re.sub(pat, rep, t)
    return t


def fmt_damage(node):
    node = deref(node)
    if node is None or not hasattr(node, "ivars"):
        return ""
    t = val(node, "@type")
    if not t:
        # type 0 = 无伤害。旧版会输出「伤害:无 公式:0 浮动:20% …」的噪声，直接留空。
        return ""
    parts = ["%s：%s" % (DAMAGE_TYPE_NAMES.get(t, t), _read_formula(node))]
    try:
        variance = int(val(node, "@variance") or 0)
    except (TypeError, ValueError):
        variance = 0
    if variance > 0:
        parts.append("浮动±%d%%" % variance)
    if val(node, "@critical"):
        parts.append("可会心")
    eid = val(node, "@element_id")
    if isinstance(eid, int) and eid > 0:
        en = _element_names().get(eid)
        parts.append("属性[%s]" % (en or "#%d" % eid))
    return "，".join(parts)


def fmt_features(node):
    node = deref(node)
    if not isinstance(node, M.ArrayNode):
        return ""
    out = []
    for f in node.items:
        code = val(f, "@code")
        d1 = val(f, "@data_id")
        v = val(f, "@value")
        try:
            fv = float(v) if v is not None else None
        except (TypeError, ValueError):
            fv = None
        if code in (11, 12, 13, 14, 15, 16, 17, 18):
            out.append("%s%+g%%" % (PARAM_NAMES[code - 11], float(v or 0) * 100))
        elif code == 21:
            en = _element_names().get(d1)
            out.append("属性[%s]有效度 %s" % (en or d1, _pct(fv)))
        elif code == 22:
            nm = _names("States").get(d1)
            if fv is not None and fv <= 0:
                out.append("状态[%s]抗性" % (nm or d1))
            else:
                out.append("状态[%s]有效度 %s" % (nm or d1, _pct(fv)))
        elif code == 23:
            out.append("状态[%s]无效" % (_names("States").get(d1) or d1))
        elif code == 31:
            en = _element_names().get(d1)
            out.append("攻击属性[%s]" % (en or d1))
        elif code == 32:
            nm = _names("States").get(d1)
            rate = "" if (fv or 0) >= 1 else " " + _pct(fv)
            out.append("攻击附加[%s]%s" % (nm or d1, rate))
        elif code == 33:
            out.append("攻击速度%+g" % (fv or 0))
        elif code == 34:
            out.append("攻击追加 %g 次" % (fv or 0))
        elif code == 35:
            out.append("普通攻击 %g 次" % (fv or 0))
        elif code in (51, 52):
            nm = _skill_type_names().get(d1)
            out.append("%s[%s]" % ("添加技能类型" if code == 51 else "封印技能类型",
                                   nm or ("#%s" % d1)))
        elif code in (53, 54, 55):
            nm = _names("Skills").get(d1)
            out.append("%s[%s]" % ({53: "添加技能", 54: "封印技能",
                                    55: "已学技能"}[code], nm or ("#%s" % d1)))
        else:
            out.append("%s(data=%s,val=%s)" % (FEATURE_CODES.get(code, "特性%s" % code),
                                               d1, v))
    return "；".join(out)


def fmt_params(node):
    node = deref(node)
    if isinstance(node, M.ArrayNode):
        return "/".join(str(val(x)) for x in node.items)
    if isinstance(node, M.UserDefNode):
        return "Table(%d 字节，职业成长曲线)" % len(node.data)
    return ""


def fmt_learnings(node):
    node = deref(node)
    if not isinstance(node, M.ArrayNode):
        return ""
    return "；".join("Lv%s→技能#%s" % (val(x, "@level"), val(x, "@skill_id"))
                    for x in node.items)


def fmt_actions(node):
    node = deref(node)
    if not isinstance(node, M.ArrayNode):
        return ""
    return "；".join("技能#%s(评分%s)" % (val(x, "@skill_id"), val(x, "@rating"))
                    for x in node.items)


def fmt_drops(node):
    """RGSS3 的 @kind 是 0=无 1=物品 2=武器 3=防具；没配的空槽直接不显示。"""
    node = deref(node)
    if not isinstance(node, M.ArrayNode):
        return ""
    kind = {1: "物品", 2: "武器", 3: "防具"}
    out = []
    for x in node.items:
        kk = val(x, "@kind")
        if not kk:                      # None / 0 → 没配掉落
            continue
        out.append("%s#%s（掉率 1/%s）" % (kind.get(kk, "类型%s" % kk),
                                          val(x, "@data_id"),
                                          val(x, "@denominator")))
    return "；".join(out) or "无"


def fmt_members(node):
    node = deref(node)
    if not isinstance(node, M.ArrayNode):
        return ""
    ids = [val(x, "@enemy_id") for x in node.items]
    uniq = {}
    for i in ids:
        uniq[i] = uniq.get(i, 0) + 1
    return "；".join("敌人#%s×%d" % (k, v) for k, v in uniq.items())


def fmt_list_count(node):
    node = deref(node)
    if isinstance(node, M.ArrayNode):
        return "%d 条指令" % len(node.items)
    return ""


def fmt_ivars(node, keys, sep="/"):
    return sep.join(s(node, k) for k in keys)


# --------------------------------------------------------------------------
# 表定义： (键, 中文名, 是否默认转, [列定义])
# 列定义 = (表头, 取值说明)；取值说明里 "@x" 表示取 ivar x，
# 前缀 fx:/dmg:/feat:/params:/learn:/act:/drop:/members:/n: 走上面的渲染函数。
# --------------------------------------------------------------------------
TABLES = [
    ("Items", "物品", True, [
        ("ID", "@id"), ("名称", "@name"), ("说明", "desc:@description,@note"),
        ("效果", "fx:@effects"), ("伤害", "dmg:@damage"), ("特性", "feat:@features"),
        ("价格", "@price"), ("消耗品", "@consumable"),
        ("使用场合", "map:@occasion"), ("影响范围", "map:@scope"),
        ("命中类型", "map:@hit_type"), ("成功率", "@success_rate"),
        ("使用次数", "@repeats"), ("TP增加", "@tp_gain"),
        ("类别", "map:@itype_id"), ("动画", "@animation_id"),
        ("图标", "@icon_index"), ("备注", "text:@note"),
    ]),
    ("Weapons", "武器", True, [
        ("ID", "@id"), ("名称", "@name"), ("说明", "desc:@description,@note"),
        ("能力加成(最大HP/MP/攻/防/魔攻/魔防/敏/运)", "params:@params"),
        ("特性", "feat:@features"), ("价格", "@price"),
        ("攻击动画", "@animation_id"), ("装备类型", "@wtype_id"),
        ("装备位置", "@etype_id"), ("图标", "@icon_index"), ("备注", "text:@note"),
    ]),
    ("Armors", "防具", True, [
        ("ID", "@id"), ("名称", "@name"), ("说明", "desc:@description,@note"),
        ("能力加成", "params:@params"), ("特性", "feat:@features"),
        ("价格", "@price"), ("防具类型", "@atype_id"),
        ("装备位置", "@etype_id"), ("图标", "@icon_index"), ("备注", "text:@note"),
    ]),
    ("Skills", "技能", True, [
        ("ID", "@id"), ("名称", "@name"), ("说明", "desc:@description,@note"),
        ("效果", "fx:@effects"), ("伤害", "dmg:@damage"),
        ("MP消耗", "@mp_cost"), ("TP消耗", "@tp_cost"), ("TP回复", "@tp_gain"),
        ("使用场合", "map:@occasion"), ("影响范围", "map:@scope"),
        ("命中类型", "map:@hit_type"), ("成功率", "@success_rate"),
        ("连续次数", "@repeats"), ("技能类型", "@stype_id"),
        ("需要武器类型", "reqw:@required_wtype_id1,@required_wtype_id2"),
        ("动画", "@animation_id"), ("图标", "@icon_index"),
        ("备注", "text:@note"),
    ]),
    ("States", "状态", True, [
        ("ID", "@id"), ("名称", "@name"), ("说明/描述", "@message1"),
        ("特性", "feat:@features"), ("优先级", "@priority"),
        ("行动限制", "map:@restriction"),
        ("持续回合", "turns:@min_turns,@max_turns"),
        ("受伤害解除概率", "@chance_by_damage"),
        ("走路解除步数", "@steps_to_remove"),
        ("走路解除", "@remove_by_walking"), ("战斗结束解除", "@remove_at_battle_end"),
        ("受伤解除", "@remove_by_damage"), ("行动限制解除", "@remove_by_restriction"),
        ("备注", "text:@note"),
    ]),
    ("Actors", "角色", True, [
        ("ID", "@id"), ("名称", "@name"), ("昵称", "@nickname"),
        ("职业ID", "@class_id"), ("初始等级", "@initial_level"),
        ("最大等级", "@max_level"), ("说明", "desc:@description,@note"),
        ("初始装备(0=无)", "params:@equips"),
        ("立绘", "@face_name"), ("行走图", "@character_name"),
        ("特性", "feat:@features"), ("备注", "text:@note"),
    ]),
    ("Classes", "职业", True, [
        ("ID", "@id"), ("名称", "@name"), ("说明", "desc:@description,@note"),
        ("学会技能", "learn:@learnings"), ("特性", "feat:@features"),
        ("升级经验曲线", "params:@exp_params"),
        ("成长曲线(Table)", "params:@params"), ("图标", "@icon_index"),
        ("备注", "text:@note"),
    ]),
    ("Enemies", "敌人", True, [
        ("ID", "@id"), ("名称", "@name"),
        ("能力(最大HP/MP/攻/防/魔攻/魔防/敏/运)", "params:@params"),
        ("经验", "@exp"), ("金钱", "@gold"), ("命中", "@hit"), ("回避", "@eva"),
        ("特性", "feat:@features"), ("行动", "act:@actions"),
        ("掉落", "drop:@drop_items"),
        ("战斗图", "@battler_name"), ("色调", "@battler_hue"),
        ("备注", "text:@note"),
    ]),
    ("Troops", "敌人队伍", False, [
        ("ID", "@id"), ("名称", "@name"), ("成员", "members:@members"),
        ("事件页数", "n:@pages"), ("备注", "text:@note"),
    ]),
    ("CommonEvents", "公共事件", False, [
        ("ID", "@id"), ("名称", "@name"), ("触发", "map:@trigger"),
        ("开关ID", "@switch_id"), ("指令数", "n:@list"),
    ]),
]

DEFAULT_KEYS = [t[0] for t in TABLES if t[2]]
ALL_KEYS = [t[0] for t in TABLES]

# 表键 -> (中文名, 文件, 是否默认)
_INFO = {t[0]: t for t in TABLES}
_cache = {}


# ---------------------------------------------------------------- 后台预载
# ⚠ 为什么要有：一张表要「解密 + 解析」0.05~0.24 秒（Skills 最大），而**第一次**
#   载入存档时界面正等着用它们（技能名/物品名/角色名）。五张常用的加起来
#   **0.66 秒**，占「载入存档」总时长的一半（2026-10-07 实测：1.52 秒里 0.66 秒
#   在解析表）。所以 App 一起来就把这几张表丢后台线程先解析掉，载入时直接命中。
#   实测载入 1.52 → 0.86 秒。
_PRELOAD_LOCK = threading.RLock()
_preload_done = set()
_preload_thread = None


def core_keys():
    """载入存档一定会用到的那几张表（顺序＝大概的耗时顺序，先啃大的）。"""
    return ["Skills", "Classes", "States", "Items", "Actors"]


def preload_done(keys=None):
    """这些表预载完了吗？—— 自动载入用它决定「要不要再等一会儿」。"""
    keys = core_keys() if keys is None else keys
    return all(k in _preload_done for k in keys)


def start_preload(keys=None):
    """起后台线程预载常用表（重复调用只会起一个）。返回线程对象。

    ⚠ 表读不出来（游戏没装 / 缺依赖）不是错，别抛也别弹框 —— 后面真要用时
      走的是同一条 `load()`，到那时才该报错。
    """
    global _preload_thread
    if _preload_thread is not None and _preload_thread.is_alive():
        return _preload_thread
    want = list(core_keys() if keys is None else keys)

    def work():
        for k in want:
            try:
                load(k)
            except Exception:
                pass
            finally:
                _preload_done.add(k)      # 失败也算"跑过了"，别让自动载入白等

    t = threading.Thread(target=work, name="xj-table-preload", daemon=True)
    _preload_thread = t
    t.start()
    return t
#: 名字实际是从哪来的（"游戏目录" / "内置表" / "无"），自检与排查用，见 `names_source()`
_SOURCE = {}


class DBError(Exception):
    pass


def table_label(key):
    t = _INFO.get(key)
    return t[1] if t else key


def is_default(key):
    """这张表是不是"默认就转"的那批。"""
    t = _INFO.get(key)
    return bool(t and t[2])


def _plain_path(key, game_dir):
    src = os.path.join(game_dir, "Data", "%s.rvdata2" % key)
    if not os.path.exists(src):
        raise DBError("找不到 %s" % src)
    d = os.path.join(os.path.dirname(HERE), "tools", "_plain")
    os.makedirs(d, exist_ok=True)
    # ⚠ 缓存名要带源文件指纹（大小 + mtime）。只按表名缓存的话，游戏更新换掉
    #   `Data\\X.rvdata2` 之后会把**旧表**一直用下去 —— 静默读到过期数据。
    st = os.stat(src)
    tag = "%x" % (st.st_size ^ (int(st.st_mtime) << 20))
    out = os.path.join(d, "Data_%s_%s.bin" % (key, tag))
    if not os.path.exists(out) or os.path.getsize(out) == 0:
        codec.decrypt_file(src, out)
    return out


def load(key, game_dir=None):
    """解析一张表，返回 (根节点, [(id, 对象节点), ...])。结果有缓存。

    ⚠ 整张表都锁着解析（见 `start_preload`）：主线程要用、后台预载线程正在
      解析同一张表时，这里**等**它解析完再取缓存 —— 等一会儿(<0.25s) 好过
      两张线程各解析一遍（纯 Python 解析，再解析一遍一样慢）。
    """
    game_dir = game_dir or paths.find_game_dir()
    ck = (key, game_dir)
    with _PRELOAD_LOCK:
        if ck in _cache:
            return _cache[ck]
        if key not in _INFO:
            raise DBError("没有这张表：%s" % key)
        plain = _plain_path(key, game_dir)
        objs = M.parse_stream(open(plain, "rb").read())
        root = objs[-1]["node"]
        items = []
        if isinstance(root, M.ArrayNode):
            for i, it in enumerate(root.items):
                n = deref(it)
                if n is None or isinstance(n, M.NilNode):
                    continue
                items.append((i, n))
        else:
            items = [(0, deref(root))]
        _cache[ck] = (root, items)
        return _cache[ck]


def _builtin():
    """内置表模块（`src/tables/db_table.py`）。**只在需要兜底时才 import** ——
    那是一份 100 KB 出头的字典字面量，正常路径（读得到游戏目录）没必要付这个钱。
    """
    try:
        from tables import db_table
        return db_table
    except Exception:
        return None


def names_source(key="Skills"):
    """上一次查这张表的名字时**实际用的是哪一路**："游戏目录" / "内置表" / "无" / "未查过"。

    纯排查与自检用（`XJ_SELFTEST` 会打出来），不参与任何业务判断。
    """
    return _SOURCE.get("names:%s" % key, "未查过")


def name_map(key, game_dir=None):
    """{id: 名称} —— 存档界面拿它把 id 显示成人能看懂的名字。

    读游戏目录**成功就用游戏目录**（跟「物品模板 / 克隆」同源，也最跟得上游戏版本）；
    失败（工具没放在游戏里、版本不符、内测版解密被授权链拦住…）才退回内置表。
    两条路都拿不到就是空字典 —— **绝不抛异常**，调用方照旧显示 `?`。
    """
    game_dir = game_dir or paths.find_game_dir()
    ck = ("__names__", key, game_dir)
    if ck in _cache:
        return _cache[ck]
    out = {}
    src = "无"
    try:
        for i, n in load(key, game_dir)[1]:
            out[i] = s(n, "@name")
        if out:
            src = "游戏目录"
    except Exception:
        out = {}
    if not out:
        b = _builtin()
        if b is not None and b.names(key):
            out = dict(b.names(key))
            src = "内置表"
    _SOURCE["names:%s" % key] = src
    _cache[ck] = out
    return out


def desc_map(key, game_dir=None):
    """{id: (名称, 完整说明)} —— 悬浮提示 / 技能说明框用。兜底规则同 `name_map`。"""
    game_dir = game_dir or paths.find_game_dir()
    ck = ("__descs__", key, game_dir)
    if ck in _cache:
        return _cache[ck]
    out = {}
    try:
        for i, n in load(key, game_dir)[1]:
            out[i] = (s(n, "@name") or "",
                      clean_desc(s(n, "@description"), s(n, "@note")))
    except Exception:
        out = {}
    if not out:
        b = _builtin()
        if b is not None:
            bn, bd = b.names(key), b.descs(key)
            for i in sorted(set(bn) | set(bd)):
                out[i] = (bn.get(i, ""), clean_desc(bd.get(i, "")))
    _cache[ck] = out
    return out


def class_learnings(class_id, game_dir=None):
    """某个职业的天生技能 → `[(等级, 技能 id), ...]`（Data\\Classes 的 `@learnings`）。

    ⚠ 读不到 Data 表时**必须**退回内置表，不能返回空：`actor_class_learnings()` /
    `class_skill_ids()` 拿它决定「清空门派」之后该给角色留哪些技能 —— 空列表会
    让技能被清光，那是静默的错误行为，不是"显示难看"。
    """
    try:
        cid = int(class_id)
    except (TypeError, ValueError):
        return []
    game_dir = game_dir or paths.find_game_dir()
    ck = ("__learn__", cid, game_dir)
    if ck in _cache:
        return _cache[ck]
    out = []
    try:
        _root, classes = load("Classes", game_dir)
        for i, node in classes:
            if i != cid:
                continue
            arr = deref(ivar(node, "@learnings"))
            if isinstance(arr, M.ArrayNode):
                for it in arr.items:
                    f = deref(it)
                    if f is None:
                        continue
                    sid = val(f, "@skill_id")
                    lv = val(f, "@level")
                    if isinstance(sid, int) and sid:
                        out.append((lv if isinstance(lv, int) else 1, sid))
            break
    except Exception:
        out = []
    if not out:
        b = _builtin()
        if b is not None:
            out = [tuple(p) for p in b.learnings(cid)]
    out = sorted(set(out))
    _cache[ck] = out
    return out


def builtin_rows(key):
    """内置表里这张表的 `[(id, 名称, 说明), ...]`（按 id 排）；没有就空表。

    给 `GameEditor.templates()` 兜底用：读不到 `Data\\<Key>.rvdata2` 时，
    「添加物品」的模板列表至少还能列出来（原来是一片空）。
    """
    b = _builtin()
    if b is None:
        return []
    nm, ds = b.names(key), b.descs(key)
    return [(i, nm.get(i) or ("#%d" % i), ds.get(i, ""))
            for i in sorted(set(nm) | set(ds))]


# --------------------------------------------------------------------------
# 效果/说明渲染用的名字解析（#id → 人话）。任何失败都退空 dict，绝不影响导出。
# --------------------------------------------------------------------------
_name_cache = {}


def _names(key):
    """{id: 名称}（懒加载 + 缓存；读不到就空 —— 渲染时退回 #id）。"""
    if key not in _name_cache:
        try:
            _name_cache[key] = dict(name_map(key))
        except Exception:
            _name_cache[key] = {}
    return _name_cache[key]


_system_cache = {}


def _system_array(ivar_name):
    """System.rvdata2 里的字符串数组 → {下标: 内容}（@elements/@skill_types）。"""
    if ivar_name not in _system_cache:
        out = {}
        try:
            p = _plain_path("System", paths.find_game_dir())
            objs = M.parse_stream(open(p, "rb").read())
            root = deref(objs[-1]["node"])
            arr = deref(ivar(root, ivar_name))
            if isinstance(arr, M.ArrayNode):
                for i, x in enumerate(arr.items):
                    v = val(x)
                    if v:
                        out[i] = v
        except Exception:
            out = {}
        _system_cache[ivar_name] = out
    return _system_cache[ivar_name]


def _element_names():
    return _system_array("@elements")


def _skill_type_names():
    return _system_array("@skill_types")


_RE_COLOR = re.compile(r"\\[cC]\[\d+\]")
_RE_HEX = re.compile(r"#[0-9A-Fa-f]{6}\b")
_RE_SPH = re.compile(r"<S:([\d\s,]+)>")


def _state_details(note):
    """备注里的 `state_details = [a, b, …]`（行匹配规则与游戏 ReadNote 一致）。

    `<S:N>` 里的 N 是**这个数组的下标**（不是状态 id）—— 游戏运行时由
    `RPG::UsableItem#description_ex` 用 `$data_states[arr[n]].name` 替换。
    """
    out = []
    m = re.search(r"^\s*state_details\s*=\s*\[([^\]]*)\]", note or "", re.M)
    if m:
        for x in m.group(1).split(","):
            x = x.strip()
            if x.isdigit():
                out.append(int(x))
    return out


def clean_desc(desc, note=""):
    """官方说明 → 可读文本：解 `<S:N>` 状态占位符 + 去掉颜色标记。

    - `<S:0>` / `<S:0,1>`：按备注 `state_details` 解成 `<剧毒/黑暗>`（与游戏
      运行时行为一致，只是不带颜色）；解不了才退「【状态】」占位。
    - 颜色码 `\\c[99]`、`#G/#R/#M/#Y`、6 位色号：游戏里是着色标记，纯文本无意义。
    - **换行归一**：作者在表里两种写法混着用 —— 真换行、字面 `\\n`
      （Items 320 处、Skills 19 处），还有 `\\r\\n`；统一成 `\\n`，否则界面上
      会原样显示成「\\n」两个字符，真 `\\r` 在 tk.Text 里还会渲染成怪字符。
    """
    t = desc or ""
    if "<S:" in t:
        ids = _state_details(note)
        st = _names("States")

        def _sub(m):
            names = []
            for k in m.group(1).split(","):
                k = k.strip()
                if k.isdigit() and int(k) < len(ids):
                    nm = st.get(ids[int(k)])
                    if nm:
                        names.append(nm)
            return "<%s>" % "/".join(names) if names else "【状态】"

        t = _RE_SPH.sub(_sub, t)
    t = _RE_COLOR.sub("", t)
    t = _RE_HEX.sub("", t)
    for c in ("#G", "#R", "#M", "#Y"):
        t = t.replace(c, "")
    t = t.replace("\r\n", "\n").replace("\r", "\n").replace("\\n", "\n")
    return t


def _note_literal(text):
    """把备注等号右边的 Ruby 字面量粗解成 Python 值（够用就行，解不了返回原文）。"""
    t = (text or "").strip()
    if not t:
        return None
    if t.startswith("["):
        end = t.rfind("]")
        inner = t[1:end] if end > 0 else t[1:]
        out = []
        for part in inner.split(","):
            v = _note_literal(part)
            if v is not None:
                out.append(v)
        return out
    if len(t) >= 2 and t[0] == t[-1] and t[0] in "\"'":
        return t[1:-1]
    try:
        return int(t)
    except ValueError:
        pass
    try:
        return float(t)
    except ValueError:
        pass
    return t


def note_val(note, key):
    """备注里一行 `key = 值` → Python 值（照游戏 `ReadNote.read`：逐行匹配
    `^\\s*key\\s*=`，等号右边按 Ruby 字面量解）。没有这一行返回 None。"""
    m = re.search(r"^\s*%s\s*=(.*)$" % re.escape(key), note or "",
                  re.M | re.I)
    if not m:
        return None
    return _note_literal(m.group(1))


_state_info_cache = {}


def _state_info():
    """`{状态 id: (名字, message1, 最短回合, 最长回合, 解除时机)}`（读不到就空）。"""
    if "v" not in _state_info_cache:
        out = {}
        try:
            for i, node in load("States")[1]:
                out[i] = (s(node, "@name") or "",
                          s(node, "@message1") or "",
                          val(node, "@min_turns"), val(node, "@max_turns"),
                          val(node, "@auto_removal_timing"))
        except Exception:
            out = {}
        _state_info_cache["v"] = out
    return _state_info_cache["v"]


def skill_extra(note, mp_cost=0, tp_cost=0):
    """技能说明**后面那几行附加信息** —— 口径照游戏
    `RPG::UsableItem#description_ex` + `Window_Info_Item#get_description`
    （本仓库 `!Tools/Github/huaji2-offline-server/scripts_dump`）：

    * 状态：`state_details` 里每个状态 → `<名字>：message1，持续到战斗结束 /
      持续到行动结束 / 持续 a~b 回合`（游戏还带 #G/#R 颜色，这里去掉）
    * `目标数 = t_nums[0](上限…)`、`攻击次数 = t_times[0]`、`伤害 = t_dmge`、
      `气血恢复量 = t_rvhp`、`法力恢复量 = t_rvmp`
    * `消耗：N点魔法`（备注带 `[mmp_cost]` → 「全部魔法」）、`消耗：N点怒气`
      （备注 `tp_cost` 优先于 `@tp_cost`）
    * `剩余冷却：0 / N 回合`（备注 `cooling`）

    ⚠ 游戏在战斗里会用「当前角色」算动态消耗，本工具一律按**非战斗**口径
      （直接 `@mp_cost`）—— 静态工具拿不到战斗中的加成。
    """
    note = note or ""
    out = []
    ids = _state_details(note)
    if ids:
        info = _state_info()
        for sid in ids:
            nm, msg, tmin, tmax, timing = info.get(
                sid, ("#%s" % sid, "", None, None, None))
            line = "<%s>：%s" % (nm or "#%s" % sid, msg or "（没有说明）")
            if timing == 0:
                line += "，持续到战斗结束"
            elif timing == 1:
                line += "，持续到行动结束"
            elif timing == 2 and tmin is not None and tmax is not None:
                line += "，持续%s回合" % (tmin if tmin == tmax
                                          else "%s~%s" % (tmin, tmax))
            out.append(line)
    for tag, key in (("目标数", "t_nums"), ("攻击次数", "t_times")):
        v = note_val(note, key)
        if v in (None, ""):
            continue
        if isinstance(v, list) and v:
            line = "%s = %s" % (tag, v[0])
            if len(v) > 1 and v[1]:
                line += "(上限%s)" % v[1]
        else:
            line = "%s = %s" % (tag, v)
        out.append(line)
    for tag, key in (("伤害", "t_dmge"), ("气血恢复量", "t_rvhp"),
                     ("法力恢复量", "t_rvmp")):
        v = note_val(note, key)
        if v in (None, ""):
            continue
        out.append("%s = %s" % (tag, v[0] if isinstance(v, list) and v else v))
    cost = []
    if "[mmp_cost]" in note:
        cost.append("全部魔法")
    else:
        try:
            mp = int(mp_cost or 0)
        except (TypeError, ValueError):
            mp = 0
        if mp:
            cost.append("%d点魔法" % mp)
    tpc = note_val(note, "tp_cost")
    if tpc is None:
        tpc = tp_cost
    try:
        tpc = int(tpc or 0)
    except (TypeError, ValueError):
        tpc = 0
    if tpc:
        cost.append("%d点怒气" % tpc)
    for c in cost:
        out.append("消耗：%s" % c)
    cooling = note_val(note, "cooling")
    if cooling not in (None, "", 0):
        out.append("剩余冷却：0 / %s 回合" % cooling)
    return out


def skill_map(game_dir=None):
    """`{id: (名字, 说明)}` —— 说明 = 官方说明（解 `<S:N>`）**＋游戏浮窗那几行**。

    `desc_map` 只管官方 `@description`；界面上的技能说明要跟游戏里看到的一致，
    所以这里额外把 `skill_extra()` 那几行（伤害/恢复量/目标数/攻击次数/消耗/
    冷却）接在后面。读不到 Data 表就退回 `desc_map`（少几行，但不会没内容）。
    """
    game_dir = game_dir or paths.find_game_dir()
    ck = ("__skillmap__", game_dir)
    if ck in _cache:
        return _cache[ck]
    out = {}
    try:
        for i, n in load("Skills", game_dir)[1]:
            note = s(n, "@note")
            desc = clean_desc(s(n, "@description"), note)
            extra = skill_extra(note, val(n, "@mp_cost"), val(n, "@tp_cost"))
            if extra:
                desc = (desc.rstrip() + "\n" + "\n".join(extra)).strip("\n")
            out[i] = (s(n, "@name") or "", desc)
        if not out:
            out = {}
    except Exception:
        out = {}
    if not out:
        out = desc_map("Skills", game_dir)
    _cache[ck] = out
    return out


#: 备注里的「开关型」标记 → 人话。语义都在游戏脚本里核过
#: （`Window_Item#use_item` / `Window_Item#ban?`、`RPG::UsableItem#single?` /
#: `#superposition?`，见本仓库 `!Tools/Github/huaji2-offline-server/scripts_dump`）。
ITEM_FLAGS = [
    ("[use_for_actor]", "只能对角色使用"),
    ("[use_for_baby]", "只能对召唤兽使用"),
    ("[Preposition]", "要先选中它、再点另一个格子（前置道具）"),
    ("[extend]", "可扩展（带附加属性）"),
    ("[single]", "不可叠加"),
    ("[superposition]", "可叠加（内容不同也不并格）"),
    ("[dynamic_hue]", "图标颜色随机"),
]

#: 分段行：`===药品===` / `======剑=======` / `---剧情道具----` / `--坐骑--` ——
#: 作者给表分的段，不是能进背包的东西。
#: ⚠ 破折号那批（Items 4 个、Skills 15 个、Actors / Classes 各 1 个）**2026-10-06
#:   才认**：原来只认 `=`，它们就顶着「物品 / 技能」的名头混在列表里；技能表更冤枉
#:   —— `---五庄观---` 这些门派标题不算边界，`==特技==` 的分段一路吃到下一个
#:   `=` 段（id 312「辅助技能」），13 个门派的技能归属全被写成「特技」。
_RE_SECTION = re.compile(r"^(?:=+|-{2,})(.+?)(?:=+|-{2,})$")


def section_of(name):
    """分段行 → 段名；不是分段行返回 None。"""
    m = _RE_SECTION.match((name or "").strip())
    if not m:
        return None
    return m.group(1).strip() or None


def item_extra(note, kind="Items"):
    """物品说明**后面那几行** —— 备注里能翻成人话的（等级 / 售价 / 使用限制…）。

    ⚠ 只写**在游戏脚本里核过语义**的键与标记；拿不准的一律不写 —— 宁可少一行，
      也不要编一条看起来像真的。
    """
    note = note or ""
    out = [text for flag, text in ITEM_FLAGS if flag in note]
    if kind == "Items":
        lv = note_val(note, "lv")
        if lv not in (None, ""):
            out.append("等级 %s" % lv)
    price = note_val(note, "price")
    if price not in (None, "", 0):
        out.append("售价 %s" % price)
    return out


def item_map(kind="Items", game_dir=None):
    """`{id: (名字, 说明)}` —— 说明 = `clean_desc()` ＋ `item_extra()` 那几行。

    **顺手把没意义的行滤掉**（2026-10-04 川：物品管理里别出现纯编号的东西）：

    * 分段行（`===药品===` / `======剑=======`）—— 不是能写进背包的东西；
    * **没名字**的行（含作者自己在表里写的注释行）—— 画迹2 三张表里一共
      689 个，界面上一律显示成 `#49` 这种，选中了还会把 id 写进背包。

    段名不丢，用 `item_group()` 取（给模板列表当「类别」列）。
    """
    game_dir = game_dir or paths.find_game_dir()
    ck = ("__itemmap__", kind, game_dir)
    if ck in _cache:
        return _cache[ck]
    out = {}
    try:
        for i, n in load(kind, game_dir)[1]:
            nm = s(n, "@name") or ""
            if section_of(nm):
                continue
            note = s(n, "@note")
            desc = clean_desc(s(n, "@description"), note)
            extra = item_extra(note, kind)
            if extra:
                desc = (desc.rstrip() + "\n" + "\n".join(extra)).strip("\n")
            if not nm.strip():
                continue        # 没名字的行列出来只有个 `#id`，选中还会写进背包
            out[i] = (nm, desc)
    except Exception:
        out = {}
    if not out:
        out = desc_map(kind, game_dir)
    _cache[ck] = out
    return out


def item_group(kind="Items", game_dir=None):
    """`{id: 段名}` —— 扫一遍原表，遇到分段行就把后面的 id 都算进这一段。

    ⚠ 扫的是**原表**（不是 `item_map()` 的结果）：分段行之间夹着大量空占位行，
      滤掉再扫就会把后面的东西算错段。
    """
    game_dir = game_dir or paths.find_game_dir()
    ck = ("__itemgrp__", kind, game_dir)
    if ck in _cache:
        return _cache[ck]
    out = {}
    cur = None
    try:
        for i, n in load(kind, game_dir)[1]:
            sec = section_of(s(n, "@name"))
            if sec:
                cur = sec
            if cur:
                out[i] = cur
    except Exception:
        out = {}
    _cache[ck] = out
    return out


def _cell(node, spec):
    """按列定义算一格。spec 形如 '@name' / 'fx:@effects' / 'map:@scope'。"""
    if ":" in spec and not spec.startswith("@"):
        kind, arg = spec.split(":", 1)
    else:
        kind, arg = "@", spec
    if kind == "@":
        return s(node, arg)
    if kind == "fx":
        return fmt_effects(ivar(node, arg))
    if kind == "dmg":
        return fmt_damage(ivar(node, arg))
    if kind == "feat":
        return fmt_features(ivar(node, arg))
    if kind == "params":
        return fmt_params(ivar(node, arg))
    if kind == "learn":
        return fmt_learnings(ivar(node, arg))
    if kind == "act":
        return fmt_actions(ivar(node, arg))
    if kind == "drop":
        return fmt_drops(ivar(node, arg))
    if kind == "members":
        return fmt_members(ivar(node, arg))
    if kind == "n":
        return fmt_list_count(ivar(node, arg))
    if kind == "text":
        return clean_text(s(node, arg))
    if kind == "desc":
        # 说明列：解 <S:N> 占位符 + 去颜色码（arg = "@description,@note"）
        a, b = arg.split(",")
        return clean_desc(s(node, a), s(node, b))
    if kind == "turns":
        a, b = arg.split(",")
        return "%s ~ %s" % (s(node, a), s(node, b))
    if kind == "reqw":
        a, b = arg.split(",")
        return "%s/%s" % (s(node, a), s(node, b))
    if kind == "map":
        v = val(node, arg)
        table = {"@occasion": OCCASION_NAMES, "@scope": SCOPE_NAMES,
                 "@hit_type": HIT_NAMES, "@itype_id": ITEM_TYPE_NAMES,
                 "@restriction": RESTRICT_NAMES, "@trigger": TRIGGER_NAMES}.get(arg, {})
        return "%s(%s)" % (table.get(v, v), v if table.get(v) is not None else "")
    return ""


def rows(key, game_dir=None, only_named=True):
    """返回 (表头, 数据行)。only_named=True 时跳过没名字的空占位行。"""
    _, items = load(key, game_dir)
    _, _, _, cols = _INFO[key]
    header = [c[0] for c in cols]
    data = []
    for i, node in items:
        row = []
        for _, spec in cols:
            row.append(clean_text(_cell(node, spec)))
        if only_named and not any(row):
            continue
        data.append(row)
    return header, data


def export_csv(key, out_dir=None, game_dir=None):
    out_dir = out_dir or DEFAULT_OUT
    game_dir = game_dir or paths.find_game_dir()
    os.makedirs(out_dir, exist_ok=True)
    header, data = rows(key, game_dir)
    path = os.path.join(out_dir, "%s_%s.csv" % (key, table_label(key)))
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(data)
    return path, len(data)


def export_all(out_dir=None, keys=None, game_dir=None):
    keys = keys or DEFAULT_KEYS
    out = []
    for k in keys:
        try:
            out.append(export_csv(k, out_dir, game_dir))
        except Exception as e:
            out.append(("%s（失败：%s）" % (k, e), 0))
    return out


def main():
    argv = sys.argv[1:]
    game = paths.find_game_dir()
    if not game:
        print("[NG] 没找到游戏目录，可设 XJ_GAME")
        return 1
    out_dir = DEFAULT_OUT
    if "--out" in argv:
        i = argv.index("--out")
        if i + 1 >= len(argv):
            print("[NG] --out 后面要跟一个目录，例如：python src/datatables.py --out csv")
            return 1
        out_dir = argv[i + 1]
        del argv[i:i + 2]
    if not argv:
        print("游戏目录 = %s" % game)
        print("%-14s %-8s %-8s %s" % ("表", "中文", "默认转", "行数"))
        for k in ALL_KEYS:
            try:
                n = len(rows(k, game)[1])
            except Exception as e:
                n = "失败：%s" % e
            print("%-14s %-8s %-8s %s" % (k, table_label(k),
                                          "是" if _INFO[k][2] else "否", n))
        print("\n用法：")
        print("  python src/datatables.py                          # 只看看有哪些表")
        print("  python src/datatables.py --out <目录>              # 转默认那批（8 张）")
        print("  python src/datatables.py --all --out <目录>        # 连可选表一起（10 张）")
        print("  python src/datatables.py Items Skills --out <目录>")
        return 0
    keys = ALL_KEYS if "--all" in argv else [a for a in argv if a in ALL_KEYS]
    bad = [a for a in argv if a not in ALL_KEYS and a != "--all"]
    if bad:
        print("[--] 不认识这些表名，已忽略：%s" % "、".join(bad))
    if not keys:
        keys = DEFAULT_KEYS
    print("游戏目录 = %s" % game)
    print("输出目录 = %s（共 %d 张表）" % (out_dir, len(keys)))
    n_bad = 0
    for path, n in export_all(out_dir, keys, game):
        if not n:
            n_bad += 1
        print("  %s %-58s %d 行" % ("[OK]" if n else "[NG]", path, n))
    return 1 if n_bad else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")
    sys.exit(main())
