# -*- coding: utf-8 -*-
r"""发 GitHub Release：按 `build.py` 里的命名规则准备好附件，再交给 `gh`。

    python tools/release.py                 # 创建/更新 v<当前版本> 的 Release
    python tools/release.py --upload-only   # Release 已存在，只重传附件
    python tools/release.py --dry           # 只打印要做什么，不动手

附件命名（**唯一来源在 tools/build.py**，别在这儿手敲）：
    huaji2-save-editor-v0.6.0.zip   发行包 = 主程序 + XJCodec32.exe + 使用说明
    ⚠ **只有一个附件**：宿主必须跟主程序一起到用户手里（散着挂总有人只下主程序，
      然后报「打不开」）。Release 上只上传这一个 zip，别再加别的。

发版日期只写在 CHANGELOG 的版本段标题里（形如 `## v0.6.1 · 261003 19:58`，
`YYMMDD HH:MM`），Release 的**标题与正文首行都从它取** —— 两处都得带日期，
只写日期（不写时分）不合格。

Release 正文 = **段标题（含发版日期）打头** → CHANGELOG 本版本段正文 →
`---` → 免责声明引用 → 一行下载说明（与画迹1 同一套规则，别往正文里堆下载说明）。
Release 标题 = `<段标题> —— <更新总结首行>`。
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
    r"""CHANGELOG 里本版本段 → `(标题, 正文)`；找不到返回 `("", "")`。

    标题形如 `v0.6.1 · 261003 19:58` —— **发版日期只写在这一处**（YYMMDD HH:MM，
    写到分钟），Release 的标题与正文首行都从它取，省得三个地方各写一遍写岔。
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
    lines = text[eol + 1:nxt if nxt > 0 else len(text)].rstrip().split("\n")
    while lines and lines[-1].strip() == "---":
        lines.pop()
    return heading, "\n".join(lines).rstrip()


def title_text():
    """Release 标题 = `<CHANGELOG 段标题> —— <更新总结首行剥粗体>`。"""
    heading, body = changelog_section()
    for ln in body.split("\n"):
        t = ln.strip().replace("**", "").strip()
        if t:
            return "%s —— %s" % (heading or TAG, t)
    return heading or TAG


def notes_text():
    """Release 正文 = 段标题（带发版日期）打头，尾部免责声明 + 一行下载说明。"""
    heading, body = changelog_section()
    (zip_name,) = (a for _, a in b.RELEASE_ASSETS)
    head = ("**%s**\n\n" % heading) if heading else ""
    tail = (
        "\n---\n\n"
        "> ⚠️ 使用前请先自己备份存档（游戏根目录下的 `save.rvdata2`）。"
        "本工具是第三方工具，与游戏作者无关；游戏本体及其素材版权归原作者所有。\n\n"
        "下载：只下 Assets 里的 **`%s`**（唯一附件），解压后双击 `%s` 即可；"
        "别只把 exe 单独拖出来，依赖要跟它在同一目录。\n"
        % (zip_name, b.EXE_NAME + ".exe")
    )
    return head + (body + "\n" if body else "") + tail


def main():
    argv = sys.argv[1:]
    dry = "--dry" in argv
    upload_only = "--upload-only" in argv
    print("版本 %s → tag %s" % (b.APP_VERSION, TAG))
    title = title_text()
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
