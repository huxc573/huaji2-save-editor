# -*- coding: utf-8 -*-
"""检查 git 提交信息 / 仓库内容的编码与完整性（写结果到 _gitcheck.txt）。"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # 仓库根
GIT = r"D:\Dev\Git\cmd\git.exe"


def run(*args):
    p = subprocess.run([GIT] + list(args), cwd=HERE, capture_output=True)
    return p.stdout


def main():
    out = []
    msg = run("log", "-1", "--pretty=format:%B").decode("utf-8", "replace")
    out.append("=== 提交信息（UTF-8 解码） ===")
    out.append(msg)
    out.append("")
    subject = run("log", "-1", "--pretty=format:%s").decode("utf-8", "replace")
    ok = subject.startswith("v0.1") and "画迹2" in subject
    out.append("主题行: %s" % subject)
    out.append("编码正常: %s" % ("是" if ok else "否 (需要重写提交信息)"))

    out.append("")
    out.append("=== 标签 ===")
    out.append(run("tag", "-n1").decode("utf-8", "replace"))

    out.append("=== 工作区状态 ===")
    out.append(run("status", "--short", "--branch").decode("utf-8", "replace"))

    out.append("=== 文件数 / 是否含游戏数据 ===")
    files = run("ls-files").decode("utf-8", "replace").splitlines()
    out.append("已跟踪文件: %d" % len(files))
    bad = [f for f in files
           if f.lower().endswith((".dll", ".rvdata2", ".rxdata", ".ogg", ".png"))
           and not f.lower().endswith("xjcodec32.exe")]
    out.append("可疑（游戏数据/第三方库）: %s" % (bad or "无"))
    big = []
    for f in files:
        p = os.path.join(HERE, f)
        if os.path.exists(p) and os.path.getsize(p) > 400 * 1024:
            big.append("%s (%d KB)" % (f, os.path.getsize(p) // 1024))
    out.append("大于 400KB 的文件: %s" % (big or "无"))
    out.append("含 XJCodec32.exe: %s" % ("src/XJCodec32.exe" in files))

    with open(os.path.join(HERE, "_gitcheck.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    print("done")


if __name__ == "__main__":
    main()
