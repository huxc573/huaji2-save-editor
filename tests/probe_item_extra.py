# -*- coding: utf-8 -*-
"""一次性探针：物品模板表的「滤过 + 附加描述 + 类别」（**纯数据层，不开窗口**）。

钉住 2026-10-04 川提的两件事：

* 物品管理里**别再出现纯编号的东西** —— `datatables.item_map()` 把两类噪音滤掉：
  分段行（`===药品===` / `======剑=======`）和没名字的行（画迹2 三张表里一共
  689 个，界面上是 `#49` 这种，选中还会把 id 写进背包）；
* **附加描述补上** —— 备注里能翻成人话的那几行（等级 / 售价 / 使用限制…），
  以及段名（`item_group()`，给模板列表的「类别」列）。

只读 `Data\\*.rvdata2`，**不碰存档**（不需要 tkinter，managed 3.13 也能跑）。
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import datatables as D


def main():
    bad = 0
    for kind in ("Items", "Weapons", "Armors"):
        m = D.item_map(kind)
        g = D.item_group(kind)
        raw = list(D.load(kind)[1])
        print("\n== %s：原表 %d → item_map %d" % (kind, len(raw), len(m)))
        no_name = [i for i in m if not m[i][0].strip()]
        sec_rows = [i for i in m if D.section_of(m[i][0])]
        print("  残留没名字的行 %d（应 0）" % len(no_name))
        print("  残留分段行     %d（应 0）" % len(sec_rows))
        print("  带类别的行     %d / %d（段名取自 %d 个 `===xxx===`）"
              % (sum(1 for i in m if g.get(i)), len(m),
                 len(set(g.values()))))
        bad += len(no_name) + len(sec_rows)
        # 分段名不能是空串，也不该把 id 算串段
        print("  段名样例 = %r" % ([g[i] for i in sorted(m) if g.get(i)][:4],))
        # 附加行
        extra = [i for i in sorted(m)
                 if any(t in m[i][1] for _f, t in D.ITEM_FLAGS)
                 or "售价 " in m[i][1] or "等级 " in m[i][1]]
        print("  带附加行的 %d 个，例：%r" % (len(extra), extra[:6]))
        for i in extra[:2]:
            print("    #%d %s：" % (i, m[i][0]))
            for ln in m[i][1].split("\n")[-2:]:
                print("       |", ln)

    # 分段归属：`===药品===` 后面那些 id 都得算「药品」
    g = D.item_group("Items")
    after = sorted(i for i in g if i > 1)
    print("\n== 分段归属抽查（Items）")
    print("  1 号是分段行:", repr(D.name_map("Items").get(1)),
          "→ 段名", g.get(1))
    print("  2 号（包子）的段名 =", g.get(2), "（应 = 药品）")
    print("  段名覆盖 id 数 = %d，最小 id = %s" % (len(g), after[:1]))

    # 换行归一：作者在表里混用「真换行 / 字面 \n / \r\n」三种写法，
    # 界面必须只见到真换行（否则浮窗里原样显示成「\n」两个字符，
    # 裸 \r 在 tk.Text 里还会渲染成怪字符）。归一键在 `clean_desc()`。
    print("\n== 换行归一（`clean_desc` 统一处理）")
    for kind in ("Items", "Weapons", "Armors"):
        m = D.item_map(kind)
        lit = [i for i in m if "\\n" in m[i][1]]
        cr = [i for i in m if "\r" in m[i][1]]
        print("  %-8s 字面 \\n %d（应 0），裸 \\r %d（应 0）"
              % (kind, len(lit), len(cr)))
        bad += len(lit) + len(cr)
    sm = D.skill_map()
    lit2 = [i for i in sm if "\\n" in sm[i][1]]
    cr2 = [i for i in sm if "\r" in sm[i][1]]
    print("  %-8s 字面 \\n %d（应 0），裸 \\r %d（应 0）"
          % ("Skills", len(lit2), len(cr2)))
    bad += len(lit2) + len(cr2)
    for i in (2, 240):
        if i in D.item_map("Items"):
            print("  样例 #%d：" % i)
            for ln in D.item_map("Items")[i][1].split("\n"):
                print("     |", ln)

    print("\n[汇总] 残留噪音 %d 条（应 0）" % bad)
    print("[探针跑完] 只读了 Data 表，没碰存档")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
