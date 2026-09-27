# -*- coding: utf-8 -*-
"""一次性：看 @exp 这个 Hash 到底有哪些 key，以及 @class_id 是什么。"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import paths  # noqa: E402
import game  # noqa: E402
import marshal_ruby as M  # noqa: E402
import save  # noqa: E402

doc = save.SaveDoc(paths.save_path())
sv = doc
g = game.GameEditor(doc)
D = save._deref

for aid, actor in sv.actors():
    name = sv.actor_name(actor)
    expnode = D(save.ivar(actor, "@exp"))
    cid = M.value_of(D(save.ivar(actor, "@class_id")))
    pairs = []
    if isinstance(expnode, M.HashNode):
        for k, v in expnode.pairs:
            pairs.append((M.value_of(D(k)), M.value_of(D(v))))
    print("%-8s @class_id=%-3s @exp=%s" % (name, cid, pairs))
    print("        g.exp()=%s  exp_key()=%s" % (g.exp(actor), g.exp_key(actor)))
    lv = g.actor_level(actor)
    print("        等级=%s  累计limit=%s" % (lv, g.limit_exp(actor)))
