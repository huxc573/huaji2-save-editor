# -*- coding: utf-8 -*-
"""《画迹2：缘起凡尘》存档工具 v0.3 —— tkinter 界面（界面参照画迹1 的编辑器）。

页签（顺序与画迹1 对齐）：
  1. 概览 / 快捷修改      存档概况 + 金钱/步数/次数 + 防作弊校验一键修复
  2. 全部解析数据         全局搜索 + 树形浏览（懒加载）+ 右侧详情 + 右键菜单
  3. 角色 / 属性          等级/HP/MP/名字 + 中文五维（Game_Actor_Attr）+ 技能装备
  4. 队伍 / 物品          金钱/步数/成员 + 物品（名字取自 Data\\Items.rvdata2）
  5. 开关 / 变量          双击切换 / 修改
  6. 数据表 (CSV)         Data\\*.rvdata2 → CSV（物品/武器/防具/技能/状态/角色/职业/敌人）
  7. 说明 / 机制          密钥、存档结构、防作弊、数据表说明
  8. 更新日志             CHANGELOG.md

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

import tkinter as tk                              # noqa: E402
from tkinter import filedialog, messagebox, ttk  # noqa: E402

import xj_codec   # noqa: E402
import xj_db      # noqa: E402
import xj_env     # noqa: E402
import xj_marshal as M  # noqa: E402
import xj_model   # noqa: E402
import xj_save    # noqa: E402

APP_NAME = "画迹2 存档工具"
VERSION = "v0.3"
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


CHANGELOG = _read_text(os.path.join(os.path.dirname(HERE), "CHANGELOG.md"))

# 注意：正文里有 `%`（浮动:20%）和 `@`，所以**只有表头**参与 %-格式化，
# 正文原样拼接 —— 否则会报 "not enough arguments for format string"。
HELP_HEAD = """%s %s
================================================================
 作者 @%s　·　开源地址 %s　·　协议 %s
================================================================

""" % (APP_NAME, VERSION, AUTHOR, HOMEPAGE, LICENSE_NAME)

HELP_BODY = """零、本工具是画迹1 存档编辑器的迭代产品
  界面、快捷键、右键菜单、"导出报告/导出明文"都沿用**画迹1 编辑器**的习惯，
  用过的直接上手；新增了「数据表 (CSV)」页（把 Data\\*.rvdata2 转成 CSV 查表）。

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

四、防作弊（重要）
  金钱等关键数值被 Lock 包着：
      @master = @value * 91 + 45 + seed / 800    （seed = $game_system.seeds[:shield]）
  游戏读的时候会验算，不一致就 msgbox '游戏异常！' 然后 exit。
  本工具改金钱时自动重算 @master；「检查并修复防作弊校验」可扫描全档一次修好。

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
  :party    @gold 金钱（Lock） @actors 出战成员 @items 物品 @steps 步数
  :actors   @data[角色id] → @name @level @hp @mp @attr(中文五维) @skills
  :switches @data[编号]      :variables @data[编号]
