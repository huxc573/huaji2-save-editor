# -*- coding: utf-8 -*-
"""游戏 `$baby` 资质配置表（**自动生成**，别手改）。

生成：python tools/gen_baby_data.py
来源：内测版脚本 `eval_17.rb` 的 `$baby = { ... }`（展开池引用后）

字段：type(普通/神兽/泡泡灵仙) type2(来自哪个池) allow_lv
      atk def hp mp agi eva grow life(pool 里是 "infinite") vip

另外抽出 `$baby[:_max]` → `MAX_ATTR`：那是**资质的硬上限**，
未进阶取 `类型`、已进阶取 `类型_p`（`BabyManager.get_attr_max`）。
"""

#: 按召唤兽 id（= Data\Actors 的 id）；池引用已展开成实际数值
SPECIES = {
    21: {'type': '普通', 'allow_lv': 0, 'atk': 960, 'def': 960, 'hp': 3600, 'mp': 1200, 'agi': 840, 'eva': 1320, 'grow': 0.918, 'life': 12000},
    22: {'type': '普通', 'allow_lv': 0, 'atk': 1080, 'def': 840, 'hp': 2700, 'mp': 1200, 'agi': 1320, 'eva': 1020, 'grow': 0.918, 'life': 9000},
    23: {'type': '普通', 'allow_lv': 5, 'atk': 1440, 'def': 900, 'hp': 2400, 'mp': 1200, 'agi': 1320, 'eva': 1200, 'grow': 1.03, 'life': 8000},
    24: {'type': '普通', 'allow_lv': 0, 'atk': 1320, 'def': 1380, 'hp': 4200, 'mp': 2160, 'agi': 1320, 'eva': 1320, 'grow': 1.122, 'life': 10000},
    25: {'type': '普通', 'allow_lv': 0, 'atk': 1080, 'def': 1140, 'hp': 2400, 'mp': 1440, 'agi': 1200, 'eva': 1020, 'grow': 0.918, 'life': 9000},
    26: {'type': '普通', 'allow_lv': 5, 'atk': 1440, 'def': 900, 'hp': 2880, 'mp': 1200, 'agi': 1380, 'eva': 1320, 'grow': 1.04, 'life': 7500},
    27: {'type': '普通', 'allow_lv': 0, 'atk': 1440, 'def': 840, 'hp': 2400, 'mp': 1200, 'agi': 1320, 'eva': 1200, 'grow': 1.03, 'life': 7500},
    28: {'type': '普通', 'allow_lv': 5, 'atk': 1140, 'def': 1140, 'hp': 3840, 'mp': 1260, 'agi': 1140, 'eva': 1200, 'grow': 1.04, 'life': 9000},
    29: {'type': '普通', 'allow_lv': 0, 'atk': 1320, 'def': 1320, 'hp': 3300, 'mp': 1320, 'agi': 900, 'eva': 960, 'grow': 0.918, 'life': 10000},
    30: {'type': '普通', 'allow_lv': 5, 'atk': 1080, 'def': 1200, 'hp': 3600, 'mp': 1200, 'agi': 1200, 'eva': 1320, 'grow': 1.035, 'life': 8000},
    31: {'type': '普通', 'allow_lv': 5, 'atk': 1260, 'def': 1260, 'hp': 3300, 'mp': 1380, 'agi': 1200, 'eva': 1200, 'grow': 1.03, 'life': 8000},
    32: {'type': '普通', 'allow_lv': 5, 'atk': 1020, 'def': 1140, 'hp': 3000, 'mp': 1440, 'agi': 1440, 'eva': 1380, 'grow': 0.969, 'life': 7800},
    33: {'type': '普通', 'allow_lv': 5, 'atk': 1080, 'def': 1140, 'hp': 2520, 'mp': 1800, 'agi': 1500, 'eva': 1500, 'grow': 1.101, 'life': 7500},
    34: {'type': '普通', 'allow_lv': 0, 'atk': 1140, 'def': 1020, 'hp': 2700, 'mp': 1800, 'agi': 1200, 'eva': 1200, 'grow': 0.969, 'life': 8500},
    35: {'type': '普通', 'allow_lv': 15, 'atk': 1380, 'def': 1140, 'hp': 3300, 'mp': 1200, 'agi': 1320, 'eva': 1320, 'grow': 1.05, 'life': 11500},
    36: {'type': '普通', 'allow_lv': 15, 'atk': 1140, 'def': 1320, 'hp': 4200, 'mp': 1320, 'agi': 1080, 'eva': 1320, 'grow': 1.045, 'life': 9000},
    37: {'type': '普通', 'allow_lv': 15, 'atk': 1320, 'def': 1260, 'hp': 3000, 'mp': 1440, 'agi': 1320, 'eva': 1200, 'grow': 1.05, 'life': 12000},
    38: {'type': '普通', 'allow_lv': 15, 'atk': 1020, 'def': 1440, 'hp': 3780, 'mp': 1440, 'agi': 1140, 'eva': 1140, 'grow': 1.071, 'life': 12000},
    39: {'type': '普通', 'allow_lv': 15, 'atk': 1200, 'def': 1200, 'hp': 3000, 'mp': 1200, 'agi': 1200, 'eva': 1500, 'grow': 1.05, 'life': 11000},
    40: {'type': '普通', 'allow_lv': 15, 'atk': 1380, 'def': 1080, 'hp': 3600, 'mp': 1380, 'agi': 1200, 'eva': 1080, 'grow': 1.045, 'life': 9000},
    41: {'type': '普通', 'allow_lv': 15, 'atk': 1260, 'def': 1380, 'hp': 3360, 'mp': 1320, 'agi': 1200, 'eva': 1200, 'grow': 1.045, 'life': 11500},
    42: {'type': '普通', 'allow_lv': 25, 'atk': 1440, 'def': 960, 'hp': 3600, 'mp': 1200, 'agi': 1500, 'eva': 1464, 'grow': 1.04, 'life': 9000},
    43: {'type': '普通', 'allow_lv': 25, 'atk': 1500, 'def': 1020, 'hp': 3000, 'mp': 1140, 'agi': 1320, 'eva': 960, 'grow': 1.122, 'life': 8000},
    44: {'type': '普通', 'allow_lv': 25, 'atk': 1200, 'def': 1380, 'hp': 4800, 'mp': 2400, 'agi': 1080, 'eva': 1440, 'grow': 1.055, 'life': 11500},
    45: {'type': '普通', 'allow_lv': 25, 'atk': 1320, 'def': 1200, 'hp': 5100, 'mp': 2280, 'agi': 1200, 'eva': 1220, 'grow': 1.066, 'life': 11500},
    46: {'type': '普通', 'allow_lv': 25, 'atk': 1140, 'def': 1380, 'hp': 3840, 'mp': 1800, 'agi': 1440, 'eva': 1080, 'grow': 1.085, 'life': 13500},
    47: {'type': '普通', 'allow_lv': 25, 'atk': 1320, 'def': 1320, 'hp': 4200, 'mp': 1200, 'agi': 1140, 'eva': 1260, 'grow': 1.035, 'life': 10000},
    48: {'type': '普通', 'allow_lv': 35, 'atk': 1020, 'def': 1440, 'hp': 5820, 'mp': 1980, 'agi': 900, 'eva': 1140, 'grow': 1.081, 'life': 14000},
    49: {'type': '普通', 'allow_lv': 35, 'atk': 1380, 'def': 1260, 'hp': 5040, 'mp': 2160, 'agi': 1020, 'eva': 1320, 'grow': 1.065, 'life': 9500},
    50: {'type': '普通', 'allow_lv': 35, 'atk': 1440, 'def': 1080, 'hp': 4320, 'mp': 2400, 'agi': 1200, 'eva': 1380, 'grow': 1.091, 'life': 8500},
    51: {'type': '普通', 'allow_lv': 35, 'atk': 1320, 'def': 1320, 'hp': 3600, 'mp': 1800, 'agi': 1440, 'eva': 1200, 'grow': 1.091, 'life': 9000},
    52: {'type': '普通', 'allow_lv': 35, 'atk': 1320, 'def': 1320, 'hp': 3600, 'mp': 1800, 'agi': 1400, 'eva': 1200, 'grow': 1.101, 'life': 9000},
    53: {'type': '普通', 'allow_lv': 35, 'atk': 1320, 'def': 1140, 'hp': 4200, 'mp': 2400, 'agi': 1440, 'eva': 1140, 'grow': 1.142, 'life': 13500},
    54: {'type': '普通', 'allow_lv': 35, 'atk': 1140, 'def': 1355, 'hp': 4980, 'mp': 2580, 'agi': 1080, 'eva': 1200, 'grow': 1.111, 'life': 9000},
    55: {'type': '普通', 'allow_lv': 45, 'atk': 1320, 'def': 1320, 'hp': 5280, 'mp': 1800, 'agi': 960, 'eva': 1380, 'grow': 1.142, 'life': 9500},
    56: {'type': '普通', 'allow_lv': 45, 'atk': 1140, 'def': 1260, 'hp': 3600, 'mp': 2400, 'agi': 1380, 'eva': 1200, 'grow': 1.173, 'life': 10000},
    57: {'type': '普通', 'allow_lv': 45, 'atk': 1140, 'def': 1440, 'hp': 6000, 'mp': 2400, 'agi': 960, 'eva': 1320, 'grow': 1.152, 'life': 9500},
    58: {'type': '普通', 'allow_lv': 45, 'atk': 1320, 'def': 1140, 'hp': 3000, 'mp': 3000, 'agi': 1440, 'eva': 1440, 'grow': 1.122, 'life': 8500},
    59: {'type': '普通', 'allow_lv': 45, 'atk': 1200, 'def': 1200, 'hp': 4200, 'mp': 1920, 'agi': 1440, 'eva': 1140, 'grow': 1.173, 'life': 11000},
    60: {'type': '普通', 'allow_lv': 55, 'atk': 1500, 'def': 1440, 'hp': 4500, 'mp': 1800, 'agi': 1080, 'eva': 1500, 'grow': 1.152, 'life': 7500},
    61: {'type': '普通', 'allow_lv': 55, 'atk': 1380, 'def': 1392, 'hp': 4200, 'mp': 2220, 'agi': 1500, 'eva': 1440, 'grow': 1.173, 'life': 8000},
    62: {'type': '普通', 'allow_lv': 55, 'atk': 1320, 'def': 1500, 'hp': 5100, 'mp': 2220, 'agi': 1320, 'eva': 1320, 'grow': 1.173, 'life': 8500},
    63: {'type': '普通', 'allow_lv': 55, 'atk': 1380, 'def': 1140, 'hp': 4800, 'mp': 2340, 'agi': 1380, 'eva': 1200, 'grow': 1.183, 'life': 8000},
    64: {'type': '普通', 'allow_lv': 65, 'atk': 1200, 'def': 1500, 'hp': 3840, 'mp': 2880, 'agi': 1200, 'eva': 1140, 'grow': 1.224, 'life': 8000},
    65: {'type': '普通', 'allow_lv': 65, 'atk': 1380, 'def': 1320, 'hp': 4200, 'mp': 2760, 'agi': 1440, 'eva': 1800, 'grow': 1.234, 'life': 8500},
    66: {'type': '普通', 'allow_lv': 65, 'atk': 1200, 'def': 1440, 'hp': 4200, 'mp': 2400, 'agi': 1560, 'eva': 1320, 'grow': 1.224, 'life': 7500},
    67: {'type': '普通', 'allow_lv': 65, 'atk': 1440, 'def': 1440, 'hp': 4560, 'mp': 3000, 'agi': 1200, 'eva': 1320, 'grow': 1.224, 'life': 7500},
    68: {'type': '普通', 'allow_lv': 65, 'atk': 1440, 'def': 1440, 'hp': 4560, 'mp': 1920, 'agi': 1380, 'eva': 1440, 'grow': 1.224, 'life': 8000},
    69: {'type': '普通', 'allow_lv': 65, 'atk': 1200, 'def': 1380, 'hp': 4200, 'mp': 3000, 'agi': 1440, 'eva': 1620, 'grow': 1.203, 'life': 8000},
    70: {'type': '普通', 'allow_lv': 75, 'atk': 1440, 'def': 1440, 'hp': 4560, 'mp': 2400, 'agi': 1380, 'eva': 1440, 'grow': 1.254, 'life': 8000},
    71: {'type': '普通', 'allow_lv': 75, 'atk': 1200, 'def': 1260, 'hp': 4200, 'mp': 2711, 'agi': 1560, 'eva': 1680, 'grow': 1.254, 'life': 7500},
    72: {'type': '普通', 'allow_lv': 75, 'atk': 1380, 'def': 1320, 'hp': 4380, 'mp': 2640, 'agi': 1440, 'eva': 1500, 'grow': 1.244, 'life': 7500},
    73: {'type': '普通', 'allow_lv': 75, 'atk': 1200, 'def': 1416, 'hp': 4380, 'mp': 2700, 'agi': 1440, 'eva': 1380, 'grow': 1.254, 'life': 7500},
    74: {'type': '普通', 'allow_lv': 75, 'atk': 1440, 'def': 1464, 'hp': 4800, 'mp': 2520, 'agi': 1200, 'eva': 1140, 'grow': 1.254, 'life': 7500},
    75: {'type': '普通', 'allow_lv': 75, 'atk': 1440, 'def': 1464, 'hp': 4800, 'mp': 2520, 'agi': 1200, 'eva': 1140, 'grow': 1.254, 'life': 7500},
    76: {'type': '普通', 'allow_lv': 75, 'atk': 1200, 'def': 1416, 'hp': 4380, 'mp': 2700, 'agi': 1440, 'eva': 1380, 'grow': 1.254, 'life': 7500},
    77: {'type': '普通', 'allow_lv': 75, 'atk': 1380, 'def': 1380, 'hp': 5400, 'mp': 2640, 'agi': 1200, 'eva': 1680, 'grow': 1.244, 'life': 8500},
    78: {'type': '普通', 'allow_lv': 85, 'atk': 1440, 'def': 1320, 'hp': 4560, 'mp': 2640, 'agi': 1560, 'eva': 1320, 'grow': 1.254, 'life': 7500},
    79: {'type': '普通', 'allow_lv': 85, 'atk': 1200, 'def': 1440, 'hp': 4440, 'mp': 2880, 'agi': 1560, 'eva': 1560, 'grow': 1.254, 'life': 8000},
    80: {'type': '普通', 'allow_lv': 85, 'atk': 1464, 'def': 1560, 'hp': 4800, 'mp': 2400, 'agi': 1200, 'eva': 1320, 'grow': 1.254, 'life': 8000},
    81: {'type': '普通', 'allow_lv': 95, 'atk': 1320, 'def': 1560, 'hp': 4800, 'mp': 3000, 'agi': 1440, 'eva': 1440, 'grow': 1.254, 'life': 8000},
    82: {'type': '普通', 'allow_lv': 95, 'atk': 1440, 'def': 1560, 'hp': 4440, 'mp': 2400, 'agi': 1440, 'eva': 1680, 'grow': 1.254, 'life': 8000},
    83: {'type': '普通', 'allow_lv': 95, 'atk': 1440, 'def': 1320, 'hp': 3600, 'mp': 2400, 'agi': 1320, 'eva': 1800, 'grow': 1.254, 'life': 8000},
    84: {'type': '普通', 'allow_lv': 95, 'atk': 1440, 'def': 1440, 'hp': 4800, 'mp': 3000, 'agi': 1500, 'eva': 1440, 'grow': 1.264, 'life': 8000},
    85: {'type': '普通', 'allow_lv': 95, 'atk': 1476, 'def': 1440, 'hp': 4200, 'mp': 2640, 'agi': 1320, 'eva': 1680, 'grow': 1.254, 'life': 8000},
    86: {'type': '普通', 'allow_lv': 105, 'atk': 1524, 'def': 1380, 'hp': 5040, 'mp': 1440, 'agi': 1320, 'eva': 1320, 'grow': 1.264, 'life': 6000},
    87: {'type': '普通', 'allow_lv': 105, 'atk': 1380, 'def': 1440, 'hp': 4320, 'mp': 2880, 'agi': 1320, 'eva': 1440, 'grow': 1.264, 'life': 7000},
    88: {'type': '普通', 'allow_lv': 105, 'atk': 1464, 'def': 1440, 'hp': 4800, 'mp': 2820, 'agi': 1560, 'eva': 1560, 'grow': 1.264, 'life': 6000},
    89: {'type': '普通', 'allow_lv': 105, 'atk': 1440, 'def': 1440, 'hp': 4200, 'mp': 2640, 'agi': 1536, 'eva': 1560, 'grow': 1.264, 'life': 7000},
    90: {'type': '普通', 'allow_lv': 125, 'atk': 1548, 'def': 1344, 'hp': 6000, 'mp': 2640, 'agi': 1200, 'eva': 1320, 'grow': 1.264, 'life': 6000},
    91: {'type': '普通', 'allow_lv': 125, 'atk': 1440, 'def': 1440, 'hp': 4560, 'mp': 2760, 'agi': 1560, 'eva': 1440, 'grow': 1.264, 'life': 6000},
    92: {'type': '普通', 'allow_lv': 125, 'atk': 1500, 'def': 1440, 'hp': 4800, 'mp': 2400, 'agi': 1500, 'eva': 1560, 'grow': 1.264, 'life': 6000},
    93: {'type': '普通', 'allow_lv': 125, 'atk': 1440, 'def': 1500, 'hp': 5400, 'mp': 3000, 'agi': 1320, 'eva': 1800, 'grow': 1.264, 'life': 6000},
    94: {'type': '普通', 'allow_lv': 125, 'atk': 1500, 'def': 1440, 'hp': 4800, 'mp': 3000, 'agi': 1440, 'eva': 1320, 'grow': 1.264, 'life': 6000},
    95: {'type': '普通', 'allow_lv': 125, 'atk': 1500, 'def': 1440, 'hp': 5760, 'mp': 2880, 'agi': 1440, 'eva': 1440, 'grow': 1.264, 'life': 6000},
    96: {'type': '普通', 'allow_lv': 135, 'atk': 1500, 'def': 1500, 'hp': 5400, 'mp': 3000, 'agi': 960, 'eva': 1800, 'grow': 1.275, 'life': 7000},
    97: {'type': '普通', 'allow_lv': 135, 'atk': 1440, 'def': 1500, 'hp': 4800, 'mp': 2760, 'agi': 1320, 'eva': 1800, 'grow': 1.264, 'life': 8000},
    98: {'type': '普通', 'allow_lv': 135, 'atk': 1500, 'def': 1440, 'hp': 4560, 'mp': 2160, 'agi': 1320, 'eva': 1560, 'grow': 1.264, 'life': 8000},
    99: {'type': '普通', 'allow_lv': 135, 'atk': 1440, 'def': 1560, 'hp': 5760, 'mp': 3000, 'agi': 1200, 'eva': 1560, 'grow': 1.275, 'life': 7000},
    100: {'type': '普通', 'allow_lv': 135, 'atk': 1464, 'def': 1464, 'hp': 4080, 'mp': 2400, 'agi': 1560, 'eva': 1680, 'grow': 1.264, 'life': 8000},
    101: {'type': '普通', 'allow_lv': 135, 'atk': 1524, 'def': 1440, 'hp': 5400, 'mp': 1800, 'agi': 1440, 'eva': 1440, 'grow': 1.264, 'life': 7000},
    102: {'type': '普通', 'allow_lv': 135, 'atk': 1464, 'def': 1464, 'hp': 6240, 'mp': 2880, 'agi': 1320, 'eva': 1920, 'grow': 1.275, 'life': 9000},
    103: {'type': '普通', 'allow_lv': 135, 'atk': 1500, 'def': 1500, 'hp': 5400, 'mp': 1680, 'agi': 1320, 'eva': 1440, 'grow': 1.275, 'life': 8500},
    104: {'type': '普通', 'allow_lv': 145, 'atk': 1524, 'def': 1440, 'hp': 4800, 'mp': 1560, 'agi': 1560, 'eva': 1560, 'grow': 1.285, 'life': 8500},
    105: {'type': '普通', 'allow_lv': 145, 'atk': 1500, 'def': 1344, 'hp': 4800, 'mp': 2520, 'agi': 1560, 'eva': 1560, 'grow': 1.264, 'life': 8500},
    106: {'type': '普通', 'allow_lv': 145, 'atk': 1440, 'def': 1500, 'hp': 5280, 'mp': 2880, 'agi': 1440, 'eva': 1440, 'grow': 1.264, 'life': 8500},
    107: {'type': '普通', 'allow_lv': 145, 'atk': 1500, 'def': 1560, 'hp': 5400, 'mp': 2400, 'agi': 1200, 'eva': 1320, 'grow': 1.264, 'life': 8500},
    108: {'type': '普通', 'allow_lv': 155, 'atk': 1440, 'def': 1500, 'hp': 5640, 'mp': 3240, 'agi': 1200, 'eva': 1560, 'grow': 1.275, 'life': 9000},
    109: {'type': '普通', 'allow_lv': 155, 'atk': 1440, 'def': 1476, 'hp': 5400, 'mp': 3240, 'agi': 1320, 'eva': 1560, 'grow': 1.295, 'life': 9000},
    110: {'type': '普通', 'allow_lv': 155, 'atk': 1500, 'def': 1440, 'hp': 4560, 'mp': 2640, 'agi': 1500, 'eva': 1560, 'grow': 1.285, 'life': 9000},
    111: {'type': '普通', 'allow_lv': 155, 'atk': 1536, 'def': 1440, 'hp': 4800, 'mp': 2280, 'agi': 1440, 'eva': 1560, 'grow': 1.275, 'life': 9000},
    112: {'type': '普通', 'allow_lv': 155, 'atk': 1524, 'def': 1464, 'hp': 4560, 'mp': 2640, 'agi': 1500, 'eva': 1680, 'grow': 1.285, 'life': 9000},
    113: {'type': '普通', 'allow_lv': 155, 'atk': 1524, 'def': 1380, 'hp': 5040, 'mp': 2400, 'agi': 1440, 'eva': 1440, 'grow': 1.285, 'life': 9000},
    114: {'type': '普通', 'allow_lv': 155, 'atk': 1464, 'def': 1440, 'hp': 4560, 'mp': 3120, 'agi': 1200, 'eva': 1440, 'grow': 1.285, 'life': 9000},
    115: {'type': '普通', 'allow_lv': 155, 'atk': 1464, 'def': 1440, 'hp': 5040, 'mp': 3240, 'agi': 1320, 'eva': 1440, 'grow': 1.285, 'life': 9000},
    116: {'type': '普通', 'allow_lv': 165, 'atk': 1536, 'def': 1380, 'hp': 4800, 'mp': 2400, 'agi': 1500, 'eva': 1440, 'grow': 1.285, 'life': 9000},
    117: {'type': '普通', 'allow_lv': 165, 'atk': 1380, 'def': 1500, 'hp': 5400, 'mp': 2400, 'agi': 1560, 'eva': 1440, 'grow': 1.295, 'life': 9000},
    118: {'type': '普通', 'allow_lv': 165, 'atk': 1440, 'def': 1440, 'hp': 4800, 'mp': 2640, 'agi': 1500, 'eva': 1440, 'grow': 1.295, 'life': 9000},
    119: {'type': '普通', 'allow_lv': 175, 'atk': 1560, 'def': 1428, 'hp': 4200, 'mp': 2160, 'agi': 1440, 'eva': 1620, 'grow': 1.285, 'life': 7000},
    120: {'type': '普通', 'allow_lv': 175, 'atk': 1440, 'def': 1380, 'hp': 6000, 'mp': 3000, 'agi': 1200, 'eva': 960, 'grow': 1.275, 'life': 8000},
    121: {'type': '普通', 'allow_lv': 175, 'atk': 1536, 'def': 1440, 'hp': 5040, 'mp': 2400, 'agi': 1380, 'eva': 1560, 'grow': 1.275, 'life': 9000},
    122: {'type': '普通', 'allow_lv': 175, 'atk': 1404, 'def': 1524, 'hp': 5760, 'mp': 2760, 'agi': 1536, 'eva': 1440, 'grow': 1.295, 'life': 9000},
    123: {'type': '普通', 'allow_lv': 175, 'atk': 1500, 'def': 1380, 'hp': 6000, 'mp': 2760, 'agi': 1200, 'eva': 960, 'grow': 1.275, 'life': 8000},
    124: {'type': '普通', 'allow_lv': 175, 'atk': 1459, 'def': 1459, 'hp': 5521, 'mp': 3301, 'agi': 1471, 'eva': 1567, 'grow': 1.297, 'life': 9000},
    125: {'type': '普通', 'allow_lv': 175, 'atk': 1423, 'def': 1423, 'hp': 5449, 'mp': 3433, 'agi': 1471, 'eva': 1567, 'grow': 1.297, 'life': 9000},
    126: {'type': '普通', 'allow_lv': 175, 'atk': 1440, 'def': 1380, 'hp': 6240, 'mp': 2640, 'agi': 1380, 'eva': 960, 'grow': 1.275, 'life': 9000},
    127: {'type': '普通', 'allow_lv': 85, 'atk': 1464, 'def': 1320, 'hp': 3840, 'mp': 2400, 'agi': 1560, 'eva': 1440, 'grow': 1.254, 'life': 8000},
    128: {'type': '普通', 'allow_lv': 85, 'atk': 1200, 'def': 1200, 'hp': 3600, 'mp': 2400, 'agi': 1200, 'eva': 1560, 'grow': 1.224, 'life': 8000},
    129: {'type': '普通', 'allow_lv': 105, 'atk': 1416, 'def': 1476, 'hp': 5400, 'mp': 2400, 'agi': 1332, 'eva': 1440, 'grow': 1.254, 'life': 9000},
    130: {'type': '普通', 'allow_lv': 105, 'atk': 1416, 'def': 1476, 'hp': 5400, 'mp': 2400, 'agi': 1344, 'eva': 1440, 'grow': 1.264, 'life': 9000},
    131: {'type': '普通', 'allow_lv': 105, 'atk': 1320, 'def': 1380, 'hp': 4320, 'mp': 2940, 'agi': 1464, 'eva': 1680, 'grow': 1.264, 'life': 6000},
    132: {'type': '普通', 'allow_lv': 105, 'atk': 1452, 'def': 1380, 'hp': 4440, 'mp': 2280, 'agi': 1320, 'eva': 1560, 'grow': 1.254, 'life': 7000},
    133: {'type': '普通', 'allow_lv': 125, 'atk': 1500, 'def': 1440, 'hp': 5040, 'mp': 2280, 'agi': 1440, 'eva': 1560, 'grow': 1.264, 'life': 7000},
    134: {'type': '普通', 'allow_lv': 125, 'atk': 1440, 'def': 1440, 'hp': 4800, 'mp': 3240, 'agi': 1380, 'eva': 1440, 'grow': 1.264, 'life': 7000},
    135: {'type': '神兽', 'type2': '神兽资质', 'allow_lv': 0, 'atk': 1600, 'def': 1600, 'hp': 6500, 'mp': 3500, 'agi': 1800, 'eva': 1800, 'grow': 1.3, 'life': 'infinite'},
    136: {'type': '神兽', 'type2': '神兽资质', 'allow_lv': 0, 'atk': 1600, 'def': 1600, 'hp': 6500, 'mp': 3500, 'agi': 1800, 'eva': 1800, 'grow': 1.3, 'life': 'infinite'},
    137: {'type': '神兽', 'type2': '神兽资质', 'allow_lv': 0, 'atk': 1600, 'def': 1600, 'hp': 6500, 'mp': 3500, 'agi': 1800, 'eva': 1800, 'grow': 1.3, 'life': 'infinite'},
    138: {'type': '神兽', 'type2': '神兽资质', 'allow_lv': 0, 'atk': 1600, 'def': 1600, 'hp': 6500, 'mp': 3500, 'agi': 1800, 'eva': 1800, 'grow': 1.3, 'life': 'infinite'},
    139: {'type': '神兽', 'type2': '神兽资质', 'allow_lv': 0, 'atk': 1600, 'def': 1600, 'hp': 6500, 'mp': 3500, 'agi': 1800, 'eva': 1800, 'grow': 1.3, 'life': 'infinite'},
    140: {'type': '神兽', 'type2': '神兽资质', 'allow_lv': 0, 'atk': 1600, 'def': 1600, 'hp': 6500, 'mp': 3500, 'agi': 1800, 'eva': 1800, 'grow': 1.3, 'life': 'infinite'},
    141: {'type': '神兽', 'type2': '神兽资质', 'allow_lv': 0, 'atk': 1600, 'def': 1600, 'hp': 6500, 'mp': 3500, 'agi': 1800, 'eva': 1800, 'grow': 1.3, 'life': 'infinite'},
    142: {'type': '神兽', 'type2': '神兽资质', 'allow_lv': 0, 'atk': 1600, 'def': 1600, 'hp': 6500, 'mp': 3500, 'agi': 1800, 'eva': 1800, 'grow': 1.3, 'life': 'infinite'},
    143: {'type': '神兽', 'type2': '神兽资质', 'allow_lv': 0, 'atk': 1600, 'def': 1600, 'hp': 6500, 'mp': 3500, 'agi': 1800, 'eva': 1800, 'grow': 1.3, 'life': 'infinite'},
    144: {'type': '神兽', 'type2': '神兽资质', 'allow_lv': 0, 'atk': 1600, 'def': 1600, 'hp': 6500, 'mp': 3500, 'agi': 1800, 'eva': 1800, 'grow': 1.3, 'life': 'infinite'},
    145: {'type': '神兽', 'type2': '神兽资质', 'allow_lv': 0, 'atk': 1600, 'def': 1600, 'hp': 6500, 'mp': 3500, 'agi': 1800, 'eva': 1800, 'grow': 1.3, 'life': 'infinite'},
    146: {'type': '神兽', 'type2': '神兽资质', 'allow_lv': 0, 'atk': 1600, 'def': 1600, 'hp': 6500, 'mp': 3500, 'agi': 1800, 'eva': 1800, 'grow': 1.3, 'life': 'infinite'},
    147: {'type': '神兽', 'type2': '神兽资质', 'allow_lv': 0, 'atk': 1600, 'def': 1600, 'hp': 6500, 'mp': 3500, 'agi': 1800, 'eva': 1800, 'grow': 1.3, 'life': 'infinite'},
    148: {'type': '神兽', 'type2': '神兽资质2', 'allow_lv': 0, 'atk': 1700, 'def': 1700, 'hp': 6650, 'mp': 3650, 'agi': 1900, 'eva': 1900, 'grow': 1.4, 'life': 'infinite'},
    149: {'type': '神兽', 'type2': '神兽资质2', 'allow_lv': 0, 'atk': 1700, 'def': 1700, 'hp': 6650, 'mp': 3650, 'agi': 1900, 'eva': 1900, 'grow': 1.4, 'life': 'infinite'},
    150: {'type': '神兽', 'type2': '神兽资质2', 'allow_lv': 0, 'atk': 1700, 'def': 1700, 'hp': 6650, 'mp': 3650, 'agi': 1900, 'eva': 1900, 'grow': 1.4, 'life': 'infinite'},
    151: {'type': '神兽', 'type2': '神兽资质2', 'allow_lv': 0, 'atk': 1700, 'def': 1700, 'hp': 6650, 'mp': 3650, 'agi': 1900, 'eva': 1900, 'grow': 1.4, 'life': 'infinite'},
    152: {'type': '神兽', 'type2': '神兽资质', 'allow_lv': 0, 'atk': 1600, 'def': 1600, 'hp': 6500, 'mp': 3500, 'agi': 1800, 'eva': 1800, 'grow': 1.3, 'life': 'infinite'},
    153: {'type': '神兽', 'type2': '神兽资质2', 'allow_lv': 0, 'atk': 1700, 'def': 1700, 'hp': 6650, 'mp': 3650, 'agi': 1900, 'eva': 1900, 'grow': 1.4, 'life': 'infinite'},
    154: {'type': '神兽', 'type2': '神兽资质', 'allow_lv': 0, 'atk': 1600, 'def': 1600, 'hp': 6500, 'mp': 3500, 'agi': 1800, 'eva': 1800, 'grow': 1.3, 'life': 'infinite'},
    155: {'type': '神兽', 'type2': '神兽资质2', 'allow_lv': 0, 'atk': 1700, 'def': 1700, 'hp': 6650, 'mp': 3650, 'agi': 1900, 'eva': 1900, 'grow': 1.4, 'life': 'infinite'},
    156: {'type': '神兽', 'type2': '神兽资质2', 'allow_lv': 0, 'atk': 1700, 'def': 1700, 'hp': 6650, 'mp': 3650, 'agi': 1900, 'eva': 1900, 'grow': 1.4, 'life': 'infinite'},
    157: {'type': '神兽', 'type2': '神兽资质2', 'allow_lv': 0, 'atk': 1700, 'def': 1700, 'hp': 6650, 'mp': 3650, 'agi': 1900, 'eva': 1900, 'grow': 1.4, 'life': 'infinite'},
    158: {'type': '神兽', 'type2': '神兽资质2', 'allow_lv': 0, 'atk': 1700, 'def': 1700, 'hp': 6650, 'mp': 3650, 'agi': 1900, 'eva': 1900, 'grow': 1.4, 'life': 'infinite'},
    159: {'type': '神兽', 'type2': '神兽资质', 'allow_lv': 0, 'atk': 1600, 'def': 1600, 'hp': 6500, 'mp': 3500, 'agi': 1800, 'eva': 1800, 'grow': 1.3, 'life': 'infinite'},
    160: {'type': '神兽', 'type2': '神兽资质', 'allow_lv': 0, 'atk': 1600, 'def': 1600, 'hp': 6500, 'mp': 3500, 'agi': 1800, 'eva': 1800, 'grow': 1.3, 'life': 'infinite'},
    161: {'type': '神兽', 'type2': '神兽资质', 'allow_lv': 0, 'atk': 1600, 'def': 1600, 'hp': 6500, 'mp': 3500, 'agi': 1800, 'eva': 1800, 'grow': 1.3, 'life': 'infinite'},
    162: {'type': '神兽', 'type2': '神兽资质2', 'allow_lv': 0, 'atk': 1700, 'def': 1700, 'hp': 6650, 'mp': 3650, 'agi': 1900, 'eva': 1900, 'grow': 1.4, 'life': 'infinite'},
    163: {'type': '神兽', 'type2': '神兽资质2', 'allow_lv': 0, 'atk': 1700, 'def': 1700, 'hp': 6650, 'mp': 3650, 'agi': 1900, 'eva': 1900, 'grow': 1.4, 'life': 'infinite'},
    164: {'type': '神兽', 'type2': '神兽资质', 'allow_lv': 0, 'atk': 1600, 'def': 1600, 'hp': 6500, 'mp': 3500, 'agi': 1800, 'eva': 1800, 'grow': 1.3, 'life': 'infinite'},
    165: {'type': '神兽', 'type2': '神兽资质', 'allow_lv': 0, 'atk': 1600, 'def': 1600, 'hp': 6500, 'mp': 3500, 'agi': 1800, 'eva': 1800, 'grow': 1.3, 'life': 'infinite'},
    166: {'type': '神兽', 'type2': '神兽资质2', 'allow_lv': 0, 'atk': 1700, 'def': 1700, 'hp': 6650, 'mp': 3650, 'agi': 1900, 'eva': 1900, 'grow': 1.4, 'life': 'infinite'},
    167: {'type': '神兽', 'type2': '神兽资质', 'allow_lv': 0, 'atk': 1600, 'def': 1600, 'hp': 6500, 'mp': 3500, 'agi': 1800, 'eva': 1800, 'grow': 1.3, 'life': 'infinite'},
    168: {'type': '神兽', 'type2': '神兽资质', 'allow_lv': 0, 'atk': 1600, 'def': 1600, 'hp': 6500, 'mp': 3500, 'agi': 1800, 'eva': 1800, 'grow': 1.3, 'life': 'infinite'},
    169: {'type': '神兽', 'type2': '神兽资质', 'allow_lv': 0, 'atk': 1600, 'def': 1600, 'hp': 6500, 'mp': 3500, 'agi': 1800, 'eva': 1800, 'grow': 1.3, 'life': 'infinite'},
    170: {'type': '神兽', 'type2': '神兽资质', 'allow_lv': 0, 'atk': 1600, 'def': 1600, 'hp': 6500, 'mp': 3500, 'agi': 1800, 'eva': 1800, 'grow': 1.3, 'life': 'infinite'},
    171: {'type': '神兽', 'type2': '神兽资质2', 'allow_lv': 0, 'atk': 1700, 'def': 1700, 'hp': 6650, 'mp': 3650, 'agi': 1900, 'eva': 1900, 'grow': 1.4, 'life': 'infinite'},
    172: {'type': '神兽', 'type2': '神兽资质2', 'allow_lv': 0, 'atk': 1700, 'def': 1700, 'hp': 6650, 'mp': 3650, 'agi': 1900, 'eva': 1900, 'grow': 1.4, 'life': 'infinite'},
    173: {'type': '神兽', 'type2': '神兽资质2', 'allow_lv': 0, 'atk': 1700, 'def': 1700, 'hp': 6650, 'mp': 3650, 'agi': 1900, 'eva': 1900, 'grow': 1.4, 'life': 'infinite'},
    174: {'type': '神兽', 'type2': '神兽资质2', 'allow_lv': 0, 'atk': 1700, 'def': 1700, 'hp': 6650, 'mp': 3650, 'agi': 1900, 'eva': 1900, 'grow': 1.4, 'life': 'infinite'},
    175: {'type': '神兽', 'type2': '神兽资质', 'allow_lv': 0, 'atk': 1600, 'def': 1600, 'hp': 6500, 'mp': 3500, 'agi': 1800, 'eva': 1800, 'grow': 1.3, 'life': 'infinite'},
    179: {'type': '神兽', 'type2': '神兽资质3', 'allow_lv': 0, 'atk': 1800, 'def': 1800, 'hp': 6800, 'mp': 3800, 'agi': 2000, 'eva': 2000, 'grow': 1.5, 'life': 'infinite'},
    180: {'type': '神兽', 'type2': '神兽资质3', 'allow_lv': 0, 'atk': 1800, 'def': 1800, 'hp': 6800, 'mp': 3800, 'agi': 2000, 'eva': 2000, 'grow': 1.5, 'life': 'infinite'},
    181: {'type': '神兽', 'type2': '神兽资质3', 'allow_lv': 0, 'atk': 1800, 'def': 1800, 'hp': 6800, 'mp': 3800, 'agi': 2000, 'eva': 2000, 'grow': 1.5, 'life': 'infinite'},
    182: {'type': '神兽', 'type2': '神兽资质3', 'allow_lv': 0, 'atk': 1800, 'def': 1800, 'hp': 6800, 'mp': 3800, 'agi': 2000, 'eva': 2000, 'grow': 1.5, 'life': 'infinite'},
    183: {'type': '神兽', 'type2': '神兽资质3', 'allow_lv': 0, 'atk': 1800, 'def': 1800, 'hp': 6800, 'mp': 3800, 'agi': 2000, 'eva': 2000, 'grow': 1.5, 'life': 'infinite'},
    184: {'type': '神兽', 'type2': '神兽资质3', 'allow_lv': 0, 'atk': 1800, 'def': 1800, 'hp': 6800, 'mp': 3800, 'agi': 2000, 'eva': 2000, 'grow': 1.5, 'life': 'infinite'},
    185: {'type': '神兽', 'type2': '神兽资质3', 'allow_lv': 0, 'atk': 1800, 'def': 1800, 'hp': 6800, 'mp': 3800, 'agi': 2000, 'eva': 2000, 'grow': 1.5, 'life': 'infinite'},
    186: {'type': '神兽', 'type2': '神兽资质3', 'allow_lv': 0, 'atk': 1800, 'def': 1800, 'hp': 6800, 'mp': 3800, 'agi': 2000, 'eva': 2000, 'grow': 1.5, 'life': 'infinite'},
    187: {'type': '神兽', 'type2': '神兽资质3', 'allow_lv': 0, 'atk': 1800, 'def': 1800, 'hp': 6800, 'mp': 3800, 'agi': 2000, 'eva': 2000, 'grow': 1.5, 'life': 'infinite'},
    200: {'type': '神兽', 'type2': '神兽资质4', 'allow_lv': 0, 'atk': 1900, 'def': 1900, 'hp': 7000, 'mp': 4000, 'agi': 2100, 'eva': 2100, 'grow': 1.6, 'life': 'infinite'},
    201: {'type': '神兽', 'type2': '神兽资质4', 'allow_lv': 0, 'atk': 1900, 'def': 1900, 'hp': 7000, 'mp': 4000, 'agi': 2100, 'eva': 2100, 'grow': 1.6, 'life': 'infinite'},
    202: {'type': '神兽', 'type2': '神兽资质4', 'allow_lv': 0, 'atk': 1900, 'def': 1900, 'hp': 7000, 'mp': 4000, 'agi': 2100, 'eva': 2100, 'grow': 1.6, 'life': 'infinite'},
    203: {'type': '神兽', 'type2': '神兽资质4', 'allow_lv': 0, 'atk': 1900, 'def': 1900, 'hp': 7000, 'mp': 4000, 'agi': 2100, 'eva': 2100, 'grow': 1.6, 'life': 'infinite'},
    204: {'type': '神兽', 'type2': '神兽资质4', 'allow_lv': 0, 'atk': 1900, 'def': 1900, 'hp': 7000, 'mp': 4000, 'agi': 2100, 'eva': 2100, 'grow': 1.6, 'life': 'infinite'},
    210: {'type': '神兽', 'type2': '神兽资质4', 'allow_lv': 0, 'atk': 1900, 'def': 1900, 'hp': 7000, 'mp': 4000, 'agi': 2100, 'eva': 2100, 'grow': 1.6, 'life': 'infinite'},
    230: {'type': '泡泡灵仙', 'type2': '灵仙资质', 'allow_lv': 0, 'atk': 1600, 'def': 1600, 'hp': 5500, 'mp': 3500, 'agi': 1400, 'eva': 1400, 'grow': 1.3, 'life': 8000},
    231: {'type': '泡泡灵仙', 'type2': '灵仙资质', 'allow_lv': 0, 'atk': 1600, 'def': 1600, 'hp': 5500, 'mp': 3500, 'agi': 1400, 'eva': 1400, 'grow': 1.3, 'life': 8000},
    232: {'type': '泡泡灵仙', 'type2': '灵仙资质', 'allow_lv': 0, 'atk': 1600, 'def': 1600, 'hp': 5500, 'mp': 3500, 'agi': 1400, 'eva': 1400, 'grow': 1.3, 'life': 8000},
    233: {'type': '泡泡灵仙', 'type2': '灵仙资质', 'allow_lv': 0, 'atk': 1600, 'def': 1600, 'hp': 5500, 'mp': 3500, 'agi': 1400, 'eva': 1400, 'grow': 1.3, 'life': 8000},
    234: {'type': '泡泡灵仙', 'type2': '灵仙资质', 'allow_lv': 0, 'atk': 1600, 'def': 1600, 'hp': 5500, 'mp': 3500, 'agi': 1400, 'eva': 1400, 'grow': 1.3, 'life': 8000},
    235: {'type': '泡泡灵仙', 'type2': '灵仙资质', 'allow_lv': 0, 'atk': 1600, 'def': 1600, 'hp': 5500, 'mp': 3500, 'agi': 1400, 'eva': 1400, 'grow': 1.3, 'life': 8000},
    236: {'type': '泡泡灵仙', 'type2': '灵仙资质', 'allow_lv': 0, 'atk': 1600, 'def': 1600, 'hp': 5500, 'mp': 3500, 'agi': 1400, 'eva': 1400, 'grow': 1.3, 'life': 8000},
    237: {'type': '泡泡灵仙', 'type2': '灵仙资质', 'allow_lv': 0, 'atk': 1600, 'def': 1600, 'hp': 5500, 'mp': 3500, 'agi': 1400, 'eva': 1400, 'grow': 1.3, 'life': 8000},
    310: {'type': '普通', 'allow_lv': 0, 'atk': 960, 'def': 960, 'hp': 3900, 'mp': 1200, 'agi': 840, 'eva': 1080, 'grow': 0.918, 'life': 12000},
    311: {'type': '普通', 'allow_lv': 0, 'atk': 1200, 'def': 900, 'hp': 2400, 'mp': 1200, 'agi': 1440, 'eva': 1200, 'grow': 1.02, 'life': 7500},
    312: {'type': '普通', 'allow_lv': 0, 'atk': 1080, 'def': 840, 'hp': 2700, 'mp': 1200, 'agi': 1200, 'eva': 1020, 'grow': 0.918, 'life': 9000},
    313: {'type': '普通', 'allow_lv': 5, 'atk': 1200, 'def': 1200, 'hp': 3600, 'mp': 2100, 'agi': 1320, 'eva': 1320, 'grow': 1.03, 'life': 7500},
    314: {'type': '普通', 'allow_lv': 0, 'atk': 1200, 'def': 900, 'hp': 2400, 'mp': 1200, 'agi': 1440, 'eva': 1200, 'grow': 1.02, 'life': 7500},
    315: {'type': '普通', 'allow_lv': 15, 'atk': 1320, 'def': 1080, 'hp': 3600, 'mp': 3000, 'agi': 1080, 'eva': 1020, 'grow': 1.055, 'life': 9000},
    316: {'type': '普通', 'allow_lv': 15, 'atk': 1380, 'def': 1320, 'hp': 3900, 'mp': 1200, 'agi': 1080, 'eva': 1200, 'grow': 1.04, 'life': 7500},
    317: {'type': '普通', 'allow_lv': 25, 'atk': 1080, 'def': 1380, 'hp': 4800, 'mp': 2400, 'agi': 840, 'eva': 1080, 'grow': 1.03, 'life': 14000},
    318: {'type': '普通', 'allow_lv': 25, 'atk': 1080, 'def': 1080, 'hp': 3000, 'mp': 1500, 'agi': 1200, 'eva': 1020, 'grow': 0.969, 'life': 9000},
    319: {'type': '普通', 'allow_lv': 35, 'atk': 960, 'def': 1200, 'hp': 3600, 'mp': 2700, 'agi': 1380, 'eva': 1080, 'grow': 1.04, 'life': 12000},
    320: {'type': '普通', 'allow_lv': 5, 'atk': 1320, 'def': 900, 'hp': 2880, 'mp': 1200, 'agi': 1380, 'eva': 1320, 'grow': 1.03, 'life': 7500},
    321: {'type': '普通', 'allow_lv': 15, 'atk': 1320, 'def': 1380, 'hp': 4800, 'mp': 1800, 'agi': 840, 'eva': 1080, 'grow': 1.03, 'life': 12000},
    322: {'type': '普通', 'allow_lv': 15, 'atk': 1440, 'def': 900, 'hp': 3600, 'mp': 1200, 'agi': 1320, 'eva': 1200, 'grow': 1.142, 'life': 7500},
    323: {'type': '普通', 'allow_lv': 25, 'atk': 1200, 'def': 1380, 'hp': 4800, 'mp': 2580, 'agi': 960, 'eva': 1080, 'grow': 1.045, 'life': 12000},
    324: {'type': '普通', 'allow_lv': 25, 'atk': 1320, 'def': 900, 'hp': 2400, 'mp': 1200, 'agi': 1320, 'eva': 1200, 'grow': 1.03, 'life': 7500},
    325: {'type': '普通', 'allow_lv': 25, 'atk': 1440, 'def': 900, 'hp': 2700, 'mp': 2700, 'agi': 1320, 'eva': 1200, 'grow': 1.045, 'life': 7500},
    326: {'type': '普通', 'allow_lv': 25, 'atk': 1380, 'def': 1320, 'hp': 3600, 'mp': 1200, 'agi': 1080, 'eva': 1020, 'grow': 1.03, 'life': 9000},
    327: {'type': '普通', 'allow_lv': 25, 'atk': 1320, 'def': 1200, 'hp': 3600, 'mp': 2400, 'agi': 1320, 'eva': 1320, 'grow': 1.04, 'life': 7500},
    328: {'type': '普通', 'allow_lv': 35, 'atk': 1320, 'def': 1320, 'hp': 3600, 'mp': 1500, 'agi': 1080, 'eva': 1020, 'grow': 1.055, 'life': 9000},
    329: {'type': '普通', 'allow_lv': 35, 'atk': 1320, 'def': 1200, 'hp': 3900, 'mp': 1320, 'agi': 1080, 'eva': 1080, 'grow': 1.04, 'life': 9000},
    330: {'type': '普通', 'allow_lv': 35, 'atk': 1080, 'def': 1356, 'hp': 4800, 'mp': 2400, 'agi': 960, 'eva': 1080, 'grow': 1.03, 'life': 12000},
    331: {'type': '普通', 'allow_lv': 35, 'atk': 1320, 'def': 1356, 'hp': 4800, 'mp': 2580, 'agi': 960, 'eva': 1080, 'grow': 1.03, 'life': 12000},
    332: {'type': '普通', 'allow_lv': 35, 'atk': 1500, 'def': 900, 'hp': 2700, 'mp': 1800, 'agi': 1320, 'eva': 1200, 'grow': 1.055, 'life': 7500},
    333: {'type': '普通', 'allow_lv': 35, 'atk': 960, 'def': 900, 'hp': 2700, 'mp': 3000, 'agi': 1320, 'eva': 1200, 'grow': 1.055, 'life': 7500},
    334: {'type': '普通', 'allow_lv': 35, 'atk': 1080, 'def': 960, 'hp': 2700, 'mp': 2100, 'agi': 1320, 'eva': 1200, 'grow': 1.055, 'life': 7500},
    335: {'type': '普通', 'allow_lv': 35, 'atk': 1440, 'def': 960, 'hp': 2700, 'mp': 2400, 'agi': 1320, 'eva': 1200, 'grow': 1.055, 'life': 7500},
    336: {'type': '普通', 'allow_lv': 0, 'atk': 960, 'def': 1380, 'hp': 3600, 'mp': 1500, 'agi': 840, 'eva': 1320, 'grow': 1.071, 'life': 12000},
    337: {'type': '普通', 'allow_lv': 0, 'atk': 1320, 'def': 1200, 'hp': 2700, 'mp': 2100, 'agi': 1320, 'eva': 1200, 'grow': 0.969, 'life': 9000},
    338: {'type': '普通', 'allow_lv': 35, 'atk': 1320, 'def': 1380, 'hp': 4800, 'mp': 1800, 'agi': 840, 'eva': 1080, 'grow': 1.122, 'life': 12000},
    339: {'type': '普通', 'allow_lv': 35, 'atk': 960, 'def': 1200, 'hp': 3600, 'mp': 2700, 'agi': 1380, 'eva': 1080, 'grow': 1.173, 'life': 12000},
    340: {'type': '普通', 'allow_lv': 35, 'atk': 1080, 'def': 1380, 'hp': 4800, 'mp': 2400, 'agi': 840, 'eva': 1080, 'grow': 1.142, 'life': 9000},
    341: {'type': '普通', 'allow_lv': 35, 'atk': 1080, 'def': 1200, 'hp': 3600, 'mp': 2700, 'agi': 1380, 'eva': 1080, 'grow': 1.202, 'life': 12000},
    342: {'type': '普通', 'allow_lv': 35, 'atk': 1080, 'def': 1080, 'hp': 3000, 'mp': 1500, 'agi': 1200, 'eva': 1020, 'grow': 1.173, 'life': 7500},
    343: {'type': '普通', 'allow_lv': 35, 'atk': 1320, 'def': 1080, 'hp': 3600, 'mp': 3000, 'agi': 1080, 'eva': 1020, 'grow': 1.202, 'life': 9000},
    344: {'type': '普通', 'allow_lv': 35, 'atk': 1320, 'def': 900, 'hp': 2400, 'mp': 1200, 'agi': 1320, 'eva': 1200, 'grow': 1.142, 'life': 7500},
    345: {'type': '普通', 'allow_lv': 35, 'atk': 1500, 'def': 900, 'hp': 2700, 'mp': 1800, 'agi': 1320, 'eva': 1200, 'grow': 1.202, 'life': 7500},
    346: {'type': '普通', 'allow_lv': 35, 'atk': 1440, 'def': 900, 'hp': 3600, 'mp': 1200, 'agi': 1320, 'eva': 1200, 'grow': 1.173, 'life': 7500},
    347: {'type': '普通', 'allow_lv': 35, 'atk': 1320, 'def': 1200, 'hp': 3600, 'mp': 2400, 'agi': 1320, 'eva': 1320, 'grow': 1.122, 'life': 9000},
    348: {'type': '普通', 'allow_lv': 35, 'atk': 1200, 'def': 1200, 'hp': 3600, 'mp': 2100, 'agi': 1320, 'eva': 1320, 'grow': 1.111, 'life': 7500},
    349: {'type': '普通', 'allow_lv': 35, 'atk': 1440, 'def': 900, 'hp': 2700, 'mp': 2400, 'agi': 1320, 'eva': 1200, 'grow': 1.173, 'life': 7500},
    350: {'type': '普通', 'allow_lv': 35, 'atk': 1500, 'def': 900, 'hp': 2700, 'mp': 1800, 'agi': 1320, 'eva': 1200, 'grow': 1.173, 'life': 7500},
    351: {'type': '普通', 'allow_lv': 35, 'atk': 1320, 'def': 1320, 'hp': 3600, 'mp': 1500, 'agi': 1080, 'eva': 1020, 'grow': 1.151, 'life': 9000},
    352: {'type': '普通', 'allow_lv': 35, 'atk': 1320, 'def': 1080, 'hp': 3600, 'mp': 3000, 'agi': 1080, 'eva': 1020, 'grow': 1.173, 'life': 7500},
    353: {'type': '普通', 'allow_lv': 35, 'atk': 1440, 'def': 900, 'hp': 3600, 'mp': 1200, 'agi': 1320, 'eva': 1200, 'grow': 1.202, 'life': 9000},
    354: {'type': '普通', 'allow_lv': 35, 'atk': 1320, 'def': 1080, 'hp': 3600, 'mp': 3000, 'agi': 1080, 'eva': 1020, 'grow': 1.055, 'life': 7500},
    400: {'type': '普通', 'allow_lv': 55, 'atk': 1440, 'def': 1320, 'hp': 4560, 'mp': 2400, 'agi': 1440, 'eva': 1080, 'grow': 1.224, 'life': 8000},
    401: {'type': '普通', 'allow_lv': 65, 'atk': 1380, 'def': 1440, 'hp': 4200, 'mp': 2760, 'agi': 1440, 'eva': 1320, 'grow': 1.203, 'life': 8000},
    402: {'type': '普通', 'allow_lv': 65, 'atk': 1380, 'def': 1200, 'hp': 3600, 'mp': 2160, 'agi': 1380, 'eva': 1440, 'grow': 1.224, 'life': 9000},
    403: {'type': '普通', 'allow_lv': 65, 'atk': 1440, 'def': 1380, 'hp': 3600, 'mp': 2400, 'agi': 1440, 'eva': 1320, 'grow': 1.202, 'life': 7500},
    404: {'type': '普通', 'allow_lv': 85, 'atk': 1440, 'def': 1260, 'hp': 4200, 'mp': 2400, 'agi': 1380, 'eva': 1320, 'grow': 1.234, 'life': 8000},
    405: {'type': '普通', 'allow_lv': 85, 'atk': 1100, 'def': 1440, 'hp': 3600, 'mp': 3000, 'agi': 1380, 'eva': 1320, 'grow': 1.253, 'life': 9000},
    406: {'type': '普通', 'allow_lv': 105, 'atk': 1320, 'def': 1380, 'hp': 4800, 'mp': 2400, 'agi': 1440, 'eva': 1560, 'grow': 1.254, 'life': 7000},
    407: {'type': '普通', 'allow_lv': 105, 'atk': 1500, 'def': 1400, 'hp': 4800, 'mp': 1600, 'agi': 1440, 'eva': 1200, 'grow': 1.263, 'life': 7500},
    408: {'type': '普通', 'allow_lv': 105, 'atk': 1440, 'def': 1500, 'hp': 4320, 'mp': 3200, 'agi': 1440, 'eva': 1520, 'grow': 1.264, 'life': 8000},
    409: {'type': '普通', 'allow_lv': 125, 'atk': 1440, 'def': 1440, 'hp': 4560, 'mp': 3000, 'agi': 1440, 'eva': 1560, 'grow': 1.264, 'life': 6000},
    410: {'type': '普通', 'allow_lv': 125, 'atk': 1440, 'def': 1380, 'hp': 5760, 'mp': 3000, 'agi': 1440, 'eva': 1560, 'grow': 1.264, 'life': 6000},
    411: {'type': '普通', 'allow_lv': 125, 'atk': 1500, 'def': 1440, 'hp': 4800, 'mp': 2160, 'agi': 1560, 'eva': 1440, 'grow': 1.263, 'life': 9000},
    412: {'type': '普通', 'allow_lv': 155, 'atk': 1500, 'def': 1440, 'hp': 4800, 'mp': 2880, 'agi': 1476, 'eva': 1560, 'grow': 1.275, 'life': 9000},
    413: {'type': '普通', 'allow_lv': 155, 'atk': 1500, 'def': 1440, 'hp': 4800, 'mp': 2880, 'agi': 1476, 'eva': 1560, 'grow': 1.275, 'life': 9000},
    414: {'type': '普通', 'allow_lv': 155, 'atk': 1440, 'def': 1500, 'hp': 5400, 'mp': 3240, 'agi': 1320, 'eva': 1200, 'grow': 1.294, 'life': 9000},
    415: {'type': '普通', 'allow_lv': 155, 'atk': 1440, 'def': 1440, 'hp': 5500, 'mp': 3240, 'agi': 1320, 'eva': 1560, 'grow': 1.275, 'life': 8000},
    416: {'type': '普通', 'allow_lv': 175, 'atk': 1, 'def': 1, 'hp': 1, 'mp': 1, 'agi': 1, 'eva': 1, 'grow': 1.0, 'life': 1},
    417: {'type': '普通', 'allow_lv': 175, 'atk': 1500, 'def': 1500, 'hp': 5040, 'mp': 2600, 'agi': 1200, 'eva': 1200, 'grow': 1.275, 'life': 7500},
    418: {'type': '普通', 'allow_lv': 175, 'atk': 1519, 'def': 1419, 'hp': 5049, 'mp': 2889, 'agi': 1389, 'eva': 1329, 'grow': 1.289, 'life': 8000},
    419: {'type': '普通', 'allow_lv': 175, 'atk': 1440, 'def': 1380, 'hp': 4080, 'mp': 2160, 'agi': 1320, 'eva': 1500, 'grow': 1.275, 'life': 7500},
    420: {'type': '普通', 'allow_lv': 175, 'atk': 1404, 'def': 1400, 'hp': 4080, 'mp': 2160, 'agi': 1200, 'eva': 1320, 'grow': 1.275, 'life': 7500},
    421: {'type': '普通', 'allow_lv': 175, 'atk': 1440, 'def': 1380, 'hp': 4200, 'mp': 2160, 'agi': 1200, 'eva': 1440, 'grow': 1.275, 'life': 7500},
    422: {'type': '普通', 'allow_lv': 175, 'atk': 1500, 'def': 1380, 'hp': 4080, 'mp': 2160, 'agi': 1440, 'eva': 1620, 'grow': 1.285, 'life': 7000},
    423: {'type': '普通', 'allow_lv': 175, 'atk': 1404, 'def': 1400, 'hp': 4200, 'mp': 2160, 'agi': 1380, 'eva': 1500, 'grow': 1.275, 'life': 7500},
    424: {'type': '普通', 'allow_lv': 65, 'atk': 1416, 'def': 1440, 'hp': 4440, 'mp': 3000, 'agi': 1320, 'eva': 1380, 'grow': 1.224, 'life': 7500},
    425: {'type': '普通', 'allow_lv': 105, 'atk': 1416, 'def': 1476, 'hp': 4800, 'mp': 2820, 'agi': 1560, 'eva': 1440, 'grow': 1.264, 'life': 9000},
    426: {'type': '普通', 'allow_lv': 105, 'atk': 1416, 'def': 1476, 'hp': 4800, 'mp': 2820, 'agi': 1560, 'eva': 1440, 'grow': 1.264, 'life': 9000},
    427: {'type': '普通', 'allow_lv': 105, 'atk': 1416, 'def': 1476, 'hp': 4800, 'mp': 2820, 'agi': 1560, 'eva': 1440, 'grow': 1.264, 'life': 9000},
    428: {'type': '普通', 'allow_lv': 105, 'atk': 1416, 'def': 1476, 'hp': 4800, 'mp': 2820, 'agi': 1560, 'eva': 1440, 'grow': 1.264, 'life': 9000},
    429: {'type': '普通', 'allow_lv': 105, 'atk': 1416, 'def': 1476, 'hp': 4800, 'mp': 2820, 'agi': 1560, 'eva': 1440, 'grow': 1.264, 'life': 9000},
    430: {'type': '普通', 'allow_lv': 155, 'atk': 1440, 'def': 1500, 'hp': 4800, 'mp': 3240, 'agi': 1560, 'eva': 1680, 'grow': 1.285, 'life': 9000},
    431: {'type': '普通', 'allow_lv': 155, 'atk': 1440, 'def': 1500, 'hp': 4800, 'mp': 3240, 'agi': 1560, 'eva': 1680, 'grow': 1.285, 'life': 9000},
    432: {'type': '普通', 'allow_lv': 175, 'atk': 1584, 'def': 1464, 'hp': 4800, 'mp': 2160, 'agi': 1500, 'eva': 1320, 'grow': 1.285, 'life': 9000},
    433: {'type': '普通', 'allow_lv': 175, 'atk': 1536, 'def': 1380, 'hp': 6000, 'mp': 2640, 'agi': 1380, 'eva': 960, 'grow': 1.275, 'life': 8000},
}

