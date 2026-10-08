# -*- coding: utf-8 -*-
"""《画迹2：缘起凡尘》存档工具 —— tkinter 界面（界面参照画迹1 的编辑器）。

页签（顺序与画迹1 对齐）：
  1. 概览 / 快捷修改      金钱/步数/次数 + 防作弊检测并修复（Lock/记账/标记一次修齐）
  2. 全部解析数据         全局搜索 + 树形浏览（懒加载）+ 右侧详情 + 右键菜单（中文注释）
  3. 角色 / 属性          等级/HP/MP/名字/经验 + 中文五维（Game_Actor_Attr）+ 技能装备
  4. 背包 / 物品          4 页 × 20 格：改数量 / 清空 / 添加（自动同步物品计数校验）
  5. 召唤兽               等级·气血·五维·六项资质·忠诚·寿命 + 常用预设
  6. 开关 / 变量          双击切换 / 修改（带游戏自己的名字注释）
  7. 数据表 (CSV)         Data\\*.rvdata2 → CSV（物品/武器/防具/技能/状态/角色/职业/敌人）
  8. 说明 / 机制          密钥、存档结构、防作弊、数据表说明
  9. 更新日志             CHANGELOG.md

启动：python src/huaji2_save_editor.py [存档路径] [--selftest]
"""
import os
import tempfile
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

try:
    sys.stdout.reconfigure(errors='replace')
except Exception:
    pass


def _setup_tcl_env():
    """打包成 exe 后 Tcl/Tk 的脚本库要显式指路。

    PyInstaller 不会自动收集它，得在打包时 `--add-data` 带上，
    运行时用 `TCL_LIBRARY` / `TK_LIBRARY` 指到解包目录（sys._MEIPASS）。
    必须在 `import tkinter` **之前**调用。
    """
    if not getattr(sys, "frozen", False):
        return
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(sys.executable)
    for sub, env in (("tcl8.6", "TCL_LIBRARY"), ("tk8.6", "TK_LIBRARY")):
        p = os.path.join(base, "tcl", sub)
        if os.path.isdir(p):
            os.environ[env] = p


_setup_tcl_env()

import tkinter as tk                              # noqa: E402
from tkinter import (filedialog, font as tkfont, messagebox,
                     ttk)                            # noqa: E402

import backup  # noqa: E402
import babies    # noqa: E402
import codec   # noqa: E402
import datatables      # noqa: E402
import paths     # noqa: E402
import game    # noqa: E402
import marshal_ruby as M  # noqa: E402
import doctree   # noqa: E402
import nodetext   # noqa: E402
import fieldnames   # noqa: E402
import itemattr   # noqa: E402
import save    # noqa: E402
from tables import sect   # noqa: E402


class _IV(object):
    """`save.ival(节点, "@actor_id")` 那种写法的小侍从（拿整数 ivar）。"""

    @staticmethod
    def ival(obj, name, default=0):
        v = M.value_of(save._deref(save.ivar(obj, name)))
        try:
            return default if v is None else int(v)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def none(obj, name, default=None):
        return save._deref(save.ivar(obj, name))

# ⚠ 带「内测版」（2026-10-02川定）：本分支适配**内测版 V2.201**，
#   与 main（尝鲜版 v0.x）并存且存档格式不通用 —— 标题必须一眼分清，
#   否则用户对着尝鲜版存档用内测版工具，只会看到"打不开"。
APP_NAME = "画迹2 内测版存档工具"
try:
    # 版本号单一来源 = tools/build.py 的 APP_VERSION（它生成 changelog.py）；
    # 界面标题 / 关于 / 帮助头都从这里取，升级只改 build.py 一处。
    import changelog as _xj_cl
    VERSION = "v" + _xj_cl.VERSION
except Exception:               # changelog 缺失时兜底（别让它再变成第二处真源）
    VERSION = "v2.201-beta.2"
AUTHOR = "huxc573"
HOMEPAGE = "https://github.com/huxc573/huaji2-save-editor"
ISSUES = HOMEPAGE + "/issues"
LICENSE_NAME = "MIT"
TITLE = "%s %s" % (APP_NAME, VERSION)

CHILD_LIMIT = 300          # 数据树每层最多显示多少项（真实存档有几万个容器）
LAST_TXT = os.path.join(os.path.expanduser("~"),
                        ".huaji2_save_editor_last_beta.txt")
DEFAULT_CSV_DIR = os.path.join(os.path.dirname(HERE), "csv")


def _in_temp(path):
    """路径是否在 %TEMP% 下（测试/自动化残留的假存档，绝不自动猜）。"""
    try:
        rp = os.path.realpath(path).lower()
        for base in (os.environ.get("TEMP", ""), tempfile.gettempdir()):
            if base and rp.startswith(os.path.realpath(base).lower()
                                      + os.sep):
                return True
        return False
    except Exception:
        return False


def _read_text(path, limit=200000):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()[:limit]
    except OSError:
        return "（读不到 %s）" % path


CHANGELOG = "（正在载入…）"      # 真正的内容在 _load_changelog() 定义之后赋值

# 注意：正文里有 `%`（浮动:20%）和 `@`，所以**只有表头**参与 %-格式化，
# 正文原样拼接 —— 否则会报 "not enough arguments for format string"。
HELP_HEAD = """%s %s
================================================================
 作者 @%s　·　开源地址 %s　·　协议 %s
================================================================

""" % (APP_NAME, VERSION, AUTHOR, HOMEPAGE, LICENSE_NAME)

HELP_BODY = """零、本工具是画迹1 存档编辑器的迭代产品
  界面、快捷键、右键菜单、"导出报告/导出明文"都沿用「画迹1 编辑器」的习惯，
  用过的直接上手。v0.4 新增了 4 个能改玩法数据的页：
      「背包 / 物品」（4 页×20 格，改数量/清空/加物品）
      「召唤兽」（等级·气血·魔法·六项资质·忠诚·寿命·成长·五维）
      「角色 / 属性」里的"获得经验"
      「概览 / 快捷修改」里的"防作弊体检"（一键修复 + 清除作弊标记）
  另外「数据表 (CSV)」页把 Data\\*.rvdata2 转成 CSV 查表。
  独立发行版：Release 上只挂一个 zip（huaji2-save-editor-vX.Y.Z.zip），
  解压出来的 画迹2内测版存档工具.exe 和 XJCodec32.exe 「必须放在同一个目录」。

一、这个游戏的存档
  <游戏根>\\save.rvdata2（手动存档）
  <游戏根>\\AutoSave\\save00..29.rvdata2（自动存档）
  格式：「AES-128-ECB + Zlib」（不是main.dll 那套 8 字节分组 ECB）——
    写：marshal(header)+marshal(contents) → Deflate → 零填充到 16 → AES-128-ECB
    读：AES 解密 → 首字节是'x' 就 Inflate → Marshal.load 两次
  实现见 src\\save_v201.py（纯 Python，不依赖 main.dll / 32 位宿主）。

二、两套加密（内测版 V2.201 与尝鲜版完全不同，别混用）
  【本工具＝内测版 V2.201】
  存档     153ad4v3fbdgbgd   ⚠ 15 字符，必须「零补齐」到 16 字节当 AES 密钥
  数据表   按文件名派生的 RC4：
           '9KQ1L0PWRESZV7HM' + b36(crc32(带扩展名的文件名))[0..13]，取「后」 16 字符
           ⚠ 取前 16 的话对所有文件都一样 ⇒ 谁也解不开（易踩）
           例外：main.rvdata2 是明文骨架、Scripts.rvdata2 解不开，别硬解
  【尝鲜版（main 分支，本工具不适用）】
  761205 / imoutogadaisuki / tiyan_version 三个密钥 + main.dll 的 8 字节分组 ECB
  ⇒ 「拿本工具开尝鲜版存档会失败，反之亦然」。要开尝鲜版请用 main 分支的 v0.6.0。

三、存档结构
  明文 = 两个 Marshal 对象相接（各自带 04 08 头）：
      { :temp => nil }                                      <- header
      { :system :timer :message :switches :variables
        :self_switches :actors :party :troop :map :player }  <- contents
  ⚠ 「内测版与尝鲜版结构有一处不同」：variables 内测版是「稀疏哈希」（键＝变量编号），
     尝鲜版是数组（下标＝编号）。实测内测版只有 {1,2,7} 三个键 ——
     「不能按位置当编号用」。工具已自动兼容。
  角色的五维/潜能是中文实例变量，放在 Game_Actor.@attr（类 Game_Actor_Attr）：
      @体质 @法力 @力量 @耐力 @敏捷 @潜能 @人气 @贡献 @体力 @活力

四、防作弊（尝鲜版查三层；⚠ 内测版 V2.201 是 Lock + Change 记账两层，详见 game.py）
  1) Lock 校验和：金钱等关键数值被 Lock 包着：
        @master = @value * 91 + 45 + seed / 800   （seed = $game_system.seeds[:shield]）
     游戏读的时候会验算，不一致就 msgbox '游戏异常！' 然后 exit。
     本工具改金钱时自动重算 @master。
  2) 周期检查（$jiance）：「尝鲜版」每 300 帧（约 5 秒）查一次
        角色等级 > 60 / 出战召唤兽等级 > 65 / 金钱 > 30,000,000 /
        仓库页号 > 3 / 五维总点数 > 等级*10+500
     超了就置 @cheated = 当前帧号，游戏弹「存档异常！」并退出。
     ⚠ 「内测版 V2.201 没有这一层」（脚本里 cheated / $jiance 全搜不到、
     存档也没有 @cheated / @keyword 字段）——工具只把上限值当「提示」用，
     不再说「会被判作弊」，上限已按 V2.201 改到 fieldnames：
        MAX_LEVEL_ACTOR 155 / MAX_LEVEL_BABY 165 / MAX_GOLD 9,999,999,999
        MAX_WAREHOUSE [0,12] / MAX_BABY_LIFE 14000
     金钱填超过上限时工具自动压到上限的 5/6，留余量。
  3) 记账校验（Change）：**两版都有**五类账（:gold 金钱 / :items 物品累计 /
     :variables 变量 / :renqi 人气 / :gongxian 贡献），游戏每次数值变动都拿账
     和实际值比对，对不上就判作弊（数值逐位 AES-ECB，密钥 admin_alskmcndfj）。
     实测内测版 V2.201 的 security **不是空的**（gold / renqi / gongxian /
     variables / achievement_point 各一笔；物品计数要等游戏自己发过道具才有条目）。
     ⚠ 惩罚方式两版不同：尝鲜版记 'NE!' 进 @cheated 再倒计时强退；内测版在线版是
     `Change#inspect` 不符就截屏上传 + msgbox「ne! + 密文」+ 当场 exit（离线补丁
     已把这段自杀网拆成只返回明文）。⇒ 工具改钱/改背包**必须**同步账，
     统一走 GameEditor.resync_all_security() 一次对齐五类。
     ⚠ 旧版工具读账用的是另一把密钥（admin_1941344749），自己写自己读永远「一致」、
     对游戏侧全盲；2026-10-04 已换成游戏真钥（见 src/aes.py 自检钉子）。
     内测版确实**没有** @cheated / @keyword 标记（脚本里 cheated / $jiance 全搜不到）
     —— 那是尝鲜版的第 2、第 4 层，跟记账无关。

五、Data 目录下的 .rvdata2
  「全都被加密」，但「内测版用的是按文件名派生的 RC4」（不是尝鲜版的 761205），
  实现见 src\\data_v201.py（纯 Python，实测 403/403 个表全部解出）。
  本工具直接解密＋解析，可转成 CSV 方便查表（Excel 双击即开，utf-8-sig 编码）：
      Items 物品 / Weapons 武器 / Armors 防具 / Skills 技能 / States 状态
      Actors 角色 / Classes 职业 / Enemies 敌人
      （可选：Troops 敌人队伍 / CommonEvents 公共事件）
  嵌套字段会翻成人话，例如物品 @effects →「HP回复 +500%；附加状态#1 0%」，
  伤害 →「伤害:无 公式:0 浮动:20% 会心:否 属性:0」。
  Map / System / Scripts / Tilesets / Animations 不转（用处不大）。

六、常用位置（第 2 页可以搜字段名直接跳过去）
  :party    @gold 金钱（Lock） @actors 出战成员 @items 背包 @steps 步数
            @warehouse_page 仓库页号
  :system   @security 五类记账(:gold/:items/:variables/:renqi/:gongxian)
            @cheated 作弊标记 @keyword 作弊记录(VNE/NE!) @seeds 防作弊种子
  :actors   @data[角色id] → @name @level @hp @mp @exp 经验 @attr(中文五维)
            @babies 召唤兽（等级/气血/魔法/六项资质/忠诚/寿命/成长/五维）
  :switches @data[编号]      :variables @data[编号]

七、背包怎么表示（想手改的人看）
  格子号 = 页号*20 + 格内序号（游戏的道具菜单是 4 页×20 格）
  @items[格子号] = [ 物品对象, 数量 ]     ← 物品对象里的 @id 才是物品 id
  清空格子 = 把值置 nil（不要删 key，免得后面 @N 链接错位）。
"""

HELP_TEXT = HELP_HEAD + HELP_BODY


def human(text):
    if isinstance(text, bytes):
        try:
            return text.decode("utf-8")
        except UnicodeDecodeError:
            return text.decode("gbk", "replace")
    return zh_text(str(text))


def parse_num(text):
    """输入框数字解析：能吃 '123'、'0x10'，也能吃游戏存出来的浮点 '200.0'。

    游戏有些字段是 Float（如角色的 @活力），fill 到输入框再原样点「应用」时，
    直接 int('200.0', 0) 会抛 ValueError —— 先按整数试，失败再按小数。
    """
    t = text.strip()
    try:
        return int(t, 0)
    except ValueError:
        return float(t)


# 英文异常消息 → 中文说法（字符串层面，专门给“直接弹 str(e)”的那些提示用）
ZH_PATTERNS = (
    ("object is not subscriptable",
     "存档结构不对：往空值上取了下标（多半是某件物品缺运行时的 @attr 之类的字段）"),
    ("object has no attribute",
     "存档里缺字段（可能不是本作存档，或者被改坏了）"),
    ("list index out of range", "序号/位置越界（存档里的格子或数组不够长）"),
    ("string index out of range", "字符串越界"),
    ("tuple index out of range", "序号越界"),
    ("invalid literal for int()", "要填数字的地方填了别的东西"),
    ("invalid literal for float()", "要填小数的地方填了别的东西"),
    ("unsupported operand type", "数值运算类型不对（某个字段不是数字）"),
    ("division by zero", "除数为 0"),
    ("not enough values to unpack", "数量对不上（预期的项数和存档里的不一样）"),
    ("unhashable type", "这个值不能当字典的键用"),
    ("'NoneType' object is not iterable", "存档里该有东西的地方是空的"),
    ("No such file or directory", "找不到文件"),
    ("Access is denied", "没有权限访问这个文件"),
    ("The process cannot access the file", "文件被占用（先关掉游戏/另一个工具窗口）"),
    ("cannot convert Array into String",
     "存档里这一段被改坏了（数组当成字符串用了）——先恢复 .bak 备份再改"),
)


def zh_text(s):
    """把常见英文异常消息换成中文说法（原文附在后面，方便对照）。"""
    for en, zh in ZH_PATTERNS:
        if en in s:
            return "%s（原文：%s）" % (zh, s[:160])
    return s


# Python / Windows 的异常消息大多是英文的，直接弹给用户看很难懂。
# 这里按异常类型翻译一句中文，再把原文（技术细节）附在后面。
ZH_ERRORS = (
    (KeyError, "存档里没有对应的东西（字段/格子/物品 id 可能不对）"),
    (IndexError, "存档里的序号/位置越界了"),
    (ValueError, "数值或格式不合法"),
    (TypeError, "存档结构和预期不一样（可能不是本作存档）"),
    (AttributeError, "存档里缺字段（可能不是本作存档，或者改坏了）"),
    (PermissionError, "文件被占用或没有权限 —— 先关掉游戏 / 另一个工具窗口再试"),
    (FileNotFoundError, "找不到文件"),
    (IsADirectoryError, "那是个文件夹，不是文件"),
    (UnicodeDecodeError, "文字编码不对"),
    (MemoryError, "内存不够"),
    (OSError, "文件读写失败"),
)


def zh_error(e, prefix=""):
    """异常 → 中文提示（弹框用）。技术细节原样附在后面，方便对照 error.log。"""
    txt = ""
    if isinstance(e, BaseException):
        for cls, zh in ZH_ERRORS:
            if isinstance(e, cls):
                txt = zh
                break
        name = type(e).__name__
        detail = human(str(e)).strip()
    else:
        name = "错误"
        detail = human(str(e)).strip()
    if detail.startswith("'"):
        detail = detail.strip("'\"")     # KeyError('...') 会带引号
    out = (prefix + "\n\n" if prefix else "")
    out += txt or "操作失败"
    if detail and detail != txt:
        out += "\n\n技术细节（%s）：%s" % (name, detail)
    return out


def _load_changelog():
    """更新日志：打包成 exe 时用**内置**那份（写死的，不依赖任何外部文件）；
    源码运行时直接看仓库里的 CHANGELOG.md。
    """
    frozen = bool(getattr(sys, "frozen", False))
    if frozen:
        try:
            import changelog
            if getattr(changelog, "TEXT", ""):
                return changelog.TEXT
        except Exception:
            pass
    for p in (os.path.join(os.path.dirname(HERE), "CHANGELOG.md"),
              os.path.join(codec.app_dir(), "CHANGELOG.md")):
        t = _read_text(p)
        if t and not t.startswith("（读不到"):
            return t
    try:
        import changelog
        if getattr(changelog, "TEXT", ""):
            return changelog.TEXT
    except Exception:
        pass
    return "（没有内置更新日志，也没找到 CHANGELOG.md）"


CHANGELOG = _load_changelog()


def actor_sash_pos(h, need, lo=80):
    """角色页上下分栏里，「属性概览」那一栏该分到多高（px）。

    * `h`    = 分栏容器（Panedwindow）的高度
    * `need` = 下面技能区**需要**的高度（它有搜索框 + 一排按钮 + 列表 + 说明，
      没有滚动条，被压一点就缺一块）
    * `lo`   = 概览最少也要留这么多（概览是只读 Text，自带滚动条，能缩）

    策略就是一句话：**先满足技能区**，剩下的给概览；实在不够就压到 lo，
    让技能区自己把列表缩掉（列表有滚动条，比按钮/说明被切好）。
    抽成纯函数是为了能在探针/冒烟里直接喂数字断言（真实窗口里量它要抢前台）。
    """
    if h <= 0:
        return lo
    return max(lo, min(h - need, h - lo))


#: 技能编辑器「门派」下拉代表「不筛」的那一项 —— 已取消（2026-09-20 川要求：
#: 「全部技能」列不出内容，直接删掉）。保留常量只会误导，所以一并删了；
#: 未选门派时 `var_actor_sect` 是空串，左栏清单留空 + 给一句话提示。


def sect_choice_labels():
    """「门派」下拉的全部选项（**无门派 + 14 个门派**，共 15 项）。

    门派**不是** Data 表，来自游戏脚本的 `$sects`（见 `sect`）。
    ⚠ 门派 id **不连号**：`0`、`1..13`、`20`（＝九黎城）—— 顺序照 id 排，
      所以九黎城排最后（2026-10-04 按真实 `$sects` 补齐，原来只有 12 个）。
    ⚠ 2026-09-27 川要求把「无门派」也放进来（原来 2026-09-20 排除了它）：
      这个下拉同时是「当前角色门派」的显示器 —— 无门派角色得有个值显示，
      而且选它 + 点「转门派」= **只把门派改成无门派**（技能一个不动）。选它时左栏会给一句提示，
      不再是死空白（见 `rebuild_learn_grid`）。
    ⚠ 「全部技能」仍然没有这一项（列出来就是几百个技能，没意义）。
    """
    out = []
    for sid in sorted(sect.SECTS):          # 0 无门派 在最前，然后 1..13 / 20
        nm = sect.sect_name(sid)
        if nm:
            out.append(nm)
    return out


def sk_match(sid, name, desc, kw):
    """技能搜索匹配 —— 技能一览和技能管理器共用这一套规则。

    2026-10-04 川：搜索要能"筛一批再批量操作"，所以比原来的
    「名字含关键词 / 关键词正好等于 id」多了两条：

    * 空格分开的**每一段都要命中**（AND）—— 搜 `高级 法术` = 两个词都得有；
    * 段以 `#` 开头（`#101`）→ 只比技能 id；
    * 段是纯数字 → id 精确命中，**或**名字 / 描述里出现这串数字；
    * 其余 → 名字或描述里含这个词（不区分大小写）。

    `kw` 为空（或全是空格）→ 全部命中。
    """
    kw = (kw or "").strip().lower()
    if not kw:
        return True
    hay = ("%s %s" % (name or "", desc or "")).lower()
    for part in kw.split():
        if part.startswith("#"):
            if str(sid) != part[1:]:
                return False
        elif part.isdigit():
            if str(sid) != part and part not in hay:
                return False
        elif part not in hay:
            return False
    return True


class SkillPicker(object):
    """技能一览的「看 + 选」逻辑：搜索过滤 + 说明框 + 悬停浮窗。

    角色页和召唤兽页共用（两边规则本来就一样）。**只管展示与选择、不写存档**
    —— 学 / 忘走 `SkillManager`（独立窗口），见那个类的说明。

    ⚠ 2026-10-04 拆过一次：原来这里还管一个「全部技能」只读下拉（选一个 →
      点「学会」），和下面的已学一览是**两套语义、两个入口**，搜索也只筛下拉
      不筛一览。现在统一成「一览 + 搜索筛一览」，学 / 忘都归技能管理器。
    """

    def __init__(self, app, key, tree, var_search, desc_text):
        self.app = app
        self.key = key                  # "baby" / "actor"，浮窗去重用
        self.tree = tree                # 技能一览（序 / id / 名字）
        self.var_search = var_search
        self.desc = desc_text           # 只读说明 Text
        self.source = []                # [(技能 id, 名字)]：这个目标已学的技能
        self.choices = []               # 当前可见的技能 id（筛选后）
        self.desc_full = ""

    # ------------------------------------------------------------ 数据
    def meta(self):
        """{技能 id: (名字, 描述)}。"""
        return self.app._skills_meta()

    def names(self):
        return self.app._skill_names()

    def set_source(self, pairs):
        """告诉它「这个目标已学了哪些技能」：`[(技能 id, 名字)]`，存档顺序。"""
        self.source = list(pairs)

    def sel_ids(self):
        """一览里当前选中的技能 id（可多选，按行顺序）。"""
        out = []
        for iid in self.tree.selection():
            try:
                out.append(int(iid[2:]))
            except (ValueError, IndexError):
                pass
        return out

    # ------------------------------------------------------------ 说明框
    def set_desc(self, text):
        """写说明框（它是 disabled 的，得临时开一下）。"""
        t = self.desc
        if t is None:
            return
        t.configure(state="normal")
        t.delete("1.0", "end")
        if text:
            t.insert("1.0", text)
        t.configure(state="disabled")

    def show_desc(self):
        """显示选中的技能说明（多选时显示第一个，并标出还选了几个）。"""
        meta = self.meta()
        sids = self.sel_ids()
        sid = sids[0] if sids else None
        if sid is None or sid not in meta:
            self.desc_full = ""
            self.set_desc("")
            return
        nm, desc = meta[sid]
        head = "技能 #%d %s" % (sid, nm)
        if len(sids) > 1:
            head += "（另外还选中 %d 个）" % (len(sids) - 1)
        text = "%s：%s" % (head, desc or "（没有说明）")
        self.desc_full = text           # 浮窗要用完整文本
        self.set_desc(text)

    # ------------------------------------------------------------ 列表
    def fill(self):
        """按搜索框重填技能一览（只列**已学**技能），并刷新说明。

        ⚠ `choices` 只装**筛选后**的 id —— 别拿它反查"这个角色会几招"。
        ⚠ 重建后按 iid 恢复选中：Treeview 一重建选中就全没，不恢复的话
          「搜索 → 再点忘掉」会莫名落空。
        """
        tree = self.tree
        keep = set(self.sel_ids())
        tree.delete(*tree.get_children())
        meta = self.meta()
        self.choices = []
        n = 0
        for sid, nm in self.source:
            d = meta.get(sid, ("", ""))[1]
            if not sk_match(sid, nm, d, self.var_search.get()):
                continue
            n += 1
            self.choices.append(sid)
            tree.insert("", "end", iid="sk%d" % sid, values=(n, sid, nm))
        for sid in keep:
            if tree.exists("sk%d" % sid):
                tree.selection_add("sk%d" % sid)
        kids = tree.get_children()
        if kids and not tree.selection():
            # 一行没选中（首次填充 / 换目标后旧选中不在了）→ 选中第一行。
            # ⚠ 别省这步：说明框只认「一览里选中的行」，不做兜底就是一片空白，
            #   看着像坏了。旧版是靠"下拉默认选中第一项"顺带兜住的（2026-10-04
            #   下拉删掉后暴露）。
            tree.selection_set(kids[0])
        self.show_desc()

    # ------------------------------------------------------------ 悬停浮窗
    def row_tip(self, event):
        """鼠标在技能一览行上移动 → 浮窗显示该技能完整说明。"""
        row = self.tree.identify_row(event.y)
        if not row:
            self.app._tip_hide()
            return
        tipkey = "%s:%s" % (self.key, row)
        if getattr(self.app, "_tip_key", None) == tipkey:
            return                      # 同一行，别反复重建（会闪）
        try:
            sid = int(row[2:])
        except (ValueError, IndexError):
            self.app._tip_hide()
            return
        meta = self.meta()
        if sid not in meta:
            self.app._tip_hide()
            return
        nm, desc = meta[sid]
        text = "技能 #%d %s\n%s" % (sid, nm, desc or "（没有说明）")
        self.app._tip_show(text,
                           self.tree.winfo_rootx() + event.x + 12,
                           self.tree.winfo_rooty() + event.y + 12,
                           key=tipkey)

    def desc_tip(self, event):
        """鼠标在说明框上移动 → 浮窗显示完整说明（框里被截断时看这个）。"""
        if not self.desc_full:
            self.app._tip_hide()
            return
        tipkey = "%s:desc" % self.key
        if getattr(self.app, "_tip_key", None) == tipkey:
            return
        self.app._tip_show(self.desc_full,
                           self.desc.winfo_rootx() + event.x + 12,
                           self.desc.winfo_rooty() + event.y + 12,
                           key=tipkey)


#: 技能管理器「归属」筛选的固定项（其余归属＝门派名 / 技能表里的分段名）
OWN_ALL, OWN_SECT, OWN_NA = "全部", "门派技能", "无归属"
#: 技能管理器「状态」筛选的固定项
ST_ALL, ST_HAVE, ST_NONE = "全部", "已学", "未学"

import re as _re

#: 技能表里的分段行（`===锻造技能===`、`==特效==` …）——游戏自己没有"归属"
#: 字段，这些分隔行就是作者给技能分的段。
_SEC_RE = _re.compile(r"^=+(.+?)=+$")

#: 破折号标题行（`---五庄观---`、`---特殊技能---`）—— 作者也用它分区。
_SECT_RE = _re.compile(r"^-{2,}(.+?)-{2,}$")


def _is_sect_title(name):
    """`---五庄观---` 这种破折号标题是不是**门派**。

    作者写的多半是简称（`---化生---`＝化生寺、`---女儿---`＝女儿村、
    `---地府---`＝阴曹地府），所以拿 `sect.SECTS` 的名字做前后缀匹配 ——
    判「认不认识」一律走 `SECTS`，别在这儿新开一张名单。
    """
    for _nm, _ids in sect.SECTS.values():
        if _nm == name or _nm.startswith(name) or _nm.endswith(name):
            return True
    return False


def skill_sections(meta):
    """`{技能 id: 所属分段名}` —— 按 `meta`（`{id: (名字, 说明)}`）的 id 顺序
    扫一遍，遇到 `===xxx===` 这种分段行就把后面的技能都算进这一段。

    ⚠ 分段行**自己也算这一段**（它就在段首）。
    ⚠ 门派标题（`---五庄观---`）**结束**当前分段、也不新开分段 —— 门派技能的
      归属交给 `sect.sect_of_skill`（`---化生---` 那种简称对不上 sect 表的全名
      「化生寺」，两边都算只会打架）。
      **2026-10-06 修的 bug**：原来只认 `=x=`，`==特技==`（id 166）的 `cur`
      一路吃到下一个 `=x=`（id 312「辅助技能」），把中间 13 个门派的技能
      （id 180~311）全吞进「特技」—— 技能管理器「归属」列于是把**门派技能
      显示成了「特技」**。
    ⚠ 其余破折号标题（`---特殊技能---`）**算分段**：它不在 `sect.SECTS` 里，
      是作者给「惊心一剑…独钓寒江」那 47 个召唤兽特殊技能分的区。
    """
    cur = None
    out = {}
    for sid in sorted(meta):
        nm = (meta[sid][0] or "").strip()
        m = _SEC_RE.match(nm)
        if m:
            cur = m.group(1).strip() or None
        else:
            m2 = _SECT_RE.match(nm)
            if m2:
                t2 = m2.group(1).strip()
                cur = None if _is_sect_title(t2) else (t2 or None)
        if cur:
            out[sid] = cur
    return out


class SkillManager(object):
    """技能管理器 —— 批量学 / 忘技能的独立窗口（角色页、召唤兽页共用）。

    为什么单开窗口（2026-10-04 川定）：主界面那块技能区只有 7 行高、筛选
    只有"搜索"一个维度，「全选 / 反选」这种批量操作根本铺不开；再往左栏挤
    还得跟 1080 窗宽下"门派技能"被裁那条老账打架。

    这里：18 行列表 + 搜索 / 归属 / 状态 三个筛选维度，按钮一律作用在**当前
    筛选出来的行**上 —— 所以「搜『高级』→ 全选 → 学会选中」就是刷一批。

    ⚠ 不复用 `SkillPicker` 实例（那个绑死了主界面的控件），但共用同一套搜索
      规则（模块级 `sk_match`）和说明表（`app._skills_meta()`）。
    ⚠ 目标（哪个角色 / 哪只召唤兽）**每次现取**（`self.target()`）：存档一
      保存，旧节点全失效（`doc.save()` 会重解析整档），窗口是常驻的，抓着
      旧引用迟早出问题。
    """

    def __init__(self, app, key, first=False):
        self.app = app
        self.key = key                  # "actor" / "baby"
        self.meta = app._skills_meta()
        self.desc_full = ""
        tk, ttk = app.tk, app.ttk

        win = tk.Toplevel(app.root)
        self.win = win
        win.title(self.title_text())
        win.transient(app.root)
        # ⚠ 宽度是按「列宽之和 + 说明框 + 滚动条」反推的，改列宽/说明框宽度
        #   要同步改这里，否则右侧留一条空白（2026-10-04 川：窗口太空）。
        win.geometry("760x600")
        f = ttk.Frame(win, padding=8)
        f.pack(fill="both", expand=True)

        # ---- 筛选行
        bar = ttk.Frame(f)
        bar.pack(fill="x")
        ttk.Label(bar, text="搜索").pack(side="left")
        self.var_kw = tk.StringVar()
        ent = ttk.Entry(bar, textvariable=self.var_kw, width=16)
        ent.pack(side="left", padx=4)
        ent.bind("<KeyRelease>", lambda e: self.refill())
        ttk.Label(bar, text="归属").pack(side="left", padx=(8, 0))
        self.var_own = tk.StringVar(value=OWN_ALL)
        self.groups = skill_sections(self.meta)     # {技能 id: 分段名}
        # 归属下拉 = 表里真实存在的分段名（特效 / 特技 / 锻造技能…）＋ 三个固定项。
        # 2026-10-04 川：「归属不是有很多吗？」—— 原来只列固定项，13 个分段名全丢了。
        vals = [OWN_ALL] + sorted(set(self.groups.values())) + [OWN_SECT, OWN_NA]
        self.cb_own = ttk.Combobox(bar, textvariable=self.var_own,
                                   state="readonly", width=10,
                                   values=tuple(vals), height=min(len(vals), 20))
        self.cb_own.pack(side="left", padx=4)
        self.cb_own.bind("<<ComboboxSelected>>", lambda e: self.refill())
        ttk.Label(bar, text="状态").pack(side="left", padx=(8, 0))
        self.var_st = tk.StringVar(value=ST_ALL)
        self.cb_st = ttk.Combobox(bar, textvariable=self.var_st,
                                  state="readonly", width=8,
                                  values=(ST_ALL, ST_HAVE, ST_NONE))
        self.cb_st.pack(side="left", padx=4)
        self.cb_st.bind("<<ComboboxSelected>>", lambda e: self.refill())
        self.var_count = tk.StringVar(value="")
        ttk.Label(bar, textvariable=self.var_count, foreground="#8a8a8a"
                  ).pack(side="left", padx=10)
        # 「已选 …」放筛选行右侧（放操作行会把那一排按钮挤到放不下）
        self.var_sel = tk.StringVar(value="")
        ttk.Label(bar, textvariable=self.var_sel, foreground="#8a8a8a"
                  ).pack(side="right", padx=6)

        # ---- 列表 + 说明
        # ⚠ 说明框先 pack：空间不够时挨刀的是列表（它自带滚动条，可缩）。
        body = ttk.Frame(f)
        body.pack(fill="both", expand=True, pady=(6, 0))
        self.desc = tk.Text(body, height=17, width=28, wrap="word",
                            font=("Microsoft YaHei UI", 9), relief="flat",
                            highlightthickness=1, highlightbackground="#ddd",
                            state="disabled")
        self.desc.pack(side="right", fill="y", padx=(6, 0))
        tv = ttk.Treeview(body, columns=("st", "id", "name", "own"),
                          show="headings", height=17, selectmode="extended")
        # ⚠ 列宽一律 stretch=False：Treeview 比列总和大时，tk 会把多余宽度
        #   摊给可拉伸的列，把「名字」撑出一大段空白（2026-10-04 川：太空）。
        # ⚠ 「已学」列＝勾选框那种表示（2026-10-04 川：要像人物学门派技能那样）。
        #   字形只能用微软雅黑自带的「■ / □」—— ⚠ 雅黑**没有** ☑(U+2611) /
        #   ☐(U+2610) / ✓(U+2713)，Tk 用的是 GDI、不做字体回退，写上去就是豆腐块。
        #   （实测过：msyh.ttc 里只有 ■□●○◆◇√×╳▪▫ 这几个可用。）
        for c, t2, w in (("st", "已学", 52), ("id", "技能 id", 62),
                         ("name", "名字", 300), ("own", "归属", 100)):
            tv.heading(c, text=t2)
            tv.column(c, width=w, stretch=False,
                      anchor="w" if c in ("name", "own") else "center")
        vs = ttk.Scrollbar(body, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=vs.set)
        vs.pack(side="right", fill="y")
        tv.pack(side="left", fill="both", expand=True)
        self.tv = tv

        # ---- 操作行
        ops = ttk.Frame(f)
        ops.pack(fill="x", pady=(6, 0))
        fit_btn(ops, text="全选",
                command=lambda: self.select("all")).pack(side="left")
        fit_btn(ops, text="反选",
                command=lambda: self.select("invert")).pack(side="left", padx=4)
        fit_btn(ops, text="全不选",
                command=lambda: self.select("none")).pack(side="left")
        ttk.Separator(ops, orient="vertical").pack(side="left", fill="y",
                                                   padx=8)
        b_lrn = fit_btn(ops, text="学会选中", command=self.do_learn)
        b_lrn.pack(side="left")
        self.app._bind_tip(b_lrn, "把选中的技能学会（已经会的自动跳过）。\n"
                                  "快捷键：在列表里按空格＝逐条反相切换\n"
                                  "（没学的学会、已学的忘掉）。\n"
                                  "也可以直接点最左边「已学」那一格：\n"
                                  "■＝已学、□＝没学，点一下当场翻面。")
        b_fgt = fit_btn(ops, text="忘掉选中", command=self.do_forget)
        b_fgt.pack(side="left", padx=4)
        self.app._bind_tip(b_fgt, "把选中的技能忘掉（本来就没学的自动跳过）。\n"
                                  "快捷键：在列表里按空格＝逐条反相切换\n"
                                  "（已学的忘掉、没学的学会）。\n"
                                  "也可以直接点最左边「已学」那一格：\n"
                                  "■＝已学、□＝没学，点一下当场翻面。")
        fit_btn(ops, text="清空已学",
                command=self.do_clear).pack(side="left")
        ttk.Separator(ops, orient="vertical").pack(side="left", fill="y",
                                                   padx=8)
        fit_btn(ops, text="复制给…",
                command=self.do_copy_to).pack(side="left")
        fit_btn(ops, text="刷新",
                command=self.refill).pack(side="left", padx=(8, 0))
        fit_btn(ops, text="关闭", command=self.close).pack(side="right")

        tv.bind("<<TreeviewSelect>>", lambda e: self.on_select())
        # 空格 = 把选中项逐条反相（没学的学会、已学的忘掉）——2026-10-04 川要求。
        # ⚠ 必须 return "break"（见 toggle_selected）：Treeview 的类绑定里 space
        #   没有默认动作，但留着 break 免得将来主题/平台给它加上"翻页/展开"之类。
        tv.bind("<space>", self.toggle_selected)
        # 点「已学」那一格 = 像勾选框一样**当场**切换（2026-10-04 川：
        # 「就像人物学门派技能那里一样」）——不用先选中再按按钮。
        tv.bind("<Button-1>", self.on_click)
        tv.bind("<Motion>", self.row_tip)
        tv.bind("<Leave>", lambda e: app._tip_hide())
        self.desc.bind("<Motion>", self.desc_tip)
        self.desc.bind("<Leave>", lambda e: app._tip_hide())

        self.refill()
        center_win(win, app.root)
        esc_close(win)
        if first:
            ent.focus_set()             # ⚠ 得写在 esc_close 之后才优先
        win.protocol("WM_DELETE_WINDOW", self.close)

    # ------------------------------------------------------------ 目标 / 数据
    def target(self):
        """当前操作对象（角色节点 / 召唤兽节点）—— 每次现取，绝不缓存。"""
        return self.app.current_actor() if self.key == "actor" \
            else self.app._baby()

    def have(self):
        """这个目标已学的技能 id 列表（存档真值）。"""
        t2 = self.target()
        if t2 is None:
            return []
        if self.key == "actor":
            return list(self.app.g.actor_skills(t2))
        return list(self.app.babies_ed().skills(t2))

    def who(self):
        t2 = self.target()
        if t2 is None:
            return "（没选中）"
        nm = self.app.sv.actor_name(t2) if self.key == "actor" \
            else self.app.babies_ed().display_name(t2)
        return "「%s」" % nm

    def title_text(self):
        return "技能管理器 — %s（已学 %d 个）" % (self.who(), len(self.have()))

    @staticmethod
    def sid_of(iid):
        try:
            return int(iid[2:])
        except (ValueError, IndexError):
            return None

    def sel_sids(self):
        out = []
        for iid in self.tv.selection():
            s = self.sid_of(iid)
            if s is not None:
                out.append(s)
        return out

    def own_text(self, sid):
        """归属列的文字：**分段优先**（技能表里的 `===xxx===` 分组），
        没分段才是门派名；都没有 →「无」。

        ⚠ 门派技能里 index 10 的「上古××」秘技**两头都占**（既在 `$sects[id][:skills]`
          里，也在技能表的「上古技能」分段里，2026-10-04 补齐门派表后才撞上）。
          两边都算的话，「按分段筛出来的行会标着门派名」——同一个筛选里混着两种
          归属，看着就乱。所以分段赢（它是技能表自己的组织方式，门派是另一维度）。
        """
        sec = getattr(self, "groups", {}).get(sid)
        if sec:
            return sec
        s = sect.sect_of_skill(sid)
        if s:
            return sect.sect_name(s)
        return "无"

    def own_ok(self, sid):
        """归属筛选：ALL 全放；SECT 只要门派技能；NA 要"既非门派、也没分段"；
        其余值＝具体分段名（`===特效===` 那一层，见 `skill_sections`）。

        ⚠ `SECT` 要把「有分段的那几个门派秘技」排掉（它们归分段那一档），
          不然「门派技能」里会混进标着「上古技能」的行 —— 和 `own_text` 同一个理。
        """
        mode = self.var_own.get()
        if mode == OWN_ALL:
            return True
        is_sect = sect.sect_of_skill(sid) is not None
        grouped = bool(self.groups.get(sid))
        if mode == OWN_SECT:
            return is_sect and not grouped
        if mode == OWN_NA:
            return not is_sect and not grouped
        return self.groups.get(sid) == mode

    # ------------------------------------------------------------ 列表
    def refill(self, keep_sel=True):
        """按三个筛选条件重填列表（重建后按 iid 恢复选中）。"""
        tv = self.tv
        keep = set(self.sel_sids()) if keep_sel else set()
        tv.delete(*tv.get_children())
        have = set(self.have())
        st = self.var_st.get()
        kw = self.var_kw.get()
        n = 0
        for sid in sorted(self.meta):
            nm, desc = self.meta[sid]
            if not nm:
                continue
            # 分隔行（`===锻造技能===` / `---五庄观---`）是作者给表分的段，不是能学的
            # 技能 —— 列出来会被「全选 → 学会选中」写进存档。它们只在算归属时有用
            # （`skill_sections`）。⚠ 破折号那批原来漏了：`---五庄观---` 会当成一条
            # 「技能」列出来（归属还写着「特技」），2026-10-06 一并补上。
            # 判据统一走 `datatables.section_of()`（两种形式都认），别在这儿另写正则。
            if datatables.section_of(nm):
                continue
            got = sid in have
            if st == ST_HAVE and not got:
                continue
            if st == ST_NONE and got:
                continue
            if not self.own_ok(sid):
                continue
            if not sk_match(sid, nm, desc, kw):
                continue
            tv.insert("", "end", iid="sk%d" % sid,
                      values=("\u25a0" if got else "\u25a1", sid, nm,
                              self.own_text(sid)))
            n += 1
        for sid in keep:
            if tv.exists("sk%d" % sid):
                tv.selection_add("sk%d" % sid)
        self.var_count.set("匹配 %d / %d" % (n, len(self.meta)))
        self.on_select()
        try:
            self.win.title(self.title_text())
        except Exception:
            pass

    def on_select(self):
        sids = self.sel_sids()
        if sids:
            have = set(self.have())
            n_have = len([s for s in sids if s in have])
            self.var_sel.set("已选 %d 项（已学 %d / 未学 %d）　"
                             "点「已学」格子 / 按空格＝切换"
                             % (len(sids), n_have, len(sids) - n_have))
        else:
            self.var_sel.set("")
        self.show_desc()

    def select(self, mode):
        """全选 / 反选 / 全不选 —— 只作用于**当前筛选出来的行**。"""
        kids = list(self.tv.get_children())
        if not kids:
            return
        if mode == "all":
            self.tv.selection_set(kids)
        elif mode == "none":
            self.tv.selection_remove(*kids)
        else:
            cur = set(self.tv.selection())
            self.tv.selection_set([i for i in kids if i not in cur])
        self.on_select()

    # ------------------------------------------------------------ 说明
    def set_desc(self, text):
        t2 = self.desc
        t2.configure(state="normal")
        t2.delete("1.0", "end")
        if text:
            t2.insert("1.0", text)
        t2.configure(state="disabled")

    def show_desc(self):
        sids = self.sel_sids()
        if not sids:
            self.desc_full = ""
            self.set_desc("")
            return
        sid = sids[0]
        nm, desc = self.meta.get(sid, ("?", ""))
        head = "技能 #%d %s" % (sid, nm)
        if len(sids) > 1:
            head += "（另外还选中 %d 个）" % (len(sids) - 1)
        text = "%s\n\n%s" % (head, desc or "（没有说明）")
        self.desc_full = text
        self.set_desc(text)

    def row_tip(self, event):
        row = self.tv.identify_row(event.y)
        if not row:
            self.app._tip_hide()
            return
        tipkey = "skm:%s" % row
        if getattr(self.app, "_tip_key", None) == tipkey:
            return
        sid = self.sid_of(row)
        if sid is None or sid not in self.meta:
            self.app._tip_hide()
            return
        nm, desc = self.meta[sid]
        self.app._tip_show("技能 #%d %s\n%s" % (sid, nm,
                                              desc or "（没有说明）"),
                           self.tv.winfo_rootx() + event.x + 12,
                           self.tv.winfo_rooty() + event.y + 12, key=tipkey)

    def desc_tip(self, event):
        if not self.desc_full:
            self.app._tip_hide()
            return
        tipkey = "skm:desc"
        if getattr(self.app, "_tip_key", None) == tipkey:
            return
        self.app._tip_show(self.desc_full,
                           self.desc.winfo_rootx() + event.x + 12,
                           self.desc.winfo_rooty() + event.y + 12, key=tipkey)

    # ------------------------------------------------------------ 批量操作
    def _need_sel(self):
        sids = self.sel_sids()
        if not sids:
            messagebox.showinfo("提示",
                                "先在列表里选技能（Ctrl 点选、Shift 连选；\n"
                                "或用「全选」「反选」）。", parent=self.win)
            return None
        return sids

    def warn_limit(self, msg):
        """召唤兽技能数超游戏上限时补一句警告（角色 `@skills` 没有上限）。"""
        if self.key != "baby":
            return msg
        n = len(self.have())
        if n > babies.GAME_LEARN_LIMIT:
            msg += ("；⚠ 现在 %d 个，超过游戏「升级学技能」的 %d 上限"
                    "（读取端没限制，实战能不能用要实机验证）"
                    % (n, babies.GAME_LEARN_LIMIT))
        return msg

    def do_learn(self):
        sids = self._need_sel()
        t2 = self.target()
        if sids is None or t2 is None:
            return
        try:
            if self.key == "actor":
                added, already = self.app.g.actor_learn_many(t2, sids)
            else:
                added, already = self.app.babies_ed().learn_many(t2, sids)
        except Exception as e:
            messagebox.showerror("改不了", zh_error(e), parent=self.win)
            return
        if not added:
            self.app.set_status("选中的 %d 个技能本来就都会了" % len(sids))
            return
        self.app.mark_dirty()
        msg = "已学会 %d 个技能" % len(added)
        if already:
            msg += "（%d 个本来就会，跳过）" % len(already)
        self.after_change(self.warn_limit(msg))

    def do_forget(self):
        sids = self._need_sel()
        t2 = self.target()
        if sids is None or t2 is None:
            return
        try:
            if self.key == "actor":
                drop, missing = self.app.g.actor_forget_many(t2, sids)
            else:
                drop, missing = self.app.babies_ed().forget_many(t2, sids)
        except Exception as e:
            messagebox.showerror("改不了", zh_error(e), parent=self.win)
            return
        if not drop:
            self.app.set_status("选中的 %d 个技能本来就没学" % len(sids))
            return
        self.app.mark_dirty()
        msg = "已忘掉 %d 个技能" % len(drop)
        if missing:
            msg += "（%d 个本来就没学，跳过）" % len(missing)
        self.after_change(msg)

    def toggle_selected(self, _e=None):
        """空格＝把选中项**逐条反相**：没学的学会、已学的忘掉。

        2026-10-04 川要求。"逐条反相"而不是"全学 / 全忘"，所以在混合选中的
        一份列表上按一下，恰好把所有行翻个面（这也是它能当开关用的原因）。

        写档：分两批各写**一次**数组（`learn_many` / `forget_many` 都是
        "一次写一份 `@skills`"），不会有"边改边遍历"的索引问题，也不会
        一次切一批就重解析 N 遍整档。
        """
        sids = self.sel_sids()
        t2 = self.target()
        if not sids or t2 is None:
            return "break"
        have = set(self.have())
        learn = [s for s in sids if s not in have]
        forget = [s for s in sids if s in have]
        try:
            if self.key == "actor":
                ga = self.app.g
                la, _a = ga.actor_learn_many(t2, learn) if learn else ([], [])
                fd, _f = ga.actor_forget_many(t2, forget) if forget else ([], [])
            else:
                bd = self.app.babies_ed()
                la, _a = bd.learn_many(t2, learn) if learn else ([], [])
                fd, _f = bd.forget_many(t2, forget) if forget else ([], [])
        except Exception as e:
            messagebox.showerror("改不了", zh_error(e), parent=self.win)
            return "break"
        if not la and not fd:
            self.app.set_status("选中的 %d 个技能没有变化" % len(sids))
            return "break"
        self.app.mark_dirty()
        msg = "空格切换：学会 %d 个、忘掉 %d 个" % (len(la), len(fd))
        self.after_change(self.warn_limit(msg))
        return "break"

    def on_click(self, event):
        """点最左边「已学」那一格 → 像勾选框一样当场切换那一行。

        2026-10-04 川：「学会没学会的用多选框表示，就像人物学门派技能那里
        一样」—— 人物那页是真的 ttk.Checkbutton，Treeview 里塞不进控件，
        所以用字形当勾选框 + 点格子直接翻面（语义等价）。

        ⚠ 只有第 1 列（`#1`，就是 `st`）吞掉点击（`return "break"`，免得
          Treeview 顺手把选中改掉）；点别的列照旧走正常的选中逻辑。
        """
        if self.tv.identify_column(event.x) != "#1":
            return None
        row = self.tv.identify_row(event.y)
        sid = self.sid_of(row) if row else None
        if sid is None:
            return None
        self.toggle_one(sid)
        return "break"

    def toggle_one(self, sid):
        """把**某一个**技能在「已学 / 未学」之间翻面（一次写一份 `@skills`）。"""
        t2 = self.target()
        if t2 is None:
            return
        got = sid in set(self.have())
        nm = (self.meta.get(sid) or ("", ""))[0] or "#%d" % sid
        try:
            if got:
                if self.key == "actor":
                    done, _skip = self.app.g.actor_forget_many(t2, [sid])
                else:
                    done, _skip = self.app.babies_ed().forget_many(t2, [sid])
                what = "忘掉"
            else:
                if self.key == "actor":
                    done, _skip = self.app.g.actor_learn_many(t2, [sid])
                else:
                    done, _skip = self.app.babies_ed().learn_many(t2, [sid])
                what = "学会"
        except Exception as e:
            messagebox.showerror("改不了", zh_error(e), parent=self.win)
            return
        if not done:
            return
        self.app.mark_dirty()
        self.after_change(self.warn_limit(
            "%s技能 #%d %s" % (what, sid, nm)))

    def do_clear(self):
        t2 = self.target()
        if t2 is None:
            return
        n = len(self.have())
        if not n:
            self.app.set_status("%s现在没学会技能" % self.who())
            return
        if not self.app.confirm("清空技能",
                                "把%s的技能全忘掉（%d 个）？"
                                % (self.who(), n)):
            return
        try:
            if self.key == "actor":
                self.app.g.actor_clear_skills(t2)
            else:
                self.app.babies_ed().clear_skills(t2)
        except Exception as e:
            messagebox.showerror("改不了", zh_error(e), parent=self.win)
            return
        self.app.mark_dirty()
        self.after_change("已清空%s的技能" % self.who())

    def _copy_targets(self, src):
        """「复制给…」的可选目标 —— 同类型的**其他**目标（排除自己）。

        召唤兽 → 存档里别的召唤兽（别的角色身上的也行）；角色 → 别的角色。
        """
        if self.key == "baby":
            return [r for r in self.app.babies_ed().all_babies()
                    if r["baby"] is not src]
        return [(aid, x) for aid, x in self.app.sv.actors() if x is not src]

    def do_copy_to(self):
        """把**选中的技能**复制给另一个同类型目标（追加去重，不动目标原有技能）。

        和「从…克隆」（整套抄、可选覆盖）方向相反：这里只搬选中的那几个，
        目标已有的自动跳过 —— 语义等同 `learn_many`。
        """
        sids = self._need_sel()
        src = self.target()
        if sids is None or src is None:
            return
        rows = self._copy_targets(src)
        if not rows:
            messagebox.showinfo("提示", "存档里没有别%s可以当目标。"
                                % ("的召唤兽" if self.key == "baby" else "的角色"),
                                parent=self.win)
            return
        meta = self.meta
        tk, ttk = self.app.tk, self.app.ttk

        def skill_text(ids):
            out = []
            for s in ids:
                out.append(meta.get(s, ("", ""))[0] or "#%d" % s)
            return "、".join(out) or "（没有技能）"

        # 目标清单（统一成 dict，两种 key 共用一套渲染）
        items = []
        if self.key == "baby":
            for r in rows:
                items.append({
                    "iid": "c%d_%d" % (r["actor_id"], r["index"]),
                    "who": "%s(#%d)" % (r["actor_name"], r["actor_id"]),
                    "no": r["index"] + 1,
                    "name": "%s / %s" % (r["name"], r["tpl"]),
                    "tname": r["name"],
                    "skills": r["skills"], "obj": r["baby"]})
        else:
            for aid, x in rows:
                nm = self.app.sv.actor_name(x)
                items.append({
                    "iid": "a%d" % aid, "who": nm, "no": aid,
                    "name": "(角色)", "tname": nm,
                    "skills": self.app.g.actor_skills(x), "obj": x})

        win = tk.Toplevel(self.win)
        win.title("复制 %d 个技能 → 选目标" % len(sids))
        win.transient(self.win)
        win.grab_set()
        f = ttk.Frame(win, padding=8)
        f.pack(fill="both", expand=True)
        ttk.Label(f, text="要复制的 %d 个技能：%s"
                  % (len(sids), skill_text(sids)), foreground="#8a8a8a",
                  wraplength=600, justify="left").pack(fill="x", pady=(0, 6))

        bar = ttk.Frame(f)
        bar.pack(fill="x")
        ttk.Label(bar, text="搜索（名字 / 序号 / 技能）：").pack(side="left")
        var_kw = tk.StringVar()
        ent = ttk.Entry(bar, textvariable=var_kw, width=16)
        ent.pack(side="left", padx=4)
        ent.bind("<KeyRelease>", lambda e: refill())

        cols = ("who", "no", "name", "n", "skills")
        heads = ("角色", "序", "名字", "已有", "技能")
        widths = (130, 34, 190, 46, 330)
        tv = ttk.Treeview(f, columns=cols, show="headings", height=12,
                          selectmode="browse")
        for c, h, w in zip(cols, heads, widths):
            tv.heading(c, text=h)
            tv.column(c, width=w, anchor="w")
        vs = ttk.Scrollbar(f, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=vs.set)
        vs.pack(side="right", fill="y")
        tv.pack(fill="both", expand=True, pady=6)

        items_map = {}

        def refill(_e=None):
            tv.delete(*tv.get_children())
            items_map.clear()
            kw = var_kw.get().strip()
            for it in items:
                hay = "%s %s %s %s" % (it["who"], it["no"], it["name"],
                                       skill_text(it["skills"]))
                if kw and kw not in hay:
                    continue
                items_map[it["iid"]] = it
                tv.insert("", "end", iid=it["iid"],
                          values=(it["who"], it["no"], it["name"],
                                  len(it["skills"]), skill_text(it["skills"])))
            kids = tv.get_children()
            if kids:
                tv.selection_set(kids[0])

        refill()

        def do_copy(_e=None):
            sel = tv.selection()
            it = items_map.get(sel[0]) if sel else None
            if it is None:
                return
            tgt, tname = it["obj"], it["tname"]
            if not self.app.confirm(
                    "复制技能",
                    "把选中的 %d 个技能加给「%s」？\n"
                    "（目标原有的技能不动，已经会的自动跳过）"
                    % (len(sids), tname)):
                return
            try:
                if self.key == "actor":
                    added, already = self.app.g.actor_learn_many(tgt, sids)
                else:
                    added, already = self.app.babies_ed().learn_many(tgt, sids)
            except Exception as e:
                messagebox.showerror("复制失败", zh_error(e), parent=win)
                return
            win.destroy()
            self.app.mark_dirty()
            if added:
                msg = "已把 %d 个技能复制给「%s」" % (len(added), tname)
                if already:
                    msg += "（%d 个目标本来就会，跳过）" % len(already)
            else:
                msg = "「%s」这些技能本来就都会（%d 个）" % (tname, len(already))
            if self.key == "baby":
                n = len(self.app.babies_ed().skills(tgt))
                if n > babies.GAME_LEARN_LIMIT:
                    msg += ("；⚠ 目标现在 %d 个，超过游戏「升级学技能」的 %d 上限"
                            "（读取端没限制，实战能不能用要实机验证）"
                            % (n, babies.GAME_LEARN_LIMIT))
            self.app.set_status(msg + "（记得点「保存修改」）")
            self.sync_main()
            self.refill()

        tv.bind("<Double-1>", do_copy)
        bf = ttk.Frame(f)
        bf.pack(fill="x")
        fit_btn(bf, text="复制给选中的目标",
                command=do_copy).pack(side="right", padx=4)
        fit_btn(bf, text="取消", command=win.destroy).pack(side="right")
        esc_close(win)
        ent.focus_set()                 # 焦点给搜索框（在 esc_close 之后才优先）
        center_win(win, self.win)

    def after_change(self, msg):
        """改完存档之后统一收尾：状态栏 + 刷主界面 + 重填自己。"""
        self.app.set_status(msg + "（记得点「保存修改」）")
        self.sync_main()
        self.refill()

    def sync_main(self):
        """把主界面那块技能区 / 召唤兽列表刷成新状态。"""
        if self.key == "actor":
            self.app.load_actor()
        else:
            self.app.load_baby()
            b = self.target()
            if b is not None:
                self.app.refresh_baby_list_keep(b)

    def close(self):
        try:
            self.app._skill_win = None
        except Exception:
            pass
        try:
            self.win.destroy()
        except Exception:
            pass


class PayloadManager(object):
    """重抽管理 —— 给背包里选中的格子重新指定「运行时内容」的独立窗口。

    为什么单开窗口（2026-10-07 川定）：原来只有一个「重抽内容」按钮 + 一个
    裸 id 输入框，要选内容得自己去 `Data\\Actors` 里查 id；而这类内容有十几个
    家族（蛋→召唤兽池、要诀→技能池、元宵→涨哪项资质、指南书→类别/等级…），
    每个家族能挑的字段都不一样。这里仿 `SkillManager`：**按选中的物品自动
    适配**，列出能挑的候选，选一个应用到**所有选中的格子**。

    ⚠ 和 `SkillManager` 一样：目标每次现取（`doc.save()` 会重解析整档，
      旧节点全失效），所以只记**槽号**、不缓存节点。
    """

    def __init__(self, app, first=False):
        self.app = app
        tk, ttk = app.tk, app.ttk
        self.groups = {}         # 家族 typ -> {slots, fields, pools, items}
        self.order = []          # 家族出现顺序
        self.fam = None
        self.picked = {}         # {家族: {字段键: 值}}
        self.cands = []          # 当前候选 [(值, 名称, 分类, 说明)]
        self.desc_full = ""
        self._babies = None
        self._skmeta = None
        #: 用户**自己填过**的数值字段 `{(家族, 字段键)}` —— 换资质时不覆盖它
        self._num_edited = set()
        #: 正在程序化回填「值」输入框（挡掉 trace 回调，别把它当用户输入）
        self._loading_int = False

        win = tk.Toplevel(app.root)
        self.win = win
        win.title("重抽管理")
        win.transient(app.root)
        win.geometry("820x600")
        f = ttk.Frame(win, padding=8)
        f.pack(fill="both", expand=True)

        # ---- 目标行（选中了哪些格子、各自现在是什么内容）
        self.var_target = tk.StringVar(value="")
        ttk.Label(f, textvariable=self.var_target, justify="left",
                  wraplength=780).pack(anchor="w")

        # ---- 筛选行：家族 / 字段 / 搜索
        bar = ttk.Frame(f)
        bar.pack(fill="x", pady=(6, 0))
        ttk.Label(bar, text="家族").pack(side="left")
        self.var_fam = tk.StringVar()
        self.cb_fam = ttk.Combobox(bar, textvariable=self.var_fam,
                                   state="readonly", width=24)
        self.cb_fam.pack(side="left", padx=4)
        self.cb_fam.bind("<<ComboboxSelected>>", lambda e: self.pick_family())
        ttk.Label(bar, text="字段").pack(side="left", padx=(8, 0))
        self.var_field = tk.StringVar()
        self.cb_field = ttk.Combobox(bar, textvariable=self.var_field,
                                     state="readonly", width=14)
        self.cb_field.pack(side="left", padx=4)
        self.cb_field.bind("<<ComboboxSelected>>", lambda e: self.show_field())
        ttk.Label(bar, text="搜索").pack(side="left", padx=(8, 0))
        self.var_kw = tk.StringVar()
        ent = ttk.Entry(bar, textvariable=self.var_kw, width=14)
        ent.pack(side="left", padx=4)
        ent.bind("<KeyRelease>", lambda e: self.fill_cands())
        fit_btn(bar, text="清空", command=self.kw_clear).pack(side="left")
        self.var_info = tk.StringVar(value="")
        ttk.Label(bar, textvariable=self.var_info,
                  foreground="#8a8a8a").pack(side="right", padx=6)

        # ---- 列表 + 说明
        # ⚠ 说明框先 pack：空间不够时挨刀的是列表（它自带滚动条，可缩）。
        body = ttk.Panedwindow(f, orient="horizontal")
        body.pack(fill="both", expand=True, pady=(6, 0))
        self.desc = tk.Text(body, height=18, width=26, wrap="word",
                            font=("Microsoft YaHei UI", 9), relief="flat",
                            highlightthickness=1, highlightbackground="#ddd",
                            state="disabled")
        self.desc.pack(side="right", fill="y", padx=(6, 0))

        left = ttk.Frame(body)
        self.box_list = ttk.Frame(left)
        self.tv = ttk.Treeview(self.box_list,
                               columns=("id", "name", "cls", "note"),
                               show="headings", height=18, selectmode="browse")
        # ⚠ 2026-10-07 川：编号、分类各占一列 —— 原来挤在悬停浮窗里太碍眼。
        for c, t2, w in (("id", "编号", 54), ("name", "名称", 148),
                         ("cls", "分类", 100), ("note", "说明", 248)):
            self.tv.heading(c, text=t2)
            # ⚠ 只让「说明」列 stretch（多余宽度摊给名字会在右边留一段空白）
            self.tv.column(c, width=w, stretch=(c == "note"),
                           anchor="w" if c != "id" else "center")
        vs = ttk.Scrollbar(self.box_list, orient="vertical",
                           command=self.tv.yview)
        self.tv.configure(yscrollcommand=vs.set)
        vs.pack(side="right", fill="y")
        self.tv.pack(side="left", fill="both", expand=True)
        self.box_int = ttk.Frame(left)
        ttk.Label(self.box_int, text="值：").pack(side="left")
        self.var_int = tk.StringVar(value="")
        self.ent_int = ttk.Entry(self.box_int, textvariable=self.var_int,
                                 width=12)
        self.ent_int.pack(side="left", padx=6)
        self.var_int_note = tk.StringVar(value="")
        ttk.Label(self.box_int, textvariable=self.var_int_note,
                  foreground="#8a8a8a").pack(side="left")
        self.var_int.trace_add("write", lambda *a: self._int_changed())
        body.add(left, weight=3)

        # ---- 操作行
        ops = ttk.Frame(f)
        ops.pack(fill="x", pady=(6, 0))
        self.b_apply = fit_btn(ops, text="应用选中的内容", command=self.apply)
        self.b_apply.pack(side="left")
        self.app._bind_tip(self.b_apply,
                           "把左边选中（或整数字段填好）的内容写到\n"
                           "**当前家族**里所有选中的格子（覆盖原来的内容）。\n"
                           "没挑的字段按游戏规则随机。")
        self.b_rand = fit_btn(ops, text="随机重抽这些格子", command=self.random_all)
        self.b_rand.pack(side="left", padx=4)
        self.app._bind_tip(self.b_rand,
                           "对**全部选中的格子**按游戏规则重抽一份内容\n"
                           "（不看你挑了什么）。")
        fit_btn(ops, text="刷新", command=self.refill).pack(side="left", padx=(8, 0))
        fit_btn(ops, text="关闭", command=self.close).pack(side="right")

        self.tv.bind("<<TreeviewSelect>>", lambda e: self.on_cand())
        self.tv.bind("<Motion>", self.row_tip)
        self.tv.bind("<Leave>", lambda e: app._tip_hide())
        self.desc.bind("<Motion>", self.desc_tip)
        self.desc.bind("<Leave>", lambda e: app._tip_hide())

        self.refill()
        center_win(win, app.root)
        esc_close(win)
        if first:
            ent.focus_set()             # ⚠ 得写在 esc_close 之后才优先
        win.protocol("WM_DELETE_WINDOW", self.close)

    # ------------------------------------------------------------ 名字/候选表
    def _baby_rows(self):
        """全部召唤兽 `[(id, 名字)]`（玩家角色/坐骑/空占位都排掉）。"""
        if self._babies is None:
            out = []
            try:
                nm = datatables.name_map("Actors")
                bd = self.app.babies_ed()
                for i in sorted(nm):
                    if bd is not None and not bd.is_baby_entry(i):
                        continue
                    out.append((i, nm[i]))
            except Exception:
                out = []
            self._babies = out
        return self._babies

    def _skill_rows(self):
        """全部技能 `[(id, 名字, 描述)]`（分段标题行排掉）。"""
        if self._skmeta is None:
            out = []
            try:
                for i, (nm, desc) in self.app._skills_meta().items():
                    if not nm or datatables.section_of(nm):
                        continue
                    out.append((i, nm, desc))
            except Exception:
                out = []
            self._skmeta = out
        return self._skmeta

    def _own_of(self, sid):
        """技能的「归属」列文字（分段名 > 门派名）—— 同技能管理器口径。"""
        if getattr(self, "_sec_map", None) is None:
            try:
                self._sec_map = skill_sections(self.app._skills_meta())
            except Exception:
                self._sec_map = {}
        sec = self._sec_map.get(sid)
        if sec:
            return sec
        s = sect.sect_of_skill(sid)
        return sect.sect_name(s) if s else ""

    # ------------------------------------------------------------ 目标 / 家族
    def refill(self):
        """按当前选中的格子重建「家族」分组（存档一保存旧节点就失效）。"""
        self.groups = {}
        self.order = []
        g = self.app.g
        kind = self.app._bag_kind()
        slots = self.app._bag_slots(quiet=True)
        if g is None or not slots:
            self.var_target.set(
                "先在背包页选中格子（Ctrl 点选 / Shift 连选），再点「重抽管理」。")
            self._render_none()
            return
        skipped = []
        for slot in slots:
            it = g._item_node(kind, slot)
            if it is None:
                skipped.append(slot)
                continue
            info = g.slot_info(kind, slot)
            iid = info[0] if info else -1
            nm = g.item_display_name(it, "?")
            typ, fields = itemattr.payload_spec(nm, iid)
            if typ is None:
                skipped.append(slot)          # 包子/装备这类没有运行时内容
                continue
            grp = self.groups.get(typ)
            if grp is None:
                grp = {"slots": [], "fields": fields, "pools": {}, "items": []}
                self.groups[typ] = grp
                self.order.append(typ)
            grp["slots"].append(slot)
            grp["items"].append((slot, nm, iid, g.payload_summary(it)))
            for fld in fields:
                if fld.get("pool"):
                    grp["pools"].setdefault(fld["key"], set()).update(
                        fld["pool"])
        # 目标行
        lines = []
        if self.order:
            seg = []
            for typ in self.order:
                grp = self.groups[typ]
                names = []
                for _s, nm, _i, _c in grp["items"]:
                    if nm not in names:
                        names.append(nm)
                seg.append("%s ×%d（%s）" % (typ, len(grp["slots"]),
                                             "、".join(names[:4])))
            lines.append("已选 %d 格：%s" % (len(slots), "；".join(seg)))
            cur = []
            for _s, nm, _i, c in [x for typ in self.order
                                  for x in self.groups[typ]["items"]][:5]:
                cur.append("%s→%s" % (nm, c or "（空）"))
            lines.append("当前：" + "；".join(cur))
        if skipped:
            lines.append("（另有 %d 格没有「运行时内容」或为空，已跳过）"
                         % len(skipped))
        self.var_target.set("\n".join(lines))
        if not self.order:
            self._render_none()
            return
        self.cb_fam.configure(values=tuple(
            "%s ×%d" % (t, len(self.groups[t]["slots"])) for t in self.order))
        if self.fam not in self.groups:
            self.fam = self.order[0]
            self.picked.pop(self.fam, None)
            self._forget_edits(self.fam)
        self.var_fam.set("%s ×%d" % (self.fam, len(self.groups[self.fam]["slots"])))
        self._sync_fields()

    def _render_none(self):
        self.cb_fam.configure(values=())
        self.var_fam.set("")
        self.cb_field.configure(values=())
        self.var_field.set("")
        self.var_info.set("")
        self.box_int.pack_forget()
        self.box_list.pack(fill="both", expand=True)
        self.tv.delete(*self.tv.get_children())
        self.cands = []
        self.set_desc("")
        self.b_apply.state(["disabled"])
        self.b_rand.state(["disabled"])

    def _fam(self):
        return self.groups.get(self.fam)

    def _sync_fields(self):
        """家族定下来后，把「字段」下拉填成这个家族能挑的字段。"""
        grp = self._fam()
        fields = grp["fields"] if grp else []
        self.cb_field.configure(state="readonly",
                                values=tuple(fd["label"] for fd in fields))
        if not fields:
            self.var_field.set("")
            self.box_int.pack_forget()
            self.box_list.pack(fill="both", expand=True)
            self.tv.delete(*self.tv.get_children())
            self.cands = []
            self.var_info.set("")
            self.b_apply.state(["!disabled"])
            self.b_rand.state(["!disabled"])
            self.set_desc("「%s」的内容是游戏写死的，挑不了具体值 ——\n"
                          "直接点「应用选中的内容」（或「随机重抽」）按游戏规则\n"
                          "生成一份即可。\n\n字段：%s"
                          % (self.fam, "、".join(sorted(
                              self._fields_of_first())) or "（无）"))
            return
        self.b_apply.state(["!disabled"])
        self.b_rand.state(["!disabled"])
        self._seed_fields(fields)
        self.var_field.set(fields[0]["label"])
        self.show_field()

    def _seed_fields(self, fields):
        """给这个家族的所有字段填初值。

        两条口径：

        1. **读得出当前值的按原样回填**（老行为 —— `payload_fields` 的「用户不
           改就原样写回」）；
        2. **读不出的数值字段填区间上限**（2026-10-07 川：「抽选有范围的，默认抽
           最大范围」，元宵的成长就是 0.02）。清空输入框＝这一项按游戏规则随机。

        ⚠ 必须**先**过一遍所有字段、再给数值字段兜底：元宵的「数值」区间是跟着
          「涨哪项资质」走的（`rng_by_type`），得等 `type` 先落进 `picked`。
        """
        cur = self.picked.setdefault(self.fam, {})
        for fd in fields:
            if fd["key"] in cur:
                continue
            got = self._current_value(fd["key"])
            if got is not None:
                cur[fd["key"]] = got
        for fd in fields:
            if fd["kind"] not in ("int", "num") or cur.get(fd["key"]) is not None:
                continue
            rng = self._rng_of(fd)
            if rng:
                cur[fd["key"]] = rng[1]

    def _fields_of_first(self):
        """当前家族第一格**现在**的内容字段名（只给说明文字用）。"""
        grp = self._fam()
        if not grp:
            return []
        slot = grp["slots"][0]
        it = self.app.g._item_node(self.app._bag_kind(), slot)
        if it is None:
            return []
        try:
            return list(self.app.g.payload_fields(it).keys())
        except Exception:
            return []

    def pick_family(self):
        """用户换了家族下拉（取下拉里显示的名字反查）。"""
        txt = self.var_fam.get()
        for typ in self.order:
            if txt.startswith(typ + " "):
                self.fam = typ
                break
        self.picked.pop(self.fam, None)
        self._forget_edits(self.fam)
        self._sync_fields()

    def _forget_edits(self, fam):
        """换了家族/格子 → 忘掉「用户自己填过」的标记，让默认值（上限）重新生效。"""
        self._num_edited = set(k for k in self._num_edited if k[0] != fam)

    def pick_field(self):
        """当前字段（字段下拉的显示名 → 字段 dict）。"""
        grp = self._fam()
        if not grp:
            return None
        lbl = self.var_field.get()
        for fd in grp["fields"]:
            if fd["label"] == lbl:
                return fd
        return grp["fields"][0] if grp["fields"] else None

    # ------------------------------------------------------------ 候选列表
    def show_field(self):
        """按当前字段的类型渲染左栏：列表（actor/skill/choice）或数值框。"""
        grp = self._fam()
        fd = self.pick_field()
        if grp is None or fd is None:
            return
        cur = (self.picked.setdefault(self.fam, {}) or {})
        if fd["key"] not in cur:
            got = self._current_value(fd["key"])
            if got is not None:
                cur[fd["key"]] = got
        if fd["kind"] in ("int", "num"):
            self._show_num(fd, cur)
            return
        self.box_int.pack_forget()
        self.box_list.pack(fill="both", expand=True)
        self.fill_cands()

    def _show_num(self, fd, cur):
        """数值字段：一个输入框 + 取值范围提示。

        `num` 是浮点档（元宵的成长 0.01~0.02），`int` 是整数档。
        """
        is_num = fd["kind"] == "num"
        self.box_list.pack_forget()
        self.box_int.pack(fill="x")
        self.cands = []
        rng = self._rng_of(fd)
        fmt = (lambda v: "%g" % float(v)) if is_num else (lambda v: str(int(v)))
        if not rng:
            self.var_int_note.set("")
            desc = "「%s」的「%s」直接填个数就行。" % (self.fam, fd["label"])
        else:
            if cur.get(fd["key"]) is None:
                cur[fd["key"]] = rng[1]              # 默认抽上限
            self.var_int_note.set("范围 %s ~ %s（默认上限；清空＝随机）"
                                  % (fmt(rng[0]), fmt(rng[1])))
            desc = ("「%s」的「%s」直接填个数就行。\n"
                    "取值范围：%s ~ %s —— 默认填**上限**。\n"
                    "（清空输入框＝这一项交回游戏规则随机）"
                    % (self.fam, fd["label"], fmt(rng[0]), fmt(rng[1])))
        self._loading_int = True                  # 回填不算“用户改过”
        try:
            v = cur.get(fd["key"])
            self.var_int.set("" if v is None else fmt(v))
        finally:
            self._loading_int = False
        self.set_desc(desc)

    def _rng_of(self, fd):
        """字段的取值范围；带 `rng_by_type` 的按**当前挑的那个字段**现算。

        元宵的「数值」就是这么走的：涨攻击资质是 4~8，涨成长是 0.01~0.02。
        取不到依赖值时退回第一个区间（宁可给个能用的默认，不弹错）。
        """
        table = fd.get("rng_by_type")
        if table:
            dep = fd.get("depends_on")
            k = (self.picked.get(self.fam) or {}).get(dep)
            if k is None and dep:
                k = self._current_value(dep)
            try:
                return table[int(k)]
            except (TypeError, ValueError, IndexError):
                return table[0]
        return fd.get("rng")

    def _refresh_dep_defaults(self, changed):
        """某个字段换了取值 → 依赖它的数值字段按新范围重算默认值。

        元宵：把「涨哪项资质」从成长改成攻击 → 「数值」的默认从 0.02 变 8。
        ⚠ 用户自己填过的（`_num_edited`）不覆盖。
        """
        grp = self._fam()
        if not grp:
            return
        cur = self.picked.setdefault(self.fam, {})
        for fd in grp["fields"]:
            if fd.get("depends_on") != changed:
                continue
            if fd["key"] in cur and (self.fam, fd["key"]) in self._num_edited:
                continue
            rng = self._rng_of(fd)
            if rng:
                cur[fd["key"]] = rng[1]

    def _current_value(self, key):
        """选中格子现在这一项的字段值（取第一个格子的）。"""
        grp = self._fam()
        if not grp:
            return None
        it = self.app.g._item_node(self.app._bag_kind(), grp["slots"][0])
        if it is None:
            return None
        try:
            return self.app.g.payload_fields(it).get(key)
        except Exception:
            return None

    def fill_cands(self):
        fd = self.pick_field()
        if fd is None or fd["kind"] == "int":
            return
        kw = (self.var_kw.get() or "").strip().lower()
        grp = self._fam()
        pool = grp["pools"].get(fd["key"]) if grp else None
        rows = []
        if fd["kind"] == "choice":
            for val, label in fd["choices"]:
                nm = str(label)
                if kw and kw not in nm.lower() and kw not in str(val).lower():
                    continue
                rows.append((val, nm, "", ""))
        elif fd["kind"] == "actor":
            want = set(pool) if pool else None
            for i, nm in self._baby_rows():
                if want is not None and i not in want:
                    continue
                if kw and kw not in str(i) and kw not in nm.lower():
                    continue
                # 分类＝档位；说明＝Actors 表里的描述
                rows.append((i, nm, self._baby_note(i),
                             self._short(self._data_desc("Actors", i), 40)))
        elif fd["kind"] == "skill":
            want = set(pool) if pool else None
            for i, nm, desc in self._skill_rows():
                if want is not None and i not in want:
                    continue
                if kw and kw not in str(i) and kw not in nm.lower():
                    continue
                # 分类＝归属（分段名 > 门派）；说明＝技能描述摘要
                rows.append((i, nm, self._own_of(i), self._short(desc)))
        self.cands = rows
        self.tv.delete(*self.tv.get_children())
        for n, (val, nm, cls, note) in enumerate(rows):
            self.tv.insert("", "end", iid="c%d" % n,
                           values=(val, nm, cls, note))
        picked = (self.picked.get(self.fam) or {}).get(fd["key"])
        hit = None
        for n, (val, _nm, _cls, _note) in enumerate(rows):
            if val == picked:
                hit = "c%d" % n
                break
        if hit is None and rows:
            hit = "c0"
        if hit is not None:
            self.tv.selection_set(hit)
            self.tv.see(hit)
        self.var_info.set("候选 %d 项%s" % (
            len(rows), "（限本物品的池子）" if pool else ""))
        self.on_cand()

    def _baby_note(self, i):
        try:
            bd = self.app.babies_ed()
            return bd.type_of(i) or "" if bd else ""
        except Exception:
            return ""

    @staticmethod
    def _short(text, n=56):
        """详情 → 一行摘要（列表「说明」列用）：换行/连续空白压成单个空格。"""
        s = " ".join((text or "").split())
        return s if len(s) <= n else s[:n] + "…"

    def _data_desc(self, kind, iid):
        """Data 表某个 id 的完整说明（读不到返回空串）。"""
        try:
            pair = self.app.g._desc_map(kind).get(int(iid))
        except Exception:
            return ""
        return (pair[1] if pair and len(pair) > 1 else "") or ""

    def _actor_detail(self, i):
        """召唤兽候选的详情：档位 / 携带等级 / 六项资质 / 成长 + Actors 表说明。"""
        lines = []
        try:
            bd = self.app.babies_ed()
            cfg = bd.config(i) if bd else None
        except Exception:
            cfg = None
        if cfg:
            head = []
            if cfg.get("type"):
                head.append("档位 %s" % cfg["type"])
            if cfg.get("allow_lv") not in (None, ""):
                head.append("携带等级 %s" % cfg["allow_lv"])
            if head:
                lines.append("　".join(head))
            apt = []
            for k, lb in (("atk", "攻"), ("def", "防"), ("hp", "体"),
                          ("mp", "法"), ("agi", "速"), ("eva", "躲")):
                if cfg.get(k) not in (None, ""):
                    apt.append("%s%s" % (lb, cfg[k]))
            if apt:
                lines.append("资质：" + "　".join(apt))
            tail = []
            if cfg.get("grow") not in (None, ""):
                tail.append("成长 %s" % cfg["grow"])
            if cfg.get("life") not in (None, ""):
                tail.append("寿命 %s" % cfg["life"])
            if tail:
                lines.append("　".join(tail))
        d = self._data_desc("Actors", i)
        if d:
            lines.append(d)
        return "\n".join(lines)

    def kw_clear(self):
        self.var_kw.set("")
        self.fill_cands()

    def on_cand(self):
        fd = self.pick_field()
        sel = self.tv.selection()
        if fd is None or not sel:
            return
        n = int(sel[0][1:])
        if not (0 <= n < len(self.cands)):
            return
        val, nm, _cls, _note = self.cands[n]
        self.picked.setdefault(self.fam, {})[fd["key"]] = val
        self._refresh_dep_defaults(fd["key"])
        self.set_desc(self._cand_desc(fd, val, nm))

    def _cand_desc(self, fd, val, nm, head=True):
        """选中候选的详情：技能读技能管理器的说明，召唤兽读档位/资质/描述。

        head=True 时开头带一行「字段 = 名字」（说明框用）；悬停浮窗传
        False —— 鼠标就停在那行候选上，再报一遍名字是多余的（2026-10-07
        川）。编号 / 分类已在列表的两列里，这里一律不重复。
        """
        first = ("%s = %s" % (fd["label"], nm)) if head else ""
        if fd["kind"] == "actor":
            body = self._actor_detail(val) or ("召唤兽 id %s" % val)
        elif fd["kind"] == "skill":
            body = ""
            for i, _n, d in self._skill_rows():
                if i == val:
                    body = d or ""
                    break
            body = body or "（没有说明）"
        else:
            body = "点「应用选中的内容」写进选中的格子。"
        return "\n".join(x for x in (first, body) if x)

    def _int_changed(self):
        fd = self.pick_field()
        if fd is None or fd["kind"] not in ("int", "num"):
            return
        if self._loading_int:        # 我自己回填的默认值，不算用户改
            return
        txt = (self.var_int.get() or "").strip()
        if txt == "":
            # 清空＝不看这一项 → 交回游戏规则随机
            self.picked.setdefault(self.fam, {}).pop(fd["key"], None)
            self._num_edited.discard((self.fam, fd["key"]))
            return
        try:
            val = float(txt) if fd["kind"] == "num" else int(txt, 0)
        except ValueError:
            return
        self.picked.setdefault(self.fam, {})[fd["key"]] = val
        self._num_edited.add((self.fam, fd["key"]))

    # ------------------------------------------------------------ 说明 / 提示
    def _item_line(self):
        """当前家族第一格那件东西自己的详情（「物品就读物品的详情」）。"""
        grp = self._fam()
        if not grp or not grp.get("items"):
            return ""
        _slot, nm, iid, _cur = grp["items"][0]
        out = ["【本物品】%s（id=%s）" % (nm, iid)]
        d = self._data_desc(self.app._bag_kind(), iid)
        if d:
            # ⚠ 说明框没有滚动条，这里只取前三行（完整说明看背包页的悬停浮窗）。
            out.append("\n".join(d.splitlines()[:3]))
        return "\n".join(out)

    def set_desc(self, text):
        t2 = self.desc
        t2.configure(state="normal")
        t2.delete("1.0", "end")
        full = text or ""
        line = self._item_line()
        if line:
            full = (line + "\n" + full) if full else line
        if full:
            t2.insert("1.0", full)
        t2.configure(state="disabled")
        self.desc_full = full

    def desc_tip(self, event):
        if not self.desc_full:
            self.app._tip_hide()
            return
        if getattr(self.app, "_tip_key", None) == "paym:desc":
            return
        self.app._tip_show(self.desc_full,
                           self.desc.winfo_rootx() + event.x + 12,
                           self.desc.winfo_rooty() + event.y + 12,
                           key="paym:desc")

    def row_tip(self, event):
        row = self.tv.identify_row(event.y)
        if not row:
            self.app._tip_hide()
            return
        tipkey = "paym:%s" % row
        if getattr(self.app, "_tip_key", None) == tipkey:
            return
        n = int(row[1:])
        if not (0 <= n < len(self.cands)):
            return
        fd = self.pick_field()
        val, nm, _cls, note = self.cands[n]
        body = (self._cand_desc(fd, val, nm, head=False)
                if fd is not None else note)
        if not body:
            self.app._tip_hide()
            return
        self.app._tip_show(body,
                           self.tv.winfo_rootx() + event.x + 12,
                           self.tv.winfo_rooty() + event.y + 12, key=tipkey)

    # ------------------------------------------------------------ 写档
    def apply(self):
        """把当前挑好的内容写进**当前家族**里所有选中的格子。"""
        grp = self._fam()
        if grp is None or self.app.g is None:
            return
        over = dict(self.picked.get(self.fam) or {})
        kind = self.app._bag_kind()
        done, bad = [], []
        for slot in grp["slots"]:
            try:
                self.app.g.set_payload(kind, slot, over=over or None,
                                       force=True)
                done.append(slot)
            except Exception as e:
                bad.append((slot, zh_error(e)))
        if not done:
            messagebox.showerror("重抽失败",
                                 "没改成功：\n  " + "\n  ".join(
                                     "槽 %s：%s" % (s, w) for s, w in bad[:8]),
                                 parent=self.win)
            return
        self.app.mark_dirty()
        msg = "已重抽 %d 格（%s）" % (len(done), self.fam)
        if bad:
            msg += "；%d 格失败" % len(bad)
        self.after_change(msg)

    def random_all(self):
        """对全部选中的格子按游戏规则随机重抽（不看挑了什么）。"""
        slots = self.app._bag_slots(quiet=True)
        if not slots or self.app.g is None:
            return
        kind = self.app._bag_kind()
        done, bad = [], []
        for slot in slots:
            try:
                self.app.g.set_payload(kind, slot, force=True)
                done.append(slot)
            except Exception as e:
                bad.append((slot, zh_error(e)))
        if not done:
            messagebox.showerror(
                "重抽失败",
                "这些格子没有可重抽的内容：\n  " + "\n  ".join(
                    "槽 %s：%s" % (s, w) for s, w in bad[:8]),
                parent=self.win)
            return
        self.app.mark_dirty()
        msg = "已按游戏规则重抽 %d 格" % len(done)
        if bad:
            msg += "（%d 格跳过）" % len(bad)
        self.after_change(msg)

    def after_change(self, msg):
        """改完存档统一收尾：状态栏 + 刷背包 + 保住选中 + 重填自己。"""
        self.app.set_status(msg + "（记得点「保存修改」）")
        keep = list(self.app._bag_slots(quiet=True))
        self.app.fill_party()
        self.app.pack_select(keep)
        self._babies = None
        self.refill()

    def close(self):
        try:
            self.app._payload_win = None
        except Exception:
            pass
        try:
            self.win.destroy()
        except Exception:
            pass


# ---- 按钮统一贴字 ---------------------------------------------------------
# vista 主题给 ttk.Button 硬设 ~87px 最小宽（文字宽完全不参与计算），
# 短文字按钮全被顶到下限、看着"宽度固定"。widget 级 padding 用负值抵掉
# 下限后，宽度 ≈ 文字宽 + 左右各 8px。控件类型与全仓一致（都是 ttk.Button），
# 只是收掉多余内边距 —— 全仓按钮一律用 fit_btn() 创建（2026-10-03 川）。
_BTN_BASE = None


def _btn_base(master):
    """量一次当前主题给 ttk.Button 的最小宽度（跨主题/跨机器自适应）。"""
    global _BTN_BASE
    if _BTN_BASE is None:
        probe = ttk.Button(master, text="试")       # ⚠ 这里必须是 ttk.Button
        probe.place(x=-999, y=-999)                 # 用 fit_btn 会递归
        probe.update_idletasks()
        _BTN_BASE = probe.winfo_reqwidth() or 87
        probe.destroy()
    return _BTN_BASE


def _fit_pad(text, master):
    """贴字要用的负 padding（文字够宽、不用收窄时返回 0）。"""
    w = tkfont.nametofont("TkDefaultFont").measure(text)
    base = _btn_base(master)
    if w + 16 < base:
        return -int((base - w - 16) / 2)
    return 0


def fit_btn(master, text=None, command=None, **kw):
    """ttk.Button + 按文字宽度贴字（负 padding 抵掉 vista 的主题下限）。

    指定了 `width=` 的按钮跳过（那是"固定 N 字符宽"的显式要求）。
    """
    if text and "width" not in kw:
        pad = _fit_pad(text, master)
        if pad:
            kw["padding"] = "%d 0" % pad
    return ttk.Button(master, text=text, command=command, **kw)


def refit_btn(btn, text):
    """改按钮文字后按新文字重算贴字宽度（fit_btn 只在创建时算一次）。

    文字会变的按钮（例：新增召唤兽的「加这只」/「加选中的 N 只」）必须走它，
    不然负 padding 是按旧文字算的，换长文字会被裁掉。
    """
    pad = _fit_pad(text, btn)
    # padding="" = 清掉自定义值、回到主题默认（写 0 会少 2px，看着不齐）
    btn.configure(text=text, padding=("%d 0" % pad) if pad else "")


def center_win(win, parent=None, y_ratio=3):
    """把子窗口摆到父窗口上方 1/3、水平居中（父窗口没映射就摆屏幕居中）。

    ⚠ 必须在控件都 pack/grid 完再调（内部 update_idletasks 才知道窗口多大）。
    """
    try:
        win.update_idletasks()
        ww, wh = win.winfo_width(), win.winfo_height()
        if ww <= 1:
            ww = win.winfo_reqwidth()
        if wh <= 1:
            wh = win.winfo_reqheight()
        if parent is not None and parent.winfo_exists() \
                and parent.winfo_width() > 1:
            pw, ph = parent.winfo_width(), parent.winfo_height()
            px, py = parent.winfo_rootx(), parent.winfo_rooty()
        else:
            pw = win.winfo_screenwidth()
            ph = win.winfo_screenheight()
            px = py = 0
        win.geometry("+%d+%d" % (max(0, px + (pw - ww) // 2),
                                 max(0, py + (ph - wh) // y_ratio)))
    except Exception:
        pass


def esc_close(win, action=None):
    """给子窗口挂「按 Esc 关掉」（默认就是关窗，可换成"取消"回调）。

    ⚠ 两层都得要：
    * 只绑 Toplevel 一层就够收事件 —— Tk 的 bindtags 里含所属 Toplevel，
      焦点在列表/输入框上也收得到；
    * 但**必须把焦点收进窗口**：Esc 是键盘事件，Tk 只投给「当前焦点所在
      窗口」，对话框刚开时焦点还留在主窗口上（实测：不抢过来按 Esc 毫无
      反应）。`focus_set()` 是 Tk 内部焦点，不会抢系统前台。
    调用方若要指定焦点（搜索框等），把 widget.focus_set() 写在**它之后**。
    """
    def _do(_e=None):
        try:
            (action or win.destroy)()
        except Exception:
            pass
        return "break"
    win.bind("<Escape>", _do)
    win.focus_set()
    return win


class App(object):
    def __init__(self, root, save_path=None):
        self.tk = tk
        self.ttk = ttk
        self.root = root
        # Tk 回调里未捕获的异常默认只往 stderr 打一行；打包成 exe 后就变成"点了没反应"
        root.report_callback_exception = self._tk_exception

        self.doc = None            # doctree.Doc
        self.sv = None             # save.SaveDoc（不是本作存档时为 None）
        self.g = None              # game.GameEditor（背包/召唤兽/防作弊）
        self.nodes = {}            # tree iid -> 节点
        self.loaded = set()        # 已展开过的 iid
        self.actor_rows = {}       # tree iid -> 角色节点
        self.hits = []             # 搜索结果

        root.title(TITLE)
        root.geometry("1220x800")

        self._build_top(save_path)
        self._build_notebook()
        self._build_status()

        auto = save_path or self._guess_save()
        self._auto_load_job = None
        if auto:
            self.var_path.set(auto)
            # ⚠ 这个延迟载入必须能被取消：万一（比如自动化脚本）随后手动
            # load 了别的文件，200ms 后这个回调会醒来把 doc 换回 auto，
            # 之后所有改动都落在 auto 那本档上 —— 玩家真档就这么被写坏过
            # （2026-09-14 踩到）。cancel_auto_load() 给它留个后门。
            self._auto_load_job = root.after(
                200, lambda: self._auto_load_when_ready(auto))
        else:
            self.set_status("请点「选择存档…」打开 <游戏根>\\save.rvdata2")

    def _auto_load_when_ready(self, path, waited=0):
        """等数据表预载完再自动载入（预载线程见 `datatables.start_preload`）。

        ⚠ 不等的话，载入会撞上后台线程正在解析的表：`datatables.load` 会等到
          那张表解析完才返回（同一张表解析两遍更亏）。实测这 0.66 秒就是
          「第一次载入特别慢」的主因。
          最多等 3 秒 —— 表读不出来时（游戏没装）预载会立刻标记"跑过了"，
          正常不会等到上限。
        """
        if not datatables.preload_done() and waited < 3000:
            self._auto_load_job = self.root.after(
                60, lambda: self._auto_load_when_ready(path, waited + 60))
            return
        self._auto_load_job = None
        self.load(path)

    def cancel_auto_load(self):
        """取消 __init__ 里排队的延迟自动载入（自动化/测试脚本必须先调）。"""
        if getattr(self, "_auto_load_job", None) is not None:
            try:
                self.root.after_cancel(self._auto_load_job)
            except Exception:
                pass
            self._auto_load_job = None

    # ================================================== 顶部
    def _build_top(self, save_path):
        tk, ttk = self.tk, self.ttk
        top = ttk.Frame(self.root, padding=6)
        top.pack(fill="x")
        fit_btn(top, text="选择存档…", command=self.choose_file).pack(side="left")
        self.var_path = tk.StringVar(value=save_path or "")
        ttk.Entry(top, textvariable=self.var_path, width=58).pack(side="left", padx=6)
        fit_btn(top, text="重新载入", command=self.reload).pack(side="left")
        ttk.Separator(top, orient="vertical").pack(side="left", fill="y", padx=6)
        fit_btn(top, text="保存修改(Ctrl+S)",
                   command=self.save_save).pack(side="left")
        fit_btn(top, text="放弃修改", command=self.reload).pack(side="left", padx=4)
        ttk.Separator(top, orient="vertical").pack(side="left", fill="y", padx=6)
        fit_btn(top, text="导出报告", command=self.export_report).pack(side="left")
        fit_btn(top, text="导出明文", command=self.export_plain).pack(side="left",
                                                                       padx=4)
        self.root.bind("<Control-s>", lambda e: self.save_save())

        self.var_env = tk.StringVar()
        ttk.Label(self.root, textvariable=self.var_env, foreground="#555",
                  anchor="w").pack(fill="x", padx=8)

        info = ttk.Frame(self.root)
        info.pack(fill="x", padx=8, pady=(0, 4))
        ttk.Label(info, text="作者 @%s　·　开源地址 " % AUTHOR,
                  foreground="#555").pack(side="left")
        link = tk.Label(info, text=HOMEPAGE, foreground="#0a58ca", cursor="hand2",
                        font=("Consolas", 9, "underline"))
        link.pack(side="left")
        link.bind("<Button-1>", lambda e: self.open_homepage())
        fit_btn(info, text="关于", command=self.show_about,
                   width=6).pack(side="left", padx=8)
        fit_btn(info, text="复制地址", command=self.copy_homepage,
                   width=9).pack(side="left")
        ttk.Label(info, text=LICENSE_NAME, foreground="#888").pack(side="left", padx=8)

    # ================================================== 页签
    def _build_notebook(self):
        self.nb = self.ttk.Notebook(self.root)
        self.nb.pack(fill="both", expand=True, padx=6, pady=4)
        self._tab_quick()
        self._tab_saves()
        self._tab_tree()
        self._tab_actor()
        self._tab_party()
        self._tab_baby()
        # 开关/变量页只有 3 个 switch，没什么实际用，开关挪到快捷修改页做勾选框；
        # 但 _tab_switch 仍要调一次（只创建 tv_sw/tv_va widget 不挂到 Notebook），
        # 否则外部直接用到 self.tv_sw 的地方会报 AttributeError
        self._tab_switch(add_to_notebook=False)
        self._tab_machine()
        self._tab_db()
        self._tab_help()
        self._tab_log()

    # -------------------------------------------------- 1 概览 / 快捷修改
    def _tab_quick(self):
        tk, ttk = self.tk, self.ttk
        f = ttk.Frame(self.nb, padding=8)
        self.tab_quick = f
        self.nb.add(f, text="概览 / 快捷修改")

        # ---- 两大功能块左右分布（PanedWindow，中间可拖，两边等大 weight=1）
        body = ttk.Panedwindow(f, orient="horizontal")
        body.pack(fill="both", expand=True)

        # ========== 左：快捷修改 ==========
        g = ttk.LabelFrame(body, text="快捷修改（先点「应用」，再点上面的「保存修改」）",
                           padding=10)
        body.add(g, weight=1)
        self.var_gold = tk.StringVar()
        self.var_steps = tk.StringVar()
        self.var_savecnt = tk.StringVar()
        self.var_battlecnt = tk.StringVar()
        # 单行 4 列：金钱 / 步数 / 存档次数 / 战斗次数（共用同一行）
        flat_top = [
            ("金钱", self.var_gold), ("步数", self.var_steps),
            ("存档次数", self.var_savecnt), ("战斗次数", self.var_battlecnt),
        ]
        for i, (label, var) in enumerate(flat_top):
            col_label = i * 2
            col_entry = i * 2 + 1
            ttk.Label(g, text=label + "：", anchor="w").grid(
                row=0, column=col_label, sticky="w", padx=(4, 2), pady=3)
            ttk.Entry(g, textvariable=var, width=10).grid(
                row=0, column=col_entry, sticky="we", padx=(0, 8))
        # ---- 祈福池储备（party.@hash 的 *_pool，4 个值一行）----
        # ⚠ 别只写「气血 / 魔法」：这 4 个是**祈福池的储备量**，不是角色的当前值。
        #   游戏战斗结束时 Game_Party#pool_apply 按池给角色/宠物补满血·灵，
        #   但只在 $game_party.hash[:pool_effective] 挂了这个单位时才生效。
        #   （2026-10-04 川以为是没用的控件要求删掉 —— 补上说明后加回。）
        lf = ttk.LabelFrame(g, text="祈福池储备", padding=6)
        lf.grid(row=1, column=0, columnspan=8, sticky="we", pady=(8, 2))
        self.var_bless = {}
        bless_flat = [
            ("角色气血", "actor_hp_pool"),
            ("角色魔法", "actor_mp_pool"),
            ("宠物气血", "baby_hp_pool"),
            ("宠物魔法", "baby_mp_pool"),
        ]
        bless_tip = ("祈福池的储备量（不是角色当前气血/魔法）。\n"
                     "游戏里用物品往池里加：左键＝角色池、右键＝宠物池；\n"
                     "战斗结束时按池给角色/宠物补满气血·灵力。\n"
                     "⚠ 前提是游戏里把这个单位挂到了池子上（pool_effective），\n"
                     "没挂过（4 个值都是 0）时填了也不生效。")
        for i, (label, key) in enumerate(bless_flat):
            ttk.Label(lf, text=label + "：", anchor="w").grid(
                row=0, column=i * 2, sticky="w", padx=(4, 2), pady=3)
            var = tk.StringVar()
            self.var_bless[key] = var
            ent = ttk.Entry(lf, textvariable=var, width=10)
            ent.grid(row=0, column=i * 2 + 1, sticky="we", padx=(0, 8))
            lf.columnconfigure(i * 2 + 1, weight=1)
            self._bind_tip(ent, bless_tip)
        ttk.Label(lf, text=("战斗结束按池给角色/宠物补满气血·灵力；\n"
                            "没在游戏里挂到池子上时（4 个都是 0）填了不生效。"),
                  foreground="#888", justify="left").grid(
            row=1, column=0, columnspan=8, sticky="w", padx=4, pady=(2, 0))
        ttk.Separator(g, orient="horizontal").grid(
            row=2, column=0, columnspan=8, sticky="we", pady=(8, 4))
        # 金钱说明：上限/安全值直接取 game 常量（内测版 MAX_GOLD = 9,999,999,999）
        ttk.Label(g, text=("金钱上限 {:,}（约 100 亿）；超限自动压到 {:,}（上限 5/6）\n"
                           "改钱会同步重算 Lock 校验和，游戏读档不会报「游戏异常」"
                           ).format(game.MAX_GOLD, game.SAFE_GOLD),
                  foreground="#888", justify="left", wraplength=420).grid(
            row=3, column=0, columnspan=8, sticky="w", pady=(4, 0))
        bar = ttk.Frame(g)
        bar.grid(row=4, column=0, columnspan=8, sticky="w", pady=(8, 0))
        fit_btn(bar, text="应用", command=self.apply_quick).pack(side="left")
        fit_btn(bar, text="防作弊检测并修复",
                   command=self.detect_and_fix_cheats).pack(side="left", padx=8)
        self.var_lock = tk.StringVar(value="防作弊检测：—")
        ttk.Label(g, textvariable=self.var_lock, foreground="#c00"
                  ).grid(row=5, column=0, columnspan=8, sticky="w", pady=(6, 0))
        # 存档概况
        inf = ttk.Frame(g)
        inf.grid(row=6, column=0, columnspan=8, sticky="nsew", pady=6)
        g.rowconfigure(6, weight=1)
        # 4 个 entry 列等权重 → 4 组输入框平均分配宽度
        for c in (1, 3, 5, 7):
            g.columnconfigure(c, weight=1)
        self.txt_info = tk.Text(inf, height=10, wrap="none", font=("Consolas", 10))
        vs = ttk.Scrollbar(inf, orient="vertical", command=self.txt_info.yview)
        hs = ttk.Scrollbar(inf, orient="horizontal", command=self.txt_info.xview)
        self.txt_info.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        vs.pack(side="right", fill="y")
        hs.pack(side="bottom", fill="x")
        self.txt_info.pack(fill="both", expand=True)

        # ========== 右：防作弊体检 ==========
        h = ttk.LabelFrame(body, text="防作弊体检（游戏自己的检查规则）", padding=10)
        body.add(h, weight=1)
        # v0.5.0 灰字提示：体检说明（精简，加 wraplength 自动换行）
        ttk.Label(h, text=
                  "内测版有两层：Lock 校验和（金钱等关键数值受它保护）+ 记账校验\n"
                  "（金钱/物品/变量/人气/贡献五类账，账实不符会被踢出游戏）；\n"
                  "没有周期检查、没有作弊标记 —— 越界本身只是提示，账不符才致命。\n"
                  "下表按游戏 Config::Game 的上限列出越界项；悬浮条目看具体说明。",
                  foreground="#555", justify="left", wraplength=420).pack(anchor="w")
        self.var_cheat = tk.StringVar(value="")
        ttk.Label(h, textvariable=self.var_cheat, foreground="#c00",
                  justify="left").pack(anchor="w", pady=(4, 0))
        gv = ttk.Frame(h)
        gv.pack(fill="both", expand=True, pady=6)
        self.tv_guard = ttk.Treeview(gv, columns=("a", "b", "c"),
                                     show="headings", height=9)
        for c, w, t in (("a", 200, "项目"), ("b", 110, "当前值"),
                        ("c", 110, "上限/记录值")):
            self.tv_guard.heading(c, text=t)
            self.tv_guard.column(c, width=w, anchor="w")
        self._guard_notes = {}
        # 保存流程里"存盘前体检"算好的那份，交给接下来的面板刷新复用；别处为 None
        self._guard_rows = None
        self.tv_guard.bind("<Motion>", self._guard_tip_motion)
        self.tv_guard.bind("<Leave>", lambda e: self._tip_hide())
        vs = ttk.Scrollbar(gv, orient="vertical", command=self.tv_guard.yview)
        self.tv_guard.configure(yscrollcommand=vs.set)
        vs.pack(side="right", fill="y")
        self.tv_guard.pack(fill="both", expand=True)
        gbar = ttk.Frame(h)
        gbar.pack(fill="x")
        fit_btn(gbar, text="体检",
                   command=self.guard_check).pack(side="left")
        fit_btn(gbar, text="一键按规则修复",
                   command=self.guard_fix).pack(side="left", padx=6)
        fit_btn(gbar, text="清除作弊标记",
                   command=self.guard_clear).pack(side="left", padx=6)
        fit_btn(gbar, text="同步物品计数校验",
                   command=self.guard_resync).pack(side="left", padx=6)
        fit_btn(gbar, text="清理所有存档（含 AutoSave）",
                   command=self.guard_fix_all).pack(side="left", padx=(18, 6))
        # 初始把 PanedWindow 分隔条放到 50%（等窗口实际尺寸出来后再设）
        self.root.after(150, lambda: body.sashpos(0, body.winfo_width() // 2))

    # -------------------------------------------------- 6.5 机器码（存档绑定）
    def _tab_machine(self):
        """照画迹1 的机器码页：看本机机器码、看存档记录的、改完写回去。"""
        tk, ttk = self.tk, self.ttk
        f = ttk.Frame(self.nb, padding=10)
        self.tab_machine = f
        self.nb.add(f, text="机器码")

        ttk.Label(f, text="机器码（存档绑定）",
                  font=("Microsoft YaHei UI", 12, "bold")).pack(anchor="w")
        ttk.Label(f, text="游戏用 System\\main.dll 的 get_hard_disk_character() 取本机机器码，"
                          "存在存档的 $game_system.config[:hard_disk_code]（一个数组）。\n"
                          "游戏启动时会 include? 比对，不在里面就 msgbox「存档异常」然后退出 ——\n"
                          "所以存档换到别的电脑上打不开；把新机器的机器码「加入」进去就行了。\n"
                          "⚠ 保存时不会自动改机器码 —— 你把它换成谁的，存盘、重载后还是那个；"
                          "要不要加本机码，只由下面这几个按钮决定。",
                  foreground="#555", justify="left").pack(anchor="w", pady=(4, 10))

        box = ttk.LabelFrame(f, text="当前情况", padding=10)
        box.pack(fill="x")
        self.var_machine = tk.StringVar(value="机器码：—")
        ttk.Label(box, textvariable=self.var_machine, justify="left",
                  font=("Microsoft YaHei UI", 10), wraplength=1100
                  ).pack(anchor="w")
        self.var_machine_list = tk.StringVar(value="")
        ttk.Label(box, textvariable=self.var_machine_list, foreground="#555",
                  justify="left", wraplength=1100).pack(anchor="w")

        eb = ttk.LabelFrame(f, text="修改", padding=10)
        eb.pack(fill="x", pady=10)
        bar1 = ttk.Frame(eb)
        bar1.pack(fill="x")
        ttk.Label(bar1, text="机器码：").pack(side="left")
        self.var_machine_id = tk.StringVar()
        ttk.Entry(bar1, textvariable=self.var_machine_id, width=22
                  ).pack(side="left")
        fit_btn(bar1, text="读取本机机器码",
                   command=self.machine_fill_local).pack(side="left", padx=6)
        fit_btn(bar1, text="读存档里第一个",
                   command=self.machine_fill_saved).pack(side="left", padx=6)
        fit_btn(bar1, text="刷新",
                   command=self.machine_show).pack(side="left", padx=6)

        bar2 = ttk.Frame(eb)
        bar2.pack(fill="x", pady=8)
        fit_btn(bar2, text="加入存档（追加，推荐）",
                   command=self.machine_add).pack(side="left")
        fit_btn(bar2, text="替换成这个（只留一个）",
                   command=self.machine_set).pack(side="left", padx=6)
        fit_btn(bar2, text="用本机机器码替换",
                   command=self.machine_use_local).pack(side="left", padx=6)
        fit_btn(bar2, text="清空存档记录",
                   command=self.machine_clear).pack(side="left", padx=6)
        ttk.Label(eb, text="改完记得 Ctrl+S 保存。只改存档是安全的：游戏只对 Game.exe 和\n"
                           "System\\main.dll 做 md5 校验，不管存档。",
                  foreground="#777", justify="left").pack(anchor="w")

        log = ttk.LabelFrame(f, text="操作记录", padding=10)
        log.pack(fill="both", expand=True)
        self.txt_machine = tk.Text(log, height=10, wrap="word",
                                   font=("Microsoft YaHei UI", 10))
        vs = ttk.Scrollbar(log, orient="vertical", command=self.txt_machine.yview)
        self.txt_machine.configure(yscrollcommand=vs.set)
        vs.pack(side="right", fill="y")
        self.txt_machine.pack(fill="both", expand=True)

    # -------------------------------------------------- 1.5 存档管理
    def _tab_saves(self):
        """存档管理：备份 / 删除备份 / 恢复选中 / 恢复最新 / 删除非最新。

        备份放在**存档旁边**的子目录里（默认 .huaji2-save-editor），只做文件复制，
        不解析内容 —— 万一存档被改坏了，这里也能救回来。
        """
        tk, ttk = self.tk, self.ttk
        f = ttk.Frame(self.nb, padding=8)
        self.tab_saves = f
        self.nb.add(f, text="存档管理")

        self.var_saves_info = tk.StringVar(value="存档管理：—")
        ttk.Label(f, textvariable=self.var_saves_info, justify="left",
                  font=("Microsoft YaHei UI", 10),
                  wraplength=1150).pack(anchor="w")
        ttk.Label(f, text="备份目录就在存档旁边（.huaji2-save-editor）；"
                          "「恢复最新」＝把上一次修改之前的存档换回来；"
                          "「删除非最新」只留最新的一份 + 手动备份（自动备份才清）。",
                  foreground="#777").pack(anchor="w", pady=(2, 6))

        bar = ttk.Frame(f)
        bar.pack(fill="x")
        fit_btn(bar, text="立即备份",
                   command=self.saves_backup).pack(side="left")
        fit_btn(bar, text="编辑备注",
                   command=self.saves_edit_note).pack(side="left", padx=6)
        fit_btn(bar, text="恢复选中",
                   command=self.saves_restore).pack(side="left", padx=6)
        fit_btn(bar, text="恢复最新",
                   command=self.saves_restore_newest).pack(side="left", padx=6)
        fit_btn(bar, text="删除选中",
                   command=self.saves_delete).pack(side="left", padx=6)
        fit_btn(bar, text="删除无备注",
                   command=self.saves_delete_no_note).pack(side="left", padx=6)
        fit_btn(bar, text="删除非最新",
                   command=self.saves_delete_old).pack(side="left", padx=6)
        fit_btn(bar, text="刷新",
                   command=self.saves_refresh).pack(side="left", padx=6)
        fit_btn(bar, text="打开备份目录",
                   command=self.saves_open_dir).pack(side="left", padx=6)

        cols = ("idx", "time", "kind", "size", "name", "note")
        self.tv_saves = ttk.Treeview(f, columns=cols, show="headings", height=16,
                                     selectmode="extended")
        for c, w, t in (("idx", 44, "#"), ("time", 168, "时间"),
                        ("kind", 108, "类型"), ("size", 86, "大小"),
                        ("name", 330, "文件"), ("note", 380, "备注")):
            self.tv_saves.heading(c, text=t)
            self.tv_saves.column(c, width=w, anchor="w")
        vs = ttk.Scrollbar(f, orient="vertical", command=self.tv_saves.yview)
        self.tv_saves.configure(yscrollcommand=vs.set)
        vs.pack(side="right", fill="y")
        self.tv_saves.pack(fill="both", expand=True, pady=6)
        self.tv_saves.bind("<Double-1>", lambda e: self.saves_restore())
        self.save_rows = []

    def saves_dir(self):
        if not self.doc:
            return None
        return backup.backup_dir(self.doc.path, create=False)

    def _saves_ready(self):
        """存档管理能不能动手：既要打开过文件，也要**确实是存档**（`self.sv`）。

        ⚠ 打开一个非存档文件（比如游戏目录里的 `Logs\\Battle\\*.bt2`）时 `self.doc`
        是有的、`self.sv` 是 None —— 以前只看 `self.doc`，结果「立即备份」会把那个
        非存档文件复制到它旁边、还在那里建出 `.huaji2-save-editor` 备份目录
        （2026-09-27 查实：测试就是这么往游戏目录里堆了几百份垃圾的）。
        """
        if not self.doc:
            messagebox.showinfo("提示", "先打开一个存档。", parent=self.root)
            return False
        if self.sv is None:
            messagebox.showwarning("不能操作",
                                   "当前打开的不是存档文件，\n没法做备份 / 恢复。",
                                   parent=self.root)
            return False
        return True

    def saves_refresh(self):
        self.tv_saves.delete(*self.tv_saves.get_children())
        self.save_rows = []
        if not self.doc:
            self.var_saves_info.set("存档管理：还没打开存档")
            return
        if self.sv is None:
            # 非存档文件（如 Logs\Battle\*.bt2）→ 不去它旁边扫备份目录
            # （既没意义，又可能在游戏目录里慢慢爬）
            self.var_saves_info.set("存档管理：当前打开的不是存档文件")
            return
        rows = backup.list_backups(self.doc.path)
        self.save_rows = rows
        kind_cn = {"auto": "自动", "manual": "手动",
                   "before-restore": "恢复前", "other": "其它"}
        for i, r in enumerate(rows):
            self.tv_saves.insert("", "end", iid="b%d" % i,
                                 values=(i + 1,
                                         r["stamp"].replace("_", " "),
                                         kind_cn.get(r["kind"], r["kind"]),
                                         "%.1f KB" % (r["size"] / 1024.0),
                                         r["name"], r["note"]))
        d = backup.backup_dir(self.doc.path)
        self.var_saves_info.set(
            "当前存档：%s\n备份目录：%s（共 %d 份，合计 %.1f MB）"
            % (self.doc.path, d, len(rows),
               sum(r["size"] for r in rows) / 1048576.0))

    def saves_backup(self):
        if not self._saves_ready():
            return
        try:
            p = backup.backup(self.doc.path, backup.KIND_MANUAL)
        except Exception as e:
            messagebox.showerror("备份失败", zh_error(e), parent=self.root)
            return
        # 备份完成 → 弹窗让玩家填备注（可留空＝不写备注）
        dlg = NoteDialog(self.root, title="备份完成 - 填备注",
                         label="已备份到：\n%s\n\n备注（可留空，会存在备份旁的 .txt）："
                               % p)
        self.root.wait_window(dlg)
        note = (dlg.result or "").strip() if dlg.result is not None else ""
        if note:
            try:
                backup.set_note(p, note)
            except Exception as e:
                messagebox.showerror("写备注失败", zh_error(e), parent=self.root)
        self.saves_refresh()
        self.set_status("已备份到 %s（备注：%s）" % (os.path.basename(p),
                                                     note or "无"))

    def _save_sel(self, quiet=False):
        sel = self.tv_saves.selection()
        if not sel:
            if not quiet:
                messagebox.showinfo("提示", "先在列表里选中一份备份。",
                                    parent=self.root)
            return []
        out = []
        for iid in sel:
            i = int(iid[1:])
            if 0 <= i < len(self.save_rows):
                out.append(self.save_rows[i])
        return out

    def saves_restore(self):
        if not self._saves_ready():
            return
        rows = self._save_sel()
        if not rows:
            return
        if len(rows) > 1:
            messagebox.showinfo("提示", "恢复一次只能选一份。", parent=self.root)
            return
        r = rows[0]
        if not self.confirm(
                "确认恢复",
                "要用这份备份覆盖当前存档吗？\n\n  %s\n  %s\n\n"
                "（备份都是完整的存档副本，恢复后直接重新载入）"
                % (r["stamp"], r["name"])):
            return
        try:
            backup.restore(r["path"], self.doc.path)
        except Exception as e:
            messagebox.showerror("恢复失败", zh_error(e), parent=self.root)
            return
        self.load(self.doc.path)          # 重新载入，界面跟着变
        self.saves_refresh()
        self.set_status("已恢复 %s" % r["name"])
        messagebox.showinfo("恢复完成",
                            "已用\n  %s\n覆盖当前存档，并重新载入。" % r["name"],
                            parent=self.root)

    def saves_restore_newest(self):
        """恢复最新＝把**上一次修改之前**的存档换回来（最新的一份备份）。"""
        if not self._saves_ready():
            return
        self.saves_refresh()
        r = self.save_rows[0] if self.save_rows else None
        for x in self.save_rows:          # 优先同一存档名的备份
            if x["is_this_file"]:
                r = x
                break
        if r is None:
            messagebox.showinfo("提示", "备份目录里还没有备份。", parent=self.root)
            return
        if not self.confirm(
                "恢复最新",
                "把存档换回「上一次修改之前」的状态吗？\n\n"
                "  用的备份：%s\n  %s\n\n"
                "（这份是目前最新的一份备份）" % (r["stamp"], r["name"])):
            return
        try:
            backup.restore(r["path"], self.doc.path)
        except Exception as e:
            messagebox.showerror("恢复失败", zh_error(e), parent=self.root)
            return
        self.load(self.doc.path)
        self.saves_refresh()
        self.set_status("已恢复到最新备份：%s" % r["name"])

    def saves_delete(self):
        rows = self._save_sel()
        if not rows:
            return
        if not self.confirm(
                "确认删除",
                "删掉这 %d 份备份？（不可撤销）\n\n%s"
                % (len(rows), "\n".join("  " + r["name"] for r in rows[:8]))):
            return
        n = backup.remove([r["path"] for r in rows])
        self.saves_refresh()
        self.set_status("已删除 %d 份备份" % n)

    def saves_delete_no_note(self):
        """删除全部没有备注的备份（有 .txt 备注的保留）。"""
        if not self.doc:
            return
        self.saves_refresh()
        rows = [r for r in self.save_rows if not r["note"]]
        if not rows:
            messagebox.showinfo("删除无备注", "没有无备注的备份。", parent=self.root)
            return
        if not self.confirm(
                "删除无备注",
                "删掉 %d 份没有备注的备份？（不可撤销）\n\n%s"
                % (len(rows), "\n".join("  " + r["name"] for r in rows[:8]))):
            return
        n = backup.remove([r["path"] for r in rows])
        self.saves_refresh()
        self.set_status("已删除 %d 份无备注备份" % n)

    def saves_edit_note(self):
        """给选中的备份改备注（存成备份旁边的 .txt；清空就是删备注）。"""
        rows = self._save_sel()
        if not rows:
            return
        if len(rows) > 1:
            messagebox.showinfo("提示", "一次只能改一份的备注。", parent=self.root)
            return
        r = rows[0]
        dlg = NoteDialog(self.root, r["note"])
        self.root.wait_window(dlg)
        if dlg.result is None:
            return
        try:
            backup.set_note(r["path"], dlg.result)
        except Exception as e:
            messagebox.showerror("写备注失败", zh_error(e), parent=self.root)
            return
        self.saves_refresh()
        self.set_status("已更新备注：%s" % r["name"])

    def saves_delete_old(self):
        """删除非最新＝只留最新的一份 + 所有手动备份，其余（自动备份）全删。"""
        if not self.doc:
            return
        self.saves_refresh()
        rows = self.save_rows
        if len(rows) < 2:
            messagebox.showinfo("提示", "只有 %d 份备份，不用清理。" % len(rows),
                                parent=self.root)
            return
        keep = rows[0]
        for x in rows:
            if x["is_this_file"]:
                keep = x
                break
        n_manual = sum(1 for r in rows if r["kind"] == "manual")
        if n_manual == len(rows):
            messagebox.showinfo("删除非最新",
                                "全是手动备份（共 %d 份），这份操作不碰手动备份。"
                                % len(rows), parent=self.root)
            return
        n_del = len(rows) - n_manual - 1     # 留最新一份 + 所有手动
        if not self.confirm(
                "删除非最新",
                "留最新的一份 + 所有手动备份，其余 %d 份自动备份删掉？"
                "（不可撤销）\n\n"
                "  保留：%s\n  %s" % (n_del, keep["stamp"], keep["name"])):
            return
        kept, n = backup.keep_newest(self.doc.path)
        self.saves_refresh()
        self.set_status("已删除 %d 份自动备份，保留最新 %s"
                        % (n, os.path.basename(kept["path"]) if kept else "无"))

    def saves_open_dir(self):
        d = self.saves_dir()
        if not d or not os.path.isdir(d):
            messagebox.showinfo("提示", "备份目录还没建（先点一次「立即备份」）。",
                                parent=self.root)
            return
        try:
            os.startfile(d)          # noqa: S606  （Windows 专用）
        except Exception:
            self.set_status("备份目录：%s" % d)

    # -------------------------------------------------- 2 全部解析数据
    def _tab_tree(self):
        tk, ttk = self.tk, self.ttk
        f = ttk.Frame(self.nb, padding=8)
        self.tab_tree = f
        self.nb.add(f, text="全部解析数据")

        bar = ttk.Frame(f)
        bar.pack(fill="x")
        ttk.Label(bar, text="全局搜索：").pack(side="left")
        self.var_search = tk.StringVar()
        ent = ttk.Entry(bar, textvariable=self.var_search, width=30)
        ent.pack(side="left")
        ent.bind("<Return>", lambda e: self.global_search())
        fit_btn(bar, text="搜索", command=self.global_search).pack(side="left",
                                                                     padx=4)
        fit_btn(bar, text="清空结果", command=self.clear_search).pack(side="left")
        fit_btn(bar, text="全部折叠", command=self.collapse_all).pack(side="left",
                                                                       padx=4)
        ttk.Label(bar, text="　（搜字段名或值 → 双击结果跳到树上；右键可改标量）",
                  foreground="#777").pack(side="left")

        self.fr_hits = ttk.Frame(f)
        self.fr_hits.pack(fill="x")
        ttk.Label(self.fr_hits, text="搜索结果（双击跳转）").pack(anchor="w")
        self.tv_hits = ttk.Treeview(self.fr_hits, columns=("p", "t", "v"),
                                    show="headings", height=5)
        for c, w, t in (("p", 460, "路径"), ("t", 60, "类型"), ("v", 320, "值")):
            self.tv_hits.heading(c, text=t)
            self.tv_hits.column(c, width=w, anchor="w")
        vs_hits = ttk.Scrollbar(self.fr_hits, orient="vertical",
                                command=self.tv_hits.yview)
        self.tv_hits.configure(yscrollcommand=vs_hits.set)
        vs_hits.pack(side="right", fill="y")
        self.tv_hits.pack(fill="x")
        self.tv_hits.bind("<Double-1>", self.goto_search_hit)
        self.tv_hits.bind("<Return>", self.goto_search_hit)

        body = ttk.Panedwindow(f, orient="horizontal")
        body.pack(fill="both", expand=True, pady=4)

        left = ttk.Frame(body)
        self.tree = ttk.Treeview(left, columns=("type", "value"),
                                 show="tree headings")
        self.tree.heading("#0", text="路径 / 字段")
        for c, w, t in (("type", 60, "类型"), ("value", 600, "值")):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor="w")
        self.tree.column("#0", width=360)
        vs = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        hs = ttk.Scrollbar(left, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        vs.pack(side="right", fill="y")
        hs.pack(side="bottom", fill="x")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewOpen>>", self.on_open)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        self.tree.bind("<Button-3>", self.tree_menu)
        self.tree.bind("<Double-1>", lambda e: self.tree_edit_value())
        self.tree.bind("<Motion>", self._tree_tip_motion)
        self.tree.bind("<Leave>", lambda e: self._tip_hide())
        body.add(left, weight=3)

        right = ttk.Frame(body)
        ttk.Label(right, text="节点详情").pack(anchor="w")
        self.txt_node = tk.Text(right, wrap="word", width=46,
                                font=("Microsoft YaHei UI", 10))
        vs3 = ttk.Scrollbar(right, orient="vertical", command=self.txt_node.yview)
        self.txt_node.configure(yscrollcommand=vs3.set)
        vs3.pack(side="right", fill="y")
        self.txt_node.pack(fill="both", expand=True)
        body.add(right, weight=2)

        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label="修改这个字段…", command=self.tree_edit_value)
        self.menu.add_command(label="展开子项", command=lambda: self.on_open())
        self.menu.add_command(label="复制值", command=self.tree_copy)
        self.menu.add_separator()
        self.menu.add_command(label="刷新整棵树", command=self.fill_tree)

    # -------------------------------------------------- 3 角色 / 属性
    def _tab_actor(self):
        tk, ttk = self.tk, self.ttk
        f = ttk.Frame(self.nb, padding=8)
        self.tab_actor = f
        self.nb.add(f, text="角色 / 属性")

        ttk.Label(f, text="角色列表（点一行在下面改；Ctrl/Shift 多选 → "
                          "预设 / 应用修改对全部选中角色生效）").pack(anchor="w")
        cols = ("no", "id", "name", "sect", "lv", "hp", "mp", "cls")
        # ⚠ height=5（不是 7）：左栏是竖向 pack，先来先分 —— 上面这块多占一行，
        #   下面就少一行。实测 1080x757 时左栏差 43px、把「门派技能」的清单底部
        #   切了（2026-09-20 川截图）。存档里就 5 个角色，5 行刚好不用滚。
        # ⚠ selectmode="extended"（2026-10-07 川：多选后点预设只改第一个）：
        #   Ctrl 点选 / Shift 连选；预设那几个按钮 + 「应用修改」对全部选中生效。
        self.tv_actor = ttk.Treeview(f, columns=cols, show="headings", height=5,
                                     selectmode="extended")
        for c, w, t in (("no", 34, "序"),
                        ("id", 50, "ID"), ("name", 130, "名字"),
                        ("sect", 80, "门派"), ("lv", 50, "等级"),
                        ("hp", 80, "HP"), ("mp", 80, "MP"), ("cls", 70, "职业ID")):
            self.tv_actor.heading(c, text=t)
            self.tv_actor.column(c, width=w, anchor="center" if c == "no" else "w")
        vs_actor = ttk.Scrollbar(f, orient="vertical", command=self.tv_actor.yview)
        self.tv_actor.configure(yscrollcommand=vs_actor.set)
        vs_actor.pack(side="right", fill="y")
        self.tv_actor.pack(fill="x")
        self.tv_actor.bind("<<TreeviewSelect>>", lambda e: self.on_actor_select())

        # ---- 左右布局（PanedWindow，中间可拖）：左「基础字段」/ 右「属性概览」
        # 参考「概览 / 快捷修改」页的写法，两边等大 weight=1。
        mid = ttk.Panedwindow(f, orient="horizontal")
        mid.pack(fill="both", expand=True, pady=6)

        # ========== 左：基础字段 + 中文属性 ==========
        left = ttk.Frame(mid)
        mid.add(left, weight=1)
        g = ttk.LabelFrame(left, text="基础字段", padding=8)
        g.pack(fill="x")
        self._actor_entry_parent = str(g)   # 冒烟测试用来确认左右确实分开了
        self.actor_vars = {}
        # 名字跟**游戏界面**保持一致（游戏里叫「获得经验」「升级经验」），免得对不上。
        # 「升级经验」是查表算出来的（游戏脚本 $exps[:actor][等级]），
        # 存档里没这个字段 → 用 "#" 前缀标记成只读。
        # ⚠ 2026-09-20：等级**只读展示**（川要求去掉所有页签的等级修改，但要看得见）。
        # 「#」前缀 = 不给改，走只读 + 灰字（和「升级经验」同一套）。
        base = [("@name", "名字"),
                ("#level", "等级"),
                ("@hp", "气血"), ("@mp", "魔法"), ("@tp", "愤怒"),
                ("@exp", "获得经验"), ("#next_exp", "升级经验")]
        # 每行**4 列**（和「概览 / 快捷修改」页的金钱/步数/存档次数/战斗次数同一套排法）：
        # 一行一个太占地，6 个字段会拉成 6 行把下面的按钮条挤没；4 列只要 2 行。
        # 行序 = i//4，第几组列 = i%4；每组占 2 个 grid 列（标签 + 输入框）。
        for i, (k, label) in enumerate(base):
            r, c = i // 4, i % 4
            # 「升级经验」是查表算的，只读 → 灰一点，一眼能分辨
            fg = "#8a8a8a" if k.startswith("#") else ""
            # ⚠ 不要给标签设 width：撑宽后文字右边的空白全垫在输入框左边
            # （2026-09-14 川截图反馈）。照「快捷修改」的样式：自适应 + 全角冒号。
            ttk.Label(g, text=label + "：", foreground=fg).grid(
                row=r, column=c * 2, sticky="w", pady=2,
                padx=(0 if c == 0 else 10, 2))
            var = tk.StringVar()
            ro = "readonly" if k.startswith("#") else "normal"
            ent = ttk.Entry(g, textvariable=var, width=13, state=ro)
            ent.grid(row=r, column=c * 2 + 1, pady=2, sticky="we")
            self.actor_vars[k] = var
            # 「获得经验」这格最容易踩坑（改了游戏里不动），挂个悬浮说明
            if k == "@exp":
                self._bind_tip(ent, "本级内经验（存档 @exp[@class_id]）。\n"
                                    "⚠ 人物升级只有两条路：地图上点「升级」\n"
                                    "按钮（一次一级），或事件指令 —— 打怪拿经验\n"
                                    "不会自动升级，所以改这里游戏里基本没反应。\n"
                                    "想自己点升级就点下面的「经验拉满」（只给经验）；\n"
                                    "要直接满级点「一键满级」（连等级一起写）。")
            elif k == "#level":
                self._bind_tip(ent, "当前等级（存档 @level）。只读。\n"
                                    "人物不会因为经验多而自动升级 —— 要直接满级点\n"
                                    "「一键满级」（连着等级一起写）；只想要经验、\n"
                                    "自己回游戏点升级，就点「经验拉满」。")
            elif k == "#next_exp":
                self._bind_tip(ent, "升到下一级还需要的经验（查游戏表 $exps，\n"
                                    "下标就是当前等级）。存档里没有这个字段，\n"
                                    "所以只读、改了也没用。")
        # 4 组输入框等权重，窗口拉宽时一起变宽
        for c in (1, 3, 5, 7):
            g.columnconfigure(c, weight=1)

        g2 = ttk.LabelFrame(left, text="中文属性（Game_Actor_Attr）", padding=8)
        g2.pack(fill="x", pady=(4, 0))
        self.attr_vars = {}
        # 每行 4 列（原来是 5 行 × 2 列）→ 10 个字段只要 3 行
        for i, k in enumerate(save.SaveDoc.ATTR_FIELDS):
            r, c = i // 4, i % 4
            ttk.Label(g2, text=k[1:] + "：").grid(
                row=r, column=c * 2, sticky="w", pady=2,
                padx=(0 if c == 0 else 10, 2))
            var = tk.StringVar()
            ttk.Entry(g2, textvariable=var, width=8).grid(
                row=r, column=c * 2 + 1, pady=2, sticky="we")
            self.attr_vars[k] = var
        for c in (1, 3, 5, 7):
            g2.columnconfigure(c, weight=1)

        bar = ttk.Frame(left)
        bar.pack(fill="x", pady=(4, 0))
        fit_btn(bar, "应用修改",
                   self.apply_actor).pack(side="left")
        # 「一键满级」= 等级顶到 60 + 获得经验对齐满级门槛（语义层 actor_exp_full）。
        # 为什么不是「+10000」：人物打怪拿经验**不会**自动升级（脚本里
        # change_exp 没有升级循环，见 game.actor_exp_full 的说明），
        # 只加经验在游戏里毫无反应；要一步到满级就得连着等级一起写。
        btn_full = fit_btn(bar, "一键满级",
                              lambda: self.actor_preset("expfull"))
        self._bind_tip(btn_full,
                       "等级直接给到 %d 级，获得经验对齐该级门槛。\n"
                       "⚠ 人物不会因为经验多而自动升级，\n"
                       "所以这里连着等级一起写。" % game.MAX_LEVEL_ACTOR)
        btn_full.pack(side="left", padx=6)
        # 「经验拉满」（2026-10-03 川）：只写经验（ACTOR_EXP_FILL），**等级不动**。
        # 回游戏在地图界面自己点「升级」（一次一级）—— 和「一键满级」只差这一点。
        btn_fill = fit_btn(bar, "经验拉满",
                              lambda: self.actor_preset("expfill"))
        # ⚠ 单位是**亿**不是万：30 亿写成"%d 万"是 300000 万，没人看得懂
        #   （2026-10-07 改成亿级时一起改的；`%.2f` 两位小数够看）。
        self._bind_tip(btn_fill,
                       "获得经验写到 %.2f 亿，等级不动。\n"
                       "回游戏在地图界面点「升级」按钮，\n"
                       "点几次升几级（一次一级），节奏自己控。\n"
                       "（89 级升满 155 一共要 19.95 亿）"
                       % (game.ACTOR_EXP_FILL / 1e8))
        btn_fill.pack(side="left", padx=6)
        fit_btn(bar, "回满 HP/MP",
                   lambda: self.actor_preset("heal")).pack(side="left",
                                                            padx=6)
        fit_btn(bar, "属性全 +10",
                   lambda: self.actor_preset("attr")).pack(side="left",
                                                            padx=6)
        # 「重置加点」= 洗点，复刻游戏里「拜师」那一下（语义层
        # game.actor_reset_attr → 脚本 `Game_Actor_Attr#reset_point`）：
        # 五维回到 20+等级-1、潜能回到 等级*5，已分配的点全部退回潜能。
        # ⚠ 和上面几个一样**并进这一行**（不新起一行）—— 左栏是竖向 pack，
        #   多一行就多一分被裁的风险（参考「一键学习」被裁那次）。
        btn_reset = fit_btn(bar, "重置加点",
                               lambda: self.actor_preset("reset_attr"))
        self._bind_tip(btn_reset,
                       "洗点：五维→20+等级-1，潜能→等级*5。\n"
                       "＝ 游戏里「拜师」那一下的效果。\n"
                       "已分配的点全部退回潜能，可重新分配。")
        btn_reset.pack(side="left", padx=(6, 0))

        # ---- 门派技能（勾选 = 学会 / 取消勾选 = 忘掉）
        # ⚠ 2026-09-23 改语义（川反馈：勾选/取消勾选之后点保存，工具却说「没有改动」）：
        #   勾选框原来只是「一键学习」的**输入** —— 勾了不点那个按钮 = 零效果，
        #   保存还会告诉你「没有改动」；已学的框还是 disabled，连“取消勾选”都点不动。
        #   现在改成**双向编辑器**：勾上立刻写 `@skills`、取消立刻删掉，点「保存修改」
        #   落盘；勾选状态 = 存档真值（见 rebuild_learn_grid / actor_toggle_sect_skill）。
        # 清单内容 = 上面「门派」下拉当前选中的那个门派（`$sects`，每门派 10 个，
        # 见 rebuild_learn_grid）→ 换门派就换清单；鼠标停在勾选框上弹技能介绍。
        # ⚠ 门派下拉**放这儿**，不再放右边技能区（2026-09-20 川反馈：右边也按门派筛
        #   等于和这份清单重复，右边技能一览该是「全部技能」）。
        # ⚠ 每多占一行就多一分被裁的风险（左栏是竖向 pack，先来先分）—— 能并到
        #   同一行就别新起一行。
        self.lf_learn = ttk.LabelFrame(left, text="门派技能", padding=6)
        self.lf_learn.pack(fill="x", pady=(4, 0))
        srow = ttk.Frame(self.lf_learn)
        srow.pack(fill="x")
        ttk.Label(srow, text="门派：").pack(side="left")
        # 初值空串 = 还没选门派（也没载入角色）；选中角色时会自动切到 TA 的门派
        self.var_actor_sect = tk.StringVar(value="")
        self.cb_actor_sect = ttk.Combobox(srow, textvariable=self.var_actor_sect,
                                          state="readonly", width=8,
                                          values=sect_choice_labels())
        self.cb_actor_sect.pack(side="left", padx=3)
        self.cb_actor_sect.bind("<<ComboboxSelected>>",
                                lambda e: self.rebuild_learn_grid())
        self._bind_tip(self.cb_actor_sect,
                       "只换下面这份「门派技能」清单，\n"
                       "右边的技能一览永远是全部技能。\n"
                       "选中角色时会自动切到 TA 的门派。")
        # ⚠ 「一键学习」**贴在门派下拉右边**（2026-09-20 川截图反馈：原来单独占
        #   一行放最底下，左栏高度不够时它会先被裁掉 —— 按钮就是看不见）。
        #   放同一行后它和下拉一起永远完整，也不再占一行高度。
        btn_learn = fit_btn(srow, text="一键学习",
                               command=self.actor_learn_checked)
        btn_learn.pack(side="left", padx=(6, 0))
        self._bind_tip(btn_learn, "把本门派还没学的技能一次学满\n"
                                  "（下面的勾选框会全部打上勾）。")
        # 「转门派」：把当前角色的门派改成**下拉里选的那个**（2026-09-27 加）。
        # ⚠ 故意**不**做成「下拉即改」——那个下拉的既定语义是「只换下面这份清单」，
        #   顺手改存档会在「只想看看别的门派技能」时把门派改掉。
        btn_sect = fit_btn(srow, text="转门派", command=self.actor_set_sect)
        btn_sect.pack(side="left", padx=(6, 0))
        self._bind_tip(btn_sect, "把当前角色的门派改成下拉里选的那个。\n"
                                 "只改门派本身（@sect_id）：\n"
                                 "已学技能、辅助/修炼、属性都不动。\n"
                                 "选「无门派」也是一样 —— 技能不动；\n"
                                 "要连技能一起重置，用「清空门派」。")
        # 「清空门派」：写 `@sect_id = 0` **并且**把技能重置成职业天生技能
        # （2026-09-27 川的要求）。⚠ 下拉里也有「无门派」，但两条路**不一样**：
        # 「转门派」只改门派（技能一个不动），连技能一起重置只有这个按钮
        # （川 260927 22:5x 明确：「无门派不清技能，清空门派才清技能」）。
        btn_nosect = fit_btn(srow, text="清空门派", command=self.actor_clear_sect)
        btn_nosect.pack(side="left", padx=(6, 0))
        self._bind_tip(btn_nosect, "把当前角色改成「无门派」（@sect_id=0），\n"
                                   "并把技能重置成职业天生技能。\n"
                                   "⚠ 游戏里快捷技能栏、门派技能页会不可用；\n"
                                   "   门派技能和技能书学的技能都会没。")
        # ⚠ 统计和「反选 / 全不选」同一行（不新起一行）：左栏是竖向 pack，
        #   多一行就多一分被裁的风险（1080 窗宽下本来只差 43px）。
        #   「全选」不用加 —— 上面那个「一键学习」就是（没学的全学会）。
        nrow = ttk.Frame(self.lf_learn)
        nrow.pack(fill="x", pady=(2, 0))
        self.var_learn_note = tk.StringVar(value="")
        ttk.Label(nrow, textvariable=self.var_learn_note,
                  foreground="#8a8a8a", justify="left", wraplength=300
                  ).grid(row=0, column=0, sticky="w")
        b_none = fit_btn(nrow, text="全不选", command=self.actor_sect_none)
        b_none.grid(row=0, column=2, sticky="e", padx=(4, 0))
        self._bind_tip(b_none, "把本门派的技能全部忘掉（勾选框全取消）。\n"
                               "只动这一份清单里的技能，别的技能不碰。")
        b_inv = fit_btn(nrow, text="反选", command=self.actor_sect_invert)
        b_inv.grid(row=0, column=1, sticky="e", padx=(6, 0))
        self._bind_tip(b_inv, "把下面这份清单反过来：\n"
                              "已学的忘掉、没学的学会。")
        nrow.columnconfigure(0, weight=1)
        self.learn_grid = ttk.Frame(self.lf_learn)
        self.learn_grid.pack(fill="x", pady=(2, 0))
        self.learn_vars = {}        # 技能 id → IntVar(0/1)
        self._learn_sids = []       # 当前清单里的技能 id（按门派表顺序）
        self.rebuild_learn_grid()

        # ========== 右：属性概览 + 技能编辑（上下可拖） ==========
        right = ttk.Frame(mid)
        mid.add(right, weight=1)
        vp = ttk.Panedwindow(right, orient="vertical")
        vp.pack(fill="both", expand=True)

        ovf = ttk.LabelFrame(vp, text="属性概览", padding=8)
        vp.add(ovf, weight=1)
        # 满级提示做成悬浮说明（鼠标移到概览上就能看），不再占版面
        self._actor_tip_holder = ttk.Frame(ovf)
        self._actor_tip_holder.pack(fill="both", expand=True)
        # 属性概览：只读 Text + 滚动条。
        # ⚠ 必须显式给 width/height：tk.Text 默认 80x24 = 要 644x460 px，
        # 加上下面技能区的 304 px，这一栏就要 806 px，而整页只有 ~563 px 可用
        # → 技能区会被裁掉（2026-09-20 量出来的）。这里只影响**请求尺寸**，
        # 实际大小仍由 pack 的 fill 决定。
        self.txt_actor = tk.Text(self._actor_tip_holder, wrap="word",
                                 width=46, height=9,
                                 font=("Microsoft YaHei UI", 10))
        vs_ta = ttk.Scrollbar(self._actor_tip_holder, orient="vertical",
                              command=self.txt_actor.yview)
        self.txt_actor.configure(yscrollcommand=vs_ta.set)
        vs_ta.pack(side="right", fill="y")
        self.txt_actor.pack(fill="both", expand=True)
        # 鼠标移到概览上 → 浮窗给出「满级 / 经验封顶 / 升级还差多少」这类提醒
        self.txt_actor.bind("<Motion>", self._actor_tip_motion)
        self.txt_actor.bind("<Leave>", lambda e: self._tip_hide())

        # ---- 技能（可编辑）：和召唤兽页同一套控件，列**全部技能**
        # ⚠ 角色技能**没有数量上限**（`Game_Actor#learn_skill` 只去重 + 排序；
        # 只有召唤兽 `Game_Baby#learn_skill` 才卡 12 个），所以不拦上限。
        # 按门派筛的那份清单在左栏「门派技能」（门派**不是** Data 表，
        # 是脚本里的 `$sects`，见 sect）。
        skf = ttk.LabelFrame(vp, text="技能（存档 @skills，无数量上限）", padding=8)
        vp.add(skf, weight=1)
        self._build_skill_editor(skf, "actor", list_height=6)

        # 初始把左右分隔条放中间；上下的分隔条按**内容需要**给：
        # 技能区是「搜索 + 一排按钮 + 列表 + 说明」，没有滚动条，压一点就缺一块；
        # 概览是只读 Text（自带滚动条）→ 空间不够就挤它。
        # ⚠ 不能用 root.after(150) 硬算：角色页不是默认页签，没显示的时候控件
        # 宽高都还是 1，算出来宽度 0 → 分栏被压扁。等它第一次真被布局
        # （<Configure>）再设；高度变了（用户拉窗口）重新夹一次。
        def _init_actor_sash(_e=None):
            w = mid.winfo_width()
            if w >= 200 and not getattr(self, "_actor_sash_done", False):
                self._actor_sash_done = True
                try:
                    mid.sashpos(0, w // 2)
                except Exception:
                    pass
            h = vp.winfo_height()
            if h < 120 or h == getattr(self, "_actor_sash_h", None):
                return                  # 没落位 / 高度没变（用户在拖 sash）→ 不抢
            self._actor_sash_h = h
            try:
                vp.sashpos(0, actor_sash_pos(h, skf.winfo_reqheight()))
            except Exception:
                pass
        mid.bind("<Configure>", _init_actor_sash)
        vp.bind("<Configure>", _init_actor_sash)

    # -------------------------------------------------- 4 队伍 / 物品
    def _tab_party(self):
        tk, ttk = self.tk, self.ttk
        f = ttk.Frame(self.nb, padding=8)
        self.tab_party = f
        self.nb.add(f, text="背包 / 物品")

        self.var_party = tk.StringVar()
        ttk.Label(f, textvariable=self.var_party, font=("Microsoft YaHei UI", 10)
                  ).pack(anchor="w", pady=(0, 6))

        bar = ttk.Frame(f)
        bar.pack(fill="x")
        ttk.Label(bar, text="背包页：").pack(side="left")
        self.var_bag_page = tk.IntVar(value=0)
        for p in range(game.MAX_PACK_PAGE):
            ttk.Radiobutton(bar, text="背包%d" % (p + 1), value=p,
                            variable=self.var_bag_page,
                            command=self.fill_party).pack(side="left", padx=2)
        ttk.Label(bar, text="　种类：").pack(side="left")
        self.var_bag_kind = tk.StringVar(value="Items")
        for key, _iv, cn, _db in game.KINDS:
            ttk.Radiobutton(bar, text=cn, value=key,
                            variable=self.var_bag_kind,
                            command=self.fill_party).pack(side="left", padx=2)
        fit_btn(bar, text="刷新", command=self.fill_party).pack(side="right")

        ttk.Label(f, text="每页 20 格（槽号 = 页*20 + 格）；左键选格子"
                          "（Ctrl 点选 / Shift 连选＝一次改一批），"
                          "右边模板里双击物品＝写进去"
                  ).pack(anchor="w", pady=(6, 2))

        body = ttk.Panedwindow(f, orient="horizontal")
        body.pack(fill="both", expand=True)

        # ---- 左：格子列表
        left = ttk.Frame(body)
        # ---- 搜索行（2026-10-04 川：跟召唤兽一览一样，格子也得能搜）
        # 只在有输入时过滤；空关键词照旧列满 20 格（含空格子），
        # 因为「往哪个空格子放东西」本身也要看着格子编号点。
        srow = ttk.Frame(left)
        srow.pack(fill="x")
        ttk.Label(srow, text="搜索：").pack(side="left")
        self.var_pack_kw = tk.StringVar()
        ent_pk = ttk.Entry(srow, textvariable=self.var_pack_kw, width=14)
        ent_pk.pack(side="left", padx=4)
        ent_pk.bind("<KeyRelease>", lambda e: self.fill_party())
        fit_btn(srow, text="清空", command=self.pack_kw_clear).pack(side="left")
        ttk.Label(left, text="背包格子（“内容”列是孵化蛋/礼包那种运行时内容；"
                             "鼠标停在物品上可看完整说明）"
                  ).pack(anchor="w")
        cols = ("slot", "idx", "id", "name", "count", "content")
        # ⚠ selectmode 显式写出来：默认就是 extended，但背包各按钮都靠它多选
        #   （2026-10-07 修了「多选只改第一个」的 bug，别哪天被改成 browse）。
        self.tv_pack = ttk.Treeview(left, columns=cols, show="headings",
                                    height=14, selectmode="extended")
        for c, w, t in (("slot", 55, "槽号"), ("idx", 45, "格"),
                        ("id", 60, "物品ID"), ("name", 190, "名称"),
                        ("count", 50, "数量"), ("content", 210, "内容")):
            self.tv_pack.heading(c, text=t)
            self.tv_pack.column(c, width=w, anchor="w")
        vs = ttk.Scrollbar(left, orient="vertical", command=self.tv_pack.yview)
        self.tv_pack.configure(yscrollcommand=vs.set)
        vs.pack(side="right", fill="y")
        self.tv_pack.pack(fill="both", expand=True)
        self.tv_pack.bind("<<TreeviewSelect>>", lambda e: self.bag_pick())
        self.tv_pack.bind("<Double-1>", lambda e: self.bag_edit())
        self.tv_pack.bind("<Motion>", self._bag_tip_motion, add="")
        self.tv_pack.bind("<Leave>", self._tip_hide, add="")
        body.add(left, weight=3)

        # ---- 右：物品模板（从 Data 表读，画迹1 也有这一栏）
        right = ttk.Frame(body)
        tr = ttk.Frame(right)
        tr.pack(fill="x")
        ttk.Label(tr, text="找物品：").pack(side="left")
        self.var_tpl_kw = tk.StringVar()
        ent = ttk.Entry(tr, textvariable=self.var_tpl_kw, width=16)
        ent.pack(side="left")
        ent.bind("<Return>", lambda e: self.fill_templates())
        fit_btn(tr, text="找", width=4,
                   command=self.fill_templates).pack(side="left", padx=3)
        ttk.Label(right, text="物品模板（Data\\%s.rvdata2）"
                  % "Items").pack(anchor="w")
        self.tv_tpl = ttk.Treeview(right, columns=("id", "name", "grp"),
                                   show="headings", height=11)
        # ⚠ 只让「名称」列 stretch：多余宽度全摊给它会撑出一段空白（同技能管理器）。
        for c, w, t in (("id", 52, "ID"), ("name", 170, "名称"),
                        ("grp", 88, "类别")):
            self.tv_tpl.heading(c, text=t)
            self.tv_tpl.column(c, width=w, anchor="w", stretch=(c == "name"))
        vs2 = ttk.Scrollbar(right, orient="vertical", command=self.tv_tpl.yview)
        self.tv_tpl.configure(yscrollcommand=vs2.set)
        vs2.pack(side="right", fill="y")
        self.tv_tpl.pack(fill="both", expand=True)
        self.tv_tpl.bind("<Double-1>", lambda e: self.bag_use_template())
        self.tv_tpl.bind("<Motion>", self._tpl_tip_motion, add="")
        self.tv_tpl.bind("<Leave>", self._tip_hide, add="")
        self.var_tpl_note = tk.StringVar(value="")
        ttk.Label(right, textvariable=self.var_tpl_note, foreground="#555",
                  wraplength=300, justify="left").pack(anchor="w", pady=2)
        fit_btn(right, text="写入选中的格子（双击模板也行）",
                   command=self.bag_use_template).pack(fill="x", pady=2)
        fit_btn(right, text="放进第一个空格子",
                   command=lambda: self.bag_use_template(False)).pack(fill="x")
        body.add(right, weight=2)

        act = ttk.Frame(f)
        act.pack(fill="x", pady=4)
        ttk.Label(act, text="物品 id：").pack(side="left")
        self.var_bag_id = tk.StringVar()
        ttk.Entry(act, textvariable=self.var_bag_id, width=8).pack(side="left")
        ttk.Label(act, text="数量：").pack(side="left", padx=(8, 0))
        self.var_bag_cnt = tk.StringVar(value="1")
        ttk.Entry(act, textvariable=self.var_bag_cnt, width=6).pack(side="left")
        fit_btn(act, text="改数量",
                   command=self.bag_set_count).pack(side="left", padx=6)
        fit_btn(act, text="按 id 写入",
                   command=self.bag_add).pack(side="left", padx=6)
        fit_btn(act, text="清空格子",
                   command=self.bag_clear).pack(side="left", padx=6)
        fit_btn(act, text="本页全部 99",
                   command=lambda: self.bag_all(99)).pack(side="left", padx=6)
        fit_btn(act, text="背包体检",
                   command=self.bag_check).pack(side="left", padx=6)
        fit_btn(act, text="一键修复",
                   command=self.bag_fix).pack(side="left", padx=6)
        fit_btn(act, text="同步计数校验",
                   command=self.guard_resync).pack(side="left", padx=6)

        pay = ttk.Frame(f)
        pay.pack(fill="x")
        self.var_bag_kid = tk.StringVar()
        b_pay = fit_btn(pay, text="重抽管理",
                        command=self.open_payload_manager)
        b_pay.pack(side="left")
        self._bind_tip(b_pay, "给选中的格子换「运行时内容」（孵化蛋孵出哪只、\n"
                              "要诀开出什么技能、元宵涨哪项资质…）。\n"
                              "开独立窗口：按选中物品**自动适配**，列出能挑的\n"
                              "候选（蛋→该蛋的兽池、要诀→该档技能池），选一个\n"
                              "应用到所有选中的格子；不挑就按游戏规则重抽。\n"
                              "Ctrl 点选 / Shift 连选 = 一次改一批。")
        fit_btn(pay, text="随机重抽",
                command=self.bag_reroll).pack(side="left", padx=6)
        ttk.Label(pay, text="孵出/开出对象 id（写入或随机重抽时用，留空＝随机）："
                  ).pack(side="left")
        ttk.Entry(pay, textvariable=self.var_bag_kid, width=8).pack(side="left")
        ttk.Label(pay, text="　（召唤兽 id 看 Data\\Actors）",
                  foreground="#777").pack(side="left")
        self.var_bag_pay = tk.StringVar(value="")
        ttk.Label(f, textvariable=self.var_bag_pay, foreground="#a33",
                  justify="left", wraplength=1150).pack(anchor="w")

        self.var_bag_note = tk.StringVar(value="")
        ttk.Label(f, textvariable=self.var_bag_note, foreground="#555",
                  justify="left", wraplength=1150).pack(anchor="w")

    # -------------------------------------------------- 4.5 召唤兽
    def _tab_baby(self):
        tk, ttk = self.tk, self.ttk
        f = ttk.Frame(self.nb, padding=8)
        self.tab_baby = f
        self.nb.add(f, text="召唤兽")

        top = ttk.Frame(f)
        top.pack(fill="x")
        ttk.Label(top, text="角色：").pack(side="left")
        self.var_baby_actor = tk.StringVar()
        self.cb_baby_actor = ttk.Combobox(top, textvariable=self.var_baby_actor,
                                          state="readonly", width=22)
        self.cb_baby_actor.pack(side="left")
        self.cb_baby_actor.bind("<<ComboboxSelected>>",
                                lambda e: self.fill_baby_list())
        fit_btn(top, text="新增召唤兽",
                   command=self.baby_add_dialog).pack(side="left", padx=(10, 4))
        fit_btn(top, text="设为出战",
                   command=self.baby_set_active).pack(side="left")
        b_del = fit_btn(top, text="放生（删除）",
                        command=self.baby_delete)
        b_del.pack(side="left", padx=4)
        self._bind_tip(b_del, "把列表里选中的召唤兽从这只角色身上删掉。\n"
                              "Ctrl 点选 / Shift 连选 → 一次删一批；\n"
                              "预设 / 恢复模板名 / 重置加点 / 改字段 也作用于\n"
                              "全部选中项（改名、设为出战、克隆只认第一个）。\n"
                              "不可撤销：删了只能重新加一只。")
        fit_btn(top, text="恢复模板名",
                   command=self.baby_restore_name).pack(side="left")
        # 宠物「重置加点」= 洗点（游戏里没有这个功能，语义见
        # game.baby_reset_attr：自己加的属性点全部退回潜能，五维回到自然成长量）。
        # ⚠ 放这一行、不放下面那排预设 —— 预设行已经有 8 个按钮，再加一个会被
        #   pack 切掉（Tk 的 pack 先来先分，空间不够切的是最后 pack 的）。
        btn_breset = fit_btn(top, text="重置加点",
                                command=lambda: self.baby_preset("reset_attr"))
        btn_breset.pack(side="left", padx=(8, 0))
        self._bind_tip(btn_breset, "洗点：自己加的属性点全部退回潜能，\n"
                                   "五维回到「10+等级+出生掷点」的自然量。\n"
                                   "总点数不变（五维和+潜能守恒）→ 战力不变，\n"
                                   "只是让你能在游戏里重新分配。")

        # ---- 搜索行（2026-10-04 川：召唤兽一多，一览表得能搜）
        # ⚠ 单独一行、不挤上面那排按钮 —— 那排已经有 7 个控件，1080 窗宽下再加
        #   输入框会被 pack 切掉（空间不够先切最后 pack 的）。
        srow = ttk.Frame(f)
        srow.pack(fill="x", pady=(4, 0))
        ttk.Label(srow, text="搜索：").pack(side="left")
        self.var_baby_kw = tk.StringVar()
        ent_bk = ttk.Entry(srow, textvariable=self.var_baby_kw, width=18)
        ent_bk.pack(side="left", padx=4)
        ent_bk.bind("<KeyRelease>", lambda e: self.fill_baby_list())
        fit_btn(srow, text="清空", command=self.baby_kw_clear).pack(side="left")
        ttk.Label(srow, text="（名字 / 模板 / 序号 / 模板 id；留空＝全列）",
                  foreground="#888").pack(side="left", padx=6)

        self.var_baby_note = tk.StringVar(value="")
        # ⚠ wraplength 别写死 1180：默认窗口才 1220 宽、川还常缩到 ~1080，写太大会
        #   让这行提示横着溢出被裁。1000 在最小窗宽下也能完整折行。
        ttk.Label(f, textvariable=self.var_baby_note, foreground="#555",
                  justify="left", wraplength=1000).pack(anchor="w", pady=(4, 4))

        # ---------------- 召唤兽列表（画迹1 那种一览）
        # ⚠ 2026-09-27：在「成长」左边插了一列「五行」（`@attr.@five`）。
        #   加列时 cols / heads / widths 三个元组要同步加，少一个会整表错位。
        cols = ("no", "name", "tpl", "lv", "five", "grow", "loyal", "life",
                "atk", "def", "hp", "mp", "agi", "eva", "sk", "act")
        heads = ("序", "名字", "模板", "等级", "五行", "成长", "忠诚", "寿命",
                 "攻资", "防资", "体资", "法资", "速资", "躲资", "技能", "出战")
        widths = (34, 104, 108, 50, 44, 54, 54, 66, 60, 60, 60, 60, 60, 60, 44, 44)
        # ⚠ selectmode="extended"（2026-10-04 川要求「多选删除」）：Ctrl 点选、
        #   Shift 连选，一次放生一批。别的按钮（设为出战 / 改字段 / 技能）只认
        #   「第一个选中项」（见 `_baby()`），多选不影响它们。
        # ⚠ 竖滚动条必须和列表装进**同一个子 frame**（2026-10-04 川截图反馈：
        #   原来直接 pack 进整页 `f`，`side="right" + fill="y"` 会让它撑满整页高、
        #   贴在窗口最右边 —— 看着像"整个窗口的滚动条"，离 6 行高的列表老远，
        #   也长得离谱）。Tk 的 pack 是"先来先分地盘"：先 pack 的 side="right"
        #   拿的是**整块**右边缘，所以必须先把容器缩到只有列表那么高。
        #   ⚠ 顺序也别动：子 frame 里先 pack 滚动条（side="right"）再 pack 列表。
        bw = ttk.Frame(f)
        bw.pack(fill="x")
        # ⚠⚠ `Treeview` 的 parent 必须是 `bw`：Tk 的 `widget.pack()` **永远 pack 到
        #   控件自己的 parent**，不是"最近 pack 过的那个 frame"。2026-10-04 就是
        #   在这儿写错的 —— 父仍是 `f` 却 `pack(side="left")`，一览表于是抢走整页
        #   左边缘（顶到窗口底），把横滚动条 / 改字段行 / 字段表全挤成右边一条。
        self.tv_babies = ttk.Treeview(bw, columns=cols, show="headings",
                                      height=6, selectmode="extended")
        for c, h, w in zip(cols, heads, widths):
            self.tv_babies.heading(c, text=h)
            self.tv_babies.column(c, width=w, anchor="w")
        self.tv_babies.tag_configure("active", foreground="#0a0")
        vs_bab = ttk.Scrollbar(bw, orient="vertical",
                               command=self.tv_babies.yview)
        self.tv_babies.configure(yscrollcommand=vs_bab.set)
        hs = ttk.Scrollbar(f, orient="horizontal", command=self.tv_babies.xview)
        self.tv_babies.configure(xscrollcommand=hs.set)
        vs_bab.pack(side="right", fill="y")
        self.tv_babies.pack(side="left", fill="x", expand=True)
        hs.pack(fill="x")
        self.tv_babies.bind("<<TreeviewSelect>>", lambda e: self.on_baby_select())

        edit = ttk.Frame(f)
        edit.pack(fill="x", pady=(6, 0))
        ttk.Label(edit, text="改字段：").pack(side="left")
        self.var_baby_key = tk.StringVar()
        ttk.Entry(edit, textvariable=self.var_baby_key, width=12,
                  state="readonly").pack(side="left")
        # 值的控件有两个，**叠在同一格**、共用 self.var_baby_val，按字段类型切：
        #   普通字段 → 数字输入框；五行（`five`，存档里是 Marshal String）→ 只读下拉。
        # 2026-09-27 加五行：以前只有一个数字输入框，五行是字符串，手敲很容易
        # 打成不存在的字（游戏按 sample 的 5 个值比，别的字等于没吃五行），
        # 所以给它一个只能选的下拉。切换在 _sync_baby_val_widget()。
        self.var_baby_val = tk.StringVar()
        val_wrap = ttk.Frame(edit)
        val_wrap.pack(side="left", padx=(4, 0))
        self.ent_baby_val = ttk.Entry(val_wrap, textvariable=self.var_baby_val,
                                      width=14)
        self.ent_baby_val.grid(row=0, column=0, sticky="w")
        self.cb_baby_val = ttk.Combobox(val_wrap, textvariable=self.var_baby_val,
                                        values=list(game.BABY_FIVE), width=12,
                                        state="readonly")
        self.cb_baby_val.grid(row=0, column=0, sticky="w")
        self.cb_baby_val.grid_remove()          # 默认是数字输入框
        fit_btn(edit, "应用", self.apply_baby).pack(side="left", padx=6)
        # ⚠ 「满级(65)」按钮没了（2026-09-20 去掉所有页签的等级修改）：
        # 2026-10-03 起，这个"连等级一起写"的按钮统一叫「一键满级」
        # （角色页同款，见 game.baby_exp_full）。
        # 2026-10-03 川要求：①加「经验拉满」（只给 @exp、等级不动，同角色页）；
        #   ②老「回满气血/魔法」+「全员忠诚满」合并＝「全员状态拉满」
        #   （一次把全体召唤兽的气血/魔法/愤怒回满 + 忠诚拉满）。
        tips = {
            "expfull": ("一键满级：等级给到 %d 级 + 经验对齐该级门槛。\n"
                        "⚠ 召唤兽靠经验最多升到「主人等级+10」，\n"
                        "所以这里直接把等级写满，不再单独给等级输入框。"
                        % game.MAX_LEVEL_BABY),
            "expfill": ("获得经验写到 %.2f 亿，等级不动。\n"
                        "⚠ 和人物不同：召唤兽自己有升级循环，\n"
                        "打完下一场战斗结算时它会自己连升\n"
                        "（顶到「主人等级+10」）。"
                        % (game.BABY_EXP_FILL / 1e8)),
            "state_all": ("一次把「所有角色」身上的「所有召唤兽」：\n"
                          "气血/魔法/愤怒 回满 + 忠诚拉到 %d。\n"
                          "忠诚只决定能不能参战（<%d 不能上），\n"
                          "没有属性加成，也不会触发作弊检测。\n"
                          "上限 %d 是游戏规定：写更高，打完一场战斗\n"
                          "结束时会被游戏自己夹回去。"
                          % (game.MAX_BABY_LOYALTY,
                             game.BABY_ALLOW_LOYALTY,
                             game.MAX_BABY_LOYALTY)),
        }
        # ---------------- 进阶（2026-10-08 川报「用了圣兽之心资质/成长没突破」）
        # 游戏侧「进阶」只做一件事：`Game_Baby_Attr#promote=(v)` → `@promote = v`
        # —— **一个资质数字都不动**，抬的是**上限**（`$baby[:_max]`，见
        # tables/baby_aptitude.MAX_ATTR）：神兽 1900/1900/7000/4000/1.6 →
        # 神兽_p 2000/2000/7200/4200/1.8。所以光进阶，面板数字纹丝不动
        # （面板画的是 `min(存档值, 上限)`，blob:78735）—— 川的「进阶前/后
        # 两张图数值一模一样」就是这个，不是 bug。于是并排两个：
        #   「进阶」    = 游戏那一步（进游戏后还能再吃元宵长上去）
        #   「进阶并拉满」= 进阶 + 六项资质/成长直接写到进阶后的上限
        #                （游戏里没有一步到位的道具，得回头把元宵吃满）
        # ⚠ 放在**这一行**（不另起一行）：默认 1220x800 下面板右侧的
        #   「常用 / 详细信息」本来就被切 20px，再加一行会到 51px
        #   （`备注` 那个 2 行 Text 会被切）—— 实测见 probe_baby_layout。
        #   本行在 1080 窗宽下还有 149px 余量，塞得下。
        tips.update({
            "promote": ("进阶（= 游戏里用进阶道具 / 勾召唤兽面板那个「进阶」框）。\n"
                        "⚠ 进阶**只抬资质上限**，一个数字都不动：\n"
                        "神兽 1900/1900/7000/4000/2100/2100/1.6\n"
                        "→ 神兽_p 2000/2000/7200/4200/2200/2200/1.8\n"
                        "面板显示的一直是 min(存档值, 上限)，所以光进阶\n"
                        "看不出变化 —— 数字得自己长（吃元宵），\n"
                        "或者直接用旁边的「进阶并拉满」。\n"
                        "顺带：立绘换成进阶形态、可食元宵次数上限也涨。"),
            "promote_fill": ("进阶 + 把六项资质和成长**直接写到进阶后的上限**：\n"
                             "神兽 → 2000/2000/7200/4200/2200/2200、成长 1.8\n"
                             "普通 → 1700/1700/6650/3750/1900/1900、成长 1.5\n"
                             "（泡泡灵仙进阶前后上限相同，只有立绘变）\n"
                             "⚠ 只能到上限为止：写更高游戏里也显示不出来\n"
                             "（读值一律 min(存档值, 上限)）。\n"
                             "⚠ 图鉴里没有进阶形象的（如恶魔泡泡 215）会跳过。"),
        })
        for txt, what in (("一键满级", "expfull"), ("经验拉满", "expfill"),
                          ("全员状态拉满", "state_all"), ("寿命满", "life"),
                          ("六项资质+100", "qual"), ("六项资质+500", "qual500"),
                          ("成长+0.1", "grow"), ("五维+10", "five10"),
                          ("进阶", "promote"), ("进阶并拉满", "promote_fill")):
            b = fit_btn(edit, txt, lambda w=what: self.baby_preset(w))
            b.pack(side="left", padx=2)
            if tips.get(what):
                self._bind_tip(b, tips[what])

        mid = ttk.Frame(f)
        mid.pack(fill="both", expand=True, pady=(6, 0))
        left = ttk.Frame(mid)
        left.pack(side="left", fill="both")
        right = ttk.Frame(mid)
        right.pack(side="left", fill="both", expand=True, padx=(8, 0))
        cols2 = ("k", "v")
        self.tv_baby = ttk.Treeview(left, columns=cols2, show="headings", height=12)
        # 字段列要能显示长标签（如「忠诚度（<100 不能参战）」），当前值多为短数字
        for c, w, t in (("k", 170, "字段"), ("v", 110, "当前值")):
            self.tv_baby.heading(c, text=t)
            self.tv_baby.column(c, width=w, anchor="w")
        vs_baby = ttk.Scrollbar(left, orient="vertical", command=self.tv_baby.yview)
        self.tv_baby.configure(yscrollcommand=vs_baby.set)
        vs_baby.pack(side="right", fill="y")
        self.tv_baby.pack(fill="both", expand=True)
        self.tv_baby.bind("<<TreeviewSelect>>", lambda e: self.baby_pick())

        # ---------------- 常用（名字+技能）/ 详细信息（2 列：2/3 vs 1/3）
        commonf = ttk.LabelFrame(right, text="常用", padding=6)
        commonf.grid(row=0, column=0, sticky="nsew", padx=(0, 4))

        # ---- 名字
        name_row = ttk.Frame(commonf)
        name_row.pack(fill="x")
        ttk.Label(name_row, text="名字：").pack(side="left")
        self.var_baby_name = tk.StringVar()
        ttk.Entry(name_row, textvariable=self.var_baby_name, width=16).pack(side="left")
        fit_btn(name_row, text="改显示名",
                   command=self.baby_rename).pack(side="left", padx=3)

        # ---- 技能（和角色页同一套控件，见 _build_skill_editor）
        ttk.Label(commonf, text="技能：").pack(anchor="w", pady=(6, 0))
        self._build_skill_editor(commonf, "baby", list_height=8)

        # ---- 详细信息
        infof = ttk.LabelFrame(right, text="详细信息", padding=6)
        infof.grid(row=0, column=1, sticky="nsew", padx=(4, 0))
        # ⚠ `tk.Text` 必须显式给 width（项目铁律）：不给的话 Tk 按 80 字符算请求宽
        #   （≈660px），会把「常用 / 详细信息」那行顶到 1332 px —— 页 frame 的请求宽
        #   虚高、窄窗口下整块被挤。实际显示宽由 grid 决定，这里只压请求宽。
        self.txt_baby = tk.Text(infof, height=2, width=30, wrap="word",
                                relief="flat", highlightthickness=1,
                                highlightbackground="#ddd",
                                font=("Microsoft YaHei UI", 10))
        self.txt_baby.pack(fill="both", expand=True)

        right.columnconfigure(0, weight=1, uniform="col")
        right.columnconfigure(1, weight=1, uniform="col")

    def fill_babies(self):
        """刷角色下拉框（召唤兽列表依赖它）。"""
        if not self.sv or self.g is None:
            self.cb_baby_actor["values"] = []
            return
        names = []
        for aid, a in self.sv.actors():
            names.append("%s (#%d)" % (self.sv.actor_name(a) or "?", aid))
        self.cb_baby_actor["values"] = names
        if names and self.var_baby_actor.get() not in names:
            self.var_baby_actor.set(names[0])
        self.fill_baby_list()

    def _baby_actor(self):
        sel = self.var_baby_actor.get()
        if not sel or not self.sv:
            return None
        try:
            aid = int(sel.split("#")[-1].rstrip(")"))
        except ValueError:
            return None
        for a_id, a in self.sv.actors():
            if a_id == aid:
                return a
        return None

    def babies_ed(self):
        """召唤兽助手（babies.Babies）——换存档后重建一次。"""
        if getattr(self, "_babies_src", None) is not self.g or not hasattr(
                self, "_babies_obj"):
            self._babies_obj = babies.Babies(self.g) if self.g is not None \
                else None
            self._babies_src = self.g
        return self._babies_obj

    @staticmethod
    def _life_text(v):
        if v == "infinite":
            return "永生"
        return "" if v is None else v

    @staticmethod
    def _baby_hit(kw, i, name, tpl, tpl_id):
        """召唤兽搜索匹配：名字 / 模板名 / 模板 id / 序号（1 起）都能搜。

        ⚠ 「序号」= 列表里那个 1 起的行号（`i + 1`），不是槽号 —— 参照背包
          格子那边的 `slot`，它是一眼能看到的那个数。
        """
        if not kw:
            return True
        for s in (name, tpl, str(tpl_id), str(i + 1), "#%d" % tpl_id):
            if s and kw in s:
                return True
        return False

    def baby_kw_clear(self):
        """清空召唤兽搜索框并重列。"""
        self.var_baby_kw.set("")
        self.fill_baby_list()

    def fill_baby_list(self):
        """刷召唤兽列表（画迹1 那种一览表）。"""
        self.baby_rows = []
        self.tv_babies.delete(*self.tv_babies.get_children())
        a = self._baby_actor()
        bd = self.babies_ed()
        if a is None or self.g is None or bd is None:
            self.var_baby_note.set("")
            return
        self.baby_rows = self.g.babies(a)
        act_i = bd.active_index(a)
        # 关键词过滤（2026-10-04 川）：只影响**列出来的行**，`baby_rows` 仍是全量
        # —— `_baby()` / `refresh_baby_list_keep()` 都按原始下标找，不能让筛选改下标。
        kw = (self.var_baby_kw.get() if hasattr(self, "var_baby_kw")
              else "").strip()
        n_hit = 0
        for i, b in self.baby_rows:
            def v(k, _b=b):
                return self.g.baby_value(_b, k)
            nm = self.g.baby_name(b)
            tpl = bd.template_name(b)
            tpl_id = _IV.ival(b, "@actor_id")
            if not self._baby_hit(kw, i, nm, tpl, tpl_id):
                continue
            n_hit += 1
            tags = ("active",) if i == act_i else ()
            self.tv_babies.insert(
                "", "end", iid="bb%d" % i,
                values=("%d" % (i + 1), nm,
                        "%s(%s)" % (tpl, tpl_id),
                        v("level"), v("five"), v("grow"), v("loyalty"),
                        self._life_text(v("life")),
                        v("atk"), v("def"), v("hpq"), v("mpq"), v("agi"), v("eva"),
                        len(bd.skills(b)), "★" if i == act_i else ""),
                tags=tags)
        # ⚠ 这行是 `ttk.Label`，**不认 Markdown**：`**粗体**` / `` `等宽` ``
        #   会原样显示成星号、反引号（2026-10-04 川截图里就是「拿不到的**小孩**」）。
        #   所以提示文案里一律不用标记，要强调就靠「」和换行。
        self.var_baby_note.set(
            ("匹配 %d / 共 %d 只" % (n_hit, len(self.baby_rows)) if kw
             else "共 %d 只" % len(self.baby_rows))
            + "（★ = 当前出战）；「新增召唤兽」可加任意一种，含正常玩法"
              "拿不到的小孩（小精灵～小丫丫，属「神兽资质3」池，"
              "只有「珍藏神兽蛋」能开出 179~186）。")
        kids = self.tv_babies.get_children()
        if kids:
            self.tv_babies.selection_set(kids[0])
            self.on_baby_select()
        else:
            self.load_baby()

    def on_baby_select(self):
        self.load_baby()

    def refresh_baby_list_keep(self, baby):
        """刷列表，但“选中”还是原来那些（单只或一串都给；不然会跳回第一行）。"""
        want = baby if isinstance(baby, (list, tuple, set)) else [baby]
        idx = [k for k, x in self.baby_rows if any(x is w for w in want)]
        self.fill_baby_list()
        keep = ["bb%d" % k for k in idx]
        keep = [i for i in keep if self.tv_babies.exists(i)]
        if not keep:
            return
        try:
            self.tv_babies.selection_set(keep)
            self.on_baby_select()
        except Exception:
            pass

    def _baby(self):
        sel = self.tv_babies.selection()
        if not sel:
            return None
        i = int(sel[0][2:])
        for k, b in self.baby_rows:
            if k == i:
                return b
        return None

    def _baby_sel(self):
        """列表里选中的**全部**召唤兽 `[(下标, 节点)]`（按行序）。

        ⚠ 2026-10-07 川：`tv_babies` 一直能多选，但预设 / 恢复模板名 / 改字段
          都只认 `_baby()`（第一个选中项）—— 改成走这里整批处理。
        """
        out = []
        for iid in self.tv_babies.selection():
            try:
                i = int(iid[2:])
            except ValueError:
                continue
            for k, b in self.baby_rows:
                if k == i:
                    out.append((i, b))
                    break
        return out

    def load_baby(self):
        b = self._baby()
        self.tv_baby.delete(*self.tv_baby.get_children())
        self.tv_baby_skills.delete(*self.tv_baby_skills.get_children())
        self.txt_baby.delete("1.0", "end")
        self.var_baby_name.set("")
        if b is None or self.g is None:
            return
        bd = self.babies_ed()
        for key, label, _path, _t in game.GameEditor.BABY_FIELDS:
            if key == "level":
                # ⚠ 等级不再单独改（2026-09-20 川要求去掉所有页签的等级修改）。
                # 字段还在 BABY_FIELDS 里（set_baby / baby_value 还要用），
                # 只是不进这张「可改字段」表；等级去左边「一键满级」一起写。
                continue
            v = self.g.baby_value(b, key)
            if key == "life":
                v = self._life_text(v)
            self.tv_baby.insert("", "end", iid="b_%s" % key,
                                values=(label, "" if v is None else v))
        sk = self.g.baby_skills(b)
        tpl_id = _IV.ival(b, "@actor_id")
        idx = [k for k, x in self.baby_rows if x is b]
        meta = self._skills_meta()
        self.skp_baby.set_source([(sid, meta.get(sid, ("?", ""))[0])
                                  for sid in bd.skills(b)])
        self.var_baby_name.set(bd.display_name(b))
        self.skp_baby.fill()
        self.txt_baby.insert("1.0", "\n".join([
            "第 %d 只：%s（模板 %s #%d，%s）　等级 %s / 忠诚 %s / 寿命 %s / 成长 %s"
            % (idx[0] if idx else -1, bd.display_name(b), bd.template_name(b),
               tpl_id, bd.type_of(tpl_id) or "普通",
               self.g.baby_value(b, "level"), self.g.baby_value(b, "loyalty"),
               self._life_text(self.g.baby_value(b, "life")),
               self.g.baby_value(b, "grow")),
            "已学技能：%s" % ("、".join("#%d %s" % (i, n) for i, n in sk) or "（无）"),
            "提示：内测版（V2.201）没有周期检查、也没有作弊标记，改数值不会被判作弊；"
            "召唤兽等级上限 165、五维参考上限＝等级×10+500。改完记得 Ctrl+S。",
            "等级不再单独改：用上面「一键满级」（等级给到 165 + 经验对齐），"
            "已学会的技能见「技能」区。",
        ]))
        kids = self.tv_baby.get_children()
        if kids:
            # 保持原来选中的那一行（不然「应用」完会跳回第一行）
            key = self.var_baby_key.get()
            keep = ("b_%s" % key) if key else ""
            iid = keep if keep and self.tv_baby.exists(keep) else kids[0]
            self.tv_baby.selection_set(iid)
            self.baby_pick()

    # -------------------------------------------------- 4.6 召唤兽：新增/删除/名字/技能
    def _skills_meta(self):
        """{技能 id: (名字, 描述)}（Data\\Skills 表，带缓存）。

        走 `datatables.skill_map()`：说明＝官方说明（解 `<S:N>`）**＋游戏浮窗
        里那几行**（状态详情 / 伤害 / 恢复量 / 目标数 / 攻击次数 / 消耗 / 冷却）
        —— 2026-10-04 川要「把附加的描述、耗蓝耗血补上」。
        读不到游戏目录会退回内置名字表，所以技能一览 / 说明框在"没放在游戏
        目录里"的机器上照样有内容（只是少那几行附加信息）。

        ⚠ 保留作者写的换行（原来把换行压成空格）：附加行本来就是一行一条，
          压掉就看不清哪行是哪条了。字面 `\n` / `\r\n` 的归一到
          `datatables.clean_desc()` 里统一做，这儿别再重复一遍。
        """
        if getattr(self, "_skill_meta", None) is None:
            meta = {}
            try:
                for i, (nm, desc) in datatables.skill_map().items():
                    meta[i] = (nm or "", (desc or "").strip())
            except Exception:
                meta = {}
            self._skill_meta = meta
        return self._skill_meta

    def _skill_names(self):
        return dict((i, nm) for i, (nm, _d) in self._skills_meta().items())

    def _build_skill_editor(self, parent, key, list_height=7, desc_height=3):
        """在 parent 里建一整块技能编辑控件，返回 SkillPicker。

        搜索框 + 一排按钮（技能管理… / 忘掉选中 / 清空 / 从…克隆）+ 技能一览
        + 说明框。2026-09-20 抽出来的：**角色页和召唤兽页共用这一套**（两边
        规则一模一样），以前这些控件和逻辑都只写在召唤兽页里。

        ⚠ 一览只列这个目标**已学**的技能（存档 `@skills` 顺序），搜索也只筛
          这一份。要学新技能、要批量操作，走「技能管理…」那个窗口。
          2026-10-04 之前这里还挂着一个"全部技能"只读下拉 + 「学会」按钮：
          下拉是另一个入口，搜索也只筛它、筛不到一览，两块语义混在一起。

        建的控件按 key 挂到 self 上（测试和别处引用用得上）：
          `tv_<key>_skills` / `var_<key>_skill_search` /
          `txt_<key>_skill_desc` / `skp_<key>`
        （`cb_<key>_skill` / `var_<key>_skill_pick` 随下拉一起去掉了。）
        四个按钮分别调 `<key>_skill_manager` / `_del` / `_clear` / `_clone`。
        """
        tk, ttk = self.tk, self.ttk
        row = ttk.Frame(parent)
        row.pack(fill="x")
        ttk.Label(row, text="搜索已学").pack(side="left")
        var_search = tk.StringVar()
        ent = ttk.Entry(row, textvariable=var_search, width=14)
        ent.pack(side="left", padx=3)
        self._bind_tip(ent, "只筛下面这份「已学」技能一览。\n"
                            "要搜全部技能（几千条里的任意一条）\n"
                            "用「技能管理…」。")

        # 按钮单独放一行（挤在搜索后面会把搜索框压没）
        btns = ttk.Frame(parent)
        btns.pack(fill="x", pady=(4, 0))
        b_mgr = fit_btn(btns, text="技能管理…",
                        command=getattr(self, "%s_skill_manager" % key))
        b_mgr.pack(side="left", padx=(0, 4))
        self._bind_tip(b_mgr, "开一个技能管理器窗口：\n"
                              "能搜全部技能、Ctrl/Shift 多选，\n"
                              "有全选 / 反选 / 全不选，批量学会或忘掉。")
        b_del = fit_btn(btns, text="忘掉选中",
                        command=getattr(self, "%s_skill_del" % key))
        b_del.pack(side="left")
        self._bind_tip(b_del, "忘掉一览里选中的技能\n"
                              "（Ctrl 点选、Shift 连选，可一次忘一批）。")
        b_clr = fit_btn(btns, text="清空",
                        command=getattr(self, "%s_skill_clear" % key))
        b_clr.pack(side="left", padx=4)
        b_clone = fit_btn(btns, text="从…克隆",
                          command=getattr(self, "%s_skill_clone" % key))
        b_clone.pack(side="left")

        # 技能一览只放 id + 名字，说明另外显示（描述太长塞进表格会看不全）
        body = ttk.Frame(parent)        # 先建、后 pack（pack 顺序见下面说明）
        # ⚠ selectmode="extended"（2026-10-04）：Ctrl / Shift 多选，
        #   「忘掉选中」一次一批。原来 browse 是单选，一次只能忘一个。
        tree = ttk.Treeview(body, columns=("no", "id", "name"), show="headings",
                            height=list_height, selectmode="extended")
        # 总宽保持 262px（原 62+200）："名字" 让 30px 给序号列，
        # 免得把角色页/召唤兽页的宽度需求顶上去（那两页以前就因为太宽被裁过）。
        for c, t2, w in (("no", "序", 34), ("id", "技能 id", 58),
                         ("name", "名字", 170)):
            tree.heading(c, text=t2)
            tree.column(c, width=w, anchor="center" if c == "no" else "w",
                        stretch=True)
        vs = ttk.Scrollbar(body, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vs.set)
        vs.pack(side="right", fill="y")
        tree.pack(side="left", fill="both", expand=True)

        # 说明用只读 Text（和「详细信息」同款），太长也能换行看全。
        # ⚠ 必须给 width/height：tk.Text 默认 80x24，光这一块就向几何管理器要
        # 566x460 px —— 两页都有这块说明，不设就直接把页签顶出窗口
        # （2026-09-20 实测：角色页因此要 1373x1021，而窗口只有 1220x800）。
        # 这里只是**请求尺寸**，实际宽高由 pack 的 fill 决定，不会真的只有 40 字宽。
        desc = tk.Text(parent, height=desc_height, width=40, wrap="word",
                       font=("Microsoft YaHei UI", 9), relief="flat",
                       highlightthickness=1, highlightbackground="#ddd",
                       state="disabled")
        # ⚠ pack 顺序也是防裁的一环：Tk 的 pack 是「先来先分」，空间不够时
        # 被切掉的是**最后 pack 的那个**。所以说明框先 pack（贴底），
        # 列表放在最后 —— 挨刀的是它（自带滚动条、可缩），说明框和按钮永远完整。
        desc.pack(side="bottom", fill="x", pady=(4, 0))
        body.pack(fill="both", expand=True, pady=(6, 0))

        setattr(self, "var_%s_skill_search" % key, var_search)
        setattr(self, "tv_%s_skills" % key, tree)
        setattr(self, "txt_%s_skill_desc" % key, desc)

        skp = SkillPicker(self, key, tree, var_search, desc)
        setattr(self, "skp_%s" % key, skp)

        ent.bind("<KeyRelease>", lambda e: skp.fill())
        tree.bind("<<TreeviewSelect>>", lambda e: skp.show_desc())
        # 鼠标放技能行 / 说明框上都弹浮窗（说明太长时窗口里看不全）
        tree.bind("<Motion>", skp.row_tip)
        tree.bind("<Leave>", lambda e: self._tip_hide())
        desc.bind("<Motion>", skp.desc_tip)
        desc.bind("<Leave>", lambda e: self._tip_hide())
        return skp

    def baby_skill_del(self):
        """忘掉技能一览里选中的技能（可多选，一次一批）。"""
        b = self._baby()
        sids = self.skp_baby.sel_ids()
        if b is None or not sids:
            messagebox.showinfo("提示", "先在技能一览里选要忘掉的技能"
                                        "（Ctrl / Shift 可多选）。",
                                parent=self.root)
            return
        try:
            drop, missing = self.babies_ed().forget_many(b, sids)
        except Exception as e:
            messagebox.showerror("改不了", zh_error(e), parent=self.root)
            return
        if not drop:
            self.set_status("选中的 %d 个技能本来就没学" % len(sids))
            return
        self.mark_dirty()
        self.load_baby()
        self.refresh_baby_list_keep(b)
        msg = "已忘掉 %d 个技能" % len(drop)
        if missing:
            msg += "（%d 个本来就没学，跳过）" % len(missing)
        self.set_status(msg)

    def baby_skill_manager(self):
        """打开召唤兽技能管理器窗口。"""
        return self.open_skill_manager("baby")

    def baby_skill_clear(self):
        b = self._baby()
        if b is None:
            return
        if not self.confirm("清空技能", "把这只召唤兽的技能全忘掉？"):
            return
        self.babies_ed().clear_skills(b)
        self.mark_dirty()
        self.load_baby()
        self.refresh_baby_list_keep(b)

    def baby_skill_clone(self):
        """从存档里任意一只召唤兽（别的角色身上的也行）把技能整套复制过来。"""
        bd = self.babies_ed()
        b = self._baby()
        if bd is None or b is None:
            messagebox.showinfo("提示", "先在列表里选一只召唤兽（被克隆的那只）。",
                                parent=self.root)
            return
        meta = self._skills_meta()
        rows = [r for r in bd.all_babies() if r["baby"] is not b]
        if not rows:
            messagebox.showinfo("提示", "存档里没有别的召唤兽可以当来源。",
                                parent=self.root)
            return

        def skill_text(ids):
            out = []
            for s in ids:
                nm = meta.get(s, ("", ""))[0]
                out.append(nm or "#%d" % s)
            return "、".join(out) or "（没有技能）"

        tk, ttk = self.tk, self.ttk
        win = self.tk.Toplevel(self.root)
        win.title("克隆技能 → %s" % bd.display_name(b))
        win.transient(self.root)
        win.grab_set()
        f = ttk.Frame(win, padding=8)
        f.pack(fill="both", expand=True)

        bar = ttk.Frame(f)
        bar.pack(fill="x")
        ttk.Label(bar, text="搜索（技能 / 名字 / 角色）：").pack(side="left")
        var_kw = tk.StringVar()
        ent = ttk.Entry(bar, textvariable=var_kw, width=20)
        ent.pack(side="left", padx=4)
        ent.bind("<KeyRelease>", lambda e: refill())
        var_merge = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="合并（保留目标原有技能）",
                        variable=var_merge).pack(side="left", padx=6)

        cols = ("who", "no", "name", "tpl", "n", "skills")
        heads = ("角色", "序", "名字", "模板", "技能数", "技能")
        widths = (130, 34, 100, 100, 48, 420)
        tv = ttk.Treeview(f, columns=cols, show="headings", height=16,
                          selectmode="browse")
        for c, h, w in zip(cols, heads, widths):
            tv.heading(c, text=h)
            tv.column(c, width=w, anchor="w")
        vs = ttk.Scrollbar(f, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=vs.set)
        vs.pack(side="right", fill="y")
        tv.pack(fill="both", expand=True, pady=6)

        rows_map = {}

        def refill(_e=None):
            tv.delete(*tv.get_children())
            rows_map.clear()
            kw = var_kw.get().strip()
            for r in rows:
                txt = skill_text(r["skills"])
                hay = "%s %s %s %s" % (r["actor_name"], r["name"], r["tpl"], txt)
                if kw and kw not in hay:
                    continue
                iid = "c%d_%d" % (r["actor_id"], r["index"])
                rows_map[iid] = r
                tv.insert("", "end", iid=iid,
                          values=("%s(#%d)" % (r["actor_name"], r["actor_id"]),
                                  r["index"] + 1, r["name"], r["tpl"],
                                  len(r["skills"]), txt))
            kids = tv.get_children()
            if kids:
                tv.selection_set(kids[0])

        refill()

        def do_clone(_e=None):
            sel = tv.selection()
            if not sel:
                return
            r = rows_map.get(sel[0])
            if r is None:
                return
            replace = not var_merge.get()
            tip = ("把「%s」的技能覆盖到「%s」上（原来的 %d 个技能会被清掉）？"
                   % (r["name"], bd.display_name(b), len(bd.skills(b)))) \
                if replace else \
                ("把「%s」的技能补进「%s」？" % (r["name"], bd.display_name(b)))
            if not self.confirm("克隆技能", tip):
                return
            try:
                res = bd.clone_skills(b, r["baby"], replace=replace)
            except Exception as e:
                messagebox.showerror("克隆失败", zh_error(e), parent=win)
                return
            win.destroy()
            self.mark_dirty()
            self.load_baby()
            self.refresh_baby_list_keep(b)
            msg = "已从「%s」克隆：现有 %d 个技能" % (r["name"], len(res["ids"]))
            if res["bad"]:
                msg += "；跳过 %d 个无效 id %s" % (len(res["bad"]), res["bad"])
            if len(res["ids"]) > babies.GAME_LEARN_LIMIT:
                msg += ("；⚠ 现在 %d 个，超过游戏「升级学技能」的 %d 上限"
                        "（读取端没限制，实战能不能用要实机验证）"
                        % (len(res["ids"]), babies.GAME_LEARN_LIMIT))
            self.set_status(msg)
            self.log("技能克隆：" + msg)

        tv.bind("<Double-1>", do_clone)
        bf = ttk.Frame(f)
        bf.pack(fill="x")
        fit_btn(bf, text="克隆给「%s」" % bd.display_name(b),
                   command=do_clone).pack(side="right", padx=4)
        fit_btn(bf, text="取消", command=win.destroy).pack(side="right")
        esc_close(win)
        ent.focus_set()                 # 焦点给搜索框（在 esc_close 之后才优先）
        center_win(win, self.root)

    def baby_add_dialog(self):
        """新增召唤兽：列出全部可选项（含小孩），挑一个加给当前角色。"""
        bd = self.babies_ed()
        a = self._baby_actor()
        if bd is None or a is None:
            messagebox.showinfo("提示", "先打开一个存档。", parent=self.root)
            return
        tk, ttk = self.tk, self.ttk
        win = self.tk.Toplevel(self.root)
        win.title("新增召唤兽")
        win.transient(self.root)
        win.grab_set()
        f = ttk.Frame(win, padding=8)
        f.pack(fill="both", expand=True)

        bar = ttk.Frame(f)
        bar.pack(fill="x")
        ttk.Label(bar, text="搜索（名字 / id / 池）：").pack(side="left")
        var_kw = tk.StringVar()
        ent = ttk.Entry(bar, textvariable=var_kw, width=18)
        ent.pack(side="left", padx=4)
        var_god = tk.BooleanVar(value=False)
        cb_god = ttk.Checkbutton(bar, text="神兽", variable=var_god)
        cb_god.pack(side="left", padx=6)
        # 标签缩短（原来"只看神兽（含小孩）"太长），含义挂 tooltip 里
        self._bind_tip(cb_god, "只看神兽档。\n"
                               "含小孩和泡泡灵仙（两类的资质都是定值，不带随机）。")
        var_mut = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="变异（普通召唤兽资质区间 ×0.66）",
                        variable=var_mut).pack(side="left", padx=6)

        # 五行（2026-09-27 新增）：炼妖合宠时和另一只比「相生 / 相克」决定结果概率
        # （见 game.GameEditor.BABY_FIELDS 里 five 那行的注释）。
        # 「随机」＝跟游戏原样（`$baby` 表里 five 是 proc，每只随机抽）。
        # ⚠ 单独占一行，不挤在 bar 上：bar 已经三个控件，再往上加会被 pack 切掉
        #   （Tk 的 pack 先来先分，空间不够切的是最后 pack 的）。
        bar2 = ttk.Frame(f)
        bar2.pack(fill="x", pady=(4, 0))
        ttk.Label(bar2, text="五行：").pack(side="left")
        var_five = tk.StringVar(value="随机")
        ttk.Combobox(bar2, textvariable=var_five,
                     values=["随机"] + list(game.BABY_FIVE), width=6,
                     state="readonly").pack(side="left", padx=4)
        ttk.Label(bar2, text="（炼妖合宠时和另一只比相生/相克；默认随机＝游戏原样）",
                  foreground="#777").pack(side="left")

        cols = ("id", "name", "type", "pool", "lv", "zi", "grow", "life")
        heads = ("id", "名字", "类型", "备注池", "携带等级", "六项资质", "成长", "寿命")
        widths = (46, 116, 50, 90, 60, 230, 50, 60)
        # 2026-10-03 川：可多选（Ctrl 点选 / Shift 连选）→ 一次加一批
        tv = ttk.Treeview(f, columns=cols, show="headings", height=16,
                          selectmode="extended")
        for c, h, w in zip(cols, heads, widths):
            tv.heading(c, text=h)
            tv.column(c, width=w, anchor="w")
        vs = ttk.Scrollbar(f, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=vs.set)
        vs.pack(side="right", fill="y")
        tv.pack(fill="both", expand=True, pady=6)

        info = tk.StringVar(value="")
        ttk.Label(f, textvariable=info, foreground="#555", justify="left",
                  wraplength=900).pack(anchor="w")

        all_c = bd.candidates()

        def refill(*_a):
            tv.delete(*tv.get_children())
            kw = var_kw.get().strip()
            rows = []
            for c in all_c:
                # ⚠ 这里必须走**模块**（`babies.GOD_TYPES`）：本函数的 `bd` 是
                #   `Babies` 实例，`bd.GOD_TYPES` 会 AttributeError —— 而且因为
                #   `and` short-circuit，只有勾上「神兽」才会炸（2026-10-07 川报）。
                if var_god.get() and c["type"] not in babies.GOD_TYPES:
                    continue
                if kw and kw not in c["name"] and kw != str(c["id"]) \
                        and kw not in c["pool"]:
                    continue
                rows.append(c)
            for c in rows:
                life = "永生" if c["life"] == "infinite" else c["life"]
                tv.insert("", "end", iid="c%d" % c["id"],
                          values=(c["id"], c["name"], c["type"], c["pool"] or "（无）",
                                  c["allow_lv"],
                                  "%s/%s/%s/%s/%s/%s" % (c["atk"], c["def"], c["hp"],
                                                         c["mp"], c["agi"], c["eva"]),
                                  c["grow"], life))
            n_est = sum(1 for c in rows if c.get("inferred"))
            # ⚠ 2026-10-08 川报「用这里新加的召唤兽，进游戏用圣兽之心后资质/成长
            #   都没突破，原本里面进阶过的就突破了」—— 因为加出来的是**未进阶**
            #   状态（资质 = 该档初始值），而游戏里进阶**只抬上限、不动数字**。
            #   所以加完要再去召唤兽页点「进阶并拉满」才看得到突破。这儿先说清。
            info.set("共 %d 种可选。神兽 / 小孩 / 泡泡灵仙资质取定值；"
                     "普通召唤兽资质带随机（勾了“变异”则区间 ×0.66）。\n"
                     "⚠ 加出来的都是**未进阶**（资质＝该档初始值）。"
                     "游戏里「进阶」只抬上限、不动数字 —— 想直接突破，"
                     "加完后在召唤兽页点「进阶并拉满」。"
                     "%s" % (len(rows),
                             ("\n⚠ 其中 %d 种的资质不在表里（按 id 区间估了个量级），"
                              "加出来后可到召唤兽页手动修正。"
                              % n_est) if n_est else ""))
            self._add_rows = rows
            kids = tv.get_children()
            if kids:
                tv.selection_set(kids[0])

        for w in (var_kw, var_god):
            if hasattr(w, "trace_add"):
                w.trace_add("write", refill)
            else:
                w.trace("w", refill)
        refill()

        btns = ttk.Frame(f)
        btns.pack(fill="x", pady=(6, 0))

        def do_add():
            sel = tv.selection()
            if not sel:
                return
            # 五行选「随机」→ 传 None（build 里按游戏原样 rnd.choice）
            five = var_five.get().strip()
            ok, bad = [], []
            for iid in sel:                 # 多选：挨个加，坏的跳过不中断
                cid = int(iid[1:])
                try:
                    self.babies_ed().add(a, cid, mutation=bool(var_mut.get()),
                                         five=None if five == "随机" else five)
                    ok.append(cid)
                except Exception as e:
                    bad.append((cid, zh_error(e)))
            if not ok:
                messagebox.showerror("加不了", bad[0][1], parent=self.root)
                return
            self.mark_dirty()
            win.destroy()
            self.refresh_panels()
            kids = self.tv_babies.get_children()
            if kids:
                self.tv_babies.selection_set(kids[-1])
                self.on_baby_select()
            msg = "已新增召唤兽：%s（id=%d）" % (bd.name_of(ok[0]), ok[0]) \
                if len(ok) == 1 else "已新增 %d 只召唤兽" % len(ok)
            if bad:
                msg += "；%d 只加不了（%s）" % (len(bad), bad[0][1])
            self.set_status(msg)

        btn_add = fit_btn(btns, text="加这只", command=do_add)
        btn_add.pack(side="left")
        fit_btn(btns, text="取消", command=win.destroy).pack(side="left", padx=6)

        def _sync_sel(*_a):
            """按钮文字跟着选中数量走（列表可多选）。"""
            n = len(tv.selection())
            refit_btn(btn_add, "加这只" if n <= 1 else "加选中的 %d 只" % n)

        tv.bind("<<TreeviewSelect>>", _sync_sel)

        esc_close(win)
        ent.focus_set()
        center_win(win, self.root)      # 在主窗口上居中（不然跑到屏幕左上角）
        self.set_status("新增召唤兽：选一只 → 「加这只」（Ctrl / Shift 可多选）")

    def _quick_add(self, actor, cid):
        try:
            self.babies_ed().add(actor, cid)
        except Exception as e:
            messagebox.showerror("加不了", zh_error(e), parent=self.root)
            return
        self.mark_dirty()
        self.refresh_panels()
        kids = self.tv_babies.get_children()
        if kids:
            self.tv_babies.selection_set(kids[-1])
            self.on_baby_select()
        self.set_status("已新增召唤兽：%s（id=%d）"
                        % (self.babies_ed().name_of(cid), cid))

    def baby_delete(self):
        """放生（删除）—— 支持 Ctrl / Shift 多选，一次删一批。

        ⚠ 多选删除必须**按索引从大到小**删：`Babies.remove` 内部是
          `arr.items.pop(index)`，先删小索引会让后面所有索引一起前移，
          接着按原索引删就会删错对象（2026-10-04 加多选时踩过）。
        ⚠ 删掉的正好是「出战」那只时，`remove` 自己会把 `@baby` 挪到剩下
          的第一只（见 babies.remove），这里不用再管。
        """
        rows = []
        for iid in self.tv_babies.selection():
            try:
                i = int(iid[2:])
            except ValueError:
                continue
            for k, b in self.baby_rows:
                if k == i:
                    rows.append((i, b))
                    break
        if not rows:
            messagebox.showinfo("提示", "先在列表里选一只召唤兽"
                                        "（Ctrl 点选 / Shift 连选，可一次放生多只）。",
                                parent=self.root)
            return
        names = [self.g.baby_name(b) for _i, b in rows]
        if len(rows) == 1:
            tip = ("把「%s」从这只角色身上删掉？（不可撤销）\n\n"
                   "游戏里相当于放生：数据没了，想找回来只能重新加一只。"
                   % names[0])
        else:
            shown = "、".join(names[:8]) + ("…" if len(names) > 8 else "")
            tip = ("把这 %d 只召唤兽从这只角色身上删掉？（不可撤销）\n"
                   "%s\n\n"
                   "游戏里相当于放生：数据没了，想找回来只能重新加一只。"
                   % (len(rows), shown))
        if not self.confirm("放生（删除）", tip):
            return
        actor = self._baby_actor()
        n = 0
        for i, _b in sorted(rows, key=lambda r: -r[0]):
            try:
                self.babies_ed().remove(actor, i)
                n += 1
            except Exception as e:
                messagebox.showerror("删不了", zh_error(e), parent=self.root)
                break
        if not n:
            return
        self.mark_dirty()
        self.fill_baby_list()
        self.set_status("已放生：%s" % names[0] if n == 1
                        else "已放生 %d 只（%s）" % (n, "、".join(names[:5])))

    def baby_set_active(self):
        b = self._baby()
        if b is None:
            return
        idx = [k for k, x in self.baby_rows if x is b][0]
        self.babies_ed().set_active(self._baby_actor(), idx)
        self.mark_dirty()
        self.refresh_baby_list_keep(b)
        self.set_status("已设为出战：%s" % self.g.baby_name(b))

    def baby_rename(self):
        """改显示名（@attr.@name）。

        显示名只是给人看的，游戏战斗查立绘/音效用的是基础名 @name（``read_note
        ('battler') or name``），所以显示名随便改、也不用查名字表；基础名不提供
        修改（改了会取不到立绘/音效）。
        """
        b = self._baby()
        if b is None:
            return
        name = self.var_baby_name.get().strip()
        if not name:
            messagebox.showinfo("提示", "名字不能是空的。", parent=self.root)
            return
        self.babies_ed().set_display_name(b, name)
        self.mark_dirty()
        self.load_baby()
        self.refresh_baby_list_keep(b)
        self.set_status("已改名：%s" % name)

    def baby_restore_name(self):
        """恢复模板本名 —— 对**选中的全部召唤兽**生效。"""
        rows = self._baby_sel()
        if not rows:
            return
        names = []
        for _i, b in rows:
            try:
                names.append(self.babies_ed().restore_name(b))
            except Exception as e:
                messagebox.showerror("改不了", zh_error(e), parent=self.root)
                return
        self.mark_dirty()
        self.refresh_baby_list_keep([b for _i, b in rows])
        if len(names) == 1:
            self.set_status("名字已恢复成模板本名：%s" % names[0])
        else:
            self.set_status("已把 %d 只召唤兽的名字恢复成模板本名" % len(names))

    def _sync_baby_val_widget(self, key=None):
        """「改字段」那行的值控件：五行 → 只读下拉，其它 → 数字输入框。

        两个控件叠在同一格上（`ent_baby_val` / `cb_baby_val`），用
        `grid_remove()` / `grid()` 切 —— 不用 pack，免得重排整行。
        """
        if key is None:
            key = self.var_baby_key.get().strip()
        if key == "five":
            self.ent_baby_val.grid_remove()
            self.cb_baby_val.grid()
        else:
            self.cb_baby_val.grid_remove()
            self.ent_baby_val.grid()

    def baby_pick(self):
        sel = self.tv_baby.selection()
        if not sel:
            return
        vals = self.tv_baby.item(sel[0], "values")
        iid = sel[0]
        key = iid[2:] if iid.startswith("b_") else iid
        self.var_baby_key.set(key)
        self.var_baby_val.set(vals[1] if len(vals) > 1 else "")
        self._sync_baby_val_widget(key)

    def apply_baby(self):
        """「改字段」的应用：写进**选中的全部召唤兽**（多选 = 一次改一批）。"""
        rows = self._baby_sel()
        if not rows or self.g is None:
            return
        key = self.var_baby_key.get().strip()
        raw = self.var_baby_val.get().strip()
        if not key or raw == "":
            messagebox.showinfo("提示", "先在上面选一个字段并填值。", parent=self.root)
            return
        # 五行（five）= 字符串，原样传；别的字段是数字（int(raw, 0) 兼容 0x）
        if game.GameEditor.baby_field_type(key) == "str":
            val = raw
        else:
            try:
                val = float(raw) if "." in raw else int(raw, 0)
            except ValueError:
                messagebox.showinfo("提示", "这个字段要填数字。", parent=self.root)
                return
        try:
            for _i, b in rows:
                self.g.set_baby(b, key, val)
        except Exception as e:
            messagebox.showerror("修改失败", human(str(e)), parent=self.root)
            return
        self.mark_dirty()
        self.refresh_baby_list_keep([b for _i, b in rows])
        label = dict((k, lb) for k, lb, _p, _t
                     in game.GameEditor.BABY_FIELDS).get(key, key)
        if len(rows) == 1:
            msg = "召唤兽「%s」的 %s 已改" % (self.g.baby_name(rows[0][1]), label)
        else:
            msg = "已把 %d 只召唤兽的 %s 改成 %s" % (len(rows), label, raw)
        # ⚠ 资质超上限**照写不误**（游戏面板把上限那个数标红、按上限算），只提示一句
        if key in game.GameEditor.BABY_ZIZHI:
            msg += self._baby_cap_note([b for _i, b in rows])
        self.set_status(msg)

    def baby_preset(self, what):
        if what == "state_all":
            # 「全员状态拉满」不依赖「当前选中哪一只」→ 走专用路径，见下
            return self.baby_state_all()
        if what == "loyalty_all":
            # 老按钮「全员忠诚满」已并入「全员状态拉满」；留这条只为兼容旧调用
            return self.baby_loyalty_all()
        if what in ("promote", "promote_fill"):
            # 进阶走 babies.promote_many（不是 game.baby_preset 那一套）
            return self.baby_promote(fill=(what == "promote_fill"))
        rows = self._baby_sel()
        if not rows or self.g is None:
            return
        did = []
        try:
            for _i, b in rows:
                did.extend(self.g.baby_preset(b, what) or [])
        except Exception as e:
            messagebox.showerror("修改失败", human(str(e)), parent=self.root)
            return
        if did:
            self.mark_dirty()
            self.refresh_baby_list_keep([b for _i, b in rows])
            self.set_status("召唤兽预设：%s%s"
                            % ("、".join(did[:8]) + ("…" if len(did) > 8 else ""),
                               self._baby_cap_note([b for _i, b in rows])))

    def _baby_cap_note(self, rows):
        """超上限提示（返回带前导分隔的空串或说明）。

        超上限**不是错误**：游戏读资质一律 `min(@值, 上限)`，面板把上限那个数画成
        **红色**。2026-10-08 川的档实测：涂山雪存 atk/def 2100、上限 2000、面板红字
        2000 —— 所以工具只管如实提示，**不动那个数**（夹回上限反而会把它变小）。
        """
        n = 0
        for b in rows:
            try:
                if self.g.baby_over_cap(b):
                    n += 1
            except Exception:
                continue
        if not n:
            return ""
        return "；⚠ %d 只的资质超过当前上限 —— 游戏里按上限显示（面板标红），要提上限得先「进阶」" % n

    def baby_promote(self, fill=False):
        """把选中的召唤兽**进阶**（= 游戏里 `attr.promote = true` 那一步）。

        2026-10-08 川报「用工具新增的召唤兽，进游戏用圣兽之心后成长/资质都没突破
        （原本里面的进阶就突破了）」—— 根因是**游戏侧进阶压根不动数字**：

            Game_Baby_Attr#promote=(v) -> @promote = v
            Game_Baby_Attr#get_max_*   -> $baby[:_max][promote ? :"类型_p" : 类型]
            Game_Baby_Attr#get_atk     -> [@atk, get_max_atk].min
            面板绘制（blob:78735）      -> "#{value} / #{max_value}"，value 已 min 过

        所以「进阶前 / 进阶后」两张面板图数值一模一样（1900/1900/7000/4000/
        2100/2100、成长 1.6）—— 进阶只把**天花板**从 `神兽 1900…1.6` 抬到
        `神兽_p 2000/2000/7200/4200/2200/2200/1.8`，数字得自己长（吃元宵）。

        `fill=True` 就补上这一步：六项资质 + 成长直接写到进阶后的上限
        （等价游戏 `set_max_zizhi`，游戏里没有一步到位的道具）。

        ⚠ 图鉴里没有进阶形象的（`Data\\Actors` 的 @note 没有 `promote =`，
          如恶魔泡泡 215）**跳过不写** —— 游戏画进阶形象时拿 nil 当立绘名会崩。
        """
        rows = self._baby_sel()
        if not rows or self.g is None:
            self.set_status("先在召唤兽列表里选一只（Ctrl / Shift 可多选）")
            return
        try:
            r = self.babies_ed().promote_many(rows, fill=fill)
        except Exception as e:
            messagebox.showerror("进阶失败", human(str(e)), parent=self.root)
            return
        if r["promoted"] or r["filled"]:
            self.mark_dirty()
        self.refresh_baby_list_keep([b for _i, b in rows])
        parts = []
        if r["promoted"]:
            parts.append("进阶 %d 只" % r["promoted"])
        if r["already"]:
            parts.append("%d 只本来就进阶过" % r["already"])
        if fill and r["filled"]:
            parts.append("资质/成长拉满 %d 项" % r["filled"])
        if r["skipped"]:
            parts.append("跳过 %d 只（%s）"
                         % (len(r["skipped"]),
                            "、".join(n for n, _w in r["skipped"][:3])))
        self.set_status("召唤兽进阶：" + ("；".join(parts) if parts else "无需改动"))

    def baby_loyalty_all(self):
        """「全员忠诚满」：一次把**所有角色**的**所有召唤兽**忠诚拉满。

        为什么按钮改成全员版（2026-09-27 川要求）：游戏里忠诚只有「<60 不能参战」
        这一个作用（`Config::Baby::ALLOW_LOYALTY`），**没有**属性/成长加成，
        `$jiance` 反作弊也完全不看它 → 一次全改没有副作用，比逐只点省事。
        上限 100 是游戏硬规定（`add_loyalty` 里 limit），写更高会被游戏夹回去，
        详见 `game.GameEditor.set_loyalty_all`。
        """
        if self.g is None:
            return
        try:
            n, na = self.g.set_loyalty_all()
        except Exception as e:
            messagebox.showerror("修改失败", human(str(e)), parent=self.root)
            return
        if not n:
            self.set_status("全员忠诚满：所有召唤兽已经是上限，无需改动")
            return
        self.mark_dirty()
        # ⚠ 必须记住当前选中：`refresh_panels()` 走的是 `fill_babies` →
        #   `fill_baby_list()`，它会把一览表的选中**重置成第一行**
        #   （2026-09-27 踩过：全员忠诚满之后，接着操作「当前选中那只」的功能
        #    全落到第一只头上）。用 `refresh_baby_list_keep` 把它拉回来。
        keep = self._baby()
        self.refresh_panels()
        if keep is not None:
            self.refresh_baby_list_keep(keep)
        self.set_status("全员忠诚满：改了 %d 只（%d 个角色）" % (n, na))

    def baby_state_all(self):
        """「全员状态拉满」（2026-10-03 川要求，合并老两个按钮）：
        **所有角色**身上的**所有召唤兽** —— 气血/魔法/愤怒 回满 + 忠诚拉满。

        老按钮是「回满气血/魔法」（只动当前选中那只）+「全员忠诚满」，
        合并后语义 = 两者并集。一次全改没有副作用：忠诚只有「<60 不能参战」
        一个作用、没有属性加成，内测版 V2.201 也没有周期检查（详见
        `game.GameEditor.set_state_all`）。

        ⚠ 刷新一览表时必须**记住当前选中**再恢复：`refresh_panels()` 走
        `fill_babies` → `fill_baby_list`，会把一览表选中重置回第一行
        （2026-09-27 踩过，同 `baby_loyalty_all`）。
        """
        if self.g is None:
            return
        try:
            n, na, nl = self.g.set_state_all()
        except Exception as e:
            messagebox.showerror("修改失败", human(str(e)), parent=self.root)
            return
        if not n:
            self.set_status("全员状态拉满：所有召唤兽都已经是上限，无需改动")
            return
        self.mark_dirty()
        keep = self._baby()
        self.refresh_panels()
        if keep is not None:
            self.refresh_baby_list_keep(keep)
        self.set_status("全员状态拉满：改了 %d 只（%d 个角色，其中忠诚 %d 只）"
                        % (n, na, nl))

    # -------------------------------------------------- 5 开关 / 变量（已隐藏页签）
    def _tab_switch(self, add_to_notebook=True):
        tk, ttk = self.tk, self.ttk
        f = ttk.Frame(self.nb, padding=8)
        self.tab_switch = f
        if add_to_notebook:
            self.nb.add(f, text="开关 / 变量")

        lf = ttk.Frame(f)
        lf.pack(side="left", fill="both", expand=True, padx=(0, 8))
        ttk.Label(lf, text="开关（双击切换）—— 本作只有 3 个，名字来自游戏脚本"
                  ).pack(anchor="w")
        self.tv_sw = ttk.Treeview(lf, columns=("i", "v", "n"),
                                  show="headings", height=20)
        self.tv_sw.heading("i", text="编号")
        self.tv_sw.heading("v", text="值")
        self.tv_sw.heading("n", text="名字 / 说明")
        self.tv_sw.column("i", width=60, anchor="w")
        self.tv_sw.column("v", width=60, anchor="w")
        self.tv_sw.column("n", width=280, anchor="w")
        vs_sw = ttk.Scrollbar(lf, orient="vertical", command=self.tv_sw.yview)
        self.tv_sw.configure(yscrollcommand=vs_sw.set)
        vs_sw.pack(side="right", fill="y")
        self.tv_sw.pack(fill="both", expand=True)
        self.tv_sw.bind("<Double-1>", lambda e: self.sw_toggle())

        rf = ttk.Frame(f)
        rf.pack(side="left", fill="both", expand=True)
        ttk.Label(rf, text="变量（双击修改）").pack(anchor="w")
        self.tv_va = ttk.Treeview(rf, columns=("i", "v", "n"),
                                  show="headings", height=20)
        self.tv_va.heading("i", text="编号")
        self.tv_va.heading("v", text="值")
        self.tv_va.heading("n", text="名字 / 说明")
        self.tv_va.column("i", width=60, anchor="w")
        self.tv_va.column("v", width=90, anchor="w")
        self.tv_va.column("n", width=280, anchor="w")
        vs_va = ttk.Scrollbar(rf, orient="vertical", command=self.tv_va.yview)
        self.tv_va.configure(yscrollcommand=vs_va.set)
        vs_va.pack(side="right", fill="y")
        self.tv_va.pack(fill="both", expand=True)
        self.tv_va.bind("<Double-1>", lambda e: self.va_edit())

    # -------------------------------------------------- 6 数据表 (CSV)
    def _tab_db(self):
        tk, ttk = self.tk, self.ttk
        f = ttk.Frame(self.nb, padding=8)
        self.tab_db = f
        self.nb.add(f, text="数据表 (CSV)")

        bar = ttk.Frame(f)
        bar.pack(fill="x")
        ttk.Label(bar, text="Data\\*.rvdata2 都是加密的（密钥 761205），"
                            "本工具解密后可直接转 CSV：").pack(side="left")
        fit_btn(bar, text="全部导出",
                   command=self.db_export_all).pack(side="right", padx=4)
        fit_btn(bar, text="导出选中表",
                   command=self.db_export_selected).pack(side="right", padx=4)
        fit_btn(bar, text="选输出目录…",
                   command=self.db_choose_dir).pack(side="right", padx=4)

        body = ttk.Panedwindow(f, orient="horizontal")
        body.pack(fill="both", expand=True, pady=6)

        left = ttk.Frame(body)
        ttk.Label(left, text="表（点一行看预览）").pack(anchor="w")
        self.lst_db = tk.Listbox(left, height=18, exportselection=False)
        self.lst_db.pack(fill="both", expand=True)
        self.lst_db.bind("<<ListboxSelect>>", lambda e: self.db_preview())
        body.add(left, weight=1)

        right = ttk.Frame(body)
        self.var_db_info = tk.StringVar(value="（选一张表看预览）")
        ttk.Label(right, textvariable=self.var_db_info,
                  font=("Microsoft YaHei UI", 10)).pack(anchor="w")
        self.tv_db = ttk.Treeview(right, columns=("c0",), show="headings", height=20)
        vs = ttk.Scrollbar(right, orient="vertical", command=self.tv_db.yview)
        hs = ttk.Scrollbar(right, orient="horizontal", command=self.tv_db.xview)
        self.tv_db.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        vs.pack(side="right", fill="y")
        hs.pack(side="bottom", fill="x")
        self.tv_db.pack(fill="both", expand=True)
        body.add(right, weight=4)

        out = ttk.Frame(f)
        out.pack(fill="x")
        ttk.Label(out, text="输出目录：").pack(side="left")
        self.var_db_out = tk.StringVar(value=DEFAULT_CSV_DIR)
        ttk.Entry(out, textvariable=self.var_db_out, width=70).pack(side="left")

        for key in datatables.ALL_KEYS:
            self.lst_db.insert("end", "%s —— %s%s" % (
                datatables.table_label(key), key,
                "" if datatables.is_default(key) else "（可选）"))
        self.lst_db.selection_set(0)

    # -------------------------------------------------- 7 / 8
    def _tab_help(self):
        tk, ttk = self.tk, self.ttk
        f = ttk.Frame(self.nb, padding=8)
        self.tab_help = f
        self.nb.add(f, text="说明 / 机制")
        t = tk.Text(f, wrap="word", font=("Microsoft YaHei UI", 10))
        t.pack(fill="both", expand=True)
        t.insert("1.0", HELP_TEXT)
        t.configure(state="disabled")

    def _tab_log(self):
        tk, ttk = self.tk, self.ttk
        f = ttk.Frame(self.nb, padding=8)
        self.tab_log = f
        self.nb.add(f, text="更新日志")
        t = tk.Text(f, wrap="word", font=("Microsoft YaHei UI", 10))
        t.pack(fill="both", expand=True)
        t.insert("1.0", CHANGELOG)
        t.configure(state="disabled")

    def _build_status(self):
        self.var_status = self.tk.StringVar(value="就绪")
        self.ttk.Label(self.root, textvariable=self.var_status, relief="sunken",
                       anchor="w").pack(fill="x", side="bottom")

    # ================================================== 基础
    def _tk_exception(self, exc, val, tb):
        text = "".join(traceback.format_exception(exc, val, tb))
        try:
            with open(os.path.join(os.path.dirname(HERE), "error.log"), "a",
                      encoding="utf-8") as f:
                f.write("\n===== %s =====\n%s"
                        % (time.strftime("%Y-%m-%d %H:%M:%S"), text))
        except OSError:
            pass
        try:
            messagebox.showerror(
                "出错", zh_error(val, "这个操作出问题了（界面里的其它功能还能用）：")
                + "\n\n（完整堆栈已写入 error.log）", parent=self.root)
        except Exception:
            pass
        self.set_status("出错：%s（详见 error.log）" % val)

    def set_status(self, s):
        try:
            self.var_status.set(s)
            self.root.update_idletasks()
        except Exception:
            pass

    def log(self, s):
        self.set_status(s)

    def err(self, e):
        self.set_status("出错：%s" % human(str(e)).replace("\n", " ")[:120])

    def confirm(self, title, text):
        """问一句“要不要”。

        走一层包装：测试里把 messagebox 换成了“只记录”的假对象，
        没有 askyesno 时就当“确认”（不然一调就 AttributeError）。
        """
        fn = getattr(messagebox, "askyesno", None)
        if fn is None:
            return True
        return bool(fn(title, text, parent=self.root))

    # ------------------------------------------------------------ 悬浮说明
    def _tip_hide(self, event=None):
        w = getattr(self, "_tip_win", None)
        if w is not None:
            try:
                w.destroy()
            except Exception:
                pass
        self._tip_win = None
        self._tip_key = None

    def _bind_tip(self, widget, text):
        """给任意 widget 绑一个简单的鼠标悬浮 tooltip。"""
        def on_enter(_e):
            try:
                self._tip_show(text, widget.winfo_rootx() + 4,
                               widget.winfo_rooty() + widget.winfo_height() + 2)
            except Exception:
                pass
        def on_leave(_e):
            self._tip_hide()
        widget.bind("<Enter>", on_enter, add="")
        widget.bind("<Leave>", on_leave, add="")

    def _tip_show(self, text, x, y, key=None):
        """弹出浮窗。

        key 是「当前浮窗对应哪个目标」的标识：调用方在 <Motion> 里先比 key、
        一样就直接 return（不然每动一像素都销毁重建，闪得厉害）。
        ⚠ 这里必须**先记住 key 再 _tip_hide()** —— _tip_hide 会把 _tip_key
        清成 None，写反了就等于每次都重建。
        """
        self._tip_hide()
        self._tip_key = key
        if not text:
            return
        tw = self.tk.Toplevel(self.root)
        tw.wm_overrideredirect(True)
        try:
            tw.wm_attributes("-topmost", True)
        except Exception:
            pass
        lbl = self.tk.Label(tw, text=text, justify="left", wraplength=420,
                            background="#fffde7", relief="solid", borderwidth=1,
                            font=("Microsoft YaHei UI", 9), padx=6, pady=4)
        lbl.pack()
        tw.wm_geometry("+%d+%d" % (x + 12, y + 12))
        self._tip_win = tw

    def _bag_tip_motion(self, event):
        """鼠标在背包格子上移动 → 浮窗显示物品完整说明（Data 表 @description）。"""
        if not getattr(self, "g", None):
            return
        row = self.tv_pack.identify_row(event.y)
        key = ("pack", self._bag_kind(), self.var_bag_page.get(), row)
        if key == getattr(self, "_tip_key", None):
            return
        self._tip_key = key
        if not row:
            self._tip_hide()
            return
        vals = list(self.tv_pack.item(row, "values")) + [""] * 6
        slot_txt, _idx, id_txt, name, cnt, content = vals[:6]
        if not id_txt or id_txt == "（空）":
            self._tip_hide()
            return
        try:
            slot = int(slot_txt)
        except (TypeError, ValueError):
            self._tip_hide()
            return
        desc = ""
        try:
            node = self.g._item_node(self._bag_kind(), slot)
            if node is not None:
                desc = self.g.item_description(node)
        except Exception:
            desc = ""
        parts = ["#%s  %s ×%s" % (id_txt, name, cnt)]
        if desc:
            parts.append(desc)
        if content:
            parts.append("运行时内容：%s" % content)
        self._tip_show("\n".join(parts), event.x_root, event.y_root, key=key)

    def _tpl_tip_motion(self, event):
        """鼠标在物品模板列表上移动 → 浮窗显示模板完整说明。"""
        if not getattr(self, "g", None):
            return
        row = self.tv_tpl.identify_row(event.y)
        key = ("tpl", self._bag_kind(), self.var_tpl_kw.get(), row)
        if key == getattr(self, "_tip_key", None):
            return
        if not row:
            self._tip_hide()
            return
        try:
            iid = int(row[1:])
        except ValueError:
            self._tip_hide()
            return
        nm, desc = "", ""
        pair = self.g._desc_map(self._bag_kind()).get(iid)
        if pair:
            nm, desc = pair
        parts = ["#%d  %s" % (iid, nm)]
        if desc:
            parts.append(desc)
        self._tip_show("\n".join(parts), event.x_root, event.y_root, key=key)

    def mark_dirty(self):
        self.root.title(TITLE + "  * 有未保存的修改")

    def clear_dirty(self):
        self.root.title(TITLE)

    def open_homepage(self):
        try:
            import webbrowser
            webbrowser.open(HOMEPAGE)
        except Exception:
            pass
        self.set_status("开源地址：%s" % HOMEPAGE)

    def copy_homepage(self):
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(HOMEPAGE)
            self.set_status("已复制开源地址：%s" % HOMEPAGE)
        except Exception as e:
            self.err(e)

    def show_about(self):
        messagebox.showinfo(
            "关于",
            "%s\n版本 %s\n\n作者：@%s\n开源地址：%s\n问题反馈：%s\n协议：%s\n\n"
            "本工具是第三方存档查看/修改器，与游戏作者无关；\n"
            "请先备份存档再使用（本工具也会自动留 .bak）。\n"
            "游戏本体及其素材、数据文件的版权归原作者所有。"
            % (APP_NAME, VERSION, AUTHOR, HOMEPAGE, ISSUES, LICENSE_NAME),
            parent=self.root)

    @staticmethod
    def _looks_like_ours(path):
        """这个存档是不是本工具吃的版本（内测版 V2.201）？

        川 2026-10-03 要求：**先识别文件和存档版本**再载入。跨版存档
        （拿内测版工具开尝鲜版档）以前要等自动载入弹「打开失败」才发现，
        模态框还把窗口卡成「未响应」；现在猜路径阶段就验，验不过不载。

        ⚠ 只看**第一个 AES 块**（16 字节），绝不整档解 —— `save_v201`
          的 `looks_like_v201()` 会把整个文件 AES+Inflate 解开，纯 Python
          AES 解几 MB 要 30+ 秒（2026-10-03 实测 35.5s），启动探测绝不能走它。
          V2.201 明文以 Zlib 流开头（0x78 'x'），第一个块里就能验。
        """
        try:
            import save_v201
            raw = open(path, "rb").read(16)
            if len(raw) < 16:
                return False
            head = save_v201._aes_ecb(raw, save_v201.save_key(), True)
            if head[:1] != b"x":                 # zlib 头 0x78
                return False
            # zlib 头两字节校验：(CMF*256 + FLG) % 31 == 0
            return (head[0] * 256 + head[1]) % 31 == 0
        except Exception:
            return False

    def _guess_save(self):
        if os.path.exists(LAST_TXT):
            p = open(LAST_TXT, encoding="utf-8").read().strip()
            # ⚠ 排除 %TEMP% 下的路径：自动化/测试会在 Temp 建假存档副本并
            #   load 过它（把 LAST_TXT 写成了副本路径），下次启动猜到它只会
            #   弹「打开失败」—— 而且弹在首帧之前，整个窗口白屏「未响应」
            #   （2026-10-03 beta.12 实际发生过）。真档永远不在 Temp 里。
            if p and os.path.exists(p) and not _in_temp(p) \
                    and self._looks_like_ours(p):
                return p
            if p and os.path.exists(p) and not _in_temp(p):
                # 名字对、打不开：多半是跨版本存档（比如尝鲜版的档）
                self.set_status(
                    "上次打开的「%s」不是内测版 V2.201 格式（可能是尝鲜版"
                    "存档），已跳过；请点「选择存档…」手动选内测版存档。"
                    % os.path.basename(p))
        p = paths.save_path()
        # 游戏目录里那份也要验：内测版工具若对着尝鲜版目录跑，同样不能载
        if p and not self._looks_like_ours(p):
            return None
        return p

    def refresh_env(self):
        g = paths.find_game_dir()
        self.var_env.set(
            "游戏目录：%s　|　当前文件：%s　|　32 位宿主：%s"
            % (g or "未找到", self.doc.path if self.doc else "—",
               "有" if os.path.exists(codec.HOST)
               else "缺！先跑 python tools/build_host.py"))

    # ================================================== 打开 / 保存
    def choose_file(self):
        p = filedialog.askopenfilename(
            title="选择存档", initialdir=paths.find_game_dir() or "",
            filetypes=[("RPG Maker 存档", "*.rvdata2 *.rxdata *.bin"),
                       ("全部文件", "*.*")])
        if p:
            self.var_path.set(p)
            self.load(p)

    def reload(self):
        p = self.var_path.get().strip() or (self.doc.path if self.doc else "")
        if p:
            self.load(p)

    def _pump(self, msg):
        """载入途中刷一条进度 + 泵一轮消息。

        ⚠ 载真档要**约 0.8 秒**（2026-10-07 提速后；此前纯 Python AES 一回要 6.5 秒），
          期间主线程若不取消息，Windows 直接给窗口挂「未响应」，看起来像死了
          （2026-10-03 川实报）。这里主动 update() 一轮：窗口能重绘、标题不挂未响应。
        ⚠ update() 会放行用户输入 ⇒ 用 _loading 挡住 load 重入（见 load）。
        """
        if msg:
            self.set_status(msg)
        try:
            self.root.update()
        except Exception:
            pass

    def load(self, path, quiet=False):
        # 防重入：_pump 会 update() 放行用户输入，别让「重新载入」在载入
        # 途中再进来一层（半载状态再 load 必炸）。
        if getattr(self, "_loading", False):
            return
        self._loading = True
        try:
            self._load_impl(path, quiet)
        finally:
            self._loading = False

    def _load_impl(self, path, quiet=False):
        # 手动载入 = 已明确指定要开哪本，把 __init__ 里排队的自动载入撤掉。
        # 不撤的话，那个 after(200) 回调随后会把 doc 换回 _guess_save() 猜到的
        # 那本档 —— 自动化脚本先 load(副本) 再改，最终就写到了玩家真档上。
        self.cancel_auto_load()
        self._pump("正在打开 %s …（解密+解析）" % os.path.basename(path))
        try:
            self.doc = doctree.Doc(path)
        except Exception as e:
            self.doc = None
            self.sv = None
            if not quiet:
                messagebox.showerror("打开失败", human(str(e)), parent=self.root)
            self.set_status("打开失败：%s" % human(str(e))[:120])
            return
        try:
            self.sv = save.SaveDoc(doc=self.doc)
            # SaveDoc 是懒解析的，动不动就"建成功"：这里确认它真的像本作存档，
            # 否则（比如 Battle.bt2）后面每个面板都会挨个抛 KeyError。
            # 注意 sections() 给的是 [(名字, 节点), ...]，不是一串名字。
            need = {"system", "party", "actors", "variables"}
            if not need <= set(n for n, _ in self.sv.sections()):
                self.sv = None
        except Exception:
            self.sv = None            # 不是本作存档：只保留"数据树"功能
        self._pump("正在解析存档结构 …")
        self.sync_editor()
        # ⚠ 只记「真档」：测试/自动化在 %TEMP% 建的副本不算 —— 记进去
        #   下次启动就会自动载它（解不开→弹框→白屏未响应，2026-10-03 踩过）。
        if not _in_temp(path):
            try:
                open(LAST_TXT, "w", encoding="utf-8").write(path)
            except OSError:
                pass
        self.var_path.set(path)
        self.clear_dirty()
        # 每个面板单独兜底：一个面板炸了不能把「全部解析数据」也一起带下去
        self._pump("正在刷新各页签 …")
        # 体检表（Lock / 五类记账 / 逐物品计数 / 作弊标记，约 0.1 秒）概览页要画、
        # 「载入后提醒」也要看 —— **算一次**给两边，别在载入里算两遍（2026-10-07）。
        rows = None
        if self.g:
            try:
                rows = self.g.anti_cheat_report()
            except Exception:
                rows = None
        bad = self.refresh_panels(guard_rows=rows)
        if bad:
            self.set_status("已载入 %s，但「%s」刷新失败：%s"
                            % (os.path.basename(path), "、".join(bad),
                               self.var_status.get()))
        else:
            self.set_status("已载入 %s（明文 %d 字节，%d 个顶层对象%s）"
                            % (os.path.basename(path), len(self.doc.raw),
                               len(self.doc.objects),
                               "" if self.sv else "；不是本作存档，只有数据树可用"))
        if not quiet:
            self.warn_cheat_after_load(rows=rows)

    def save_save(self):
        if not self.doc or not self.doc.dirty:
            messagebox.showinfo("保存", "没有改动。", parent=self.root)
            return
        self._guard_rows = None
        if not self._pre_save_guard():
            return
        # 保存前先在“存档管理”的目录里留一份（同一份文件 90 秒内只留一次）
        auto = backup.auto_backup_once(self.doc.path)
        try:
            p = self.doc.save()
        except Exception as e:
            messagebox.showerror("保存失败", zh_error(e), parent=self.root)
            return
        try:
            self.sv = save.SaveDoc(doc=self.doc)
        except Exception:
            self.sv = None
        self.sync_editor()
        self.clear_dirty()
        # ⚠ 存盘不改数据，体检表内容与刚才那份完全一样 → 直接给它，别在
        #   fill_info 里再算一遍（anti_cheat_report 要扫 Lock/记账/物品，约 0.4s）。
        #   刚 auto-fix 过时 `_guard_rows` 是 None，那时才重算。
        self.refresh_panels(guard_rows=self._guard_rows)
        self._guard_rows = None
        messagebox.showinfo(
            "保存", "已写回：\n%s\n\n%s"
            % (p, ("存档管理里也留了一份：%s" % os.path.basename(auto))
               if auto else "原文件已备份为 %s.bak.<时间>" % os.path.basename(p)),
            parent=self.root)
        self.set_status("已保存" + self._machine_note_after_save())

    def _machine_note_after_save(self):
        """保存后在状态栏缀一句机器码提醒 —— **只提示，绝不代写**。

        本机机器码不在存档里时，游戏在本机启动会弹「存档异常」；但那是
        「换机器玩」的正常状态，工具不替用户改（2026-10-04 川：把机器码换成
        别的一保存又被塞回本机码）。走 `machine_status()`，机器码在进程内
        有缓存，这里不会再起一次 exe。
        """
        try:
            now, err, ids, ok = self.g.machine_status()
        except Exception:
            return ""
        if now and not ok:
            return ("　机器码：本机 %s 不在存档里（工具没动它；"
                    "要加去「机器码」页）" % now)
        return ""

    def _pre_save_guard(self):
        """存盘前体检：有超限项 / 作弊标记就说清楚，并问要不要顺手修好。

        为什么必须提醒（**尝鲜版**口径）：周期检查一旦把 `@cheated` 记下来，
        20 分钟后就会开始“惩罚”（脚本 29485-29495 行：画面转圈、缩放），
        那段代码在**战斗中**会去碰已经 dispose 的 `$game_player.sprite`
        → `RGSSError: disposed sprite`。⚠ 内测版 V2.201 没有周期检查 /
        @cheated —— 在这里只剩「上限提示」的意义（超了游戏也不正常），
        不会再说「会被判作弊」。
        """
        if not self.g:
            return True
        try:
            rows = self.g.anti_cheat_report()
        except Exception:
            return True
        over = [r for r in rows if r[3]]
        if not over:
            self._guard_rows = rows        # 没超限：内容待会儿直接喂给面板
            return True
        detail = "\n".join("  · %s：当前 %s（上限 %s）" % (r[0], r[1], r[2])
                           for r in over[:8])
        if self.confirm(
                "存档里有 %d 项超限 / 作弊标记" % len(over),
                "游戏会在 20 分钟后开始“惩罚”（画面转圈、缩放），\n"
                "战斗中会直接报 RGSSError（disposed sprite）崩掉。\n\n"
                "%s\n\n"
                "点「是」＝ 现在按规则修好（数值修复 + 清作弊标记 + 同步物品计数）再保存\n"
                "点「否」＝ 先不修，再问一次要不要照样保存" % detail):
            done = self.guard_autofix(quiet=True)
            self._guard_rows = None        # 修过了，面板那份得重算
            self.refresh_panels()
            self.set_status("保存前已顺手修好：%s" % "、".join(done or ["（无需处理）"]))
            return True
        self._guard_rows = rows
        return self.confirm("照样保存？",
                            "带着超限项 / 作弊标记保存？（进战斗可能会崩）")

    def guard_autofix(self, quiet=False):
        """一键：按规则修数值 + 清作弊标记 + 同步物品计数校验。"""
        done = []
        if not self.g:
            return done
        for fn, what in ((self.g.fix_anti_cheat, "数值按规则修复"),
                         (self.g.clear_cheat_flag, "清除作弊标记"),
                         (self.g.resync_security, "同步物品计数校验")):
            try:
                r = fn()
                if r:
                    done.append(what)
            except Exception as e:
                if not quiet:
                    self.err(e)
        if done:
            self.mark_dirty()
        return done

    def refresh_panels(self, guard_rows=None):
        """把所有面板刷一遍。每步单独兜底，返回出错的步骤名列表。

        存档面板和"全部解析数据"互不依赖，一个炸了不该连坐。
        `guard_rows`：已经算好的体检表（保存流程里刚算过一份），传进来就不再重算。
        """
        bad = []
        for step, fn in (("概览", lambda: self.fill_info(guard_rows)),
                         ("数据树", self.fill_tree),
                         ("角色", self.fill_actors), ("背包", self.fill_party),
                         ("召唤兽", self.fill_babies),
                         ("开关/变量", self.fill_switches),   # 页签已隐藏，仅刷新内容
                         ("机器码", lambda: self.machine_show(quiet=True)),
                         ("存档管理", self.saves_refresh),
                         ("环境信息", self.refresh_env)):
            self._pump("正在刷新「%s」…" % step)
            try:
                fn()
            except Exception as e:
                bad.append(step)
                self.err("刷新「%s」失败：%s" % (step, human(str(e))))
        return bad

    def sync_editor(self):
        """sv 变了（载入/保存）就重建 GameEditor。"""
        self.g = game.GameEditor(self.sv) if self.sv else None

    def export_report(self):
        if not self.doc:
            return
        p = filedialog.asksaveasfilename(
            title="导出报告", defaultextension=".txt",
            initialfile="画迹2存档报告.txt", filetypes=[("文本", "*.txt")])
        if not p:
            return
        L = self.sv.summary_lines() if self.sv else ["（这个文件不是本作存档）"]
        if self.sv:
            L += ["", "金钱 = %s　步数 = %s" % (self.sv.gold(), self.sv.steps()),
                  "开关/变量 = %d / %d" % self.sv.counts(),
                  "防作弊校验 = %s" % ("正常" if not self.sv.check_locks()
                                       else "不一致 %r" % self.sv.check_locks()),
                  "", "角色："]
            for aid, a in self.sv.actors():
                L.append("  #%-3d %s" % (aid, self.sv.actor_summary(a)))
                L.append("       技能 = %s" % self.sv.skill_names(a))
                L.append("       五维 = %s" % self.sv.attr_items(a))
            L += ["", "队伍物品："]
            for kid, nm, cnt in self.sv.item_rows():
                L.append("  #%-4d %-20s x%s" % (kid, nm, cnt))
        try:
            open(p, "w", encoding="utf-8").write("\n".join(L) + "\n")
            self.set_status("报告已导出：%s" % p)
            messagebox.showinfo("导出报告", "已写出：\n%s" % p, parent=self.root)
        except OSError as e:
            self.err(e)

    def export_plain(self):
        if not self.doc:
            return
        p = filedialog.asksaveasfilename(
            title="导出明文（给高级用户）", defaultextension=".bin",
            initialfile=os.path.basename(self.doc.path) + ".plain",
            filetypes=[("二进制", "*.bin"), ("全部", "*.*")])
        if not p:
            return
        try:
            open(p, "wb").write(self.doc.raw)
            self.set_status("明文已导出：%s" % p)
        except OSError as e:
            self.err(e)

    # ================================================== 1 概览
    def fill_info(self, guard_rows=None):
        if not self.sv:
            if self.doc:
                self.txt_info.delete("1.0", "end")
                self.txt_info.insert("1.0", "（这个文件不是本作存档，"
                                            "只有「全部解析数据」页可用）")
            return
        L = self.sv.summary_lines()
        L += ["", "金钱 = %s（上限 %d）　步数 = %s"
              % (self.sv.gold(), game.MAX_GOLD, self.sv.steps()),
              "存档次数 = %s　战斗次数 = %s"
              % (self.sv.sys_get("@save_count"), self.sv.sys_get("@battle_count")),
              "开关/变量 = %d / %d" % self.sv.counts()]
        bad = self.sv.check_locks()
        L.append("Lock 校验和 = %s" % ("全部正常" if not bad
                                        else "不一致 %d 处" % len(bad)))
        self.txt_info.delete("1.0", "end")
        self.txt_info.insert("1.0", "\n".join(L))
        self.var_gold.set(str(self.sv.gold()))
        self.var_steps.set(str(self.sv.steps()))
        for var, name in ((self.var_savecnt, "@save_count"),
                          (self.var_battlecnt, "@battle_count")):
            v = self.sv.sys_get(name)
            var.set("" if v is None else str(v))
        # 祈福池 4 个储备量回填（2026-10-04 加回控件）
        if hasattr(self, "var_bless") and self.g:
            for key, _cn, val in self.g.blessing_rows():
                self.var_bless[key].set(str(val))
        self.var_lock.set("防作弊检测：%s"
                          % ("Lock 校验和正常" if not bad
                             else "Lock 不一致 %d 处，点「防作弊检测并修复」"
                             % len(bad)))
        if self.g:
            ch = M.value_of(save._deref(
                save.ivar(self.sv.section("system"), "@cheated")))
            L2 = ("作弊标记 @cheated = %r" % (ch,))
            if ch:
                L2 += "　← 游戏已判定作弊：20 分钟后警告、25 分钟后强制退出，" \
                      "点「清除作弊标记」"
            L.append(L2)
        try:
            self.guard_check(guard_rows)
        except Exception:
            pass

    def apply_quick(self):
        if not self.sv:
            messagebox.showinfo("提示", "这个文件不是本作存档。", parent=self.root)
            return
        clamped_msg = None
        try:
            if self.var_gold.get().strip():
                want = parse_num(self.var_gold.get())
                if self.g:
                    # 统一入口：钳到安全值 + Lock @master + 游戏金钱账一起同步
                    got, clamped = self.g.set_gold(want)
                    if clamped:
                        clamped_msg = (
                            "金钱 %d 超过上限 %d，已自动改为 %d（上限的 5/6，"
                            "留安全余量，游戏里怎么花钱赚钱都不会被判定作弊）"
                            % (want, game.MAX_GOLD, got))
                        self.var_gold.set(str(got))
                else:
                    self.sv.set_gold(want)
            if self.var_steps.get().strip():
                self.sv.set_steps(parse_num(self.var_steps.get()))
            if self.var_savecnt.get().strip():
                self.sv.sys_set("@save_count",
                                parse_num(self.var_savecnt.get()))
            if self.var_battlecnt.get().strip():
                self.sv.sys_set("@battle_count",
                                parse_num(self.var_battlecnt.get()))
            # 祈福池储备（4 个值共用同一个「应用」按钮）
            if self.g and hasattr(self, "var_bless"):
                for key, _cn, _old in self.g.blessing_rows():
                    raw = self.var_bless[key].get().strip()
                    if raw:
                        self.g.set_blessing(key, parse_num(raw))
        except Exception as e:
            messagebox.showerror("修改失败", human(str(e)), parent=self.root)
            return
        self.doc.dirty = True
        self.mark_dirty()
        self.fill_info()
        self.fill_party()
        self.set_status("已应用（记得点「保存修改」）")
        if clamped_msg:
            messagebox.showinfo("金钱超限已自动调整", clamped_msg,
                                parent=self.root)

    def detect_and_fix_cheats(self):
        """「防作弊检测并修复」：游戏的全部作弊触发点一次查完、一次修好。

        检查/修复范围：
          ① Lock 校验和（金钱等数值的 @master）；
          ② 上限规则（金钱超过 MAX_GOLD 压到 5/6；等级/召唤兽/
             仓库页/五维）；
          ③ 五类 Change 记账（金钱/物品/变量/人气/贡献）对齐实际值；
          ④ @cheated 置回 Ruby false、@keyword 清空（VNE/NE!/修改器关键字）；
          ⑤ 机器码绑定（**只提示，不动手** —— 改机器码去「机器码」页）。
        """
        if not self.g:
            return
        try:
            rows = self.g.anti_cheat_report()
        except Exception as e:
            self.err(e)
            return
        bad = [r for r in rows if r[3]]
        if not bad:
            self.fill_info()
            messagebox.showinfo(
                "防作弊检测并修复",
                "共检查 %d 项，未发现异常 ✔\n"
                "（Lock 校验和、金钱等上限、五类记账、作弊标记 @cheated/@keyword、"
                "机器码）" % len(rows), parent=self.root)
            return
        listing = "\n".join("  · %s：当前 %s，应为 %s" % (r[0], r[1], r[2])
                            for r in bad[:15])
        if len(bad) > 15:
            listing += "\n  · …（其余 %d 项）" % (len(bad) - 15)
        if not self.confirm(
                "检测到 %d 项作弊风险" % len(bad),
                "发现这些会被游戏判定作弊的问题：\n\n%s\n\n"
                "现在全部修复？\n"
                "（金钱超限会压到 %d；Lock、五类记账会重算对齐；"
                "@cheated/@keyword 会清掉；修复前会自动备份）"
                % (listing, game.SAFE_GOLD)):
            return
        try:
            # 修之前先在“存档管理”目录留一份磁盘原件（90 秒去重）
            try:
                backup.auto_backup_once(self.doc.path)
            except Exception:
                pass
            done = self.g.fix_anti_cheat()
        except Exception as e:
            messagebox.showerror("修复失败", human(str(e)), parent=self.root)
            return
        if done:
            self.mark_dirty()
        self.refresh_panels()
        messagebox.showinfo(
            "防作弊检测并修复",
            "共检查 %d 项、修复 %d 项：\n  " % (len(rows), len(done))
            + ("\n  ".join(done) if done else "（无需修改）")
            + "\n\n记得点「保存修改」写回存档。", parent=self.root)

    # 旧名保留（历史版本按钮/测试入口），等价于新的综合检测修复
    def fix_locks(self):
        self.detect_and_fix_cheats()

    # ================================================== 防作弊体检
    def guard_check(self, rows=None):
        """把游戏自己的检查规则跑一遍，结果显示在表里。

        `rows`：外面已经算好的体检结果（保存流程里刚算过），给了就用它，
        省掉一次 anti_cheat_report（要扫 Lock / 五类记账 / 逐物品校验）。
        """
        self.tv_guard.delete(*self.tv_guard.get_children())
        if not self.g:
            return
        if rows is None:
            try:
                rows = self.g.anti_cheat_report()
            except Exception as e:
                self.err(e)
                return
        for i, (name, cur, limit, bad, why) in enumerate(rows):
            iid = "g%d" % i
            self._guard_notes[iid] = ("❌ " + why) if bad else why
            self.tv_guard.insert("", "end", iid=iid,
                                 values=(name, cur, limit))
        n_bad = len([r for r in rows if r[3]])
        over = [r for r in rows if r[3]]
        flag = [r for r in over
                if ("作弊标记" in r[0] or "作弊记录" in r[0])]
        others = [r for r in over
                  if ("作弊标记" not in r[0] and "作弊记录" not in r[0])]
        tips = []
        if flag:
            tips.append("⚠ 存档带着作弊标记 @cheated / @keyword 记录：游戏 20 分钟后"
                        "开始“惩罚”（画面转圈/缩放），25 分钟后弹「存档异常」并退出，"
                        "战斗中还会报 disposed sprite 崩掉 → 点「防作弊检测并修复」")
        if others:
            tips.append("⚠ 还有 %d 项异常（超限/记账不符/校验和）：%s → "
                        "点「防作弊检测并修复」或「一键按规则修复」"
                        % (len(others), "、".join(r[0] for r in others)[:130]))
        if not tips:
            tips.append("✔ 体检 %d 项全部正常（含 Lock 校验和与五类记账）" % len(rows))
        try:
            self.var_cheat.set("\n".join(tips))
        except Exception:
            pass
        self.set_status("防作弊体检：%d 项，其中 %d 项有问题%s"
                        % (len(rows), n_bad,
                           "（点「一键按规则修复」）" if n_bad else " ✔"))
        return n_bad

    def guard_fix(self):
        if not self.g:
            return
        try:
            done = self.g.fix_anti_cheat()
        except Exception as e:
            messagebox.showerror("修复失败", human(str(e)), parent=self.root)
            return
        if done:
            self.mark_dirty()
            self.refresh_panels()
        self.guard_check()
        messagebox.showinfo("防作弊体检",
                            ("已处理：\n  " + "\n  ".join(done)) if done
                            else "没有需要处理的。", parent=self.root)

    def guard_clear(self):
        if not self.g:
            return
        try:
            done = self.g.clear_cheat_flag()
        except Exception as e:
            messagebox.showerror("操作失败", human(str(e)), parent=self.root)
            return
        if done:
            self.mark_dirty()
            self.fill_info()
        self.guard_check()
        messagebox.showinfo("清除作弊标记",
                            ("已处理：\n  " + "\n  ".join(done)) if done
                            else "存档里没有作弊标记（@cheated 已经是 false）。",
                            parent=self.root)

    def guard_resync(self):
        if not self.g:
            return
        try:
            n = self.g.resync_security()
        except Exception as e:
            messagebox.showerror("同步失败", human(str(e)), parent=self.root)
            return
        if n:
            self.mark_dirty()
        self.guard_check()
        self.fill_party()
        messagebox.showinfo("物品计数校验",
                            "已把 %d 件物品的计数对齐到背包实际数量。" % n if n
                            else "已经全部对得上。", parent=self.root)

    def guard_fix_all(self):
        """把游戏目录下**所有存档**（主存档 + AutoSave/*）的作弊标记/超限一起清掉。

        为什么要这个：AutoSave 里也可能带着 @cheated —— 读那种档一样会被惩罚
        （20 分钟后画面转圈，25 分钟后弹「存档异常」直接退出）。
        """
        if not self.doc:
            return
        paths = game.save_files(self.doc.path)
        self.set_status("正在检查 %d 个存档…" % len(paths))
        try:
            self.root.update_idletasks()
        except Exception:
            pass
        bad = []
        for p in paths:
            try:
                _b, _d, over = game.fix_save_file(p, dry_run=True)
                if over:
                    bad.append((p, over))
            except Exception as e:
                self.err(e)
        if not bad:
            messagebox.showinfo("清理所有存档",
                                "检查了 %d 个存档（含 AutoSave），"
                                "全都没有超限项/作弊标记 ✔" % len(paths),
                                parent=self.root)
            self.set_status("所有存档都干净")
            return
        txt = "\n".join("  · %s：%s" % (os.path.basename(p),
                                       "、".join(r[0] for r in ov[:4]))
                         for p, ov in bad[:10])
        if not self.confirm("有 %d 个存档要被游戏惩罚" % len(bad),
                            "这些存档带着超限项/作弊标记（读它们都会触发惩罚）：\n\n"
                            "%s\n\n全部按规则修好？（各自会先备份一份）" % txt):
            return
        n = 0
        cur_fixed = False
        for p, _ov in bad:
            try:
                _b, done, _o = game.fix_save_file(p)
                if done:
                    n += 1
                if os.path.abspath(p) == os.path.abspath(self.doc.path):
                    cur_fixed = True
            except Exception as e:
                self.err(e)
        if cur_fixed and not self.doc.dirty:
            self.load(self.doc.path, quiet=True)     # 当前档被改过 → 重新载入
        else:
            self.refresh_panels()
        messagebox.showinfo("清理所有存档",
                            "已修好 %d 个存档（各自备份在 .huaji2-save-editor）。\n\n"
                            "如果游戏里已经弹过「存档异常」，请把游戏「整个关掉再重开」；"
                            "读档后就不会再被惩罚了。" % n, parent=self.root)

    def warn_cheat_after_load(self, quiet=False, rows=None):
        """载入后如果存档带作弊标记 → 立刻提醒（惩罚 20 分钟后开始、25 分钟后强退）。

        `rows`：`load()` 里刚算好的体检表（概览页画的就是它），传进来就不再重算
        —— 一份档扫一遍 Lock / 记账 / 逐物品要 ~0.1 秒，载入路径上只该算一次。

        返回是否真的提醒过（测试用；也方便上层决定要不要再提示一次）。
        """
        if not self.g or quiet:
            return False
        if rows is None:
            try:
                rows = self.g.anti_cheat_report()
            except Exception:
                return False
        over = [r for r in rows if r[3]]
        flag = [r for r in over if ("作弊标记" in r[0] or "作弊记录" in r[0])]
        if not flag:
            return False
        if self.confirm(
                "这个存档被游戏标记了作弊（@cheated）",
                "游戏会在 20 分钟后开始“惩罚”（画面转圈/缩放），25 分钟后弹\n"
                "「存档异常」直接退出；战斗中还会报 RGSSError: disposed sprite 崩掉。\n\n"
                "要现在顺手修好吗？（推荐）\n"
                "点「是」= 按规则修数值 + 清作弊标记 + 同步物品计数，之后 Ctrl+S 保存\n"
                "点「否」= 先不管（概览页随时可以点按钮处理）"):
            self.guard_autofix()
            self.refresh_panels()
            self.set_status("已清除作弊标记 —— 记得点「保存修改」（Ctrl+S）")
        return True

    # ================================================== 2 数据树（懒加载）
    def _kids(self, node):
        """返回 [(显示名, 子节点, 中文说明), ...]。

        以前 Hash 的键直接用 `value_of()`，而符号（SymbolNode）没有 `.value`，
        于是满屏都是 `[None]`；现在走 `nodetext.children_of()`：
        符号写成 `:system`，并且把 `fieldnames` 里的中文说明带出来。
        """
        return nodetext.children_of(node)

    def _tree_tip_motion(self, event):
        """数据树节点悬浮 → 显示说明（浮窗）。"""
        iid = self.tree.identify_row(event.y)
        note = self._tree_notes.get(iid) if iid else None
        if not note or note.endswith(":?") or note == "…":
            self._tip_hide()
            return
        # 只在不同 iid 时刷新 tooltip，防闪烁
        if getattr(self, "_tip_key", None) == ("tree", iid):
            return
        self._tip_show(note, self.tree.winfo_rootx() + event.x + 10,
                       self.tree.winfo_rooty() + event.y + 10,
                       key=("tree", iid))

    def _guard_tip_motion(self, event):
        """防作弊体检条目悬浮 → 浮窗显示该条的具体说明。"""
        iid = self.tv_guard.identify_row(event.y)
        note = self._guard_notes.get(iid) if iid else None
        if not note:
            self._tip_hide()
            return
        if getattr(self, "_tip_key", None) == ("guard", iid):
            return
        self._tip_show(note, self.tv_guard.winfo_rootx() + event.x + 10,
                       self.tv_guard.winfo_rooty() + event.y + 10,
                       key=("guard", iid))

    def _add_stub(self, iid):
        node = self.nodes.get(iid)
        if node is None or not self._kids(node):
            return
        self.tree.insert(iid, "end", iid="%s:?" % iid, text="…（展开以加载）",
                         values=("", ""))

    def fill_tree(self):
        self.tree.delete(*self.tree.get_children())
        self.nodes.clear()
        self.loaded.clear()
        self._tree_notes = {}
        if not self.doc:
            return
        for i, node in enumerate(self.doc.top_level()):
            iid = "r%d" % i
            self.tree.insert("", "end", iid=iid,
                             text="#%d %s" % (i, doctree.describe(node)),
                             values=("", ""), open=False)
            self.nodes[iid] = node
            self._add_stub(iid)

    def on_open(self, event=None):
        iid = self.tree.focus()
        if iid:
            self._fill_children(iid)
        for x in self.tree.selection() or ():
            self._fill_children(x)

    def _fill_children(self, iid, limit=CHILD_LIMIT):
        if iid in self.loaded:
            return
        self.loaded.add(iid)
        for c in self.tree.get_children(iid):
            if str(c).endswith(":?"):
                self.tree.delete(c)
        node = self.nodes.get(iid)
        if node is None:
            return
        kids = self._kids(node)
        for n, row in enumerate(kids[:limit]):
            label, kid, note = row[0], row[1], row[2]
            iid2 = "%s|%d" % (iid, n)
            if not note:
                note = nodetext.type_label(kid)
            self._tree_notes[iid2] = note
            self.tree.insert(iid, "end", iid=iid2, text=label,
                             values=(nodetext.type_label(kid),
                                     short(nodetext.brief(kid, 60))))
            self.nodes[iid2] = kid
            self._add_stub(iid2)
        if len(kids) > limit:
            self.tree.insert(iid, "end", iid="%s|more" % iid,
                             text="…（共 %d 项，只显示前 %d 项，用搜索定位）"
                                  % (len(kids), limit), values=("", ""))

    def _collapse(self, iid):
        for c in self.tree.get_children(iid):
            self._collapse(c)
        try:
            self.tree.item(iid, open=False)
        except Exception:
            pass

    def collapse_all(self):
        for r in self.tree.get_children(""):
            self._collapse(r)
        self.set_status("已全部折叠")

    def on_select(self, event=None):
        sel = self.tree.selection()
        if not sel:
            return
        node = self.nodes.get(sel[0])
        if node is None:
            return
        self.txt_node.delete("1.0", "end")
        self.txt_node.insert("1.0", node_detail(node))

    def tree_menu(self, event=None):
        iid = self.tree.identify_row(event.y) if event else None
        if iid:
            self.tree.selection_set(iid)
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    def tree_edit_value(self):
        sel = self.tree.selection()
        if not sel or not self.doc:
            return
        node = self.nodes.get(sel[0])
        if node is None:
            return
        node = save._deref(node)
        cur = value_of(node)
        if isinstance(cur, (list, tuple)):
            messagebox.showinfo("提示", "这是容器节点，请选它的子项。", parent=self.root)
            return
        dlg = EditDialog(self.root, cur, node.type)
        self.root.wait_window(dlg)
        if dlg.result is None:
            return
        try:
            self.doc.set_value(node, dlg.result)
        except Exception as e:
            messagebox.showerror("修改失败", human(str(e)), parent=self.root)
            return
        self.doc.dirty = True
        self.mark_dirty()
        self.tree.set(sel[0], "value", short(describe_value(node)))
        self.set_status("已改：%s = %s" % (node.type, short(describe_value(node))))

    def tree_copy(self):
        sel = self.tree.selection()
        if not sel:
            return
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(str(value_of(self.nodes.get(sel[0]))))
            self.set_status("已复制值")
        except Exception as e:
            self.err(e)

    # ----------------------------------------- 全局搜索（在模型里搜，不建树）
    def global_search(self, event=None):
        q = self.var_search.get().strip().lower()
        if not q or not self.doc:
            return
        budget = [400000]
        out = []
        for i, node in enumerate(self.doc.top_level()):
            self._walk_search(node, i, "#%d" % i, q, out, budget, 0)
            if len(out) >= 200:
                break
        self.hits = out
        self.tv_hits.delete(*self.tv_hits.get_children())
        for n, (path, t, v, top, labels) in enumerate(out):
            self.tv_hits.insert("", "end", iid="h%d" % n, values=(path, t, v))
        self.set_status("搜到 %d 条%s" % (len(out), "（最多列 200 条）" if out else ""))

    def _walk_search(self, node, top, path, kw, out, budget, depth):
        if budget[0] <= 0 or depth > 24 or len(out) >= 200:
            return
        budget[0] -= 1
        node2 = node.target if isinstance(node, M.LinkNode) and node.target is not None else node
        if node2 is None:
            return
        txt = str(nodetext.brief(node2, 200))
        if kw in txt.lower() or kw in path.lower():
            out.append((path, nodetext.type_label(node2), short(txt, 60), top,
                        path.split("|")[1:]))
        for row in self._kids(node2):
            self._walk_search(row[1], top, path + "|" + row[0], kw, out, budget,
                              depth + 1)

    def clear_search(self):
        self.hits = []
        self.tv_hits.delete(*self.tv_hits.get_children())
        self.var_search.set("")
        self.set_status("已清空搜索结果")

    def goto_search_hit(self, event=None):
        sel = self.tv_hits.selection()
        if not sel or not self.hits:
            return
        path, t, v, top, labels = self.hits[int(sel[0][1:])]
        iid = self._reveal(top, labels)
        if iid:
            self.tree.see(iid)
            self.tree.selection_set(iid)
            self.on_select()
            self.set_status("已定位到 %s" % path)
        else:
            self.set_status("命中的项排在某一层的前 %d 项之后，界面上没建出来"
                            % CHILD_LIMIT)

    def _reveal(self, top_index, labels):
        """按标签路径一层层展开（每层找第一个同名子项）。"""
        iid = "r%d" % top_index
        for label in labels:
            self._fill_children(iid)
            nxt = None
            for c in self.tree.get_children(iid):
                txt = str(c)
                if txt.endswith(":?") or txt.endswith("|more"):
                    continue
                if self.tree.item(c, "text") == label:
                    nxt = c
                    break
            if nxt is None:
                return None
            self.tree.item(iid, open=True)
            iid = nxt
        self.tree.item(iid, open=True)
        return iid

    # ================================================== 3 角色
    def fill_actors(self, keep_id=None):
        """重建角色列表。keep_id 指定时保持选中的那些行（单个 id 或列表都给）
        （apply_actor 改了人再刷新，别把选中跳回第一个 —— 会让人以为改错了）。
        ⚠ 列表 2026-10-07 起可多选，选中是**一组**，恢复时要整组恢复。
        """
        sel = self.tv_actor.selection()
        if keep_id is None and sel:
            keep_id = list(sel)
        elif isinstance(keep_id, str):
            keep_id = [keep_id]
        self.tv_actor.delete(*self.tv_actor.get_children())
        self.actor_rows.clear()
        if not self.sv:
            self._actor_sel_done = ()           # 列表空了：排队的事件别再来刷
            return
        for n, (aid, a) in enumerate(self.sv.actors(), 1):
            iid = "a%d" % aid
            self.tv_actor.insert("", "end", iid=iid, values=(
                n, aid, self.sv.actor_name(a),
                (self.g.actor_sect_name(a) or "（认不出）") if self.g else "",
                self.sv.actor_field(a, "@level"),
                self.sv.actor_field(a, "@hp"), self.sv.actor_field(a, "@mp"),
                self.sv.actor_field(a, "@class_id")))
            self.actor_rows[iid] = a
        kids = self.tv_actor.get_children()
        keep = [i for i in (keep_id or []) if i in self.actor_rows]
        if keep:
            self.tv_actor.selection_set(keep)       # 多选要整组恢复
            self.tv_actor.see(keep[0])
        elif kids:
            self.tv_actor.selection_set(kids[0])
        # 选中那一行**当场加载**，别指望 <<TreeviewSelect>>：那个事件是排队的，
        # 等它跑起来时 Tk 还在一批控件 churn 的几何脏状态里 —— 同一个
        # load_actor() 从 0.04s 涨到 0.5s+（2026-10-07 载入优化实测）。
        # 记下"这个选中已经刷过"，排队的那次就会被 on_actor_select 直接跳过。
        self._actor_sel_done = tuple(self.tv_actor.selection())
        self.load_actor()

    def on_actor_select(self):
        """角色列表选中变化 → 刷右侧详情。

        ⚠ 选中没变就**直接返回**：`fill_actors` 已经当场刷过一遍了，而它
          `selection_set` 排队的那个 `<<TreeviewSelect>>` 随后还会来一次；
          不挡的话同一个人要被刷两遍（第二遍还在几何脏状态里，更贵）。
        """
        sel = tuple(self.tv_actor.selection())
        if sel == getattr(self, "_actor_sel_done", None):
            return
        self._actor_sel_done = sel
        self.load_actor()

    def current_actor(self):
        sel = self.tv_actor.selection()
        return self.actor_rows.get(sel[0]) if sel else None

    def selected_actors(self):
        """列表里选中的**全部**角色（按行序）。多选 = 一次改一批。"""
        return [self.actor_rows[i] for i in self.tv_actor.selection()
                if i in self.actor_rows]

    def load_actor(self):
        a = self.current_actor()
        if a is None or not self.sv:
            self.load_actor_skills(None)    # 没角色/没存档 → 别留着上一个人的技能
            return
        for k, var in self.actor_vars.items():
            if k == "#next_exp":
                v = self.g.next_level_exp(a)      # 查表：升级经验
            elif k == "#level":
                v = self.g.actor_level(a)         # 只读展示（改等级走「一键满级」）
            elif k == "@exp":
                v = self.g.exp(a)
            else:
                v = self.sv.actor_field(a, k)
            var.set("" if v is None else str(v))
        attrs = dict(self.sv.attr_items(a))
        for k, var in self.attr_vars.items():
            var.set(str(attrs.get(k, "")))
        sk = "、".join("#%d %s" % (i, nm) for i, nm in self.sv.skill_names(a))
        eq = "、".join("槽%d:%s#%s" % (i, "武器" if c == 0 else "防具", i2)
                       for i, c, i2 in self.sv.equips(a))
        lv = self.sv.actor_field(a, "@level") or 0
        cur = self.g.exp(a)
        nxt = self.g.next_level_exp(a)
        lim = self.g.limit_exp(a)
        # 累计获得经验不再给输入框（改它没意义），但封顶这件事必须能看见
        # —— 挂在概览里 + 做成悬浮提示。
        gate = not self.g.limit_exp_on(a)
        self._actor_tip_note = self._actor_note(
            self.sv.actor_name(a), lv, cur, nxt, lim, gate)
        if lv >= game.MAX_LEVEL_ACTOR:
            exp_txt = "已满级（上限 %d），游戏不再发经验" % game.MAX_LEVEL_ACTOR
        elif nxt is None:
            exp_txt = "—（等级越界，查不到门槛）"
        else:
            exp_txt = "%d（还差 %d）" % (nxt, max(0, nxt - cur))
        # 门派（存档 @sect_id）：正常游戏里角色学的技能就是本门派那 10 个，
        # 所以把「是不是本门派的技能」直接摆出来（非本门派的多半是改出来的）。
        sect_id = self.g.actor_sect_id(a)
        sect_nm = self.g.actor_sect_name(a)
        off = self.g.off_sect_skills(a)
        apps, app_idx = self.g.actor_appellations(a)
        app_show = apps[app_idx] if 0 <= app_idx < len(apps) else None
        L = ["名字：%s（存档 @name）" % self.sv.actor_name(a),
             "级别：%s（上限 %d）" % (lv, game.MAX_LEVEL_ACTOR),
             "获得经验：%s（本级内）" % cur,
             "升级经验：%s" % exp_txt,
             "累计获得经验：%s%s" % (lim, "　⚠ 已封顶" if gate else ""),
             "门派：%s（@sect_id=%s，本门派技能 %d 个）"
             % (sect_nm or "（认不出）", sect_id, len(self.g.sect_skills(a))),
             self._appellation_line(a, apps, app_show),
             "防作弊：五维总点数 %d（上限 = 等级*10+500 = %d）"
             % (self.g.point_num(a), lv * 10 + 500),
             "已学技能：%s" % (sk or "（无）"),
             "装备：%s" % (eq or "（无）"),
             "五维/潜能：%s" % "、".join("%s=%s" % (k, v)
                                        for k, v in self.sv.attr_items(a))]
        if off:
            # ⚠ 不写「多半是改出来的」：游戏支持换门派（剧情脚本直接改 @sect_id），
            # 而 learn_skill 从不清理换门派前的技能 → 老技能会留着（2026-09-20 核过真档）。
            L.append("非本门派技能：%s（不属于当前门派体系；换门派/剧情发技能都会留着）"
                     % "、".join("#%d %s" % (i, nm or "?") for i, nm in off))
        n = len(self.g.babies(a))
        L.append("携带召唤兽：%d 只（见「召唤兽」页）" % n)
        self.txt_actor.delete("1.0", "end")
        self.txt_actor.insert("1.0", "\n".join(L))
        self.load_actor_skills(a)       # 右下角的技能一览（可编辑）

    def _appellation_line(self, a, apps, app_show):
        """属性文本里的「称谓：…」那一行（游戏里叫称谓，存档字段 `@appellations`）。

        门派称谓（「五庄观弟子」）是拜师事件硬编码发下来的，**跟门派走**；
        存档里 `[[称谓...], 下标]`，下标 -1 = 不显示。2026-09-27 川指出：
        光改 `@sect_id` 不会动它，所以这里把「称谓和门派对不上」直接摆出来。
        """
        if not apps:
            return "称谓：（没有）"
        line = "称谓：%s（共 %d 个：%s）" % (
            ("显示「%s」" % app_show) if app_show else "不显示（下标 -1）",
            len(apps), "、".join(apps))
        sect_id = self.g.actor_sect_id(a)
        stale = [n for n, s in self.g.sect_appellations_of(a) if s != sect_id]
        if stale:
            line += ("　⚠ 「%s」不是当前门派的 —— 用「转门派」/「清空门派」回收"
                     % "、".join(stale))
        elif sect_id and not any(self.g.sect_appellations_of(a)):
            want = self.g.sect_appellation_name(sect_id)
            if want:
                line += "　⚠ 缺本门派称谓（可点「转门派」补上）"
        return line

    def _actor_note(self, name, lv, cur, nxt, lim, gate):
        """鼠标移到「属性概览」上要看的那段提醒（满级 / 封顶 / 升级进度）。"""
        P = ["【%s】" % name,
             "级别 %s / 上限 %d" % (lv, game.MAX_LEVEL_ACTOR)]
        if lv >= game.MAX_LEVEL_ACTOR:
            P.append("⚠ 已满级：游戏对满级角色直接不发经验，")
            P.append("  改「获得经验」在游戏里看不出任何变化。")
            P.append("  「经验拉满」「一键满级」对这个角色都是空操作。")
        elif gate:
            P.append("⚠ 累计获得经验 %d 已超过 %d：" % (lim, self.g.LIMIT_EXP_MAX))
            P.append("  游戏判定「经验累计获得已达上限」，")
            P.append("  该角色再获得的经验全部作废（等级也涨不上去）。")
            P.append("  用「一键按规则修复」里的清零可解除。")
        elif nxt is None:
            P.append("升级经验查不到（等级越界），请确认等级在 1..%d"
                     % game.MAX_LEVEL_ACTOR)
        else:
            P.append("升级经验 %d，还差 %d 点获得经验" % (nxt, max(0, nxt - cur)))
            P.append("累计获得经验 %d（距体验版封顶 %d 还差 %d）"
                     % (lim, self.g.LIMIT_EXP_MAX,
                        max(0, self.g.LIMIT_EXP_MAX - lim)))
        P.append("")
        P.append("提示：「获得经验」光改游戏里不会升级 ——")
        P.append("人物只能在地图界面点「升级」按钮（一次一级）。")
        P.append("想自己点升级用「经验拉满」（只给经验）；要直接满级用")
        P.append("「一键满级」（连着等级一起写）。")
        return "\n".join(P)

    def _actor_tip_motion(self, event):
        """鼠标在「属性概览」上移动 → 浮窗显示满级/封顶等提醒。"""
        note = getattr(self, "_actor_tip_note", "")
        if not note:
            self._tip_hide()
            return
        if getattr(self, "_tip_key", None) == "actor":
            return                      # 已经在显示同一段，别反复重建闪烁
        self._tip_show(note, self.txt_actor.winfo_rootx() + event.x + 10,
                       self.txt_actor.winfo_rooty() + event.y + 10,
                       key="actor")

    def apply_actor(self):
        """「应用修改」：写进**选中的全部角色**（多选 = 一次改一批）。"""
        actors = self.selected_actors()
        if not actors:
            messagebox.showinfo("提示", "先在上面选一个角色。", parent=self.root)
            return
        try:
            for a in actors:
                self._apply_actor_one(a)
        except Exception as e:
            messagebox.showerror("修改失败", human(str(e)), parent=self.root)
            return
        self.doc.dirty = True
        self.mark_dirty()
        self.fill_actors(list(self.tv_actor.selection()))
        self.load_actor()
        self.set_status("已改 %d 个角色（记得点「保存修改」）" % len(actors)
                        if len(actors) > 1
                        else "角色已改（记得点「保存修改」）")

    def _apply_actor_one(self, a):
        """写单个角色：基础字段 + 中文属性（`apply_actor` 的内部动作）。"""
        # ⚠ 2026-09-20：**「级别」输入框已去掉**，这里不再处理等级
        # （等级只有「一键满级」会连带写，见 actor_preset / game.actor_exp_full）。
        for k, var in self.actor_vars.items():
            if k.startswith("#"):
                continue          # 只读项（「升级经验」是查表算的）
            raw = var.get().strip()
            if raw == "":
                continue
            if k == "@exp":
                self.g.set_exp(a, parse_num(raw))
            else:
                self.sv.set_actor_field(a, k, raw)
        for k, var in self.attr_vars.items():
            raw = var.get().strip()
            if raw == "":
                continue
            # @活力 等浮点字段原样回写也不能炸（parse_num 吃 '200.0'，
            # set_attr 按节点原类型写回）
            self.sv.set_attr(a, k, parse_num(raw))

    def actor_reset_limit_exp(self):
        """把所有角色的累计获得经验清零 —— 解「体验版经验已达上限」。

        「累计获得经验」已经不给输入框改了（改它没意义），但这个清零按钮有用：
        顶着封顶线的角色，游戏再也不发经验。放在概览浮窗的提示里指过来。
        """
        if not self.sv:
            return
        done = self.g.reset_limit_exp()
        if not done:
            messagebox.showinfo("不用清", "没有角色的累计获得经验是被顶着的。",
                                parent=self.root)
            return
        txt = "、".join("%s(%s)" % (n, v) for n, v in done)
        if not messagebox.askyesno(
                "清零累计获得经验",
                "会把下列角色的累计获得经验清零：\n%s\n\n"
                "（清零后体验版的经验上限重新计算，游戏里继续正常获得经验）\n"
                "确定吗？" % txt, parent=self.root):
            return
        self.doc.dirty = True
        self.mark_dirty()
        self.fill_actors()
        self.load_actor()
        self.set_status("已清零 %d 个角色的累计获得经验（记得点「保存修改」）"
                        % len(done))

    def actor_preset(self, what):
        """预设按钮：对列表里**选中的全部角色**生效（多选 = 一次改一批）。

        ⚠ 2026-10-07 川：以前只认 `current_actor()`（第一个选中项），多选之后
          点「经验拉满」只有第一个角色变 —— 改成整批。
        """
        actors = self.selected_actors()
        if not actors or not self.sv:
            return
        notes = []
        try:
            for a in actors:
                one = self._actor_preset_one(a, what)
                if one:
                    notes.append("%s：%s" % (self.sv.actor_name(a) or "?", one))
        except Exception as e:
            messagebox.showerror("修改失败", human(str(e)), parent=self.root)
            return
        self.doc.dirty = True
        self.mark_dirty()
        self.fill_actors(list(self.tv_actor.selection()))
        self.load_actor()
        if not notes:
            return
        if len(notes) == 1:
            self.set_status("角色预设：%s（记得点「保存修改」）" % notes[0])
        else:
            head = "、".join(notes[:3]) + ("…" if len(notes) > 3 else "")
            self.set_status("角色预设：%d 个角色已改（%s）（记得点「保存修改」）"
                            % (len(notes), head))

    def _actor_preset_one(self, a, what):
        """对单个角色做一次预设，返回一句说明（空串 = 没动）。"""
        if what == "expfull":
            # 「一键满级」：等级顶到满级 + 获得经验对齐满级门槛（一步到位，
            # 理由见 game.actor_exp_full：人物不会因经验多而自动升级）
            lv, wrote = self.g.actor_exp_full(a)
            return "等级→%d、获得经验→%s" % (lv, wrote)
        if what == "expfill":
            # 「经验拉满」：只写经验、**等级不动** —— 回游戏自己点升级
            wrote = self.g.actor_exp_fill(a)
            return "获得经验→%s（等级没动，回游戏自己点「升级」）" % wrote
        if what == "heal":
            for k, v in (("@hp", 9999), ("@mp", 9999), ("@tp", 100)):
                if self.sv.actor_field(a, k) is not None:
                    self.sv.set_actor_field(a, k, v)
            return "回满 HP/MP/愤怒"
        if what == "attr":
            for k, v in self.sv.attr_items(a):
                if isinstance(v, int):
                    self.sv.set_attr(a, k, v + 10)
            return "属性全 +10"
        if what == "reset_attr":
            # 洗点（= 游戏里拜师那一下）：五维/潜能回到等级自然成长值
            r = self.g.actor_reset_attr(a)
            if r is None:
                return "这个角色没有 @attr，没动"
            return "五维→%d、潜能→%d" % r
        return ""

    # ---------------------------------------------- 3.5 角色技能（@skills）
    # 2026-09-20：角色技能可视化编辑。和召唤兽页共用 _build_skill_editor 那一套控件，
    # 区别有两点（都在游戏脚本里确认过）：
    #   1) 角色技能**没有数量上限**，不用像召唤兽那样截断到 12 个；
    #   2) 游戏里「实际能用」的技能 = (@skills | added_skills | equip_skills).sort，
    #      这里只编 @skills（= original_skills），装备/升级给的技能不写回去。
    def load_actor_skills(self, a=None, grid=True):
        """刷右下角的技能一览 + 技能下拉（改完技能 load_actor 会调它）。

        `grid=False`：**不重建**左栏「门派技能」勾选清单 —— 给「直接点勾选框」
        那条路用（当前就在那个 Checkbutton 的回调里，重建会把它 destroy 掉）。
        """
        tree = getattr(self, "tv_actor_skills", None)
        if tree is None:
            return
        if a is None:
            a = self.current_actor()
        tree.delete(*tree.get_children())
        # 「门派」下拉跟着**换角色**走：默认站到 TA 自己的门派上（正常游戏里
        # 能学的就这些）。⚠ 只在换角色时切 —— 每次刷新都切会把用户手选的
        # 门派抢回去，想看看别的门派技能就没法看了。
        var_sect = getattr(self, "var_actor_sect", None)
        if var_sect is not None and a is not getattr(self, "_sect_actor", "\0None"):
            self._sect_actor = a
            label = ""                 # 没角色 → 留空
            # 直接站到 TA 自己的门派上（无门派角色就是「无门派」——
            # 2026-09-27 起下拉里有这一项了，不再留空）。
            # ⚠ 得确认这名字真在下拉里，别 set 进去一个 Combobox 认不出的值。
            if a is not None and self.g is not None:
                nm = self.g.actor_sect_name(a)
                if nm in sect_choice_labels():
                    label = nm
            var_sect.set(label)
        if a is None or self.g is None:
            if hasattr(self, "skp_actor"):
                self.skp_actor.set_source([])
                self.skp_actor.fill()
            if grid:
                self.rebuild_learn_grid()   # 没角色 → 左栏清单也清掉
            return
        meta = self._skills_meta()
        self.skp_actor.set_source([(sid, meta.get(sid, ("?", ""))[0])
                                   for sid in self.g.actor_skills(a)])
        self.skp_actor.fill()
        # 左栏「门派技能」清单跟着刷（勾选状态 = 存档真值）
        if grid:
            self.rebuild_learn_grid()

    # ---------------------------------------------- 3.6 门派技能（勾选 → 一键学习）
    def rebuild_learn_grid(self):
        """按「门派」下拉重建左栏「门派技能」勾选清单（**勾上 = 已学**）。

        清单 = 门派下拉当前选中的那个门派的技能（`$sects`，每门派 10 个）；
        没选门派（空串，无门派角色 / 还没载档）时列不出来 → 给一句话先让人选。
        勾选框直接反映存档 `@skills`（已学打勾、未学空着），点一下就立刻改写
        `@skills`（见 `actor_toggle_sect_skill`）；鼠标停在勾选框上弹技能介绍。
        """
        grid = getattr(self, "learn_grid", None)
        if grid is None:
            return
        for w in grid.winfo_children():
            w.destroy()
        self.learn_vars = {}
        self._learn_sids = []
        note = getattr(self, "var_learn_note", None)

        label = None
        var_sect = getattr(self, "var_actor_sect", None)
        if var_sect is not None:
            label = var_sect.get()
        sid = sect.SECT_NAME_TO_ID.get(label) if label else None
        if sid is None or sid == 0:
            if note is not None:
                a = self.current_actor() if self.g is not None else None
                if a is not None and self.g.actor_sect_id(a) == 0:
                    # 无门派角色（@sect_id=0）：提示别写成「还没选」，会让人以为漏点了
                    note.set("这个角色没有门派 —— 想学哪个门派的技能，"
                             "就在上面选哪个门派。")
                elif sid == 0:
                    # 用户自己把下拉切到「无门派」（角色其实有门派）
                    note.set("「无门派」没有门派技能。要看别的门派就在这里换一个。")
                else:
                    note.set("先在上面选一个门派，这里才会列出它的 10 个技能。")
            return
        sids = list(sect.sect_skill_ids(sid))
        if not sids:
            if note is not None:
                note.set("「%s」没有门派技能。" % label)
            return
        known = set()
        if self.g is not None:
            a = self.current_actor()
            if a is not None:
                known = set(self.g.actor_skills(a))
        meta = self._skills_meta() if self.g is not None else {}
        if note is not None:
            n_known = len([s for s in sids if s in known])
            note.set("%s · 共 %d 个（已学 %d，剩 %d 个可勾）"
                     % (label, len(sids), n_known, len(sids) - n_known))
        self._learn_sids = sids
        for i, s in enumerate(sids):
            r, c = i // 2, i % 2
            nm, dsc = meta.get(s) or ("#%d" % s, "")
            nm = nm or "#%d" % s
            got = s in known
            # 勾上 = 已学（不再 disabled、「（已学）」后缀也去掉 —— 勾没勾本身就是状态）
            var = self.tk.IntVar(value=1 if got else 0)
            self.learn_vars[s] = var
            cb = ttk.Checkbutton(grid, text=nm, variable=var,
                                 command=lambda _s=s: self.actor_toggle_sect_skill(_s))
            cb.grid(row=r, column=c, sticky="w", padx=(0, 8))
            # 悬停弹技能介绍（和右边技能一览一样）
            self._bind_tip(cb, "#%d %s\n%s\n勾上＝学会，取消＝忘掉（记得点「保存修改」）"
                           % (s, nm, dsc or "（没有说明）"))
        grid.columnconfigure(0, weight=1, uniform="lrn")
        grid.columnconfigure(1, weight=1, uniform="lrn")

    def actor_sect_invert(self):
        """门派技能清单「反选」：已学的忘掉、没学的学会（各写一次）。"""
        a = self.current_actor()
        if a is None or self.g is None or not self._learn_sids:
            messagebox.showinfo("提示", "左栏没有门派技能清单。\n"
                                        "先在「门派技能」里选一个门派。",
                                parent=self.root)
            return
        have = set(self.g.actor_skills(a))
        will_learn = [s for s in self._learn_sids if s not in have]
        will_forget = [s for s in self._learn_sids if s in have]
        if not will_learn and not will_forget:
            return
        if will_forget and not self.confirm(
                "反选门派技能",
                "反选「%s」的技能：\n学会 %d 个、忘掉 %d 个？"
                % (self.var_actor_sect.get(), len(will_learn),
                   len(will_forget))):
            return
        try:
            if will_forget:
                self.g.actor_forget_many(a, will_forget)
            if will_learn:
                self.g.actor_learn_many(a, will_learn)
        except Exception as e:
            messagebox.showerror("改不了", zh_error(e), parent=self.root)
            return
        self.mark_dirty()
        self.load_actor_skills(a)       # grid=True → 清单按新真值重建
        self.set_status("反选完成：学会 %d 个、忘掉 %d 个（记得点「保存修改」）"
                        % (len(will_learn), len(will_forget)))

    def actor_sect_none(self):
        """门派技能清单「全不选」：把本门派的技能全部忘掉。"""
        a = self.current_actor()
        if a is None or self.g is None or not self._learn_sids:
            messagebox.showinfo("提示", "左栏没有门派技能清单。\n"
                                        "先在「门派技能」里选一个门派。",
                                parent=self.root)
            return
        have = set(self.g.actor_skills(a))
        drop = [s for s in self._learn_sids if s in have]
        if not drop:
            self.set_status("本门派技能现在一个都没学")
            return
        if not self.confirm("忘掉门派技能",
                            "忘掉「%s」的技能 %d 个？"
                            % (self.var_actor_sect.get(), len(drop))):
            return
        try:
            self.g.actor_forget_many(a, drop)
        except Exception as e:
            messagebox.showerror("改不了", zh_error(e), parent=self.root)
            return
        self.mark_dirty()
        self.load_actor_skills(a)
        self.set_status("已忘掉本门派技能 %d 个（记得点「保存修改」）"
                        % len(drop))

    def actor_toggle_sect_skill(self, sid):
        """门派技能勾选框：勾上＝学会，取消＝忘掉（立刻写 `@skills` + 标 dirty）。

        ⚠ 这里**不重建勾选清单**（当前就在某个 Checkbutton 的回调里，重建等于把它
        `destroy` 掉）→ `load_actor_skills(..., grid=False)`。换角色 / 换门派时
        `rebuild_learn_grid` 会按存档真值把清单重建回来。
        """
        a = self.current_actor()
        var = (getattr(self, "learn_vars", None) or {}).get(sid)
        if a is None or self.g is None or var is None:
            return
        want = bool(var.get())
        try:
            if want:
                self.g.actor_learn_skill(a, sid)
            else:
                self.g.actor_forget_skill(a, sid)
        except Exception as e:
            messagebox.showerror("改不了", zh_error(e), parent=self.root)
            return
        self.mark_dirty()
        self.load_actor_skills(a, grid=False)
        self.update_learn_note()
        nm = self._skill_names().get(sid) or "#%d" % sid
        self.set_status("%s #%d %s（记得点「保存修改」）"
                        % ("已学会" if want else "已忘掉", sid, nm))

    def update_learn_note(self):
        """更新左栏「门派技能」下面那行统计（勾/取消之后要跟着变）。"""
        note = getattr(self, "var_learn_note", None)
        sids = list(getattr(self, "_learn_sids", []))
        if note is None or not sids:
            return
        known = set()
        a = self.current_actor() if self.g is not None else None
        if a is not None:
            known = set(self.g.actor_skills(a))
        n_known = len([s for s in sids if s in known])
        label = self.var_actor_sect.get() if hasattr(self, "var_actor_sect") else ""
        note.set("%s · 共 %d 个（已学 %d，剩 %d）"
                 % (label, len(sids), n_known, len(sids) - n_known))

    def actor_learn_checked(self):
        """「一键学习」＝ 把当前门派还没学的技能一次学满（勾选框同步打上勾）。

        走的是语义层 `actor_learn_skill`（= `@skills` 去重 + 排序），
        已学过的再学一遍也不会重复、不会报错。逐个点勾选框
        （`actor_toggle_sect_skill`）当然也行 —— 那是一次一个，这里是「全都要」。
        """
        a = self.current_actor()
        if a is None or self.g is None:
            messagebox.showinfo("提示", "先在角色列表选一个角色。",
                                parent=self.root)
            return
        sids = list(getattr(self, "_learn_sids", []))
        if not sids:
            messagebox.showinfo("提示", "左栏没有可学的门派技能。\n"
                                        "先在「门派技能」里选一个门派。",
                                parent=self.root)
            return
        known = set(self.g.actor_skills(a))
        left = [s for s in sids if s not in known]
        if not left:
            messagebox.showinfo("提示", "本门派技能这个角色已经全学会了。",
                                parent=self.root)
            return
        done, err = [], ""
        for s in left:
            try:
                self.g.actor_learn_skill(a, s)
                done.append(s)
            except Exception as e:      # 单个失败不打断其余的
                err = str(e)
        self.mark_dirty()
        self.load_actor()               # 会重建左栏清单 → 勾选框全部打上
        if err:
            self.set_status("已学会 %d 个技能，有 1 个失败：%s" % (len(done), err))
        else:
            self.set_status("已学会 %d 个技能：%s（记得点「保存修改」）"
                            % (len(done), "、".join("#%d" % s for s in done)))

    def actor_set_sect(self):
        """把**当前角色**的门派改成左栏下拉里选的那个（只写 `@sect_id`）。

        档位＝「只改门派」（2026-09-27 川选的 ①，见 `docs/待解决问题.md` 的「门派修改」一节）：
          * 只动门派本身 —— `@skills` / `@sect_data` / 属性一律不碰，和游戏里
            换门派的行为一致（`learn_skill` 从不清理旧门派技能，它们会留着）；
          * 下拉里有 13 项（无门派 + 12 门派，2026-09-27 川要求把无门派也放进来）。
            ⚠ 选「无门派」也是**只改门派、技能一个不动**（与转别的门派一致）；
            「连技能一起重置」只属于「清空门派」那个按钮
            （川 260927 22:5x：「无门派不清技能，清空门派才清技能」—— 两路**不**合并）；
          * 顺带把**称谓**对齐（`@appellations`）：回收旧门派称谓、补上新门派那个
            （2026-09-27 川指出原来不带这个）；门派本来就对、只是称谓不对时
            也能点这个按钮修（不会白写 `@sect_id`）；
          * 越界 id 的校验在 `GameEditor.set_actor_sect()` 里（写别的值游戏崩菜单）。
        """
        if self.g is None or self.sv is None:
            return
        a = self.current_actor()
        if a is None:
            messagebox.showinfo("提示", "先在角色列表选一个角色。",
                                parent=self.root)
            return
        var = getattr(self, "var_actor_sect", None)
        label = (var.get() if var is not None else "").strip()
        sid = sect.SECT_NAME_TO_ID.get(label)
        if sid is None:
            messagebox.showinfo("提示", "先在左边选一个门派（下拉里挑一个）。",
                                parent=self.root)
            return
        old_id = self.g.actor_sect_id(a)
        # 称谓（@appellations）：门派称谓跟门派走 —— 转门派时回收旧的、补上新的
        apps, app_idx = self.g.actor_appellations(a)
        cur_app = apps[app_idx] if 0 <= app_idx < len(apps) else None
        old_apps = self.g.sect_appellations_of(a)
        want_app = self.g.sect_appellation_name(sid)
        stale = [n for n, s in old_apps if s != sid]
        missing = bool(want_app) and not any(s == sid for _n, s in old_apps)
        # ⚠ 早退条件里**必须**算上称谓：真档里就有「门派对、称谓错」的角色
        #   （秦媚儿：@sect_id=5 女儿村，称谓却是「地府弟子」）—— 只看
        #   「门派一样」就早退，她就永远修不了。
        if old_id == sid and not stale and not missing:
            self.set_status("已经是「%s」了、称谓也没问题，无需改动" % label)
            return
        old_nm = self.g.actor_sect_name(a) or "（认不出：@sect_id=%s）" % old_id
        same = (old_id == sid)
        if same:
            # 门派没变、只是称谓不对 → 只把称谓对齐（不白写 @sect_id）
            lines = ["「%s」的门派已经是「%s」了，把称谓对齐过来？"
                     % (self.sv.actor_name(a), label), ""]
        elif sid == 0:
            # ⚠ 「转门派」选「无门派」= **只改门派**，技能一个不动（和转别的门派
            #   完全一致）。连技能一起重置是「清空门派」那个按钮的事
            #   （川 260927 22:5x：「无门派不清技能，清空门派才清技能」）。
            lines = ["把「%s」的门派改成「无门派」（@sect_id = 0）？"
                     % self.sv.actor_name(a),
                     "",
                     "· 只改存档里的门派本身（@sect_id）",
                     "· 技能一个不动（原来是「%s」的技能会留着）" % old_nm,
                     "  ⚠ 要连技能一起重置成天生技能 → 用「清空门派」那个按钮",
                     "  ⚠ 游戏里快捷技能栏、门派技能页都会不可用"]
        else:
            lines = ["把「%s」的门派改成「%s」？" % (self.sv.actor_name(a), label),
                     "",
                     "· 只改存档里的门派本身（@sect_id）",
                     "· 已学技能、辅助/修炼、属性 都不动",
                     "  （原来是「%s」，它的技能会留在角色身上，游戏里照旧能用）"
                     % old_nm]
        moves = []
        if stale:
            moves.append("回收「%s」" % "、".join(stale))
        if want_app:
            moves.append("发「%s」" % want_app)
        elif stale:
            moves.append("不补新的")
        if moves:
            lines.append("· 称谓：%s" % " → ".join(moves))
            if cur_app is not None and cur_app in [n for n, _s in old_apps]:
                lines.append("  （原来显示的就是门派称谓 → 改成显示新的那个）")
            lines.append("  ⚠ 游戏自己只加不删（而且不让改门派），回收/补发是工具额外做的")
        if not messagebox.askyesno("改门派", "\n".join(lines), parent=self.root):
            return
        try:
            if not same:
                self.g.set_actor_sect(a, sid)
            removed, added, _ap, _ai = self.g.set_actor_sect_appellation(a, sid)
        except Exception as e:
            messagebox.showerror("改不了", zh_error(e), parent=self.root)
            return
        self.mark_dirty()
        # ⚠ 下拉只在「换角色」时才自动切（见 `load_actor_skills`）→ 这里要把跟随
        #   标记显式更新掉；否则下次刷新面板会把下拉抢回**旧**门派，看着像没改成。
        self._sect_actor = a
        keep = self.tv_actor.selection()
        self.fill_actors(keep_id=keep[0] if keep else None)   # 列表「门派」列
        self.load_actor()                                     # 属性文本 + 清单
        extra = ""
        if removed or added:
            bits = []
            if removed:
                bits.append("回收「%s」" % "、".join(removed))
            if added:
                bits.append("发「%s」" % "、".join(added))
            extra = "，称谓%s" % "、".join(bits)
        if same:
            self.set_status("门派没变「%s」，只把称谓对齐了%s（记得点「保存修改」）"
                            % (label, extra))
        elif sid == 0:
            self.set_status("门派已改成「无门派」%s，技能没动"
                            "（要重置技能用「清空门派」；游戏里快捷技能栏/门派技能页"
                            "不可用；记得点「保存修改」）" % extra)
        else:
            self.set_status("门派已改成「%s」%s（@sect_id 已写，记得点「保存修改」）"
                            % (label, extra))

    def actor_clear_sect(self):
        """把**当前角色**清成「无门派」+ 把技能重置成职业天生技能。

        ⚠ 和「转门派」的边界（川 260927 22:5x 定）：**清技能只归本方法**。
        下拉里选「无门派」再点「转门派」只改门派（技能一个不动），**不**再转发到这里
        —— 两路合并过一次，是工具加戏，川明确要拆开（「无门派不清技能，清空门派才清技能」）。
        本方法自己要做的事：写 `@sect_id = 0` + 把 `@skills` 重置成职业自带
        （= 游戏 `clear_skills` + `init_skills`，见 `actor_reset_skills_to_class`），
        也就是「回到刚出生、没门派」的状态。

        ⚠ 两件事都必须告知到（确认框里写清楚了）：
          * `@sect_id = 0` 在游戏里是**减功能**：脚本 34699 / 34797 让快捷技能栏
            不可用，35804 隐藏门派技能页；
          * 清技能是**工具额外做的**，游戏自己换门派时**不会**清（`learn_skill`
            只 push + 排序）→ 门派技能、技能书/剧情给的技能会一起没。
        2026-09-27 第三轮补：**门派称谓也一起回收**（`@appellations`，
        「五庄观弟子」这种）—— 见 `set_actor_sect_appellation`。真档里有
        「已经无门派、却还挂着门派称谓」的角色，所以早退条件里也算上了它。
        `@sect_data`（辅助/修炼）和属性一律不动。
        """
        if self.g is None or self.sv is None:
            return
        a = self.current_actor()
        if a is None:
            messagebox.showinfo("提示", "先在角色列表选一个角色。",
                                parent=self.root)
            return
        nm = self.sv.actor_name(a)
        old_id = self.g.actor_sect_id(a)
        innate = set(self.g.actor_class_learnings(a))
        cur = set(self.g.actor_skills(a))
        drop = sorted(cur - innate)
        # ⚠ 还有「**天生技能没学全**」这一种（2026-10-04 真档实测：李修远
        #   `@skills` 是空的，而职业自带是 9/204/211）。以前只看 `drop`，
        #   这种档点完「清空门派」技能还是个空 —— 而提示却说「已经只剩天生
        #   技能，不动」。两边都得管：重置就是「`@skills` = 职业自带」。
        missing = sorted(innate - cur)
        # 称谓（@appellations）：门派称谓也得一起回收（2026-09-27 川指出）。
        # ⚠ 真档里有「已经无门派、却还挂着门派称谓」的角色（李修远：@sect_id=0
        #   但称谓是「五庄观弟子」）→ 早退条件里必须算上称谓，否则点了一直
        #   说「无需改动」、称谓永远回收不掉。
        apps, app_idx = self.g.actor_appellations(a)
        cur_app = apps[app_idx] if 0 <= app_idx < len(apps) else None
        old_apps = self.g.sect_appellations_of(a)
        if old_id == 0 and not drop and not missing and not old_apps:
            # 门派是 0、技能和天生技能一模一样、也没门派称谓 → 真没什么可做的
            self.set_status("「%s」已经是「无门派」、技能也只剩天生技能、"
                            "也没有门派称谓，无需改动" % nm)
            return
        old_nm = self.g.actor_sect_name(a) or "（认不出：@sect_id=%s）" % old_id
        sname = self.g.valid_skill_ids()
        lines = ["把「%s」改成「无门派」（@sect_id = 0）？" % nm, ""]
        if old_id != 0:
            lines.append("· 门派：%s → 无门派" % old_nm)
            lines.append("  ⚠ 游戏里快捷技能栏、门派技能页都会不可用")
        if drop or missing:
            keep_nm = "、".join("#%d %s" % (s, sname.get(s, ""))
                               for s in sorted(innate))
            lines.append("· 技能：%d 个 → 只剩职业自带的 %d 个"
                         % (len(cur), len(innate)))
            if keep_nm:
                lines.append("  留下：%s" % keep_nm)
            if drop:
                lines.append("  清掉 %d 个（含门派技能、技能书/剧情给的）" % len(drop))
            if missing:
                lines.append("  补上没学的 %d 个（%s）"
                             % (len(missing),
                                "、".join("#%d" % s for s in missing)))
            lines.append("  ⚠ 游戏自己换门派不会清技能，这一步是工具额外做的")
        else:
            lines.append("· 技能：已经是只剩天生技能，不动")
        if old_apps:
            lines.append("· 称谓：回收「%s」" % "、".join(n for n, _s in old_apps))
            lines.append("  ⚠ 游戏自己只加不删、也不让退门派，回收是工具额外做的")
        else:
            lines.append("· 称谓：没有门派称谓，不动")
        if cur_app is not None and cur_app in [n for n, _s in old_apps]:
            lines.append("  （显示的就是它 → 回收后改成不显示）")
        lines.append("")
        lines.append("辅助/修炼、属性不动。")
        if not messagebox.askyesno("清空门派", "\n".join(lines),
                                   parent=self.root):
            return
        try:
            self.g.set_actor_sect(a, 0)
            if drop or missing:
                self.g.actor_reset_skills_to_class(a)
            removed, _added, _ap, _ai = self.g.set_actor_sect_appellation(a, 0)
        except Exception as e:
            messagebox.showerror("改不了", zh_error(e), parent=self.root)
            return
        self.mark_dirty()
        # ⚠ 这里和 `actor_set_sect` 相反：**把跟随标记清掉**（= 不认「已同步」），
        #   让下面的 `load_actor` 重新同步下拉 —— 无门派角色现在会同步成
        #   「无门派」（下拉里有这一项了），左栏清单收起并提示没门派。
        self._sect_actor = None
        keep = self.tv_actor.selection()
        self.fill_actors(keep_id=keep[0] if keep else None)
        self.load_actor()
        if drop or missing:
            msg = ("「%s」已清成无门派，技能重置为天生技能 %d 个"
                   % (nm, len(innate)))
        else:
            msg = "「%s」门派已清成「无门派」（技能本来就只有天生技能）" % nm
        if removed:
            msg += "，回收称谓「%s」" % "、".join(removed)
        self.set_status("%s（游戏里快捷技能栏/门派技能页不可用；记得点「保存修改」）"
                        % msg)

    def open_skill_manager(self, key):
        """开技能管理器窗口（已经开着就抬到前面；目标没了就给一句提示）。

        ⚠ 窗口是**常驻**的：操作完不自动关，可以连着刷几批。`_skill_win`
          留着引用，这样重复点按钮不会开出第二个一模一样的窗口。
        """
        if key == "actor" and self.current_actor() is None:
            messagebox.showinfo("提示", "先在角色列表选一个角色。",
                                parent=self.root)
            return None
        if key == "baby" and self._baby() is None:
            messagebox.showinfo("提示", "先在列表里选一只召唤兽。",
                                parent=self.root)
            return None
        w = getattr(self, "_skill_win", None)
        if w is not None and getattr(w, "win", None) is not None \
                and w.win.winfo_exists():
            w.win.lift()
            w.win.focus_set()
            w.refill()
            return w
        w = SkillManager(self, key, first=True)
        self._skill_win = w
        return w

    def actor_skill_manager(self):
        """打开角色技能管理器窗口。"""
        return self.open_skill_manager("actor")

    def actor_skill_del(self):
        """忘掉技能一览里选中的技能（可多选，一次一批）。"""
        a = self.current_actor()
        sids = self.skp_actor.sel_ids()
        if a is None or not sids:
            messagebox.showinfo("提示", "先在技能一览里选要忘掉的技能"
                                        "（Ctrl / Shift 可多选）。",
                                parent=self.root)
            return
        try:
            drop, missing = self.g.actor_forget_many(a, sids)
        except Exception as e:
            messagebox.showerror("改不了", zh_error(e), parent=self.root)
            return
        if not drop:
            self.set_status("选中的 %d 个技能本来就没学" % len(sids))
            return
        self.mark_dirty()
        self.load_actor()
        msg = "已忘掉 %d 个技能" % len(drop)
        if missing:
            msg += "（%d 个本来就没学，跳过）" % len(missing)
        self.set_status(msg + "（记得点「保存修改」）")

    def actor_skill_clear(self):
        a = self.current_actor()
        if a is None or self.g is None:
            return
        nm = self.sv.actor_name(a)
        if not self.confirm("清空技能",
                            "把「%s」的技能全忘掉？\n"
                            "（游戏里这个角色就一个技能都不会了）" % nm):
            return
        self.g.actor_clear_skills(a)
        self.mark_dirty()
        self.load_actor()
        self.set_status("已清空「%s」的技能（记得点「保存修改」）" % nm)

    def actor_skill_clone(self):
        """从存档里**别的角色**把技能整套抄过来（覆盖 / 合并可选）。

        角色技能没有数量上限，所以不像召唤兽那样会「满了 12 个塞不进去」，
        来源有几个就抄几个。
        """
        a = self.current_actor()
        if a is None or self.g is None:
            messagebox.showinfo("提示", "先在角色列表选一个角色（被克隆的那个）。",
                                parent=self.root)
            return
        meta = self._skills_meta()
        rows = [(aid, x) for aid, x in self.sv.actors() if x is not a]
        if not rows:
            messagebox.showinfo("提示", "存档里没有别的角色可以当来源。",
                                parent=self.root)
            return
        tk, ttk = self.tk, self.ttk
        win = self.tk.Toplevel(self.root)
        win.title("克隆技能 → %s" % self.sv.actor_name(a))
        win.transient(self.root)
        win.grab_set()
        f = ttk.Frame(win, padding=8)
        f.pack(fill="both", expand=True)

        def skill_text(ids):
            out = []
            for s in ids:
                out.append(meta.get(s, ("", ""))[0] or "#%d" % s)
            return "、".join(out) or "（没有技能）"

        bar = ttk.Frame(f)
        bar.pack(fill="x")
        ttk.Label(bar, text="搜索（技能 / 名字 / 角色）：").pack(side="left")
        var_kw = tk.StringVar()
        ent = ttk.Entry(bar, textvariable=var_kw, width=18)
        ent.pack(side="left", padx=4)
        ent.bind("<KeyRelease>", lambda e: refill())
        var_merge = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="合并（保留目标原有技能）",
                        variable=var_merge).pack(side="left", padx=6)

        cols = ("who", "n", "skills")
        heads = ("角色", "技能数", "技能")
        widths = (150, 56, 460)
        tv = ttk.Treeview(f, columns=cols, show="headings", height=14,
                          selectmode="browse")
        for c, h, w in zip(cols, heads, widths):
            tv.heading(c, text=h)
            tv.column(c, width=w, anchor="w")
        vs = ttk.Scrollbar(f, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=vs.set)
        vs.pack(side="right", fill="y")
        tv.pack(fill="both", expand=True, pady=6)

        rows_map = {}

        def refill(_e=None):
            tv.delete(*tv.get_children())
            rows_map.clear()
            kw = var_kw.get().strip()
            for aid, x in rows:
                nm = self.sv.actor_name(x)
                ids = self.g.actor_skills(x)
                txt = skill_text(ids)
                if kw and kw not in "%s %s %s" % (nm, aid, txt):
                    continue
                iid = "a%d" % aid
                rows_map[iid] = (aid, x)
                tv.insert("", "end", iid=iid,
                          values=("%s (#%d)" % (nm, aid), len(ids), txt))
            kids = tv.get_children()
            if kids:
                tv.selection_set(kids[0])

        refill()

        def do_clone(_e=None):
            sel = tv.selection()
            row = rows_map.get(sel[0]) if sel else None
            if row is None:
                return
            _aid, src = row
            sname, dname = self.sv.actor_name(src), self.sv.actor_name(a)
            ids = self.g.actor_skills(src)
            merge = bool(var_merge.get())
            if merge:
                tip = "把「%s」的技能补进「%s」？" % (sname, dname)
            else:
                tip = ("把「%s」的技能覆盖到「%s」上（原来的 %d 个技能会被清掉）？"
                       % (sname, dname, len(self.g.actor_skills(a))))
            if not self.confirm("克隆技能", tip):
                return
            try:
                if merge:
                    res = self.g.actor_set_skills(
                        a, self.g.actor_skills(a) + ids)
                else:
                    res = self.g.actor_set_skills(a, ids)
            except Exception as e:
                messagebox.showerror("克隆失败", zh_error(e), parent=win)
                return
            win.destroy()
            self.mark_dirty()
            self.load_actor()
            self.set_status("已从「%s」克隆：现有 %d 个技能"
                            % (sname, len(res)))

        tv.bind("<Double-1>", do_clone)
        bf = ttk.Frame(f)
        bf.pack(fill="x")
        fit_btn(bf, text="克隆给「%s」" % self.sv.actor_name(a),
                   command=do_clone).pack(side="right", padx=4)
        fit_btn(bf, text="取消", command=win.destroy).pack(side="right")
        esc_close(win)
        ent.focus_set()
        center_win(win, self.root)

    # ================================================== 4 队伍 / 物品
    @staticmethod
    def _pack_hit(kw, slot, i, iid, name, content):
        """背包格子搜索匹配：名称 / 物品 id / 槽号 / 格子号 / 「内容」列。

        ⚠ 只搜**当前这一页**（背包页是分页显示的，跨页搜要另做一套；
          这里的需求是"这一页东西多了找一件"，够用）。
        """
        if not kw:
            return True
        for s in (name, content, str(iid), str(slot), str(i)):
            if s and kw in s:
                return True
        return False

    def pack_kw_clear(self):
        """清空背包格子搜索框并重列。"""
        self.var_pack_kw.set("")
        self.fill_party()

    def fill_party(self):
        """刷背包页（当前页 20 格 + 物品计数校验状态）。"""
        self._tip_hide()
        self.tv_pack.delete(*self.tv_pack.get_children())
        if not self.sv or self.g is None:
            return
        page = self.var_bag_page.get()
        kind = self.var_bag_kind.get()
        self.var_party.set("金钱 = %s　步数 = %s　出战成员 = %s　"
                           "仓库页号 = %s"
                           % (self.sv.gold(), self.sv.steps(),
                              self.sv.party_member_ids(),
                              self.g.warehouse_page()))
        rows = dict((r[0], r) for r in self.g.bag(kind, page))
        kw = (self.var_pack_kw.get() if hasattr(self, "var_pack_kw")
              else "").strip()
        n_hit = 0
        for i in range(game.PACK_PAGE_SIZE):
            slot = self.g.slot_key(page, i)
            r = rows.get(slot)
            if r:
                try:
                    cnt_txt = self.g.payload_summary(
                        self.g._item_node(kind, slot))
                except Exception:
                    cnt_txt = ""
                if kw and not self._pack_hit(kw, slot, i, r[3], r[4], cnt_txt):
                    continue
                n_hit += 1
                self.tv_pack.insert("", "end", iid="s%d" % slot,
                                    values=(slot, i, r[3], r[4], r[5], cnt_txt))
            elif not kw:
                # 搜索时不列空格子：找东西的时候空格子只是噪音。
                # （⚠ 空关键词仍要列满 20 格 —— 「放进第一个空格子」要看着格子挑。）
                self.tv_pack.insert("", "end", iid="s%d" % slot,
                                    values=(slot, i, "（空）", "", "", ""))
        bad = [r for r in self.g.security_rows() if r[2] != r[3]]
        try:
            self.bag_bad = self.g.pack_report(kinds=(kind,))
        except Exception:
            self.bag_bad = []
        note = ("物品计数校验（游戏自己的 $game_system.security）：%d 条记录%s"
                % (len(self.g.security_rows()),
                   "，有 %d 条和背包对不上（点「同步计数校验」）" % len(bad)
                   if bad else "，全部对得上 ✓"))
        if kw:
            # ⚠ 这句得挂在 note 赋好之后：搜索前缀是「加在最前面」的。
            note = "搜索「%s」：本页命中 %d 个格子；\n" % (kw, n_hit) + note
        if self.bag_bad:
            note += ("\n这一页背包体检：%d 项异常（点「背包体检」看详情、"
                     "「一键修复」处理）" % len(self.bag_bad))
        self.var_bag_note.set(note)
        self.fill_templates()

    # ------------------------------------------------ 物品模板（从 Data 表读）
    def fill_templates(self):
        """右侧模板列表：可搜索、双击写进当前选中的格子（仿画迹1）。"""
        if not hasattr(self, "tv_tpl"):
            return
        self._tip_hide()
        # ⚠ Treeview 重建后必须按 key 恢复选中（通则）—— 否则「放进第一个空格子」
        #   一刷就把右边刚选中的模板掉选（2026-10-07 川报的）。
        keep = list(self.tv_tpl.selection())
        self.tv_tpl.delete(*self.tv_tpl.get_children())
        if not self.sv or self.g is None:
            return
        kind = self.var_bag_kind.get()
        kw = self.var_tpl_kw.get()
        try:
            rows = self.g.templates(kind, keyword=kw, limit=400)
        except Exception as e:
            self.var_tpl_note.set("读不到 Data 表：%s" % human(str(e))[:80])
            return
        self.tpl_rows = rows
        try:
            grp = self.g.group_map(kind)
        except Exception:
            grp = {}
        for iid, nm, _desc in rows:
            self.tv_tpl.insert("", "end", iid="t%d" % iid,
                               values=(iid, nm, grp.get(iid, "")))
        still = [i for i in keep if self.tv_tpl.exists(i)]
        if still:
            try:
                self.tv_tpl.selection_set(still)
            except Exception:
                pass
        self.var_tpl_note.set("共 %d 个%s" % (
            len(rows), "（按关键字过滤）" if kw else "（已滤掉分段行和空占位）"))

    def _bag_kid(self):
        """“孵出/开出对象 id”输入框（空＝让工具按游戏规则随机）。"""
        txt = (self.var_bag_kid.get() if hasattr(self, "var_bag_kid")
               else "").strip()
        if not txt:
            return None
        try:
            return int(txt, 0)
        except ValueError:
            messagebox.showinfo("提示", "“孵出对象 id”要填整数（或留空）。",
                                parent=self.root)
            return None

    def _warn_payload(self, kind, iid):
        """这件东西是不是“运行时才有内容”：是就提醒一句，并显示在提示行。"""
        try:
            need, nm = self.g.item_needs_payload(kind, iid)
        except Exception:
            return True
        if hasattr(self, "var_bag_pay"):
            if need:
                self.var_bag_pay.set(
                    "⚠ %s 属于“游戏运行时才生成内容”的东西（孵化蛋/礼包/图纸…）："
                    "工具会现生成一份内容；若存档里有同款，会直接克隆它的内容。"
                    % nm)
            else:
                self.var_bag_pay.set("")
        return need

    def _bag_slots(self, quiet=False):
        """选中的格子号（多选按槽号升序）；一个都没选返回 []。

        ⚠ 2026-10-07 川报「多选之后点功能还是只改第一个」：`tv_pack` 一直是
          `extended`（能多选），但各按钮都只取 `selection()[0]`。改成统一从
          这里取**全部**选中格 —— 每格的操作逻辑跟单格时完全一样。
        """
        out = set()
        for iid in self.tv_pack.selection():
            try:
                out.add(int(iid[1:]))
            except (ValueError, IndexError):
                pass
        if not out and not quiet:
            messagebox.showinfo("提示",
                                "先在左边点一个格子（Ctrl 点选 / Shift 连选）。",
                                parent=self.root)
        return sorted(out)

    def _bag_slot(self, quiet=False):
        """单格（取第一个选中项）—— 只给「预览 / 双击」这类单格操作用。"""
        slots = self._bag_slots(quiet=quiet)
        return slots[0] if slots else None

    def pack_select(self, slots):
        """把背包列表里的这些槽号重新选中（`fill_party()` 之后恢复选中用）。

        ⚠ Treeview 重建后必须按 key 恢复选中，否则选中会跳回第一行（通则）。
        """
        if not hasattr(self, "tv_pack"):
            return
        keep = []
        for s in slots:
            iid = "s%d" % s
            if self.tv_pack.exists(iid):
                keep.append(iid)
        if keep:
            try:
                self.tv_pack.selection_set(keep)
            except Exception:
                pass

    def bag_pick(self):
        """选中格子 → 把 id / 数量填到输入框（仿画迹1 的 load_pack_edit）。"""
        slot = self._bag_slot(quiet=True)
        if slot is None or not self.g:
            return
        kind = self._bag_kind()
        info = None
        for r in self.g.bag(kind):
            if r[0] == slot:
                info = r
                break
        if info:
            self.var_bag_id.set(str(info[3]))
            self.var_bag_cnt.set(str(info[5]))
            self.set_status("槽 %d：%s ×%d（id=%d）" % (slot, info[4], info[5], info[3]))
        else:
            self.var_bag_id.set("")
            self.var_bag_cnt.set("1")
            self.set_status("槽 %d：空格" % slot)

    def bag_use_template(self, into_selected=True):
        """把右边选中的模板写进背包：into_selected=选中格子，False=第一个空格。

        画迹1 的做法也是这样：模板列表 + 写进指定槽位（会换掉原来那件东西）。
        """
        if not self.g:
            return
        sel = self.tv_tpl.selection()
        if not sel:
            messagebox.showinfo("提示", "先在右边选一个物品模板。",
                                parent=self.root)
            return
        iid = int(sel[0][1:])
        kind = self._bag_kind()
        self._warn_payload(kind, iid)
        try:
            n = int(self.var_bag_cnt.get() or "1", 0)
        except ValueError:
            n = 1
        # ⚠ 2026-10-07 川：「放进第一个空格子」之后选中会跳到新写的格子，
        #   原来选中的那几格丢了 → 先记下来，非「写入选中的格子」时原位恢复。
        prev = self._bag_slots(quiet=True)
        if into_selected:
            slots = self._bag_slots()
            if not slots:
                return
        else:
            page = self.var_bag_page.get()
            used = set(r[0] for r in self.g.bag(kind, page))
            free = [self.g.slot_key(page, i)
                    for i in range(game.PACK_PAGE_SIZE)
                    if self.g.slot_key(page, i) not in used]
            if not free:
                messagebox.showinfo("提示", "这一页没空格了，先清一个。",
                                    parent=self.root)
                return
            slots = [free[0]]
        kid = self._bag_kid()
        done, bad = [], []
        for slot in slots:
            try:
                self.g.set_item(kind, slot, iid, n, kid=kid)
                done.append(slot)
            except Exception as e:
                bad.append((slot, human(str(e))))
        if not done:
            messagebox.showerror("写入失败",
                                 "没写进去：\n  " + "\n  ".join(
                                     "槽 %s：%s" % (s, w) for s, w in bad[:8]),
                                 parent=self.root)
            return
        self.mark_dirty()
        self.fill_party()
        # 「放进第一个空格子」不跳选中：留在原来那几格上（右边模板列表的选中
        # 由 fill_templates 自己按 iid 恢复）。
        self.pack_select(done if into_selected else prev)
        msg = ("槽 %s 已换成 id=%d ×%d" % ("、".join(str(s) for s in done),
                                           iid, n)
               if len(done) > 1 else "槽 %d 已换成 id=%d ×%d" % (done[0], iid, n))
        if bad:
            msg += "（%d 格失败）" % len(bad)
        self.set_status(msg + "（计数校验已同步；保存时会整档重写）")

    def bag_reroll(self):
        """给**选中的全部格子**按游戏规则重抽“运行时内容”（蛋孵哪只、要诀开什么技能）。

        ⚠ 「孵出/开出对象 id」输入框填了就按它来（老行为），留空＝按游戏范围随机。
          2026-10-07 之前只作用第一个选中格 —— 川报过一次，现在改成多格。
        """
        slots = self._bag_slots()
        if not slots:
            return
        kind = self._bag_kind()
        kid = self._bag_kid()
        done, bad = [], []
        for slot in slots:
            try:
                self.g.set_payload(kind, slot, kid=kid, force=True)
                done.append(slot)
            except Exception as e:
                bad.append((slot, zh_error(e)))
        if not done:
            messagebox.showerror(
                "重抽内容",
                "这些格子没有可重抽的内容：\n  " + "\n  ".join(
                    "槽 %s：%s" % (s, w) for s, w in bad[:8]),
                parent=self.root)
            return
        self.mark_dirty()
        self.fill_party()
        self.pack_select(done)
        it = self.g._item_node(kind, done[-1])
        msg = ("槽 %s 的内容已重新生成" % "、".join(str(s) for s in done)
               if len(done) > 1 else "槽 %d 的内容已重新生成" % done[0])
        if bad:
            msg += "（%d 格跳过）" % len(bad)
        self.set_status("%s：%s" % (msg, self.g.payload_summary(it)))

    def open_payload_manager(self):
        """开「重抽管理」窗口（已经开着就抬到前面 + 重读选中）。"""
        if self.g is None:
            messagebox.showinfo("提示", "先打开一个存档。", parent=self.root)
            return None
        w = getattr(self, "_payload_win", None)
        if w is not None and getattr(w, "win", None) is not None \
                and w.win.winfo_exists():
            w.win.lift()
            w.win.focus_set()
            w.refill()
            return w
        w = PayloadManager(self, first=True)
        self._payload_win = w
        return w

    def bag_all(self, count=99):
        """把本页已有格子的数量批量设成 count。"""
        slot = self._bag_slot(quiet=True)
        page = (slot // game.PACK_PAGE_SIZE if slot is not None
                else self.var_bag_page.get())
        try:
            n = self.g.set_all_counts(self._bag_kind(), count, page)
        except Exception as e:
            messagebox.showerror("批量修改失败", human(str(e)), parent=self.root)
            return
        if n:
            self.mark_dirty()
            self.fill_party()
        self.set_status("背包第 %d 页：已把 %d 个格子的数量改成 %d"
                        % (page + 1, n, count))

    def bag_check(self):
        """背包体检：把不正常的格子（结构坏/id 无效/数量 0/超上限/重复）列出来。"""
        if not self.g:
            return []
        try:
            rows = self.g.pack_report()
        except Exception as e:
            self.err(e)
            return []
        self.bag_bad = rows
        cn = dict((k[0], k[2]) for k in game.KINDS)
        lines = "\n".join("  [%s] 槽 %s %s：%s"
                          % (cn.get(k, k), s, nm, why)
                          for k, s, nm, why, _f, _e in rows[:20])
        messagebox.showinfo("背包体检",
                            ("发现问题 %d 项：\n%s%s"
                             % (len(rows), lines,
                                "\n…（只显示前 20 项）" if len(rows) > 20 else ""))
                            if rows else "背包里没发现问题 ✓",
                            parent=self.root)
        self.fill_party()
        return rows

    def bag_fix(self):
        """一键修复：重复格合并、数量超上限截断、坏格子清空。"""
        if not self.g:
            return
        try:
            done = self.g.pack_fix()
        except Exception as e:
            messagebox.showerror("修复失败", human(str(e)), parent=self.root)
            return
        if done:
            self.mark_dirty()
            self.refresh_panels()
        messagebox.showinfo(
            "背包修复",
            "已处理：\n  " + "\n  ".join("%s 槽 %s %s" % d for d in done[:20])
            if done else "没发现需要修的。",
            parent=self.root)

    # ------------------------------------------------ 机器码（存档绑定）
    def machine_show(self, quiet=False):
        """读本机机器码 + 存档里记录的机器码。本机码放进输入框方便直接用。"""
        if not self.g:
            return
        try:
            now, err, ids, ok = self.g.machine_status()
        except Exception as e:
            self.var_machine.set("机器码：读失败（%s）" % human(str(e))[:70])
            return
        if now and not self.var_machine_id.get().strip():
            self.var_machine_id.set(now)
        if err:
            self.var_machine.set("本机机器码：读不到 — %s" % err.splitlines()[0][:80])
        else:
            self.var_machine.set(
                "本机机器码：%s　%s\n存档记录的机器码：%s"
                % (now, "✓ 在存档记录里" if ok else "✗ 不在存档记录里（换机器玩会弹「存档异常」）",
                   "、".join(ids) or "（空）"))
        if hasattr(self, "var_machine_list"):
            self.var_machine_list.set(
                "存档里一共 %d 个：%s"
                % (len(ids), "、".join("%d) %s" % (i + 1, x)
                             for i, x in enumerate(ids)) or "（一个也没有）"))
        if hasattr(self, "var_machine_quick"):
            self.var_machine_quick.set(
                "机器码：本机 %s / 存档 %s　（在「机器码」页里改）"
                % (now or "读不到", "、".join(ids) or "空"))
        if not quiet:
            self.set_status("机器码：本机 %s / 存档 %s"
                            % (now or "?", "、".join(ids) or "空"))

    def machine_log(self, text):
        """机器码页的“操作记录”。"""
        if not hasattr(self, "txt_machine"):
            return
        try:
            self.txt_machine.insert("end", "[%s] %s\n"
                                    % (time.strftime("%H:%M:%S"), text))
            self.txt_machine.see("end")
        except Exception:
            pass

    def machine_fill_local(self):
        """读本机机器码填进输入框（不写存档）。"""
        if not self.g:
            return
        now, err, _ids, _ok = self.g.machine_status(refresh=True)
        if err:
            messagebox.showerror("取机器码", zh_error(err), parent=self.root)
            return
        self.var_machine_id.set(now)
        self.machine_log("读取本机机器码：%s" % now)
        self.machine_show(quiet=True)

    def machine_fill_saved(self):
        """把存档里第一个机器码填进输入框（方便“以旧换新”地改）。"""
        if not self.g:
            return
        ids = self.g.machine_ids()
        if not ids:
            messagebox.showinfo("提示", "存档里没记录机器码。", parent=self.root)
            return
        self.var_machine_id.set(ids[0])
        self.machine_log("读存档记录：%s" % ids[0])
        self.set_status("已把存档里的第一个机器码填到输入框：%s" % ids[0])

    def _machine_apply(self, replace=False):
        mid = self.var_machine_id.get().strip()
        if not mid:
            messagebox.showinfo("提示", "先填一个机器码（可以点「读取本机机器码」）。",
                                parent=self.root)
            return
        before = self.g.machine_ids() if self.g else []
        try:
            if replace:
                ids = self.g.set_machine_ids([mid])
            else:
                ids = self.g.add_machine_id(mid)
        except Exception as e:
            messagebox.showerror("写入失败", zh_error(e), parent=self.root)
            return
        self.mark_dirty()
        self.machine_show(quiet=True)
        if self.g:
            self.guard_check()
        self.machine_log("%s：%s → %s"
                         % ("替换" if replace else "追加",
                            "、".join(before) or "（空）", "、".join(ids)))
        self.set_status("存档机器码现在有：%s（记得保存）" % "、".join(ids))

    def machine_add(self):
        self._machine_apply(False)

    def machine_set(self):
        self._machine_apply(True)

    def machine_use_local(self):
        """取本机机器码，直接替换存档记录（换机器玩最直接的做法）。"""
        if not self.g:
            return
        now, err, ids, ok = self.g.machine_status(refresh=True)
        if err:
            messagebox.showerror("取机器码", zh_error(err), parent=self.root)
            return
        if ok:
            messagebox.showinfo("机器码",
                                "本机机器码 %s 已经在存档记录里了，不用改。" % now,
                                parent=self.root)
            return
        if not self.confirm(
                "确认",
                "把存档里的机器码\n  %s\n换成本机机器码\n  %s\n吗？\n\n"
                "（换机器玩建议改成「追加」，这样两台机器都能进）"
                % ("、".join(ids) or "（空）", now)):
            return
        self.var_machine_id.set(now)
        self._machine_apply(True)

    def machine_clear(self):
        """清空存档里的机器码记录（游戏会在下次启动时重新写入）。"""
        if not self.g:
            return
        ids = self.g.machine_ids()
        if not ids:
            messagebox.showinfo("提示", "存档里本来就没有机器码记录。",
                                parent=self.root)
            return
        if not self.confirm(
                "确认", "清空存档里的机器码记录（%s）？\n\n"
                "注意：清空后如果本机机器码也不在里面，游戏会弹「存档异常」。"
                % "、".join(ids)):
            return
        self.g.set_machine_ids([])
        self.mark_dirty()
        self.machine_show(quiet=True)
        if self.g:
            self.guard_check()
        self.machine_log("清空了机器码记录（原来：%s）" % "、".join(ids))

    # ------------------------------------------------ 背包操作
    def _bag_sel(self):
        sel = self.tv_pack.selection()
        if not sel:
            messagebox.showinfo("提示", "先在列表里点一格。", parent=self.root)
            return None
        return int(sel[0][1:])

    def _bag_kind(self):
        return self.var_bag_kind.get()

    def bag_edit(self):
        """双击：有东西就改数量，空的就按 id 框里的 id 加。"""
        slot = self._bag_sel()
        if slot is None:
            return
        kind = self._bag_kind()
        exist = dict((r[0], r) for r in self.g.bag(kind, slot // game.PACK_PAGE_SIZE))
        if slot in exist:
            self.bag_set_count()
        else:
            self.bag_add()

    def bag_set_count(self):
        """把选中的**每一格**数量都改成输入框里的数（多选=一次改一批）。"""
        slots = self._bag_slots()
        if not slots:
            return
        try:
            n = int(self.var_bag_cnt.get() or "0", 0)
        except ValueError:
            messagebox.showinfo("提示", "数量要填整数。", parent=self.root)
            return
        kind = self._bag_kind()
        done, bad = [], []
        for slot in slots:
            try:
                done.append((slot, self.g.set_count(kind, slot, n)))
            except Exception as e:
                bad.append((slot, human(str(e))))
        if not done:
            messagebox.showerror(
                "改数量失败",
                "没改成功：\n  " + "\n  ".join(
                    "槽 %s：%s" % (s, w) for s, w in bad[:8]),
                parent=self.root)
            return
        self.mark_dirty()
        self.fill_party()
        self.pack_select([s for s, _ in done])
        msg = ("槽 %s 数量 = %d" % ("、".join(str(s) for s, _ in done), n)
               if len(done) > 1 else "槽 %d 数量 = %d" % (done[0][0], done[0][1]))
        if bad:
            msg += "（%d 格是空的/结构不对，跳过）" % len(bad)
        self.set_status(msg + "（物品计数校验已同步）")

    def bag_clear(self):
        """清空选中的**每一格**（多选=一次清一批）。"""
        slots = self._bag_slots()
        if not slots:
            return
        kind = self._bag_kind()
        done, bad = [], []
        for slot in slots:
            try:
                if self.g.clear_slot(kind, slot):
                    done.append(slot)
            except Exception as e:
                bad.append((slot, human(str(e))))
        if done:
            self.mark_dirty()
            self.fill_party()
            self.pack_select(done)
        if bad:
            messagebox.showerror("清空失败",
                                 "有 %d 格没清掉：\n  " % len(bad) + "\n  ".join(
                                     "槽 %s：%s" % (s, w) for s, w in bad[:8]),
                                 parent=self.root)
            return
        self.set_status("已清空 %d 格（%s）（计数校验已同步）"
                        % (len(done), "、".join(str(s) for s in done))
                        if done else "选中的格子本来就是空的")

    def bag_add(self):
        """按 id 往选中的**每一格**写一份（多选=一次铺一批；已有东西的格子不覆盖）。"""
        slots = self._bag_slots()
        if not slots:
            return
        kind = self._bag_kind()
        try:
            iid = int(self.var_bag_id.get() or "0", 0)
            n = int(self.var_bag_cnt.get() or "1", 0)
        except ValueError:
            messagebox.showinfo("提示", "物品 id / 数量要填整数。", parent=self.root)
            return
        db_key = dict((k[0], k[3]) for k in game.KINDS)[kind]
        try:
            name = self.g.item_name(db_key, iid)
        except Exception:
            name = "?"
        if name == "?":
            try:
                name = self.g.item_display_name(
                    self.g.find_like(kind, iid)) or "?"
            except Exception:
                pass
        if name == "?" and not messagebox.askyesno(
                "确认", "Data\\%s.rvdata2 里没有 id=%d 这件东西。\n"
                        "还是往里写吗？" % (db_key, iid), parent=self.root):
            return
        self._warn_payload(kind, iid)
        kid = self._bag_kid()
        done, bad = [], []
        for slot in slots:
            try:
                self.g.add_item(kind, slot, iid, n, kid=kid)
                done.append(slot)
            except Exception as e:
                bad.append((slot, human(str(e))))
        if not done:
            messagebox.showerror(
                "添加失败",
                "没写进去：\n  " + "\n  ".join(
                    "槽 %s：%s" % (s, w) for s, w in bad[:8]),
                parent=self.root)
            return
        self.mark_dirty()
        self.fill_party()
        self.pack_select(done)
        msg = ("已往槽 %s 各放入 %s ×%d" % ("、".join(str(s) for s in done),
                                            name, n)
               if len(done) > 1 else "已往槽 %d 放入 %s ×%d" % (done[0], name, n))
        if bad:
            msg += "（%d 格已有东西，没覆盖）" % len(bad)
        self.set_status(msg + "（结构性改动：保存时会整档重写）")

    # ================================================== 5 开关 / 变量
    def fill_switches(self):
        self.tv_sw.delete(*self.tv_sw.get_children())
        self.tv_va.delete(*self.tv_va.get_children())
        if not self.sv:
            return
        nsw, nva = self.sv.counts()
        for i in range(nsw):
            self.tv_sw.insert("", "end", iid="s%d" % i,
                              values=(i, "开" if self.sv.get_switch(i) else "关",
                                      fieldnames.note_of_switch(i)))
        for i in range(nva):
            self.tv_va.insert("", "end", iid="v%d" % i,
                              values=(i, self.sv.get_variable(i),
                                      fieldnames.note_of_variable(i)))

    def sw_toggle(self):
        sel = self.tv_sw.selection()
        if not sel or not self.sv:
            return
        i = int(sel[0][1:])
        v = not bool(self.sv.get_switch(i))
        self.sv.set_switch(i, v)
        self.doc.dirty = True
        self.mark_dirty()
        self.tv_sw.item(sel[0], values=(i, "开" if v else "关"))

    def va_edit(self):
        sel = self.tv_va.selection()
        if not sel or not self.sv:
            return
        i = int(sel[0][1:])
        dlg = EditDialog(self.root, self.sv.get_variable(i), "i")
        self.root.wait_window(dlg)
        if dlg.result is None:
            return
        try:
            self.sv.set_variable(i, int(dlg.result))
        except Exception as e:
            messagebox.showerror("修改失败", human(str(e)), parent=self.root)
            return
        self.doc.dirty = True
        self.mark_dirty()
        self.tv_va.item(sel[0], values=(i, dlg.result))

    # ================================================== 6 数据表 (CSV)
    def db_selected_key(self):
        sel = self.lst_db.curselection()
        return datatables.ALL_KEYS[sel[0]] if sel else None

    def db_preview(self):
        key = self.db_selected_key()
        if not key:
            return
        try:
            header, data = datatables.rows(key)
        except Exception as e:
            self.var_db_info.set("解析失败：%s" % human(str(e)))
            return
        cols = ["c%d" % i for i in range(len(header))]
        self.tv_db.configure(columns=cols, show="headings")
        self.tv_db.delete(*self.tv_db.get_children())
        for i, h in enumerate(header):
            cid = cols[i]
            self.tv_db.heading(cid, text=h)
            self.tv_db.column(cid, width=max(70, min(300, 10 * len(h) + 40)),
                              anchor="w")
        for row in data[:300]:
            self.tv_db.insert("", "end", values=row)
        self.var_db_info.set("%s（%s.rvdata2）—— 共 %d 行，预览前 %d 行"
                             % (datatables.table_label(key), key, len(data),
                                min(300, len(data))))

    def db_choose_dir(self):
        d = filedialog.askdirectory(title="选 CSV 输出目录",
                                    initialdir=self.var_db_out.get() or ".")
        if d:
            self.var_db_out.set(d)

    def db_export_selected(self):
        key = self.db_selected_key()
        if key:
            self._db_export([key])

    def db_export_all(self):
        self._db_export(None)

    def _db_export(self, keys):
        out = self.var_db_out.get().strip() or DEFAULT_CSV_DIR
        try:
            os.makedirs(out, exist_ok=True)
            res = datatables.export_all(out, keys)
        except Exception as e:
            messagebox.showerror("导出失败", human(str(e)), parent=self.root)
            return
        msg = "\n".join("%s（%d 行）" % (os.path.basename(p), n) for p, n in res)
        messagebox.showinfo("导出 CSV", "已写到：\n%s\n\n%s" % (out, msg),
                            parent=self.root)
        self.set_status("CSV 已导出到 %s" % out)


# ==========================================================================
# 小工具
# ==========================================================================
def value_of(node):
    return nodetext.value_of(node)


def describe_value(node):
    """节点 → 一句人话（旧名保留，内部改用 nodetext）。"""
    return nodetext.brief(node, 200)


NOTES = fieldnames.IVAR_NOTES          # 保留旧名字（测试/外部可能引用）


def note_of(node):
    """给数据树加一列"说明"：抽节点类型 / 类名。"""
    return nodetext.note_for(None, None, node)


def note_for_ivar(name):
    return fieldnames.note_of_ivar(name)


def short(v, n=80):
    s = human(v)
    s = s.replace("\n", "\\n").replace("\r", "")
    return s if len(s) <= n else s[:n] + "…"


def node_detail(node):
    """右侧"节点详情"：类型 + 值 + 字节区间 + 子项速览（带中文注释）。"""
    node = nodetext.deref(node)
    L = ["类型：%s" % nodetext.type_label(node),
         "值：%s" % short(nodetext.brief(node, 400), 400),
         "字节区间：[%s, %s)" % (getattr(node, "start", "?"),
                                 getattr(node, "end", "?"))]
    if isinstance(node, (M.ObjNode, M.StructNode)):
        n = fieldnames.note_of_class(node.cls)
        if n:
            L.append("这是什么：%s" % n)
        L.append("实例变量：")
        for k, v in node.ivars:
            L.append("  %-24s %-30s %s" % (k, short(nodetext.brief(v, 40), 36),
                                           fieldnames.note_of_ivar(k)))
    elif isinstance(node, M.HashNode):
        L.append("前 20 对：")
        for k, v in node.pairs[:20]:
            L.append("  %-24s %-30s %s"
                     % (short(nodetext.key_label(k), 22),
                        short(nodetext.brief(v, 60), 60),
                        nodetext.note_for(node, k, v)))
    elif isinstance(node, M.ArrayNode):
        L.append("前 20 项：")
        for i, v in enumerate(node.items[:20]):
            L.append("  [%-3d] %-30s %s" % (i, short(nodetext.brief(v, 60), 60),
                                             nodetext.note_for(node, i, v)))
    elif isinstance(node, M.UserDefNode):
        L.append("自定义序列化：%s，%d 字节" % (node.cls, len(node.data)))
    return "\n".join(L)


class NoteDialog(tk.Toplevel):
    """改备份备注的小窗：多行文本，确定/取消；result=None 表示取消。"""

    def __init__(self, master, cur="", title="编辑备注", label=None):
        tk.Toplevel.__init__(self, master)
        self.title(title)
        self.result = None
        ttk.Label(self, text=label
                  or "备注（会存在备份旁边的 .txt；留空＝删除备注）"
                  ).pack(anchor="w", padx=8, pady=(8, 2))
        self.txt = tk.Text(self, width=60, height=6,
                           font=("Microsoft YaHei UI", 10), wrap="word")
        vs = ttk.Scrollbar(self, orient="vertical", command=self.txt.yview)
        self.txt.configure(yscrollcommand=vs.set)
        vs.pack(side="right", fill="y")
        self.txt.pack(fill="both", expand=True, padx=(8, 0), pady=2)
        self.txt.insert("1.0", cur or "")
        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=8)
        fit_btn(bar, text="确定", command=self.ok).pack(side="left", padx=8)
        fit_btn(bar, text="取消", command=self.destroy).pack(side="left", padx=6)
        self.bind("<Control-Return>", lambda e: self.ok())
        esc_close(self)
        center_win(self, master)
        self.txt.focus_set()        # 焦点给文本框（排在 esc_close 之后才优先）

    def ok(self):
        self.result = self.txt.get("1.0", "end").strip()
        self.destroy()


class EditDialog(tk.Toplevel):
    def __init__(self, master, cur, ntype):
        tk.Toplevel.__init__(self, master)
        self.title("修改字段")
        self.result = None
        self.ntype = ntype
        ttk.Label(self, text="当前值：").grid(row=0, column=0, sticky="w",
                                            padx=8, pady=6)
        ttk.Label(self, text=short(cur, 200)).grid(row=0, column=1, sticky="w")
        ttk.Label(self, text="新值：").grid(row=1, column=0, sticky="w", padx=8, pady=6)
        self.var = tk.StringVar(value="" if cur is None else str(cur))
        ent = ttk.Entry(self, textvariable=self.var, width=48)
        ent.grid(row=1, column=1, padx=8, pady=6)
        bar = ttk.Frame(self)
        bar.grid(row=2, column=0, columnspan=2, pady=8)
        fit_btn(bar, text="确定", command=self.ok).pack(side="left", padx=6)
        fit_btn(bar, text="取消", command=self.destroy).pack(side="left", padx=6)
        self.bind("<Return>", lambda e: self.ok())
        esc_close(self)
        center_win(self, master)
        ent.focus_set()             # 焦点给输入框（排在 esc_close 之后才优先）

    def ok(self):
        raw = self.var.get()
        try:
            if self.ntype in ("i", "l"):
                self.result = int(raw, 0)
            elif self.ntype == "f":
                self.result = float(raw)
            else:
                self.result = raw
        except ValueError:
            messagebox.showerror("输入有误", "这个字段需要数字。", parent=self)
            return
        self.destroy()


def main():
    argv = [a for a in sys.argv[1:] if not a.startswith("--")]
    save = argv[0] if argv else None
    selftest = ("--selftest" in sys.argv) or bool(os.environ.get("XJ_SELFTEST"))
    try:
        root = tk.Tk()
    except Exception:
        return _fatal(traceback.format_exc())
    try:
        app = App(root, save)
    except codec.CodecError as e:
        messagebox.showerror("缺少依赖", str(e))
        return 2
    except Exception:
        return _fatal(traceback.format_exc())

    # 数据表预载（详见 `datatables.start_preload`）：Skills/Classes/States/Items/
    # Actors 这五张表第一次解密+解析要 0.5~0.66 秒，而「载入存档」时界面正等着用
    # 它们 —— 占了载入时长的一大半（2026-10-07 实测：预载后载入 1.65 → 0.71 秒）。
    # ⚠ 放在**界面建好之后**再起：建界面那 1 秒是纯 Python，跟预载抢 GIL 只会
    #   让窗口晚出来；界面先出来，预载在后台跑，自动载入会等它就绪（见
    #   `_auto_load_when_ready`），用户点开存档时通常已经好了。
    try:
        datatables.start_preload()
    except Exception:
        pass

    # 关窗口（点 × / Alt+F4）= 硬退出：原因同 `_hard_exit` —— 走 Tk 自己的收尾
    # 偶尔会卡住，任务管理器里留一个「画迹2内测版存档工具.exe」不放。
    # 现版本没有「未保存就拦一下」的提示，所以直接退不会丢东西。
    root.protocol("WM_DELETE_WINDOW", lambda: _hard_exit(0))

    if selftest:
        # ⚠ 先把 `__init__` 里排队的自动载入掐掉。它 200ms 后醒来会自己去 `load()`：
        #   缺宿主（只拷了 exe、漏下 XJCodec32.exe）时 `load()` 会弹**模态**「打开失败」，
        #   而模态框在无人值守的自检会话里没人点 → 进程挂死、`selftest_result.txt`
        #   根本写不出来。这是**竞态**（时有时无，2026-09-30 在 tools/check_pack.py
        #   的「只拷 exe」一组里实测到），所以不能靠运气，必须显式掐掉。
        app.cancel_auto_load()
        root.update()
        lines = selftest_lines(app)
        out = os.path.join(codec.app_dir(), "selftest_result.txt")
        try:
            open(out, "w", encoding="utf-8").write("\n".join(lines))
        except OSError:
            pass
        try:
            print("\n".join(lines))
        except Exception:
            pass
        # ⚠ 这里**不能** `root.destroy()`：打包版上它偶尔会卡住（结果文件已经写好、
        #   窗口还在，进程就是不走）。结果已经落盘了，直接硬退出。
        _hard_exit(0 if lines[-1].startswith("结果: OK") else 1)
    try:
        root.mainloop()
    except Exception:
        return _fatal(traceback.format_exc())
    return 0


def selftest_lines(app):
    """打包后的自检：依赖、版本、存档、各功能模块能不能跑。"""
    import hashlib
    # 自检要拿"真正的存档"来跑：可能上次打开的是 Battle.bt2 之类，别被带偏。
    # 顺序：XJ_SAVE 环境变量 → 游戏目录下的 save.rvdata2 → 刚才打开的那个。
    cands = []
    env = os.environ.get("XJ_SAVE")
    if env:
        cands.append(env)
    p = paths.save_path()
    if p:
        cands.append(p)
    if app.doc is not None and app.doc.path:
        cands.append(app.doc.path)
    for c in cands:
        if not c or not os.path.exists(c):
            continue
        try:
            app.load(c, quiet=True)
            app.root.update()
        except Exception:
            continue
        if app.sv is not None:      # 找到本作存档了
            break
    L = ["%s %s 自检" % (APP_NAME, VERSION),
         "程序目录: %s" % codec.app_dir(),
         "打包运行(frozen): %s" % bool(getattr(sys, "frozen", False)),
         "Python: %s" % sys.version.split()[0]]
    host = codec.find_host()
    L.append("32 位宿主: %s" % (host or "未找到（改不了存档！）"))
    game = paths.find_game_dir()
    L.append("游戏目录: %s" % (game or "未找到（可设 XJ_GAME 指定）"))
    doc, sv = app.doc, app.sv
    if doc is None:
        L.append("未加载存档")
    else:
        L.append("存档: %s" % doc.path)
        L.append("明文 %d 字节 / 顶层对象 %d 个" % (len(doc.raw),
                                                   len(doc.objects)))
        L.append("明文 MD5: %s" % hashlib.md5(doc.raw).hexdigest())
    if sv is None:
        L.append("SaveDoc: 未建立（不是本作存档？）")
    else:
        g = app.g
        L.append("金钱 = %s" % sv.gold())
        L.append("角色数 = %d" % len(sv.actors()))
        L.append("背包 = %d 件 / 空槽 %d 个"
                 % (len(g.bag("Items")), len(g.empty_slots("Items"))))
        L.append("召唤兽 = %s"
                 % ("、".join(g.baby_name(b) for _i, b in g.babies(
                     sv.actors()[0][1])) if sv.actors() else "无"))
        rep = g.anti_cheat_report()
        L.append("防作弊体检 = %d 项，超限 %d 项"
                 % (len(rep), len([r for r in rep if r[3]])))
        L.append("物品计数校验 = %d 条" % len(g.security_rows()))
        # 名字表这条要看的是：**读不到游戏目录时有没有顶上**（内置快照）。
        # 打包版测试（tests/test_bundle_db_table.py）就靠下面两行断言。
        import datatables as _dt

        def _named(k):
            # 只数"真有名字"的：Data 表里那些空占位槽不算，否则跟内置快照没法比
            return len([v for v in _dt.name_map(k).values() if v])

        L.append("名字表: %s（技能 %d 条有名字 / 物品 %d 条）"
                 % (_dt.names_source("Skills"), _named("Skills"),
                    _named("Items")))
        L.append("技能名自检: 9=%s / 1=%s / 101=%s"
                 % (_dt.name_map("Skills").get(9),
                    _dt.name_map("Skills").get(1),
                    _dt.name_map("Skills").get(101)))
        # 在内存里试一次结构性重写（不写盘）
        try:
            import marshal_ruby as _M
            n = len(sv.doc.plain_bytes(structural=True))
            _M.parse_stream(sv.doc.plain_bytes(structural=True))
            L.append("整档重写自检 = %d 字节，可解析" % n)
        except Exception as e:
            L.append("整档重写自检 = 失败：%r" % (e,))
            L.append("结果: NG")
            return L
    ok = (host is not None) and (not (sv is None and doc is not None))
    L.append("结果: %s" % ("OK" if ok else "NG"))
    return L


def _hard_exit(code):
    """不走解释器正常收尾的退出。

    ⚠ tkinter + PyInstaller onefile 的收尾**偶尔会卡死**（Tcl 拆除 / 删 `_MEI` 临时
    目录那一段）：窗口已经关掉、自检结果文件也写好了，进程却一直不退 ——
    任务管理器里留着，还锁着 `dist` 里的文件；打包自检因此 300s 超时。
    所以退出统一走这里：flush 一下输出就 `os._exit()`。
    """
    try:
        sys.stdout.flush()
        sys.stderr.flush()
    except Exception:
        pass
    os._exit(code)


def _fatal(text):
    try:
        open(os.path.join(codec.app_dir(), "error.log"), "w",
             encoding="utf-8").write(text)
    except OSError:
        pass
    try:
        messagebox.showerror("程序异常", text[-1200:])
    except Exception:
        pass
    return 3


if __name__ == "__main__":
    # 所有退出路径统一走 `_hard_exit`（含自检、缺依赖、关窗口），不走 `sys.exit()`。
    _hard_exit(main())