"""

HELP_TEXT = HELP_HEAD + HELP_BODY


def human(text):
    if isinstance(text, bytes):
        try:
            return text.decode("utf-8")
        except UnicodeDecodeError:
            return text.decode("gbk", "replace")
    return str(text)


class App(object):
    def __init__(self, root, save_path=None):
        self.tk = tk
        self.ttk = ttk
        self.root = root
        # Tk 回调里未捕获的异常默认只往 stderr 打一行；打包成 exe 后就变成"点了没反应"
        root.report_callback_exception = self._tk_exception

        self.doc = None            # xj_model.Doc
        self.sv = None             # xj_save.SaveDoc（不是本作存档时为 None）
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
        self._tab_tree()
        self._tab_actor()
        self._tab_party()
        self._tab_switch()
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
        rows = [("金钱", self.var_gold, "Lock 包装：改值会同步重算 @master 校验和"),
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
        base = [("@name", "名字"), ("@level", "等级"), ("@hp", "HP"), ("@mp", "MP"),
                ("@tp", "TP"), ("@limit_exp", "升级所需经验")]
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
        ttk.Button(bar, text="满级(99)",
                   command=lambda: self.actor_preset("maxlv")).pack(side="left", padx=6)
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
        self.nb.add(f, text="队伍 / 物品")

        self.var_party = tk.StringVar()
        ttk.Label(f, textvariable=self.var_party, font=("Microsoft YaHei UI", 10)
                  ).pack(anchor="w", pady=(0, 6))

        ttk.Label(f, text="队伍物品（名字取自 Data\\Items.rvdata2）").pack(anchor="w")
        cols = ("id", "name", "count")
        self.tv_pack = ttk.Treeview(f, columns=cols, show="headings", height=14)
        for c, w, t in (("id", 70, "物品ID"), ("name", 320, "名称"),
                        ("count", 90, "数量")):
            self.tv_pack.heading(c, text=t)
            self.tv_pack.column(c, width=w, anchor="w")
        vs = ttk.Scrollbar(f, orient="vertical", command=self.tv_pack.yview)
        self.tv_pack.configure(yscrollcommand=vs.set)
        vs.pack(side="right", fill="y")
        self.tv_pack.pack(fill="both", expand=True)
        ttk.Button(f, text="刷新", command=self.fill_party).pack(anchor="w", pady=4)
        ttk.Label(f, text="提示：改数量请到「全部解析数据」页搜 @items —— "
                          "数值在 [数量, …] 数组的第 1 项",
                  foreground="#777").pack(anchor="w")

    # -------------------------------------------------- 5 开关 / 变量
    def _tab_switch(self):
        tk, ttk = self.tk, self.ttk
        f = ttk.Frame(self.nb, padding=8)
        self.tab_switch = f
        self.nb.add(f, text="开关 / 变量")

        lf = ttk.Frame(f)
        lf.pack(side="left", fill="both", expand=True, padx=(0, 8))
        ttk.Label(lf, text="开关（双击切换）").pack(anchor="w")
        self.tv_sw = ttk.Treeview(lf, columns=("i", "v"), show="headings", height=20)
        self.tv_sw.heading("i", text="编号")
        self.tv_sw.heading("v", text="值")
        self.tv_sw.column("i", width=80, anchor="w")
        self.tv_sw.column("v", width=90, anchor="w")
        self.tv_sw.pack(fill="both", expand=True)
        self.tv_sw.bind("<Double-1>", lambda e: self.sw_toggle())

        rf = ttk.Frame(f)
        rf.pack(side="left", fill="both", expand=True)
        ttk.Label(rf, text="变量（双击修改）").pack(anchor="w")
        self.tv_va = ttk.Treeview(rf, columns=("i", "v"), show="headings", height=20)
        self.tv_va.heading("i", text="编号")
        self.tv_va.heading("v", text="值")
        self.tv_va.column("i", width=80, anchor="w")
        self.tv_va.column("v", width=140, anchor="w")
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
                "出错", "%s: %s\n\n（详细信息已写入 error.log）"
                % (getattr(exc, "__name__", exc), val), parent=self.root)
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
        self.set_status("出错：%s" % e)

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
        try:
            p = self.doc.save()
        except Exception as e:
            messagebox.showerror("保存失败", human(str(e)), parent=self.root)
            return
        try:
            self.sv = xj_save.SaveDoc(doc=self.doc)
        except Exception:
            self.sv = None
        self.clear_dirty()
        self.refresh_panels()
        messagebox.showinfo("保存", "已写回：\n%s\n\n原文件已备份为 %s.bak.<时间>"
                            % (p, os.path.basename(p)), parent=self.root)
        self.set_status("已保存（备份已生成）")

    def refresh_panels(self):
        """把所有面板刷一遍。每步单独兜底，返回出错的步骤名列表。

        存档面板和"全部解析数据"互不依赖，一个炸了不该连坐。
        """
        bad = []
        for step, fn in (("概览", self.fill_info), ("数据树", self.fill_tree),
                         ("角色", self.fill_actors), ("队伍/物品", self.fill_party),
                         ("开关/变量", self.fill_switches),
                         ("环境信息", self.refresh_env)):
            try:
                fn()
            except Exception as e:
                bad.append(step)
                self.err("刷新「%s」失败：%s" % (step, human(str(e))))
        return bad

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
        L += ["", "金钱 = %s　步数 = %s" % (self.sv.gold(), self.sv.steps()),
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

    # ================================================== 2 数据树（懒加载）
    def _kids(self, node):
        node = xj_save._deref(node)
        kids = []
        if isinstance(node, M.HashNode):
            for k, v in node.pairs:
                kids.append(("[%s]" % short(value_of(k), 40), v))
        elif isinstance(node, M.ArrayNode):
            for i, v in enumerate(node.items):
                kids.append(("[%d]" % i, v))
        elif isinstance(node, M.IVarNode):
            if node.inner is not None:
                kids.append(("（内容）", node.inner))
            for name, v in node.ivars:
                kids.append((name, v))
        elif isinstance(node, (M.ObjNode, M.StructNode)):
            for name, v in node.ivars:
                kids.append((name, v))
        return kids

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
        for n, (label, kid) in enumerate(kids[:limit]):
            iid2 = "%s|%d" % (iid, n)
            note = note_for_ivar(label) if label.startswith("@") else note_of(kid)
            self.tree.insert(iid, "end", iid=iid2, text=label,
                             values=(kid.type if hasattr(kid, "type") else "?",
                                     short(describe_value(kid)), note))
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
        txt = str(describe_value(node2))
        if kw in txt.lower() or kw in path.lower():
            out.append((path, getattr(node2, "type", "?"), short(txt, 60), top,
                        path.split("|")[1:]))
        for label, kid in self._kids(node2):
            self._walk_search(kid, top, path + "|" + label, kw, out, budget,
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
            v = self.sv.actor_field(a, k)
            var.set("" if v is None else str(v))
        attrs = dict(self.sv.attr_items(a))
        for k, var in self.attr_vars.items():
            var.set(str(attrs.get(k, "")))
        sk = "、".join("#%d %s" % (i, nm) for i, nm in self.sv.skill_names(a))
        eq = "、".join("槽%d:%s#%s" % (i, "武器" if c == 0 else "防具", i2)
                       for i, c, i2 in self.sv.equips(a))
        L = ["名字：%s（存档 @name）" % self.sv.actor_name(a),
             "已学技能：%s" % (sk or "（无）"),
             "装备：%s" % (eq or "（无）"),
             "五维/潜能：%s" % "、".join("%s=%s" % (k, v)
                                        for k, v in self.sv.attr_items(a))]
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
                self.sv.set_actor_field(a, "@level", 99)
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
        self.tv_pack.delete(*self.tv_pack.get_children())
        if not self.sv:
            return
        self.var_party.set("金钱 = %s　步数 = %s　出战成员 = %s"
                           % (self.sv.gold(), self.sv.steps(),
                              self.sv.party_member_ids()))
        for kid, nm, cnt in self.sv.item_rows():
            self.tv_pack.insert("", "end", values=(kid, nm, cnt))

    # ================================================== 5 开关 / 变量
    def fill_switches(self):
        self.tv_sw.delete(*self.tv_sw.get_children())
        self.tv_va.delete(*self.tv_va.get_children())
        if not self.sv:
            return
        nsw, nva = self.sv.counts()
        for i in range(nsw):
            self.tv_sw.insert("", "end", iid="s%d" % i,
                              values=(i, "开" if self.sv.get_switch(i) else "关"))
        for i in range(nva):
            self.tv_va.insert("", "end", iid="v%d" % i,
                              values=(i, self.sv.get_variable(i)))

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
    node = node.target if isinstance(node, M.LinkNode) and node.target is not None else node
    return getattr(node, "value", None)


def describe_value(node):
    node = node.target if isinstance(node, M.LinkNode) and node.target is not None else node
    if node is None:
        return "nil"
    v = getattr(node, "value", None)
    if v is not None:
        return "是" if v is True else ("否" if v is False else v)
    if isinstance(node, M.StrNode):
        return node.data
    if isinstance(node, M.SymbolNode):
        return ":" + node.name
    if isinstance(node, M.ArrayNode):
        return "<数组 %d 项>" % len(node.items)
    if isinstance(node, M.HashNode):
        return "<哈希 %d 项>" % len(node.pairs)
    if isinstance(node, (M.ObjNode, M.StructNode)):
        return "<%s>（%d 个 @变量）" % (node.cls, len(node.ivars))
    if isinstance(node, M.LinkNode):
        return "-> 对象 #%d" % getattr(node, "index", getattr(node, "idx", -1))
    if isinstance(node, M.IVarNode):
        return "<带 @变量包装>"
    if isinstance(node, (M.ClassNode, M.ModuleNode)):
        return "类/模块 %s" % node.name.decode("utf-8", "replace")
    if isinstance(node, M.UserDefNode):
        return "<自定义 %s %d 字节>" % (node.cls, len(node.data))
    t = getattr(node, "text", None)
    return t() if callable(t) else ""


NOTES = {
    "@gold": "金钱（Lock 包装）", "@level": "等级", "@hp": "HP", "@mp": "MP",
    "@tp": "TP", "@exp": "经验", "@skills": "已学技能 id 数组",
    "@items": "物品 {id => [数量,…]}", "@steps": "步数",
    "@seeds": "防作弊种子表", "@attr": "中文五维/潜能",
    "@switch_id": "开关ID", "@switch": "开关", "@variable": "变量",
    "@name": "名字", "@description": "说明", "@note": "备注",
    "@price": "价格", "@effects": "效果", "@damage": "伤害",
    "@features": "特性", "@equips": "装备", "@class_id": "职业ID",
    "@members": "成员", "@save_count": "存档次数", "@battle_count": "战斗次数",
    "@master": "校验和（防作弊）", "@value": "值", "@data": "数据数组",
    "@actors": "出战成员 id", "@baby": "召唤兽", "@babys": "召唤兽列表",
    "@limit_exp": "升级所需经验", "@sect_data": "门派数据",
}


def note_of(node):
    """给数据树加一列"说明"：把常见字段翻成人话。"""
    n = node.target if isinstance(node, M.LinkNode) and node.target is not None else node
    if isinstance(n, M.ObjNode):
        return n.cls
    if isinstance(n, M.HashNode):
        return "哈希"
    if isinstance(n, M.ArrayNode):
        return "数组"
    return ""


def note_for_ivar(name):
    return NOTES.get(name, "")


def short(v, n=80):
    s = human(v)
    s = s.replace("\n", "\\n").replace("\r", "")
    return s if len(s) <= n else s[:n] + "…"


def node_detail(node):
    node = node.target if isinstance(node, M.LinkNode) and node.target is not None else node
    L = ["类型：%s" % type(node).__name__,
         "值：%s" % short(describe_value(node), 400),
         "字节区间：[%s, %s)" % (getattr(node, "start", "?"),
                                 getattr(node, "end", "?"))]
    if isinstance(node, (M.ObjNode, M.StructNode)):
        L.append("类：%s" % node.cls)
        L.append("实例变量：")
        for k, v in node.ivars:
            L.append("  %-24s %-28s %s" % (k, short(describe_value(v), 36),
                                           note_for_ivar(k)))
    elif isinstance(node, M.HashNode):
        L.append("前 20 对：")
        for k, v in node.pairs[:20]:
            L.append("  %-24s %s" % (short(value_of(k), 22),
                                     short(describe_value(v), 60)))
    elif isinstance(node, M.ArrayNode):
        L.append("前 20 项：")
        for i, v in enumerate(node.items[:20]):
            L.append("  [%-3d] %s" % (i, short(describe_value(v), 60)))
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
    root = tk.Tk()
    app = App(root, save)
    if "--selftest" in sys.argv:
        root.update()
        print("selftest ok: doc=%s sv=%s" % (app.doc is not None, app.sv is not None))
        root.destroy()
        return 0
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