#: 资质池（运行时 `[:池名, ...]` / `:池名` 引用的那份数值）
POOLS = {
    '灵仙资质': {'type': '泡泡灵仙', 'allow_lv': 0, 'atk': 1600, 'def': 1600, 'hp': 5500, 'mp': 3500, 'agi': 1400, 'eva': 1400, 'grow': 1.3, 'life': 8000},
    '神兽资质': {'type': '神兽', 'allow_lv': 0, 'atk': 1600, 'def': 1600, 'hp': 6500, 'mp': 3500, 'agi': 1800, 'eva': 1800, 'grow': 1.3, 'life': 'infinite'},
    '神兽资质2': {'type': '神兽', 'allow_lv': 0, 'atk': 1700, 'def': 1700, 'hp': 6650, 'mp': 3650, 'agi': 1900, 'eva': 1900, 'grow': 1.4, 'life': 'infinite'},
    '神兽资质3': {'type': '神兽', 'allow_lv': 0, 'atk': 1800, 'def': 1800, 'hp': 6800, 'mp': 3800, 'agi': 2000, 'eva': 2000, 'grow': 1.5, 'life': 'infinite'},
    '神兽资质4': {'type': '神兽', 'allow_lv': 0, 'atk': 1900, 'def': 1900, 'hp': 7000, 'mp': 4000, 'agi': 2100, 'eva': 2100, 'grow': 1.6, 'life': 'infinite'},
}

