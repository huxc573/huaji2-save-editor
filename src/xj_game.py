# -*- coding: utf-8 -*-
"""v0.4 新增的"游戏内容"编辑层：存银 / 背包 / 经验 / 召唤兽 / 防作弊体检。

和 `xj_save.SaveDoc` 的分工：
  * `xj_save` 管**存档骨架**（分区、Lock、开关变量、角色基础字段）；
  * 这里管**游戏玩法数据**（背包 4 页×20 格、召唤兽资质、经验、以及游戏的
    `$jiance` 周期性反作弊检查 和 `Change` 物品计数校验）。

防作弊（v0.4 新发现，见 docs/逆向过程.md）：

1. **周期检查**（脚本 29455 行起，每 300 帧一次）：
       $jiance = [MAX_LEVEL_ACTOR*761205, MAX_LEVEL_BABY*761205,
                  MAX_GOLD*654321, MAX_WAREHOUSE[1]*159753]
       任一角色 level > 60               → 作弊
       某角色当前召唤兽 level > 65        → 作弊
       $game_party.gold > 30,000,000      → 作弊
       $game_party.hash[:warehouse_page]>3→ 作弊
       a.attr.point_num > a.level*10+500  → 作弊   （point_num = 体质+法力+力量+耐力+敏捷）
   一旦被判定作弊：`$game_system.cheated = Graphics.frame_count`，
   游戏内 20 分钟后弹警告、25 分钟后 `msgbox "存档异常！" + exit`。
   ⇒ 改数值时**必须**守住这些上限；本模块提供"体检 + 一键按规则修复 + 清除作弊标记"。

2. **物品计数校验**：游戏给物品记了一笔"累计获得数量"，
   存在 `$game_system.security[:items][id]`（`Change` 对象，逐位数字 AES-ECB 加密）。
   改背包数量后如果不同步，游戏下次**合法获得**同一件物品时会发现对不上 → 记作弊。
   ⇒ 本模块改数量/加物品时自动同步（AES 实现在 `xj_aes`，密钥来自游戏脚本第 1142 行）。
"""
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import xj_aes  # noqa: E402
import xj_marshal as M  # noqa: E402
import xj_notes  # noqa: E402
from xj_save import _deref, _as_str, ivar, hash_get, hash_put_pairs  # noqa: E402

# 游戏里的上限（Config::Game + $jiance）
MAX_LEVEL_ACTOR = xj_notes.MAX_LEVEL_ACTOR
MAX_LEVEL_BABY = xj_notes.MAX_LEVEL_BABY
MAX_GOLD = xj_notes.MAX_GOLD
MAX_ITEM = xj_notes.MAX_ITEM
MAX_WAREHOUSE_PAGE = 3
MAX_BABY_LIFE = xj_notes.MAX_BABY_LIFE
MAX_BABY_LOYALTY = xj_notes.MAX_BABY_LOYALTY
MAX_PACK_PAGE = xj_notes.PACK_PAGES
PACK_PAGE_SIZE = xj_notes.PACK_PAGE_SIZE

KINDS = (("Items", "@items", "道具", "Items"),
         ("Weapons", "@weapons", "武器", "Weapons"),
         ("Armors", "@armors", "防具", "Armors"))


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


def get_int(node, default=0):
    v = M.value_of(_deref(node))
    return default if v is None else int(v)


def get_float(node, default=0.0):
    v = M.value_of(_deref(node))
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def set_ivar(obj, name, node):
    """替换对象的某个 ivar 的值节点（保持位置）。"""
    obj = _deref(obj)
    for i, (k, _v) in enumerate(obj.ivars):
        if k == name:
            obj.ivars[i] = (k, node)
            return True
    return False


