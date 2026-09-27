# -*- coding: utf-8 -*-
"""临时探针：看看打包用的解释器有没有 tkinter / PyInstaller。"""
import sys

print("python:", sys.version.replace("\n", " "))
print("exe:", sys.executable)
try:
    import tkinter
    print("tkinter: OK，Tk", tkinter.TkVersion)
    r = tkinter.Tk()
    print("Tk() 能建窗口: OK")
    r.destroy()
except Exception as e:
    print("tkinter: 失败", repr(e))
try:
    import PyInstaller
    print("pyinstaller:", PyInstaller.__version__)
except Exception as e:
    print("pyinstaller: 没有", repr(e))
