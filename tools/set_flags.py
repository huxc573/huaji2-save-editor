# -*- coding: utf-8 -*-
"""快速切换 xj_marshal.py 顶部的实验开关（解析器行为对照用）。

用法：
    python tools/set_flags.py                     # 只看当前值
    python tools/set_flags.py CLASS=1 IVAR=0
可切换的键：CLASS（类/模块是否占对象编号）、IVAR（'I' 是否额外占编号）、
STRICT（严格校验开关）
"""
import os
import re
import sys

sys.stdout.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(os.path.dirname(HERE), "src", "xj_marshal.py")

MAP = {
    "CLASS": "REGISTER_CLASS_MODULE",
    "IVAR": "IVAR_REGISTER",
    "STRICT": "STRICT_LINKS",
}

txt = open(SRC, encoding="utf-8").read()
for arg in sys.argv[1:]:
    k, _, v = arg.partition("=")
    name = MAP.get(k.upper())
    if not name:
        print("未知开关 %r" % k)
        continue
    val = "True" if v not in ("0", "false", "False") else "False"
    pat = re.compile(r"^(%s = )(True|False)$" % name, re.M)
    if not pat.search(txt):
        print("找不到 %s" % name)
        continue
    txt = pat.sub(lambda m: m.group(1) + val, txt)

open(SRC, "w", encoding="utf-8").write(txt)
for k, name in MAP.items():
    m = re.search(r"^%s = (True|False)$" % name, txt, re.M)
    print("%-6s %s = %s" % (k, name, m.group(1) if m else "?"))