class GameEditor(object):
    """针对一份 SaveDoc 的游戏数据编辑。"""

    def __init__(self, sv):
        self.sv = sv
        self.doc = sv.doc

    # ==================================================== 存银 / 上限
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

    def _hash(self):
        """$game_party.hash（Key 是符号，这里用字符串键取）。"""
        return _deref(ivar(self.sv.section("party"), "@hash"))

    # ==================================================== 背包
    def container(self, kind="Items"):
        """返回容器 HashNode（key = 槽号，value = [对象, 数量]）。"""
        for key, ivname, _cn, _db in KINDS:
            if key == kind:
                node = _deref(ivar(self.sv.section("party"), ivname))
                if isinstance(node, M.HashNode):
                    return node
                raise KeyError("存档里没有 %s" % ivname)
        raise KeyError("不认识的背包类型 %r" % kind)

    def slot_key(self, page, index):
        return page * PACK_PAGE_SIZE + index

    def _pair_index(self, h, slot):
        for i, (k, _v) in enumerate(h.pairs):
            if M.value_of(_deref(k)) == slot:
                return i
        return -1

    def bag(self, kind="Items", page=None):
        """背包内容：[(槽号, 翻页, 页内格, id, 名称, 数量), ...]，空槽不列。

        page=None 表示整本背包（4 页 × 20 格），给了 page 就只看那一页。
        """
        h = self.container(kind)
        nm = self._name_map(kind)
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
            iid = get_int(ivar(item, "@id"), -1) if item is not None else -1
            count = get_int(arr.items[1]) if len(arr.items) > 1 else 1
            out.append((slot, p, idx, iid, nm.get(iid, "?"), count))
        out.sort()
        return out

    def empty_slots(self, kind="Items", page=None):
        h = self.container(kind)
        used = set()
        for k, _v in h.pairs:
            slot = M.value_of(_deref(k))
            if isinstance(slot, int):
                used.add(slot)
        pages = [page] if page is not None else range(MAX_PACK_PAGE)
        out = []
        for p in pages:
            for i in range(PACK_PAGE_SIZE):
                s = self.slot_key(p, i)
                if s not in used:
                    out.append(s)
        return out

    def _name_map(self, kind):
        import xj_db
        try:
            return xj_db.name_map(kind)
        except Exception:
            return {}

    def item_name(self, kind, item_id):
        return self._name_map(kind).get(item_id, "?")

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
        count = max(0, min(int(count), 99 * 99))
        self.doc.set_value(_deref(arr.items[1]), count)
        if kind == "Items":
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
        if kind == "Items" and iid >= 0:
            self.sync_security_item(iid)
        return True

    def add_item(self, kind, slot, item_id, count=1):
        """往空格子里加一件物品（结构性改动：从 Data 模板复制一份对象）。

        只允许往**空槽**加：这样不会覆盖玩家已有的东西。
        """
        h = self.container(kind)
        if self._pair_index(h, slot) >= 0:
            arr = _deref(h.pairs[self._pair_index(h, slot)][1])
            if isinstance(arr, M.ArrayNode) and arr.items:
                raise ValueError("第 %d 格已经有东西了" % slot)
        node = self.make_item(kind, item_id)
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
        if kind == "Items":
            self.sync_security_item(item_id)
        self.doc.mark_structural()
        return node

    def make_item(self, kind, item_id):
        """按 `Data\\<kind>.rvdata2` 里的模板造一个物品对象。

        模板只有 19 个 ivar，存档里的物品还多了游戏自己加的 5 个
        （`@result_note` / `@attr` / `@update` / `@new` / `@transaction_code`）——
        这几个照存档里的同类物品补上，免得游戏读到 nil 出岔子。
        """
        import xj_db
        root, items = xj_db.load(kind)
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
        return node

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

    # ==================================================== 物品计数校验（Change）
    def security_hash(self):
        sec = _deref(ivar(self.sv.section("system"), "@security"))
        if not isinstance(sec, M.HashNode):
            return None, None
        items = _deref(hash_get(sec, "items"))
        return (sec, items if isinstance(items, M.HashNode) else None)

    def security_total(self, item_id):
        """游戏记录的"该物品累计获得数量"（读不出来返回 None）。"""
        _sec, items = self.security_hash()
        if items is None:
            return None
        ch = _deref(hash_get(items, item_id))
        if ch is None:
            return None
        val = _deref(ivar(ch, "@value"))
        if not isinstance(val, M.ArrayNode):
            return None
        digits = []
        for x in val.items:
            d = xj_aes.decrypt_digit(_as_str(x))
            if d is None:
                return None
            digits.append(d)
        return int("".join(digits) or "0")

    def _set_security_total(self, ch, total):
        arr = M.ArrayNode([hex_str_node(xj_aes.encrypt_digit(d))
                           for d in str(int(total))])
        if not set_ivar(ch, "@value", arr):
            ch.ivars.append(("@value", arr))

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
                        [hex_str_node(xj_aes.encrypt_digit(d))
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
        """角色经验（Hash：职业id → 经验）。"""
        h = _deref(ivar(actor, "@exp"))
        if not isinstance(h, M.HashNode) or not h.pairs:
            return 0
        return M.value_of(_deref(h.pairs[0][1])) or 0

    def set_exp(self, actor, value):
        h = _deref(ivar(actor, "@exp"))
        if not isinstance(h, M.HashNode) or not h.pairs:
            raise KeyError("这个角色没有 @exp")
        self.doc.set_value(_deref(h.pairs[0][1]), int(value))
        return int(value)

    def exp_key(self, actor):
        h = _deref(ivar(actor, "@exp"))
        if isinstance(h, M.HashNode) and h.pairs:
            return M.value_of(_deref(h.pairs[0][0]))
        return None

    def limit_exp(self, actor):
        return get_int(ivar(actor, "@limit_exp"))

    def set_limit_exp(self, actor, value):
        node = _deref(ivar(actor, "@limit_exp"))
        if node is None:
            raise KeyError("这个角色没有 @limit_exp")
        self.doc.set_value(node, int(value))
        return int(value)

    def add_exp(self, actor, delta):
        return self.set_exp(actor, self.exp(actor) + int(delta))

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

    #: (键, 说明, ivar 路径, 类型)
    BABY_FIELDS = (
        ("level", "等级（上限 65）", "@level", "int"),
        ("hp", "气血（HP）", "@hp", "int"),
        ("mp", "魔法（MP）", "@mp", "int"),
        ("tp", "TP", "@tp", "int"),
        ("exp", "当前经验", "@exp#", "int"),
        ("loyalty", "忠诚度（<100 不能参战）", "@attr.@loyalty", "float"),
        ("life", "寿命（上限 12000）", "@attr.@life", "int"),
        ("grow", "成长", "@attr.@grow", "float"),
        ("atk", "攻击资质", "@attr.@atk", "int"),
        ("def", "防御资质", "@attr.@def", "int"),
        ("hpq", "体力资质", "@attr.@hp", "int"),
        ("mpq", "法力资质", "@attr.@mp", "int"),
        ("agi", "速度资质", "@attr.@agi", "int"),
        ("eva", "躲闪资质", "@attr.@eva", "int"),
        ("体质", "体质", "@attr.@体质", "int"),
        ("法力", "法力", "@attr.@法力", "int"),
        ("力量", "力量", "@attr.@力量", "int"),
        ("耐力", "耐力", "@attr.@耐力", "int"),
        ("敏捷", "敏捷", "@attr.@敏捷", "int"),
        ("潜能", "潜能", "@attr.@潜能", "int"),
    )

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
                return (get_float(node) if typ == "float" else get_int(node))
        return None

    def set_baby(self, baby, key, value):
        for k, _label, path, typ in self.BABY_FIELDS:
            if k != key:
                continue
            node = self._resolve(baby, path)
            if node is None:
                raise KeyError("召唤兽没有 %s（%s）" % (k, path))
            if typ == "float":
                self.doc.set_value(node, float(value))
            else:
                self.doc.set_value(node, int(value))
            return value
        raise KeyError("不认识的召唤兽字段 %r" % key)

    def baby_preset(self, baby, what):
        """常用预设：满级 / 回满 / 忠诚满 / 寿命满 / 资质 +100。"""
        did = []
        if what == "maxlv":
            self.set_baby(baby, "level", MAX_LEVEL_BABY)
            did.append("等级→%d" % MAX_LEVEL_BABY)
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
        elif what == "qual":
            for k in ("atk", "def", "hpq", "mpq", "agi", "eva"):
                v = self.baby_value(baby, k)
                if v is not None:
                    self.set_baby(baby, k, v + 100)
            did.append("六项资质 +100")
        elif what == "five":
            for k in ("体质", "法力", "力量", "耐力", "敏捷"):
                v = self.baby_value(baby, k)
                if v is not None:
                    self.set_baby(baby, k, v + 10)
            did.append("五维 +10")
        return did

    def baby_skills(self, baby):
        arr = _deref(ivar(baby, "@skills"))
        if not isinstance(arr, M.ArrayNode):
            return []
        import xj_db
        try:
            nm = xj_db.name_map("Skills")
        except Exception:
            nm = {}
        return [(M.value_of(_deref(x)), nm.get(M.value_of(_deref(x)), "?"))
                for x in arr.items]

    # ==================================================== 防作弊体检
    def point_num(self, actor):
        """五维之和（游戏的反作弊就是这么算的：不含潜能）。"""
        total = 0
        for k in ("@体质", "@法力", "@力量", "@耐力", "@敏捷"):
            total += get_int(ivar(_deref(ivar(actor, "@attr")), k))
        return total

    def anti_cheat_report(self):
        """返回 [(项目, 当前, 上限, 是否超限, 说明), ...]。"""
        rows = []

        def row(name, cur, limit, why):
            rows.append((name, cur, limit, cur is not None and cur > limit, why))

        gold = self.sv.gold()
        row("存银", gold, MAX_GOLD, "游戏每 300 帧检查一次，超了算作弊")
        row("仓库页号 warehouse_page", self.warehouse_page(), MAX_WAREHOUSE_PAGE,
            "同上")
        for aid, a in self.sv.actors():
            nm = self.sv.actor_name(a) or ("角色%d" % aid)
            row("%s 等级" % nm, get_int(ivar(a, "@level")), MAX_LEVEL_ACTOR,
                "上限来自 Config::Game::MAX_LEVEL_ACTOR")
            pn = self.point_num(a)
            lim = get_int(ivar(a, "@level")) * 10 + 500
            rows.append(("%s 五维总点数" % nm, pn, lim, pn > lim,
                         "上限 = 等级*10+500（体质+法力+力量+耐力+敏捷）"))
            for i, b in self.babies(a):
                row("%s 的召唤兽「%s」等级" % (nm, self.baby_name(b)),
                    get_int(ivar(b, "@level")), MAX_LEVEL_BABY,
                    "上限来自 Config::Game::MAX_LEVEL_BABY")
        ch = M.value_of(_deref(ivar(self.sv.section("system"), "@cheated")))
        rows.append(("作弊标记 @cheated", ch, 0, bool(ch),
                     "非 false 表示游戏已经判定作弊："
                     "20 分钟后警告、25 分钟后强制退出"))
        for iid, nm, rec, act in self.security_rows():
            if rec is not None and rec != act:
                rows.append(("物品计数校验：%s (id=%d)" % (nm, iid), act, rec,
                             True, "背包里有 %d 个，游戏记录的是 %d 个" % (act, rec)))
        return rows

    def fix_anti_cheat(self, clamp=True, clear_flag=True, resync=True):
        """按游戏规则把越界的东西压回上限，并（可选）清掉作弊标记。"""
        done = []
        if clamp:
            gold = self.sv.gold()
            if gold > MAX_GOLD:
                self.sv.set_gold(MAX_GOLD)
                done.append("存银 %d → %d" % (gold, MAX_GOLD))
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
            n = self.resync_security()
            if n:
                done.append("同步了 %d 件物品的计数校验" % n)
        if clear_flag:
            n = self.clear_cheat_flag()
            if n:
                done.append("已清除作弊标记（%s）" % "、".join(n))
        return done

    def clear_cheat_flag(self):
        """把 `@cheated` 置 false，并把 keyword 里的 'VNE' 标记去掉。"""
        done = []
        sysn = self.sv.section("system")
        node = _deref(ivar(sysn, "@cheated"))
        if node is not None:
            cur = M.value_of(node)
            if cur:
                self.doc.set_value(node, False)
                done.append("@cheated: %r → false" % (cur,))
        kw = _deref(ivar(sysn, "@keyword"))
        if isinstance(kw, M.ArrayNode):
            keep = [x for x in kw.items
                    if _as_str(x) not in ("VNE",)]
            if len(keep) != len(kw.items):
                kw.items = keep
                self.doc.mark_structural()
                done.append("keyword 去掉了 %d 个 VNE"
                            % (len(kw.items) + len(keep) - 2 * len(keep)))
        return done
