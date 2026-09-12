# -*- coding: utf-8 -*-
"""总体验证：解密后的所有游戏文件都能被解析器完整解析、并且"重写→再解析"结果一致。

用法：python tools/verify_all.py
输出：tools/_verify_all.txt
"""
import os
import sys

sys.stdout.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
import xj_marshal as M  # noqa: E402

LOG = os.path.join(HERE, "_verify_all.txt")
PLAIN = os.path.join(HERE, "_plain")

FILES = [
    "Data_System.rvdata2.bin", "Data_Actors.rvdata2.bin",
    "Data_Classes.rvdata2.bin", "Data_Skills.rvdata2.bin",
    "Data_Items.rvdata2.bin", "Data_Weapons.rvdata2.bin",
    "Data_Armors.rvdata2.bin", "Data_Enemies.rvdata2.bin",
    "Data_Troops.rvdata2.bin", "Data_States.rvdata2.bin",
    "Data_Animations.rvdata2.bin", "Data_Tilesets.rvdata2.bin",
    "Data_CommonEvents.rvdata2.bin", "Data_Map001.rvdata2.bin",
    "Data_Scripts.rvdata2.bin",
    "save.rvdata2.bin", "AutoSave_save00.rvdata2.bin",
]


def count(n, acc):
    if n is None:
        return
    acc[type(n).__name__] = acc.get(type(n).__name__, 0) + 1
    if isinstance(n, (M.ObjNode, M.StructNode)):
        for _, v in n.ivars:
            count(v, acc)
    elif isinstance(n, M.ArrayNode):
        for x in n.items:
            count(x, acc)
    elif isinstance(n, M.HashNode):
        for k, v in n.pairs:
            count(k, acc)
            count(v, acc)
        count(n.default, acc)
    elif isinstance(n, M.IVarNode):
        count(n.inner, acc)
        for _, v in n.ivars:
            count(v, acc)
    elif isinstance(n, M.UserMarshalNode):
        count(n.inner, acc)


L = []
ok_all = True
for fn in FILES:
    p = os.path.join(PLAIN, fn)
    if not os.path.exists(p) or os.path.getsize(p) == 0:
        L.append("%-32s （没有明文，跳过）" % fn)
        continue
    data = open(p, "rb").read()
    line = "%-32s %8d 字节  " % (fn, len(data))
    try:
        streams = M.parse_stream(data)
        acc = {}
        for st in streams:
            count(st["node"], acc)
        kinds = ", ".join("%s=%d" % kv for kv in sorted(acc.items())
                          if kv[0] in ("ObjNode", "HashNode", "ArrayNode",
                                       "StrNode", "UserDefNode", "ClassNode",
                                       "IVarNode", "FloatNode", "LinkNode"))
        line += "[OK] 对象=%d  %s" % (len(streams), kinds)
        # 重写 → 再解析 → 再重写，看两次重写是否一致（自洽性）
        out1 = bytearray()
        for st in streams:
            out1 += b"\x04\x08" if st["head"] is not None else b""
            out1 += M.serialize(st["node"], 0, {}, 0)
        s2 = M.parse_stream(bytes(out1))
        out2 = bytearray()
        for st in s2:
            out2 += b"\x04\x08" if st["head"] is not None else b""
            out2 += M.serialize(st["node"], 0, {}, 0)
        line += "  重写自洽=%s" % (bytes(out1) == bytes(out2))
    except Exception as e:
        ok_all = False
        line += "[NG] %s" % e
    L.append(line)

L.append("")
L.append("全部通过 = %s" % ok_all)
open(LOG, "w", encoding="utf-8").write("\n".join(L) + "\n")
print("\n".join(L))
