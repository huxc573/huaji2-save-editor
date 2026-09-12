# -*- coding: utf-8 -*-
"""把 Data\\*.rvdata2 各个数据库的"结构"打出来（类名 / 字段名 / 一条样本）。

用途：设计 CSV 列顺序时先看清每个 DB 有哪些字段。
用法：python tools/db_schema.py [depth]
输出：tools/_schema.txt
"""
import os
import sys

sys.stdout.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))

import xj_codec  # noqa: E402
import xj_env  # noqa: E402
import xj_marshal as M  # noqa: E402

LOG = os.path.join(HERE, "_schema.txt")
DEPTH = int(sys.argv[1]) if len(sys.argv) > 1 else 2

GAME = xj_env.find_game_dir()
PLAIN = os.path.join(HERE, "_plain")

DBS = ["Items", "Weapons", "Armors", "Skills", "States", "Actors",
       "Classes", "Enemies", "Troops", "CommonEvents", "Tilesets",
       "Animations", "System"]


def deref(n):
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


def val(n):
    n = deref(n)
    if n is None:
        return None
    v = M.value_of(n)
    if isinstance(v, bytes):
        try:
            return v.decode("utf-8")
        except UnicodeDecodeError:
            return v.decode("gbk", "replace")
    return v


def shape(n, depth):
    """把一个值说成短字符串。"""
    n = deref(n)
    if n is None:
        return "nil"
    if isinstance(n, M.ObjNode):
        if depth <= 0:
            return "Obj:%s" % n.cls
        inner = ", ".join("%s=%s" % (k, shape(v, depth - 1)) for k, v in n.ivars[:6])
        return "%s{%s}" % (n.cls, inner)
    if isinstance(n, M.ArrayNode):
        if depth <= 0:
            return "Array(%d)" % len(n.items)
        return "[%s]" % ", ".join(shape(x, depth - 1) for x in n.items[:6])
    if isinstance(n, M.HashNode):
        if depth <= 0:
            return "Hash(%d)" % len(n.pairs)
        return "{%s}" % ", ".join("%s=>%s" % (val(k), shape(v, depth - 1))
                                  for k, v in n.pairs[:6])
    if isinstance(n, (M.ClassNode, M.ModuleNode)):
        return "Class:%s" % n.name.decode("utf-8", "replace")
    if isinstance(n, M.UserDefNode):
        return "UserDef:%s(%d)" % (n.cls, len(n.data))
    return repr(val(n))


L = []
for name in DBS:
    # 明文优先用 tools/_plain 里已经解好的，没有就现解
    plain = os.path.join(PLAIN, ("Data_%s.rvdata2.bin" % name))
    src = os.path.join(GAME, "Data", ("%s.rvdata2" % name))
    if not os.path.exists(plain) or os.path.getsize(plain) == 0:
        if not os.path.exists(src):
            continue
        plain = os.path.join(PLAIN, ("Data_%s.rvdata2.bin" % name))
        try:
            xj_codec.decrypt_file(src, plain)
        except Exception as e:
            L.append("== %s == 解密失败 %s" % (name, e))
            continue
    try:
        objs = M.parse_stream(open(plain, "rb").read())
    except Exception as e:
        L.append("== %s == 解析失败 %s" % (name, e))
        continue
    root = objs[-1]["node"]
    L.append("=" * 70)
    L.append("== %s ==  文件=%s  顶层=%s  项数=%d"
             % (name, os.path.basename(plain), type(root).__name__,
                len(root.items) if isinstance(root, M.ArrayNode) else 0))
    if not isinstance(root, M.ArrayNode):
        L.append("   （不是数组，跳过）")
        continue
    for i, it in enumerate(root.items):
        n = deref(it)
        if n is None or isinstance(n, M.NilNode):
            continue
        if True:
            if isinstance(n, M.ObjNode):
                L.append("  [id=%d] %s" % (i, n.cls))
                for k, v in n.ivars:
                    L.append("      %-22s %s" % (k, shape(v, DEPTH)))
                L.append("    --- 样本展开 ---")
                L.append("      " + shape(n, DEPTH + 1))
            else:
                L.append("  [id=%d] %s" % (i, shape(n, DEPTH)))
            break

open(LOG, "w", encoding="utf-8").write("\n".join(L) + "\n")
print("已写出 %s（%d 行）" % (LOG, len(L)))
