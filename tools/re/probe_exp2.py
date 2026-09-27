# -*- coding: utf-8 -*-
"""一次性：把每个角色的 @level / @class_id / @exp 全表 / @limit_exp 原样打出来。"""
import io, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import paths, save, game, marshal_ruby as M

doc = save.SaveDoc(paths.save_path())
sv = doc
g = game.GameEditor(doc)
D = save._deref
for aid, actor in sv.actors():
    cid = M.value_of(D(save.ivar(actor, "@class_id")))
    lv = M.value_of(D(save.ivar(actor, "@level")))
    h = D(save.ivar(actor, "@exp"))
    pairs = [(M.value_of(D(k)), M.value_of(D(v))) for k, v in h.pairs] if isinstance(h, M.HashNode) else h
    print("%-6s class_id=%-4s level=%-3s @exp=%s" % (sv.actor_name(actor), cid, lv, pairs))
    print("        -> g.exp()=%s  门槛=%s   limit_exp=%s"
          % (g.exp(actor), g.next_level_exp(actor), g.limit_exp(actor)))
