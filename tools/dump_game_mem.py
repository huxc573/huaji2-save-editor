# -*- coding: utf-8 -*-
"""在游戏进程里 dump System\\main.dll 的内存镜像（用来找"密钥状态"）。

原理：main.dll 是 32 位 MPRESS 壳，导出函数的实现体在解壳后位于固定 RVA。
     它内部有一份"分组密码状态"，游戏启动时 qqeat 会把它装配好。
     我们在外部 LoadLibrary 得到的只是**出厂状态**（所以解密游戏文件会得到 0 字节）。
     把两个镜像做差分，就能定位到这份状态，然后搬进我们自己的宿主。

用法：
    python tools/dump_game_mem.py --launch        # 自己启动游戏再 dump
    python tools/dump_game_mem.py --pid 1234      # 附着已有进程
    python tools/dump_game_mem.py --launch --wait 25 --keep   # 保留游戏不关

结果：tools/_game_main.bin（并打印模块基址/大小）
"""
import ctypes
import ctypes.wintypes as wt
import hashlib
import os
import subprocess
import sys
import time

sys.stdout.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GAME = os.path.normpath(os.path.join(ROOT, "..", "..", ".."))
OUT = os.path.join(HERE, "_game_main.bin")
LOG = os.path.join(HERE, "_game_dump.txt")


def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin():
    """用 UAC 重新启动自己（只弹一次提示）。"""
    params = " ".join('"%s"' % a for a in sys.argv[1:])
    r = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable,
        '"%s" %s' % (os.path.abspath(__file__), params), ROOT, 1)
    return r > 32

k32 = ctypes.WinDLL("kernel32", use_last_error=True)

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
TH32CS_SNAPMODULE = 0x00000008
TH32CS_SNAPMODULE32 = 0x00000010
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


class MODULEENTRY32(ctypes.Structure):
    _fields_ = [("dwSize", wt.DWORD),
                ("th32ModuleID", wt.DWORD),
                ("th32ProcessID", wt.DWORD),
                ("GlblcntUsage", wt.DWORD),
                ("ProccntUsage", wt.DWORD),
                ("modBaseAddr", ctypes.POINTER(ctypes.c_byte)),
                ("modBaseSize", wt.DWORD),
                ("hModule", wt.HMODULE),
                ("szModule", ctypes.c_char * 256),
                ("szExePath", ctypes.c_char * 260)]


