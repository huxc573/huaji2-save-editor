# -*- coding: utf-8 -*-
"""存档管理：备份 / 删除备份 / 恢复 / 撤销上一次恢复。

存档放在**游戏根目录**（和 `save.rvdata2` 同级）下的子目录里，默认叫
`huxji2-save-editor`（用户指定；如果已经存在 `huaji2-save-editor` 就沿用那个）。

命名规矩（都能排序、看得懂）：

    save.2026-09-13_014530.rvdata2            手动备份
    save.2026-09-13_014530.auto.rvdata2       打开/保存前的自动备份
    save.2026-09-13_014530.before-restore.rvdata2
                                              恢复前自动留的那份（“恢复上一个”用它）

只做文件层面的复制/删除，不解析存档内容 —— 万一存档坏了，这里也能救。
"""
import os
import re
import shutil
import time

#: 备份目录名（优先用第一个，找不到就用第二个）
DIR_NAMES = ("huxji2-save-editor", "huaji2-save-editor")

STAMP_FMT = "%Y-%m-%d_%H%M%S"
KIND_AUTO = "auto"                    # 自动（打开/保存前）
KIND_MANUAL = "manual"                # 手动
KIND_BEFORE_RESTORE = "before-restore"   # 恢复前

SUFFIX = ".rvdata2"


def backup_dir(save_path, create=True, prefer=None):
    """备份目录 = 存档所在目录 / <DIR_NAMES>。

    `prefer` 可以显式指定目录名（设置里用得上）。
    """
    root = os.path.dirname(os.path.abspath(save_path))
    names = ([prefer] if prefer else []) + list(DIR_NAMES)
    for n in names:
        p = os.path.join(root, n)
        if os.path.isdir(p):
            return p
    p = os.path.join(root, names[0])
    if create:
        try:
            os.makedirs(p, exist_ok=True)
        except OSError:
            pass
    return p


def _stamp(t=None):
    return time.strftime(STAMP_FMT, t or time.localtime())


def parse_name(name):
    """`save.2026-09-13_014530.auto.rvdata2` → (来源名, 时间串, 类型)。

    解析不出来就返回 (name, "", "other")，宁可在列表里显示也不丢。
    """
    if not name.endswith(SUFFIX):
        return name, "", "other"
    body = name[:-len(SUFFIX)]
    m = re.match(r"^(?P<src>.+?)\.(?P<t>\d{4}-\d{2}-\d{2}_\d{6})"
                 r"(?:\.(?P<kind>[a-z\-]+))?$", body)
    if not m:
        return body, "", "other"
    return (m.group("src"), m.group("t"), m.group("kind") or KIND_MANUAL)


def backup(save_path, kind=KIND_MANUAL, note=""):
    """把存档复制进备份目录，返回备份文件路径。"""
    if not os.path.exists(save_path):
        raise IOError("找不到要备份的存档：%s" % save_path)
    d = backup_dir(save_path)
    src_name = os.path.basename(os.path.abspath(save_path))
    base = os.path.splitext(src_name)[0]
    stamp = _stamp()
    name = "%s.%s%s%s" % (base, stamp,
                          "" if kind == KIND_MANUAL else "." + kind, SUFFIX)
    dst = os.path.join(d, name)
    i = 1
    while os.path.exists(dst):          # 同一秒里连点两次也不覆盖
        i += 1
        dst = os.path.join(d, name[:-len(SUFFIX)] + "-%d%s" % (i, SUFFIX))
    shutil.copyfile(save_path, dst)
    if note:
        try:
            with open(dst + ".txt", "w", encoding="utf-8") as f:
                f.write(note)
        except OSError:
            pass
    return dst


def list_backups(save_path, prefer=None):
    """列出备份：[{name, path, size, mtime, stamp, kind, src, note}, ...]，新的在前。"""
    d = backup_dir(save_path, create=False, prefer=prefer)
    out = []
    if not os.path.isdir(d):
        return out
    want = os.path.splitext(os.path.basename(save_path))[0]
    for n in os.listdir(d):
        p = os.path.join(d, n)
        if not os.path.isfile(p) or not n.endswith(SUFFIX):
            continue
        src, stamp, kind = parse_name(n)
        st = os.stat(p)
        note = ""
        tf = p + ".txt"
        if os.path.exists(tf):
            try:
                note = open(tf, encoding="utf-8").read().strip()[:120]
            except OSError:
                note = ""
        out.append({"name": n, "path": p, "size": st.st_size,
                    "mtime": st.st_mtime, "stamp": stamp, "kind": kind,
                    "src": src, "note": note,
                    "is_this_file": src == want})
    out.sort(key=lambda r: (r["mtime"], r["name"]), reverse=True)
    return out


def remove(paths):
    """删掉若干备份（连 .txt 备注一起删）。返回删掉的个数。"""
    n = 0
    for p in paths:
        for f in (p, p + ".txt"):
            try:
                if os.path.exists(f):
                    os.remove(f)
                    if f == p:
                        n += 1
            except OSError:
                pass
    return n


def restore(backup_path, save_path, keep_current=True):
    """把某个备份恢复成存档。

    keep_current=True 时先把**现在的存档**存一份 `before-restore`，
    方便「恢复上一个」一键退回。返回 (恢复用的文件, 撤销用的文件|None)。
    """
    if not os.path.exists(backup_path):
        raise IOError("找不到备份：%s" % backup_path)
    undo = None
    if keep_current and os.path.exists(save_path):
        undo = backup(save_path, kind=KIND_BEFORE_RESTORE,
                      note="恢复 %s 之前的存档" % os.path.basename(backup_path))
    shutil.copyfile(backup_path, save_path)
    return backup_path, undo


def last_undo(save_path, prefer=None):
    """最近一次“恢复前”留下的备份（给「恢复上一个」用）。"""
    for r in list_backups(save_path, prefer=prefer):
        if r["kind"] == KIND_BEFORE_RESTORE:
            return r
    return None


def auto_backup_once(path, prefer=None, min_gap=90):
    """打开/保存存档前自动留一份，太频繁就跳过（同一份文件 90 秒内只留一次）。"""
    try:
        if not os.path.exists(path):
            return None
        for r in list_backups(path, prefer=prefer)[:5]:
            if r["kind"] == KIND_AUTO and time.time() - r["mtime"] < min_gap:
                return None
        return backup(path, kind=KIND_AUTO, note="打开/保存前自动备份")
    except Exception:
        return None
