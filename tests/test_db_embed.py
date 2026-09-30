# -*- coding: utf-8 -*-
"""内置名字表（`src/tables/db_table.py`）回归测试。

要证两件事：

  A) **内置表本身是对的** —— 结构齐、抽样对，而且跟**当前游戏数据一致**
     （直接调 `tools/gen_db_table.py` 的 `collect()` 对比，不额外 spawn 进程，
      等价于 `python tools/gen_db_table.py --check`）。

  B) **兜底链是通的** —— 把「读游戏目录」那一步打断后（模拟别人的机器：工具没放在
     游戏目录里 / 版本不符 / 内测版解密被授权链拦住），名字 / 说明 / 天生技能 /
     模板行全部退回内置表；而且**解除打断之后必须回到游戏目录** ——
     读得到游戏目录时永远优先用它，否则游戏更新后名字会一直停在旧版快照上。

用法：python tests/test_db_embed.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.stdout.reconfigure(errors="replace")

import babies as B  # noqa: E402
import datatables  # noqa: E402
import game as G  # noqa: E402
import marshal_ruby as M  # noqa: E402
import paths  # noqa: E402
import tables.db_table as T  # noqa: E402

OK = 0
NG = 0


def check(cond, msg):
    global OK, NG
    if cond:
        OK += 1
        print("  [OK] %s" % msg)
    else:
        NG += 1
        print("  [NG] %s" % msg)


def check_eq(got, want, msg):
    check(got == want, "%s（得到 %r）" % (msg, got) if got != want
          else "%s = %r" % (msg, got))


# --------------------------------------------------------------------------
# 打断「读游戏目录」
# --------------------------------------------------------------------------
class BrokenGame(object):
    """上下文管理器：让 datatables 读不到任何 Data 表，退出时原样恢复。"""

    def __enter__(self):
        self._save = datatables._plain_path

        def boom(key, game_dir):
            raise datatables.DBError("（测试）模拟读不到 Data\\%s.rvdata2" % key)

        datatables._plain_path = boom
        datatables._cache.clear()
        datatables._SOURCE.clear()
        return self

    def __exit__(self, *a):
        datatables._plain_path = self._save
        datatables._cache.clear()
        datatables._SOURCE.clear()
        return False


class FakeEd(object):
    """只实现 `GameEditor.actor_class_learnings` 用到的那一点点。"""

    _cls_learn_cache = {}

    def actor_level(self, actor):
        return 999          # 足够高：@learnings 里所有条目都算"等级已经够"


def fake_actor(class_id):
    """够 `actor_class_learnings` 用就行：只带 @class_id / @level。

    ⚠ `ObjNode(cls, start=0, end=0)` —— 实例变量要自己 append（没有 ivars 形参）。
    """
    a = M.ObjNode("Game_Actor")
    a.ivars.append(("@class_id", M.IntNode(int(class_id))))
    a.ivars.append(("@level", M.IntNode(999)))
    return a


class _FakeG(object):
    doc = None
    sv = None


def main():
    game = paths.find_game_dir()
    print("游戏目录 = %s" % (game or "（没找到）"))

    # ======================================================================
    print("\n== A. 内置表本身 ==")
    # ======================================================================
    check(sorted(T.NAMES) == sorted(T.DESCS) ==
          ["Actors", "Armors", "Classes", "Items", "Skills", "Weapons"],
          "NAMES / DESCS 覆盖 6 张表")
    check_eq(T.names("Skills").get(9), "牛刀小试", "技能 9 的名字")
    check_eq(T.names("Skills").get(1), "攻击", "技能 1 的名字")
    check(bool(T.descs("Skills").get(9)), "技能 9 有说明")
    check(len(T.learnings(1)) >= 1, "职业 1 有天生技能（%d 条）"
          % len(T.learnings(1)))
    check(T.learnings(999999) == [], "不存在的职业 → 空列表（不抛异常）")
    check(T.names("不存在的表") == {}, "不存在的表 → 空字典")
    check("\\" not in T.GENERATED_FROM and "/" not in T.GENERATED_FROM,
          "GENERATED_FROM 只记目录名（%r），换盘符不该让 --check 变红"
          % T.GENERATED_FROM)
    for key in T.NAMES:
        check(bool(T.names(key)), "%s 的名字表非空（%d 条）"
              % (key, len(T.names(key))))

    if not game:
        print("\n[SKIP] 没找到游戏目录，跳过「与游戏数据一致」的比对")
    else:
        import gen_db_table
        n2, d2, l2 = gen_db_table.collect(game)
        drift = []
        for key in T.NAMES:
            if {k: v for k, v in n2[key].items() if v} != T.names(key):
                drift.append("%s 名字" % key)
            if {k: v for k, v in d2[key].items() if v} != T.descs(key):
                drift.append("%s 说明" % key)
        if {k: [tuple(p) for p in v] for k, v in l2.items()} != \
                dict((k, T.learnings(k)) for k in l2):
            drift.append("Classes 天生技能")
        check(not drift,
              "内置表与当前游戏数据一致（不一致：%s；跑 tools/gen_db_table.py "
              "重新生成）" % ("、".join(drift) if drift else "无"))

    # ======================================================================
    print("\n== B. 兜底链：读得到游戏目录时（不许被内置表抢走） ==")
    # ======================================================================
    nm = datatables.name_map("Skills")
    check_eq(datatables.names_source("Skills"), "游戏目录",
             "名字来源 = 游戏目录")
    check({k: v for k, v in nm.items() if v} == T.names("Skills"),
          "读得到游戏目录时的名字与内置快照内容一致")
    check(bool(datatables.desc_map("Skills").get(9)),
          "desc_map 拿得到技能 9 的说明")
    check(bool(datatables.builtin_rows("Items")), "builtin_rows('Items') 非空")

    # ======================================================================
    print("\n== C. 兜底链：读不到游戏目录时 ==")
    # ======================================================================
    with BrokenGame():
        datatables.name_map("Skills")        # 先触发一次，让 _SOURCE 落下来
        check_eq(datatables.names_source("Skills"), "内置表", "名字来源 = 内置表")
        check(datatables.name_map("Skills") == T.names("Skills"),
              "技能名字整表退回内置表（%d 条）"
              % len(datatables.name_map("Skills")))
        check(datatables.name_map("Items") == T.names("Items"),
              "物品名字整表退回内置表")
        d5 = datatables.desc_map("Skills")
        check_eq(d5.get(9), (T.names("Skills").get(9), T.descs("Skills").get(9)),
                 "技能 9 的（名字, 说明）")
        check(datatables.class_learnings(1) == sorted(set(T.learnings(1))),
              "职业 1 的天生技能退回内置表")
        check(datatables.builtin_rows("Items") ==
              [(i, T.names("Items").get(i) or ("#%d" % i), T.descs("Items").get(i, ""))
               for i in sorted(set(T.names("Items")) | set(T.descs("Items")))],
              "内置模板行格式正确（id / 名称 / 说明）")

        # —— 消费方（界面后面挂的东西）在无 Data 时也不能变空
        ed = FakeEd()
        ids = G.GameEditor.actor_class_learnings(ed, fake_actor(1))
        check(ids == [sid for _lv, sid in T.learnings(1)],
              "GameEditor.actor_class_learnings 仍给得出天生技能（%r）" % (ids,))

        b = B.Babies(_FakeG())
        check(b.class_skill_ids(1) ==
              sorted(set(sid for _lv, sid in T.learnings(1))),
              "Babies.class_skill_ids 仍给得出职业技能")
        check(bool(b.valid_skill_ids()), "Babies.valid_skill_ids 非空")
        first_id = sorted(T.names("Actors"))[0]
        check_eq(b.name_of(first_id), T.names("Actors")[first_id],
                 "Babies.name_of(%d) 退回内置表" % first_id)
        check(bool(b.known_names()), "Babies.known_names 非空")

        # 数据表预览的 CSV 行是"整份数据"，内置表没这个能力 —— 保持报错降级，
        # 但**必须只是抛由调用方接住的异常**，不能是别的什么。
        try:
            datatables.rows("Skills")
            check(False, "rows() 在无 Data 时应抛 DBError（而不是静默给假数据）")
        except datatables.DBError:
            check(True, "rows() 明确抛 DBError，由调用方降级")
        except Exception as e:
            check(False, "rows() 抛的是 %s（应是 DBError）" % type(e).__name__)

    # ======================================================================
    print("\n== D. 解除打断：不能留下污染 ==")
    # ======================================================================
    nm2 = datatables.name_map("Skills")
    check_eq(datatables.names_source("Skills"), "游戏目录",
             "恢复后名字来源回到游戏目录")
    check(nm2 == nm, "恢复后的名字与打断前完全一样")

    print("\n==== 通过 %d, 失败 %d ====" % (OK, NG))
    return 1 if NG else 0


if __name__ == "__main__":
    sys.exit(main())
