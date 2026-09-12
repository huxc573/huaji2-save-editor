# -*- coding: utf-8 -*-
"""中文注释表：把存档里的字段名翻译成人能看懂的中文。

来源：
  * `Data\\Scripts.rvdata2` 里游戏自己的类定义（`tools/dump_scripts.py` 导出的
    `tools/_scripts/*.rb`）；
  * `tools/_sv.txt` / `tools/_pty.txt` / `tools/_baby.txt` / `tools/_attrs.txt`
    这些结构探查结果（实测存档里的真实字段名）。

用法（界面里）：
    from xj_notes import note_of_ivar, note_of_class, SECTION_NOTES
    note_of_ivar("@gold")            # -> "存银（金钱）"
    note_of_ivar("@体质")            # -> "体质（五维之一）"
    note_of_class("Game_Baby")       # -> "召唤兽"
"""

# --------------------------------------------------------------------------
# 顶层分区
# --------------------------------------------------------------------------
SECTION_NOTES = {
    "system": "系统（存/读档次数、成就、随机种子、防作弊校验种子…）",
    "timer": "计时器",
    "message": "对话框状态（正在显示的文字/脸图）",
    "switches": "开关（本作只用了 3 个）",
    "variables": "变量（本作只用了 3 个）",
    "self_switches": "独立开关（每个地图事件自己的 A/B/C/D）",
    "actors": "角色数据（8 个槽位，@data[角色id]）",
    "party": "队伍（存银、步数、背包、出战成员…）",
    "troop": "当前战斗的敌群",
    "map": "当前地图（地图 id、事件、卷动位置…）",
    "player": "主角（坐标、朝向、队伍跟随）",
}

