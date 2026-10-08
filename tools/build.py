# -*- coding: utf-8 -*-
"""打包脚本（构建 + 发行目录）。

    python tools/build.py              # 全套：编宿主 → 准备 dist/ → PyInstaller 打包 → 自检
    python tools/build.py --hostonly   # 只编 32 位宿主
    python tools/build.py --nopack     # 只准备 dist/（不打包）
    python tools/build.py --dll-dir    # 宿主放 dist/dll/ 子目录（DLL 多的时候用）
    python tools/build.py --noselftest # 跳过打包后的 exe 自检

发行目录（dist/）里有什么：

    画迹2内测版存档工具.exe  PyInstaller 单文件 exe（内含 tcl/tk 脚本库）
    XJCodec32.exe            自带的 32 位加解密宿主（**必须**和 exe 放一起，
                             或者放 dll/ 子目录；codec 会按顺序找）
    使用说明.txt
    huaji2-save-editor-vX.Y.Z.zip  ← **唯一发到 Release 上的东西**（上面几个打成一个包）

**不放进去的东西**：游戏自己的 `System\\main.dll`（有版权，而且运行期就是
从用户自己的游戏目录加载的，和 huaji1 的做法一致）。

**为什么发 zip 而不是一个个附件**（2026-09-30，照画迹1 v1.4.0 的教训）：
宿主 `XJCodec32.exe` **不在** onefile 里（`codec.host_candidates()` 是在 exe 所在目录
找它的），少了它就会弹「打开失败 / 缺少依赖」，整个工具都用不了。
以前 Release 上挂 exe / USAGE.txt / XJCodec32.exe 三个附件，**总有人只下主程序**。
实测（`python tools/check_pack.py`）：只把 exe 拷进临时目录跑自检 → `32 位宿主: 未找到`、
`未加载存档`、`结果: NG`；连宿主一起拷 → `结果: OK`。

打包踩过的坑：
  * tcl/tk 的脚本库不会被自动收集，必须 `--add-data` 带上，并在 `import tkinter`
    之前设 `TCL_LIBRARY` / `TK_LIBRARY`（见 `huaji2_save_editor._setup_tcl_env()`）；
  * PyInstaller 用 `subprocess.run(list)` 调，路径里有 `!`、`【】`、`[]` 也没事；
  * 从测试脚本启动 exe 前要清掉 `PYTHONHOME` / `PYTHONPATH` / `VIRTUAL_ENV`，
    否则会以退出码 1 失败（uv/venv 的环境变量会干扰引导）。
"""
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)
sys.stdout.reconfigure(errors="replace")

