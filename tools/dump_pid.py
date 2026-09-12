# -*- coding: utf-8 -*-
"""把正在运行的 Game.exe 里的 System\\main.dll 镜像 dump 出来（需要管理员权限）。

用法：
    python tools/dump_pid.py                 # 自动找 Game.exe
    python tools/dump_pid.py --pid 1234
    python tools/dump_pid.py --no-elevate    # 调试用，不提权

结果：tools/_pid_main.bin + tools/_pid_dump.txt（逐行 flush，便于观察进度）
"""
import ctypes
import ctypes.wintypes as wt
import os
import subprocess
import sys

sys.stdout.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GAME = os.path.normpath(os.path.join(ROOT, "..", "..", ".."))
OUT = os.path.join(HERE, "_pid_main.bin")
LOG = os.path.join(HERE, "_pid_dump.txt")

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
TH32CS_SNAPMODULE = 0x00000008
TH32CS_SNAPMODULE32 = 0x00000010
INVALID = ctypes.c_void_p(-1).value


class MODULEENTRY32(ctypes.Structure):
    _fields_ = [("dwSize", wt.DWORD), ("th32ModuleID", wt.DWORD),
                ("th32ProcessID", wt.DWORD), ("GlblcntUsage", wt.DWORD),
                ("ProccntUsage", wt.DWORD),
                ("modBaseAddr", ctypes.POINTER(ctypes.c_byte)),
                ("modBaseSize", wt.DWORD), ("hModule", wt.HMODULE),
                ("szModule", ctypes.c_char * 256), ("szExePath", ctypes.c_char * 260)]


k32.CreateToolhelp32Snapshot.restype = wt.HANDLE
k32.CreateToolhelp32Snapshot.argtypes = [wt.DWORD, wt.DWORD]
k32.Module32First.argtypes = [wt.HANDLE, ctypes.POINTER(MODULEENTRY32)]
k32.Module32Next.argtypes = [wt.HANDLE, ctypes.POINTER(MODULEENTRY32)]
k32.OpenProcess.restype = wt.HANDLE
k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
k32.ReadProcessMemory.argtypes = [wt.HANDLE, wt.LPCVOID, wt.LPVOID,
                                  ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
k32.CloseHandle.argtypes = [wt.HANDLE]

LOG_F = None


def log(*a):
    line = " ".join(str(x) for x in a)
    if LOG_F:
        LOG_F.write(line + "\n")
        LOG_F.flush()
    try:
        print(line)
    except Exception:
        pass


def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch():
    params = " ".join('"%s"' % a for a in sys.argv[1:])
    r = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable,
        '"%s" %s' % (os.path.abspath(__file__), params), ROOT, 1)
    return r > 32


def find_game():
    p = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Game.exe", "/FO", "CSV", "/NH"],
                       capture_output=True, timeout=30)
    txt = (p.stdout or b"").decode("gbk", "replace")
    for ln in txt.splitlines():
        if "game.exe" in ln.lower():
            parts = [x.strip().strip('"') for x in ln.split('","')]
            for x in parts:
                if x.isdigit():
                    return int(x)
    return None


def modules(pid):
    out = []
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, pid)
    if snap == INVALID:
        return out, ctypes.get_last_error()
    try:
        me = MODULEENTRY32()
        me.dwSize = ctypes.sizeof(MODULEENTRY32)
        ok = k32.Module32First(snap, ctypes.byref(me))
        while ok:
            out.append((me.szModule.decode("mbcs", "replace"),
                        ctypes.cast(me.modBaseAddr, ctypes.c_void_p).value,
                        me.modBaseSize))
            ok = k32.Module32Next(snap, ctypes.byref(me))
    finally:
        k32.CloseHandle(snap)
    return out, 0


def read_mem(h, base, size, chunk=0x10000):
    buf = ctypes.create_string_buffer(size)
    got = ctypes.c_size_t(0)
    off = 0
    while off < size:
        n = min(chunk, size - off)
        ok = k32.ReadProcessMemory(h, ctypes.c_void_p(base + off),
                                   ctypes.byref(buf, off), n, ctypes.byref(got))
        if not ok or got.value == 0:
            return None, off, ctypes.get_last_error()
        off += got.value
    return buf.raw, off, 0


def main():
    global LOG_F
    argv = sys.argv[1:]
    no_elev = "--no-elevate" in argv
    if not no_elev and not is_admin():
        if relaunch():
            print("已请求管理员权限（请在 UAC 弹窗点「是」）")
            print("提权后的进度请查看 tools/_pid_dump.txt")
            return 0
        print("[WARN] 提权被拒绝，尝试以当前权限继续")

    LOG_F = open(LOG, "w", encoding="utf-8", buffering=1)
    log("admin =", is_admin())
    pid = None
    if "--pid" in argv:
        pid = int(argv[argv.index("--pid") + 1])
    else:
        pid = find_game()
    log("pid =", pid)
    if pid is None:
        log("[NG] 没有找到 Game.exe，请先启动游戏")
        return 1

    mods, err = modules(pid)
    log("模块数 =", len(mods), "枚举错误 =", err)
    main_mod = None
    for name, base, size in mods:
        if name.lower().endswith("main.dll"):
            main_mod = (name, base, size)
        if name.lower().endswith((".dll", ".exe")) and (
                "rgss" in name.lower() or "main" in name.lower()
                or "ws2" in name.lower() or "astar" in name.lower()
                or "game" in name.lower()):
            log("   %-20s base=0x%08X size=0x%X" % (name, base, size))
    if not main_mod:
        log("[NG] 目标进程里没有 main.dll")
        return 2
    log("main.dll base=0x%08X size=0x%X" % (main_mod[1], main_mod[2]))

    h = k32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if not h:
        log("[NG] OpenProcess 失败 win32err=", ctypes.get_last_error())
        return 3
    try:
        data, got, e = read_mem(h, main_mod[1], main_mod[2])
        if data is None:
            log("[NG] ReadProcessMemory 失败 @0x%X err=%d" % (main_mod[1] + got, e))
            return 4
        with open(OUT, "wb") as f:
            f.write(data)
        log("[OK] dump %d 字节 -> %s" % (len(data), OUT))
        log("     头 16 字节 = " + data[:16].hex(" "))
    finally:
        k32.CloseHandle(h)
    log("done")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001
        import traceback
        log("[EXC] %s" % e)
        log(traceback.format_exc())
        raise