k32.CreateToolhelp32Snapshot.restype = wt.HANDLE
k32.CreateToolhelp32Snapshot.argtypes = [wt.DWORD, wt.DWORD]
k32.Module32First.argtypes = [wt.HANDLE, ctypes.POINTER(MODULEENTRY32)]
k32.Module32Next.argtypes = [wt.HANDLE, ctypes.POINTER(MODULEENTRY32)]
k32.OpenProcess.restype = wt.HANDLE
k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
k32.ReadProcessMemory.argtypes = [wt.HANDLE, wt.LPCVOID, wt.LPVOID,
                                  ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
k32.CloseHandle.argtypes = [wt.HANDLE]


def log(f, *a):
    line = " ".join(str(x) for x in a)
    f.write(line + "\n")


def find_process(name="Game.exe"):
    """用 tasklist 找 pid（比 CreateToolhelp32Process32 少写几百行）。"""
    p = subprocess.run(["tasklist", "/FI", "IMAGENAME eq " + name,
                        "/FO", "CSV", "/NH"], capture_output=True, timeout=30)
    txt = (p.stdout or b"").decode("gbk", "replace")
    for ln in txt.splitlines():
        if name.lower() in ln.lower():
            parts = [x.strip().strip('"') for x in ln.split('","')]
            for x in parts:
                if x.isdigit():
                    return int(x)
    return None


def module_info(pid, want="main.dll"):
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, pid)
    if snap == INVALID_HANDLE_VALUE:
        return None
    try:
        me = MODULEENTRY32()
        me.dwSize = ctypes.sizeof(MODULEENTRY32)
        ok = k32.Module32First(snap, ctypes.byref(me))
        while ok:
            name = me.szModule.decode("mbcs", "replace")
            if name.lower() == want.lower():
                return (ctypes.cast(me.modBaseAddr, ctypes.c_void_p).value,
                        me.modBaseSize, name, me.szExePath.decode("mbcs", "replace"))
            ok = k32.Module32Next(snap, ctypes.byref(me))
    finally:
        k32.CloseHandle(snap)
    return None


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
    argv = sys.argv[1:]
    if "--elevated" not in argv and not is_admin():
        if relaunch_as_admin():
            print("已请求管理员权限（请在 UAC 弹窗点“是”），本进程退出")
            return 0
        print("[NG] 提权失败")
        return 9
    if "--elevated" not in argv:
        argv = argv + ["--elevated"]

    pid = None
    launch = "--launch" in argv
    keep = "--keep" in argv
    wait = 25
    if "--wait" in argv:
        wait = int(argv[argv.index("--wait") + 1])
    if "--pid" in argv:
        pid = int(argv[argv.index("--pid") + 1])

    with open(LOG, "w", encoding="utf-8") as f:
        log(f, "admin =", is_admin())
        for rel in ("Data/main.rvdata2", "Game.exe", "System/main.dll",
                    "Config.ini", "was.info", "save.rvdata2"):
            p = os.path.join(GAME, rel.replace("/", os.sep))
            if os.path.exists(p):
                d = open(p, "rb").read()
                log(f, "md5 %-20s %s (%d B)" % (rel, hashlib.md5(d).hexdigest(), len(d)))
        log(f, "Config.ini 里写的 = a36839d89d4822fcd7461364c46c4a42")
        proc = None
        if pid is None:
            if not launch:
                pid = find_process()
                log(f, "现有 Game.exe pid =", pid)
            if pid is None:
                exe = os.path.join(GAME, "Game.exe")
                log(f, "启动", exe)
                proc = subprocess.Popen([exe], cwd=GAME, close_fds=True)
                time.sleep(1.0)
                pid = proc.pid
                log(f, "启动的 pid =", pid)
                for _ in range(wait * 2):
                    if module_info(pid, "main.dll"):
                        break
                    time.sleep(0.5)
                time.sleep(max(0, wait - 12))
        if pid is None:
            log(f, "[NG] 没有 Game.exe")
            print("no game")
            return 1

        mi = module_info(pid, "main.dll")
        log(f, "main.dll 模块信息 =", mi)
        if not mi:
            log(f, "[NG] 进程里找不到 main.dll（可能还没启动完，或权限不够）")
            print("no module")
            if proc and not keep:
                proc.terminate()
            return 2

        base, size, name, path = mi
        log(f, "base=0x{0:X} size=0x{1:X}".format(base, size))
        h = k32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
        if not h:
            err = ctypes.get_last_error()
            log(f, "[NG] OpenProcess 失败 win32err={0}（多半是权限：游戏以管理员运行，"
                   f"请用管理员身份重跑本脚本）".format(err))
            print("open failed")
            if proc and not keep:
                proc.terminate()
            return 3
        try:
            data, got, err = read_mem(h, base, size)
            if data is None:
                log(f, "[NG] ReadProcessMemory 在读 0x{0:X} 处失败 err={1}".format(
                    base + got, err))
                return 4
            open(OUT, "wb").write(data)
            log(f, "[OK] dump {0} 字节 -> {1}".format(len(data), OUT))
            log(f"     头 16 字节 = {data[:16].hex(' ')}")
        finally:
            k32.CloseHandle(h)

        if proc and not keep:
            log(f, "关闭游戏进程 pid={0}".format(pid))
            try:
                proc.terminate()
                proc.wait(timeout=15)
            except Exception as e:  # noqa: BLE001
                log(f"  关闭失败: {e}")
        elif keep:
            log("(--keep) 游戏保持运行，请自己收尾")

    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
