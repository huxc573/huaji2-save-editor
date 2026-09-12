# -*- coding: utf-8 -*-
"""探针 09：看 Logs/Battle 里的日志内容 + 全部存档头对比。"""
import os
import sys

sys.stdout.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
GAME = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))
_OUT = []


def print(*a):  # noqa: A001
    _OUT.append(" ".join(str(x) for x in a))


def flush(name="_out_09.txt"):
    open(os.path.join(HERE, name), "w", encoding="utf-8").write("\n".join(_OUT))


def main():
    battle = os.path.join(GAME, "Logs", "Battle")
    print("==== Logs/Battle 内容 ====")
    if os.path.isdir(battle):
        for d in sorted(os.listdir(battle)):
            p = os.path.join(battle, d)
            if os.path.isdir(p):
                files = sorted(os.listdir(p))
                print("  [%s] %d 个文件: %s" % (d, len(files), files[:10]))
                for f in files[:6]:
                    fp = os.path.join(p, f)
                    data = open(fp, "rb").read()
                    print("      %-22s %-8d head=%s" % (
                        f, len(data), data[:24].hex(" ")))
                    if len(data) > 40 and data[:2] == b"\x04\x08":
                        print("        -> 明文 Marshal! 后面 64 字节: %s" % (
                            data[40:104].hex(" ")))
    print("\n==== 全部存档头部对比 ====")
    cands = [("save.rvdata2", os.path.join(GAME, "save.rvdata2"))]
    ad = os.path.join(GAME, "AutoSave")
    if os.path.isdir(ad):
        for f in sorted(os.listdir(ad)):
            cands.append(("AutoSave/" + f, os.path.join(ad, f)))
    for rel, p in cands:
        d = open(p, "rb").read(32)
        print("  %-28s %s" % (rel, d.hex(" ")))

    print("\n==== 跨文件 8 字节块重合度（ECB 判据） ====")
    def blocks(path, kap=400000):
        data = open(path, "rb").read()
        return [data[i:i + 8] for i in range(0, min(len(data), kap) - 7, 8)]

    a = blocks(os.path.join(GAME, "save.rvdata2"))
    b = blocks(os.path.join(GAME, "AutoSave", "save00.rvdata2"))
    c = blocks(os.path.join(GAME, "Data", "System.rvdata2"))
    sa, sb, sc = set(a), set(b), set(c)
    print("  save 块数=%d 唯一=%d" % (len(a), len(sa)))
    print("  auto0 块数=%d 唯一=%d" % (len(b), len(sb)))
    print("  system 块数=%d 唯一=%d" % (len(c), len(sc)))
    print("  save ∩ auto0 = %d   save ∩ system = %d   auto0 ∩ system = %d" % (
        len(sa & sb), len(sa & sc), len(sb & sc)))

    flush()


if __name__ == "__main__":
    main()
