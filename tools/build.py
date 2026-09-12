# -*- coding: utf-8 -*-
"""打包脚本（构建 + 发行目录）。

    python tools/build.py              # 全套：编宿主 → 准备 dist/ → PyInstaller 打包 → 自检
    python tools/build.py --hostonly   # 只编 32 位宿主
    python tools/build.py --nopack     # 只准备 dist/（不打包）
    python tools/build.py --dll-dir    # 宿主放 dist/dll/ 子目录（DLL 多的时候用）
    python tools/build.py --noselftest # 跳过打包后的 exe 自检

发行目录（dist/）里有什么：

    画迹2存档工具v0.4.exe    PyInstaller 单文件 exe（内含 tcl/tk 脚本库）
    XJCodec32.exe            自带的 32 位加解密宿主（**必须**和 exe 放一起，
                             或者放 dll/ 子目录；xj_codec 会按顺序找）
    使用说明.txt

**不放进去的东西**：游戏自己的 `System\\main.dll`（有版权，而且运行期就是
从用户自己的游戏目录加载的，和 huaji1 的做法一致）。

打包踩过的坑：
  * tcl/tk 的脚本库不会被自动收集，必须 `--add-data` 带上，并在 `import tkinter`
    之前设 `TCL_LIBRARY` / `TK_LIBRARY`（见 `xj_viewer._setup_tcl_env()`）；
  * PyInstaller 用 `subprocess.run(list)` 调，路径里有 `!`、`【】`、`[]` 也没事；
  * 从测试脚本启动 exe 前要清掉 `PYTHONHOME` / `PYTHONPATH` / `VIRTUAL_ENV`，
    否则会以退出码 1 失败（uv/venv 的环境变量会干扰引导）。
"""
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)
sys.stdout.reconfigure(errors="replace")

APP_VERSION = "0.4.5"
EXE_NAME = "画迹2存档工具v" + APP_VERSION
DIST = os.path.join(ROOT, "dist")
BUILD = os.path.join(ROOT, "build")
HOST_NAME = "XJCodec32.exe"

