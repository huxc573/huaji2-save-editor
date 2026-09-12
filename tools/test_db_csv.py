# -*- coding: utf-8 -*-
"""Data\\*.rvdata2 → CSV 回归测试（不碰存档，只读 Data 目录 + 写临时 csv）。

用法：python tools/test_db_csv.py
"""
import csv
import os
import shutil
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
    import xj_db
    import xj_env

    game = xj_env.find_game_dir()
    if not game or not os.path.isdir(os.path.join(game, "Data")):
        print("  [--] 没找到游戏目录，跳过")
        return 0
    print("游戏目录 = %s" % game)

    check("默认表 = 8 张", len(xj_db.DEFAULT_KEYS) == 8, xj_db.DEFAULT_KEYS)
    check("可选表 = Troops/CommonEvents",
          [k for k in xj_db.ALL_KEYS if not xj_db.is_default(k)]
          == ["Troops", "CommonEvents"])
    check("中文表名", xj_db.table_label("Items") == "物品"
          and xj_db.table_label("Enemies") == "敌人")

    # ---------------- 逐表解析
    counts = {}
    for key in xj_db.ALL_KEYS:
        try:
            header, data = xj_db.rows(key)
        except Exception as e:
            check("%s 解析" % key, False, str(e)[:60])
            continue
        counts[key] = len(data)
        check("%-12s 解析成表" % key, len(header) >= 3 and len(data) >= 1,
              "%d 列 / %d 行" % (len(header), len(data)))

    # ---------------- Items：列名 + 能查到"说明/效果"
    header, data = xj_db.rows("Items")
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
    check("伤害已翻成人话", "浮动" in "".join(r[idx["伤害"]] for r in data))

    # ---------------- 其它表的嵌套字段
    h, w = xj_db.rows("Enemies")
    i = {c: k for k, c in enumerate(h)}
    pcol = "能力(最大HP/MP/攻/防/魔攻/魔防/敏/运)"
    check("Enemy 能力 8 项", len(w[0][i[pcol]].split("/")) == 8,
          w[0][i[pcol]])
    dr = "".join(r[i["掉落"]] for r in w)
    check("Enemy 掉落列可读", dr != "" and ("掉率" in dr or "无" in dr),
          w[0][i["掉落"]])
    h, s = xj_db.rows("Skills")
    i = {c: k for k, c in enumerate(h)}
    check("技能 使用场合/范围 已翻译",
          all("(" in r[i["使用场合"]] for r in s), s[0][i["使用场合"]])
    h, st = xj_db.rows("States")
    i = {c: k for k, c in enumerate(h)}
    check("状态 持续回合 可读", "~" in st[0][i["持续回合"]], st[0][i["持续回合"]])
    h, c = xj_db.rows("Classes")
    i = {c2: k for k, c2 in enumerate(h)}
    check("职业 学会技能 可读", "Lv" in c[0][i["学会技能"]]
          and "技能#" in c[0][i["学会技能"]], c[0][i["学会技能"]][:40])

    # ---------------- 名字映射（存档界面用）
    nm = xj_db.name_map("Items")
    check("name_map 可用", len(nm) >= 100 and nm.get(1, "") != "",
          "共 %d 条，1 = %s" % (len(nm), nm.get(1)))

    # ---------------- 导出 CSV
    shutil.rmtree(WORK, ignore_errors=True)
    res = xj_db.export_all(WORK)
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
    p, n = xj_db.export_csv("States", os.path.join(WORK, "sub"))
    check("单表导出到指定目录", os.path.exists(p) and "States" in p, os.path.basename(p))

    # 只有 8 张默认表时不该顺手把可选的也转了
    os.makedirs(os.path.join(WORK, "def8"), exist_ok=True)
    xj_db.export_all(os.path.join(WORK, "def8"))
    n8 = len([x for x in os.listdir(os.path.join(WORK, "def8")) if x.endswith(".csv")])
    check("默认只导 8 张", n8 == 8, "%d 个" % n8)

    shutil.rmtree(WORK, ignore_errors=True)
    print("\n==== %d 通过 / %d 失败 ====" % (OK[0], OK[1]))
    return 1 if OK[1] else 0


if __name__ == "__main__":
    sys.exit(main())
