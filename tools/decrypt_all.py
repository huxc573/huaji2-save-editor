# -*- coding: utf-8 -*-
"""按正确的密钥把游戏各文件解密到 tools/_plain/ 下，方便后续分析/测试。

密钥（逆向出来的）：
  Data\\*.rvdata2 数据库 / System\\Game.md5  ->  761205
  Data\\Scripts.rvdata2（脚本）              ->  imoutogadaisuki
  存档 save.rvdata2 / AutoSave\\*.rvdata2     ->  tiyan_version

用法：python tools/decrypt_all.py
"""
import os
import subprocess
import sys

sys.stdout.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GAME = os.path.normpath(os.path.join(ROOT, "..", "..", ".."))
HOST = os.path.join(ROOT, "src", "XJCodec32.exe")
DLL = os.path.join(GAME, "System", "main.dll")
OUT = os.path.join(HERE, "_plain")

KEYS = {
    "761205": ["Data/System.rvdata2", "Data/Actors.rvdata2", "Data/Classes.rvdata2",
               "Data/Skills.rvdata2", "Data/Items.rvdata2", "Data/Weapons.rvdata2",
               "Data/Armors.rvdata2", "Data/Enemies.rvdata2", "Data/Troops.rvdata2",
               "Data/States.rvdata2", "Data/Animations.rvdata2", "Data/Tilesets.rvdata2",
               "Data/CommonEvents.rvdata2", "Data/Map001.rvdata2",
               "System/Game.md5"],
    "imoutogadaisuki": ["Data/Scripts.rvdata2"],
    "tiyan_version": ["save.rvdata2", "AutoSave/save00.rvdata2"],
}

os.makedirs(OUT, exist_ok=True)
L = []
for key, files in KEYS.items():
    for rel in files:
        src = os.path.join(GAME, rel.replace("/", os.sep))
        if not os.path.exists(src):
            L.append("%-30s 不存在" % rel)
            continue
        dst = os.path.join(OUT, rel.replace("/", "_") + ".bin")
        if os.path.exists(dst):
            os.remove(dst)
        p = subprocess.run([HOST, "decrypt", DLL, src, dst, key],
                           capture_output=True, cwd=GAME)
        n = os.path.getsize(dst) if os.path.exists(dst) else -1
        head = open(dst, "rb").read(6).hex(" ") if n > 0 else "-"
        L.append("%-30s key=%-16s 密文=%-8d 明文=%-8d 头=%s" %
                 (rel, key, os.path.getsize(src), n, head))
        print(L[-1])
open(os.path.join(HERE, "_plain_index.txt"), "w", encoding="utf-8").write(
    "\n".join(L) + "\n")