CSC = [r"C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe",
       r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"]


def log(s):
    print(s)


# --------------------------------------------------------------------------
# 1) 32 位宿主
# --------------------------------------------------------------------------
def build_host():
    csc = next((p for p in CSC if os.path.exists(p)), None)
    if not csc:
        raise SystemExit("找不到 csc.exe（需要 .NET Framework 4.x）")
    src = os.path.join(SRC, "xj_codec32.cs")
    if not os.path.exists(src):
        raise SystemExit("找不到 %s" % src)
    out = os.path.join(SRC, HOST_NAME)
    # 宿主在跑的时候编不进去：先试着删掉旧的
    if os.path.exists(out):
        try:
            os.remove(out)
        except OSError:
            log("  ! %s 正被占用，直接覆盖试试" % HOST_NAME)
    cmd = [csc, "/nologo", "/platform:x86", "/optimize+", "/target:exe",
           "/out:" + out, src]
    p = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if p.returncode != 0 or not os.path.exists(out):
        log(p.stdout or "")
        log(p.stderr or "")
        raise SystemExit("编译 %s 失败" % HOST_NAME)
    log("已编译 32 位宿主：%s（%d 字节）" % (out, os.path.getsize(out)))
    return out


# --------------------------------------------------------------------------
# 2) 发行目录
# --------------------------------------------------------------------------
def prepare(host_exe, use_dll_dir=False):
    os.makedirs(DIST, exist_ok=True)
    target_dir = os.path.join(DIST, "dll") if use_dll_dir else DIST
    os.makedirs(target_dir, exist_ok=True)
    gen_changelog()
    items = [(host_exe, HOST_NAME),
             (os.path.join(ROOT, "使用说明.txt"), "使用说明.txt"),
             (os.path.join(ROOT, "README.md"), "README.md"),
             (os.path.join(ROOT, "CHANGELOG.md"), "CHANGELOG.md")]
    for src, name in items:
        if not os.path.exists(src):
            log("  ! 缺少 %s，跳过" % src)
            continue
        dst = os.path.join(target_dir, name)
        if _same_file(src, dst):
            log("已是最新：%s%s" % ("" if not use_dll_dir else "dll/", name))
            continue
        try:
            shutil.copyfile(src, dst)
        except PermissionError:
            log("  ! %s 正被占用（可能程序还开着），跳过" % name)
            continue
        log("已放入发行目录：%s%s" % ("" if not use_dll_dir else "dll/", name))
    if use_dll_dir:
        log("（宿主放在 dll/ 子目录：xj_codec 会依次找 exe 目录、dll/、bin/…）")
    sweep_old_exes(EXE_NAME + ".exe")
    return target_dir


def _same_file(a, b):
    """两个文件内容是否一样（省得为了同一份内容去覆盖被占用的文件）。"""
    try:
        if os.path.getsize(a) != os.path.getsize(b):
            return False
        with open(a, "rb") as fa, open(b, "rb") as fb:
            while True:
                x, y = fa.read(65536), fb.read(65536)
                if x != y:
                    return False
                if not x:
                    return True
    except OSError:
        return False


def gen_changelog():
    """把 CHANGELOG.md **写死进源码**（生成 src/xj_changelog.py）。

    以前 exe 里的“更新日志”是去读一个外部文件，打包成 onefile 后
    运行时目录是临时解包目录，读不到就成了空白 —— 现在直接把文本编进 exe。
    """
    src = os.path.join(ROOT, "CHANGELOG.md")
    out = os.path.join(SRC, "xj_changelog.py")
    if not os.path.exists(src):
        log("  ! 没有 CHANGELOG.md，跳过内置更新日志")
        return
    text = open(src, encoding="utf-8").read()
    body = ('# -*- coding: utf-8 -*-\n'
            '"""内置的更新日志（由 tools/build.py 自动生成，别手改）。\n\n'
            '源码见仓库根目录的 CHANGELOG.md。\n"""\n'
            'VERSION = "%s"\n\n'
            'TEXT = %r\n' % (APP_VERSION, text))
    with open(out, "w", encoding="utf-8") as f:
        f.write(body)
    log("已生成内置更新日志：src/xj_changelog.py（%d 字）" % len(text))


def sweep_old_exes(keep):
    """把 dist 里**其它版本**的主程序删掉（留着容易点错版本）。

    只删 `画迹2存档工具v*.exe`，不碰宿主 XJCodec32.exe。
    """
    try:
        names = sorted(os.listdir(DIST))
    except OSError:
        return
    for n in names:
        if not n.endswith(".exe") or n == keep:
            continue
        if not n.startswith("画迹2存档工具"):
            continue
        try:
            os.remove(os.path.join(DIST, n))
            log("  清掉旧版本主程序：%s" % n)
        except OSError:
            log("  ! 旧版本主程序删不掉（可能正开着）：%s" % n)


# --------------------------------------------------------------------------
# 3) PyInstaller
# --------------------------------------------------------------------------
def find_pyinstaller_python():
    """找一个装了 PyInstaller 的解释器：XJ_PY → 仓库旁的 .venv → 当前解释器。"""
    cands = []
    env = os.environ.get("XJ_PY")
    if env:
        cands.append(env)
    venv = os.path.join(os.path.dirname(ROOT), ".venv", "Scripts", "python.exe")
    if os.path.exists(venv):
        cands.append(venv)
    venv2 = os.path.join(ROOT, ".venv", "Scripts", "python.exe")
    if os.path.exists(venv2):
        cands.append(venv2)
    cands.append(sys.executable)
    for p in cands:
        try:
            r = subprocess.run([p, "-m", "PyInstaller", "--version"],
                               capture_output=True, text=True, timeout=120)
        except Exception:
            continue
        if r.returncode == 0:
            return p, (r.stdout or "").strip()
    return None, None


def tcl_data_args(py):
    """tcl/tk 的脚本库要显式带上（PyInstaller 不会自动收集）。"""
    r = subprocess.run([py, "-c", "import sys,os;print(os.path.join(sys.base_prefix,'tcl'))"],
                       capture_output=True, text=True)
    root = (r.stdout or "").strip()
    args = []
    if not root or not os.path.isdir(root):
        log("  ! 找不到 tcl 目录（%r），打包后的 exe 可能起不来" % root)
        return args
    for sub in ("tcl8.6", "tk8.6", "tcl8"):
        p = os.path.join(root, sub)
        if os.path.isdir(p):
            args += ["--add-data", "%s;tcl/%s" % (p, sub)]
            log("  带上 %s" % sub)
    return args


def free_old_exe(name):
    """把上一次的 exe 让开。

    常见情况：上次的自检 exe 还没退干净、杀软正在扫它、
    或者用户正开着它 → `os.remove` 报 WinError 5。
    先重试几次，还不行就改名让路（PyInstaller 就能写新文件了）。
    """
    import time
    p = os.path.join(DIST, name)
    if not os.path.exists(p):
        return
    for _ in range(5):
        try:
            os.remove(p)
            return
        except OSError:
            time.sleep(1)
    alt = p + ".old"
    try:
        if os.path.exists(alt):
            os.remove(alt)
        os.rename(p, alt)
        log("  ! 旧 exe 删不掉（可能正被占用），已改名让路：%s"
            % os.path.basename(alt))
    except OSError as e:
        raise SystemExit("旧 exe 既删不掉也改不了名（%s）：%s\n"
                         "请先关掉正在运行的 %s（或重启资源管理器）再打包。"
                         % (p, e, name))


def build_exe(py):
    free_old_exe(EXE_NAME + ".exe")
    cmd = ([py, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile",
            "--windowed", "--name", EXE_NAME,
            "--distpath", DIST, "--workpath", BUILD, "--specpath", ROOT,
            "--paths", SRC]
           + tcl_data_args(py)
           + [os.path.join(SRC, "xj_viewer.py")])
    log("打包中…（第一次会慢一点）")
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if p.returncode != 0:
        log((p.stdout or "")[-4000:])
        log((p.stderr or "")[-4000:])
        raise SystemExit("PyInstaller 打包失败")
    exe = os.path.join(DIST, EXE_NAME + ".exe")
    log("打包完成：%s（%.1f MB）" % (exe, os.path.getsize(exe) / 1048576.0))
    return exe


# --------------------------------------------------------------------------
# 4) 自检（把 dist 拷到临时目录跑，确保不依赖源码）
# --------------------------------------------------------------------------
def selftest(exe):
    import tempfile
    tmp = tempfile.mkdtemp(prefix="xj_dist_")
    try:
        work = os.path.join(tmp, "dist")
        shutil.copytree(DIST, work)
        exe2 = os.path.join(work, os.path.basename(exe))
        env = dict(os.environ)
        for k in ("PYTHONHOME", "PYTHONPATH", "PYTHONSTARTUP",
                  "PYTHONEXECUTABLE", "VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT"):
            env.pop(k, None)
        env["XJ_SELFTEST"] = "1"
        # 临时目录里 exe 找不到游戏（往回走几层是临时目录），
        # 直接把游戏目录/存档喂给它，让自检跑真数据。
        if SRC not in sys.path:
            sys.path.insert(0, SRC)
        try:
            import xj_env
            game = env.get("XJ_GAME") or xj_env.find_game_dir()
            if game:
                env["XJ_GAME"] = game
                sp = os.path.join(game, "save.rvdata2")
                if os.path.exists(sp):
                    env["XJ_SAVE"] = sp
                log("  喂给自检：XJ_GAME=%s" % game)
        except Exception as e:
            log("  ! 没找到游戏目录（%s），自检只能跑空档" % e)
        log("自检：在临时目录跑 %s …" % os.path.basename(exe2))
        p = subprocess.run([exe2], cwd=work, env=env, timeout=300,
                           capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        txt = ""
        for name in ("selftest_result.txt", "error.log"):
            f = os.path.join(work, name)
            if os.path.exists(f):
                txt += open(f, encoding="utf-8", errors="replace").read() + "\n"
        log(txt or "(没有自检输出)")
        log("自检退出码 = %d" % p.returncode)
        kill_leftover(os.path.basename(exe2))
        return 0 if "结果: OK" in txt else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def kill_leftover(name):
    """自检的 exe 偶尔会赖着不退（tkinter + onefile 引导），它会锁住 dist 里的文件。"""
    if os.name != "nt":
        return
    try:
        r = subprocess.run(["taskkill", "/f", "/im", name],
                           capture_output=True, text=True, timeout=20)
        if (r.stdout or "").strip():
            log("  清掉没退干净的进程：%s" % (r.stdout or "").strip()[:120])
    except Exception:
        pass


def main():
    argv = sys.argv[1:]
    host = build_host()
    if "--hostonly" in argv:
        return 0
    prepare(host, use_dll_dir="--dll-dir" in argv)
    if "--nopack" in argv:
        log("只准备发行目录（未打包）")
        return 0
    py, ver = find_pyinstaller_python()
    if not py:
        log("[NG] 没找到装了 PyInstaller 的解释器。装一个：")
        log("     python -m pip install pyinstaller")
        log("     或指定： $env:XJ_PY = '<python.exe 路径>'")
        return 1
    log("用 %s（PyInstaller %s）打包" % (py, ver))
    exe = build_exe(py)
    log("")
    log("发行目录 %s：" % DIST)
    for n in sorted(os.listdir(DIST)):
        p = os.path.join(DIST, n)
        if os.path.isfile(p):
            log("   %-40s %.2f MB" % (n, os.path.getsize(p) / 1048576.0))
        else:
            log("   %-40s <目录>" % (n + "/"))
    if "--noselftest" in argv:
        return 0
    return selftest(exe)


if __name__ == "__main__":
    sys.exit(main())
