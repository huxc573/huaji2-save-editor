# -*- coding: utf-8 -*-
"""一次性：跳过 32 位宿主重编，只跑「准备 dist → PyInstaller → 自检」。

（tools/_* 被 .gitignore 忽略，跑完可删）
原因：build.build_host() 会先 os.remove(src/native/XJCodec32.exe) 再重编，
      而 native/codec32.cs 这轮没动过，没必要动仓库里被跟踪的那个 exe。
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.stdout.reconfigure(errors="replace")
import importlib.util

spec = importlib.util.spec_from_file_location(
    "xjbuild", os.path.join(HERE, "build.py"))
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)

host = os.path.join(b.SRC, "native", b.HOST_NAME)
if not os.path.exists(host):
    sys.exit("缺宿主：%s" % host)
b.log("宿主用现成的：%s（%d 字节）" % (host, os.path.getsize(host)))

b.prepare(host)
py, ver = b.find_pyinstaller_python()
if not py:
    sys.exit("[NG] 没找到装了 PyInstaller 的解释器")
b.log("用 %s（PyInstaller %s）打包" % (py, ver))
exe = b.build_exe(py)
b.log("")
b.log("发行目录 %s：" % b.DIST)
for n in sorted(os.listdir(b.DIST)):
    p = os.path.join(b.DIST, n)
    if os.path.isfile(p):
        b.log("   %-40s %.2f MB" % (n, os.path.getsize(p) / 1048576.0))
    else:
        b.log("   %-40s <目录>" % (n + "/"))
sys.exit(b.selftest(exe))
