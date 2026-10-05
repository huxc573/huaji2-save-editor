# -*- coding: utf-8 -*-
"""从游戏脚本里把 `$baby` 资质配置表抽出来，生成 `src/tables/baby_aptitude.py`。

为什么要生成：`$baby` 表（每种召唤兽的 type / allow_lv / 六项资质 / 成长 /
寿命）只存在于游戏脚本 VM 里（`Data\\` 下没有明文），运行时解析脚本太重；
一次性抽成 Python 常量最省事。

真值来源（2026-10-04 换）：内测版 V2.201 的 `$baby` 定义在脚本 **eval_17.rb**
（离线补丁仓库的 `_work_re/eval_decoded/`），**不是**尝鲜版那份。它有三种形态：

    * 21  => { :type => :普通, :atk => 960, ... }        直接给数值
    * 179 => :神兽资质3                                  Symbol 引用池
    * 135 => [:神兽资质, { :select_type => { ... } }]     Array 引用池 + 覆盖

池定义写成 `:_池名 => { ... }`（同一个 `$baby` 哈希里的键）。运行时展开规则照抄
脚本：

    v.is_a?(Symbol) → val = $baby[:"_#{v}"].dup; val[:type2] = v
    v.is_a?(Array)  → 同上，再把 v[1] 的键并进 val

⇒ 生成时把引用**展开成实际数值**，`config_of()` 拿到的就是真值；同时保留
   `type2`（来自哪个池）备查。`select_type` 是技能池、`five` 是 proc ⇒ 都丢弃。

用法：
    python tools/gen_baby_data.py                 # 自动找 eval_17.rb
    python tools/gen_baby_data.py --src <file>    # 指定脚本（或 XJ_BABY_RB=<file>）
    python tools/gen_baby_data.py --check         # 只比对，不写文件
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "src", "tables", "baby_aptitude.py")

#: `$baby` 脚本的候选位置（按顺序取第一个存在的）
SEARCH = (
    os.path.join(HERE, "_scripts", "eval_17.rb"),
    os.path.join(ROOT, "..", "huaji2-offline-server",
                 "_work_re", "eval_decoded", "eval_17.rb"),
    os.path.join(ROOT, "..", "huaji2-offline-server",
                 "scripts_dump", "eval_17.rb"),
)

sys.stdout.reconfigure(errors="replace")

#: 顶层条目（行首无缩进；嵌套的 `:物理 => {` 因为带缩进不会被命中）
_ENTRY = re.compile(r"(?m)^(?P<key>\d+|:\w+)[ \t]*=>")
#: 一对 `:key => 值`（值是数字或 :符号；`=> {` / `=> [` 都不匹配）
_NUM = re.compile(r":(?P<k>\w+)\s*=>\s*(?P<v>-?\d+(?:\.\d+)?|:\w+)")
_BABY_HEAD = re.compile(r"(?m)^\$baby\s*=\s*\{")
_ARR_POOL = re.compile(r"\[\s*:(\w+)")

#: 输出时的字段顺序（其余字段按名字排在后面）
ORDER = ("type", "type2", "allow_lv", "atk", "def", "hp", "mp",
         "agi", "eva", "grow", "life", "vip")


def find_src(explicit=None):
    if explicit:
        return explicit if os.path.exists(explicit) else None
    env = os.environ.get("XJ_BABY_RB")
    if env and os.path.exists(env):
        return env
    for p in SEARCH:
        if os.path.exists(p):
            return p
    return None


def _coerce(raw):
    if raw.startswith(":"):
        return raw[1:]
    if "." in raw:
        return float(raw)
    return int(raw)


def _parse_pairs(body):
    """`body` 里所有 `:k => 数字|:符号`（跳过嵌套 hash / proc）。"""
    out = {}
    for m in _NUM.finditer(body or ""):
        out[m.group("k")] = _coerce(m.group("v"))
    return out


def _brace_body(s):
    """取第一个 `{` 的**内容**（大括号配平，能容忍 select_type 那样的嵌套）。"""
    i = (s or "").find("{")
    if i < 0:
        return None
    depth = 0
    for j in range(i, len(s)):
        if s[j] == "{":
            depth += 1
        elif s[j] == "}":
            depth -= 1
            if depth == 0:
                return s[i + 1:j]
    return None


def parse(text):
    """解析 `$baby`：返回 (species, pools)。species[i] = {shape, pool, over, data}。"""
    m = _BABY_HEAD.search(text)
    if not m:
        return None, None
    starts = [x for x in _ENTRY.finditer(text, m.end())]
    species, pools = {}, {}
    for n, it in enumerate(starts):
        key = it.group("key")
        if key == ":_max":                    # `_max` 之后的都不是召唤兽
            break
        end = starts[n + 1].start() if n + 1 < len(starts) else len(text)
        body = text[it.end():end].strip().rstrip(",").strip()
        if key.startswith(":"):               # 池定义 `:_神兽资质 => {...}`
            pools[key[1:]] = _parse_pairs(_brace_body(body))
            continue
        bid = int(key)
        if body.startswith("{"):              # 形态 1：直接数值
            species[bid] = {"shape": "num",
                            "data": _parse_pairs(_brace_body(body))}
        elif body.startswith(":"):            # 形态 2：Symbol 引用池
            species[bid] = {"shape": "sym", "pool": body[1:].strip()}
        elif body.startswith("["):            # 形态 3：Array 引用池 + 覆盖
            pm = _ARR_POOL.match(body)
            species[bid] = {"shape": "arr", "pool": pm.group(1),
                            "over": _parse_pairs(_brace_body(body))}
    return species, pools


def expand(species, pools):
    """把引用展开成实际数值（照抄脚本的 dup + type2 + 合并覆盖）。"""
    out = {}
    for bid in sorted(species):
        rec = species[bid]
        if rec["shape"] == "num":
            cfg = dict(rec["data"])
        else:
            name = rec["pool"]
            base = pools.get("_" + name)
            if base is None:
                raise ValueError("id %d 引用的池 %r 不存在" % (bid, name))
            cfg = dict(base)
            cfg["type2"] = name
            cfg.update(rec.get("over") or {})
        out[bid] = cfg
    return out


def _fmt(d):
    keys = [k for k in ORDER if k in d]
    keys += [k for k in sorted(d) if k not in ORDER]
    return "{" + ", ".join("%r: %r" % (k, d[k]) for k in keys) + "}"


TAIL = r'''

# ---------------------------------------------------------------- 兜底（真值表外）
# `SPECIES` / `POOLS` 已是**内测版真值**（257 条 / 5 个池，解析 `$baby`），
# 绝大多数召唤兽的六项资质**不再需要估算**。下面这套只服务真值表里没有的 id。
#
# ⚠ 「是不是召唤兽」一律看 `babies.Babies.is_baby_entry()`（有名字、不是玩家
#   角色 / 坐骑 / 空占位）。`V201_BABY_IDS` 只是**候选 id 全集**，比真值表宽：
#   135~254 段真值只覆盖 64 个 id，剩下 56 个（176~178 / 188~199 / 205~209 /
#   211~229 / 238~254）若在 `Data\\Actors` 里有名字，仍走这里取估算值。
#
# 真实分段（实测 `csv/Actors_角色.csv`，2026-10-03）：
#   1~20      玩家角色（**不是**）      21~134   普通召唤兽
#   135~170   神兽                      171~254  神兽 / 小孩 / 泡泡灵仙系列
#   255       `--坐骑--` 分隔（**不是**） 256~309  坐骑（**不是**）
#   310~354   普通召唤兽                355~399  空占位（**不是**）
#   400~433   普通召唤兽
V201_BABY_IDS = frozenset(
    [*range(21, 135), *range(135, 255),
     *range(310, 355), *range(400, 434)]
)
#: 神兽 / 小孩 / 灵仙区间（实测）：135~254。
GOD_ID_RANGE = (135, 255)
#: 兜底用的普通池基准（真值 `SPECIES[21]` 的量级）。
_V201_NORMAL = {'type': '普通', 'allow_lv': 0, 'atk': 960, 'def': 960,
                'hp': 3600, 'mp': 1200, 'agi': 840, 'eva': 1320,
                'grow': 0.918, 'life': 12000}


def _v201_fallback(baby_id):
    """真值表里没有这个 id 时的兜底：**按 id 区间**判类型、给基准资质。

    返回 None 表示「这个 id 连候选都不是」（例如 1~20 的玩家角色），让调用方
    （`Babies.candidates()`）照旧过滤掉 —— 宁缺毋滥。
    `inferred=True` 标记告诉界面「这条是估的」，由界面提示用户。
    """
    i = int(baby_id)
    if i not in V201_BABY_IDS:
        return None                    # 不是召唤兽（例如 1~20 的玩家角色）
    lo, hi = GOD_ID_RANGE
    if lo <= i <= hi:
        cfg = dict(POOLS['神兽资质'])
    else:
        cfg = dict(_V201_NORMAL)
    cfg['inferred'] = True
    return cfg


def config_of(baby_id, data_key=None):
    """取某种召唤兽的配置：备注池 → id 查表 → **兜底**。

    第一档服务老档（`Data\\Actors` 的 note 写了 `data = :池名`）；第二档是主路
    （内测版 257 条真值）；第三档只给真值表外的 id 估算值。
    """
    if data_key and data_key in POOLS:
        return POOLS[data_key]
    got = SPECIES.get(int(baby_id))
    if got:
        return got
    return _v201_fallback(baby_id)
'''


def render(species, pools, src_name):
    L = []
    L.append("# -*- coding: utf-8 -*-")
    L.append('"""游戏 `$baby` 资质配置表（**自动生成**，别手改）。')
    L.append("")
    L.append("生成：python tools/gen_baby_data.py")
    L.append("来源：内测版脚本 `%s` 的 `$baby = { ... }`（展开池引用后）" % src_name)
    L.append("")
    L.append("字段：type(普通/神兽/泡泡灵仙) type2(来自哪个池) allow_lv")
    L.append("      atk def hp mp agi eva grow life(pool 里是 \"infinite\") vip")
    L.append('"""')
    L.append("")
    L.append("#: 按召唤兽 id（= Data\\Actors 的 id）；池引用已展开成实际数值")
    L.append("SPECIES = {")
    for i in sorted(species):
        L.append("    %d: %s," % (i, _fmt(species[i])))
    L.append("}")
    L.append("")
    L.append("#: 资质池（运行时 `[:池名, ...]` / `:池名` 引用的那份数值）")
    L.append("POOLS = {")
    for k in sorted(pools):
        name = k[1:] if k.startswith("_") else k
        L.append("    %r: %s," % (name, _fmt(pools[k])))
    L.append("}")
    L.append(TAIL)
    return "\n".join(L) + "\n"


