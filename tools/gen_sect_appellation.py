# -*- coding: utf-8 -*-
"""从游戏的「拜师」事件里抽出「门派 -> 称谓」，生成 `src/tables/sect_appellation.py`。

    python tools/gen_sect_appellation.py           # 生成（Data 里的地图会自动先解密）
    python tools/gen_sect_appellation.py --check   # 只核对，不写文件

背景：门派称谓**不是表**，是硬编码在每张地图的拜师事件脚本里，一处一个门派：

    $game_player.actor.clear_skills
    $game_player.actor.learn_skill(9)
    $game_player.actor.instance_variable_set(:@sect_id, 1)     # ← 门派 id
    $game_player.actor.attr.reset_point
    $game_player.actor.add_appellation('五庄观弟子')            # ← 称谓
    $tip.add_text("... 3.获得了新的门派称谓 ...")

所以同一个事件页里同时有 `:@sect_id, N` 和 `add_appellation('X')` —— 成对抠出来
就是权威映射（比对门派名+「弟子」硬拼可靠：id 12「龙宫」的称谓是「东海龙宫弟子」）。

游戏内测换版本后重跑一次即可。
"""
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "src")
OUT = os.path.join(SRC, "tables", "sect_appellation.py")
PLAIN = os.path.join(HERE, "_plain_events")

sys.path.insert(0, SRC)
sys.path.insert(0, os.path.join(SRC, "tables"))

import codec                                                    # noqa: E402
import marshal_ruby as M                                        # noqa: E402
import sect as sect_mod                                         # noqa: E402


def deref(n, depth=0):
    while depth < 8 and n is not None:
        depth += 1
        if isinstance(n, M.LinkNode) and n.target is not None:
            n = n.target
            continue
        if isinstance(n, M.IVarNode) and n.inner is not None:
            n = n.inner
            continue
        break
    return n


def ivar(o, name):
    for k, v in getattr(deref(o), "ivars", []) or []:
        if k == name:
            return v
    return None


def as_text(n):
    n = deref(n)
    try:
        v = M.value_of(n)
    except Exception:
        return ""
    if isinstance(v, bytes):
        return v.decode("utf-8", "replace")
    return "" if v is None else str(v)


def items(n):
    return list(getattr(deref(n), "items", []) or [])


def pairs(n):
    n = deref(n)
    return list(n.pairs) if isinstance(n, M.HashNode) else []


#: 从一条脚本行里抠门派 id / 称谓
import re                                                       # noqa: E402
RE_SECT = re.compile(r"instance_variable_set\(:\s*@?sect_id\s*,\s*(\d+)\s*\)")
RE_APP = re.compile(r"add_appellation\(\s*['\"]([^'\"]{1,40})['\"]\s*\)")


def find_game_dir():
    sys.path.insert(0, SRC)
    import paths
    return paths.find_game_dir()


def scan(game_dir):
    """返回 (found, sources)：found = {sect_id: 称谓}；sources = {sect_id: 文件}。"""
    data = os.path.join(game_dir, "Data")
    os.makedirs(PLAIN, exist_ok=True)
    found, sources, notes = {}, {}, []
    for name in sorted(os.listdir(data)):
        if not name.endswith(".rvdata2"):
            continue
        src = os.path.join(data, name)
        dst = os.path.join(PLAIN, name + ".bin")
        if not os.path.exists(dst) or os.path.getsize(dst) == 0:
            try:
                codec.decrypt_file(src, dst)
            except Exception:
                continue
        if os.path.getsize(dst) == 0:
            continue
        b = open(dst, "rb").read()
        if b"add_appellation" not in b:
            continue
        try:
            root = M.parse_stream(b)[-1]["node"]
        except Exception as e:
            notes.append("%s 解析失败：%r" % (name, e))
            continue
        for _k, ev in pairs(ivar(root, "@events")):
            for pg in items(ivar(ev, "@pages")):
                lines = []
                for cmd in items(ivar(pg, "@list")):
                    code = M.value_of(deref(ivar(cmd, "@code")))
                    params = items(ivar(cmd, "@parameters"))
                    if code in (355, 655) and params:
                        lines.append(as_text(params[0]))
                blob = "\n".join(lines)
                ms, ma = RE_SECT.search(blob), RE_APP.search(blob)
                if not ma:
                    continue
                app = ma.group(1)
                if not ms:
                    notes.append("%s：有 add_appellation(%r) 但同一页没有 @sect_id" %
                                 (name, app))
                    continue
                sid = int(ms.group(1))
                if sid in found and found[sid] != app:
                    notes.append("%s：门派 %d 出现了两个称谓 %r / %r"
                                 % (name, sid, found[sid], app))
                found[sid] = app
                sources[sid] = name
    return found, sources, notes


