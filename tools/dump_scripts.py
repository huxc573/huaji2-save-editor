# -*- coding: utf-8 -*-
"""解密 Data\\Scripts.rvdata2 并把里面的 Ruby 脚本全部导出。

输出：
  tools/_dec/Data_Scripts.rvdata2.bin  解密后的明文（Marshal）
  tools/_scripts/<NNN>_<名字>.rb       每个脚本段
  tools/_scripts/_index.txt            脚本清单
  tools/_scripts/_hits.txt            关键字命中（密钥/存档相关）
"""
import os
import re
import subprocess
import sys
import zlib

sys.stdout.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GAME = os.path.normpath(os.path.join(ROOT, "..", "..", ".."))
HOST = os.path.join(ROOT, "src", "XJCodec32.exe")
DLL = os.path.join(GAME, "System", "main.dll")
DEC = os.path.join(HERE, "_dec")
OUTDIR = os.path.join(HERE, "_scripts")
KEY = sys.argv[1] if len(sys.argv) > 1 else "imoutogadaisuki"

sys.path.insert(0, os.path.join(ROOT, "src"))
import xj_marshal  # noqa: E402

os.makedirs(DEC, exist_ok=True)
os.makedirs(OUTDIR, exist_ok=True)

src = os.path.join(GAME, "Data", "Scripts.rvdata2")
plain = os.path.join(DEC, "Data_Scripts.rvdata2.bin")
if not os.path.exists(plain) or os.path.getsize(plain) == 0:
    p = subprocess.run([HOST, "decrypt", DLL, src, plain, KEY],
                       capture_output=True, cwd=GAME)
    print("decrypt rc=%d size=%d" % (p.returncode,
                                     os.path.getsize(plain) if os.path.exists(plain) else -1))
data = open(plain, "rb").read()

# 脚本表把每段代码存成 zlib 压缩串 —— 直接扫 zlib 头最稳，不依赖 Marshal 结构。
entries = []
i = 0
n = len(data)
while i < n - 1:
    if data[i] == 0x78 and data[i + 1] in (0x01, 0x5E, 0x9C, 0xDA):
        try:
            out = zlib.decompressobj().decompress(data[i:])
        except Exception:
            out = b""
        if len(out) > 20:
            sample = out[:400]
            good = sum(1 for b in sample
                       if 32 <= b < 127 or b in (9, 10, 13) or b >= 0x80)
            if good > len(sample) * 0.9:
                entries.append((i, out))
                i += 2
                continue
    i += 1
print("zlib 脚本段 = %d" % len(entries))

index = []
hits = []
PAT = re.compile(r"Win32API|decryption|encryption|qqeat|main\.dll|761205|"
                 r"imoutogadaisuki|save_data|load_data|Marshal|File\.open|"
                 r"key|hard_disk|md5|Game\.md5|save\.rvdata2", re.I)

for k, (off, code) in enumerate(entries):
    txt = code.decode("utf-8", "replace")
    if txt.count("\ufffd") > len(txt) * 0.05:
        txt = code.decode("gbk", "replace")
    fn = "%04d_%06X.rb" % (k, off)
    open(os.path.join(OUTDIR, fn), "w", encoding="utf-8").write(txt)
    index.append("%s  offset=0x%06X  %d 字节" % (fn, off, len(code)))
    for ln, line in enumerate(txt.splitlines(), 1):
        if PAT.search(line):
            hits.append("%s:%d: %s" % (fn, ln, line.rstrip()))

open(os.path.join(OUTDIR, "_index.txt"), "w", encoding="utf-8").write(
    "\n".join(index) + "\n")
open(os.path.join(OUTDIR, "_hits.txt"), "w", encoding="utf-8").write(
    "\n".join(hits) + "\n")
print("脚本段 = %d, 命中行 = %d" % (len(entries), len(hits)))