APP_VERSION = "2.201-beta.16"
# 版本线（2026-10-02 川定）：本分支（`beta`）是**内测版**的开发线，独立于尝鲜版的 v0.x 线。
#
# 版本号 = **游戏版本号 + SemVer 预发布后缀**：`2.201-beta.2`
#   前段直接抄游戏内测版号，一眼看出适配的是哪个游戏版本（游戏是 2.201，修改器就是 2.201-x）；
#   后段是**同一个游戏版本内、修改器自己的第几次发版**（跟游戏无关）。
#
#   两条改法，别搞混：
#     * 游戏内测版更新了 → 只改前段：2.201-beta.2 → 2.202-beta.1（后缀重新从1数）
#     * 同一游戏版本内又修了 bug / 加了功能 → 只加后缀：2.201-beta.2 → 2.201-beta.3
#
#   * 用标准 SemVer 后缀，GitHub 会自动把它标成「Pre-release」，不会跟正式版混淆；
#   * tag 唯一性天然不与主线 v0.x 相撞，两条线可以各自随便发版。
# ⚠ 改动这里的版本号后，`使用说明.txt` 首行和 CHANGELOG 都要跟着改
#   （前者 build.py 只提示不拦，后者有 gen_changelog 兜底）。
APP_VERSION_LINE = "beta"  # 本分支对应的发版分支（gh release --target 用）
#: 发 Release 时是否挂 GitHub 的「Pre-release」标签。本线永远是内测版 → True。
#: （后缀已经是标准 SemVer 预发布，GitHub 本就会自动标；这里显式再给一次，
#:   不依赖平台推断 —— 免得哪次版本号写成 `2.201-beta.x` 之外的形状就悄悄变成正式版。）
APP_PRERELEASE = True
#: 发 Release 时先存成 **Draft（草稿）**，不对外公布。内测版线永远是 `True`
#: （2026-10-05 川定：「内测版修改器产物正常情况下不公布，有源码、有能力的人自然会
#:   自己用和编译」）。Draft 期间的效果：
#:   * Releases 页不列出、`/releases/tags/<tag>` 对非协作者 **404**；
#:   * **tag 也不会被创建** —— 前提是这个 tag 没被手动 `git push` 过
#:     （创建 draft 用的是 `--target <分支>`，GitHub 到 publish 那一刻才真正建 tag）
#:     ⇒ 连版本号都不对外露。⚠ draft 流程下**别提前 `git push` tag**。
#:   * 附件与正文原样保留，想公开就 `python tools/release.py --publish`。
#:   * 命令行可临时覆盖：`--draft` 强制存草稿、`--no-draft` 强制直接公布。
APP_DRAFT = True
# 本地产物名**不带版本号**（2026-09-20 川）：dist 里永远只有一个
# 画迹2内测版存档工具.exe，不会被 vX.Y.Z 版本名占满、也不会误点开旧版本。
# 版本号只出现在发行包名上（见下面的 ZIP_NAME）。
# ⚠ 带「内测版」三字（2026-10-02 川定）：本分支是**内测版 V2.201** 的修改器，
#   与main（尝鲜版 v0.x 线）并存，必须一眼能分清装的是哪个 —— 两者存档格式不通用，
#   拿错就会「打不开存档」。exe 名跟着变，界面标题栏也跟着变（APP_NAME）。
EXE_NAME = "画迹2内测版存档工具"

# GitHub Release 的附件名：平台对中文文件名会自动改名，所以一律用 ASCII，
# **跟仓库名保持一致 + 版本号**（本地 dist\ 里的中文名不影响，内容同一个文件）。
# 发 Release 别手敲名字，直接跑 `python tools/release.py`。
REPO_NAME = "huaji2-save-editor"
# 发行包（zip）：dist 里打好一个包发出去，别人**不用再单独下依赖 exe**。
# 本地名与 Release 上的名字一致，都是 ASCII（GitHub 会剔除资源名里的中文）。
ZIP_NAME = "%s-v%s.zip" % (REPO_NAME, APP_VERSION)
#: 打进 zip 的东西（dist 里的本地名，按这个顺序写进包）；解压出来就是一份能直接双击的完整工具
ZIP_MEMBERS = [EXE_NAME + ".exe", "XJCodec32.exe", "使用说明.txt"]

# (dist 里的文件名, Release 上的附件名) —— **唯一来源**，tools/release.py 读这里。
# ⚠ 只有一个附件：宿主和说明必须跟主程序一起到用户手里，散着挂就会有人漏下。
RELEASE_ASSETS = [
    (ZIP_NAME, ZIP_NAME),
]

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
    src = os.path.join(SRC, "native", "codec32.cs")
    if not os.path.exists(src):
        raise SystemExit("找不到 %s" % src)
    out = os.path.join(SRC, "native", HOST_NAME)
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
def check_usage_version():
    """`使用说明.txt` 首行的版本号对不对（忘了改就会在自检里露馅）。

    它是手写的静态文档，不像 CHANGELOG 有 gen_changelog 兜着；发版时最容易漏。
    只提示不中断 —— 说明文档的版本号写岔了不该挡住打包。
    """
    path = os.path.join(ROOT, "使用说明.txt")
    try:
        with open(path, encoding="utf-8") as f:
            first = f.readline().strip()
    except OSError:
        return
    if APP_VERSION not in first:
        log("  ! 使用说明.txt 首行没写当前版本 %s：%s" % (APP_VERSION, first))


