# -*- coding: utf-8 -*-
"""判定"密钥状态"到底有没有被密码用到。

做法：同一段明文分别在不写状态 / 写状态两种情况下加密，比较密文。
  不同 -> 这份状态确实喂进了密码（那就继续缩减到最小片段）
  相同 -> 状态与密码无关，要找的是别的东西

用法： python tools/test_state.py [state文件]
"""
import os
import shutil
import subprocess
import sys

sys.stdout.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GAME = os.path.normpath(os.path.join(ROOT, "..", "..", ".."))
HOST = os.path.join(ROOT, "src", "XJCodec32.exe")
DLL = os.path.join(GAME, "System", "main.dll")
STATE = os.path.join(ROOT, "src", "xj_state.txt")
WORK = os.path.join(HERE, "_ts")
LOG = os.path.join(HERE, "_test_state.txt")


def run(args, env=None):
    e = dict(os.environ)
    if env:
        e.update(env)
    p = subprocess.run([HOST] + args, capture_output=True, timeout=300, env=e,
                       cwd=GAME)
    return (p.stdout or b"").decode("utf-8", "replace")


def main():
    if os.path.isdir(WORK):
        shutil.rmtree(WORK, ignore_errors=True)
    os.makedirs(WORK)
    plain = os.path.join(WORK, "plain.bin")
    open(plain, "wb").write(bytes(range(256)) * 4)      # 1024 字节，固定内容

    bak = STATE + ".bak"
    has = os.path.exists(STATE)
    if has:
        shutil.copyfile(STATE, bak)

    results = {}
    try:
        for tag in ("nostate", "state"):
            if tag == "nostate":
                if os.path.exists(STATE):
                    os.remove(STATE)
            else:
                if has:
                    shutil.copyfile(bak, STATE)
            out = os.path.join(WORK, tag + ".bin")
            run(["encrypt", DLL, plain, out])
            results[tag] = open(out, "rb").read() if os.path.exists(out) else b""

        a, b = results["nostate"], results["state"]
        L = []
        L.append("state 文件 = %s (存在=%s)" % (STATE, has))
        L.append("无状态密文 长度=%d 头=%s" % (len(a), a[:16].hex(" ")))
        L.append("有状态密文 长度=%d 头=%s" % (len(b), b[:16].hex(" ")))
        L.append("两者相同 = %s" % (a == b))
        if a != b and a and b:
            nd = sum(1 for x, y in zip(a, b) if x != y)
            L.append("不同字节数 = %d / %d" % (nd, len(a)))
        L.append("\n=> 结论：%s" % (
            "这份状态**确实**参与密码运算" if a != b
            else "这份状态与密码无关（不是密钥状态）"))

        # 再验一次：有状态时能不能解密游戏原档
        for rel in ("Data/System.rvdata2", "save.rvdata2"):
            src = os.path.join(GAME, rel.replace("/", os.sep))
            out = os.path.join(WORK, "dec_" + rel.replace("/", "_"))
            txt = run(["decrypt", DLL, src, out])
            sz = os.path.getsize(out) if os.path.exists(out) else 0
            L.append("解密 %-20s -> %d 字节  %s" % (
                rel, sz, "★成功★" if sz else txt.strip().replace("\n", " | ")[:200]))
    finally:
        if has and os.path.exists(bak):
            shutil.copyfile(bak, STATE)
            os.remove(bak)

    open(LOG, "w", encoding="utf-8").write("\n".join(L))
    print("done")


if __name__ == "__main__":
    main()
