# -*- coding: utf-8 -*-
"""区间补丁写入引擎（只改"动过的字段"的字节区间，其余原样保留）。

为什么不用"整棵树重新序列化"：
Ruby Marshal 有对象链接（`@N`）——同一个对象第二次出现只写一个编号。
只要某个对象内部成员数量变了，后面所有编号都会错位，存档就悄悄坏掉
（游戏里表现为 TypeError: cannot convert Array into String 之类）。
所以：

* 改**标量**（整数 / 布尔 / 字符串…）→ 只重编码那一个字段的 [start, end)；
* 改**数组元素 / 对象成员**（长度变化）→ 必须走 `replace_tree`，
  整块重写并且把链接全部展开成独立副本（自包含）。

这个文件是 huaji1 版本的精简版，v0.1 只实现标量补丁与自包含重写两个入口。
"""
import xj_marshal as M


class PatchError(Exception):
    pass


class PatchEngine(object):
    """收集补丁，最后一次性拼接成新缓冲区。

    同一个节点被改两次时，以最后一次为准（用 id(node) 去重），
    并且**始终用第一次记录的原始区间**——所以千万不要在节点上改 start/end。
    """

    def __init__(self, buf):
        self.buf = bytes(buf)
        self._orig = {}                # id(node) -> (start, end)
        self._patches = {}             # id(node) -> (start, end, bytes)
        self._raw = []                 # [(start, end, bytes)]

    @property
    def patches(self):
        out = list(self._patches.values()) + self._raw
        return sorted(out, key=lambda p: p[0])

    # ---------------------------------------------------------------- 标量
    def set_scalar(self, node, value):
        """把一个标量节点换成新值（就地替换它的字节区间）。"""
        new = encode_scalar(node, value)
        key = id(node)
        if key not in self._orig:
            self._orig[key] = (node.start, node.end)
        start, end = self._orig[key]
        self._patches[key] = (start, end, new)
        assign_value(node, value)
        return new

    # ------------------------------------------------------------ 整块替换
    def replace_range(self, start, end, newbytes):
        self._raw.append((start, end, bytes(newbytes)))

    # ---------------------------------------------------------------- 应用
    def apply(self):
        ps = self.patches
        if not ps:
            return self.buf
        out = []
        pos = 0
        for start, end, data in ps:
            if start < pos:
                raise PatchError("补丁区间重叠 @%d" % start)
            out.append(self.buf[pos:start])
            out.append(data)
            pos = end
        out.append(self.buf[pos:])
        return b"".join(out)


# --------------------------------------------------------------------------
# 标量编码
# --------------------------------------------------------------------------
def assign_value(node, value):
    """把新值写回节点的"内存表示"。

    ⚠ 不是所有节点都叫 `.value`：字符串是 `.data`、符号是 `.name`/`.raw`、
    浮点还要同步 `.raw`（序列化时直接用 raw）。以前一律写 `node.value`，
    碰到改名字（StrNode）就报 `'StrNode' object has no attribute 'value'`。
    """
    if isinstance(node, M.StrNode):
        node.data = value.encode('utf-8') if isinstance(value, str) else bytes(value)
        return
    if isinstance(node, M.SymbolNode):
        raw = value.encode('utf-8') if isinstance(value, str) else bytes(value)
        node.raw = raw
        try:
            node.name = raw.decode('utf-8')
        except UnicodeDecodeError:
            node.name = raw.decode('latin-1')
        return
    if isinstance(node, M.FloatNode):
        node.value = float(value)
        node.raw = repr(float(value)).encode('ascii')
        return
    node.value = value


def encode_scalar(node, value):
    """按节点的类型把 value 编码成 Marshal 字节。"""
    t = node.type
    if t == 'i':
        return M.encode_integer(value)
    if t == 'l':
        return M.encode_bignum(value)
    if t == '"':
        if isinstance(value, str):
            value = value.encode('utf-8')
        return M.encode_string(value)
    if t == ':':
        return M.w_symbol_bytes(value)
    if t == 'f':
        # Ruby 的浮点是 `f` + w_long(长度) + ASCII 文本
        txt = repr(float(value)).encode('ascii')
        return b'f' + M.encode_long(len(txt)) + txt
    if t == '0':                       # nil 节点改写成别的标量
        if value is None:
            return b'0'
        if isinstance(value, bool):
            return b'T' if value else b'F'
        if isinstance(value, int):
            return M.encode_integer(value)
        if isinstance(value, str):
            return M.encode_string(value)
        raise PatchError("nil 节点不支持写入 %r" % (value,))
    # BoolNode 的 type 是 '?'（见 xj_marshal.BoolNode），按值判断
    if t == '?' and isinstance(getattr(node, 'value', None), bool):
        return b'T' if value else b'F'
    raise PatchError("不支持修改类型 %r 的标量" % t)


def value_of(node):
    """取节点的"值"（标量）或 None。"""
    if isinstance(node, M.LinkNode):
        return value_of(node.target) if node.target is not None else None
    return getattr(node, 'value', None)


# --------------------------------------------------------------------------
# 自包含序列化（链接全部展开）
# --------------------------------------------------------------------------
def serialize_tree(node):
    """把一棵树序列化成**不含任何 `@N` 链接**的字节（体积略增，编号永远自洽）。"""
    return M.serialize(node)
