# -*- coding: utf-8 -*-
"""把某个公共事件的指令序列打印出来（看孵化蛋到底调了什么）。

用法：python tools/probe_event.py 24 [条数]
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.stdout.reconfigure(errors="replace")

import xj_db          # noqa: E402
import xj_marshal as M  # noqa: E402

# RPG Maker VX Ace 的事件指令码（只列我们关心的）
CODE = {
    0: "结束", 101: "显示文字", 401: "文字", 102: "选项", 402: "选项分支",
    111: "条件", 411: "否则", 112: "循环", 413: "循环结束", 115: "跳出循环",
    117: "调用公共事件", 121: "开关", 122: "变量", 125: "改变金钱",
    126: "改变物品", 127: "改变武器", 128: "改变防具",
    201: "场所移动", 230: "等待", 355: "脚本（1 行）", 655: "脚本（续行）",
    356: "脚本…（单行 355 的旧写法）", 655: "脚本",
}
CODE[355] = "脚本"
CODE[655] = "脚本续"


def s(node, name=None):
    return xj_db.s(node, name) if name else xj_db.s(node)


def main():
    eid = int(sys.argv[1]) if len(sys.argv) > 1 else 24
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 200
    _r, items = xj_db.load("CommonEvents")
    ev = dict(items).get(eid)
    if ev is None:
        print("没有 24 号公共事件（%d 号也没有）" % eid)
        return 1
    print("=== 公共事件 %d：%s（开关 %s）==="
          % (eid, s(ev, "@name") or "（无名）", s(ev, "@switch_id")))
    lst = xj_db.deref(xj_db.ivar(ev, "@list"))
    if lst is None:
        print("没有指令列表")
        return 1
    n = 0
    for i, cmd in enumerate(getattr(lst, "items", [])):
        c = M.value_of(xj_db.ivar(cmd, "@code"))
        ind = M.value_of(xj_db.ivar(cmd, "@indent"))
        p = xj_db.deref(xj_db.ivar(cmd, "@parameters"))
        params = []
        if p is not None and hasattr(p, "items"):
            for x in p.items:
                v = M.value_of(xj_db.deref(x))
                if isinstance(v, bytes):
                    v = v.decode("utf-8", "replace")
                params.append(v)
        label = CODE.get(c, "code=%s" % c)
        text = "  " * (ind if isinstance(ind, int) else 0) + "%-10s %s" % (
            label, " | ".join(str(x) for x in params)[:150])
        print("%4d %s" % (i, text))
        n += 1
        if n >= limit:
            print("…（还有更多，用第二个参数调大）")
            break
    return 0


if __name__ == "__main__":
    sys.exit(main())