#: **资质硬上限**（`$baby[:_max]`，六项 + grow；`_p` = 已进阶档）
#: ⚠ 游戏读资质是 `min(@值, 上限)` ⇒ 写超上限的数游戏里看不出来。
MAX_ATTR = {
    '普通': {'atk': 1600, 'def': 1600, 'hp': 6500, 'mp': 3500, 'agi': 1800, 'eva': 1800, 'grow': 1.3},
    '普通_p': {'atk': 1700, 'def': 1700, 'hp': 6650, 'mp': 3750, 'agi': 1900, 'eva': 1900, 'grow': 1.5},
    '泡泡灵仙': {'atk': 1600, 'def': 1600, 'hp': 5500, 'mp': 3500, 'agi': 1400, 'eva': 1400, 'grow': 1.3},
    '泡泡灵仙_p': {'atk': 1600, 'def': 1600, 'hp': 5500, 'mp': 3500, 'agi': 1400, 'eva': 1400, 'grow': 1.3},
    '神兽': {'atk': 1900, 'def': 1900, 'hp': 7000, 'mp': 4000, 'agi': 2100, 'eva': 2100, 'grow': 1.6},
    '神兽_p': {'atk': 2000, 'def': 2000, 'hp': 7200, 'mp': 4200, 'agi': 2200, 'eva': 2200, 'grow': 1.8},
}