def render(found, sources):
    lines = ["# -*- coding: utf-8 -*-",
             '"""门派 -> 门派称谓（「拜师」时游戏发的那个）。',
             "",
             "**自动生成，别手改** —— `python tools/gen_sect_appellation.py` 重新生成。",
             "",
             "来源：每张地图的拜师事件脚本里成对出现的",
             "`instance_variable_set(:@sect_id, N)` 与 `add_appellation('X')`",
             "（见生成器头部的说明）。游戏内测换版本后重跑生成器即可。",
             '"""',
             "",
             "#: 门派 id -> 称谓（0「无门派」没有称谓）",
             "SECT_APPELLATION = {"]
    for sid in sorted(found):
        lines.append("    %d: %r,   # %s / %s"
                     % (sid, found[sid], sect_mod.sect_name(sid), sources[sid]))
    lines += ["}",
              "",
              "#: 称谓 -> 门派 id（反查用；同名歧义时取小的 id）",
              "APPELLATION_TO_SECT = {}",
              "for _sid in sorted(SECT_APPELLATION, reverse=True):",
              "    APPELLATION_TO_SECT[SECT_APPELLATION[_sid]] = _sid",
              "del _sid",
              "",
              "",
              "def sect_appellation(sect_id):",
              '    """门派 id -> 称谓（0 或认不出的 id -> None）。"""',
              "    try:",
              "        return SECT_APPELLATION.get(int(sect_id))",
              "    except (TypeError, ValueError):",
              "        return None",
              "",
              "",
              "def sect_of_appellation(text):",
              '    """这个称谓属于哪个门派（不是门派称谓 -> None）。"""',
              "    return APPELLATION_TO_SECT.get(text)",
              ""]
    return "\n".join(lines)


def main():
    check = "--check" in sys.argv
    game_dir = find_game_dir()
    print("游戏目录 = %s" % game_dir)
    found, sources, notes = scan(game_dir)
    for n in notes:
        print("  ⚠ %s" % n)
    print("\n抠到 %d 个门派称谓：" % len(found))
    bad = []
    for sid in sorted(found):
        nm = sect_mod.sect_name(sid) or "?"
        ok = nm in found[sid]
        if not ok:
            bad.append(sid)
        print("  %2d %-6s -> %-12r  (%s)%s"
              % (sid, nm, found[sid], sources[sid], "" if ok else "  ← 门派名不在称谓里"))
    missing = [s for s in sect_mod.SECTS if s and s not in found]
    if missing:
        print("  ⚠ 有门派没抠到称谓：%r" % (missing,))
    if bad:
        print("  ⚠ 这些门派的称谓里没有门派名（自己核对一下）：%r" % (bad,))

    text = render(found, sources)
    if check:
        old = open(OUT, encoding="utf-8").read() if os.path.exists(OUT) else ""
        same = old == text
        print("\n--check：%s" % ("与现有表一致" if same else "和现有表**不一致**，要重跑生成"))
        return 0 if same else 1
    open(OUT, "w", encoding="utf-8", newline="\n").write(text)
    print("\n已写出 %s（%d 字节）" % (OUT, len(text.encode("utf-8"))))
    return 0 if not (missing or bad) else 0     # 缺项只提示，不挡生成


if __name__ == "__main__":
    sys.exit(main())
