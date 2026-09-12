# -*- coding: utf-8 -*-
"""在运行中的《画迹2》进程里挂钩 main.dll 的 encryption_file / decryption_file，
把每次调用的三个参数（输入、输出、**密钥**）记录下来。

原理：
  Game.ini 里的 Scripts 指向 Data\\main.rvdata2，那是一小段明文脚本，
  内容是 `Win32API.new('System/main','qqeat','v','v').call` —— 也就是说
  **Game.exe / RGSS301.dll 都不静态导入 main.dll**，是 Ruby 在运行时
  用 LoadLibrary 把 System\\main.dll 拉起来的。所以我们可以：

    1. 以管理员身份挂起启动 Game.exe；
    2. 轮询模块列表，等 System\\main.dll 出现；
    3. 在目标进程里 VirtualAllocEx 一块 RWX 内存当"代码洞"，
       写入「把参数存到缓冲区再跳回原函数」的桩；
    4. 把导出函数开头 5 字节改成 jmp 到桩；
    5. 轮询缓冲区，把参数（含密钥字符串）读出来写进日志。

用法（会自动请求管理员权限）：
    python tools/hook_key.py [最长等待秒数]

日志：tools/_hook.txt
"""
import ctypes
import json
import os
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(errors="replace")

from ctypes import wintypes  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GAME = os.path.normpath(os.path.join(ROOT, "..", "..", ".."))
HOST = os.path.join(ROOT, "src", "XJCodec32.exe")
DLL = os.path.join(GAME, "System", "main.dll")
LOG = os.path.join(HERE, "_hook.txt")
EXE = os.path.join(GAME, "Game.exe")

WAIT_EXIT = "--wait-exit" in sys.argv
TIMEOUT = 300
for a in sys.argv[1:]:
    if a.isdigit():
        TIMEOUT = int(a)

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
user32 = ctypes.WinDLL("user32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)
psapi = ctypes.WinDLL("psapi", use_last_error=True)

TH32CS_SNAPMODULE = 0x00000008
TH32CS_SNAPMODULE32 = 0x00000010
CREATE_SUSPENDED = 0x00000004
PAGE_EXECUTE_READWRITE = 0x40
MEM_COMMIT = 0x1000
MEM_RESERVE = 0x2000
INFINITE = 0xFFFFFFFF
STILL_ACTIVE = 259


class PROCESSENTRY32(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
                ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD),
                ("pcPriClassBase", ctypes.c_long),
                ("dwFlags", wintypes.DWORD), ("szExeFile", ctypes.c_char * 260)]
    # 用 MODULEENTRY32 的名字区分
    pass


class MODULEENTRY32(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD), ("th32ModuleID", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD),
                ("GlblcntUsage", wintypes.DWORD),
                ("ProccntUsage", wintypes.DWORD),
                ("modBaseAddr", ctypes.POINTER(ctypes.c_byte)),
                ("modBaseSize", wintypes.DWORD),
                ("hModule", wintypes.HMODULE),
                ("szModule", ctypes.c_char * 256),
                ("szExePath", ctypes.c_char * 260)]


class STARTUPINFO(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("lpReserved", wintypes.LPWSTR),
                ("lpDesktop", wintypes.LPWSTR), ("lpTitle", wintypes.LPWSTR),
                ("dwX", wintypes.DWORD), ("dwY", wintypes.DWORD),
                ("dwXSize", wintypes.DWORD), ("dwYSize", wintypes.DWORD),
                ("dwXCountChars", wintypes.DWORD),
                ("dwYCountChars", wintypes.DWORD),
                ("dwFillAttribute", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD), ("wShowWindow", wintypes.WORD),
                ("cbReserved2", wintypes.WORD),
                ("lpReserved2", ctypes.POINTER(ctypes.c_byte)),
                ("hStdInput", wintypes.HANDLE), ("hStdOutput", wintypes.HANDLE),
                ("hStdError", wintypes.HANDLE)]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [("hProcess", wintypes.HANDLE), ("hThread", wintypes.HANDLE),
                ("dwProcessId", wintypes.DWORD), ("dwThreadId", wintypes.DWORD)]


def is_admin():
    return bool(shell32.IsUserAnAdmin())


# ---- 声明原型，避免 64 位 Python 下指针被截断 ----
LPVOID = ctypes.c_void_p
SIZE_T = ctypes.c_size_t
k32.VirtualAllocEx.restype = LPVOID
k32.VirtualAllocEx.argtypes = [wintypes.HANDLE, LPVOID, SIZE_T, wintypes.DWORD,
                               wintypes.DWORD]
