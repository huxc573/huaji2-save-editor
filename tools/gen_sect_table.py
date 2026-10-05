# -*- coding: utf-8 -*-
"""从游戏脚本里抽出「门派表」，生成 `src/tables/sect.py`。

    python tools/gen_sect_table.py                  # 生成
    python tools/gen_sect_table.py --check          # 只核对，不写文件
    python tools/gen_sect_table.py --src <xxx.rb>   # 指定装着 $sects 的脚本

背景：游戏里「门派」不是 Data 表，而是脚本里硬编码的一个全局量：

    $sects = {
      0 => {name: '无门派', nick: {...}, skills: []},
      1 => {name: '五庄观', nick: {...},
            skills: [{index: 0, id: 188, lv: 10, max: 10}, ...]},
      ...
    }

角色的门派存在存档的 `@sect_id`（Game_Actor#setup 里 `@sect_id = 0`，由事件改写），
学门派技能走 `Window_Actor_Skill` 的「门派」页：

    lv = actor.sect_data[:门派][skill[:id]] += 1
    actor.learn_skill(skill[:id]) if lv >= skill[:max]     # 满了才写进 @skills

所以**正常游戏里角色能学到的 = 本门派 `skills` 那一串**（10 个，凌波城 12 个；
外加每个门派 index 10 那一个「上古××」秘技），另有 Data\\Classes 的
`@learnings` 自带的基础技能（如 id 9「牛刀小试」）。

⚠ **门派 id 不是连续的**：0 无门派、1..13（13＝凌波城）、**20**（九黎城）。
   ⇒ 判断「认不认识这个门派」一律走 `sect.SECTS`，别用 `0 <= id <= N`。

⚠ 这个全局量在 V2.201 的**脚本 VM 里**（`main.dll` 加壳、`Data/` 下没有
   `Scripts.rvdata2`），本仓库自己解不出来。现成的解码件在离线补丁仓库：

       【画迹2】内测版\\!Tools\\Github\\huaji2-offline-server\\
             _work_re\\eval_decoded\\eval_11.rb

   优先用 `--src` / 环境变量 `XJ_SECTS_RB` 指定；没给就按上面这个默认位置找。
   游戏换版本后重跑一次这个脚本即可。
"""
import io
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "src", "tables", "sect.py")

#: 找 `$sects` 的地方（按顺序试）：本地解出的脚本段 → 离线补丁仓库的解码件
SEARCH_DIRS = (
    os.path.join(HERE, "_scripts"),
    os.path.join(HERE, "..", "..", "huaji2-offline-server",
                 "_work_re", "eval_decoded"),
    os.path.join(HERE, "..", "..", "huaji2-offline-server", "scripts_dump"),
)


def _scan_dir(d):
    """目录里第一个含 `$sects = {` 的 .rb。"""
    if not os.path.isdir(d):
        return None
    for n in sorted(os.listdir(d)):
        if not n.endswith(".rb"):
            continue
        p = os.path.join(d, n)
        try:
            if "$sects = {" in open(p, encoding="utf-8",
                                    errors="replace").read():
                return p
        except OSError:
            continue
    return None


def find_script_file(explicit=None):
    """找装着 `$sects` 的那个脚本段。"""
    if explicit:
        return explicit if os.path.isfile(explicit) else None
    env = os.environ.get("XJ_SECTS_RB")
    if env and os.path.isfile(env):
        return env
    for d in SEARCH_DIRS:
        p = _scan_dir(os.path.abspath(d))
        if p:
            return p
    return None


def _block(txt):
    """取 `$sects = { ... }` 整段（按大括号配平，别用正则硬截）。"""
    i = txt.find("$sects = {")
    if i < 0:
        raise SystemExit("脚本里找不到 `$sects = {`")
    j = txt.index("{", i)
    depth = 0
    for k in range(j, len(txt)):
        c = txt[k]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return txt[j:k + 1]
    raise SystemExit("$sects 大括号不配平")



#: 门派条目的开头（`1 => {`）
_ENTRY_HEAD = re.compile(r"(?m)^\s*(\d+)\s*=>\s*\{")
_NAME = re.compile(r"name:\s*'([^']*)'")
#: `skills: [ ... ]` —— 非贪婪到第一个 `]`（条目的花括号里没有方括号，够用）
_SKILLS = re.compile(r"skills:\s*\[(.*?)\]", re.S)
#: ⚠ `index:` 在 V2.201 有、老脚本没有 ⇒ 可选。`lv` 可能是 -1（秘技）。
_SKILL = re.compile(
    r"\{\s*(?:index:\s*\d+\s*,\s*)?id:\s*(\d+)\s*,\s*lv:\s*(-?\d+)\s*,"
    r"\s*max:\s*(\d+)\s*\}")


def _entries(block):
    """把 `$sects` 里每个 `N => { ... }` 整段抠出来（大括号配平，能带 `nick:` 嵌套）。"""
    out = []
    for m in _ENTRY_HEAD.finditer(block):
        i = block.index("{", m.start())
        depth = 0
        for k in range(i, len(block)):
            c = block[k]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    out.append((int(m.group(1)), block[i:k + 1]))
                    break
    return out


