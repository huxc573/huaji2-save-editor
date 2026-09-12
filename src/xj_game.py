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
import xj_payload  # noqa: E402
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
        名称按**物件自己的类**选表（背包里混装着道具/武器/防具）。
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
            iid = get_int(ivar(item, "@id"), -1) if item is not None else -1
            nm = self.item_display_name(item, "?") if item is not None else "?"
            count = get_int(arr.items[1]) if len(arr.items) > 1 else 1
            out.append((slot, p, idx, iid, nm, count))
        out.sort()
        return out

    def templates(self, kind="Items", keyword=None, limit=500):
        """物品模板表：[(id, 名称, 说明), ...]（从 Data\\<kind>.rvdata2 读）。

        仿画迹1：右边一个可搜索的模板列表，选中后写进背包格子。
        """
        import xj_db
        _root, items = xj_db.load(kind)
        kw = (keyword or "").strip().lower()
        out = []
        for i, node in items:
            nm = xj_db.s(node, "@name") or ("#%d" % i)
            desc = (xj_db.s(node, "@description") or "")[:40].replace("\n", " ")
            if kw and kw not in nm.lower() and kw not in str(i) \
                    and kw not in desc.lower():
                continue
            out.append((i, nm, desc))
            if len(out) >= limit:
                break
        return out

    def set_all_counts(self, kind="Items", count=99, page=None):
        """把（某一页/整本）已有的格子数量批量改成 count（仿画迹1 的批量改）。"""
        count = max(0, min(int(count), MAX_ITEM))
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
        for key, _iv, cn, db in KINDS:
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
                elif cnt > MAX_ITEM:
                    out.append((key, slot, nm, "数量 %d 超过单格上限 %d"
                                % (cnt, MAX_ITEM), True,
                                {"id": iid, "count": cnt}))
                if iid in seen:
                    out.append((key, slot, nm, "和 %d 号格子重复（同一物品占两格）"
                                % seen[iid], True,
                                {"id": iid, "count": cnt, "dup_of": seen[iid]}))
                else:
                    seen[iid] = slot
                # 孵化蛋/礼包这类“运行时才填内容”的东西：@attr 空的话一用就报
                # `undefined method '[]' for nil:NilClass`
                need_pay, _nm = self.item_needs_payload(key, iid)
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
                self._fix_payload(it, kind, extra.get("id", -1))
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
                if total > MAX_ITEM:            # 上限就留一格 99、多余丢掉
                    total = MAX_ITEM
                self.set_count(kind, keep, total)
                self.clear_slot(kind, slot)
                done.append((kind, slot, "%s 并到 %d 号格子（现在 %d 个）"
                             % (name, keep, total)))
                continue
            if "超过" in why:
                self.set_count(kind, slot, MAX_ITEM)
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

    def machine_id_now(self):
        """本机机器码（调 main.dll!get_hard_disk_character）。"""
        import xj_codec
        return xj_codec.try_machine_id()

    def machine_status(self):
        """返回 (本机机器码 或 None, 出错原因, 存档记录列表, 本机是否在档)。"""
        now, err = self.machine_id_now()
        ids = self.machine_ids()
        return now, err, ids, bool(now and now in ids)
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

    def add_item(self, kind, slot, item_id, count=1, kid=None, clone_like=True):
        """往空格子里加一件物品（结构性改动）。

        优先克隆**存档里同款**（带运行时内容）；没有才用 Data 模板新建。
        只允许往**空槽**加：这样不会覆盖玩家已有的东西。
        """
        h = self.container(kind)
        if self._pair_index(h, slot) >= 0:
            arr = _deref(h.pairs[self._pair_index(h, slot)][1])
            if isinstance(arr, M.ArrayNode) and arr.items:
                raise ValueError("第 %d 格已经有东西了" % slot)
        like = self.find_like(kind, item_id) if clone_like else None
        node = self.make_item(kind, item_id, kid=kid, like=like)
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

    def slot_info(self, kind, slot):
        """某一格的内容：`(物品id, 数量)`；空格/坏格返回 None。"""
        for s, _p, _i, iid, _nm, cnt in self.bag(kind):
            if s == slot:
                return (iid, cnt)
        return None

    def set_item(self, kind, slot, item_id, count=None, kid=None,
                 clone_like=True):
        """把某一格**换成**另一件物品（从 Data 模板新建对象，仿画迹1 的"写入槽位"）。

        count=None 表示沿用原来那一格的数量（原来是空的就是 1）。
        这是结构性改动（保存时会整档重写），并且会自动同步物品计数校验。
        """
        old = self.slot_info(kind, slot)
        if count is None:
            count = old[1] if old else 1
        count = max(0, min(int(count), MAX_ITEM))
        try:
            self.make_item(kind, item_id, kid=kid,
                           like=self.find_like(kind, item_id) if clone_like
                           else None)      # 先确认能造出来，别改到一半失败
        except KeyError:
            raise
        if old is not None:
            self.clear_slot(kind, slot)         # 先腾空（置 nil，不删 key）
        self.add_item(kind, slot, item_id, count, kid=kid, clone_like=clone_like)
        return count

    def make_item(self, kind, item_id, kid=None, like=None):
        """造一个物品对象。

        优先 `like`：**存档里已经有的同一件东西**（连 `@attr` 里的运行时内容
        一起克隆）——游戏自己发的孵化蛋/礼包里的内容就是现抽的，
        从模板凭空造会缺东西（用起来直接 NoMethodError）。
        没参照物时才用 Data 模板 + 补上游戏自加的 5 个 ivar，
        并且对“运行时才填内容”的家族（孵化蛋/礼包/图纸…）现生成一份。

        kid：孵化类物品的“孵出/开出什么”id；不给就随机（自己按游戏的范围抽）。
        """
        import xj_db
        if like is not None:
            node = clone_node(like)
            self._fix_payload(node, kind, item_id, kid)
            return node
        _root, items = xj_db.load(kind)
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
        """读一个物件 `@attr` 里的运行时内容：`(type, data)`，没有则 (None, None)。"""
        a = _deref(ivar(node, "@attr"))
        d = _deref(hash_get(a, "data")) if a is not None else None
        if not isinstance(d, M.HashNode):
            return None, None
        t = M.value_of(_deref(hash_get(d, "type")))
        inner = _deref(hash_get(d, "data"))
        return t, inner

    def item_needs_payload(self, kind, item_id):
        """这件东西是不是“游戏运行时才生成内容”（孵化蛋、各类礼包…）。"""
        import xj_db
        nm = xj_db.name_map(kind).get(item_id, "")
        return xj_payload.needs_payload(nm), nm

    def baby_note_map(self):
        """`{备注里的 data 值: [召唤兽 id, ...]}`（从 Data\\Actors 的 @note 里拓）。"""
        import re
        import xj_db
        out = {}
        try:
            _r, items = xj_db.load("Actors")
        except Exception:
            return out
        for i, node in items:
            note = xj_db.s(node, "@note") or ""
            m = re.search(r"data\s*=\s*:([^\s|\r\n]+)", note)
            if m:
                out.setdefault(m.group(1), []).append(i)
        return out

    def payload_template(self, kind, item_id):
        """从存档里任意一件**有内容**的同款物品上把 `@attr` 整份抄下来。"""
        for key, _iv, _cn, _db in KINDS:
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

    def _fix_payload(self, node, kind, item_id, kid=None, force=False):
        """给物品补上 `@attr`（游戏运行时才生成的那部分）。

        优先级：现成的内容（不动）→ 存档里同款的内容（整份抄）→ 按游戏
        脚本里的规则现生成（见 `xj_payload`）。
        force=True 时不看“同款”，直接按规则重抽一份（“重抽内容”按钮用）。
        """
        cur_t, cur_d = self.item_payload(node)
        if cur_t and kid is None and not force:
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
        if not need and kid is None:
            return node
        sib = None if force else self.payload_template(kind, item_id)
        if sib is not None and kid is None:
            if not set_ivar(node, "@attr", sib):
                node.ivars.append(("@attr", sib))
            return node
        spec = xj_payload.build(nm, item_id, ctx=self.baby_note_map)
        if spec is None:
            return node
        typ, data = spec
        if kid is not None and "id" in data:
            data["id"] = int(kid)
        attr = M.HashNode([], default=None)
        # ⚠ 这里的**外层键必须是字符串 "data"**：游戏写的就是 `@attr["data"]`，
        # 读的时候是 `item.data[:data][:id]`。早期工具写成了符号键 :data，
        # 于是“内容列”读不出来、游戏用蛋时 `item.data` 为 nil 直接报
        # NoMethodError: undefined method '[]' for nil:NilClass。
        attr.pairs.append((self._str_key("data"), self._payload_node(typ, data)))
        if not set_ivar(node, "@attr", attr):
            node.ivars.append(("@attr", attr))
        return node

    @staticmethod
    def _str_key(text):
        """字符串键（不加 I/E 包装，和游戏写的一样）。"""
        return M.StrNode(text.encode("utf-8"))

    def set_payload(self, kind, slot, kid=None, force=True):
        """给某一格的东西重新生成/指定“运行时内容”（孵化蛋、要诀之类的）。

        kid：孵化类物品要孵出哪只（不给就按游戏范围随机抽一个）。
        """
        it = self._item_node(kind, slot)
        if it is None:
            raise KeyError("第 %d 格是空的" % slot)
        iid = get_int(ivar(it, "@id"), -1)
        need, nm = self.item_needs_payload(kind, iid)
        if not need:
            raise ValueError("%s 不需要运行时内容" % (nm or ("id=%d" % iid)))
        self._fix_payload(it, kind, iid, kid=kid, force=force)
        self.doc.mark_structural()
        return self.item_payload(it)

    def payload_summary(self, node):
        """一句话描述物件的运行时内容（背包列表“内容”列用），空代表没有。"""
        t, d = self.item_payload(node)
        if not t:
            return ""
        kid = M.value_of(_deref(hash_get(d, "id"))) if d is not None else None
        if t == "baby_egg":
            acts = self._name_map("Actors")
            return "蛋→%s(%s)" % (acts.get(kid, "?"), kid)
        if t == "skill_book":
            sk = self._name_map("Skills")
            return "技能书→%s(%s)" % (sk.get(kid, "?"), kid)
        if t == "formation":
            key = M.value_of(_deref(hash_get(d, "key"))) if d is not None else None
            return "阵型→%s" % (key or "?")
        if t == "guide_book":
            return "指南书→%s" % self._plain_text(d)
        if t in ("iron", "god_eye_bead", "stone"):
            return "%s→等级%s" % (t, M.value_of(_deref(hash_get(d, "lv")))
                                    if d is not None else "?")
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

    def _payload_node(self, typ, data):
        """把 `(type, data)` 转成 `{:type => ..., :data => {...}}` 节点。"""
        pairs = [(self._sym("type"), self._sym(typ)),
                 (self._sym("data"), self._plain_node(data))]
        return M.HashNode(pairs, default=None)

    def _plain_node(self, value):
        """Python 值 → Marshal 节点（只支持这几个基本类型，够用）。"""
        if isinstance(value, xj_payload.Sym):
            return self._sym(value.name)
        if isinstance(value, bool):
            return M.BoolNode(value)
        if isinstance(value, int):
            return int_node(value)
        if isinstance(value, float):
            return M.FloatNode(value)
        if isinstance(value, bytes):
            return str_node(value)
        if isinstance(value, str):
            return str_node(value)
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
        """在**同一个容器**里找一件同类的现成物件（用来克隆运行时内容）。"""
        h = self.container(kind)
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
                n = _deref(node)
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

    def set_baby(self, baby, key, value):
        for k, _label, path, typ in self.BABY_FIELDS:
            if k != key:
                continue
            node = self._resolve(baby, path)
            if node is None:
                raise KeyError("召唤兽没有 %s（%s）" % (k, path))
            if isinstance(_deref(node), M.SymbolNode):
                # 例如神兽的 @life = :infinite：整个换成数字节点
                parent, leaf = self._resolve_parent(baby, path)
                if parent is None or not set_ivar(parent, leaf, int_node(int(value))):
                    raise KeyError("改不了 %s（%s）" % (k, path))
                self.doc.mark_structural()
                return value
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
        elif what == "qual500":
            for k in ("atk", "def", "hpq", "mpq", "agi", "eva"):
                v = self.baby_value(baby, k)
                if v is not None:
                    self.set_baby(baby, k, v + 500)
            did.append("六项资质 +500")
        elif what == "grow":
            v = self.baby_value(baby, "grow")
            if v is not None:
                self.set_baby(baby, "grow", round(v + 0.1, 2))
                did.append("成长 +0.1")
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
        now, err, ids, ok = self.machine_status()
        if err:
            rows.append(("机器码（本机）", "—", "—", False,
                         "读不到：%s" % err.splitlines()[0][:70]))
        elif not ok:
            rows.append(("机器码 %s 不在存档记录里" % now, "不在", "在", True,
                         "存档记录的机器码：%s —— 游戏启动时会 include? 比对，"
                         "对不上就弹「存档异常」（换机器玩就会碰到）"
                         % ("、".join(ids) or "（空）")))
        else:
            rows.append(("机器码 %s 已在存档记录里" % now, "在", "在", False,
                         "存档记录的机器码：%s" % "、".join(ids)))
        for iid, nm, rec, act in self.security_rows():
            if rec is not None and rec != act:
                rows.append(("物品计数校验：%s (id=%d)" % (nm, iid), act, rec,
                             True,
                             "游戏记录的 %d / 背包实际 %d —— 不一致时建议点"
                             "「同步物品计数校验」（正常玩着玩着也可能不一致，"
                             "游戏自己用掉道具时不一定同步）" % (rec, act)))
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
            # 机器码：换机器玩时，把本机机器码追加进存档
            now, err, ids, ok = self.machine_status()
            if now and not ok:
                self.add_machine_id(now)
                done.append("机器码 %s 已加进存档（原来只有 %s）"
                            % (now, "、".join(ids) or "空"))
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
