# -*- coding: utf-8 -*-
"""排查 _scripts 行号：按 \\n 分段 vs 文本逻辑行。"""
import sys

sys.stdout.reconfigure(errors="replace")

p = r"d:\Life\Game\Local\MH\画迹\【画迹2：缘起凡尘】 [尝鲜版]\!Tools\Github\huaji2-save-editor\tools\_scripts\0000_000015.rb"
raw = open(p, "rb").read()
by_n = raw.split(b"\n")
txt = raw.decode("utf-8", errors="replace")
logical = txt.splitlines()
print("按\\n 分段:", len(by_n), " 文本逻辑行:", len(logical))

KW = b"is_passive?($skills[:\xe6\x85\xa7\xe6\xa0\xb9])"   # 慧根
KW2 = "is_passive?($skills[:\u6167\u6839])"
for i, x in enumerate(by_n):
    if KW in x:
        print("慧根 by_n 行号", i + 1)
        break
for i, x in enumerate(logical):
    if KW2 in x:
        print("慧根 logical 行号", i + 1)
        break

crr = sum(1 for x in by_n if x.endswith(b"\r\r"))
cr1 = sum(1 for x in by_n if x.endswith(b"\r"))
print("以 \\r\\r 结尾的行:", crr, " 以 \\r 结尾的行:", cr1)
# 统计一段：前 200 行字节样例
print("前5行字节:", [repr(x[-8:]) for x in by_n[:5]])