def extract(txt):
    """返回 [(sect_id, 名字, [(技能id, 需求等级, 上限)]), ...]（按 id 排序）。"""
    block = _block(txt)
    out = []
    for sid, body in _entries(block):
        nm = _NAME.search(body)
        sk = _SKILLS.search(body)
        if nm is None or sk is None:
            raise SystemExit("门派 %d 解析不出 name / skills：%r"
                             % (sid, body[:80]))
        skills = [(int(a), int(b), int(c))
                  for a, b, c in _SKILL.findall(sk.group(1))]
        out.append((sid, nm.group(1), skills))
    if not out:
        raise SystemExit("$sects 里一条门派都没解析出来")
    out.sort(key=lambda x: x[0])
    return out


def gen(sects):
    lines = []
    for sid, name, skills in sects:
        ids = ", ".join("%d" % s for s, _lv, _mx in skills)
        if len(ids) > 68:
            # 太长就折行
            parts, cur = [], ""
            for s, _lv, _mx in skills:
                piece = ("%d, " % s)
                if len(cur) + len(piece) > 68:
                    parts.append(cur.rstrip())
                    cur = ""
                cur += piece
            parts.append(cur.rstrip())
            body = "\n        ".join(parts)
            lines.append("    %d: (%r, (\n        %s\n    ))," % (sid, name, body))
        else:
            lines.append("    %d: (%r, (%s))," % (sid, name, ids))
    table = "SECTS = {\n" + "\n".join(lines) + "\n}"
    tail = '''

#: 门派 id 顺序（0「无门派」在最前）
SECT_ORDER = tuple(sorted(SECTS))

#: 门派名字 -> 门派 id
SECT_NAME_TO_ID = dict((nm, sid) for sid, (nm, _ids) in SECTS.items())

#: 技能 id -> 门派 id。一个技能只属于一个门派；辅助技能/装备技能不在表里。
SKILL_TO_SECT = {}
for _sid, (_nm, _ids) in SECTS.items():
    for _i in _ids:
        SKILL_TO_SECT.setdefault(_i, _sid)
del _sid, _nm, _ids, _i


def sect_name(sect_id):
    """门派 id -> 名字（不认识就返回 None）。"""
    v = SECTS.get(sect_id)
    return v[0] if v else None


def sect_skill_ids(sect_id):
    """该门派的技能 id 元组（「无门派」或认不出的 id -> 空元组）。"""
    v = SECTS.get(sect_id)
    return v[1] if v else ()


def sect_of_skill(skill_id):
    """这个技能属于哪个门派（不属于任何门派 -> None，例如装备技能/辅助技能）。"""
    return SKILL_TO_SECT.get(skill_id)
'''
    head = '''# -*- coding: utf-8 -*-
"""门派表（**自动生成，别手改** —— 改了跑 `python tools/gen_sect_table.py`）。

来源：游戏脚本里硬编码的 `$sects`（门派**不是** Data 表）。
`SECTS[门派 id] = (名字, (该门派技能 id, ...))`，门派 id 就是存档的 `@sect_id`。

⚠ **门派 id 不是连续的**：0 无门派、1..13（13＝凌波城）、**20**（九黎城）
—— 判「认不认识」一律走 `SECTS` / `sect_name()`，别写 `0 <= id <= 12`。
⚠ 每个门派最后还有一个 index 10 的「上古××」秘技（`lv: -1, max: 1`，
游戏里开局就能拿）；凌波城有 12 个。

游戏里学门派技能（`Window_Actor_Skill`「门派」页）：
技能先攒 `@sect_data[:门派][id]` 的次数，攒够 `max` 才 `learn_skill` 写进 `@skills`
—— 所以**正常游戏里角色能学到的就是本门派 `skills` 那一串**（外加 Data\\\\Classes
`@learnings` 自带的基础技能，如 id 9「牛刀小试」）。

⚠ 辅助技能（强身术/冥想/…）和修炼是加属性/加点的，**不进 `@skills`**，
  别把它们算进「角色技能」。
"""
'''
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(head + "\n" + table + "\n" + tail)
    print("已生成 %s（%d 个门派）" % (OUT, len(sects)))
    for sid, name, skills in sects:
        print("  %2d %-6s %2d 个技能" % (sid, name, len(skills)))


def main():
    argv = sys.argv[1:]
    explicit = None
    if "--src" in argv:
        explicit = argv[argv.index("--src") + 1]
    p = find_script_file(explicit)
    if p is None:
        print("没找到装着 `$sects` 的脚本 —— 用 --src 指定，"
              "或设环境变量 XJ_SECTS_RB。\n（默认找：%s）"
              % "；".join(SEARCH_DIRS))
        return 1
    print("脚本 = %s" % p)
    txt = open(p, encoding="utf-8", errors="replace").read()
    sects = extract(txt)
    if "--check" in argv:
        sys.path.insert(0, os.path.join(ROOT, "src"))
        from tables import sect
        same = (dict((k, (v[0], tuple(v[1]))) for k, v in sect.SECTS.items())
                == dict((sid, (nm, tuple(s for s, _l, _m in sk)))
                        for sid, nm, sk in sects))
        print("一致" if same else "不一致，重新生成")
        return 0 if same else 1
    gen(sects)
    return 0


if __name__ == "__main__":
    sys.exit(main())
