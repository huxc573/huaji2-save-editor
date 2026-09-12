# -*- coding: utf-8 -*-
"""节点显示/取值的小工具（界面和数据树共用）。

这里是"把人话讲清楚"的地方：

* `unwrap()` 穿过 `@N` 链接与 `I` 包装（Ruby 1.9 的非 ASCII 字符串/符号会包一层）；
* `key_label()` 把 Hash 的键变成 `:gold` / `12` / `"文字"`，
  以前的界面在这里显示成 `[None]`（因为 SymbolNode 没有 `.value`）；
* `child_label()` 给"数组下标 / Hash 键 / ivar 名"各起一个能看懂的名字；
* `note_for()` 查 `xj_notes` 里的中文说明。
"""
import xj_marshal as M
import xj_notes


def deref(node):
    """只穿 `@N` 链接。"""
    seen = 0
    while (isinstance(node, M.LinkNode) and node.target is not None
           and seen < 8):
        node = node.target
        seen += 1
    return node


def unwrap(node):
    """穿 `@N` 链接 + `I` 包装，拿到真正的值节点。"""
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


def b2s(v):
    if isinstance(v, bytes):
        try:
            return v.decode("utf-8")
        except UnicodeDecodeError:
            return v.decode("gbk", "replace")
    return v


def value_of(node):
    """取标量值（穿链接 + 包装）。非标量返回 None。"""
    node = unwrap(node)
    if node is None:
        return None
    return M.value_of(node)


def text_of(node, limit=None):
    """取"能显示"的值：字符串/符号/数字/布尔 → 文本。"""
    node = unwrap(node)
    if node is None:
        return "nil"
    if isinstance(node, M.NilNode):
        return "nil" if node.value is None else str(node.value)
    if isinstance(node, M.BoolNode):
        return "是" if node.value else "否"
    if isinstance(node, M.SymbolNode):
        return ":" + node.name
    if isinstance(node, M.StrNode):
        s = b2s(node.data)
        return s[:limit] if limit else s
    if isinstance(node, (M.IntNode, M.BignumNode)):
        return str(node.value)
    if isinstance(node, M.FloatNode):
        return "%g" % node.value
    if isinstance(node, M.ClassNode):
        return (("module " if isinstance(node, M.ModuleNode) else "class ")
                + b2s(node.name))
    if isinstance(node, M.UserDefNode):
        return "Table(%d 字节)" % len(node.data)
    return ""


def type_label(node):
    """节点类型的中文名（树里"类型"那一列）。"""
    if isinstance(node, M.LinkNode):
        node = deref(node)
    if node is None:
        return "?"
    if isinstance(node, M.ObjNode):
        return node.cls
    return {
        "[": "数组", "{": "哈希", "}": "哈希(带默认值)",
        '"': "字符串", ":": "符号", "i": "整数", "l": "大整数",
        "f": "小数", "0": "nil", "T": "真", "F": "假",
        "u": "自定义(Table)", "U": "自定义", "S": "结构体",
        "c": "类", "m": "模块", "e": "扩展", "@": "链接", "I": "带变量",
    }.get(getattr(node, "type", "?"), getattr(node, "type", "?"))


def is_nil(node):
    return isinstance(unwrap(node), M.NilNode)


def key_label(node):
    """Hash 键 / 数组下标的显示文本。"""
    node = unwrap(node)
    if node is None:
        return "nil"
    if isinstance(node, M.SymbolNode):
        return ":" + node.name
    if isinstance(node, M.StrNode):
        return '"%s"' % b2s(node.data)
    if isinstance(node, (M.IntNode, M.BignumNode)):
        return str(node.value)
    if isinstance(node, M.NilNode):
        return "nil"
    if isinstance(node, (M.ObjNode, M.ArrayNode, M.HashNode)):
        return "<%s>" % type_label(node)
    return text_of(node) or "?"


def child_label(parent, key):
    """给子节点起个名字：数组用 ``[i]``，Hash 用键，对象用 ivar 名。"""
    p = deref(parent)
    if isinstance(p, M.HashNode):
        return key_label(key)
    if isinstance(p, M.ArrayNode):
        return "[%s]" % (key.value if hasattr(key, "value") else key)
    return str(key)


def note_for(parent, key, child=None):
    """中文说明：优先 ivar 名 / Hash 键，其次类名。"""
    p = deref(parent)
    if isinstance(p, M.HashNode):
        kv = unwrap(key)
        if isinstance(kv, M.SymbolNode):
            n = (xj_notes.note_of_section(kv.name)
                 or xj_notes.note_of_ivar(":@" + kv.name)
                 or xj_notes.note_of_config(kv.name))
            if n:
                return n
        c = unwrap(child)
        if isinstance(c, M.ObjNode):
            return xj_notes.note_of_class(c.cls)
        return ""
    if isinstance(p, M.ObjNode):
        if isinstance(key, str) and key.startswith("@"):
            return xj_notes.note_of_ivar(key)
        return ""
    c = unwrap(child) if child is not None else None
    if isinstance(c, M.ObjNode):
        return xj_notes.note_of_class(c.cls)
    return ""


def brief(node, limit=120):
    """一句话描述一个节点（右侧详情、说明列都用它）。"""
    node = deref(node)
    if node is None:
        return "（空）"
    if isinstance(node, M.LinkNode):
        return node.text()
    if isinstance(node, M.ObjNode):
        n = xj_notes.note_of_class(node.cls)
        return "<%s> %d 个 @变量%s" % (node.cls, len(node.ivars),
                                      "（%s）" % n if n else "")
    if isinstance(node, M.StructNode):
        return "<%s 结构体> %d 项" % (node.cls, len(node.ivars))
    if isinstance(node, M.ArrayNode):
        return "数组 %d 项" % len(node.items)
    if isinstance(node, M.HashNode):
        return "哈希 %d 对" % len(node.pairs)
    if isinstance(node, M.IVarNode):
        return brief(node.inner, limit)
    t = text_of(node, limit)
    return t if t != "" else ("<%s>" % type_label(node))


def children_of(node):
    """返回 [(标签, 子节点, 说明), ...]（懒加载时按需取前 N 个）。"""
    node = deref(node)
    out = []
    if isinstance(node, M.ObjNode) or isinstance(node, M.StructNode):
        for k, v in node.ivars:
            out.append((k, v, xj_notes.note_of_ivar(k)))
    elif isinstance(node, M.IVarNode):
        if node.inner is not None:
            out.append(("（值）", node.inner, brief(node.inner)))
        for k, v in node.ivars:
            out.append((k, v, xj_notes.note_of_ivar(k)))
    elif isinstance(node, M.ArrayNode):
        for i, v in enumerate(node.items):
            out.append(("[%d]" % i, v, note_for(node, i, v)))
    elif isinstance(node, M.HashNode):
        for k, v in node.pairs:
            out.append((key_label(k), v, note_for(node, k, v)))
    return out


def can_edit(node):
    """能不能就地改成标量。"""
    node = deref(node)
    return isinstance(node, (M.IntNode, M.BignumNode, M.FloatNode,
                             M.StrNode, M.SymbolNode, M.NilNode, M.BoolNode))
