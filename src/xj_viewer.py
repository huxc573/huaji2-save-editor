# -*- coding: utf-8 -*-
"""《画迹2：缘起凡尘》存档工具 v0.4 —— tkinter 界面（界面参照画迹1 的编辑器）。

页签（顺序与画迹1 对齐）：
  1. 概览 / 快捷修改      存银/步数/次数 + 防作弊体检（一键按游戏规则修复 + 清作弊标记）
  2. 全部解析数据         全局搜索 + 树形浏览（懒加载）+ 右侧详情 + 右键菜单（中文注释）
  3. 角色 / 属性          等级/HP/MP/名字/经验 + 中文五维（Game_Actor_Attr）+ 技能装备
  4. 背包 / 物品          4 页 × 20 格：改数量 / 清空 / 添加（自动同步物品计数校验）
  5. 召唤兽               等级·气血·五维·六项资质·忠诚·寿命 + 常用预设
  6. 开关 / 变量          双击切换 / 修改（带游戏自己的名字注释）
  7. 数据表 (CSV)         Data\\*.rvdata2 → CSV（物品/武器/防具/技能/状态/角色/职业/敌人）
  8. 说明 / 机制          密钥、存档结构、防作弊、数据表说明
  9. 更新日志             CHANGELOG.md

启动：python src/xj_viewer.py [存档路径] [--selftest]
"""
import os
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
from tkinter import filedialog, messagebox, ttk  # noqa: E402

import xj_backup  # noqa: E402
import xj_baby    # noqa: E402
import xj_codec   # noqa: E402
import xj_db      # noqa: E402
import xj_env     # noqa: E402
import xj_game    # noqa: E402
import xj_marshal as M  # noqa: E402
import xj_model   # noqa: E402
import xj_nodes   # noqa: E402
import xj_notes   # noqa: E402
import xj_save    # noqa: E402


class _IV(object):
    """`xj_save.ival(节点, "@actor_id")` 那种写法的小侍从（拿整数 ivar）。"""

    @staticmethod
    def ival(obj, name, default=0):
        v = M.value_of(xj_save._deref(xj_save.ivar(obj, name)))
        try:
            return default if v is None else int(v)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def none(obj, name, default=None):
        return xj_save._deref(xj_save.ivar(obj, name))

APP_NAME = "画迹2 存档工具"
VERSION = "v0.4.7"
AUTHOR = "huxc573"
HOMEPAGE = "https://github.com/huxc573/huaji2-save-editor"
ISSUES = HOMEPAGE + "/issues"
LICENSE_NAME = "MIT"
TITLE = "%s %s" % (APP_NAME, VERSION)

CHILD_LIMIT = 300          # 数据树每层最多显示多少项（真实存档有几万个容器）
LAST_TXT = os.path.join(os.path.expanduser("~"), ".huaji2_save_editor_last.txt")
DEFAULT_CSV_DIR = os.path.join(os.path.dirname(HERE), "csv")


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
  界面、快捷键、右键菜单、"导出报告/导出明文"都沿用**画迹1 编辑器**的习惯，
  用过的直接上手。v0.4 新增了 4 个能改玩法数据的页：
      「背包 / 物品」（4 页×20 格，改数量/清空/加物品）
      「召唤兽」（等级·气血·魔法·六项资质·忠诚·寿命·成长·五维）
      「角色 / 属性」里的"获得经验"
      「概览 / 快捷修改」里的"防作弊体检"（一键修复 + 清除作弊标记）
  另外「数据表 (CSV)」页把 Data\\*.rvdata2 转成 CSV 查表。
  独立发行版：dist\\画迹2存档工具v0.4.exe（XJCodec32.exe 要挨着它放）。

一、这个游戏的存档
  <游戏根>\\save.rvdata2（手动存档）
  <游戏根>\\AutoSave\\save00..29.rvdata2（自动存档）
  存档由 System\\main.dll 加密，密钥 **tiyan_version**。

二、三个密钥（都已逆向出来）
  761205            Data\\*.rvdata2 数据库、System\\Game.md5
  imoutogadaisuki   Data\\Scripts.rvdata2（游戏脚本本体）
  tiyan_version     存档 save.rvdata2 / AutoSave\\*.rvdata2
  密钥不对时 main.dll 不报错，只写 0 字节空文件 —— 本工具靠这个判定命中，
  按文件名猜不出时还会依次试这三个密钥。

三、存档结构
  明文 = 两个 Marshal 对象相接（各自带 04 08 头）：
      { :temp => nil }                                      <- header
      { :system :timer :message :switches :variables
        :self_switches :actors :party :troop :map :player }  <- contents
  角色的五维/潜能是中文实例变量，放在 Game_Actor.@attr（类 Game_Actor_Attr）：
      @体质 @法力 @力量 @耐力 @敏捷 @潜能 @人气 @贡献 @体力 @活力

四、防作弊（重要，游戏查三重）
  1) Lock 校验和：存银（游戏里就叫这个名，就是金钱）等关键数值被 Lock 包着：
        @master = @value * 91 + 45 + seed / 800   （seed = $game_system.seeds[:shield]）
     游戏读的时候会验算，不一致就 msgbox '游戏异常！' 然后 exit。
     本工具改存银时自动重算 @master。
  2) 周期检查（$jiance）：游戏每 300 帧（约 5 秒）查一次
        角色等级 > 60 / 出战召唤兽等级 > 65 / 存银 > 30,000,000 /
        仓库页号 > 3 / 五维总点数 > 等级*10+500
     超了就置 @cheated = 当前帧号；之后游戏会弹「存档异常！」并退出。
     ⇒ 用「概览 / 快捷修改」页的「体检 → 一键按规则修复 → 清除作弊标记」。
  3) 物品计数校验（Change）：$game_system.security[:items] 记着
     "这件物品累计获得过几个"（逐位数字 AES-ECB 加密，密钥 admin_1941344749）。
     本工具改背包数量/加物品时会自动一起改对；也能手动「同步物品计数校验」。

五、Data 目录下的 .rvdata2
  **全都被加密**（与存档同一套 main.dll 加密，密钥 761205）。本工具直接解密＋解析，
  可转成 CSV 方便查表（Excel 双击即开，utf-8-sig 编码）：
      Items 物品 / Weapons 武器 / Armors 防具 / Skills 技能 / States 状态
      Actors 角色 / Classes 职业 / Enemies 敌人
      （可选：Troops 敌人队伍 / CommonEvents 公共事件）
  嵌套字段会翻成人话，例如物品 @effects →「HP回复 +500%；附加状态#1 0%」，
  伤害 →「伤害:无 公式:0 浮动:20% 会心:否 属性:0」。
  Map / System / Scripts / Tilesets / Animations 不转（用处不大）。

六、常用位置（第 2 页可以搜字段名直接跳过去）
  :party    @gold 存银（Lock） @actors 出战成员 @items 背包 @steps 步数
            @warehouse_page 仓库页号
  :system   @security[:items] 物品计数校验 @cheated 作弊标记 @seeds 防作弊种子
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
            import xj_changelog
            if getattr(xj_changelog, "TEXT", ""):
                return xj_changelog.TEXT
        except Exception:
            pass
    for p in (os.path.join(os.path.dirname(HERE), "CHANGELOG.md"),
              os.path.join(xj_codec.app_dir(), "CHANGELOG.md")):
        t = _read_text(p)
        if t and not t.startswith("（读不到"):
            return t
    try:
        import xj_changelog
        if getattr(xj_changelog, "TEXT", ""):
            return xj_changelog.TEXT
    except Exception:
        pass
    return "（没有内置更新日志，也没找到 CHANGELOG.md）"


CHANGELOG = _load_changelog()


