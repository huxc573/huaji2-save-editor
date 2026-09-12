# -*- coding: utf-8 -*-
"""探针 21：安全批次爆破 decryption_file 的第 3 参数（只用字符串，分批防崩）。"""
import hashlib
import os
import re
import shutil
import subprocess
import sys
import zlib

sys.stdout.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
GAME = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))
DLL = os.path.join(GAME, "System", "main.dll")
HOST = os.path.join(HERE, "xjhost32.exe")
WORK = os.path.join(HERE, "_w21")
LOG = os.path.join(HERE, "_out_21.txt")


def log(*a):
    line = " ".join(str(x) for x in a)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def cands():
    out = [
        "", "0", "1", "4984", "310440", "4992", "310448", "save", "rvdata2",
        "data", "info", "was", "was.info", "qqeat", "QQEat", "xjy.11",
        "a36839d89d4822fcd7461364c46c4a42",
        "System.rvdata2", "Data/System.rvdata2", "Data\\System.rvdata2",
        "System/Game.md5", "Game.md5", "main.rvdata2", "Data/main.rvdata2",
        "海毛虫", "画迹", "画迹2", "缘起凡尘", "落日情缘", "hx", "hj", "huaji",
        "huaji2", "yqfz", "HUAJI", "wasinfo", "WAS", "WASINFO",
        "adf", "gfd", "123", "abc",
    ]
    for rel in ("Data/main.rvdata2", "Config.ini", "was.info", "System/Game.md5",
                "System/main.dll", "Game.ini"):
        p = os.path.join(GAME, rel.replace("/", os.sep))
        if not os.path.exists(p):
            continue
        d = open(p, "rb").read()
        out += [hashlib.md5(d).hexdigest(), hashlib.md5(d).hexdigest().upper(),
                hashlib.sha1(d).hexdigest()]
        out += [d[:8].decode("latin-1"), d[:16].decode("latin-1"),
                d[:32].decode("latin-1")]
    raw = open(os.path.join(GAME, "Data", "main.rvdata2"), "rb").read()
    m = re.search(rb"x\x9c", raw)
    if m:
        try:
            code = zlib.decompressobj().decompress(raw[m.start():])
            out += [code.decode("utf-8", "replace"),
                    code.decode("utf-8", "replace").strip(" \r\n"),
                    code.decode("utf-8", "replace").split("'")[1]]
        except Exception:
            pass
    # was.info 里的中文键
    wi = os.path.join(GAME, "was.info")
    if os.path.exists(wi):
        d = open(wi, "rb").read(4096)
        for mm in re.finditer(rb"[\xe4-\xe9][\x80-\xbf]{2}(?:[\xe4-\xe9][\x80-\xbf]{2}){1,7}", d):
            out.append(mm.group().decode("utf-8", "replace"))
    return [x for x in dict.fromkeys(out) if x is not None]


def main():
    if os.path.isdir(WORK):
        shutil.rmtree(WORK, ignore_errors=True)
    os.makedirs(WORK)
    open(LOG, "w", encoding="utf-8").write("")

    rel = "Data/System.rvdata2"
    lock = os.path.join(WORK, "in.bin")
    shutil.copyfile(os.path.join(GAME, rel.replace("/", os.sep)), lock)
    C = cands()
    log("候选 %d 个" % len(C))

    BATCH = 10
    for bi in range(0, len(C), BATCH):
        chunk = C[bi:bi + BATCH]
        lines = []
        jobs = []
        for j, s in enumerate(chunk):
            out = os.path.join(WORK, "o_%03d.bin" % (bi + j))
            if os.path.exists(out):
                os.remove(out)
            lines.append("decryption_file;s%s;s%s;s%s" % (lock, out, s))
            jobs.append((s, out))
        sp = os.path.join(HERE, "_script.txt")
        with open(sp, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        try:
            p = subprocess.run([HOST, "script", DLL, sp], cwd=GAME,
                               capture_output=True, timeout=180)
            rc = p.returncode
        except subprocess.TimeoutExpired:
            rc = "timeout"
        for s, out in jobs:
            if not os.path.exists(out):
                continue
            d = open(out, "rb").read(8)
            if len(d) >= 2 and d[0] == 4 and d[1] == 8:
                log("★★★ 命中! key=%r 输出=%d B %s" % (
                    s, os.path.getsize(out), d.hex(" ")))
            elif os.path.getsize(out) > 0:
                log("  非空 key=%r size=%d head=%s" % (s, os.path.getsize(out), d.hex(" ")))
        log("批次 %d..%d rc=%s" % (bi, bi + len(chunk) - 1, rc))
    log("完成")


if __name__ == "__main__":
    main()
