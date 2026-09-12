# -*- coding: utf-8 -*-
"""编译 32 位编解码宿主 src/XJCodec32.exe。

只依赖 .NET Framework 的 csc.exe（Windows 自带），不需要额外安装任何东西。

用法：
    python tools/build_host.py            # 编译 src/XJCodec32.exe
    python tools/build_host.py --check    # 只检查能否编译
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "src", "xj_codec32.cs")
OUT = os.path.join(ROOT, "src", "XJCodec32.exe")

CSC_CANDIDATES = [
    r"C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe",
    r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe",
    r"C:\Windows\Microsoft.NET\Framework\v3.5\csc.exe",
]


def find_csc():
    for p in CSC_CANDIDATES:
        if os.path.exists(p):
            return p
    raise SystemExit("[NG] 找不到 csc.exe，请确认已安装 .NET Framework 4.x")


def main():
    csc = find_csc()
    print("[OK] csc = %s" % csc)
    cmd = [csc, "/nologo", "/platform:x86", "/optimize+", "/out:" + OUT, SRC]
    print("[--] %s" % " ".join(cmd))
    p = subprocess.run(cmd, capture_output=True)
    out = (p.stdout or b"").decode("utf-8", "replace")
    err = (p.stderr or b"").decode("utf-8", "replace")
    if out.strip():
        print(out.strip())
    if err.strip():
        print(err.strip())
    if p.returncode != 0 or not os.path.exists(OUT):
        raise SystemExit("[NG] 编译失败 rc=%s" % p.returncode)
    print("[OK] 生成 %s (%d 字节)" % (OUT, os.path.getsize(OUT)))


if __name__ == "__main__":
    main()
