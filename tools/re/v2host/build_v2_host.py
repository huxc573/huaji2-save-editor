# -*- coding: utf-8 -*-
"""经计划任务编译 XJCodec32v2.exe（32 位）。

流程：生成 build.bat（CRLF、纯 ASCII）→ schtasks 建/跑 → 轮询 build.log 结果。
"""
import os
import subprocess
import sys
import time

sys.stdout.reconfigure(errors="replace")

T = r"C:\Users\a\AppData\Local\Temp\xjv22"
BAT = os.path.join(T, "build.bat")
LOG = os.path.join(T, "build.log")

lines = [
    "@echo off",
    "setlocal",
    'cd /d "%~dp0"',
    r'set "CSC=%WINDIR%\Microsoft.NET\Framework\v4.0.30319\csc.exe"',
    r'if not exist "%CSC%" set "CSC=%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe"',
    r'if not exist "%CSC%" goto nocsc',
    'if exist "XJCodec32v2.new.exe" del /q "XJCodec32v2.new.exe"',
    r'"%CSC%" /nologo /noconfig /optimize+ /platform:x86 /out:XJCodec32v2.new.exe'
    r' codec32v2.cs > build.log 2>&1',
    "if errorlevel 1 goto failed",
    'if not exist "XJCodec32v2.new.exe" goto failed',
    'move /y "XJCodec32v2.new.exe" "XJCodec32v2.exe" >> build.log 2>&1',
    "if errorlevel 1 goto locked",
    "echo BUILD_OK>> build.log",
    "exit /b 0",
    ":locked",
    "echo BUILD_FAILED_EXE_LOCKED>> build.log",
    "exit /b 2",
    ":failed",
    "echo BUILD_FAILED>> build.log",
    "exit /b 1",
    ":nocsc",
    "echo BUILD_FAILED_NO_CSC> build.log",
    "exit /b 1",
]
with open(BAT, "wb") as f:
    f.write(("\r\n".join(lines) + "\r\n").encode("ascii"))

for f in (LOG, os.path.join(T, "XJCodec32v2.exe")):
    if os.path.exists(f):
        os.remove(f)

def sch(*a):
    p = subprocess.run(["schtasks"] + list(a), capture_output=True)
    out = (p.stdout or b"").decode("gbk", "replace")
    err = (p.stderr or b"").decode("gbk", "replace")
    return (out + err).strip()

print(sch("/create", "/tn", "XJ_BuildCodecV2",
          "/tr", BAT, "/sc", "once", "/st", "23:59",
          "/sd", "2099/12/31", "/f"))
print(sch("/run", "/tn", "XJ_BuildCodecV2"))

ok = False
for _ in range(40):
    time.sleep(2)
    if os.path.exists(LOG):
        txt = open(LOG, "rb").read().decode("gbk", "replace")
        if "BUILD_OK" in txt:
            ok = True
            break
        if "BUILD_FAILED" in txt:
            print(txt)
            sys.exit(1)
exe = os.path.join(T, "XJCodec32v2.exe")
print("结果:", "BUILD_OK" if ok else "超时")
print("exe:", exe, os.path.getsize(exe) if os.path.exists(exe) else "缺失")
if not ok and os.path.exists(LOG):
    print(open(LOG, "rb").read().decode("gbk", "replace"))