# ---------------------------------------------------------------- 兜底（真值表外）
# `SPECIES` / `POOLS` 已是**内测版真值**（257 条 / 5 个池，解析 `$baby`），
# 绝大多数召唤兽的六项资质**不再需要估算**。下面这套只服务真值表里没有的 id。
#
# ⚠ 「是不是召唤兽」一律看 `babies.Babies.is_baby_entry()`（有名字、不是玩家
#   角色 / 坐骑 / 空占位）。`V201_BABY_IDS` 只是**候选 id 全集**，比真值表宽：
#   135~254 段真值只覆盖 64 个 id，剩下 56 个（176~178 / 188~199 / 205~209 /
#   211~229 / 238~254）若在 `Data\\Actors` 里有名字，仍走这里取估算值。
#
# 真实分段（实测 `csv/Actors_角色.csv`，2026-10-03）：
#   1~20      玩家角色（**不是**）      21~134   普通召唤兽
#   135~170   神兽                      171~254  神兽 / 小孩 / 泡泡灵仙系列
#   255       `--坐骑--` 分隔（**不是**） 256~309  坐骑（**不是**）
#   310~354   普通召唤兽                355~399  空占位（**不是**）
#   400~433   普通召唤兽
V201_BABY_IDS = frozenset(
    [*range(21, 135), *range(135, 255),
     *range(310, 355), *range(400, 434)]
)
#: 神兽 / 小孩 / 灵仙区间（实测）：135~254。
GOD_ID_RANGE = (135, 255)
#: 兜底用的普通池基准（真值 `SPECIES[21]` 的量级）。
_V201_NORMAL = {'type': '普通', 'allow_lv': 0, 'atk': 960, 'def': 960,
                'hp': 3600, 'mp': 1200, 'agi': 840, 'eva': 1320,
                'grow': 0.918, 'life': 12000}


