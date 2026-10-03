# -*- coding: utf-8 -*-
r"""发 GitHub Release：按 `build.py` 里的命名规则准备好附件，再交给 `gh`。

    python tools/release.py                 # 创建/更新 v<当前版本> 的 Release
    python tools/release.py --upload-only   # Release 已存在，只重传附件
    python tools/release.py --dry           # 只打印要做什么，不动手
    python tools/release.py --no-prerelease # 临时不挂 Pre-release 标签

附件命名（**唯一来源在 tools/build.py**，别在这儿手敲）：
    huaji2-save-editor-v<版本>.zip   发行包 = 主程序 + XJCodec32.exe + 使用说明
    ⚠ **只有一个附件**：宿主必须跟主程序一起到用户手里（散着挂总有人只下主程序，
      然后报「打不开」）。Release 上只上传这一个 zip，别再加别的。

版本号形状：`2.201-beta.N` —— 前段抄游戏内测版号，后段是同一游戏版本内
    修改器自己的发版次数（游戏更新就只改前段，见 build.py 的注释）。

⚠ tag 打在哪条线（2026-10-02 双线后新增）：本仓库有两条发版线，共用同一个仓库 ——
    main = 尝鲜版 v0.x，beta = 内测版 2.201-beta.N。
    `gh release create` 的 `--target` 已显式取 build.py 的 `APP_VERSION_LINE`，
    别删掉它 —— 漏了就会把 tag 落在「当前 HEAD」上，很容易发错线。
    tag 本身是全仓库唯一的，所以两条线的版本号永远不会撞。

Release 正文 = CHANGELOG.md 里本版本那段的**更新总结打头**，尾部接免责声明 +
一行下载说明（与画迹1 同一套规则，别往正文里堆下载说明）。
Release 标题 = `vX.Y.Z —— <总结第一行>`（发版日期只留在 CHANGELOG 段标题里，
不再往 Release 标题/正文上堆）。
需要本机装了 `gh` 且已登录（`gh auth status`）；git 推送另说。
"""
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.stdout.reconfigure(errors="replace")
import importlib.util

spec = importlib.util.spec_from_file_location("xjbuild", os.path.join(HERE, "build.py"))
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)

TAG = "v" + b.APP_VERSION


def stage_dir():
    r"""附件暂存目录。

    ⚠ 不能用仓库里的 `_tmp\`：本机仓库路径带 `[]`（`【画迹2…】 [尝鲜版]`），
    而 `gh release upload` 把文件参数当 **glob** 解析，方括号会被当字符类 →
    报 `no matches found`。丢到系统临时目录（纯 ASCII 无方括号）就没这事。
    """
    import tempfile
    d = os.path.join(tempfile.gettempdir(), "xj_release_" + b.APP_VERSION)
    if os.path.isdir(d):
        shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d, exist_ok=True)
    return d


def stage_assets():
    """把 dist 里的文件复制成 Release 用的 ASCII 名。"""
    STAGE = stage_dir()
    os.makedirs(STAGE, exist_ok=True)
    out = []
    for src_name, asset_name in b.RELEASE_ASSETS:
        src = os.path.join(b.DIST, src_name)
        if not os.path.exists(src):
            raise SystemExit("缺少 %s —— 先跑 python tools/build.py" % src)
        dst = os.path.join(STAGE, asset_name)
        shutil.copyfile(src, dst)
        out.append(dst)
        print("  准备 %-38s <- %s" % (asset_name, src_name))
    return out


def summary_lines():
    r"""CHANGELOG 里本版本段的正文（剥掉 `## vX.Y.Z (日期)` 标题行与尾部 `---`）。

    正文第一行就是这版的更新总结（`**主题：…**`）—— Release 标题与正文都从它取，
    所以日期只留在 CHANGELOG 的段标题里，不再往标题/正文上堆。
    """
    path = os.path.join(ROOT, "CHANGELOG.md")
    if not os.path.exists(path):
        return []
    text = open(path, encoding="utf-8").read()
    head = text.find("## " + TAG)
    if head < 0:
        return []
    nxt = text.find("\n## ", head + 1)
    body = text[head:nxt if nxt > 0 else len(text)].rstrip()
    lines = body.split("\n")
    while lines and (lines[0].startswith("## ") or not lines[0].strip()):
        lines.pop(0)
    while lines and lines[-1].strip() == "---":
        lines.pop()
    return lines


def title_text():
    """Release 标题 = `tag —— 更新总结`（取总结第一行，剥粗体标记）。"""
    for ln in summary_lines():
        t = ln.strip().replace("**", "").strip()
        if t:
            return "%s —— %s" % (TAG, t)
    return TAG


def notes_text():
    """Release 正文 = 更新总结打头，尾部免责声明 + 一行下载说明。"""
    lines = summary_lines()
    summary = "\n".join(lines).strip()
    (zip_name,) = (a for _, a in b.RELEASE_ASSETS)
    tail = (
        "\n---\n\n"
        "> ⚠️ 使用前请先自己备份存档（游戏根目录下的 `save.rvdata2`）。"
        "本工具是第三方工具，与游戏作者无关；游戏本体及其素材版权归原作者所有。\n\n"
        "下载：只下 Assets 里的 **`%s`**（唯一附件），解压后双击 `%s` 即可；"
        "别只把 exe 单独拖出来，依赖要跟它在同一目录。\n"
        % (zip_name, b.EXE_NAME + ".exe")
    )
    return (summary + "\n" if summary else "") + tail


def main():
    argv = sys.argv[1:]
    dry = "--dry" in argv
    upload_only = "--upload-only" in argv
    # 版本号是 `2.201-beta.N` 这种标准 SemVer 预发布形状，GitHub 本会自动标
    # Pre-release；这里再显式给一次（见 build.py 的 APP_PRERELEASE），
    # 不依赖平台推断。`--no-prerelease` 可以临时关掉。
    prerelease = b.APP_PRERELEASE and "--no-prerelease" not in argv
    print("版本 %s → tag %s%s" % (b.APP_VERSION, TAG,
                                  "（Pre-release）" if prerelease else ""))
    title = title_text()
    print("Release 标题：%s" % title)
    files = stage_assets()
    # notes 也放临时目录：仓库路径里的 `[]` 会让 gh 把 --notes-file 当 glob 处理
    notes = os.path.join(os.path.dirname(files[0]), "_notes.md")
    open(notes, "w", encoding="utf-8", newline="\n").write(notes_text())

    cmd = ["gh", "release", "upload", TAG] + files + ["--clobber"]
    if not upload_only:
        # --target 必须显式给：本仓库 main（尝鲜版 v0.x 线）和 beta（内测版线）
        # 共用同一个仓库，漏了它 tag 会落在「当前 HEAD」上 —— 从哪个分支跑就发哪条线，
        # 很容易把内测版的 tag 误打到 main 上。
        cmd = ["gh", "release", "create", TAG,
               "--target", b.APP_VERSION_LINE,
               "--title", title,
               "--notes-file", notes] + files
        if prerelease:
            cmd.insert(4, "--prerelease")
    print("将执行：gh release %s %s …" % ("upload" if upload_only else "create", TAG))
    if dry:
        print("--dry，未执行")
        return 0
    p = subprocess.run(cmd, cwd=ROOT)
    if p.returncode != 0:
        print("[NG] gh 返回 %d（Release 已存在就加 --upload-only）" % p.returncode)
    return p.returncode


if __name__ == "__main__":
    sys.exit(main())
