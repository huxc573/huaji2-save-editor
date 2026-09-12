# -*- coding: utf-8 -*-
"""Data\\*.rvdata2 数据表：解析 + 转 CSV。

**是的，Data 目录下的 .rvdata2 全都被加密了**（和存档同一套 main.dll 加密），
密钥是 `761205`（见 xj_codec.KEY_DATA），本模块会自动解密 + 解析。

能转的有用的表（默认这一批；Map / System / Scripts / Tilesets / Animations 不转）：

    Items 物品 · Weapons 武器 · Armors 防具 · Skills 技能 · States 状态
    Actors 角色 · Classes 职业 · Enemies 敌人
    （可选：Troops 敌人队伍 · CommonEvents 公共事件）

CSV 用 **utf-8-sig** 编码（Excel 双击直接正常显示中文），一行一个 id，
列名是中文，值里嵌套的东西（效果 / 特性 / 伤害 / 学会技能…）会翻成人话，
比如 `@effects` 会写成「HP回复 +500；附加状态#1 100%」。

用法：
    python src/xj_db.py                      # 列出所有表 + 行数
    python src/xj_db.py --out <目录>          # 默认那批全转
    python src/xj_db.py --all --out <目录>    # 连 Troops/CommonEvents 一起转
    python src/xj_db.py Items Skills --out <目录>
"""
import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import xj_codec  # noqa: E402
import xj_env  # noqa: E402
import xj_marshal as M  # noqa: E402

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
        name = EFFECT_CODES.get(code, "效果%s" % code)
        if code in (11, 12):
            out.append("%s %+g%%" % (name, float(v2 or 0)))
        elif code == 13:
            out.append("%s %+g" % (name, float(v2 or 0)))
        elif code in (21, 22):
            out.append("%s#%s %.0f%%" % (name, d1, float(v2 or 0) * 100))
        elif code in (31, 32, 33, 34):
            pname = PARAM_NAMES[d1] if isinstance(d1, int) and 0 <= d1 < 8 else d1
            out.append("%s[%s]%.0f" % (name, pname, float(v2 or 0) * 100))
        elif code == 42:
            pname = PARAM_NAMES[d1] if isinstance(d1, int) and 0 <= d1 < 8 else d1
            out.append("成长[%s]+%g" % (pname, float(v2 or 0)))
        elif code == 43:
            out.append("习得技能#%s" % d1)
        elif code == 44:
            out.append("公共事件#%s" % d1)
        else:
            out.append("%s(data=%s,%s,%s)" % (name, d1, v1, v2))
    return "；".join(out)


def fmt_damage(node):
    node = deref(node)
    if node is None or not hasattr(node, "ivars"):
        return ""
    t = val(node, "@type")
    return "伤害:%s 公式:%s 浮动:%s%% 会心:%s 属性:%s" % (
        DAMAGE_TYPE_NAMES.get(t, t), s(node, "@formula"), s(node, "@variance"),
        s(node, "@critical"), s(node, "@element_id"))


def fmt_features(node):
    node = deref(node)
    if not isinstance(node, M.ArrayNode):
        return ""
    out = []
    for f in node.items:
        code = val(f, "@code")
        name = FEATURE_CODES.get(code, "特性%s" % code)
        if code in (11, 12, 13, 14, 15, 16, 17, 18):
            out.append("%s%+g%%" % (name, float(val(f, "@value") or 0) * 100))
        elif code in (31, 32, 33, 53, 54, 55):
            out.append("%s#%s" % (name, val(f, "@data_id")))
        else:
            out.append("%s(data=%s,val=%s)" % (name, val(f, "@data_id"),
                                               val(f, "@value")))
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
        ("ID", "@id"), ("名称", "@name"), ("说明", "@description"),
        ("效果", "fx:@effects"), ("伤害", "dmg:@damage"), ("特性", "feat:@features"),
        ("价格", "@price"), ("消耗品", "@consumable"),
        ("使用场合", "map:@occasion"), ("影响范围", "map:@scope"),
        ("命中类型", "map:@hit_type"), ("成功率", "@success_rate"),
        ("使用次数", "@repeats"), ("TP增加", "@tp_gain"),
        ("类别", "map:@itype_id"), ("动画", "@animation_id"),
        ("图标", "@icon_index"), ("备注", "text:@note"),
    ]),
    ("Weapons", "武器", True, [
        ("ID", "@id"), ("名称", "@name"), ("说明", "@description"),
        ("能力加成(最大HP/MP/攻/防/魔攻/魔防/敏/运)", "params:@params"),
        ("特性", "feat:@features"), ("价格", "@price"),
        ("攻击动画", "@animation_id"), ("装备类型", "@wtype_id"),
        ("装备位置", "@etype_id"), ("图标", "@icon_index"), ("备注", "text:@note"),
    ]),
    ("Armors", "防具", True, [
        ("ID", "@id"), ("名称", "@name"), ("说明", "@description"),
        ("能力加成", "params:@params"), ("特性", "feat:@features"),
        ("价格", "@price"), ("防具类型", "@atype_id"),
        ("装备位置", "@etype_id"), ("图标", "@icon_index"), ("备注", "text:@note"),
    ]),
    ("Skills", "技能", True, [
        ("ID", "@id"), ("名称", "@name"), ("说明", "@description"),
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
        ("最大等级", "@max_level"), ("说明", "@description"),
        ("初始装备(0=无)", "params:@equips"),
        ("立绘", "@face_name"), ("行走图", "@character_name"),
        ("特性", "feat:@features"), ("备注", "text:@note"),
    ]),
    ("Classes", "职业", True, [
        ("ID", "@id"), ("名称", "@name"), ("说明", "@description"),
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
    out = os.path.join(d, "Data_%s.rvdata2.bin" % key)
    if not os.path.exists(out) or os.path.getsize(out) == 0:
        xj_codec.decrypt_file(src, out)
    return out


def load(key, game_dir=None):
    """解析一张表，返回 (根节点, [(id, 对象节点), ...])。结果有缓存。"""
    game_dir = game_dir or xj_env.find_game_dir()
    ck = (key, game_dir)
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


def name_map(key, game_dir=None):
    """{id: 名称} —— 存档界面拿它把 id 显示成人能看懂的名字。"""
    game_dir = game_dir or xj_env.find_game_dir()
    ck = ("__names__", key, game_dir)
    if ck in _cache:
        return _cache[ck]
    out = {}
    try:
        for i, n in load(key, game_dir)[1]:
            out[i] = s(n, "@name")
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
    game_dir = game_dir or xj_env.find_game_dir()
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
    game = xj_env.find_game_dir()
    if not game:
        print("[NG] 没找到游戏目录，可设 XJ_GAME")
        return 1
    out_dir = DEFAULT_OUT
    if "--out" in argv:
        i = argv.index("--out")
        if i + 1 >= len(argv):
            print("[NG] --out 后面要跟一个目录，例如：python src/xj_db.py --out csv")
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
        print("  python src/xj_db.py                          # 只看看有哪些表")
        print("  python src/xj_db.py --out <目录>              # 转默认那批（8 张）")
        print("  python src/xj_db.py --all --out <目录>        # 连可选表一起（10 张）")
        print("  python src/xj_db.py Items Skills --out <目录>")
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