def prepare(host_exe, use_dll_dir=False):
    os.makedirs(DIST, exist_ok=True)
    target_dir = os.path.join(DIST, "dll") if use_dll_dir else DIST
    os.makedirs(target_dir, exist_ok=True)
    check_usage_version()
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
        log("（宿主放在 dll/ 子目录：codec 会依次找 exe 目录、dll/、bin/…）")
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
    """把 CHANGELOG.md **写死进源码**（生成 src/changelog.py）。

    以前 exe 里的“更新日志”是去读一个外部文件，打包成 onefile 后
    运行时目录是临时解包目录，读不到就成了空白 —— 现在直接把文本编进 exe。
    """
    src = os.path.join(ROOT, "CHANGELOG.md")
    out = os.path.join(SRC, "changelog.py")
    if not os.path.exists(src):
        log("  ! 没有 CHANGELOG.md，跳过内置更新日志")
        return
    text = open(src, encoding="utf-8").read()
    body = ('# -*- coding: utf-8 -*-\n'
            '"""内置的更新日志（由 tools/build.py 自动生成，别手改）。\n\n'
            '源码见仓库根目录的 CHANGELOG.md。\n"""\n'
            'VERSION = "%s"\n\n'
            'TEXT = %r\n' % (APP_VERSION, text))
    # newline="\n"：Windows 上默认会写成 CRLF，而仓库按 LF 存（见 .gitattributes），
    # 不钉死的话每次打包生成的这个文件都会变成「整文件重写」的假 diff。
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(body)
    log("已生成内置更新日志：src/changelog.py（%d 字）" % len(text))


def sweep_old_exes(keep):
    """把 dist 里**旧命名的**主程序删掉（留着容易点错版本）。

    历史产物名带版本号（`画迹2存档工具v0.5.4.exe`），现在固定叫
    `画迹2内测版存档工具.exe` —— 打包时顺手清掉以前留下的那些。
    ⚠ 认**两个**前缀：老的 `画迹2存档工具`（v0.x 时代留下的）和新的
    `画迹2内测版存档工具`。别只认新的 —— dist 里躺着旧名 exe 会让人
    以为是两个工具，其实一个是死的。不碰宿主 XJCodec32.exe。
    """
    try:
        names = sorted(os.listdir(DIST))
    except OSError:
        return
    for n in names:
        if not n.endswith(".exe") or n == keep:
            continue
        if not (n.startswith("画迹2内测版存档工具")
                or n.startswith("画迹2存档工具")):
            continue
        try:
            os.remove(os.path.join(DIST, n))
            log("  清掉旧命名的主程序：%s" % n)
        except OSError:
            log("  ! 旧主程序删不掉（可能正开着）：%s" % n)


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
            # cwd 必须指定：PyInstaller 6.22+ 拒绝在 Windows 系统目录下运行，
            # 而工具/终端启动脚本时 cwd 未必是仓库根。
            r = subprocess.run([p, "-m", "PyInstaller", "--version"],
                               capture_output=True, text=True, timeout=120,
                               cwd=ROOT)
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
            # --specpath 必须指 build/（不是 ROOT）：spec 是纯中间产物，
            # 放仓库根目录会按版本号越堆越多（v0.4.x~v0.5.x 堆了二十几个）。
            "--distpath", DIST, "--workpath", BUILD, "--specpath", BUILD,
            "--paths", SRC]
           + tcl_data_args(py)
           + [os.path.join(SRC, "huaji2_save_editor.py")])
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
# 4) 打包成发行 zip
# --------------------------------------------------------------------------
def pack_zip(target_dir=None):
    r"""把 dist 里的整套文件打成一个 zip（**发到 Release 的就是它**）。

    人最容易漏的是 `XJCodec32.exe`（少了它读不了存档，弹「打开失败」），
    打成一个包就不会漏。缺东西**直接报错退出**，绝不发半包。
    """
    import zipfile
    base = target_dir or DIST
    found = {}
    for n in ZIP_MEMBERS:
        cands = [os.path.join(base, n), os.path.join(base, "dll", n)]
        p = next((c for c in cands if os.path.exists(c)), None)
        if p is None:
            raise SystemExit(
                "dist 里还缺 %s —— 发行包不该少东西。\n"
                "  先跑 python tools/build.py（宿主 XJCodec32.exe 由 build_host() "
                "编译生成），确认它在 dist 根目录或 dist/dll/。" % n)
        found[n] = p
    dst = os.path.join(base, ZIP_NAME)
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
        for n in ZIP_MEMBERS:
            # 一律平铺在压缩包根目录：解压出来就能双击，不用再挪文件
            z.write(found[n], n)
    log("已打包发行 zip：%s（%.2f MB，%d 个文件）"
        % (ZIP_NAME, os.path.getsize(dst) / 1048576.0, len(ZIP_MEMBERS)))
    return dst