# --------------------------------------------------------------------------
# 通用 ivar（很多类共用）
# --------------------------------------------------------------------------
IVAR_NOTES = {
    # ---- 金钱 / 队伍
    "@gold": "存银（金钱，游戏里就叫\"存银\"，Lock 包装）",
    "@limit_gold": "存银上限/累计计数（游戏里另有的一笔）",
    "@value": "数值本体",
    "@master": "防作弊校验和（= 数值*91+45+种子/800，改数值要同步重算）",
    "@steps": "步数",
    "@last_item": "最后使用的道具",
    "@menu_actor_id": "菜单里选中的角色",
    "@target_actor_id": "被指定的目标角色",
    "@actors": "出战成员 id",
    "@items": "背包（槽号 → [道具对象, 数量]，每页 20 格，共 4 页）",
    "@weapons": "武器袋（槽号 → [武器对象, 数量]）",
    "@armors": "防具袋（槽号 → [防具对象, 数量]）",
    "@hash": "队伍杂项（仓库/阵型/疲劳/自动战斗池…）",
    "@in_battle": "是否在战斗中",

    # ---- 角色 / 召唤兽 通用
    "@actor_id": "角色 id（召唤兽则是召唤兽 id）",
    "@name": "名字",
    "@nickname": "昵称",
    "@class_id": "职业 id",
    "@level": "等级",
    "@hp": "当前气血（HP）",
    "@mp": "当前魔法（MP）",
    "@tp": "TP（战术点）",
    "@exp": "经验值（Hash：职业id → 经验）",
    "@limit_exp": "升下一级所需经验",
    "@equips": "装备（6 格：0 武器、1-5 防具；召唤兽 4 格）",
    "@skills": "已学技能 id",
    "@attr": "属性对象（Game_Actor_Attr / Game_Baby_Attr）",
    "@character_name": "行走图",
    "@character_index": "行走图序号",
    "@face_name": "脸图",
    "@face_index": "脸图序号",
    "@battler_name": "战斗图",
    "@battler_hue": "战斗图色调",
    "@hue": "色调",

    # ---- 召唤兽专属
    "@babys": "携带的召唤兽（数组）",
    "@baby": "当前出战的那只召唤兽",
    "@signature": "个体特征码（每只召唤兽唯一）",
    "@seed": "随机种子（技能/个体）",
    "@seeds": "随机种子表",
    "@mutation": "是否变异（变异 = 资质更好）",
    "@dyeing": "染色",
    "@battler_dir_": "战斗图目录名（通常就是召唤兽名）",
    "@battler_weapon_": "武器战斗图",
    "@type": "类型（:普通 / :变异…）",
    "@allow_lv": "捕捉所需等级",
    "@atk": "攻击资质",
    "@def": "防御资质",
    "@agi": "速度资质",
    "@eva": "躲闪资质",
    "@grow": "成长（资质成长率）",
    "@five": "五行",
    "@life": "寿命",
    "@loyalty": "忠诚度（<100 不能参战）",
    "@体质": "体质（影响气血）",
    "@法力": "法力（影响魔法/灵力）",
    "@力量": "力量（影响攻击）",
    "@耐力": "耐力（影响防御）",
    "@敏捷": "敏捷（影响速度/躲闪）",
    "@潜能": "潜能（可分配点数）",
    "@人气": "人气",
    "@贡献": "贡献",
    "@体力": "体力（上限 200）",
    "@活力": "活力（上限 200）",
    "@fatigue": "疲劳度",

    # ---- 战斗状态（大部分时候不用管）
    "@result": "上一次战斗结算结果",
    "@actions": "本回合行动",
    "@speed": "速度",
    "@guarding": "是否防御中",
    "@hidden": "是否隐藏",
    "@real_dead": "是否真的倒下",
    "@die_turn": "倒下回合",
    "@states": "附加的状态 id",
    "@state_turns": "状态剩余回合",
    "@state_steps": "状态剩余步数",
    "@buffs": "能力强化/弱化（8 项，百分比）",
    "@buff_turns": "强化剩余回合",
    "@param_plus": "能力加成（8 项：最大HP/MP/攻/防/魔攻/魔防/敏/运）",
    "@last_skill": "最后使用的技能",
    "@last_target_index": "上次目标下标",
    "@last_selected_index": "上次选择下标",
    "@animation_id": "动画 id",
    "@sprite_effect_type": "精灵特效",

    # ---- 系统
    "@save_count": "存档次数",
    "@battle_count": "战斗次数",
    "@save_disabled": "禁止存档（事件用）",
    "@menu_disabled": "禁止菜单",
    "@encounter_disabled": "禁止遇敌",
    "@formation_disabled": "禁止换阵",
    "@version": "存档版本",
    "@version_id": "版本号",
    "@gm_version": "GM 版本",
    "@seeds": "随机种子表（防作弊校验种子在这里面）",
    "@security": "安全/校验信息（物品计数校验：id → Change 对象）",
    "@config": "系统设置（机器码、网码、快捷键…）；换机器玩要改里面的 hard_disk_code",
    "@seeds": "随机种子（含防作弊用的 :shield）",
    "@frames_on_save": "存档时的游戏帧数",
    "@game_time": "游戏时间",
    "@config": "设置（音量、按键、本机硬盘码…）",
    "@tasks": "任务进度",
    "@achievement": "成就",
    "@dynamic_event": "动态事件（刷怪/新闻）",
    "@events": "事件表",
    "@bgm_on_save": "存档时的 BGM",
    "@bgs_on_save": "存档时的 BGS",
    "@window_tone": "画面色调",
    "@battle_bgm": "战斗 BGM",
    "@battle_end_me": "战斗结束 ME",
    "@saved_bgm": "保存的 BGM",
    "@cheated": "作弊计数（游戏自己记的）",
    "@keyword": "关键字",
    "@time": "时间",
    "@data": "数据数组",

    # ---- 主角 / 地图
    "@x": "X 坐标",
    "@y": "Y 坐标",
    "@direction": "朝向",
    "@map_id": "地图 id",
    "@display_x": "显示 X 偏移",
    "@display_y": "显示 Y 偏移",
    "@scroll_x": "卷动 X",
    "@scroll_y": "卷动 Y",
    "@map": "地图数据",
    "@interpreter": "事件解释器",
    "@self_switches": "独立开关",
}

# 中文 ivar 的补充说明（五维/资质这类成组的）
IVAR_GROUP = {
    "@体质": "召唤兽/角色的五维之一（影响气血）",
    "@法力": "五维之一（影响魔法）",
    "@力量": "五维之一（影响攻击）",
    "@耐力": "五维之一（影响防御）",
    "@敏捷": "五维之一（影响速度）",
    "@潜能": "五维之一（可分配点数）",
}

