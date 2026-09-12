# -*- coding: utf-8 -*-
"""从游戏脚本里把 `$baby` 资质配置表抽出来，生成 `src/xj_baby_data.py`。

为什么要生成：`$baby` 表（每种召唤兽的 type/allow_lv/六项资质上限/成长/寿命）
只存在于 `Data\\Scripts.rvdata2` 的 Ruby 代码里，运行时解析脚本太重；
一次性抽成 Python 常量最省事（和 `src/xj_changelog.py` 一个套路）。

用法：python tools/gen_baby_data.py
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SD = os.path.join(HERE, "_scripts")
OUT = os.path.join(ROOT, "src", "xj_baby_data.py")

sys.stdout.reconfigure(errors="replace")

ENTRY = re.compile(
    r"^\s*(?P<key>\d+|:\w+)\s*=>\s*\{(?P<body>[^}]*)\}\s*,?\s*$")
NUM = re.compile(r":(?P<k>\w+)\s*=>\s*(?P<v>-?[\d.]+|:\w+)")


def main():
    fs = [os.path.join(SD, n) for n in sorted(os.listdir(SD))
          if n.endswith(".rb")]
    if not fs:
        print("没有 %s，先跑 python tools/dump_scripts.py" % SD)
        return 1
    fs.sort(key=os.path.getsize, reverse=True)
    raw = open(fs[0], "rb").read()
    u = raw.decode("utf-8", "replace")
    g = raw.decode("gbk", "replace")
    lines = (u if u.count("\ufffd") <= g.count("\ufffd") else g).split("\n")

    start = None
    for i, l in enumerate(lines):
        if re.match(r"^\$baby\s*=", l):
            start = i
            break
    if start is None:
        print("找不到 $baby = 定义")
        return 1

    species = {}
    pools = {}
    for i in range(start, min(len(lines), start + 200)):
        l = lines[i]
        if l.strip().startswith(":_max"):
            break
        m = ENTRY.match(l)
        if not m:
            continue
        key, body = m.group("key"), m.group("body")
        data = {}
        for mm in NUM.finditer(body):
            k, v = mm.group("k"), mm.group("v")
            if v.startswith(":"):
                data[k] = v[1:]            # :infinite → "infinite"
            elif "." in v:
                data[k] = float(v)
            else:
                data[k] = int(v)
        if "type" not in data:
            continue
        if key.startswith(":"):
            pools[key[1:]] = data
        else:
            species[int(key)] = data

    # 生成 Python 模块
    L = []
    L.append("# -*- coding: utf-8 -*-")
    L.append('"""游戏 `$baby` 资质配置表（**自动生成**，别手改）。')
    L.append("")
    L.append("生成：python tools/gen_baby_data.py")
    L.append("来源：Data\\\\Scripts.rvdata2 里的 `$baby = { ... }`（脚本 %s）" % os.path.basename(fs[0]))
    L.append("")
    L.append("字段：type(普通/神兽) allow_lv atk def hp mp agi eva grow life(pool 里是 \"infinite\")")
    L.append('"""')
    L.append("")
    L.append("#: 按召唤兽 id（= Data\\Actors 的 id）")
    L.append("SPECIES = {")
    for i in sorted(species):
        d = species[i]
        L.append("    %d: %r," % (i, d))
    L.append("}")
    L.append("")
    L.append("#: 备注池（Data\\Actors 的 note 里 `data = :池名`）")
    L.append("POOLS = {")
    for k in sorted(pools):
        L.append("    %r: %r," % (k, pools[k]))
    L.append("}")
    L.append("")
    L.append("")
    L.append("def config_of(baby_id, data_key=None):")
    L.append('    """取某种召唤兽的配置：优先备注池，其次按 id 查表。"""')
    L.append("    if data_key and data_key in POOLS:")
    L.append("        return POOLS[data_key]")
    L.append("    return SPECIES.get(int(baby_id))")
    L.append("")

    with io.open(OUT, "w", encoding="utf-8", newline="") as f:
        f.write("\n".join(L) + "\n")
    print("已写 %s（%d 种普通召唤兽 + %d 个备注池）"
          % (OUT, len(species), len(pools)))
    for k in sorted(pools):
        print("   池 %s：type=%s atk=%s hp=%s grow=%s life=%s"
              % (k, pools[k].get("type"), pools[k].get("atk"),
                 pools[k].get("hp"), pools[k].get("grow"), pools[k].get("life")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