k32.VirtualProtectEx.restype = wintypes.BOOL
k32.VirtualProtectEx.argtypes = [wintypes.HANDLE, LPVOID, SIZE_T,
                                 wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
k32.ReadProcessMemory.restype = wintypes.BOOL
k32.ReadProcessMemory.argtypes = [wintypes.HANDLE, LPVOID, LPVOID, SIZE_T,
                                  ctypes.POINTER(SIZE_T)]
k32.WriteProcessMemory.restype = wintypes.BOOL
k32.WriteProcessMemory.argtypes = [wintypes.HANDLE, LPVOID, LPVOID, SIZE_T,
                                   ctypes.POINTER(SIZE_T)]
k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
k32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
k32.CreateProcessW.restype = wintypes.BOOL
k32.CreateProcessW.argtypes = [LPVOID, wintypes.LPCWSTR, LPVOID, LPVOID,
                               wintypes.BOOL, wintypes.DWORD, LPVOID,
                               wintypes.LPCWSTR, LPVOID, LPVOID]
k32.ResumeThread.restype = wintypes.DWORD
k32.ResumeThread.argtypes = [wintypes.HANDLE]
k32.GetExitCodeProcess.restype = wintypes.BOOL
k32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
k32.Module32First.restype = wintypes.BOOL
k32.Module32First.argtypes = [wintypes.HANDLE, LPVOID]
k32.Module32Next.restype = wintypes.BOOL
k32.Module32Next.argtypes = [wintypes.HANDLE, LPVOID]


def elevate():
    params = " ".join(['"%s"' % os.path.abspath(__file__)] +
                      [a for a in sys.argv[1:]])
    r = shell32.ShellExecuteW(None, "runas", sys.executable,
                              params, HERE, 1)
    print("已请求管理员权限（UAC 请点“是”），结果码=%d，进度看 %s" % (r, LOG))
    sys.exit(0)


def export_rvas():
    """用 32 位宿主问出导出函数的 RVA。"""
    p = subprocess.run([HOST, "info", DLL], capture_output=True, cwd=GAME)
    txt = (p.stdout or b"").decode("utf-8", "replace")
    base = None
    m = re.search(r"base=0x([0-9A-Fa-f]+)", txt)
    if m:
        base = int(m.group(1), 16)
    out = {}
    for line in txt.splitlines():
        mm = re.match(r"\[INFO\] (\S+)\s+0x([0-9A-Fa-f]{8})", line)
        if mm and base is not None:
            out[mm.group(1)] = int(mm.group(2), 16) - base
    return out


def find_module(pid, name):
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, pid)
    if snap == -1:
        return None
    try:
        me = MODULEENTRY32()
        me.dwSize = ctypes.sizeof(MODULEENTRY32)
        if not k32.Module32First(snap, ctypes.byref(me)):
            return None
        while True:
            if me.szModule.decode("ascii", "replace").lower() == name.lower():
                return (ctypes.cast(me.modBaseAddr, ctypes.c_void_p).value,
                        me.modBaseSize)
            if not k32.Module32Next(snap, ctypes.byref(me)):
                return None
    finally:
        k32.CloseHandle(snap)


def build_stub(buff_addr, stolen, back_addr):
    """构造代码洞桩。"""
    code = bytearray()
    code += b"\x60"                                     # pushad
    code += b"\x8B\x44\x24\x24"                         # mov eax,[esp+36]  arg1
    code += b"\x8B\x54\x24\x28"                         # mov edx,[esp+40]  arg2
    code += b"\x8B\x4C\x24\x2C"                         # mov ecx,[esp+44]  arg3
    code += b"\xA3" + buff_addr.to_bytes(4, "little")   # mov [buff],eax
    code += b"\x89\x15" + (buff_addr + 4).to_bytes(4, "little")   # mov [buff+4],edx
    code += b"\x89\x0D" + (buff_addr + 8).to_bytes(4, "little")   # mov [buff+8],ecx
    code += b"\x61"                                     # popad
    code += stolen                                     # 原函数被覆盖的字节
    rel = back_addr - (buff_addr + len(code) + 5)
    code += b"\xE9" + (rel & 0xFFFFFFFF).to_bytes(4, "little")
    return bytes(code)


