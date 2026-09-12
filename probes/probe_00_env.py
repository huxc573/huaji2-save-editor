# -*- coding: utf-8 -*-
"""环境自检：把结果写到 _env_out.txt，避免控制台编码/引号问题。"""
import glob
import os
import subprocess
import sys

LINES = []
LINES.append("python = %s (%d bit)" % (sys.executable, 64 if sys.maxsize > 2**32 else 32))
LINES.append("version = %s" % sys.version.replace("\n", " "))

for mod in ("capstone", "tkinter", "zlib", "struct"):
    try:
        m = __import__(mod)
        LINES.append("import %-10s OK  %s" % (mod, getattr(m, "__version__", "")))
    except Exception as e:
        LINES.append("import %-10s FAIL %s" % (mod, e))

# 找 .NET Framework 的 csc.exe
cands = []
for pat in (r"C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe",
            r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe",
            r"C:\Windows\Microsoft.NET\Framework\v3.5\csc.exe"):
    if os.path.exists(pat):
        cands.append(pat)
LINES.append("csc.exe = %s" % cands)

# 找 32 位 python
p32 = []
for pat in (r"C:\Python*\python.exe", r"D:\Dev\Python\**\python.exe",
            r"C:\Program Files (x86)\Python*\python.exe"):
    p32.extend(glob.glob(pat, recursive=True))
LINES.append("python 候选(前 20) = %s" % p32[:20])

for exe in ("where", "git", "py", "dotnet", "dumpbin"):
    try:
        out = subprocess.run([exe, "--version"], capture_output=True, timeout=10)
        LINES.append("run %-8s -> rc=%s %s" % (exe, out.returncode,
                                               out.stdout[:80].decode("utf-8", "replace")))
    except Exception as e:
        LINES.append("run %-8s -> FAIL %s" % (exe, e))

LINES.append("PATH = %s" % os.environ.get("PATH", "")[:600])

open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "_env_out.txt"),
     "w", encoding="utf-8").write("\n".join(LINES))
print("done")
