# -*- coding: utf-8 -*-
"""探针：`Babies.remove()` 到底有没有落盘？（只碰副本，不碰真档）

复现 test_baby.py 的关键几步：加一只 → 存 → 删那只 → 存 → 重读。
并逐个补上测试里多做的动作，定位是哪一步让「删」看起来没落盘。
"""
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.stdout.reconfigure(errors="replace")

import babies              # noqa: E402
import game                # noqa: E402
import marshal_ruby as M   # noqa: E402
import paths               # noqa: E402
import save                # noqa: E402


def _tail(B, g, actor, n=3):
    rows = g.babies(actor)
    return len(rows), [B.display_name(x) for _i, x in rows][-n:]


def main():
    real = paths.save_path()
    if not os.path.exists(real):
        print("找不到存档 %s，跳过" % real)
        return 0
    work = os.path.join(HERE, "_probe_remove")
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work, exist_ok=True)
    path = os.path.join(work, "copy.rvdata2")
    shutil.copyfile(real, path)

    # ---- ①最朴素的：加 → 存 → 删 → 存
    sv = save.SaveDoc(path)
    g = game.GameEditor(sv)
    B = babies.Babies(g)
    actor = sv.actors()[0][1]
    n0, tail0 = _tail(B, g, actor)
    print("① 原始          %d 只  末尾=%s" % (n0, tail0))
    B.add(actor, 21)
    sv.doc.save()
    sv2 = save.SaveDoc(path)
    g2 = game.GameEditor(sv2)
    B2 = babies.Babies(g2)
    a2 = sv2.actors()[0][1]
    n1, tail1 = _tail(B2, g2, a2)
    print("② 加一只后重读   %d 只  末尾=%s  (+%d)" % (n1, tail1, n1 - n0))
    B2.remove(a2, n1 - 1)
    print("   内存里删完     %d 只" % len(g2.babies(a2)))
    sv2.doc.save()
    sv3 = save.SaveDoc(path)
    g3 = game.GameEditor(sv3)
    B3 = babies.Babies(g3)
    a3 = sv3.actors()[0][1]
    n2, tail2 = _tail(B3, g3, a3)
    print("③ 删完重读       %d 只  末尾=%s  %s"
          % (n2, tail2, "OK" if n2 == n1 - 1 else "**NG**（该 %d）" % (n1 - 1)))

    # ---- ④多一步 set_active 再删
    svA = save.SaveDoc(path)
    gA = game.GameEditor(svA)
    BA = babies.Babies(gA)
    aA = svA.actors()[0][1]
    BA.add(aA, 21)
    nA = len(gA.babies(aA))
    BA.set_active(aA, nA - 1)
    BA.remove(aA, nA - 1)
    svA.doc.save()
    svB = save.SaveDoc(path)
    gB = game.GameEditor(svB)
    aB = svB.actors()[0][1]
    nB = len(gB.babies(aB))
    print("④ set_active+删+存 %d 只（应 %d）%s"
          % (nB, nA - 1, "OK" if nB == nA - 1 else "**NG**"))

    # ---- ⑤先做 @baby 链接实验，再加再删
    svC = save.SaveDoc(path)
    gC = game.GameEditor(svC)
    BC = babies.Babies(gC)
    aC = svC.actors()[0][1]
    BC.add(aC, 21)
    nC = len(gC.babies(aC))
    _b0 = save._deref(save.ivar(aC, "@babys").items[0])
    _lk = M.LinkNode(0)
    _lk.target = _b0
    game.set_ivar(aC, "@baby", _lk)
    svC.doc.mark_structural()
    svC.doc.save()
    BC.remove(aC, nC - 1)
    print("   内存里删完     %d 只" % len(gC.babies(aC)))
    svC.doc.save()
    svD = save.SaveDoc(path)
    gD = game.GameEditor(svD)
    aD = svD.actors()[0][1]
    nD = len(gD.babies(aD))
    print("⑤ 链接实验+删+存 %d 只（应 %d）%s"
          % (nD, nC - 1, "OK" if nD == nC - 1 else "**NG**"))

    shutil.rmtree(work, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
