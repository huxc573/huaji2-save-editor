# -*- coding: utf-8 -*-
"""探针 20：爆破 decryption_file 的第 3 个参数（口令 / 类型标记 / 标志位）。

成功判据：解密结果以 04 08 开头（Ruby Marshal 4.8）。
"""
import os
import shutil
import subprocess
import sys

sys.stdout.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
GAME = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))
DLL = os.path.join(GAME, "System", "main.dll")
HOST = os.path.join(HERE, "xjhost32.exe")
WORK = os.path.join(HERE, "_w20")
LOG = os.path.join(HERE, "_out_20.txt")


def log(*a):
    line = " ".join(str(x) for x in a)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


STRINGS = [
    "", "save", "Save", "SAVE", "rvdata2", "data", "Data", "info", "was", "was.info",
    "System.rvdata2", "Data/System.rvdata2", "Data\\System.rvdata2", "System",
    "Game.md5", "System/Game.md5", "qqeat", "QQEat", "xjy.11", "was.info",
    "a36839d89d4822fcd7461364c46c4a42", "A36839D89D4822FCD7461364C46C4A42",
    "script", "Scripts", "Data/Scripts.rvdata2", "Data/main.rvdata2", "main",
    "huaji", "huaji2", "画迹", "画迹2", "缘起凡尘", "yqfz", "hx",
    "111111", "123456", "000000", "admin", "password", "888888", "666666",
    "2026", "2025", "2024", "save.rvdata2", "AutoSave", "Logs", "Game.ini",
    "Config.ini", "./Config.ini", "System/main.dll", "RGSS301.dll",
    "0", "1", "2", "3", "9", "26", "200", "256", "1024",
]
INTS = [0, 1, 2, 3, 4, 5, 6, 7, 8, 16, 32, 64, 100, 200, 255, 256, 1024,
        0x80000000, 0x80000004]

FILES = ["Data/System.rvdata2", "Data/Actors.rvdata2", "save.rvdata2"]


def derived_candidates():
    """由游戏的明文文件派生候选密钥。"""
    import hashlib
    out = []
    for rel in ("Data/main.rvdata2", "Config.ini", "Game.ini", "was.info",
                "System/main.dll", "System/Game.md5"):
        p = os.path.join(GAME, rel.replace("/", os.sep))
        if not os.path.exists(p):
            continue
        d = open(p, "rb").read()
        for tag, h in (("md5", hashlib.md5(d).hexdigest()),
                       ("sha1", hashlib.sha1(d).hexdigest()),
                       ("sha256", hashlib.sha256(d).hexdigest())):
            out.append(h)
            out.append(h.upper())
        if rel == "Data/main.rvdata2":
            import re
            import zlib
            m = re.search(rb"x\x9c", d)
            if m:
                try:
                    code = zlib.decompressobj().decompress(d[m.start():])
                    out.append(code.decode("utf-8", "replace"))
                    out.append(code.decode("utf-8", "replace").strip())
                    out.append(hashlib.md5(code).hexdigest())
                    out.append(code[code.rfind(b"'") + 1:].decode("utf-8", "replace"))
                except Exception:
                    pass
    # Config.ini 里的 md5 值
    cfg = os.path.join(GAME, "Config.ini")
    if os.path.exists(cfg):
        for line in open(cfg, "r", encoding="utf-8", errors="replace"):
            if "=" in line:
                v = line.split("=", 1)[1].strip()
                if v:
                    out.append(v)
    return [x for x in dict.fromkeys(out) if x]


def main():
    if os.path.isdir(WORK):
        shutil.rmtree(WORK, ignore_errors=True)
    os.makedirs(WORK)
    open(LOG, "w", encoding="utf-8").write("")

    locks = {}
    for i, rel in enumerate(FILES):
        src = os.path.join(GAME, rel.replace("/", os.sep))
        lock = os.path.join(WORK, "f%d.bin" % i)
        shutil.copyfile(src, lock)
        locks[rel] = lock

    STRINGS.extend(derived_candidates())
    log("候选字符串 %d 个" % len(STRINGS))
    lines = []
    jobs = []  # (label, fileidx, outpath)
    idx = 0
    for rel in FILES:
        base = rel.split("/")[-1]
        extra = [base, rel, rel.replace("/", "\\"),
                 os.path.join(GAME, rel.replace("/", os.sep)),
                 rel.lower(), base.lower(), base.replace(".rvdata2", "")]
        for s in STRINGS + extra:
            out = os.path.join(WORK, "o%04d.bin" % idx)
            jobs.append(("s", s, rel, out))
            lines.append("decryption_file;s%s;s%s;s%s" % (locks[rel], out, s))
            idx += 1
        for v in INTS:
            out = os.path.join(WORK, "o%04d.bin" % idx)
            jobs.append(("i", v, rel, out))
            lines.append("decryption_file;s%s;s%s;i%d" % (locks[rel], out, v))
            idx += 1
        # NULL 第三参
        out = os.path.join(WORK, "o%04d.bin" % idx)
        jobs.append(("e", None, rel, out))
        lines.append("decryption_file;s%s;s%s;e" % (locks[rel], out))
        idx += 1

    log("共 %d 个组合，一次调用" % len(jobs))
    sp = os.path.join(HERE, "_script.txt")
    with open(sp, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    p = subprocess.run([HOST, "script", DLL, sp], cwd=GAME,
                       capture_output=True, timeout=1800)
    log("host rc=%s" % p.returncode)

    hits = 0
    for kind, val, rel, out in jobs:
        if not os.path.exists(out):
            continue
        d = open(out, "rb").read(8)
        if len(d) >= 2 and d[0] == 4 and d[1] == 8:
            n = os.path.getsize(out)
            log("★★ 命中! %s %-14s 文件=%s 输出=%d B %s" % (
                kind, repr(val), rel, n, d.hex(" ")))
            hits += 1
        elif os.path.getsize(out) > 0:
            log("  (非空但不像 Marshal) %s %-14s 文件=%s 大小=%d head=%s" % (
                kind, repr(val), rel, os.path.getsize(out), d.hex(" ")))
    log("命中 %d 个" % hits)
    if not hits:
        log("全部失败：第 3 个参数不是口令/标记")


if __name__ == "__main__":
    main()
