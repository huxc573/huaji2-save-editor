# -*- coding: utf-8 -*-
"""看 :system.@security 里的 Change 对象：能不能凑齐 0-9 的密文字典。

`Change` 把数字**逐位** AES-ECB 加密后存进 `@value`（字符串数组），
所以只要从已有对象里把 `E('0')..E('9')` 的对应关系捞出来，
以后写新的总数就能直接查表（不用知道 AES 密钥）。

用法：python tools/probe_security.py [--out 文件]
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.stdout.reconfigure(errors="replace")

import xj_env  # noqa: E402
import xj_marshal as M  # noqa: E402
import xj_model  # noqa: E402

out = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def deref(n):
    while isinstance(n, M.LinkNode) and n.target is not None:
        n = n.target
    return n


def unwrap(node):
    node = deref(node)
    seen = 0
    while isinstance(node, M.IVarNode) and node.inner is not None and seen < 8:
        node = deref(node.inner)
        seen += 1
    return node


def b2s(v):
    if isinstance(v, bytes):
        try:
            return v.decode("utf-8")
        except UnicodeDecodeError:
            return v.decode("gbk", "replace")
    return v


def key_of(k):
    kk = deref(k)
    return (getattr(kk, "name", None) or b2s(getattr(kk, "value", None)) or "?")


def ivar(node, name):
    node = deref(node)
    if not isinstance(node, M.ObjNode):
        return None
    for k, v in node.ivars:
        if b2s(k) == name:
            return v
    return None


def brief(node, n=40):
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
    return "%s(%r)" % (node.type, b2s(getattr(node, "value", None)))


def main():
    global out
    if "--out" in sys.argv:
        out = open(sys.argv[sys.argv.index("--out") + 1], "w", encoding="utf-8")
    doc = xj_model.Doc(xj_env.save_path())
    contents = deref(doc.objects[-1]["node"])
    secs = {key_of(k): v for k, v in contents.pairs}
    system = deref(secs["system"])
    sec = deref(ivar(system, "@security"))
    out.write("@cheated = %s   @frames_on_save = %s\n"
              % (brief(ivar(system, "@cheated")),
                 brief(ivar(system, "@frames_on_save"))))
    out.write("@security = %s\n" % brief(sec))
    if not isinstance(sec, M.HashNode):
        return 0
    letters = {}
    for k, v in sec.pairs:
        out.write("\n  %s -> %s\n" % (key_of(k), brief(v, 80)))
        vv = deref(v)
        if not isinstance(vv, M.HashNode):
            continue
        for k2, v2 in vv.pairs:
            c = deref(v2)
            out.write("     %s -> %s\n" % (key_of(k2), brief(c, 80)))
            if not isinstance(c, M.ObjNode):
                continue
            code = deref(ivar(c, "@code"))
            val = deref(ivar(c, "@value"))
            out.write("        @code = %s\n" % brief(code, 120))
            out.write("        @value = %s\n" % brief(val, 120))
            if isinstance(val, M.ArrayNode):
                out.write("        数字 = %d 位\n" % len(val.items))
                for i, x in enumerate(val.items):
                    xx = unwrap(x)
                    b = xx.data if isinstance(xx, M.StrNode) else b""
                    out.write("           [%d] %r\n" % (i, b))
                    if len(b) == 16:
                        letters.setdefault(b, []).append(key_of(k2))
    out.write("\n不同的 16 字节密文块 = %d 个\n"
              % len([k for k in letters if not isinstance(k, str)]))
    for k, ids in sorted(letters.items(), key=lambda kv: (len(kv[0]), kv[0])):
        out.write("   %s  ← 出现在 item %s\n" % (k.hex(), ids))
    out.flush()
    if "--out" in sys.argv:
        out.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
