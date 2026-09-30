# -*- coding: utf-8 -*-
"""从游戏 `Data\\*.rvdata2` 生成 `src/tables/db_table.py`（内置名字表）。

为什么要有这个文件
------------------
工具里所有的**名字**（技能 / 物品 / 武器 / 防具 / 召唤兽 / 职业）都是运行时
去游戏目录读 `Data\\<Key>.rvdata2` 拿的：先 `XJCodec32.exe` 解出来、再解析
Marshal。别人的机器上这一步可能失败 —— 工具没放在游戏目录里、游戏版本对不上、
杀软拦了、加密改了（内测版 V2.2 的解密被绑进授权链）—— 名字就会整片变成 `?`。

内嵌之后：**读游戏目录成功就用游戏目录（保持与"模板 / 克隆"同源、拿到最新），
读失败才退回内置表**，永不抛异常。

顺带把 `Classes` 的「天生技能」也内嵌了：`actor_class_learnings()` /
`class_skill_ids()` 拿不到表时返回 `[]`，"清空门派"就会把技能清光而不是重置成
天生技能 —— 那是**静默的错误行为**，不只是显示难看。

生成哪些东西（表结构见 `src/tables/db_table.py` 的模块 docstring）
------------------------------------------------------------------
    NAMES            {表键: {id: @name}}
    DESCS            {表键: {id: @description}}
    CLASS_LEARNINGS  {职业 id: [[等级, 技能 id], ...]}

用法
----
    python tools/gen_db_table.py                 # 生成/覆盖 src/tables/db_table.py
    python tools/gen_db_table.py --check         # 只校验（CI / 回归用，不一致退 1）
    python tools/gen_db_table.py --game <游戏根>  # 显式指定游戏目录
    python tools/gen_db_table.py --out <路径>     # 写到别处（调试用）

⚠ 生成结果**只跟游戏数据有关**，与登录/账号无关；`--check` 全绿 = 磁盘上的内置表
就是当前游戏数据导出的那一份。
"""
import argparse
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

import datatables  # noqa: E402
import paths  # noqa: E402

DEFAULT_OUT = os.path.join(SRC, "tables", "db_table.py")

#: 收名字/说明的表；顺序固定，生成结果才稳定（diff 才有意义）
NAME_KEYS = ["Skills", "Items", "Weapons", "Armors", "Actors", "Classes"]


def collect(game_dir):
    """读游戏目录，返回 (names, descs, learnings)。"""
    names, descs = {}, {}
    for key in NAME_KEYS:
        n_map, d_map = {}, {}
        _root, items = datatables.load(key, game_dir)
        for i, node in items:
            nm = datatables.s(node, "@name") or ""
            if nm:
                n_map[i] = nm
            desc = datatables.s(node, "@description") or ""
            if desc:
                d_map[i] = desc
        names[key] = n_map
        descs[key] = d_map

    learnings = {}
    _root, classes = datatables.load("Classes", game_dir)
    for cid, node in classes:
        arr = datatables.deref(datatables.ivar(node, "@learnings"))
        pairs = []
        if isinstance(arr, datatables.M.ArrayNode):
            for it in arr.items:
                f = datatables.deref(it)
                if f is None:
                    continue
                sid = datatables.val(f, "@skill_id")
                lv = datatables.val(f, "@level")
                if isinstance(sid, int) and sid:
                    pairs.append([lv if isinstance(lv, int) else 1, sid])
        if pairs:
            learnings[cid] = sorted(pairs)
    return names, descs, learnings


def _render_dict_lines(name, mapping, indent="    "):
    out = ["%s = {" % name]
    for k in sorted(mapping):
        out.append("%s%r: %r," % (indent, k, mapping[k]))
    out.append("}")
    return out