def main(argv):
    args = list(argv[1:])
    src = None
    check = False
    if "--check" in args:
        check = True
        args.remove("--check")
    if "--src" in args:
        i = args.index("--src")
        src = args[i + 1] if i + 1 < len(args) else None
    src = find_src(src)
    if not src:
        print("找不到 eval_17.rb（试过：%s）" % "、".join(SEARCH))
        return 1

    text = io.open(src, "r", encoding="utf-8", errors="replace").read()
    species, pools = parse(text)
    if species is None:
        print("在 %s 里找不到 `$baby = {`" % src)
        return 1
    if not species:
        print("抠到 0 条召唤兽 —— 不写文件（怕是解析炸了）")
        return 1
    real = expand(species, pools)

    body = render(real, pools, os.path.basename(src))
    if check:
        cur = io.open(OUT, "r", encoding="utf-8").read() if os.path.exists(OUT) else ""
        ok = cur == body
        print("%s（表里 %d 条 / 池 %d 个）"
              % ("一致" if ok else "**不一致**，要重跑不带 --check 的",
                 len(real), len(pools)))
        return 0 if ok else 2

    with io.open(OUT, "w", encoding="utf-8", newline="") as f:
        f.write(body)
    n_num = sum(1 for r in species.values() if r["shape"] == "num")
    print("已写 %s" % OUT)
    print("  来源 %s：%d 条（直接数值 %d + 展开引用 %d）/ 池 %d 个"
          % (src, len(real), n_num, len(real) - n_num, len(pools)))
    for k in sorted(pools):
        p = pools[k]
        print("   池 %-8s type=%-6s atk=%-5s hp=%-5s grow=%-4s life=%s"
              % (k, p.get("type"), p.get("atk"), p.get("hp"),
                 p.get("grow"), p.get("life")))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
