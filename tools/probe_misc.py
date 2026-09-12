# -*- coding: utf-8 -*-
"""零散小探针：
  1) Config.ini 里的 md5 到底是哪个文件的（判断改游戏文件会不会被抓）
  2) was.info 开头那 6 个"不像 Marshal"的字节后面，是不是标准 Marshal
  3) 顺带看看 was.info 的顶层结构
结果： tools/_misc.txt
"""
import hashlib
import os
import sys

sys.stdout.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GAME = os.path.normpath(os.path.join(ROOT, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
LOG = os.path.join(HERE, "_misc.txt")

import xj_marshal as M  # noqa: E402


def main():
    L = []
    L.append("== 1. md5 对照 ==")
    target = "a36839d89d4822fcd7461364c46c4a42"
    cands = ["Data/main.rvdata2", "Game.exe", "Game.ini", "Config.ini", "was.info",
             "save.rvdata2", "System/main.dll", "System/RGSS301.dll",
             "Data/Scripts.rvdata2", "Data/main.rvdata2"]
    hit = None
    for rel in dict.fromkeys(cands):
        p = os.path.join(GAME, rel.replace("/", os.sep))
        if not os.path.exists(p):
            continue
        d = open(p, "rb").read()
        h = hashlib.md5(d).hexdigest()
        mark = "  ★ 就是它！" if h == target else ""
        if h == target:
            hit = rel
        L.append("  %-24s %s%s" % (rel, h, mark))
    L.append("  Config.ini 里的 md5 = %s" % target)
    L.append("  结论：%s" % ("命中的是 " + hit if hit else "以上都不是（另有来源）"))

    L.append("\n== 2. was.info 结构 ==")
    p = os.path.join(GAME, "was.info")
    d = open(p, "rb").read()
    L.append("  大小 = %d  头 16 字节 = %s" % (len(d), d[:16].hex(" ")))
    for off in (0, 2, 6):
        try:
            objs = M.parse_stream(d[off:])
            kinds = [o['node'].type for o in objs]
            L.append("  从偏移 %d 解析 -> %d 个顶层对象, 类型 %s" % (off, len(objs), kinds))
            if objs:
                node = objs[0]['node']
                L.append("      #0 类型=%s 描述=%s" % (node.type, getattr(node, 'text', lambda: '')()))
            # 看是否解析到文件末尾
            last = objs[-1]
            L.append("      最后对象结束位置 = %d / %d" % (last['node'].end, len(d) - off))
        except Exception as e:  # noqa: BLE001
            L.append("  从偏移 %d 解析失败：%s" % (off, e))
    L.append("  前 6 字节 = %s" % d[:6].hex(" "))

    open(LOG, "w", encoding="utf-8").write("\n".join(L))
    print("done")


if __name__ == "__main__":
    main()
