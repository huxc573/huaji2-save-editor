# -*- coding: utf-8 -*-
"""存档管理（备份/恢复/删除/撤销）回归测试 —— 全程在临时目录里跑。

用法：python tools/test_backup.py
"""
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.stdout.reconfigure(errors="replace")

import xj_backup as B  # noqa: E402

OK = [0, 0]
WORK = os.path.join(HERE, "_bak")


def check(name, cond, extra=""):
    OK[0 if cond else 1] += 1
    print("  %s %-46s %s" % ("[OK]" if cond else "[NG]", name, extra))


def main():
    shutil.rmtree(WORK, ignore_errors=True)
    os.makedirs(WORK, exist_ok=True)
    save = os.path.join(WORK, "save.rvdata2")
    open(save, "wb").write(b"A" * 100)

    d = B.backup_dir(save)
    check("备份目录建在存档旁边", os.path.isdir(d)
          and os.path.dirname(d) == WORK, os.path.basename(d))
    check("目录名符合约定", os.path.basename(d) == B.DIR_NAMES[0],
          os.path.basename(d))

    check("一开始没有备份", B.list_backups(save) == [])

    p1 = B.backup(save, B.KIND_MANUAL)
    check("手动备份生成文件", os.path.exists(p1), os.path.basename(p1))
    r = B.list_backups(save)
    check("列表里有 1 份", len(r) == 1, "%r" % (r[0]["name"],))
    check("解析出时间与类型", r[0]["kind"] == "manual" and r[0]["stamp"],
          "%s / %s" % (r[0]["stamp"], r[0]["kind"]))
    check("内容与存档一致", open(p1, "rb").read() == b"A" * 100)

    # 改存档 → 自动备份 → 恢复
    open(save, "wb").write(b"B" * 120)
    time.sleep(0.01)
    p2 = B.backup(save, B.KIND_AUTO, note="测试自动备份")
    check("自动备份也能生成", os.path.exists(p2), os.path.basename(p2))
    r = B.list_backups(save)
    check("自动备份带备注", any(x["note"] == "测试自动备份" for x in r),
          "%r" % [x["note"] for x in r])
    check("新的排在前面", r[0]["path"] == p2, os.path.basename(r[0]["path"]))

    used, undo = B.restore(p1, save)
    check("恢复成功", open(save, "rb").read() == b"A" * 100)
    check("恢复前自动留了“恢复前”备份", undo and os.path.exists(undo),
          os.path.basename(undo or ""))
    check("能认出“恢复前”那份", B.last_undo(save)
          and B.last_undo(save)["path"] == undo)

    # 「恢复上一个」＝退回恢复之前
    B.restore(undo, save, keep_current=False)
    check("恢复上一个能退回", open(save, "rb").read() == b"B" * 120)

    # 频繁保存不会刷一堆自动备份
    n0 = len([x for x in B.list_backups(save) if x["kind"] == "auto"])
    B.auto_backup_once(save)
    n1 = len([x for x in B.list_backups(save) if x["kind"] == "auto"])
    check("90 秒内不重复留自动备份", n1 == n0, "%d -> %d" % (n0, n1))

    # 删除
    before = len(B.list_backups(save))
    n = B.remove([p1, p2])
    after = len(B.list_backups(save))
    check("删除备份生效", n == 2 and after == before - 2,
          "删了 %d，剩 %d" % (n, after))
    check("删掉的文件真的没了", not os.path.exists(p1) and not os.path.exists(p2))

    # 已经存在旧目录名时沿用旧目录
    shutil.rmtree(d, ignore_errors=True)
    old = os.path.join(WORK, B.DIR_NAMES[1])
    os.makedirs(old, exist_ok=True)
    check("有旧目录名时沿用旧的", B.backup_dir(save) == old,
          os.path.basename(B.backup_dir(save)))
    shutil.rmtree(WORK, ignore_errors=True)
    print("\n==== 通过 %d, 失败 %d ====" % (OK[0], OK[1]))
    return 1 if OK[1] else 0


if __name__ == "__main__":
    sys.exit(main())
