# -*- coding: utf-8 -*-
"""一次性：从游戏脚本里提取 $exps[:actor] / $exps[:baby] 两张经验表并验证。"""
import io
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

src = open(r"tools/_scripts/0000_000015.rb", encoding="utf-8", errors="replace").read()
i = src.find("$exps = {")
j = src.find("};", i)
block = src[i:j]
print("块长度:", len(block))


def extract(name):
    k = block.find(":%s => [" % name)
    end = block.find("]", k)
    nums = [int(x) for x in re.findall(r"-?\d+", block[k:end])]
    return nums


actor = extract("actor")
baby = extract("baby")
print("actor 表: %d 项" % len(actor))
print("baby  表: %d 项" % len(baby))

# 验证：乐天凌 40 级，游戏显示升级经验 332296，当前经验 35000
# → next_level_exp(40) = $exps[:actor][40]（第 41 项，0 起）应为 367296
print("actor[40] =", actor[40], "（期望 367296 = 332296 + 35000）")
print("差值 =", actor[40] - 35000, "（期望 332296）")
# 60 级的角色（李修远）：升级经验应为 actor[60] - @exp
print("actor[60] =", actor[60])
# 表尾部
print("actor 尾 5 项:", actor[-5:])
print("baby 尾 5 项:", baby[-5:])
# 存成 python 模块片段备用
with open(r"tools/_exp_tables.txt", "w", encoding="utf-8") as f:
    f.write("ACTOR = %r\n\nBABY = %r\n" % (actor, baby))
print("已写 tools/_exp_tables.txt")
