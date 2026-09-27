# -*- coding: utf-8 -*-
r"""清道夫：删掉所有「可重跑生成」的中间产物，把工作区收拾回干净状态。

用法：
    python tools/cleanup.py               # 干活（默认不碰 dist/、不碰仓库外）
    python tools/cleanup.py --dry         # 只列清单，一个字节都不删
    python tools/cleanup.py --with-dist   # 连 dist/ 里上次打包的成品一起清
    python tools/cleanup.py --game        # 顺带清**游戏根**里我们留下的残留

清什么（全部在 .gitignore 覆盖范围内，删了随时能再跑出来）：
    __pycache__/                  各处字节码缓存
    build/  *.spec                PyInstaller 工作目录
    _tmp/                         仓库根的杂物暂存区
    tools/_*  tools/re/_*         脚本自己写的报告 / 日志
    probes/_*                     探针解出的游戏明文、内存镜像、爆破日志
    0  1  qqeat  xjy.11           main.dll 的 init_key 落的占位文件

不动的（这些是资产）：
    src/  tests/  docs/  csv/  probes/*.py  tools/**/*.py
    dist/                         上次打包的成品（除非 --with-dist）
    <游戏根>\save.rvdata2.bak.*   存档备份（--game 时也保留）
"""
import os
import shutil
import sys

sys.stdout.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
# <游戏根>\!Tools\Github\huaji2-save-editor  →  往上三级才是游戏根
GAME = os.path.normpath(os.path.join(ROOT, "..", "..", ".."))

DRY = "--dry" in sys.argv
WITH_DIST = "--with-dist" in sys.argv
WITH_GAME = "--game" in sys.argv

# 文件名以 _ 开头就该清掉的目录（只清文件，不动子目录）
JUNK_PREFIX_DIRS = ["tools", "tools/re", "probes", "tests"]
# 整个目录清掉
JUNK_DIRS = ["_tmp", "build"]
if WITH_DIST:
    JUNK_DIRS.append("dist")
# 点名要清的零散文件（相对 ROOT）
JUNK_FILES = ["tools/xj_state.txt", "selftest_result.txt", "error.log",
              "last.txt", "0", "1", "qqeat", "xjy.11"]
# 游戏根里我们留下的残留（只在 --game 时处理）
GAME_JUNK_SUFFIX = (".xj_plain", ".xj_new", ".plain", ".enc", ".bak")
GAME_JUNK_PREFIX = ("_xj", "xj_")
GAME_KEEP_PREFIX = "save.rvdata2.bak"     # 存档备份，永远保留

n = 0
freed = 0


def size_of(p):
    if os.path.isfile(p):
        return os.path.getsize(p)
    if os.path.isdir(p):
        return sum(os.path.getsize(os.path.join(b, f))
                   for b, _, fs in os.walk(p) for f in fs)
    return 0


def drop(p, label):
    global n, freed
    sz = size_of(p)
    print("  %s %-46s %9.1f KB" % ("[dry]" if DRY else "[del]", label, sz / 1024.0))
    if not DRY:
        try:
            if os.path.isdir(p):
                shutil.rmtree(p)
            else:
                os.remove(p)
        except OSError as e:
            print("       失败：%s" % e)
            return
    n += 1
    freed += sz


print("仓库根：%s" % ROOT)
print("游戏根：%s%s" % (GAME, "" if WITH_GAME else "   （没给 --game，仓库外一律不动）"))
print()

print("== 1. __pycache__ ==")
for base, dirs, _files in os.walk(ROOT):
    if os.sep + ".git" in base:
        continue
    for d in list(dirs):
        if d == "__pycache__":
            p = os.path.join(base, d)
            drop(p, os.path.relpath(p, ROOT))
            dirs.remove(d)

print("\n== 2. 构建 / 打包产物 ==")
for d in JUNK_DIRS:
    p = os.path.join(ROOT, d)
    if os.path.exists(p):
        drop(p, d)
for base, dirs, files in os.walk(ROOT):
    dirs[:] = [x for x in dirs if x not in (".git", "build", "dist", "_tmp")]
    for f in files:
        if f.endswith(".spec"):
            p = os.path.join(base, f)
            drop(p, os.path.relpath(p, ROOT))

print("\n== 3. 脚本写的本地报告 / 临时目录 ==")
for d in JUNK_PREFIX_DIRS:
    base = os.path.join(ROOT, *d.split("/"))
    if not os.path.isdir(base):
        continue
    for name in sorted(os.listdir(base)):
        if not name.startswith("_"):
            continue
        p = os.path.join(base, name)
        # 目录也清（tests 会造 tools\_smoke / tools\_gui / tools\_csvtest 这类）
        drop(p, os.path.relpath(p, ROOT))
for rel in JUNK_FILES:
    p = os.path.join(ROOT, rel)
    if os.path.exists(p):
        drop(p, rel)

if WITH_GAME:
    print("\n== 4. 游戏根的残留 ==")
    if os.path.isdir(GAME):
        for name in sorted(os.listdir(GAME)):
            p = os.path.join(GAME, name)
            if not os.path.isfile(p):
                continue
            if name.startswith(GAME_KEEP_PREFIX):
                print("  ·  保留 %s（存档备份）" % name)
                continue
            if name.endswith(GAME_JUNK_SUFFIX) or name.startswith(GAME_JUNK_PREFIX):
                drop(p, "游戏根\\" + name)
    else:
        print("  找不到游戏根，跳过")

print("\n共处理 %d 项，约 %.1f MB%s"
      % (n, freed / 1048576.0, "（--dry 预演，什么都没删）" if DRY else ""))
