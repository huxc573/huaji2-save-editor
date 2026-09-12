# -*- coding: utf-8 -*-
"""xj_marshal 回归测试：解析 / 序列化 / 重编码。

测试样本优先用游戏自带的**明文** Marshal 文件：
  * Logs/Battle/<时间>/Battle.bt2   （VX Ace / Ruby 1.9 风格，含 i / : / [ / { / I / l）
  * Data/main.rvdata2               （引导脚本，70 字节）
找不到就退化成内置样本。

用法： python tests/test_marshal.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.stdout.reconfigure(errors="replace")

import xj_env  # noqa: E402
import xj_marshal as M  # noqa: E402

OK = 0
NG = 0


def check(cond, msg):
    global OK, NG
    if cond:
        OK += 1
        print("  [OK] %s" % msg)
    else:
        NG += 1
        print("  [NG] %s" % msg)


def samples():
    game = xj_env.find_game_dir()
    out = []
    if game:
        p = os.path.join(game, "Data", "main.rvdata2")
        if os.path.exists(p):
            out.append(p)
        ad = os.path.join(game, "Logs", "Battle")
        if os.path.isdir(ad):
            for d in sorted(os.listdir(ad)):
                p = os.path.join(ad, d, "Battle.bt2")
                if os.path.exists(p):
                    out.append(p)
                    break
    return out


def test_builtin():
    print("\n== 内置样本 ==")
    # Ruby 1.9(RGSS3) 风格： {:a=>1, :b=>"x", :c=>[1,2,3]}
    #   整数必须写成 'i' 前缀 + w_long
    src = (b'\x04\x08{\x08'
           b':\x06a' b'i\x06'
           b':\x06b' b'"\x06x'
           b':\x06c' b'[\x08' b'i\x06' b'i\x07' b'i\x08')
    objs = M.parse_stream(src)
    check(len(objs) == 1, "解析出 1 个顶层对象")
    node = objs[0]['node']
    check(node.type == '{', "顶层是 Hash")
    check(len(node.pairs) == 3, "Hash 有 3 项")
    # 序列化后能再解析
    again = M.parse_stream(M.serialize(node))
    check(again[0]['node'].type == '{', "自包含序列化后可再解析")
    check(len(again[0]['node'].pairs) == 3, "项数不变")


def test_file(path):
    print("\n== %s ==" % path)
    buf = open(path, "rb").read()
    check(buf[:2] == M.MARSHAL_MAGIC if hasattr(M, 'MARSHAL_MAGIC') else buf[:2] == b'\x04\x08',
          "头部是 04 08")
    objs = M.parse_stream(buf)
    check(len(objs) >= 1, "解析出 %d 个顶层对象" % len(objs))
    for i, o in enumerate(objs):
        node = o['node']
        check(node.start == (2 if o['head'] is not None else 0), "#%d 起点正确" % i)
    # 每个顶层对象都要能被重新序列化并再解析
    for i, o in enumerate(objs):
        blob = M.serialize(o['node'])
        again = M.parse_stream(blob)
        check(len(again) == 1, "#%d 自包含序列化/再解析" % i)


def test_long():
    print("\n== w_long 边界 ==")
    for v in (0, 1, 122, 123, 255, 256, 65535, 65536, 2 ** 31 - 1,
              -(2 ** 31), 2 ** 32 - 1):
        enc = M.encode_integer(v)
        node, pos, _ = M.parse_object(enc, 0, 0, [])
        check(pos == len(enc) and node.value == v,
              "整数 %d 编解码一致 (%s)" % (v, enc.hex()))
    for v in (2 ** 40, -(2 ** 40), 2 ** 63 + 1):
        enc = M.encode_integer(v)
        node, pos, _ = M.parse_object(enc, 0, 0, [])
        check(pos == len(enc) and node.value == v, "大整数 %d 编解码一致" % v)


def main():
    test_builtin()
    test_long()
    for p in samples():
        test_file(p)
    print("\n==== 通过 %d, 失败 %d ====" % (OK, NG))
    sys.exit(1 if NG else 0)


if __name__ == "__main__":
    main()