def _v201_fallback(baby_id):
    """真值表里没有这个 id 时的兜底：**按 id 区间**判类型、给基准资质。

    返回 None 表示「这个 id 连候选都不是」（例如 1~20 的玩家角色），让调用方
    （`Babies.candidates()`）照旧过滤掉 —— 宁缺毋滥。
    `inferred=True` 标记告诉界面「这条是估的」，由界面提示用户。
    """
    i = int(baby_id)
    if i not in V201_BABY_IDS:
        return None                    # 不是召唤兽（例如 1~20 的玩家角色）
    lo, hi = GOD_ID_RANGE
    if lo <= i <= hi:
        cfg = dict(POOLS['神兽资质'])
    else:
        cfg = dict(_V201_NORMAL)
    cfg['inferred'] = True
    return cfg


def config_of(baby_id, data_key=None):
    """取某种召唤兽的配置：备注池 → id 查表 → **兜底**。

    第一档服务老档（`Data\\Actors` 的 note 写了 `data = :池名`）；第二档是主路
    （内测版 257 条真值）；第三档只给真值表外的 id 估算值。
    """
    if data_key and data_key in POOLS:
        return POOLS[data_key]
    got = SPECIES.get(int(baby_id))
    if got:
        return got
    return _v201_fallback(baby_id)


#: 六项资质（+成长）的内部键，顺序与 `Game_Baby_Attr#set_max_zizhi` 一致
ATTR_KEYS = ("atk", "def", "hp", "mp", "agi", "eva", "grow")


def max_attr(type_name, promote=False):
    """该档位在游戏里的**资质硬上限**（`{atk: …, grow: …}`）；查不到返回 None。

    `type_name` = `$baby` 的 `:type`（普通 / 神兽 / 泡泡灵仙）；
    `promote` = 是否已进阶（存档里 `@attr.@promote`）。
    游戏侧同一个函数：`BabyManager.get_attr_max(type, promote)`。
    """
    key = "%s_p" % (type_name,) if promote else str(type_name)
    return MAX_ATTR.get(key)

