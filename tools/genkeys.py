# -*- coding: utf-8 -*-
"""生成"密钥候选"列表，然后用 XJCodec32.exe brute 批量试。

候选来源（都写成 UTF-8 文本行；二进制用 hex: 前缀）：
  1. main.dll / Game.exe 解壳镜像里的所有 ASCII 串（长度 1..64）
  2. 上面的 UTF-16LE 串
  3. 游戏各文本文件里的串（Config.ini / Game.ini / main.rvdata2 脚本 / was.info 里的中文词）
  4. main.dll 数据区里所有 8/16/24/32 字节窗口（hex:）
  5. 上面这些串的前缀/后缀片段

用法： python tools/genkeys.py [--windows] [--limit N]
结果： tools/_genkeys.txt（候选数）+ tools/_brute.txt（命中情况）
"""
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GAME = os.path.normpath(os.path.join(ROOT, "..", "..", ".."))
HOST = os.path.join(ROOT, "src", "XJCodec32.exe")
DLL = os.path.join(GAME, "System", "main.dll")
DUMP = os.path.join(HERE, "_ours_main.bin")
KEYS = os.path.join(HERE, "_keys.txt")
LOG = os.path.join(HERE, "_brute.txt")
TARGETS = [
    os.path.join(GAME, "Data", "Scripts.rvdata2"),
    os.path.join(GAME, "save.rvdata2"),
    os.path.join(GAME, "AutoSave", "save00.rvdata2"),
]

# 手工补充的高可能性候选
EXTRA = [
    "761205", "a36839d89d4822fcd7461364c46c4a42",
    "80c6d0789fc7fa10b29a62324e051659",
    "dd25855ac39d32da033902fc58fa210b",
    "System/main.dll", "System\\main.dll", "main.dll", "System/main",
    "RGSS301.dll", "System\\RGSS301.dll",
    "save.rvdata2", "AutoSave/save00.rvdata2",
    "Data/main.rvdata2", "Data/Scripts.rvdata2", "Data\\Scripts.rvdata2",
    "画迹2：缘起凡尘", "【画迹2：缘起凡尘】", "画迹", "huaji", "huaji2",
    "qqeat", "QQEat", "was", "was.info", "xjy", "xjy.11",
    "7612050", "7612051", "76120", "7612056",
]


def ascii_strings(data, minlen=1, maxlen=64):
    out = set()
    for m in re.finditer(rb"[\x20-\x7E]{%d,}" % minlen, data):
        s = m.group()
        if len(s) <= maxlen:
            out.add(s.decode("ascii", "replace"))
        for L in (4, 6, 8, 10, 12, 16, 20):
            if len(s) >= L:
                out.add(s[:L].decode("ascii", "replace"))
    return out


def utf16_strings(data, minlen=3):
    out = set()
    for m in re.finditer(rb"(?:[\x20-\x7E]\x00){%d,}" % minlen, data):
        try:
            out.add(m.group().decode("utf-16-le"))
        except Exception:
            pass
    return out


def main():
    argv = sys.argv[1:]
    want_win = "--windows" in argv
    limit = 0
    if "--limit" in argv:
        limit = int(argv[argv.index("--limit") + 1])

    dump = open(DUMP, "rb").read()
    keys = set()

    # 1+2. dll 镜像
    keys |= ascii_strings(dump)
    keys |= utf16_strings(dump)
    # 3. 其它文件
    for rel in ("System/main.dll", "Game.exe", "Config.ini", "Game.ini",
                "Data/main.rvdata2"):
        p = os.path.join(GAME, rel.replace("/", os.sep))
        if os.path.exists(p):
            d = open(p, "rb").read()
            keys |= ascii_strings(d)
            keys |= utf16_strings(d)
    # main.rvdata2 里的脚本正文
    raw = open(os.path.join(GAME, "Data", "main.rvdata2"), "rb").read()
    m = re.search(rb"x\x9c", raw)
    if m:
        import zlib
        try:
            code = zlib.decompressobj().decompress(raw[m.start():])
            keys.add(code.decode("utf-8", "replace"))
            keys.add(code.decode("utf-8", "replace").strip())
        except Exception:
            pass
    # was.info 里的中文词
    wi = os.path.join(GAME, "was.info")
    if os.path.exists(wi):
        d = open(wi, "rb").read()
        for mm in re.finditer(rb"[\xe4-\xe9][\x80-\xbf]{2}"
                              rb"(?:[\xe4-\xe9][\x80-\xbf]{2}){1,7}", d):
            keys.add(mm.group().decode("utf-8", "replace"))

    # 4. 数据区窗口
    if want_win:
        for start, end in ((0x0A0000, 0x143000),):
            for off in range(start, min(end, len(dump)) - 8):
                w = dump[off:off + 8]
                if w.count(0) >= 6:
                    continue
                keys.add("hex:" + w.hex())
        # 16 字节窗口只在疑似"常量区"扫
        for off in range(0x0F5000, 0x0F6000):
            for L in (16, 24):
                w = dump[off:off + L]
                if len(w) == L and w.count(0) < L - 2:
                    keys.add("hex:" + w.hex())

    keys = [k for k in keys if k and len(k) <= 128]
    keys = sorted(set(keys) | set(EXTRA))
    if limit:
        keys = keys[:limit]
    with open(KEYS, "w", encoding="utf-8") as f:
        f.write("\n".join(keys) + "\n")
    print("候选数 = %d" % len(keys))

    if "--keys-only" in argv:
        return

    sys.path.insert(0, HERE)
    from run_brute import run_brute  # noqa: E402

    hits = run_brute(KEYS, TARGETS, os.path.join(HERE, "_brute"), LOG)
    print("hits = %r" % hits)


if __name__ == "__main__":
    main()
