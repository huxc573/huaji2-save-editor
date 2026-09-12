# -*- coding: utf-8 -*-
"""在导出的游戏脚本（tools/_scripts/*.rb）里搜关键词 / 打印指定行。

中文关键词没法从命令行安全传进来（终端是 GBK），所以：
  * 关键词写在 tools/_keys.txt（UTF-8，一行一个），或用 `--kw 键1,键2`；
  * 结果用 `--out <文件>` 直接写 UTF-8 文件，**不要**经 PowerShell 管道
    （PS 5.1 控制台是 GBK，会把中文变成"UTF-8 字节当 GBK 读"的乱码）。

用法：
    python tools/grep_scripts.py --out tools/_g1.txt              # 用 _keys.txt 里的词
    python tools/grep_scripts.py --kw gold --out tools/_g1.txt
    python tools/grep_scripts.py --dump 40000 40300 --out tools/_d1.txt
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, "_scripts")


def script_files():
    if not os.path.isdir(SCRIPTS):
        return []
    fs = [os.path.join(SCRIPTS, n) for n in sorted(os.listdir(SCRIPTS))
          if n.endswith(".rb")]
    return sorted(fs, key=os.path.getsize, reverse=True)


def load(path):
    """返回 (utf8 行, gbk 行, 是否 UTF-8 更干净)。脚本大多是 UTF-8，个别段可能 GBK。"""
    raw = open(path, "rb").read()
    u = raw.decode("utf-8", "replace")
    g = raw.decode("gbk", "replace")
    return (u.split("\n"), g.split("\n"), u.count("\ufffd") <= g.count("\ufffd"))


def main():
    argv = sys.argv[1:]
    outf = kwarg = only = None
    rng = None
    while argv:
        a = argv.pop(0)
        if a == "--out":
            outf = argv.pop(0)
        elif a == "--kw":
            kwarg = argv.pop(0).split(",")
        elif a == "--file":
            only = argv.pop(0)
        elif a == "--dump":
            rng = (int(argv.pop(0)), int(argv.pop(0)))
        elif a == "--ctx":
            argv.pop(0)          # 值在下面统一重扫
            continue
        else:
            pass                 # 不认识的参数忽略
    # ctx 重扫一遍（上面 pop 掉了值，简单点：单独解析）
    ctx = 3
    if "--ctx" in sys.argv:
        ctx = int(sys.argv[sys.argv.index("--ctx") + 1])

    out = (open(outf, "w", encoding="utf-8") if outf
           else io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                 errors="replace"))
    files = script_files()
    if not files:
        out.write("[NG] 没有 %s，先跑 python tools/dump_scripts.py\n" % SCRIPTS)
        return 1

    if rng:
        lo, hi = rng
        for path in files:
            if only and only not in os.path.basename(path):
                continue
            u, g, use_u = load(path)
            lines = u if use_u else g
            out.write("### %s（%d 行，%s）\n"
                      % (os.path.basename(path), len(lines),
                         "UTF-8" if use_u else "GBK"))
            for j in range(max(0, lo - 1), min(len(lines), hi)):
                out.write("%6d| %s\n" % (j + 1, lines[j]))
        out.flush()
        if outf:
            out.close()
        return 0

    keys = kwarg or []
    if not keys:
        kf = os.path.join(HERE, "_keys.txt")
        if os.path.exists(kf):
            keys = [x.strip() for x in open(kf, encoding="utf-8")
                    if x.strip() and not x.startswith("#")]
    if not keys:
        out.write("用法见文件头注释\n")
        return 1
    out.write("关键词：%s\n" % "、".join(keys))
    for kw in keys:
        out.write("\n" + "=" * 78 + "\n### 关键词：%s\n" % kw)
        hits = 0
        for path in files:
            if only and only not in os.path.basename(path):
                continue
            u, g, use_u = load(path)
            for tag, lines in (("utf8", u), ("gbk", g)):
                for i, line in enumerate(lines):
                    if kw in line:
                        hits += 1
                        lo, hi = max(0, i - ctx), min(len(lines), i + ctx + 1)
                        out.write("--- %s[%s] : 第 %d 行\n"
                                  % (os.path.basename(path), tag, i + 1))
                        for j in range(lo, hi):
                            out.write("%s%6d| %s\n" % (">>" if j == i else "  ",
                                                       j + 1, lines[j][:200]))
                        out.write("   " + "-" * 68 + "\n")
                        if hits > 120:
                            break
                if hits > 120:
                    break
            if hits > 120:
                break
        out.write("（%s 命中 %d 处）\n" % (kw, hits))
    out.flush()
    if outf:
        out.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
