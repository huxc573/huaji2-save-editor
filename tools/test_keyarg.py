# -*- coding: utf-8 -*-
"""关键判定实验：

A) decryption_file 的第 3 个参数到底是不是"口令/密钥"？
   交叉验证：用 K1 加密、用 K2 解密。
     解不出来 -> K 参与密钥派生（是密钥）
     解得出来 -> K 只是旁路标志

B) 试 decryption_buff / encryption_buff 的各种参数组合，看能不能解开游戏文件
   （如果游戏文件是用 buff 版写的，file 版会解不开——那就能解释 0 字节）

结果： tools/_keyarg.txt
"""
import os
import shutil
import subprocess
import sys

sys.stdout.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GAME = os.path.normpath(os.path.join(ROOT, "..", "..", ".."))
DLL = os.path.join(GAME, "System", "main.dll")
HOST = os.path.join(ROOT, "probes", "xjhost32b.exe")
WORK = os.path.join(HERE, "_ka")
LOG = os.path.join(HERE, "_keyarg.txt")
SCRIPT = os.path.join(WORK, "script.txt")


def run_script(lines, tag):
    with open(SCRIPT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    try:
        p = subprocess.run([HOST, "script", DLL, SCRIPT], capture_output=True,
                           timeout=180, cwd=GAME)
        txt = (p.stdout or b"").decode("utf-8", "replace")
        rc = p.returncode
    except subprocess.TimeoutExpired:
        txt, rc = "<超时>", "timeout"
    return txt, rc


def main():
    if os.path.isdir(WORK):
        shutil.rmtree(WORK, ignore_errors=True)
    os.makedirs(WORK)
    L = []

    plain = os.path.join(WORK, "plain.bin")
    open(plain, "wb").write(bytes(range(256)) * 4)

    # ---------------- A. 第 3 参数是不是密钥
    L.append("==== A. 第 3 参数的性质 ====")
    tests = [("", ""), ("", "1"), ("1", "2"), ("abc", "abd"),
             ("a36839d89d4822fcd7461364c46c4a42", "")]
    for k1, k2 in tests:
        c = os.path.join(WORK, "c.bin")
        d = os.path.join(WORK, "d.bin")
        for f in (c, d):
            if os.path.exists(f):
                os.remove(f)
        txt, rc = run_script([
            "encryption_file;s%s;s%s;s%s" % (plain, c, k1),
            "decryption_file;s%s;s%s;s%s" % (c, d, k2),
        ], "k1=%r k2=%r" % (k1, k2))
        same = (os.path.exists(d) and open(d, "rb").read() == open(plain, "rb").read())
        sz = os.path.getsize(d) if os.path.exists(d) else -1
        L.append("  加密用 %-34r 解密用 %-8r -> 输出 %-6d 还原=%s" % (
            k1, k2, sz, "是" if same else "否"))
    L.append("  结论：%s" % (
        "第 3 参数**不参与密钥**（换一个也能还原）" if False else "看上表：跨参数还原成功的行说明它只是旁路标志"))

    # ---------------- B. buff 版的各种组合
    L.append("\n==== B. decryption_buff 组合（目标：解开 Data/System.rvdata2） ====")
    src_game = os.path.join(GAME, "Data", "System.rvdata2")
    tgt = os.path.join(WORK, "buff_in.bin")
    shutil.copyfile(src_game, tgt)
    combos = [
        ["decryption_buff", "o%s,64" % (WORK + "\\o1.bin"), "s" + tgt],
        ["decryption_buff", "e", "s" + tgt],
        ["decryption_buff", "b" + tgt, "s" + tgt],
        ["decryption_buff", "o%s,64" % (WORK + "\\o2.bin"), "i0"],
        ["decryption_buff", "i0", "s" + tgt],
        ["encryption_buff", "o%s,64" % (WORK + "\\o3.bin"), "s" + tgt],
        ["encryption_buff", "b" + tgt, "s" + tgt],
    ]
    for c in combos:
        txt, rc = run_script([";".join(c)], " ".join(c)[:70])
        rets = [x.strip() for x in txt.splitlines() if "ret=" in x or "wrote" in x
                or "in-buf now" in x]
        after = open(tgt, "rb").read(12).hex(" ") if os.path.exists(tgt) else "<缺>"
        L.append("  %-70s rc=%-8s %s" % (" ".join(c)[:70], rc, " | ".join(rets)[:160]))
        L.append("      in 文件现状：%s" % after)
        # 复原
        shutil.copyfile(src_game, tgt)

    open(LOG, "w", encoding="utf-8").write("\n".join(L))
    print("done")


if __name__ == "__main__":
    main()
