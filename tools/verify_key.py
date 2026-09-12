# -*- coding: utf-8 -*-
"""用找到的密钥验证 main.dll 的加解密是否真的能还原游戏文件。

用法：python tools/verify_key.py [key]
输出：tools/_verify.txt
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
OUT = os.path.join(HERE, "_dec")
LOG = os.path.join(HERE, "_verify.txt")

sys.path.insert(0, os.path.join(ROOT, "src"))
import xj_marshal  # noqa: E402

KEY = sys.argv[1] if len(sys.argv) > 1 else "tiyan_version"

TARGETS = [
    "save.rvdata2",
    "AutoSave/save00.rvdata2",
    "AutoSave/save27.rvdata2",
    "Data/System.rvdata2",
    "Data/Actors.rvdata2",
    "Data/Scripts.rvdata2",
    "System/Game.md5",
]

L = ["密钥 = %r" % KEY, "state 文件存在 = %s" % os.path.exists(os.path.join(ROOT, "src", "xj_state.txt"))]

os.makedirs(OUT, exist_ok=True)
for rel in TARGETS:
    src = os.path.join(GAME, rel.replace("/", os.sep))
    if not os.path.exists(src):
        L.append("-- %-28s 不存在" % rel)
        continue
    dst = os.path.join(OUT, rel.replace("/", "_") + ".bin")
    if os.path.exists(dst):
        os.remove(dst)
    p = subprocess.run([HOST, "decrypt", DLL, src, dst, KEY],
                       capture_output=True, cwd=GAME)
    n = os.path.getsize(dst) if os.path.exists(dst) else -1
    head = open(dst, "rb").read(8).hex(" ") if n > 0 else "-"
    insize = os.path.getsize(src)
    tag = ""
    if n > 0:
        b = open(dst, "rb").read(2)
        if b == b"\x04\x08":
            tag = " Marshal 4.8 OK"
            try:
                streams = xj_marshal.parse_stream(open(dst, "rb").read())
                tag += " 解析成功 顶层对象=%d 根=%s" % (
                    len(streams), type(streams[0]["node"]).__name__)
            except Exception as e:
                tag += " 解析失败: %s" % e
        elif b == b"PK":
            tag = " ZIP"
    L.append("%-28s 密文=%-8d 明文=%-8d 头=%s%s" % (rel, insize, n, head, tag))

# 往返自检
tmp1 = os.path.join(OUT, "_rt.enc")
tmp2 = os.path.join(OUT, "_rt.dec")
payload = os.path.join(OUT, "_rt.src")
open(payload, "wb").write(bytes(range(256)) * 4)
subprocess.run([HOST, "encrypt", DLL, payload, tmp1, KEY], capture_output=True, cwd=GAME)
subprocess.run([HOST, "decrypt", DLL, tmp1, tmp2, KEY], capture_output=True, cwd=GAME)
ok = open(tmp2, "rb").read() == open(payload, "rb").read() if os.path.exists(tmp2) else False
L.append("往返自检(1024B) = %s" % ok)

# 错误密钥应当失败
bad = os.path.join(OUT, "_bad.bin")
if os.path.exists(bad):
    os.remove(bad)
subprocess.run([HOST, "decrypt", DLL, os.path.join(GAME, "Data/System.rvdata2"), bad, KEY + "x"],
               capture_output=True, cwd=GAME)
L.append("错误密钥输出 = %d 字节（期望 0）" % (os.path.getsize(bad) if os.path.exists(bad) else -1))

open(LOG, "w", encoding="utf-8").write("\n".join(L) + "\n")
print("done")
