# -*- coding: utf-8 -*-
"""门派 -> 门派称谓（「拜师」时游戏发的那个）。

**自动生成，别手改** —— `python tools/gen_sect_appellation.py` 重新生成。

来源：每张地图的拜师事件脚本里成对出现的
`instance_variable_set(:@sect_id, N)` 与 `add_appellation('X')`
（见生成器头部的说明）。游戏内测换版本后重跑生成器即可。
"""

#: 门派 id -> 称谓（0「无门派」没有称谓）
SECT_APPELLATION = {
    1: '五庄观弟子',   # 五庄观 / Map129.rvdata2
    2: '化生寺弟子',   # 化生寺 / Map183.rvdata2
    3: '大唐官府弟子',   # 大唐官府 / Map130.rvdata2
    4: '天宫弟子',   # 天宫 / Map122.rvdata2
    5: '女儿村弟子',   # 女儿村 / Map126.rvdata2
    6: '方寸山弟子',   # 方寸山 / Map114.rvdata2
    7: '普陀山弟子',   # 普陀山 / Map168.rvdata2
    8: '狮驼岭弟子',   # 狮驼岭 / Map167.rvdata2
    9: '盘丝洞弟子',   # 盘丝洞 / Map115.rvdata2
    10: '地府弟子',   # 地府 / Map143.rvdata2
    11: '魔王寨弟子',   # 魔王寨 / Map199.rvdata2
    12: '东海龙宫弟子',   # 龙宫 / Map019.rvdata2
}

#: 称谓 -> 门派 id（反查用；同名歧义时取小的 id）
APPELLATION_TO_SECT = {}
for _sid in sorted(SECT_APPELLATION, reverse=True):
    APPELLATION_TO_SECT[SECT_APPELLATION[_sid]] = _sid
del _sid


def sect_appellation(sect_id):
    """门派 id -> 称谓（0 或认不出的 id -> None）。"""
    try:
        return SECT_APPELLATION.get(int(sect_id))
    except (TypeError, ValueError):
        return None


def sect_of_appellation(text):
    """这个称谓属于哪个门派（不是门派称谓 -> None）。"""
    return APPELLATION_TO_SECT.get(text)
