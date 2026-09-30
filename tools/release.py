# -*- coding: utf-8 -*-
r"""发 GitHub Release：按 `build.py` 里的命名规则准备好附件，再交给 `gh`。

    python tools/release.py                 # 创建/更新 v<当前版本> 的 Release
    python tools/release.py --upload-only   # Release 已存在，只重传附件
    python tools/release.py --dry           # 只打印要做什么，不动手

附件命名（**唯一来源在 tools/build.py**，别在这儿手敲）：
    huaji2-save-editor-v0.6.0.zip   发行包 = 主程序 + XJCodec32.exe + 使用说明
    ⚠ **只有一个附件**：宿主必须跟主程序一起到用户手里（散着挂总有人只下主程序，
      然后报「打不开」）。Release 上只上传这一个 zip，别再加别的。

Release 正文 = 一段固定的下载说明 + CHANGELOG.md 里对应版本的那一段，
标题与正文开头都带上 CHANGELOG 版本标题里的发版日期（写到分钟）。
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


def changelog_section():
    r"""CHANGELOG 里本版本的那一段 → `(标题, 正文)`；找不到返回 `("", "")`。

    标题形如 `v0.6.0 (2026-09-30 17:20)` —— **发版日期只写在这一处**（写到分钟），
    Release 的标题和正文开头都从这儿取，省得三个地方各写一遍写岔。
    """
    path = os.path.join(ROOT, "CHANGELOG.md")
    if not os.path.exists(path):
        return "", ""
    text = open(path, encoding="utf-8").read()
    head = text.find("## " + TAG)
    if head < 0:
        return "", ""
    eol = text.find("\n", head)
    if eol < 0:
        return text[head + 3:].strip(), ""
    heading = text[head + 3:eol].strip()
    nxt = text.find("\n## ", head + 1)
    return heading, text[eol + 1:nxt if nxt > 0 else len(text)].rstrip()


def release_title():
    """Release 标题：`v0.6.0 (2026-09-30 17:20) —— 见下方更新日志`。"""
    heading, _ = changelog_section()
    return "%s —— 见下方更新日志" % (heading or TAG)


def notes_text():
    """一段固定的下载说明 + CHANGELOG 里本版本的那一段（开头带发版日期）。"""
    heading, body = changelog_section()
    (zip_name,) = (a for _, a in b.RELEASE_ASSETS)
    extra = (
        ("**%s**\n\n" % heading if heading else "") +
        "## 下载 / 用法\n\n"
        "下这一个附件就行 —— 里面是完整的工具：\n\n"
        "* `%s` —— 解压出来直接双击 `画迹2存档工具.exe`，免安装。\n"
        "  包里已经带上 **XJCodec32.exe**（32 位加解密宿主，用来加载游戏的 "
        "`System/main.dll`，没有它读不了存档）和使用说明，不用再单独下别的。\n\n"
        "> 附件名用 ASCII（GitHub 对中文文件名会自动改名），跟仓库名保持一致 + 版本号。\n"
        "> 以前是 exe / USAGE.txt / XJCodec32.exe 三个附件，**总有人只下主程序**然后\n"
        "> 报「打不开 / 缺少依赖」—— 现在只挂一个包，漏不了。\n"
        % (zip_name,)
    )
    if not body:
        return extra
    return extra + "\n---\n\n## %s\n\n%s\n" % (heading, body)


def main():
    argv = sys.argv[1:]
    dry = "--dry" in argv
    upload_only = "--upload-only" in argv
    print("版本 %s → tag %s" % (b.APP_VERSION, TAG))
    title = release_title()
    print("Release 标题：%s" % title)
    files = stage_assets()
    # notes 也放临时目录：仓库路径里的 `[]` 会让 gh 把 --notes-file 当 glob 处理
    notes = os.path.join(os.path.dirname(files[0]), "_notes.md")
    open(notes, "w", encoding="utf-8", newline="\n").write(notes_text())

    cmd = ["gh", "release", "upload", TAG] + files + ["--clobber"]
    if not upload_only:
        cmd = ["gh", "release", "create", TAG,
               "--title", title,
               "--notes-file", notes] + files
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
