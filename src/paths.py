# -*- coding: utf-8 -*-
"""环境定位：找到《画迹2：缘起凡尘》的游戏目录与关键文件。

游戏目录 = 含 `Game.exe` / `Game.ini` / `System\\main.dll` 的那一层。

查找顺序：
  1. 环境变量 XJ_GAME（显式指定，最优先）
  2. 从本文件所在目录向上/向下找
  3. 从当前工作目录向上/向下找
  4. 同级目录里所有含 Game.exe 的目录（huaji2 目录通常是 `【画迹2：缘起凡尘】 xxx`）

⚠ 路径里含 `【】[]` 和空格，**不要用 glob**（`[` 会被当字符类），
   一律用 os.listdir + os.path.join。
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                 # 仓库根目录


def is_game_dir(path):
    if not path or not os.path.isdir(path):
        return False
    for name in ("Game.exe", "Game.ini"):
        if not os.path.exists(os.path.join(path, name)):
            return False
    return os.path.isdir(os.path.join(path, "System")) or \
        os.path.isdir(os.path.join(path, "Data"))


def _walk_up(path, limit=6):
    cur = os.path.abspath(path)
    for _ in range(limit):
        if is_game_dir(cur):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return None


def _scan_children(path, depth=2):
    """在 path 下（有限深度）找游戏目录。"""
    if not os.path.isdir(path):
        return None
    stack = [(path, 0)]
    while stack:
        cur, d = stack.pop(0)
        if is_game_dir(cur):
            return cur
        if d >= depth:
            continue
        try:
            names = sorted(os.listdir(cur))
        except OSError:
            continue
        for n in names:
            p = os.path.join(cur, n)
            if os.path.isdir(p):
                stack.append((p, d + 1))
    return None


def find_game_dir(start=None):
    env = os.environ.get("XJ_GAME")
    if env and is_game_dir(env):
        return os.path.abspath(env)
    for base in (start, HERE, os.getcwd()):
        if not base:
            continue
        hit = _walk_up(base)
        if hit:
            return hit
        hit = _scan_children(base)
        if hit:
            return hit
    # 同级目录（`!Tools/Github/xxx` 这种布局下，游戏根在仓库的爷爷层）
    hit = _scan_children(os.path.dirname(ROOT))
    if hit:
        return hit
    return None


def main_dll(game_dir=None):
    game_dir = game_dir or find_game_dir()
    if not game_dir:
        return None
    p = os.path.join(game_dir, "System", "main.dll")
    return p if os.path.exists(p) else None


def save_path(game_dir=None):
    """默认存档：<游戏根>\\save.rvdata2（用户实测确认）。"""
    game_dir = game_dir or find_game_dir()
    if not game_dir:
        return None
    return os.path.join(game_dir, "save.rvdata2")


def autosave_dir(game_dir=None):
    game_dir = game_dir or find_game_dir()
    return os.path.join(game_dir, "AutoSave") if game_dir else None


def main():
    g = find_game_dir()
    print("game_dir  =", g)
    print("main.dll  =", main_dll(g))
    print("save      =", save_path(g))
    print("autosave  =", autosave_dir(g))
    print("python    =", sys.executable, "(%d bit)" % (64 if sys.maxsize > 2 ** 32 else 32))


if __name__ == "__main__":
    main()