class App(object):
    def __init__(self, root, save_path=None):
        self.tk = tk
        self.ttk = ttk
        self.root = root
        # Tk 回调里未捕获的异常默认只往 stderr 打一行；打包成 exe 后就变成"点了没反应"
        root.report_callback_exception = self._tk_exception

        self.doc = None            # xj_model.Doc
        self.sv = None             # xj_save.SaveDoc（不是本作存档时为 None）
        self.g = None              # xj_game.GameEditor（背包/召唤兽/防作弊）
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
        if auto:
            self.var_path.set(auto)
            root.after(200, lambda: self.load(auto))
        else:
            self.set_status("请点「选择存档…」打开 <游戏根>\\save.rvdata2")

    # ================================================== 顶部
    def _build_top(self, save_path):
        tk, ttk = self.tk, self.ttk
        top = ttk.Frame(self.root, padding=6)
        top.pack(fill="x")
        ttk.Button(top, text="选择存档…", command=self.choose_file).pack(side="left")
        self.var_path = tk.StringVar(value=save_path or "")
        ttk.Entry(top, textvariable=self.var_path, width=58).pack(side="left", padx=6)
        ttk.Button(top, text="重新载入", command=self.reload).pack(side="left")
        ttk.Separator(top, orient="vertical").pack(side="left", fill="y", padx=6)
        ttk.Button(top, text="保存修改(Ctrl+S)",
                   command=self.save_save).pack(side="left")
        ttk.Button(top, text="放弃修改", command=self.reload).pack(side="left", padx=4)
        ttk.Separator(top, orient="vertical").pack(side="left", fill="y", padx=6)
        ttk.Button(top, text="导出报告", command=self.export_report).pack(side="left")
        ttk.Button(top, text="导出明文", command=self.export_plain).pack(side="left",
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
        ttk.Button(info, text="关于", command=self.show_about,
                   width=6).pack(side="left", padx=8)
        ttk.Button(info, text="复制地址", command=self.copy_homepage,
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
        self._tab_switch()
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

        self.txt_info = tk.Text(f, height=14, wrap="none", font=("Consolas", 10))
        self.txt_info.pack(fill="x")

        g = ttk.LabelFrame(f, text="快捷修改（先点「应用」，再点上面的「保存修改」）",
                           padding=10)
        g.pack(fill="x", pady=8)
        self.var_gold = tk.StringVar()
        self.var_steps = tk.StringVar()
        self.var_savecnt = tk.StringVar()
        self.var_battlecnt = tk.StringVar()
        rows = [("存银", self.var_gold,
                 "游戏里就叫「存银」；Lock 包装，改值会同步重算 @master；"
                 "上限 30,000,000"),
                ("步数", self.var_steps, ""),
                ("存档次数", self.var_savecnt, ""),
                ("战斗次数", self.var_battlecnt, "")]
        for i, (label, var, hint) in enumerate(rows):
            ttk.Label(g, text=label, width=9).grid(row=i, column=0, sticky="w", pady=3)
            ttk.Entry(g, textvariable=var, width=20).grid(row=i, column=1, sticky="w")
            if hint:
                ttk.Label(g, text=hint, foreground="#888").grid(
                    row=i, column=2, sticky="w", padx=8)
        bar = ttk.Frame(g)
        bar.grid(row=len(rows), column=1, sticky="w", pady=8)
        ttk.Button(bar, text="应用", command=self.apply_quick).pack(side="left")
        ttk.Button(bar, text="检查并修复防作弊校验",
                   command=self.fix_locks).pack(side="left", padx=8)
        self.var_lock = tk.StringVar(value="防作弊校验：—")
        ttk.Label(g, textvariable=self.var_lock).grid(
            row=len(rows) + 1, column=0, columnspan=3, sticky="w")

        # ---- 防作弊体检（v0.4：游戏每 300 帧会自己查一遍）
        h = ttk.LabelFrame(f, text="防作弊体检（游戏自己的检查规则）", padding=10)
        h.pack(fill="both", expand=True, pady=8)
        ttk.Label(h, text="游戏每 300 帧检查一次：角色等级 ≤ 60、出战召唤兽等级 ≤ 65、"
                          "存银 ≤ 30,000,000、仓库页号 ≤ 3、五维总点数 ≤ 等级*10+500。\n"
                          "越界就把存档标记成「作弊」（@cheated），之后 20 分钟弹警告、"
                          "25 分钟强制退出。",
                  foreground="#555", justify="left").pack(anchor="w")
        self.tv_guard = ttk.Treeview(h, columns=("a", "b", "c", "d"),
                                     show="headings", height=9)
        for c, w, t in (("a", 240, "项目"), ("b", 130, "当前值"),
                        ("c", 130, "上限/记录值"), ("d", 420, "说明")):
            self.tv_guard.heading(c, text=t)
            self.tv_guard.column(c, width=w, anchor="w")
        self.tv_guard.pack(fill="both", expand=True, pady=6)
        gbar = ttk.Frame(h)
        gbar.pack(fill="x")
        ttk.Button(gbar, text="体检",
                   command=self.guard_check).pack(side="left")
        ttk.Button(gbar, text="一键按规则修复",
                   command=self.guard_fix).pack(side="left", padx=6)
        ttk.Button(gbar, text="清除作弊标记",
                   command=self.guard_clear).pack(side="left", padx=6)
        ttk.Button(gbar, text="同步物品计数校验",
                   command=self.guard_resync).pack(side="left", padx=6)

        # ---- 机器码：单独一页（照画迹1 的布局）
        mq = ttk.Frame(h)
        mq.pack(fill="x", pady=(6, 0))
        self.var_machine_quick = tk.StringVar(value="机器码：—　（详细在「机器码」页）")
        ttk.Label(mq, textvariable=self.var_machine_quick,
                  foreground="#555").pack(anchor="w")

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
                          "所以存档换到别的电脑上打不开；把新机器的机器码「加入」进去就行了。",
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
        ttk.Button(bar1, text="读取本机机器码",
                   command=self.machine_fill_local).pack(side="left", padx=6)
        ttk.Button(bar1, text="读存档里第一个",
                   command=self.machine_fill_saved).pack(side="left", padx=6)
        ttk.Button(bar1, text="刷新",
                   command=self.machine_show).pack(side="left", padx=6)

        bar2 = ttk.Frame(eb)
        bar2.pack(fill="x", pady=8)
        ttk.Button(bar2, text="加入存档（追加，推荐）",
                   command=self.machine_add).pack(side="left")
        ttk.Button(bar2, text="替换成这个（只留一个）",
                   command=self.machine_set).pack(side="left", padx=6)
        ttk.Button(bar2, text="用本机机器码替换",
                   command=self.machine_use_local).pack(side="left", padx=6)
        ttk.Button(bar2, text="清空存档记录",
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
                          "「删除非最新」只留最新的一份。",
                  foreground="#777").pack(anchor="w", pady=(2, 6))

        bar = ttk.Frame(f)
        bar.pack(fill="x")
        ttk.Button(bar, text="立即备份",
                   command=self.saves_backup).pack(side="left")
        ttk.Button(bar, text="恢复选中",
                   command=self.saves_restore).pack(side="left", padx=6)
        ttk.Button(bar, text="恢复最新",
                   command=self.saves_restore_newest).pack(side="left", padx=6)
        ttk.Button(bar, text="删除选中",
                   command=self.saves_delete).pack(side="left", padx=6)
        ttk.Button(bar, text="删除非最新",
                   command=self.saves_delete_old).pack(side="left", padx=6)
        ttk.Button(bar, text="刷新",
                   command=self.saves_refresh).pack(side="left", padx=6)
        ttk.Button(bar, text="打开备份目录",
                   command=self.saves_open_dir).pack(side="left", padx=6)

        cols = ("time", "kind", "size", "name", "note")
        self.tv_saves = ttk.Treeview(f, columns=cols, show="headings", height=16,
                                     selectmode="extended")
        for c, w, t in (("time", 170, "时间"), ("kind", 110, "类型"),
                        ("size", 90, "大小"), ("name", 330, "文件"),
                        ("note", 380, "备注")):
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
        return xj_backup.backup_dir(self.doc.path, create=False)

    def saves_refresh(self):
        self.tv_saves.delete(*self.tv_saves.get_children())
        self.save_rows = []
        if not self.doc:
            self.var_saves_info.set("存档管理：还没打开存档")
            return
        rows = xj_backup.list_backups(self.doc.path)
        self.save_rows = rows
        kind_cn = {"auto": "自动", "manual": "手动",
                   "before-restore": "恢复前", "other": "其它"}
        for i, r in enumerate(rows):
            self.tv_saves.insert("", "end", iid="b%d" % i,
                                 values=(r["stamp"].replace("_", " "),
                                         kind_cn.get(r["kind"], r["kind"]),
                                         "%.1f KB" % (r["size"] / 1024.0),
                                         r["name"], r["note"]))
        d = xj_backup.backup_dir(self.doc.path)
        self.var_saves_info.set(
            "当前存档：%s\n备份目录：%s（共 %d 份，合计 %.1f MB）"
            % (self.doc.path, d, len(rows),
               sum(r["size"] for r in rows) / 1048576.0))

    def saves_backup(self):
        if not self.doc:
            messagebox.showinfo("提示", "先打开一个存档。", parent=self.root)
            return
        try:
            p = xj_backup.backup(self.doc.path, xj_backup.KIND_MANUAL)
        except Exception as e:
            messagebox.showerror("备份失败", zh_error(e), parent=self.root)
            return
        self.saves_refresh()
        self.set_status("已备份到 %s" % os.path.basename(p))
        messagebox.showinfo("备份完成", "已备份：\n%s" % p, parent=self.root)

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
        if not self.doc:
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
            xj_backup.restore(r["path"], self.doc.path)
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
        if not self.doc:
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
                "把存档换回**上一次修改之前**的状态吗？\n\n"
                "  用的备份：%s\n  %s\n\n"
                "（这份是目前最新的一份备份）" % (r["stamp"], r["name"])):
            return
        try:
            xj_backup.restore(r["path"], self.doc.path)
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
        n = xj_backup.remove([r["path"] for r in rows])
        self.saves_refresh()
        self.set_status("已删除 %d 份备份" % n)

    def saves_delete_old(self):
        """删除非最新＝只留最新的一份备份，其余全删。"""
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
        if not self.confirm(
                "删除非最新",
                "只留最新的一份，其余 %d 份都删掉？（不可撤销）\n\n"
                "  保留：%s\n  %s" % (len(rows) - 1, keep["stamp"], keep["name"])):
            return
        kept, n = xj_backup.keep_newest(self.doc.path)
        self.saves_refresh()
        self.set_status("已删除 %d 份旧备份，保留 %s"
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
        ttk.Button(bar, text="搜索", command=self.global_search).pack(side="left",
                                                                     padx=4)
        ttk.Button(bar, text="清空结果", command=self.clear_search).pack(side="left")
        ttk.Button(bar, text="全部折叠", command=self.collapse_all).pack(side="left",
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
        self.tv_hits.pack(fill="x")
        self.tv_hits.bind("<Double-1>", self.goto_search_hit)
        self.tv_hits.bind("<Return>", self.goto_search_hit)

        body = ttk.Panedwindow(f, orient="horizontal")
        body.pack(fill="both", expand=True, pady=4)

        left = ttk.Frame(body)
        self.tree = ttk.Treeview(left, columns=("type", "value", "note"),
                                 show="tree headings")
        self.tree.heading("#0", text="路径 / 字段")
        for c, w, t in (("type", 60, "类型"), ("value", 400, "值"),
                        ("note", 190, "说明")):
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

        ttk.Label(f, text="角色列表（点一行在下面改）").pack(anchor="w")
        cols = ("id", "name", "lv", "hp", "mp", "cls")
        self.tv_actor = ttk.Treeview(f, columns=cols, show="headings", height=7)
        for c, w, t in (("id", 50, "ID"), ("name", 160, "名字"), ("lv", 60, "等级"),
                        ("hp", 90, "HP"), ("mp", 90, "MP"), ("cls", 80, "职业ID")):
            self.tv_actor.heading(c, text=t)
            self.tv_actor.column(c, width=w, anchor="w")
        self.tv_actor.pack(fill="x")
        self.tv_actor.bind("<<TreeviewSelect>>", lambda e: self.load_actor())

        mid = ttk.Frame(f)
        mid.pack(fill="x", pady=6)
        g = ttk.LabelFrame(mid, text="基础字段", padding=8)
        g.pack(side="left", fill="y")
        self.actor_vars = {}
        base = [("@name", "名字"), ("@level", "等级（上限 60）"),
                ("@hp", "HP"), ("@mp", "MP"), ("@tp", "TP"),
                ("@exp", "获得经验"), ("@limit_exp", "升级所需经验")]
        for i, (k, label) in enumerate(base):
            ttk.Label(g, text=label, width=12).grid(row=i, column=0, sticky="w", pady=2)
            var = tk.StringVar()
            ttk.Entry(g, textvariable=var, width=18).grid(row=i, column=1, pady=2)
            self.actor_vars[k] = var

        g2 = ttk.LabelFrame(mid, text="中文属性（Game_Actor_Attr）", padding=8)
        g2.pack(side="left", fill="y", padx=8)
        self.attr_vars = {}
        for i, k in enumerate(xj_save.SaveDoc.ATTR_FIELDS):
            col = (i // 5) * 2
            ttk.Label(g2, text=k[1:], width=7).grid(row=i % 5, column=col,
                                                   sticky="w", pady=2)
            var = tk.StringVar()
            ttk.Entry(g2, textvariable=var, width=8).grid(row=i % 5, column=col + 1,
                                                          pady=2, padx=(0, 8))
            self.attr_vars[k] = var

        bar = ttk.Frame(f)
        bar.pack(fill="x")
        ttk.Button(bar, text="应用修改", command=self.apply_actor).pack(side="left")
        ttk.Button(bar, text="满级(60)",
                   command=lambda: self.actor_preset("maxlv")).pack(side="left", padx=6)
        ttk.Button(bar, text="经验 +10000",
                   command=lambda: self.actor_preset("exp")
                   ).pack(side="left", padx=6)
        ttk.Button(bar, text="回满 HP/MP",
                   command=lambda: self.actor_preset("heal")).pack(side="left", padx=6)
        ttk.Button(bar, text="属性全 +10",
                   command=lambda: self.actor_preset("attr")).pack(side="left", padx=6)

        ttk.Label(f, text="已学技能 / 装备 / 五维（只读，技能名取自 Data\\Skills.rvdata2）"
                  ).pack(anchor="w", pady=(8, 0))
        self.txt_actor = tk.Text(f, height=8, wrap="word",
                                 font=("Microsoft YaHei UI", 10))
        self.txt_actor.pack(fill="both", expand=True)

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
        for p in range(xj_game.MAX_PACK_PAGE):
            ttk.Radiobutton(bar, text="背包%d" % (p + 1), value=p,
                            variable=self.var_bag_page,
                            command=self.fill_party).pack(side="left", padx=2)
        ttk.Label(bar, text="　种类：").pack(side="left")
        self.var_bag_kind = tk.StringVar(value="Items")
        for key, _iv, cn, _db in xj_game.KINDS:
            ttk.Radiobutton(bar, text=cn, value=key,
                            variable=self.var_bag_kind,
                            command=self.fill_party).pack(side="left", padx=2)
        ttk.Button(bar, text="刷新", command=self.fill_party).pack(side="right")

        ttk.Label(f, text="每页 20 格（槽号 = 页*20 + 格）；左键选格子，右边模板里双击物品＝写进去"
                  ).pack(anchor="w", pady=(6, 2))

        body = ttk.Panedwindow(f, orient="horizontal")
        body.pack(fill="both", expand=True)

        # ---- 左：格子列表
        left = ttk.Frame(body)
        ttk.Label(left, text="背包格子").pack(anchor="w")
        ttk.Label(left, text="背包格子（“内容”列是孵化蛋/礼包那种运行时内容）"
                  ).pack(anchor="w")
        cols = ("slot", "idx", "id", "name", "count", "content")
        self.tv_pack = ttk.Treeview(left, columns=cols, show="headings", height=14)
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
        ttk.Button(tr, text="找", width=4,
                   command=self.fill_templates).pack(side="left", padx=3)
        ttk.Label(right, text="物品模板（Data\\%s.rvdata2）"
                  % "Items").pack(anchor="w")
        self.tv_tpl = ttk.Treeview(right, columns=("id", "name"),
                                   show="headings", height=11)
        for c, w, t in (("id", 60, "ID"), ("name", 190, "名称")):
            self.tv_tpl.heading(c, text=t)
            self.tv_tpl.column(c, width=w, anchor="w")
        vs2 = ttk.Scrollbar(right, orient="vertical", command=self.tv_tpl.yview)
        self.tv_tpl.configure(yscrollcommand=vs2.set)
        vs2.pack(side="right", fill="y")
        self.tv_tpl.pack(fill="both", expand=True)
        self.tv_tpl.bind("<Double-1>", lambda e: self.bag_use_template())
        self.var_tpl_note = tk.StringVar(value="")
        ttk.Label(right, textvariable=self.var_tpl_note, foreground="#555",
                  wraplength=300, justify="left").pack(anchor="w", pady=2)
        ttk.Button(right, text="写入选中的格子（双击模板也行）",
                   command=self.bag_use_template).pack(fill="x", pady=2)
        ttk.Button(right, text="放进第一个空格子",
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
        ttk.Button(act, text="改数量",
                   command=self.bag_set_count).pack(side="left", padx=6)
        ttk.Button(act, text="按 id 写入",
                   command=self.bag_add).pack(side="left", padx=6)
        ttk.Button(act, text="清空格子",
                   command=self.bag_clear).pack(side="left", padx=6)
        ttk.Button(act, text="本页全部 99",
                   command=lambda: self.bag_all(99)).pack(side="left", padx=6)
        ttk.Button(act, text="背包体检",
                   command=self.bag_check).pack(side="left", padx=6)
        ttk.Button(act, text="一键修复",
                   command=self.bag_fix).pack(side="left", padx=6)
        ttk.Button(act, text="同步计数校验",
                   command=self.guard_resync).pack(side="left", padx=6)

        pay = ttk.Frame(f)
        pay.pack(fill="x")
        self.var_bag_kid = tk.StringVar()
        ttk.Label(pay, text="孵出/开出对象 id（孵化蛋类用，留空＝随机）："
                  ).pack(side="left")
        ttk.Entry(pay, textvariable=self.var_bag_kid, width=8).pack(side="left")
        ttk.Button(pay, text="给选中的格子重抽内容",
                   command=self.bag_reroll).pack(side="left", padx=6)
        ttk.Label(pay, text="　（召唤兽 id 看 Data\\Actors；留空就是按游戏范围随机）",
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
        ttk.Button(top, text="新增召唤兽",
                   command=self.baby_add_dialog).pack(side="left", padx=(10, 4))
        ttk.Button(top, text="设为出战",
                   command=self.baby_set_active).pack(side="left")
        ttk.Button(top, text="放生（删除）",
                   command=self.baby_delete).pack(side="left", padx=4)
        ttk.Button(top, text="恢复模板名",
                   command=self.baby_restore_name).pack(side="left")

        self.var_baby_note = tk.StringVar(value="")
        ttk.Label(f, textvariable=self.var_baby_note, foreground="#555",
                  justify="left", wraplength=1180).pack(anchor="w", pady=(4, 4))

        # ---------------- 召唤兽列表（画迹1 那种一览）
        cols = ("no", "name", "tpl", "lv", "grow", "loyal", "life", "atk",
                "def", "hp", "mp", "agi", "eva", "sk", "act")
        heads = ("序", "名字", "模板", "等级", "成长", "忠诚", "寿命", "攻资",
                 "防资", "体资", "法资", "速资", "躲资", "技能", "出战")
        widths = (34, 104, 108, 50, 54, 54, 66, 60, 60, 60, 60, 60, 60, 44, 44)
        self.tv_babies = ttk.Treeview(f, columns=cols, show="headings",
                                      height=8, selectmode="browse")
        for c, h, w in zip(cols, heads, widths):
            self.tv_babies.heading(c, text=h)
            self.tv_babies.column(c, width=w, anchor="w")
        self.tv_babies.tag_configure("active", foreground="#0a0")
        hs = ttk.Scrollbar(f, orient="horizontal", command=self.tv_babies.xview)
        self.tv_babies.configure(xscrollcommand=hs.set)
        self.tv_babies.pack(fill="x")
        hs.pack(fill="x")
        self.tv_babies.bind("<<TreeviewSelect>>", lambda e: self.on_baby_select())

        edit = ttk.Frame(f)
        edit.pack(fill="x", pady=(6, 0))
        ttk.Label(edit, text="改字段：").pack(side="left")
        self.var_baby_key = tk.StringVar()
        ttk.Entry(edit, textvariable=self.var_baby_key, width=12,
                  state="readonly").pack(side="left")
        self.var_baby_val = tk.StringVar()
        ttk.Entry(edit, textvariable=self.var_baby_val, width=14).pack(side="left")
        ttk.Button(edit, text="应用", command=self.apply_baby).pack(side="left",
                                                                   padx=6)
        for txt, what in (("满级(65)", "maxlv"), ("回满气血/魔法", "heal"),
                          ("忠诚满", "loyalty"), ("寿命满", "life"),
                          ("六项资质+100", "qual"), ("六项资质+500", "qual500"),
                          ("成长+0.1", "grow"), ("五维+10", "five")):
            ttk.Button(edit, text=txt,
                       command=lambda w=what: self.baby_preset(w)
                       ).pack(side="left", padx=2)

        mid = ttk.Frame(f)
        mid.pack(fill="both", expand=True, pady=(6, 0))
        left = ttk.Frame(mid)
        left.pack(side="left", fill="both", expand=True)
        cols2 = ("k", "v", "note")
        self.tv_baby = ttk.Treeview(left, columns=cols2, show="headings", height=12)
        for c, w, t in (("k", 190, "字段"), ("v", 110, "当前值"),
                        ("note", 300, "说明")):
            self.tv_baby.heading(c, text=t)
            self.tv_baby.column(c, width=w, anchor="w")
        self.tv_baby.pack(fill="both", expand=True)
        self.tv_baby.bind("<<TreeviewSelect>>", lambda e: self.baby_pick())

        # ---------------- 名字 + 技能
        right = ttk.Frame(mid)
        right.pack(side="left", fill="both", expand=True, padx=(8, 0))
        nf = ttk.LabelFrame(right, text="名字（游戏显示 @attr.@name）", padding=6)
        nf.pack(fill="x")
        self.var_baby_name = tk.StringVar()
        ttk.Entry(nf, textvariable=self.var_baby_name, width=16).pack(side="left")
        ttk.Button(nf, text="改显示名",
                   command=self.baby_rename).pack(side="left", padx=3)
        ttk.Button(nf, text="改基础名",
                   command=lambda: self.baby_rename(base=True)).pack(side="left")
        self.var_baby_name_ok = tk.StringVar(value="")
        ttk.Label(nf, textvariable=self.var_baby_name_ok,
                  foreground="#777").pack(side="left", padx=8)

        skf = ttk.LabelFrame(right, text="技能（@skills，最多 12 个）", padding=6)
        skf.pack(fill="both", expand=True, pady=(6, 0))
        skbar = ttk.Frame(skf)
        skbar.pack(fill="x")
        ttk.Label(skbar, text="搜索").pack(side="left")
        self.var_skill_search = tk.StringVar()
        ske = ttk.Entry(skbar, textvariable=self.var_skill_search, width=10)
        ske.pack(side="left", padx=3)
        ske.bind("<KeyRelease>", lambda e: self.fill_skill_templates())
        self.var_skill_pick = tk.StringVar()
        self.cb_skill = ttk.Combobox(skbar, textvariable=self.var_skill_pick,
                                     state="readonly", width=26)
        self.cb_skill.pack(side="left")
        self.cb_skill.bind("<<ComboboxSelected>>",
                           lambda e: self.show_skill_desc())
        ttk.Button(skbar, text="学会", command=self.baby_skill_add).pack(side="left",
                                                                       padx=4)
        ttk.Button(skbar, text="忘掉选中",
                   command=self.baby_skill_del).pack(side="left")
        ttk.Button(skbar, text="清空", command=self.baby_skill_clear).pack(
            side="left", padx=4)
        self.var_skill_desc = tk.StringVar(value="")
        ttk.Label(skf, textvariable=self.var_skill_desc, foreground="#555",
                  justify="left", wraplength=560).pack(anchor="w", pady=(4, 0))
        self.tv_baby_skills = ttk.Treeview(skf, columns=("id", "name", "desc"),
                                           show="headings", height=6,
                                           selectmode="browse")
        for c, t, w in (("id", "技能 id", 62), ("name", "名字", 140),
                        ("desc", "描述", 340)):
            self.tv_baby_skills.heading(c, text=t)
            self.tv_baby_skills.column(c, width=w, anchor="w")
        self.tv_baby_skills.pack(fill="both", expand=True, pady=(6, 0))
        self.tv_baby_skills.bind("<<TreeviewSelect>>",
                                 lambda e: self.show_skill_desc())

        self.txt_baby = tk.Text(f, height=3, wrap="word",
                                font=("Microsoft YaHei UI", 10))
        self.txt_baby.pack(fill="x", pady=(6, 0))

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
        """召唤兽助手（xj_baby.Babies）——换存档后重建一次。"""
        if getattr(self, "_babies_src", None) is not self.g or not hasattr(
                self, "_babies_obj"):
            self._babies_obj = xj_baby.Babies(self.g) if self.g is not None \
                else None
            self._babies_src = self.g
        return self._babies_obj

    @staticmethod
    def _life_text(v):
        if v == "infinite":
            return "永生"
        return "" if v is None else v

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
        for i, b in self.baby_rows:
            def v(k, _b=b):
                return self.g.baby_value(_b, k)
            tags = ("active",) if i == act_i else ()
            self.tv_babies.insert(
                "", "end", iid="bb%d" % i,
                values=("%d" % i, self.g.baby_name(b),
                        "%s(%s)" % (bd.template_name(b), _IV.ival(b, "@actor_id")),
                        v("level"), v("grow"), v("loyalty"), self._life_text(v("life")),
                        v("atk"), v("def"), v("hpq"), v("mpq"), v("agi"), v("eva"),
                        len(bd.skills(b)), "★" if i == act_i else ""),
                tags=tags)
        self.var_baby_note.set(
            "共 %d 只（★ = 当前出战）；「新增召唤兽」可以加任意一种，"
            "包括正常玩法拿不到的**小孩**（小精灵/小毛头/小魔头/小仙灵/"
            "小仙女/小丫丫，它们属于神兽资质3 池，没有任何道具能开出来）。"
            % len(self.baby_rows))
        kids = self.tv_babies.get_children()
        if kids:
            self.tv_babies.selection_set(kids[0])
            self.on_baby_select()
        else:
            self.load_baby()

    def on_baby_select(self):
        self.load_baby()

    def refresh_baby_list_keep(self, baby):
        """刷列表，但“选中”还是原来那只（不然会跳回第一行）。"""
        idx = [k for k, x in self.baby_rows if x is baby]
        self.fill_baby_list()
        if not idx:
            return
        iid = "bb%d" % idx[0]
        try:
            if self.tv_babies.exists(iid):
                self.tv_babies.selection_set(iid)
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

    def load_baby(self):
        b = self._baby()
        self.tv_baby.delete(*self.tv_baby.get_children())
        self.tv_baby_skills.delete(*self.tv_baby_skills.get_children())
        self.txt_baby.delete("1.0", "end")
        self.var_baby_name.set("")
        self.var_baby_name_ok.set("")
        if b is None or self.g is None:
            return
        bd = self.babies_ed()
        for key, label, _path, _t in xj_game.GameEditor.BABY_FIELDS:
            v = self.g.baby_value(b, key)
            if key == "life":
                v = self._life_text(v)
            self.tv_baby.insert("", "end", iid="b_%s" % key,
                                values=(label, "" if v is None else v, key))
        sk = self.g.baby_skills(b)
        tpl_id = _IV.ival(b, "@actor_id")
        idx = [k for k, x in self.baby_rows if x is b]
        meta = self._skills_meta()
        for sid in bd.skills(b):
            nm, desc = meta.get(sid, ("?", ""))
            self.tv_baby_skills.insert("", "end", iid="sk%d" % sid,
                                       values=(sid, nm, desc))
        self.show_skill_desc()
        self.var_baby_name.set(bd.display_name(b))
        ok = bd.name_ok(bd.display_name(b))
        self.var_baby_name_ok.set("√ 名字在游戏名字表里" if ok
                                  else "⚠ 名字不在名字表里（战斗可能取不到立绘）")
        self.fill_skill_templates()
        self.txt_baby.insert("1.0", "\n".join([
            "第 %d 只：%s（模板 %s #%d，%s）　等级 %s / 忠诚 %s / 寿命 %s / 成长 %s"
            % (idx[0] if idx else -1, bd.display_name(b), bd.template_name(b),
               tpl_id, "神兽" if bd.is_god(tpl_id) else "普通",
               self.g.baby_value(b, "level"), self.g.baby_value(b, "loyalty"),
               self._life_text(self.g.baby_value(b, "life")),
               self.g.baby_value(b, "grow")),
            "已学技能：%s" % ("、".join("#%d %s" % (i, n) for i, n in sk) or "（无）"),
            "提示：游戏的周期检查只看「当前出战那只」的等级（>65 算作弊）；"
            "五维总点数也有上限（等级×10+500）。改完记得 Ctrl+S。",
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
        """{技能 id: (名字, 描述)}（Data\\Skills 表，带缓存）。"""
        if getattr(self, "_skill_meta", None) is None:
            meta = {}
            try:
                _r, items = xj_db.load("Skills")
                for i, node in items:
                    desc = xj_db.s(node, "@description") or ""
                    desc = desc.replace("\\n", " ").replace("\n", " ").strip()
                    meta[i] = (xj_db.s(node, "@name") or "", desc)
            except Exception:
                meta = {}
            self._skill_meta = meta
        return self._skill_meta

    def _skill_names(self):
        return dict((i, nm) for i, (nm, _d) in self._skills_meta().items())

    def show_skill_desc(self):
        """显示选中的技能描述（下拉里选的，或技能表里选中的）。"""
        meta = self._skills_meta()
        sid = None
        sel = self.tv_baby_skills.selection()
        if sel:
            try:
                sid = int(sel[0][2:])
            except ValueError:
                sid = None
        if sid is None:
            sid = self._skill_pick_id()
        if sid is None or sid not in meta:
            self.var_skill_desc.set("")
            return
        nm, desc = meta[sid]
        self.var_skill_desc.set("技能 #%d %s：%s" % (sid, nm, desc or "（没有说明）"))

    def fill_skill_templates(self):
        nm = self._skill_names()
        kw = self.var_skill_search.get().strip()
        vals = []
        for i in sorted(nm):
            if not nm[i]:
                continue
            if kw and kw not in nm[i] and kw != str(i):
                continue
            vals.append("#%d %s" % (i, nm[i]))
        self._skill_choices = vals
        self.cb_skill["values"] = vals
        if vals and self.var_skill_pick.get() not in vals:
            self.var_skill_pick.set(vals[0])

    def _skill_pick_id(self):
        s = self.var_skill_pick.get()
        if s.startswith("#") and " " in s:
            try:
                return int(s[1:s.index(" ")])
            except ValueError:
                return None
        return None

    def baby_skill_add(self):
        b = self._baby()
        sid = self._skill_pick_id()
        if b is None or sid is None:
            messagebox.showinfo("提示", "先在列表里选一只召唤兽、再选一个技能。",
                                parent=self.root)
            return
        try:
            self.babies_ed().learn(b, sid)
        except Exception as e:
            messagebox.showerror("改不了", zh_error(e), parent=self.root)
            return
        self.mark_dirty()
        self.load_baby()
        self.refresh_baby_list_keep(b)
        self.set_status("已学会技能 #%d" % sid)

    def baby_skill_del(self):
        b = self._baby()
        sel = self.tv_baby_skills.selection()
        if b is None or not sel:
            messagebox.showinfo("提示", "先在技能列表里选一个要忘掉的技能。",
                                parent=self.root)
            return
        sid = int(sel[0][2:])
        self.babies_ed().forget(b, sid)
        self.mark_dirty()
        self.load_baby()
        self.refresh_baby_list_keep(b)
        self.set_status("已忘掉技能 #%d" % sid)

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
        ttk.Checkbutton(bar, text="只看神兽（含小孩）",
                        variable=var_god).pack(side="left", padx=6)
        var_mut = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="变异（普通召唤兽资质区间 ×0.66）",
                        variable=var_mut).pack(side="left", padx=6)

        cols = ("id", "name", "type", "pool", "lv", "zi", "grow", "life")
        heads = ("id", "名字", "类型", "备注池", "携带等级", "六项资质", "成长", "寿命")
        widths = (46, 116, 50, 90, 60, 230, 50, 60)
        tv = ttk.Treeview(f, columns=cols, show="headings", height=16,
                          selectmode="browse")
        for c, h, w in zip(cols, heads, widths):
            tv.heading(c, text=h)
            tv.column(c, width=w, anchor="w")
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
                if var_god.get() and c["type"] != "神兽":
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
            info.set("共 %d 种可选。神兽（含小孩）资质取定值；"
                     "普通召唤兽资质带随机（勾了“变异”则区间 ×0.66）。"
                     % len(rows))
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
            cid = int(sel[0][1:])
            try:
                self.babies_ed().add(a, cid, mutation=bool(var_mut.get()))
            except Exception as e:
                messagebox.showerror("加不了", zh_error(e), parent=self.root)
                return
            self.mark_dirty()
            win.destroy()
            self.refresh_panels()
            kids = self.tv_babies.get_children()
            if kids:
                self.tv_babies.selection_set(kids[-1])
                self.on_baby_select()
            self.set_status("已新增召唤兽：%s（id=%d）" % (bd.name_of(cid), cid))

        ttk.Button(btns, text="加这只", command=do_add).pack(side="left")
        ttk.Button(btns, text="取消", command=win.destroy).pack(side="left", padx=6)

        # 让窗口在主窗口上居中（不然会跑到屏幕左上角）
        w_ = win
        w_.update_idletasks()
        pw, ph = self.root.winfo_width(), self.root.winfo_height()
        px, py = self.root.winfo_rootx(), self.root.winfo_rooty()
        ww, wh = w_.winfo_width(), w_.winfo_height()
        if pw > 1 and ph > 1:
            w_.geometry("+%d+%d" % (max(0, px + (pw - ww) // 2),
                                    max(0, py + (ph - wh) // 3)))
        self.set_status("新增召唤兽：选一只 → 「加这只」")

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
        b = self._baby()
        if b is None:
            messagebox.showinfo("提示", "先在列表里选一只召唤兽。", parent=self.root)
            return
        idx = [k for k, x in self.baby_rows if x is b][0]
        name = self.g.baby_name(b)
        if not self.confirm("放生（删除）",
                            "把「%s」从这只角色身上删掉？（不可撤销）\n\n"
                            "游戏里相当于放生：数据没了，想找回来只能重新加一只。"
                            % name):
            return
        try:
            self.babies_ed().remove(self._baby_actor(), idx)
        except Exception as e:
            messagebox.showerror("删不了", zh_error(e), parent=self.root)
            return
        self.mark_dirty()
        self.fill_baby_list()
        self.set_status("已放生：%s" % name)

    def baby_set_active(self):
        b = self._baby()
        if b is None:
            return
        idx = [k for k, x in self.baby_rows if x is b][0]
        self.babies_ed().set_active(self._baby_actor(), idx)
        self.mark_dirty()
        self.refresh_baby_list_keep(b)
        self.set_status("已设为出战：%s" % self.g.baby_name(b))

    def baby_rename(self, base=False):
        b = self._baby()
        if b is None:
            return
        name = self.var_baby_name.get().strip()
        if not name:
            messagebox.showinfo("提示", "名字不能是空的。", parent=self.root)
            return
        bd = self.babies_ed()
        if not bd.name_ok(name) and not self.confirm(
                "名字不在名字表里",
                "「%s」不在游戏的召唤兽名字表里。\n\n"
                "名字不是取不到的话，只是战斗里可能取不到对应立绘/音效，"
                "也可能显示成默认样子。仍要改吗？" % name):
            return
        if base:
            bd.set_base_name(b, name)
        else:
            bd.set_display_name(b, name)
        self.mark_dirty()
        self.load_baby()
        self.refresh_baby_list_keep(b)
        self.set_status("已改名：%s" % name)

    def baby_restore_name(self):
        b = self._baby()
        if b is None:
            return
        tpl = self.babies_ed().restore_name(b)
        self.mark_dirty()
        self.load_baby()
        self.refresh_baby_list_keep(b)
        self.set_status("名字已恢复成模板本名：%s" % tpl)

    def baby_pick(self):
        sel = self.tv_baby.selection()
        if not sel:
            return
        vals = self.tv_baby.item(sel[0], "values")
        self.var_baby_key.set(vals[2])
        self.var_baby_val.set(vals[1])

    def apply_baby(self):
        b = self._baby()
        if b is None or self.g is None:
            return
        key = self.var_baby_key.get().strip()
        raw = self.var_baby_val.get().strip()
        if not key or raw == "":
            messagebox.showinfo("提示", "先在上面选一个字段并填值。", parent=self.root)
            return
        try:
            self.g.set_baby(b, key, float(raw) if "." in raw else int(raw, 0))
        except Exception as e:
            messagebox.showerror("修改失败", human(str(e)), parent=self.root)
            return
        self.mark_dirty()
        self.load_baby()
        self.set_status("召唤兽「%s」的 %s 已改" % (self.g.baby_name(b), key))

    def baby_preset(self, what):
        b = self._baby()
        if b is None or self.g is None:
            return
        try:
            did = self.g.baby_preset(b, what)
        except Exception as e:
            messagebox.showerror("修改失败", human(str(e)), parent=self.root)
            return
        if did:
            self.mark_dirty()
            self.load_baby()
            self.set_status("召唤兽预设：%s" % "、".join(did))

    # -------------------------------------------------- 5 开关 / 变量
    def _tab_switch(self):
        tk, ttk = self.tk, self.ttk
        f = ttk.Frame(self.nb, padding=8)
        self.tab_switch = f
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
        ttk.Button(bar, text="全部导出",
                   command=self.db_export_all).pack(side="right", padx=4)
        ttk.Button(bar, text="导出选中表",
                   command=self.db_export_selected).pack(side="right", padx=4)
        ttk.Button(bar, text="选输出目录…",
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

        for key in xj_db.ALL_KEYS:
            self.lst_db.insert("end", "%s —— %s%s" % (
                xj_db.table_label(key), key,
                "" if xj_db.is_default(key) else "（可选）"))
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

    def _guess_save(self):
        if os.path.exists(LAST_TXT):
            p = open(LAST_TXT, encoding="utf-8").read().strip()
            if p and os.path.exists(p):
                return p
        return xj_env.save_path()

    def refresh_env(self):
        g = xj_env.find_game_dir()
        self.var_env.set(
            "游戏目录：%s　|　当前文件：%s　|　32 位宿主：%s"
            % (g or "未找到", self.doc.path if self.doc else "—",
               "有" if os.path.exists(xj_codec.HOST)
               else "缺！先跑 python tools/build_host.py"))

    # ================================================== 打开 / 保存
    def choose_file(self):
        p = filedialog.askopenfilename(
            title="选择存档", initialdir=xj_env.find_game_dir() or "",
            filetypes=[("RPG Maker 存档", "*.rvdata2 *.rxdata *.bin"),
                       ("全部文件", "*.*")])
        if p:
            self.var_path.set(p)
            self.load(p)

    def reload(self):
        p = self.var_path.get().strip() or (self.doc.path if self.doc else "")
        if p:
            self.load(p)

    def load(self, path, quiet=False):
        try:
            self.doc = xj_model.Doc(path)
        except Exception as e:
            self.doc = None
            self.sv = None
            if not quiet:
                messagebox.showerror("打开失败", human(str(e)), parent=self.root)
            self.set_status("打开失败：%s" % human(str(e))[:120])
            return
        try:
            self.sv = xj_save.SaveDoc(doc=self.doc)
            # SaveDoc 是懒解析的，动不动就"建成功"：这里确认它真的像本作存档，
            # 否则（比如 Battle.bt2）后面每个面板都会挨个抛 KeyError。
            # 注意 sections() 给的是 [(名字, 节点), ...]，不是一串名字。
            need = {"system", "party", "actors", "variables"}
            if not need <= set(n for n, _ in self.sv.sections()):
                self.sv = None
        except Exception:
            self.sv = None            # 不是本作存档：只保留"数据树"功能
        self.sync_editor()
        try:
            open(LAST_TXT, "w", encoding="utf-8").write(path)
        except OSError:
            pass
        self.var_path.set(path)
        self.clear_dirty()
        # 每个面板单独兜底：一个面板炸了不能把「全部解析数据」也一起带下去
        bad = self.refresh_panels()
        if bad:
            self.set_status("已载入 %s，但「%s」刷新失败：%s"
                            % (os.path.basename(path), "、".join(bad),
                               self.var_status.get()))
        else:
            self.set_status("已载入 %s（明文 %d 字节，%d 个顶层对象%s）"
                            % (os.path.basename(path), len(self.doc.raw),
                               len(self.doc.objects),
                               "" if self.sv else "；不是本作存档，只有数据树可用"))

    def save_save(self):
        if not self.doc or not self.doc.dirty:
            messagebox.showinfo("保存", "没有改动。", parent=self.root)
            return
        if not self._pre_save_guard():
            return
        # 保存前先在“存档管理”的目录里留一份（同一份文件 90 秒内只留一次）
        auto = xj_backup.auto_backup_once(self.doc.path)
        try:
            p = self.doc.save()
        except Exception as e:
            messagebox.showerror("保存失败", zh_error(e), parent=self.root)
            return
        try:
            self.sv = xj_save.SaveDoc(doc=self.doc)
        except Exception:
            self.sv = None
        self.sync_editor()
        self.clear_dirty()
        self.refresh_panels()
        messagebox.showinfo(
            "保存", "已写回：\n%s\n\n%s"
            % (p, ("存档管理里也留了一份：%s" % os.path.basename(auto))
               if auto else "原文件已备份为 %s.bak.<时间>" % os.path.basename(p)),
            parent=self.root)
        self.set_status("已保存")

    def _pre_save_guard(self):
        """存盘前体检：有超限项 / 作弊标记就说清楚，并问要不要顺手修好。

        为什么必须提醒：游戏的周期检查一旦把 `@cheated` 记下来，20 分钟后就会
        开始“惩罚”（脚本 29485-29495 行：画面转圈、缩放），而那段代码在**战斗中**
        会去碰已经 dispose 的 `$game_player.sprite` → `RGSSError: disposed sprite`。
        """
        if not self.g:
            return True
        try:
            rows = self.g.anti_cheat_report()
        except Exception:
            return True
        over = [r for r in rows if r[3]]
        if not over:
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
            self.refresh_panels()
            self.set_status("保存前已顺手修好：%s" % "、".join(done or ["（无需处理）"]))
            return True
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

    def refresh_panels(self):
        """把所有面板刷一遍。每步单独兜底，返回出错的步骤名列表。

        存档面板和"全部解析数据"互不依赖，一个炸了不该连坐。
        """
        bad = []
        for step, fn in (("概览", self.fill_info), ("数据树", self.fill_tree),
                         ("角色", self.fill_actors), ("背包", self.fill_party),
                         ("召唤兽", self.fill_babies),
                         ("开关/变量", self.fill_switches),
                         ("机器码", lambda: self.machine_show(quiet=True)),
                         ("存档管理", self.saves_refresh),
                         ("环境信息", self.refresh_env)):
            try:
                fn()
            except Exception as e:
                bad.append(step)
                self.err("刷新「%s」失败：%s" % (step, human(str(e))))
        return bad

    def sync_editor(self):
        """sv 变了（载入/保存）就重建 GameEditor。"""
        self.g = xj_game.GameEditor(self.sv) if self.sv else None

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
    def fill_info(self):
        if not self.sv:
            if self.doc:
                self.txt_info.delete("1.0", "end")
                self.txt_info.insert("1.0", "（这个文件不是本作存档，"
                                            "只有「全部解析数据」页可用）")
            return
        L = self.sv.summary_lines()
        L += ["", "存银 = %s（上限 %d）　步数 = %s"
              % (self.sv.gold(), xj_game.MAX_GOLD, self.sv.steps()),
              "存档次数 = %s　战斗次数 = %s"
              % (self.sv.sys_get("@save_count"), self.sv.sys_get("@battle_count")),
              "开关/变量 = %d / %d" % self.sv.counts()]
        bad = self.sv.check_locks()
        L.append("防作弊校验 = %s" % ("全部正常" if not bad
                                      else "不一致 %d 处" % len(bad)))
        self.txt_info.delete("1.0", "end")
        self.txt_info.insert("1.0", "\n".join(L))
        self.var_gold.set(str(self.sv.gold()))
        self.var_steps.set(str(self.sv.steps()))
        for var, name in ((self.var_savecnt, "@save_count"),
                          (self.var_battlecnt, "@battle_count")):
            v = self.sv.sys_get(name)
            var.set("" if v is None else str(v))
        self.var_lock.set("防作弊校验：%s"
                          % ("正常" if not bad
                             else "不一致 %d 处，点右边按钮修复" % len(bad)))
        if self.g:
            ch = M.value_of(xj_save._deref(
                xj_save.ivar(self.sv.section("system"), "@cheated")))
            L2 = ("作弊标记 @cheated = %r" % (ch,))
            if ch:
                L2 += "　← 游戏已判定作弊：20 分钟后警告、25 分钟后强制退出，" \
                      "点「清除作弊标记」"
            L.append(L2)
        try:
            self.guard_check()
        except Exception:
            pass

    def apply_quick(self):
        if not self.sv:
            messagebox.showinfo("提示", "这个文件不是本作存档。", parent=self.root)
            return
        try:
            if self.var_gold.get().strip():
                self.sv.set_gold(int(self.var_gold.get(), 0))
            if self.var_steps.get().strip():
                self.sv.set_steps(int(self.var_steps.get(), 0))
            if self.var_savecnt.get().strip():
                self.sv.sys_set("@save_count", int(self.var_savecnt.get(), 0))
            if self.var_battlecnt.get().strip():
                self.sv.sys_set("@battle_count", int(self.var_battlecnt.get(), 0))
        except Exception as e:
            messagebox.showerror("修改失败", human(str(e)), parent=self.root)
            return
        self.doc.dirty = True
        self.mark_dirty()
        self.fill_info()
        self.fill_party()
        self.set_status("已应用（记得点「保存修改」）")

    def fix_locks(self):
        if not self.sv:
            return
        bad = self.sv.check_locks()
        n = self.sv.repair_locks()
        if n:
            self.doc.dirty = True
            self.mark_dirty()
        self.fill_info()
        messagebox.showinfo("防作弊校验",
                            "检查到不一致 %d 处，已修复 %d 处。\n（记得点「保存修改」）"
                            % (len(bad), n), parent=self.root)

    # ================================================== 防作弊体检
    def guard_check(self):
        """把游戏自己的检查规则跑一遍，结果显示在表里。"""
        self.tv_guard.delete(*self.tv_guard.get_children())
        if not self.g:
            return
        try:
            rows = self.g.anti_cheat_report()
        except Exception as e:
            self.err(e)
            return
        for name, cur, limit, bad, why in rows:
            self.tv_guard.insert("", "end", values=(
                name, cur, limit, ("❌ " + why) if bad else why))
        n_bad = len([r for r in rows if r[3]])
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

    # ================================================== 2 数据树（懒加载）
    def _kids(self, node):
        """返回 [(显示名, 子节点, 中文说明), ...]。

        以前 Hash 的键直接用 `value_of()`，而符号（SymbolNode）没有 `.value`，
        于是满屏都是 `[None]`；现在走 `xj_nodes.children_of()`：
        符号写成 `:system`，并且把 `xj_notes` 里的中文说明带出来。
        """
        return xj_nodes.children_of(node)

    def _add_stub(self, iid):
        node = self.nodes.get(iid)
        if node is None or not self._kids(node):
            return
        self.tree.insert(iid, "end", iid="%s:?" % iid, text="…（展开以加载）",
                         values=("", "", ""))

    def fill_tree(self):
        self.tree.delete(*self.tree.get_children())
        self.nodes.clear()
        self.loaded.clear()
        if not self.doc:
            return
        for i, node in enumerate(self.doc.top_level()):
            iid = "r%d" % i
            self.tree.insert("", "end", iid=iid,
                             text="#%d %s" % (i, xj_model.describe(node)),
                             values=("", "", ""), open=False)
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
            # 说明列：优先中文注释，没有就给节点类型（至少不是空白）
            if not note:
                note = xj_nodes.type_label(kid)
            self.tree.insert(iid, "end", iid=iid2, text=label,
                             values=(xj_nodes.type_label(kid),
                                     short(xj_nodes.brief(kid, 60)), note))
            self.nodes[iid2] = kid
            self._add_stub(iid2)
        if len(kids) > limit:
            self.tree.insert(iid, "end", iid="%s|more" % iid,
                             text="…（共 %d 项，只显示前 %d 项，用搜索定位）"
                                  % (len(kids), limit), values=("", "", ""))

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
        node = xj_save._deref(node)
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
        txt = str(xj_nodes.brief(node2, 200))
        if kw in txt.lower() or kw in path.lower():
            out.append((path, xj_nodes.type_label(node2), short(txt, 60), top,
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
    def fill_actors(self):
        self.tv_actor.delete(*self.tv_actor.get_children())
        self.actor_rows.clear()
        if not self.sv:
            return
        for aid, a in self.sv.actors():
            iid = "a%d" % aid
            self.tv_actor.insert("", "end", iid=iid, values=(
                aid, self.sv.actor_name(a), self.sv.actor_field(a, "@level"),
                self.sv.actor_field(a, "@hp"), self.sv.actor_field(a, "@mp"),
                self.sv.actor_field(a, "@class_id")))
            self.actor_rows[iid] = a
        kids = self.tv_actor.get_children()
        if kids:
            self.tv_actor.selection_set(kids[0])

    def current_actor(self):
        sel = self.tv_actor.selection()
        return self.actor_rows.get(sel[0]) if sel else None

    def load_actor(self):
        a = self.current_actor()
        if a is None or not self.sv:
            return
        for k, var in self.actor_vars.items():
            if k == "@exp":
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
        L = ["名字：%s（存档 @name）" % self.sv.actor_name(a),
             "等级 / 经验 / 升级所需：%s / %s / %s"
             % (self.sv.actor_field(a, "@level"), self.g.exp(a),
                self.g.limit_exp(a)),
             "防作弊：五维总点数 %d（上限 = 等级*10+500 = %d）"
             % (self.g.point_num(a),
                (self.sv.actor_field(a, "@level") or 0) * 10 + 500),
             "已学技能：%s" % (sk or "（无）"),
             "装备：%s" % (eq or "（无）"),
             "五维/潜能：%s" % "、".join("%s=%s" % (k, v)
                                        for k, v in self.sv.attr_items(a))]
        n = len(self.g.babies(a))
        L.append("携带召唤兽：%d 只（见「召唤兽」页）" % n)
        self.txt_actor.delete("1.0", "end")
        self.txt_actor.insert("1.0", "\n".join(L))

    def apply_actor(self):
        a = self.current_actor()
        if a is None:
            messagebox.showinfo("提示", "先在上面选一个角色。", parent=self.root)
            return
        try:
            for k, var in self.actor_vars.items():
                raw = var.get().strip()
                if raw == "":
                    continue
                if k == "@exp":
                    self.g.set_exp(a, int(raw, 0))
                else:
                    self.sv.set_actor_field(a, k, raw)
            for k, var in self.attr_vars.items():
                raw = var.get().strip()
                if raw == "":
                    continue
                self.sv.set_attr(a, k, int(raw, 0))
        except Exception as e:
            messagebox.showerror("修改失败", human(str(e)), parent=self.root)
            return
        self.doc.dirty = True
        self.mark_dirty()
        self.fill_actors()
        self.load_actor()
        self.set_status("角色已改（记得点「保存修改」）")

    def actor_preset(self, what):
        a = self.current_actor()
        if a is None or not self.sv:
            return
        try:
            if what == "maxlv":
                self.sv.set_actor_field(a, "@level", xj_game.MAX_LEVEL_ACTOR)
            elif what == "exp":
                self.g.add_exp(a, 10000)
            elif what == "heal":
                for k, v in (("@hp", 9999), ("@mp", 9999), ("@tp", 100)):
                    if self.sv.actor_field(a, k) is not None:
                        self.sv.set_actor_field(a, k, v)
            elif what == "attr":
                for k, v in self.sv.attr_items(a):
                    if isinstance(v, int):
                        self.sv.set_attr(a, k, v + 10)
        except Exception as e:
            messagebox.showerror("修改失败", human(str(e)), parent=self.root)
            return
        self.doc.dirty = True
        self.mark_dirty()
        self.fill_actors()
        self.load_actor()

    # ================================================== 4 队伍 / 物品
    def fill_party(self):
        """刷背包页（当前页 20 格 + 物品计数校验状态）。"""
        self.tv_pack.delete(*self.tv_pack.get_children())
        if not self.sv or self.g is None:
            return
        page = self.var_bag_page.get()
        kind = self.var_bag_kind.get()
        self.var_party.set("存银 = %s　步数 = %s　出战成员 = %s　"
                           "仓库页号 = %s"
                           % (self.sv.gold(), self.sv.steps(),
                              self.sv.party_member_ids(),
                              self.g.warehouse_page()))
        rows = dict((r[0], r) for r in self.g.bag(kind, page))
        for i in range(xj_game.PACK_PAGE_SIZE):
            slot = self.g.slot_key(page, i)
            r = rows.get(slot)
            if r:
                try:
                    cnt_txt = self.g.payload_summary(
                        self.g._item_node(kind, slot))
                except Exception:
                    cnt_txt = ""
                self.tv_pack.insert("", "end", iid="s%d" % slot,
                                    values=(slot, i, r[3], r[4], r[5], cnt_txt))
            else:
                self.tv_pack.insert("", "end", iid="s%d" % slot,
                                    values=(slot, i, "（空）", "", "", ""))
        bad = [r for r in self.g.security_rows() if r[2] != r[3]]
        try:
            self.bag_bad = self.g.pack_report(kinds=(kind,))
        except Exception:
            self.bag_bad = []
        note = ("物品计数校验（游戏自己的 `$game_system.security`）：%d 条记录%s"
                % (len(self.g.security_rows()),
                   "，有 %d 条和背包对不上（点「同步计数校验」）" % len(bad)
                   if bad else "，全部对得上 ✓"))
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
        for iid, nm, _desc in rows:
            self.tv_tpl.insert("", "end", iid="t%d" % iid, values=(iid, nm))
        self.var_tpl_note.set("共 %d 个%s" % (len(rows), "（已过滤）" if kw else ""))

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

    def _bag_slot(self, quiet=False):
        sel = self.tv_pack.selection()
        if not sel:
            if not quiet:
                messagebox.showinfo("提示", "先在左边点一个格子。", parent=self.root)
            return None
        return int(sel[0][1:])

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
        if into_selected:
            slot = self._bag_slot()
            if slot is None:
                return
        else:
            page = self.var_bag_page.get()
            used = set(r[0] for r in self.g.bag(kind, page))
            free = [self.g.slot_key(page, i)
                    for i in range(xj_game.PACK_PAGE_SIZE)
                    if self.g.slot_key(page, i) not in used]
            if not free:
                messagebox.showinfo("提示", "这一页没空格了，先清一个。",
                                    parent=self.root)
                return
            slot = free[0]
        try:
            self.g.set_item(kind, slot, iid, n, kid=self._bag_kid())
        except Exception as e:
            messagebox.showerror("写入失败", human(str(e)), parent=self.root)
            return
        self.mark_dirty()
        self.fill_party()
        self.tv_pack.selection_set("s%d" % slot)
        self.set_status("槽 %d 已换成 id=%d ×%d（计数校验已同步；保存时会整档重写）"
                        % (slot, iid, n))

    def bag_reroll(self):
        """给选中的格子重抽/指定“运行时内容”（孵化蛋孵出哪只、要诀开出什么技能）。"""
        slot = self._bag_slot()
        if slot is None:
            return
        kind = self._bag_kind()
        kid = self._bag_kid()
        try:
            t, d = self.g.set_payload(kind, slot, kid=kid, force=True)
        except Exception as e:
            messagebox.showerror("重抽内容", zh_error(e), parent=self.root)
            return
        self.mark_dirty()
        self.fill_party()
        self.tv_pack.selection_set("s%d" % slot)
        it = self.g._item_node(kind, slot)
        self.set_status("槽 %d 的内容已重新生成：%s"
                        % (slot, self.g.payload_summary(it)))

    def bag_all(self, count=99):
        """把本页已有格子的数量批量设成 count。"""
        slot = self._bag_slot(quiet=True)
        page = (slot // xj_game.PACK_PAGE_SIZE if slot is not None
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
        cn = dict((k[0], k[2]) for k in xj_game.KINDS)
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
        now, err, _ids, _ok = self.g.machine_status()
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
        now, err, ids, ok = self.g.machine_status()
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
        exist = dict((r[0], r) for r in self.g.bag(kind, slot // xj_game.PACK_PAGE_SIZE))
        if slot in exist:
            self.bag_set_count()
        else:
            self.bag_add()

    def bag_set_count(self):
        slot = self._bag_sel()
        if slot is None:
            return
        try:
            n = int(self.var_bag_cnt.get() or "0", 0)
        except ValueError:
            messagebox.showinfo("提示", "数量要填整数。", parent=self.root)
            return
        try:
            got = self.g.set_count(self._bag_kind(), slot, n)
        except Exception as e:
            messagebox.showerror("改数量失败", human(str(e)), parent=self.root)
            return
        self.mark_dirty()
        self.fill_party()
        self.set_status("槽 %d 数量 = %d（物品计数校验已同步）" % (slot, got))

    def bag_clear(self):
        slot = self._bag_sel()
        if slot is None:
            return
        try:
            if self.g.clear_slot(self._bag_kind(), slot):
                self.mark_dirty()
                self.fill_party()
                self.set_status("已清空槽 %d（计数校验已同步）" % slot)
        except Exception as e:
            messagebox.showerror("清空失败", human(str(e)), parent=self.root)

    def bag_add(self):
        slot = self._bag_sel()
        if slot is None:
            return
        kind = self._bag_kind()
        try:
            iid = int(self.var_bag_id.get() or "0", 0)
            n = int(self.var_bag_cnt.get() or "1", 0)
        except ValueError:
            messagebox.showinfo("提示", "物品 id / 数量要填整数。", parent=self.root)
            return
        db_key = dict((k[0], k[3]) for k in xj_game.KINDS)[kind]
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
        try:
            self.g.add_item(kind, slot, iid, n, kid=self._bag_kid())
        except Exception as e:
            messagebox.showerror("添加失败", human(str(e)), parent=self.root)
            return
        self.mark_dirty()
        self.fill_party()
        self.set_status("已往槽 %d 放入 %s ×%d（结构性改动：保存时会整档重写）"
                        % (slot, name, n))

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
                                      xj_notes.note_of_switch(i)))
        for i in range(nva):
            self.tv_va.insert("", "end", iid="v%d" % i,
                              values=(i, self.sv.get_variable(i),
                                      xj_notes.note_of_variable(i)))

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
        return xj_db.ALL_KEYS[sel[0]] if sel else None

    def db_preview(self):
        key = self.db_selected_key()
        if not key:
            return
        try:
            header, data = xj_db.rows(key)
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
                             % (xj_db.table_label(key), key, len(data),
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
            res = xj_db.export_all(out, keys)
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
    return xj_nodes.value_of(node)


def describe_value(node):
    """节点 → 一句人话（旧名保留，内部改用 xj_nodes）。"""
    return xj_nodes.brief(node, 200)


NOTES = xj_notes.IVAR_NOTES          # 保留旧名字（测试/外部可能引用）


def note_of(node):
    """给数据树加一列"说明"：抽节点类型 / 类名。"""
    return xj_nodes.note_for(None, None, node)


def note_for_ivar(name):
    return xj_notes.note_of_ivar(name)


def short(v, n=80):
    s = human(v)
    s = s.replace("\n", "\\n").replace("\r", "")
    return s if len(s) <= n else s[:n] + "…"


def node_detail(node):
    """右侧"节点详情"：类型 + 值 + 字节区间 + 子项速览（带中文注释）。"""
    node = xj_nodes.deref(node)
    L = ["类型：%s" % xj_nodes.type_label(node),
         "值：%s" % short(xj_nodes.brief(node, 400), 400),
         "字节区间：[%s, %s)" % (getattr(node, "start", "?"),
                                 getattr(node, "end", "?"))]
    if isinstance(node, (M.ObjNode, M.StructNode)):
        n = xj_notes.note_of_class(node.cls)
        if n:
            L.append("这是什么：%s" % n)
        L.append("实例变量：")
        for k, v in node.ivars:
            L.append("  %-24s %-30s %s" % (k, short(xj_nodes.brief(v, 40), 36),
                                           xj_notes.note_of_ivar(k)))
    elif isinstance(node, M.HashNode):
        L.append("前 20 对：")
        for k, v in node.pairs[:20]:
            L.append("  %-24s %-30s %s"
                     % (short(xj_nodes.key_label(k), 22),
                        short(xj_nodes.brief(v, 60), 60),
                        xj_nodes.note_for(node, k, v)))
    elif isinstance(node, M.ArrayNode):
        L.append("前 20 项：")
        for i, v in enumerate(node.items[:20]):
            L.append("  [%-3d] %-30s %s" % (i, short(xj_nodes.brief(v, 60), 60),
                                             xj_nodes.note_for(node, i, v)))
    elif isinstance(node, M.UserDefNode):
        L.append("自定义序列化：%s，%d 字节" % (node.cls, len(node.data)))
    return "\n".join(L)


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
        ent.focus_set()
        bar = ttk.Frame(self)
        bar.grid(row=2, column=0, columnspan=2, pady=8)
        ttk.Button(bar, text="确定", command=self.ok).pack(side="left", padx=6)
        ttk.Button(bar, text="取消", command=self.destroy).pack(side="left", padx=6)
        self.bind("<Return>", lambda e: self.ok())
        self.bind("<Escape>", lambda e: self.destroy())

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
    except xj_codec.CodecError as e:
        messagebox.showerror("缺少依赖", str(e))
        return 2
    except Exception:
        return _fatal(traceback.format_exc())

    if selftest:
        root.update()
        lines = selftest_lines(app)
        out = os.path.join(xj_codec.app_dir(), "selftest_result.txt")
        try:
            open(out, "w", encoding="utf-8").write("\n".join(lines))
        except OSError:
            pass
        try:
            print("\n".join(lines))
        except Exception:
            pass
        root.destroy()
        return 0 if lines[-1].startswith("结果: OK") else 1
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
    p = xj_env.save_path()
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
         "程序目录: %s" % xj_codec.app_dir(),
         "打包运行(frozen): %s" % bool(getattr(sys, "frozen", False)),
         "Python: %s" % sys.version.split()[0]]
    host = xj_codec.find_host()
    L.append("32 位宿主: %s" % (host or "未找到（改不了存档！）"))
    game = xj_env.find_game_dir()
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
        L.append("存银 = %s" % sv.gold())
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
        # 在内存里试一次结构性重写（不写盘）
        try:
            import xj_marshal as _M
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


def _fatal(text):
    try:
        open(os.path.join(xj_codec.app_dir(), "error.log"), "w",
             encoding="utf-8").write(text)
    except OSError:
        pass
    try:
        messagebox.showerror("程序异常", text[-1200:])
    except Exception:
        pass
    return 3


if __name__ == "__main__":
    sys.exit(main())