# --------------------------------------------------------------------------
# 类名 → 中文
# --------------------------------------------------------------------------
CLASS_NOTES = {
    "Game_Actor": "角色",
    "Game_Actor_Attr": "角色属性（中文五维）",
    "Game_Actors": "角色容器",
    "Game_Party": "队伍",
    "Game_Baby": "召唤兽",
    "Game_Baby_Attr": "召唤兽属性（资质/忠诚/寿命）",
    "Game_System": "系统",
    "Game_Timer": "计时器",
    "Game_Message": "对话框状态",
    "Game_Switches": "开关",
    "Game_Variables": "变量",
    "Game_SelfSwitches": "独立开关",
    "Game_Troop": "敌群",
    "Game_Map": "地图",
    "Game_Player": "主角",
    "Game_ActionResult": "战斗结算",
    "Game_Action": "战斗行动",
    "Game_BaseItem": "道具引用（武器/防具/技能通用）",
    "Game_Achievement": "成就",
    "Game_Dynamic_Event": "动态事件",
    "Game_Interpreter": "事件解释器",
    "Game_Event": "地图事件",
    "Game_CommonEvent": "公共事件",
    "Lock": "防作弊包装（@value + @master）",
    "RPG::Item": "道具（数据表里的定义）",
    "RPG::Weapon": "武器定义",
    "RPG::Armor": "防具定义",
    "RPG::Skill": "技能定义",
    "RPG::State": "状态定义",
    "RPG::Actor": "角色定义",
    "RPG::Class": "职业定义",
    "RPG::Enemy": "敌人定义",
    "RPG::Troop": "敌群定义",
    "RPG::UsableItem::Effect": "使用效果",
    "RPG::UsableItem::Damage": "伤害公式",
    "RPG::BaseItem::Feature": "特性",
}

# --------------------------------------------------------------------------
# 开关 / 变量（只有 3 个，名字来自游戏自己的 Config 模块）
# --------------------------------------------------------------------------
SWITCH_NAMES = {
    0: "（未使用）",
    1: "MAP_SCROLL 地图卷动",
    2: "PLOTING 剧情进行中（演出时锁操作）",
}

# `$game_system.config` 里的键（存档绑定等）
CONFIG_NOTES = {
    "hard_disk_code": "机器码（数组）：游戏启动时比对本机机器码，不匹配就弹「存档异常」；"
                      "换机器玩就把它加进去（工具里「机器码」面板可以一键处理）",
    "network_synchronous_code": "联网同步码",
    "send_temp": "发送临时标记",
    "shortcut_skill": "快捷键技能",
    "show_mp_bar": "显示魔法条",
    "dead_battler_command": "倒下队友指令",
}
VARIABLE_NAMES = {
    0: "（未使用）",
    1: "CHOICS_COLUMN 选项列数（对话框选项排几列）",
    2: "DIALOGUE 对话（当前对话 id / 状态）",
}

# --------------------------------------------------------------------------
# 背包
# --------------------------------------------------------------------------
PACK_PAGE_SIZE = 20      # 游戏里 pack(page) = container[page*20 + i]
PACK_PAGES = 4           # Game_Party::MAX_PACK_PAGE
MAX_GOLD = 30000000      # Config::Game::MAX_GOLD
MAX_ITEM = 99            # Config::Game::MAX_ITEM
MAX_LEVEL_ACTOR = 60
MAX_LEVEL_BABY = 65
MAX_BABY_LIFE = 12000
MAX_BABY_LOYALTY = 100


def note_of_section(name):
    return SECTION_NOTES.get(name, "")


def note_of_ivar(name):
    """ivar 名 → 中文说明（没有就返回空串）。"""
    if name in IVAR_GROUP:
        return IVAR_GROUP[name]
    return IVAR_NOTES.get(name, "")


def note_of_class(cls):
    return CLASS_NOTES.get(cls, "")


def note_of_switch(i, raw=None):
    n = SWITCH_NAMES.get(i)
    if n:
        return n
    return "开关 #%d（没名字，游戏里没用到）" % i


def note_of_variable(i, raw=None):
    n = VARIABLE_NAMES.get(i)
    if n:
        return n
    return "变量 #%d（没名字，游戏里没用到）" % i


def note_of_container(cls):
    """按容器/对象类名给一句说明。"""
    return CLASS_NOTES.get(cls, "")


def note_of_config(key):
    """`$game_system.config` 里的键 → 中文说明。"""
    return CONFIG_NOTES.get(key, "")
