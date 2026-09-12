# -*- coding: utf-8 -*-
"""探查 召唤兽(Game_Baby) / 角色属性 / 物品槽 / 开关变量名。

用法：python tools/probe_v04_baby.py [--out 文件]
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.stdout.reconfigure(errors="replace")

import xj_db  # noqa: E402
import xj_env  # noqa: E402
import xj_marshal as M  # noqa: E402
import xj_model  # noqa: E402

out = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def deref(n):
    while isinstance(n, M.LinkNode) and n.target is not None:
        n = n.target
    return n


def b2s(v):
    if isinstance(v, bytes):
        try:
            return v.decode("utf-8")
        except UnicodeDecodeError:
            return v.decode("gbk", "replace")
    return v


def key_str(k):
    """键的字符串形式：符号给名字（不带冒号），其它给值。"""
    kk = deref(k)
    if isinstance(kk, M.SymbolNode):
        return kk.name
    v = getattr(kk, "name", None)
    if v is None:
        v = b2s(getattr(kk, "value", None))
    if v is None:
        return "<%s>" % type(kk).__name__
    return str(v)


def short(node, n=60):
    node = deref(node)
    if node is None:
        return "None"
    if isinstance(node, M.ObjNode):
        return "<%s> %d ivars" % (node.cls, len(node.ivars))
    if isinstance(node, M.ArrayNode):
        return "Array(%d)" % len(node.items)
    if isinstance(node, M.HashNode):
        return "Hash(%d)" % len(node.pairs)
    if isinstance(node, M.StrNode):
        return repr(b2s(node.data)[:n])
    if isinstance(node, M.SymbolNode):
        return ":" + node.name
    return repr(b2s(getattr(node, "value", node.type)))


def ivar(node, name):
    node = deref(node)
    if not isinstance(node, M.ObjNode):
        return None
    for k, v in node.ivars:
        if b2s(k) == name:
            return v
    return None


def dump_ivars(node, indent="    ", skip=()):
    node = deref(node)
    if not isinstance(node, M.ObjNode):
        out.write("%s%s\n" % (indent, short(node)))
        return
    out.write("%s<%s>  %d ivars\n" % (indent, node.cls, len(node.ivars)))
    for k, v in node.ivars:
        ks = b2s(k) if k else "?"
        if ks in skip:
            continue
        out.write("%s  %-24s %s\n" % (indent, ks, short(v)))


def main():
    global out
    if "--out" in sys.argv:
        out = open(sys.argv[sys.argv.index("--out") + 1], "w", encoding="utf-8")
    doc = xj_model.Doc(xj_env.save_path())
    contents = deref(doc.objects[-1]["node"])
    secs = {key_str(k): v for k, v in contents.pairs}

    # ---------------- 开关 / 变量
    for name in ("switches", "variables"):
        node = deref(secs[name])
        data = deref(ivar(node, "@data"))
        out.write("### :%s → <Game_%s> @data %s\n"
                  % (name, name.capitalize(), short(data)))
        if isinstance(data, (M.ArrayNode, M.HashNode)):
            for k, v in (data.pairs if isinstance(data, M.HashNode)
                         else list(enumerate(data.items))):
                out.write("    %-6s = %s\n" % (key_str(k) if not isinstance(k, int)
                                               else k, short(v)))

    # ---------------- Data\\System.rvdata2 里的名字
    try:
        h, rows = xj_db.rows("System")
        out.write("\n### Data\\System.rvdata2 转表\n%s\n" % h)
    except Exception as e:
        out.write("\n（System 表不可转：%s）\n" % e)
    try:
        root, items = xj_db.load("System")
        for k, n in items:
            sw = deref(xj_db.ivar(n, "@switches"))
            va = deref(xj_db.ivar(n, "@variables"))
            out.write("System.@switches %s / @variables %s\n"
                      % (short(sw), short(va)))
            for nm, arr in (("switches", sw), ("variables", va)):
                if isinstance(arr, M.ArrayNode):
                    for i, v in enumerate(arr.items):
                        s = xj_db.s(v if not isinstance(v, M.ArrayNode) else v)
                        out.write("   %s[%d] = %r\n" % (nm, i, s))
    except Exception as e:
        out.write("（System 解析失败：%s）\n" % e)

    # ---------------- 物品槽
    party = deref(secs["party"])
    for ivname in ("@items", "@weapons", "@armors"):
        h = deref(ivar(party, ivname))
        out.write("\n### party.%s %s\n" % (ivname, short(h)))
        if isinstance(h, M.HashNode):
            for k, v in h.pairs:
                vv = deref(v)
                slot = key_str(k)
                if isinstance(vv, M.ArrayNode) and len(vv.items) >= 2:
                    it = deref(vv.items[0])
                    out.write("    槽 %-4s id=%-6s count=%-4s %s\n"
                              % (slot, short(ivar(it, "@id"), 12),
                                 short(vv.items[1], 12), short(it, 40)))
                else:
                    out.write("    槽 %-4s %s\n" % (slot, short(vv)))

    # ---------------- 角色 / 召唤兽
    actors = deref(secs["actors"])
    data = deref(ivar(actors, "@data"))
    for i, a in enumerate(data.items):
        aa = deref(a)
        if not isinstance(aa, M.ObjNode):
            continue
        out.write("\n" + "=" * 78 + "\n### actors.@data[%d]  <Game_Actor>\n" % i)
        out.write("    @name=%s @level=%s @class_id=%s @exp=%s @limit_exp=%s\n"
                  % (short(ivar(aa, "@name")), short(ivar(aa, "@level")),
                     short(ivar(aa, "@class_id")), short(ivar(aa, "@exp")),
                     short(ivar(aa, "@limit_exp"))))
        out.write("    --- @exp 内容\n")
        e = deref(ivar(aa, "@exp"))
        if isinstance(e, M.HashNode):
            for k, v in e.pairs:
                out.write("        class %s -> %s\n" % (key_str(k), short(v)))
        out.write("    --- @attr (Game_Actor_Attr)\n")
        dump_ivars(ivar(aa, "@attr"), "        ")
        out.write("    --- @sect_data\n")
        sd = deref(ivar(aa, "@sect_data"))
        if isinstance(sd, M.HashNode):
            for k, v in sd.pairs:
                out.write("        %-14s %s\n" % (key_str(k), short(v, 120)))
                vv = deref(v)
                if isinstance(vv, M.HashNode):
                    for k2, v2 in vv.pairs:
                        out.write("            %-12s %s\n" % (key_str(k2),
                                                              short(v2, 60)))
        out.write("    --- @babys %s\n" % short(ivar(aa, "@babys")))
        babys = deref(ivar(aa, "@babys"))
        if isinstance(babys, M.ArrayNode):
            for j, b in enumerate(babys.items):
                out.write("      [%d] " % j)
                dump_ivars(b, "          ")
        out.write("    --- @baby（当前出战的那只）\n")
        dump_ivars(ivar(aa, "@baby"), "        ")
    out.write("\n（end）\n")
    out.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
