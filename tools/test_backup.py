# -*- coding: utf-8 -*-
"""存档管理（备份 / 恢复选中 / 恢复最新 / 删除 / 删除非最新）回归测试。

全程在临时目录里跑，一个真实文件都不碰。

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
    check("目录名就是 .huaji2-save-editor", B.DIR_NAME == ".huaji2-save-editor",
          B.DIR_NAME)

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

    n_before = len(B.list_backups(save))
    used = B.restore(p1, save)
    check("恢复成功", open(save, "rb").read() == b"A" * 100)
    check("恢复不再额外多留一份备份", len(B.list_backups(save)) == n_before,
          "%d -> %d" % (n_before, len(B.list_backups(save))))
    check("restore 返回用的那份", used == p1, os.path.basename(used))

    # 「恢复最新」＝回到最新那份备份（＝上一次修改之前）
    r = B.newest(save)
    check("newest 取到最新的一份", r and r["path"] == p2,
          os.path.basename(r["path"]) if r else "None")
    B.restore(r["path"], save)
    check("恢复最新能换回上一次修改前", open(save, "rb").read() == b"B" * 120)

    # 「删除非最新」：留最新一份 + **所有手动备份**（只清自动备份）
    B.backup(save, B.KIND_MANUAL)
    time.sleep(0.01)
    last = B.backup(save, B.KIND_MANUAL)
    n_all = len(B.list_backups(save))
    n_manual = len([x for x in B.list_backups(save) if x["kind"] == "manual"])
    kept, gone = B.keep_newest(save)
    check("删除非最新：留下的就是最新那份", kept and kept["path"] == last,
          os.path.basename(kept["path"]) if kept else "None")
    rows_left = B.list_backups(save)
    check("删除非最新：只删自动备份，手动全留",
          gone == n_all - n_manual
          and len(rows_left) == n_manual
          and all(x["kind"] == "manual" for x in rows_left),
          "删了 %d，剩 %d" % (gone, len(rows_left)))
    check("只剩手动备份时不再删", B.keep_newest(save)[1] == 0)

    # 备注编辑：写 → 改 → 清空（删掉 .txt）
    B.set_note(last, "这是备注")
    check("备注写进去了",
          B.list_backups(save)[0]["note"] == "这是备注",
          "%r" % B.list_backups(save)[0]["note"])
    B.set_note(last, "改过的备注")
    check("备注能改",
          B.list_backups(save)[0]["note"] == "改过的备注",
          "%r" % B.list_backups(save)[0]["note"])
    B.set_note(last, "")
    check("备注清空后 .txt 被删掉",
          not os.path.exists(last + ".txt")
          and B.list_backups(save)[0]["note"] == "",
          "note=%r" % B.list_backups(save)[0]["note"])

    # 频繁保存不会刷一堆自动备份
    B.backup(save, B.KIND_AUTO)          # 先保证有一份“刚做的”自动备份
    n0 = len([x for x in B.list_backups(save) if x["kind"] == "auto"])
    B.auto_backup_once(save)
    n1 = len([x for x in B.list_backups(save) if x["kind"] == "auto"])
    check("90 秒内不重复留自动备份", n1 == n0 and n0 >= 1, "%d -> %d" % (n0, n1))

    # 删除（重新造两份，免得受上一步「删除非最新」影响）
    pa = B.backup(save, B.KIND_MANUAL)
    time.sleep(0.01)
    pb = B.backup(save, B.KIND_MANUAL)
    check("同一秒连点两次也不会覆盖", pa != pb,
          "%s / %s" % (os.path.basename(pa), os.path.basename(pb)))
    before = len(B.list_backups(save))
    n = B.remove([pa, pb])
    after = len(B.list_backups(save))
    check("删除备份生效", n == 2 and after == before - 2,
          "删了 %d，剩 %d" % (n, after))
    check("删掉的文件真的没了", not os.path.exists(pa) and not os.path.exists(pb))

    # 老目录名（huxji2-/huaji2-）里的备份也要读得到、删得掉
    shutil.rmtree(d, ignore_errors=True)
    old = os.path.join(WORK, B.DIR_NAMES[1])
    os.makedirs(old, exist_ok=True)
    legacy = os.path.join(old, "save.2020-01-01_000000.rvdata2")
    open(legacy, "wb").write(b"L" * 60)
    rows = B.list_backups(save)
    check("老目录里的备份也能列出来", any(x["path"] == legacy for x in rows),
          "%d 份" % len(rows))
    check("新备份仍然写进新目录",
          os.path.basename(B.backup_dir(save)) == B.DIR_NAME,
          os.path.basename(B.backup_dir(save)))
    check("老目录里的备份也能删", B.remove([legacy]) == 1
          and not os.path.exists(legacy))

    shutil.rmtree(WORK, ignore_errors=True)
    print("\n==== 通过 %d, 失败 %d ====" % (OK[0], OK[1]))
    return 1 if OK[1] else 0


if __name__ == "__main__":
    sys.exit(main())
