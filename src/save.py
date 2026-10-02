# -*- coding: utf-8 -*-
"""存档语义层：按《画迹2：缘起凡尘》自己的数据结构提供「人话」接口。

层级：doctree.py（文档树） → **save.py（本文）** → game.py（游戏内容）。

存档结构（实测，见 docs/存档格式.md）：

    <存档文件>
      Marshal.dump({ :temp => nil })                     ← header
      Marshal.dump({                                     ← contents
          :system, :timer, :message, :switches, :variables,
          :self_switches, :actors, :party, :troop, :map, :player })

**防作弊（重要）**：游戏把金钱这类关键数值包在 `Lock` 对象里：

    class Lock
      def initialize(v); @value = v; @master = get_encryption(@value); end
      def seed; $game_system.seeds[:shield]; end
      def get_encryption(v); v * 91 + 45 + seed / 800; end     # Ruby 整除
      def show
        if get_encryption(@value) != @master   # ← 直接改 @value 就会踩这里
          msgbox '游戏异常！'; exit
        end
        @value
      end
    end

所以本模块改 `@value` 时会**顺手把 `@master` 重算**（`repair_locks()` 可以
一次性修全档），这样改出来的存档游戏不会报"游戏异常！"。
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import patchwriter  # noqa: E402
import paths  # noqa: E402
import marshal_ruby as M  # noqa: E402
import doctree  # noqa: E402

SECTION_ORDER = ["system", "timer", "message", "switches", "variables",
                 "self_switches", "actors", "party", "troop", "map", "player"]

LOCK_CLASS = "Lock"
LOCK_MUL = 91
LOCK_ADD = 45
LOCK_DIV = 800


def _deref(node):
    """展开 '@N' 链接与 'I'（带实例变量的包装）——读值时用得着。

    Ruby 1.9 的非 ASCII 字符串会被写成 `I "字节" { :E => true }`，
    真正的内容在内层节点里。
    """
    seen = 0
    while node is not None and seen < 8:
        seen += 1
        if isinstance(node, M.LinkNode) and node.target is not None:
            node = node.target
            continue
        if isinstance(node, M.IVarNode) and node.inner is not None:
            node = node.inner
            continue
        break
    return node


def _as_str(node):
    v = M.value_of(_deref(node))
    if isinstance(v, bytes):
        try:
            return v.decode("utf-8")
        except UnicodeDecodeError:
            return v.decode("gbk", "replace")
    return v


def ivar(obj, name, default=None):
    """取对象/结构体的实例变量节点。"""
    obj = _deref(obj)
    iv = getattr(obj, "ivars", None)
    if not iv:
        return default
    for k, v in iv:
        if k == name:
            return v
    return default


def hash_get(h, key, default=None):
    """取 Hash 里的一对。

    注意：**同一个 Hash 里可能混着字符串键和符号键**！
    例如物品的 `@attr`，游戏写的是 `@attr["data"]`（**字符串**键），
    而工具早期写的是 `:data`（符号键）—— 读的时候两边都要认，
    否则就会出现“游戏写的内容工具读不出来”。
    """
    h = _deref(h)
    if not isinstance(h, M.HashNode):
        return default
    for k, v in h.pairs:
        # 键本身也可能是 I 包装（`I"data"{E=true}`），必须先解引用再取值
        kv = M.value_of(_deref(k))
        if isinstance(kv, bytes):
            kv = kv.decode("utf-8", "replace")
        if kv == key:
            return v
    return default


def hash_put_pairs(h):
    h = _deref(h)
    return h.pairs if isinstance(h, M.HashNode) else []


class SaveDoc(object):
    """一份存档 + 常用字段的读写。底层还是 doctree.Doc / 区间补丁。"""

    def __init__(self, path=None, doc=None):
        """doc 不为空则直接包住它（GUI 里必须这样用：

        否则 SaveDoc 会自己另开一份 doctree.Doc，改的是第二份内存副本，
        界面上看到"改了"，但保存时写出去的是第一份（改动全丢）。
        """
        if doc is not None:
            self.doc = doc
            self.path = doc.path
        else:
            self.path = path or paths.save_path()
            if not self.path:
                raise ValueError("没找到游戏目录/存档，可用环境变量 XJ_GAME 指定")
            self.doc = doctree.Doc(self.path)
        self.header = self.doc.objects[0]["node"]
        self.contents = self.doc.objects[-1]["node"]

    # ------------------------------------------------------------ 分区
    def sections(self):
        out = []
        for k, v in hash_put_pairs(self.contents):
            name = M.value_of(k)
            if isinstance(name, str):
                out.append((name, v))
        return out

    def section(self, name):
        for n, v in self.sections():
            if n == name:
                return v
        raise KeyError("存档里没有分区 %r" % name)

    def summary_lines(self):
        L = ["文件   : %s" % self.path,
             "明文   : %d 字节（%s）" % (len(self.doc.raw),
                                        "明文" if self.doc.plain else "已解密"),
             "分区   :"]
        for name, v in self.sections():
            v2 = _deref(v)
            if isinstance(v2, M.ObjNode):
                L.append("  %-14s %s（%d 个 @变量）" % (name, v2.cls, len(v2.ivars)))
            elif isinstance(v2, M.ArrayNode):
                L.append("  %-14s Array(%d)" % (name, len(v2.items)))
            elif isinstance(v2, M.HashNode):
                L.append("  %-14s Hash(%d)" % (name, len(v2.pairs)))
            else:
                L.append("  %-14s %s" % (name, type(v2).__name__))
        return L

    # ------------------------------------------------------------ 防作弊校验
    def shield_seed(self):
        """`$game_system.seeds[:shield]`（Lock 校验用的种子）。"""
        seeds = ivar(self.section("system"), "@seeds")
        v = hash_get(seeds, "shield")
        val = M.value_of(_deref(v)) if v is not None else None
        return int(val) if isinstance(val, int) else 0

    def lock_master(self, value, seed=None):
        """复刻 Ruby 的 `v * 91 + 45 + seed / 800`（Ruby 的 / 是整除）。"""
        seed = self.shield_seed() if seed is None else seed
        return int(value) * LOCK_MUL + LOCK_ADD + int(seed) // LOCK_DIV

    def iter_locks(self):
        """遍历整档里所有 Lock 对象（返回 [(lockNode, valueNode, masterNode)]）。"""
        found = []

        def walk(node, seen):
            node = _deref(node)
            if node is None or id(node) in seen:
                return
            seen = seen | {id(node)}
            if isinstance(node, M.ObjNode):
                if node.cls.split("::")[-1] == LOCK_CLASS:
                    v = ivar(node, "@value")
                    m = ivar(node, "@master")
                    if v is not None and m is not None:
                        found.append((node, _deref(v), _deref(m)))
                for _, child in node.ivars:
                    walk(child, seen)
            elif isinstance(node, M.StructNode):
                for _, child in node.ivars:
                    walk(child, seen)
            elif isinstance(node, M.ArrayNode):
                for child in node.items:
                    walk(child, seen)
            elif isinstance(node, M.HashNode):
                for k, v in node.pairs:
                    walk(k, seen)
                    walk(v, seen)
            elif isinstance(node, M.IVarNode):
                walk(node.inner, seen)
                for _, child in node.ivars:
                    walk(child, seen)

        for _, v in self.sections():
            walk(v, frozenset())
        return found

    def repair_locks(self, verbose=False):
        """把所有 Lock 的 @master 按当前 @value 重算。返回修了几个。"""
        n = 0
        for lock, vnode, mnode in self.iter_locks():
            val = M.value_of(vnode)
            if not isinstance(val, int):
                continue
            want = self.lock_master(val)
            if M.value_of(mnode) != want:
                self.doc.set_value(mnode, want)
                n += 1
                if verbose:
                    print("  Lock @value=%r 重算 @master %r -> %r"
                          % (val, M.value_of(mnode), want))
        return n

    def check_locks(self):
        """返回所有校验不一致的 Lock 列表（只读检查）。"""
        bad = []
        for lock, vnode, mnode in self.iter_locks():
            val = M.value_of(vnode)
            if not isinstance(val, int):
                continue
            if M.value_of(mnode) != self.lock_master(val):
                bad.append((val, M.value_of(mnode), self.lock_master(val)))
        return bad

    # ------------------------------------------------------------ 金钱
    def gold_node(self):
        """返回 (Lock节点, @value节点) —— 金钱是 Lock 包装的。"""
        g = ivar(self.section("party"), "@gold")
        g2 = _deref(g)
        if g2 is None:
            return None, None
        if isinstance(g2, M.ObjNode) and g2.cls.split("::")[-1] == LOCK_CLASS:
            return g2, _deref(ivar(g2, "@value"))
        return None, g2

    def gold(self):
        _, v = self.gold_node()
        return M.value_of(v) if v is not None else None

    def set_gold(self, value):
        lock, v = self.gold_node()
        if v is None:
            raise ValueError("存档里没有 @gold")
        self.doc.set_value(v, int(value))
        # 关键：连同 @master 一起改，否则游戏读金钱时会报"游戏异常！"
        if lock is not None:
            m = _deref(ivar(lock, "@master"))
            if m is not None:
                self.doc.set_value(m, self.lock_master(int(value)))
        return int(value)

    # ------------------------------------------------------------ 开关 / 变量
    def _data_array(self, section):
        return _deref(ivar(self.section(section), "@data"))

    # ------------------------------------------------------------ 开关 / 变量
    #
    # ⚠ **两个游戏版本结构不同**，这里统一兼容（2026-10-02 实测）：
    #   尝鲜版 v0.x：`variables` 是 **ArrayNode**（下标 = 变量编号）
    #   内测版 V2.201：`variables` 是 **HashNode**（键 = 变量编号 → 值）
    #     实测该档`hash_put_pairs` 只有 3 对：{2=>11, 1=>1, 7=>1}，
    #     而 Array 版本同样的位置是 30 个变量 ⇒ **不能按位置当编号用**。
    #   `switches` 两版都是 ArrayNode，但 V2.201 里未用到的位是 `nil`（不是 false），
    #   所以取值一律走 `_switch_value()` 归一。
    #
    # `_switch_len` / `_var_len` / `_var_pairs` 三个辅助把差异收在一处，
    # 上面的 get/set 只管按编号读写。
    def _switch_arr(self):
        return self._data_array("switches")

    def _switch_len(self):
        a = self._switch_arr()
        if a is None or not hasattr(a, "items"):
            return 0
        return len(a.items)

    def _switch_value(self, i):
        """第 i 个开关的值；空位（nil）算False。"""
        a = self._switch_arr()
        if a is None or not hasattr(a, "items") or i < 0 or i >= len(a.items):
            return None
        v = M.value_of(_deref(a.items[i]))
        return bool(v) if v is not None else False

    def _var_is_hash(self):
        a = self._data_array("variables")
        return isinstance(a, M.HashNode) or hasattr(a, "pairs")

    def _var_pairs(self):
        """`[(编号, 值节点), ...]`，两种结构都归一成这个。"""
        a = self._data_array("variables")
        if a is None:
            return []
        if self._var_is_hash():
            out = []
            for k, v in hash_put_pairs(a):
                kid = M.value_of(_deref(k))
                if isinstance(kid, int):
                    out.append((kid, v))
            return out
        return list(enumerate(a.items))

    def _var_len(self):
        """「变量总数」。

        ⚠ Hash 版（V2.201）是**稀疏**的：实测只有 `{2=>11, 1=>1, 7=>1}` 三个键，
        编号 0/3/4/5/6 **根本不存在**。所以
          * 报`max(键)+1`（=8）是**误导** —— 让人以为能写 0；
          * 报「键的个数」（=3）同样不对 —— 键 7 明明在。
        这里只用于**错误提示**，所以给「实际存在的编号数」并在提示里说清是稀疏的；
        真正的能不能写，由 `_var_node()` 说了算（不存在就抛 IndexError）。
        """
        a = self._data_array("variables")
        if a is None:
            return 0
        if self._var_is_hash():
            return len(self._var_pairs())
        return len(a.items) if hasattr(a, "items") else 0

    def _var_hint(self):
        """错误提示用：这个版本 variables 的实际编号长什么样。"""
        a = self._data_array("variables")
        if a is not None and self._var_is_hash():
            ids = sorted(i for i, _ in self._var_pairs())
            return "（本版本 variables 是稀疏哈希，只有编号 %s 存在）" % (
                "、".join(str(i) for i in ids) if ids else "无")
        return ""

    def _var_node(self, i):
        """第 i 个变量的**值节点**（可直接给 set_value）；没有返回 None。"""
        a = self._data_array("variables")
        if a is None:
            return None
        if self._var_is_hash():
            for kid, v in self._var_pairs():
                if kid == i:
                    return _deref(v)
            return None
        if i < 0 or not hasattr(a, "items") or i >= len(a.items):
            return None
        return _deref(a.items[i])

    def get_switch(self, i):
        return self._switch_value(i)

    def set_switch(self, i, value):
        a = self._switch_arr()
        if a is None or not hasattr(a, "items") or i < 0 or i >= len(a.items):
            raise IndexError("开关 %d 超出范围（共 %d 个）"
                             % (i, self._switch_len()))
        self.doc.set_value(_deref(a.items[i]), bool(value))
        return bool(value)

    def get_variable(self, i):
        n = self._var_node(i)
        return None if n is None else M.value_of(n)

    def set_variable(self, i, value):
        n = self._var_node(i)
        if n is None:
            raise IndexError("变量 %d 不存在%s"
                             % (i, self._var_hint()))
        self.doc.set_value(n, int(value))
        return int(value)

    def counts(self):
        # ⚠ 不能直接摸 `arr.items`：V2.201 的 variables 是 HashNode（没有 .items）
        return (self._switch_len(), self._var_len())

    # ------------------------------------------------------------ 角色
    def actors(self):
        """返回 [(actor_id, Game_Actor 节点), ...]（只列存在的）。"""
        arr = self._data_array("actors")
        out = []
        if arr is None:
            return out
        for i, a in enumerate(arr.items):
            a2 = _deref(a)
            if isinstance(a2, M.ObjNode):
                out.append((i, a2))
        return out

    def actor_name(self, actor):
        v = M.value_of(_deref(ivar(actor, "@name")))
        if isinstance(v, bytes):
            v = v.decode("utf-8", "replace")
        return v


    def actor_field(self, actor, name):
        v = _deref(ivar(actor, name))
        val = M.value_of(v) if v is not None else None
        if isinstance(val, bytes):
            val = val.decode("utf-8", "replace")
        return val

    def set_actor_field(self, actor, name, value):
        v = _deref(ivar(actor, name))
        if v is None:
            raise KeyError("角色没有 @%s" % name)
        if isinstance(M.value_of(v), int) and not isinstance(value, bool):
            value = int(value)
        self.doc.set_value(v, value)
        return value

    def actor_summary(self, actor):
        """一句话描述角色（名字 / 等级 / 经验 / HP / MP）。"""
        return ("%s  Lv=%s  EXP=%s  HP=%s  MP=%s" % (
            self.actor_name(actor),
            self.actor_field(actor, "@level"),
            self.actor_field(actor, "@exp"),
            self.actor_field(actor, "@hp"),
            self.actor_field(actor, "@mp")))

    # ------------------------------------------------------------ 队伍
    def party_member_ids(self):
        arr = _deref(ivar(self.section("party"), "@actors"))
        if arr is None or not isinstance(arr, M.ArrayNode):
            return []
        return [M.value_of(_deref(x)) for x in arr.items]

    def items(self):
        """返回 [(item_id, [数量, ...]), ...]。"""
        h = ivar(self.section("party"), "@items")
        out = []
        for k, v in hash_put_pairs(h):
            kid = M.value_of(k)
            v2 = _deref(v)
            if isinstance(v2, M.ArrayNode):
                out.append((kid, [M.value_of(_deref(x)) for x in v2.items]))
            else:
                out.append((kid, M.value_of(v2)))
        return out

    # ------------------------------------------------------------ 角色属性（中文）
    # 游戏把五维/潜能等放在 Game_Actor.@attr（类 Game_Actor_Attr），字段名是中文。
    ATTR_FIELDS = ["@体质", "@法力", "@力量", "@耐力", "@敏捷", "@潜能",
                   "@人气", "@贡献", "@体力", "@活力"]

    def attr_obj(self, actor):
        """角色对应的 Game_Actor_Attr 节点（没有就返回 None）。"""
        a = _deref(ivar(actor, "@attr"))
        if isinstance(a, M.ObjNode):
            return a
        return None

    def attr_items(self, actor):
        """返回 [(字段名, 当前值), ...]，只列存档里真实存在的。"""
        out = []
        obj = self.attr_obj(actor)
        if obj is None:
            return out
        names = [k for k, _ in obj.ivars]
        for want in self.ATTR_FIELDS:
            if want in names:
                out.append((want, M.value_of(_deref(ivar(obj, want)))))
        for k, v in obj.ivars:                 # 再补上不认识的
            if k not in self.ATTR_FIELDS and k not in ("@master", "@name"):
                out.append((k, M.value_of(_deref(v))))
        return out

    def set_attr(self, actor, name, value):
        obj = self.attr_obj(actor)
        if obj is None:
            raise KeyError("这个角色没有 @attr")
        node = _deref(ivar(obj, name))
        if node is None:
            raise KeyError("属性 %s 不存在" % name)
        # @活力 这类字段游戏存的是 Float（如 200.0）—— 节点原本是什么类型
        # 就写回什么类型，别把浮点写成整型节点。
        value = float(value) if isinstance(node, M.FloatNode) else int(value)
        self.doc.set_value(node, value)
        return value

    def skills(self, actor):
        """已学技能 id 列表。"""
        arr = _deref(ivar(actor, "@skills"))
        if not isinstance(arr, M.ArrayNode):
            return []
        return [M.value_of(_deref(x)) for x in arr.items]

    def skill_names(self, actor):
        """已学技能 [(id, 名称), ...]（名称来自 Data\\Skills.rvdata2）。"""
        import datatables
        try:
            nm = datatables.name_map("Skills")
        except Exception:
            nm = {}
        return [(i, nm.get(i, "?")) for i in self.skills(actor)]

    def equips(self, actor):
        """装备 [[槽位, 类别, id], ...]，类别 0=武器 1=防具。"""
        arr = _deref(ivar(actor, "@equips"))
        out = []
        if isinstance(arr, M.ArrayNode):
            for i, e in enumerate(arr.items):
                e2 = _deref(e)
                if isinstance(e2, M.ObjNode):
                    out.append((i, M.value_of(_deref(ivar(e2, "@class"))),
                                M.value_of(_deref(ivar(e2, "@item_id")))))
        return out

    # ------------------------------------------------------------ 队伍杂项
    def steps(self):
        return M.value_of(_deref(ivar(self.section("party"), "@steps")))

    def set_steps(self, value):
        node = _deref(ivar(self.section("party"), "@steps"))
        if node is None:
            raise KeyError("存档里没有 @steps")
        self.doc.set_value(node, int(value))
        return int(value)

    def sys_get(self, name):
        return M.value_of(_deref(ivar(self.section("system"), name)))

    def sys_set(self, name, value):
        node = _deref(ivar(self.section("system"), name))
        if node is None:
            raise KeyError("存档 :system 里没有 %s" % name)
        self.doc.set_value(node, int(value))
        return int(value)

    def item_rows(self):
        """队伍物品 [(id, 名称, 数量), ...]（名称来自 Data\\Items.rvdata2）。"""
        import datatables
        try:
            nm = datatables.name_map("Items")
        except Exception:
            nm = {}
        out = []
        for kid, counts in self.items():
            n = counts[0] if isinstance(counts, list) and counts else counts
            out.append((kid, nm.get(kid, "?"), n))
        return out

    # ------------------------------------------------------------ 保存
    def save(self, path=None, backup=True):
        return self.doc.save(path, backup=backup)

    def reload(self, path=None):
        self.doc = doctree.Doc(path or self.path)
        self.path = self.doc.path
        self.header = self.doc.objects[0]["node"]
        self.contents = self.doc.objects[-1]["node"]
        return self


def main():
    argv = sys.argv[1:]
    if argv and argv[0] in ("-h", "--help"):
        print("用法：")
        print("  python src/save.py               # 概览")
        print("  python src/save.py check         # 检查防作弊校验")
        print("  python src/save.py repair        # 修好校验（会写回，自动备份）")
        return
    s = SaveDoc()
    print("\n".join(s.summary_lines()))
    print("\n金钱 = %s（Lock 校验 %s）"
          % (s.gold(), "正常" if not s.check_locks() else "不一致：%r" % s.check_locks()))
    print("开关/变量 = %d / %d" % s.counts())
    print("角色：")
    for i, a in s.actors():
        print("  #%-3d %s" % (i, s.actor_summary(a)))
    print("队伍成员 id = %s" % s.party_member_ids())
    if argv and argv[0] == "repair":
        n = s.repair_locks(verbose=True)
        if n:
            s.save()
            print("已修好 %d 处并写回 %s" % (n, s.path))
        else:
            print("无需修改")


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")
    main()
