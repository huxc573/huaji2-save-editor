# -*- coding: utf-8 -*-
"""体检：解析已解密的 Data 数据库文件，看类名是怎么编码的、能否完整解析、能否字节级还原。

用法：python tools/check_db_parse.py [明文文件]
输出：tools/_dbparse.txt
"""
import os
import sys

sys.stdout.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
import xj_marshal as M  # noqa: E402

LOG = os.path.join(HERE, "_dbparse.txt")
path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    HERE, "_dec", "Data_System.rvdata2.bin")
data = open(path, "rb").read()
L = ["文件 = %s (%d 字节)" % (path, len(data))]

cls_names = {}


def walk(n):
    if n is None:
        return
    if isinstance(n, (M.ObjNode, M.StructNode)):
        cls_names[n.cls] = cls_names.get(n.cls, 0) + 1
        for _, v in n.ivars:
            walk(v)
    elif isinstance(n, (M.ClassNode, M.ModuleNode)):
        cls_names["<class>" + n.name.decode("utf-8", "replace")] = \
            cls_names.get("<class>" + n.name.decode("utf-8", "replace"), 0) + 1
    elif isinstance(n, M.ArrayNode):
        for x in n.items:
            walk(x)
    elif isinstance(n, M.HashNode):
        for k, v in n.pairs:
            walk(k)
            walk(v)
        walk(n.default)
    elif isinstance(n, M.IVarNode):
        walk(n.inner)
        for _, v in n.ivars:
            walk(v)
    elif isinstance(n, (M.UserDefNode, M.UserMarshalNode)):
        walk(getattr(n, "inner", None))


try:
    streams = M.parse_stream(data)
    L.append("顶层对象数 = %d" % len(streams))
    for i, st in enumerate(streams):
        L.append("  #%d 头=%s 节点=%s 范围=%s" % (
            i, st["head"], type(st["node"]).__name__,
            (st["node"].start, st["node"].end)))
        walk(st["node"])
    L.append("涉及类名：")
    for k, v in sorted(cls_names.items(), key=lambda x: -x[1])[:40]:
        L.append("   %-40s x%d" % (k, v))
except Exception as e:
    L.append("解析失败: %s" % e)

# 字节级还原检查
try:
    out = bytearray()
    for st in M.parse_stream(data):
        out += b"\x04\x08" if st["head"] is not None else b""
        out += M.serialize(st["node"], 0, {}, 0)
    L.append("重写后长度 %d（原 %d）  完全一致=%s" %
             (len(out), len(data), bytes(out) == data))
    if bytes(out) != data:
        n = min(len(out), len(data))
        for i in range(n):
            if out[i] != data[i]:
                L.append("首个不同偏移 = %d" % i)
                L.append("  原文: %s" % data[max(0, i - 16):i + 16].hex(" "))
                L.append("  重写: %s" % bytes(out[max(0, i - 16):i + 16]).hex(" "))
                break
except Exception as e:
    L.append("重写失败: %s" % e)

open(LOG, "w", encoding="utf-8").write("\n".join(L) + "\n")
print("\n".join(L[:6]))