def render(names, descs, learnings, game_dir):
    L = []
    L.append("# -*- coding: utf-8 -*-")
    L.append('"""游戏 Data\\\\*.rvdata2 的名字表（由 tools/gen_db_table.py 生成，**请勿手改**）。')
    L.append("")
    L.append("工具里每个名字本来都是运行时去游戏目录读 `Data\\\\<Key>.rvdata2` 拿的；")
    L.append("别人的机器上那一步可能失败（没放在游戏目录里 / 版本不符 / 加密改了），")
    L.append("名字就会整片变成 `?`。这里是同一份数据的**内置快照**，只在读不到游戏目录时兜底。")
    L.append("")
    L.append("    NAMES            {表键: {id: @name}}")
    L.append("    DESCS            {表键: {id: @description}}")
    L.append("    CLASS_LEARNINGS  {职业 id: [[等级, 技能 id], ...]}   ← 天生技能")
    L.append("")
    L.append("用法：`datatables.name_map()` / `desc_map()` / `class_learnings()` 自动兜底，")
    L.append("调用方**不需要**知道自己用的是内置表还是游戏目录。")
    L.append("")
    L.append("重新生成：`python tools/gen_db_table.py`（`--check` 只校验）。")
    L.append('"""')
    L.append("")
    L.append("#: 生成来源的游戏目录**名**（不用全路径：换台机器/换盘符不该让 --check 变红）")
    L.append("GENERATED_FROM = %r" % os.path.basename(game_dir.rstrip("\\/")))
    L.append("")
    for key in NAME_KEYS:
        L.append("# ---------------------------------------------------------------- %s" % key)
        L += _render_dict_lines("_%s_NAMES" % key.upper(), names[key])
        L.append("")
    for key in NAME_KEYS:
        # 空表也要写出来：下面 DESCS 会引用它，缺了就是 NameError
        L += _render_dict_lines("_%s_DESCS" % key.upper(), descs[key])
        L.append("")
    L += _render_dict_lines("CLASS_LEARNINGS",
                            dict((k, [tuple(p) for p in v])
                                 for k, v in learnings.items()))
    L.append("")
    L.append("")
    # 汇总成按表键索引的大字典（调用方只认这一个口）
    L.append("NAMES = {")
    for key in NAME_KEYS:
        L.append("    %r: _%s_NAMES," % (key, key.upper()))
    L.append("}")
    L.append("")
    L.append("DESCS = {")
    for key in NAME_KEYS:
        L.append("    %r: _%s_DESCS," % (key, key.upper()))
    L.append("}")
    L.append("")
    L.append("")
    L.append("def names(key):")
    L.append('    """{id: 名字}；没有这张表就返回空字典。"""')
    L.append("    return NAMES.get(key) or {}")
    L.append("")
    L.append("")
    L.append("def descs(key):")
    L.append('    """{id: 说明}；没有这张表就返回空字典。"""')
    L.append("    return DESCS.get(key) or {}")
    L.append("")
    L.append("")
    L.append("def learnings(class_id):")
    L.append('    """某个职业的天生技能 → [(等级, 技能 id), ...]；没有就返回 []。"""')
    L.append("    try:")
    L.append("        return list(CLASS_LEARNINGS.get(int(class_id), ()))")
    L.append("    except (TypeError, ValueError):")
    L.append("        return []")
    L.append("")
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser(description="生成 src/tables/db_table.py")
    ap.add_argument("--check", action="store_true",
                    help="只校验磁盘上的内置表是否与游戏数据一致")
    ap.add_argument("--game", default=None, help="游戏根目录（默认自动找）")
    ap.add_argument("--out", default=DEFAULT_OUT, help="输出路径")
    a = ap.parse_args()

    game = a.game or paths.find_game_dir()
    if not game:
        print("[NG] 找不到游戏目录（可用 --game 指定，或设 XJ_GAME）")
        return 1
    print("游戏目录 = %s" % game)

    names, descs, learnings = collect(game)
    for key in NAME_KEYS:
        print("  %-10s 名字 %4d 条 / 说明 %4d 条"
              % (key, len(names[key]), len(descs[key])))
    print("  %-10s %d 个职业有天生技能" % ("Classes", len(learnings)))

    text = render(names, descs, learnings, game)
    # 行尾保持 LF：仓库有 .gitattributes，且生成文件不该因为平台变行尾
    blob = text.encode("utf-8")

    if a.check:
        if not os.path.exists(a.out):
            print("[NG] 没有 %s，先跑一次：python tools/gen_db_table.py" % a.out)
            return 1
        with open(a.out, "rb") as f:
            cur = f.read()
        if cur == blob:
            print("[OK] %s 与游戏数据一致（%d 行 / %.1f KB）"
                  % (a.out, text.count("\n"), len(blob) / 1024.0))
            return 0
        print("[NG] %s 与游戏数据**不一致** —— 重新生成并提交" % a.out)
        print("     磁盘 %d 字节，应为 %d 字节" % (len(cur), len(blob)))
        for i, (x, y) in enumerate(zip(cur.splitlines(), blob.splitlines())):
            if x != y:
                print("     第一处不同在第 %d 行：" % (i + 1))
                print("       磁盘：%r" % x[:160])
                print("       应为：%r" % y[:160])
                break
        else:
            print("     （前面都一样，是行数不同）")
        return 1

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "wb") as f:
        f.write(blob)
    print("[OK] 已写入 %s（%d 行 / %.1f KB）"
          % (a.out, text.count("\n"), len(blob) / 1024.0))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")
    sys.exit(main())
