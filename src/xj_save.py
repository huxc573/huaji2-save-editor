# -*- coding: utf-8 -*-
"""存档语义层（按《画迹2：缘起凡尘》自己的数据结构提供"人话"接口）。

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

import xj_edit  # noqa: E402
import xj_env  # noqa: E402
import xj_marshal as M  # noqa: E402
import xj_model  # noqa: E402

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
    h = _deref(h)
    if not isinstance(h, M.HashNode):
        return default
    for k, v in h.pairs:
        kv = M.value_of(k)
        if kv == key or (isinstance(kv, bytes) and kv == key):
            return v
    return default


def hash_put_pairs(h):
    h = _deref(h)
    return h.pairs if isinstance(h, M.HashNode) else []


class SaveDoc(object):
    """一份存档 + 常用字段的读写。底层还是 xj_model.Doc / 区间补丁。"""

    def __init__(self, path=None):
        self.path = path or xj_env.save_path()
        if not self.path:
            raise ValueError("没找到游戏目录/存档，可用环境变量 XJ_GAME 指定")
        self.doc = xj_model.Doc(self.path)
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

    def get_switch(self, i):
        arr = self._data_array("switches")
        if arr is None or i < 0 or i >= len(arr.items):
            return None
        return bool(M.value_of(_deref(arr.items[i])))

    def set_switch(self, i, value):
        arr = self._data_array("switches")
        if arr is None or i < 0 or i >= len(arr.items):
            raise IndexError("开关 %d 超出范围（共 %d 个）"
                             % (i, 0 if arr is None else len(arr.items)))
        self.doc.set_value(_deref(arr.items[i]), bool(value))
        return bool(value)

    def get_variable(self, i):
        arr = self._data_array("variables")
        if arr is None or i < 0 or i >= len(arr.items):
            return None
        return M.value_of(_deref(arr.items[i]))

    def set_variable(self, i, value):
        arr = self._data_array("variables")
        if arr is None or i < 0 or i >= len(arr.items):
            raise IndexError("变量 %d 超出范围（共 %d 个）"
                             % (i, 0 if arr is None else len(arr.items)))
        self.doc.set_value(_deref(arr.items[i]), int(value))
        return int(value)

    def counts(self):
        sw = self._data_array("switches")
        va = self._data_array("variables")
        return (len(sw.items) if sw is not None else 0,
                len(va.items) if va is not None else 0)

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

    # ------------------------------------------------------------ 保存
    def save(self, path=None, backup=True):
        return self.doc.save(path, backup=backup)

    def reload(self, path=None):
        self.doc = xj_model.Doc(path or self.path)
        self.header = self.doc.objects[0]["node"]
        self.contents = self.doc.objects[-1]["node"]
        return self


def main():
    argv = sys.argv[1:]
    if argv and argv[0] in ("-h", "--help"):
        print("用法：")
        print("  python src/xj_save.py               # 概览")
        print("  python src/xj_save.py check         # 检查防作弊校验")
        print("  python src/xj_save.py repair        # 修好校验（会写回，自动备份）")
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
