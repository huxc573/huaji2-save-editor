# -*- coding: utf-8 -*-
"""从游戏脚本里抽出「门派表」，生成 `src/tables/sect.py`。

    python tools/gen_sect_table.py           # 生成（没有解出的脚本会自动先解密）
    python tools/gen_sect_table.py --check   # 只核对生成结果和脚本里的表是否一致

背景：游戏里「门派」不是 Data 表，而是脚本里硬编码的一个全局量：

    $sects = {
      0 => {name: '无门派', skills: []},
      1 => {name: '五庄观', skills: [{id: 181, lv: 20, max: 35}, ...]},
      ...
    }

角色的门派存在存档的 `@sect_id`（Game_Actor#setup 里 `@sect_id = 0`，由事件改写），
学门派技能走 `Window_Actor_Skill` 的「门派」页：

    lv = actor.sect_data[:门派][skill[:id]] += 1
    actor.learn_skill(skill[:id]) if lv >= skill[:max]     # 满了才写进 @skills

所以**正常游戏里角色能学到的技能 = 本门派那 10 个**（外加 Data\\Classes 的
`@learnings` 自带的基础技能，如 id 9「牛刀小试」）。

游戏换版本后重跑一次这个脚本即可。
"""
import io
import os
import re
import subprocess
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCRIPTS = os.path.join(HERE, "_scripts")
OUT = os.path.join(ROOT, "src", "tables", "sect.py")


def find_script_file():
    """找装着 `$sects` 的那个脚本段。"""
    if not os.path.isdir(SCRIPTS):
        return None
    for n in sorted(os.listdir(SCRIPTS)):
        if not n.endswith(".rb"):
            continue
        p = os.path.join(SCRIPTS, n)
        try:
            txt = open(p, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        if "$sects = {" in txt:
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


_ENTRY = re.compile(
    r"(\d+)\s*=>\s*\{\s*name:\s*'([^']*)'\s*,\s*skills:\s*\[(.*?)\]\s*,?\s*\}",
    re.S)
_SKILL = re.compile(r"\{\s*id:\s*(\d+)\s*,\s*lv:\s*(\d+)\s*,\s*max:\s*(\d+)\s*\}")


def extract(txt):
    """返回 [(sect_id, 名字, [(技能id, 需求等级, 上限)]), ...]（按 id 排序）。"""
    block = _block(txt)
    out = []
    for m in _ENTRY.finditer(block):
        sid = int(m.group(1))
        name = m.group(2)
        skills = [(int(a), int(b), int(c)) for a, b, c in _SKILL.findall(m.group(3))]
        out.append((sid, name, skills))
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

游戏里学门派技能（`Window_Actor_Skill`「门派」页）：
技能先攒 `@sect_data[:门派][id]` 的次数，攒够 `max` 才 `learn_skill` 写进 `@skills`
—— 所以**正常游戏里角色能学到的就是本门派这 10 个**（外加 Data\\\\Classes
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
    p = find_script_file()
    if p is None:
        print("没解出脚本，先跑：python tools/re/dump_scripts.py")
        if "--auto" not in argv:
            return 1
        r = subprocess.run([sys.executable, os.path.join(HERE, "dump_scripts.py")])
        if r.returncode != 0:
            return r.returncode
        p = find_script_file()
        if p is None:
            return 1
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