# --------------------------------------------------------------------------
# 5) 自检（把 dist 拷到临时目录跑，确保不依赖源码）
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
            import paths
            game = env.get("XJ_GAME") or paths.find_game_dir()
            if game:
                env["XJ_GAME"] = game
                sp = os.path.join(game, "save.rvdata2")
                if os.path.exists(sp):
                    env["XJ_SAVE"] = sp
                log("  喂给自检：XJ_GAME=%s" % game)
        except Exception as e:
            log("  ! 没找到游戏目录（%s），自检只能跑空档" % e)
        log("自检：在临时目录跑 %s …" % os.path.basename(exe2))
        # ⚠ 不等它「自己退干净」：PyInstaller onefile 的**引导进程**偶尔会卡在
        #   删 `_MEI` 临时目录那一步（本机安全钩子会拦删除）—— 自检结果文件其实早就
        #   写好了，进程却一直不退，subprocess.run(timeout=300) 于是白等 5 分钟。
        #   所以：轮询结果文件 → 到点收尸（连子进程一起），判定只看结果文件。
        res = os.path.join(work, "selftest_result.txt")
        outlog = os.path.join(tmp, "selfcheck.log")
        with open(outlog, "wb") as fh:
            p = subprocess.Popen([exe2], cwd=work, env=env,
                                 stdout=fh, stderr=subprocess.STDOUT)
            deadline = time.time() + 120
            while time.time() < deadline:
                if os.path.exists(res) or p.poll() is not None:
                    break
                time.sleep(0.5)
            rc = p.poll()
            killed = rc is None
            if killed:
                kill_tree(p.pid)
                rc = p.wait()
                log("  （exe 没自己退，已连子进程一起清掉；判定只看结果文件）")
        txt = ""
        for name in ("selftest_result.txt", "error.log"):
            f = os.path.join(work, name)
            if os.path.exists(f):
                txt += open(f, encoding="utf-8", errors="replace").read() + "\n"
        log(txt or "(没有自检输出)")
        log("自检退出码 = %d%s" % (rc, "（上面是我们 taskkill 的，不代表失败）"
                                 if killed else ""))
        kill_leftover(os.path.basename(exe2))
        return 0 if "结果: OK" in txt else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def kill_tree(pid):
    """把一棵进程树干掉（onefile 的引导进程 + 它拉起的真正程序）。"""
    if os.name != "nt":
        return
    try:
        # encoding/errors 必须给：taskkill 在中文系统上是 GBK 输出，
        # 让 subprocess 按 UTF-8 硬解会在读线程里抛 UnicodeDecodeError
        # （只留一段难看的 traceback，不影响结果但很吵）。
        subprocess.run(["taskkill", "/f", "/t", "/pid", str(pid)],
                       capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=30)
    except Exception:
        pass


def kill_leftover(name):
    """自检的 exe 偶尔会赖着不退（tkinter + onefile 引导），它会锁住 dist 里的文件。"""
    if os.name != "nt":
        return
    try:
        r = subprocess.run(["taskkill", "/f", "/im", name],
                           capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=20)
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
    pack_zip()
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
