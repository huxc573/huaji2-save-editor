# -*- coding: utf-8 -*-
"""Data\\*.rvdata2 → CSV 回归测试（不碰存档，只读 Data 目录 + 写临时 csv）。

用法：python tests/test_db_csv.py
"""
import csv
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.stdout.reconfigure(errors="replace")

OK = [0, 0]
WORK = os.path.join(HERE, "_csvtest")


def check(name, cond, extra=""):
    OK[0 if cond else 1] += 1
    print("  %s %-42s %s" % ("[OK]" if cond else "[NG]", name, extra))


def main():
    import datatables
    import paths

    game = paths.find_game_dir()
    if not game or not os.path.isdir(os.path.join(game, "Data")):
        print("  [--] 没找到游戏目录，跳过")
        return 0
    print("游戏目录 = %s" % game)

    check("默认表 = 8 张", len(datatables.DEFAULT_KEYS) == 8, datatables.DEFAULT_KEYS)
    check("可选表 = Troops/CommonEvents",
          [k for k in datatables.ALL_KEYS if not datatables.is_default(k)]
          == ["Troops", "CommonEvents"])
    check("中文表名", datatables.table_label("Items") == "物品"
          and datatables.table_label("Enemies") == "敌人")

    # ---------------- 逐表解析
    counts = {}
    for key in datatables.ALL_KEYS:
        try:
            header, data = datatables.rows(key)
        except Exception as e:
            check("%s 解析" % key, False, str(e)[:60])
            continue
        counts[key] = len(data)
        check("%-12s 解析成表" % key, len(header) >= 3 and len(data) >= 1,
              "%d 列 / %d 行" % (len(header), len(data)))

    # ---------------- Items：列名 + 能查到"说明/效果"
    header, data = datatables.rows("Items")
    for col in ("ID", "名称", "说明", "效果", "伤害", "特性"):
        check("Items 有列「%s」" % col, col in header)
    idx = {c: i for i, c in enumerate(header)}
    by_id = {r[idx["ID"]]: r for r in data}
    check("Items 含药品说明行",
          "1" in by_id and "HP" in by_id["1"][idx["效果"]],
          "%r" % (by_id.get("1", ["?"])[:5],))
    fx = "".join(r[idx["效果"]] for r in data)
    check("效果已翻成人话", "HP回复" in fx and "解除状态" in fx,
          fx[:40])
    check("效果里没有光秃的代码数字", " 11 " not in fx and " 22 " not in fx)
    check("伤害已翻成人话",
          "浮动" in "".join(r[idx["伤害"]] for r in datatables.rows("Skills")[1]))

    # ---------------- 2026-10-03 描述增强：<S:N> 解名 / 去转译噪声
    h, sk = datatables.rows("Skills")
    i = {c: k for k, c in enumerate(h)}
    descs = "".join(r[i["说明"]] for r in sk)
    fxs = "".join(r[i["效果"]] for r in sk)
    dmgs = "".join(r[i["伤害"]] for r in sk)
    check("技能说明无 <S:N> 占位符（已解成状态名）", "<S:" not in descs,
          descs[:40])
    check("技能效果无 #id 转译残留", "#" not in fxs)
    check("技能伤害无「公式:」转译残留", "公式:" not in dmgs)
    check("技能伤害无 type0 噪声行",
          all(not r[i["伤害"]].startswith("伤害:无") for r in sk))
    check("回复量取固定值（不是 +500%）", "%)" not in by_id["1"][idx["效果"]],
          by_id["1"][idx["效果"]])
    check("附加状态解出状态名", "附加状态[" in fxs)
    dm = datatables.desc_map("Skills")
    bad_dm = [k for k, (_n, d) in dm.items() if "<S:" in d]
    check("desc_map（界面悬浮）同样已清洗", not bad_dm, "%d 条残留" % len(bad_dm))

    # ---------------- 其它表的嵌套字段
    h, w = datatables.rows("Enemies")
    i = {c: k for k, c in enumerate(h)}
    pcol = "能力(最大HP/MP/攻/防/魔攻/魔防/敏/运)"
    check("Enemy 能力 8 项", len(w[0][i[pcol]].split("/")) == 8,
          w[0][i[pcol]])
    dr = "".join(r[i["掉落"]] for r in w)
    check("Enemy 掉落列可读", dr != "" and ("掉率" in dr or "无" in dr),
          w[0][i["掉落"]])
    h, s = datatables.rows("Skills")
    i = {c: k for k, c in enumerate(h)}
    check("技能 使用场合/范围 已翻译",
          all("(" in r[i["使用场合"]] for r in s), s[0][i["使用场合"]])
    h, st = datatables.rows("States")
    i = {c: k for k, c in enumerate(h)}
    check("状态 持续回合 可读", "~" in st[0][i["持续回合"]], st[0][i["持续回合"]])
    h, c = datatables.rows("Classes")
    i = {c2: k for k, c2 in enumerate(h)}
    check("职业 学会技能 可读", "Lv" in c[0][i["学会技能"]]
          and "技能#" in c[0][i["学会技能"]], c[0][i["学会技能"]][:40])

    # ---------------- 名字映射（存档界面用）
    nm = datatables.name_map("Items")
    check("name_map 可用", len(nm) >= 100 and nm.get(1, "") != "",
          "共 %d 条，1 = %s" % (len(nm), nm.get(1)))

    # ---------------- 导出 CSV
    shutil.rmtree(WORK, ignore_errors=True)
    res = datatables.export_all(WORK)
    bad = [p for p, n in res if n == 0 or not os.path.exists(p)]
    check("全部导出成功", not bad, "%d 个文件" % len(res))
    for p, n in res:
        raw = open(p, "rb").read(8)
        name = os.path.basename(p)
        check("%-22s 有 BOM(Excel 直接开)" % name, raw.startswith(b"\xef\xbb\xbf"),
              raw.hex())
        with open(p, encoding="utf-8-sig", newline="") as f:
            rows = list(csv.reader(f))
        check("%-22s 行数对得上" % name, len(rows) - 1 == n and len(rows) > 1,
              "csv %d 行 / 内存 %d 行" % (len(rows) - 1, n))
        check("%-22s 表头是中文" % name,
              any("\u4e00" <= ch <= "\u9fff" for ch in rows[0][0] + rows[0][1]),
              ",".join(rows[0][:4]))

    # 单独导出一张表 & 指定目录
    os.makedirs(os.path.join(WORK, "sub"), exist_ok=True)
    p, n = datatables.export_csv("States", os.path.join(WORK, "sub"))
    check("单表导出到指定目录", os.path.exists(p) and "States" in p, os.path.basename(p))

    # 只有 8 张默认表时不该顺手把可选的也转了
    os.makedirs(os.path.join(WORK, "def8"), exist_ok=True)
    datatables.export_all(os.path.join(WORK, "def8"))
    n8 = len([x for x in os.listdir(os.path.join(WORK, "def8")) if x.endswith(".csv")])
    check("默认只导 8 张", n8 == 8, "%d 个" % n8)

    # 命令行入口：只给 --out 也必须真导出（曾经只会打印一遍表清单就退出）
    cli_dir = os.path.join(WORK, "cli")
    os.makedirs(cli_dir, exist_ok=True)
    script = os.path.join(ROOT, "src", "datatables.py")
    p = subprocess.run([sys.executable, script, "--out", cli_dir],
                       capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    n_csv = len([x for x in os.listdir(cli_dir) if x.endswith(".csv")])
    check("CLI: --out <目录> 真导出了 8 张", p.returncode == 0 and n_csv == 8,
          "退出码 %d / %d 个 csv" % (p.returncode, n_csv))
    p2 = subprocess.run([sys.executable, script], capture_output=True, text=True,
                        encoding="utf-8", errors="replace")
    check("CLI: 不带参数仍是表清单", "用法：" in (p2.stdout or ""),
          "退出码 %d" % p2.returncode)

    shutil.rmtree(WORK, ignore_errors=True)
    print("\n==== %d 通过 / %d 失败 ====" % (OK[0], OK[1]))
    return 1 if OK[1] else 0


if __name__ == "__main__":
    sys.exit(main())
