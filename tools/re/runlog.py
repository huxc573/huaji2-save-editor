# -*- coding: utf-8 -*-
"""跑一条命令，把它的输出**自己**写进 UTF-8 文件（不经过 PowerShell 重定向）。

为什么要它：PS 5.1 里 `命令 > 文件` 写出来的是 **UTF-16LE**，
再用普通工具读就成了乱码/读不出来（本工作区反复踩）。

用法：
    python tools/runlog.py <输出文件> <命令> [参数...]
"""
import subprocess
import sys

sys.stdout.reconfigure(errors="replace")

if len(sys.argv) < 3:
    print(__doc__)
    raise SystemExit(2)

out, cmd = sys.argv[1], sys.argv[2:]
p = subprocess.run(cmd, capture_output=True, text=True,
                   encoding="utf-8", errors="replace")
txt = (p.stdout or "") + (p.stderr or "")
with open(out, "w", encoding="utf-8") as f:
    f.write(txt)
print("rc=%d -> %s（%d 字）" % (p.returncode, out, len(txt)))
