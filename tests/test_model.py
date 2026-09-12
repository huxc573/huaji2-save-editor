# -*- coding: utf-8 -*-
"""语义层 / 编辑引擎回归测试（用游戏自带的明文 Marshal 文件当样本）。

* Doc 能打开明文文件并给出摘要
* set_value 改标量后，写出的字节里只有目标区间变了
* 自包含序列化不破坏对象链接

用法： python tests/test_model.py
"""
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.stdout.reconfigure(errors="replace")

import xj_env  # noqa: E402
import xj_edit  # noqa: E402
import xj_marshal as M  # noqa: E402
import xj_model  # noqa: E402

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


def plaintext_sample():
    game = xj_env.find_game_dir()
    if not game:
        return None
    ad = os.path.join(game, "Logs", "Battle")
    if os.path.isdir(ad):
        for d in sorted(os.listdir(ad)):
            p = os.path.join(ad, d, "Battle.bt2")
            if os.path.exists(p):
                return p
    return None


def main():
    print("== 内置：区间补丁 ==")
    buf = (b'\x04\x08{\x08'
           b':\x06a' b'i\x06'
           b':\x06b' b'"\x06x'
           b':\x06c' b'[\x08' b'i\x06' b'i\x07' b'i\x08')
    objs = M.parse_stream(buf)
    h = objs[0]['node']
    v = h.pairs[0][1]
    hp = h.pairs[0][0]
    check(hp.name == 'a' and v.value == 1, "定位到 :a => 1")
    eng = xj_edit.PatchEngine(buf)
    eng.set_scalar(v, 100)
    new = eng.apply()
    check(len(new) == len(buf), "改标量后字节数不变（同宽度）")
    check(new != buf, "字节确实变了")
    h2 = M.parse_stream(new)[0]['node']
    check(h2.pairs[0][1].value == 100, "改后读回 = 100")
    check(h2.pairs[2][1].items[1].value == 2, "其它字段没被动到")
    # 同一个节点再改一次：应覆盖上一次补丁，而不是叠加
    eng.set_scalar(v, 7)
    new = eng.apply()
    h2b = M.parse_stream(new)[0]['node']
    check(h2b.pairs[0][1].value == 7, "同一节点改两次以最后一次为准")
    check(len(new) == len(buf), "重复改同宽度仍然等长")

    print("\n== 内置：变宽标量 ==")
    eng = xj_edit.PatchEngine(buf)
    eng.set_scalar(v, 70000)
    new = eng.apply()
    h3 = M.parse_stream(new)[0]['node']
    check(h3.pairs[0][1].value == 70000, "70000 能写回")
    check(h3.pairs[1][0].name == 'b' and h3.pairs[2][1].items[0].value == 1,
          "变宽后后续字段仍然正确（区间补丁生效）")

    print("\n== Doc：打开明文文件 ==")
    p = plaintext_sample()
    if not p:
        print("  [--] 没有找到明文样本（跳过）")
    else:
        doc = xj_model.Doc(p)
        check(len(doc.objects) >= 1, "解析出 %d 个顶层对象" % len(doc.objects))
        check("顶层对象数" in doc.summary(), "摘要正常")
        # 找一个整数标量改掉再存到临时文件
        tmp = tempfile.mkdtemp(prefix="xj_model_")
        dst = os.path.join(tmp, "out.rvdata2")
        shutil.copyfile(p, dst)
        d2 = xj_model.Doc(dst)
        target = find_int(d2.top_level()[0], 3)
        if target is None:
            print("  [--] 样本里没找到可改的整数（跳过）")
        else:
            old = target.value
            d2.set_value(target, old + 1)
            d2.save(dst, backup=False)
            d3 = xj_model.Doc(dst)
            t2 = find_int(d3.top_level()[0], 3)
            check(t2 is not None and t2.value == old + 1,
                  "改值写回并重新读回（%s -> %s）" % (old, old + 1))
        shutil.rmtree(tmp, ignore_errors=True)

    print("\n==== 通过 %d, 失败 %d ====" % (OK, NG))
    sys.exit(1 if NG else 0)


def find_int(node, depth):
    """在树里找第一个 IntNode。"""
    if depth <= 0:
        return None
    node = node.target if isinstance(node, M.LinkNode) and node.target is not None else node
    if isinstance(node, M.IntNode):
        return node
    kids = []
    if isinstance(node, M.ArrayNode):
        kids = node.items
    elif isinstance(node, M.HashNode):
        kids = [v for _, v in node.pairs] + [k for k, _ in node.pairs]
    elif isinstance(node, (M.ObjNode, M.StructNode)):
        kids = [v for _, v in node.ivars]
    for k in kids:
        r = find_int(k, depth - 1)
        if r is not None:
            return r
    return None


if __name__ == "__main__":
    main()