def main():
    if not is_admin():
        elevate()
        return
    rvas = export_rvas()
    log = ["导出 RVA: " + json.dumps({k: "0x%X" % v for k, v in rvas.items()})]

    si = STARTUPINFO()
    si.cb = ctypes.sizeof(STARTUPINFO)
    pi = PROCESS_INFORMATION()
    cmd = '"%s"' % EXE
    ok = k32.CreateProcessW(None, ctypes.c_wchar_p(cmd), None, None, False,
                            CREATE_SUSPENDED, None,
                            ctypes.c_wchar_p(GAME), ctypes.byref(si),
                            ctypes.byref(pi))
    if not ok:
        log.append("CreateProcess 失败 err=%d" % ctypes.get_last_error())
        open(LOG, "w", encoding="utf-8").write("\n".join(log) + "\n")
        print(log[-1])
        return
    pid = pi.dwProcessId
    hp = pi.hProcess
    log.append("已挂起启动 Game.exe pid=%d" % pid)

    mod = None
    t0 = time.time()
    while time.time() - t0 < 60:
        mod = find_module(pid, "main.dll")
        if mod:
            break
        time.sleep(0.005)
    if not mod:
        log.append("等不到 main.dll，放弃")
        k32.TerminateProcess(hp, 0)
        open(LOG, "w", encoding="utf-8").write("\n".join(log) + "\n")
        print("等不到 main.dll")
        return
    base, msize = mod
    log.append("main.dll 基址=0x%08X 大小=0x%X" % (base, msize))

    # 分配代码洞
    cave = k32.VirtualAllocEx(hp, None, 0x1000, MEM_COMMIT | MEM_RESERVE,
                              PAGE_EXECUTE_READWRITE)
    if not cave:
        log.append("VirtualAllocEx 失败 err=%d" % ctypes.get_last_error())
        k32.TerminateProcess(hp, 0)
        open(LOG, "w", encoding="utf-8").write("\n".join(log) + "\n")
        print(log[-1])
        return
    buff = cave + 0x800
    log.append("代码洞=0x%08X 缓冲=0x%08X" % (cave, buff))

    hooked = []
    for fname in ("decryption_file", "encryption_file"):
        rva = rvas.get(fname)
        if rva is None:
            log.append("%s: 没有 RVA" % fname)
            continue
        addr = base + rva
        old = ctypes.create_string_buffer(5)
        nread = ctypes.c_size_t(0)
        if not k32.ReadProcessMemory(hp, ctypes.c_void_p(addr), old, 5,
                                     ctypes.byref(nread)):
            log.append("%s: ReadProcessMemory 失败" % fname)
            continue
        stub = build_stub(buff, old.raw, addr + 5)
        k32.WriteProcessMemory(hp, ctypes.c_void_p(cave), stub, len(stub),
                               ctypes.byref(nread))
        # 改写入口
        oldprot = wintypes.DWORD()
        k32.VirtualProtectEx(hp, ctypes.c_void_p(addr), 5,
                             PAGE_EXECUTE_READWRITE, ctypes.byref(oldprot))
        rel = cave - (addr + 5)
        patch = b"\xE9" + (rel & 0xFFFFFFFF).to_bytes(4, "little")
        w = k32.WriteProcessMemory(hp, ctypes.c_void_p(addr), patch, 5,
                                   ctypes.byref(nread))
        log.append("挂钩 %s @0x%08X -> 洞 0x%08X write=%s 原字节=%s"
                   % (fname, addr, cave, bool(w), old.raw.hex(" ")))
        hooked.append((fname, addr, old.raw))

    open(LOG, "w", encoding="utf-8").write("\n".join(log) + "\n")
    for line in log:
        print(line)
    if not hooked:
        k32.TerminateProcess(hp, 0)
        return

    k32.ResumeThread(pi.hThread)
    print("已恢复运行。请在游戏里【打开读档界面】或【存档】一次；"
          "最多等 %d 秒。" % TIMEOUT)

    seen = set()
    t0 = time.time()
    buf = ctypes.create_string_buffer(12)
    nread = ctypes.c_size_t(0)
    while time.time() - t0 < TIMEOUT:
        try:
            if k32.ReadProcessMemory(hp, ctypes.c_void_p(buff), buf, 12,
                                     ctypes.byref(nread)):
                vals = [int.from_bytes(buf.raw[i * 4:i * 4 + 4], "little")
                        for i in range(3)]
                if any(vals):
                    strs = []
                    for v in vals:
                        if not v:
                            strs.append(None)
                            continue
                        raw = ctypes.create_string_buffer(512)
                        if k32.ReadProcessMemory(hp, ctypes.c_void_p(v), raw,
                                                 512, ctypes.byref(nread)):
                            strs.append(raw.raw.split(b"\0")[0].decode(
                                "utf-8", "replace"))
                        else:
                            strs.append("<读不到>")
                    key = repr(strs)
                    if key not in seen:
                        seen.add(key)
                        line = "调用 in=%r out=%r key=%r" % tuple(strs)
                        log.append(line)
                        open(LOG, "a", encoding="utf-8").write(line + "\n")
                        print(line)
                    zero = ctypes.create_string_buffer(12)
                    k32.WriteProcessMemory(hp, ctypes.c_void_p(buff), zero, 12,
                                           ctypes.byref(nread))
        except OSError:
            pass
        code = wintypes.DWORD()
        if k32.GetExitCodeProcess(hp, ctypes.byref(code)) and code.value != STILL_ACTIVE:
            log.append("游戏进程已退出 code=%d" % code.value)
            break
        time.sleep(0.02)

    log.append("结束，共捕获 %d 种调用" % len(seen))
    open(LOG, "w", encoding="utf-8").write("\n".join(log) + "\n")
    print("结束，共捕获 %d 种调用；详情见 %s" % (len(seen), LOG))


if __name__ == "__main__":
    main()
