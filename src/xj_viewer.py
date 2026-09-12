# -*- coding: utf-8 -*-
"""《画迹2：缘起凡尘》存档工具 v0.2 —— tkinter 界面。

页签：
  * 概览        存档概况 + 加解密自检 + 环境信息
  * 快捷修改    金钱 / 角色属性 / 开关 / 变量 / 防作弊校验一键修复
  * 数据树      全部顶层对象树形浏览（字段 / 类型 / 值），右键改标量
  * 说明        格式、密钥与防作弊机制说明

启动： python src/xj_viewer.py
"""
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import tkinter as tk                          # noqa: E402
from tkinter import filedialog, messagebox, ttk  # noqa: E402

import xj_codec  # noqa: E402
import xj_edit  # noqa: E402
import xj_env  # noqa: E402
import xj_marshal as M  # noqa: E402
import xj_model  # noqa: E402
import xj_save  # noqa: E402

APP = "画迹2 存档工具 v0.2"
LAST_TXT = os.path.join(os.path.expanduser("~"), ".huaji2_save_editor_last.txt")


def human(text):
    if isinstance(text, bytes):
        return text.decode("utf-8", "replace")
    return str(text)


class App(tk.Tk):
    def __init__(self):
        tk.Tk.__init__(self)
        self.title(APP)
        self.geometry("1080x680")
        self.doc = None
        self.nodes = {}                     # tree item id -> node
        self.sv = None                      # xj_save.SaveDoc（快捷面板用）

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)
        self.tab_over = ttk.Frame(nb)
        self.tab_quick = ttk.Frame(nb)
        self.tab_tree = ttk.Frame(nb)
        self.tab_help = ttk.Frame(nb)
        nb.add(self.tab_over, text="概览")
        nb.add(self.tab_quick, text="快捷修改")
        nb.add(self.tab_tree, text="数据树")
        nb.add(self.tab_help, text="说明 / 机制")

        self._build_over()
        self._build_quick()
        self._build_tree()
        self._build_help()

        self.after(200, self.try_autoload)

    # ------------------------------------------------------------- 概览页
    def _build_over(self):
        bar = ttk.Frame(self.tab_over)
        bar.pack(fill="x", padx=8, pady=6)
        ttk.Button(bar, text="打开存档…", command=self.open_save).pack(side="left")
        ttk.Button(bar, text="打开文件…", command=self.open_any).pack(side="left", padx=4)
        ttk.Button(bar, text="保存 (Ctrl+S)", command=self.save).pack(side="left", padx=4)
        ttk.Button(bar, text="加解密自检", command=self.selftest).pack(side="left", padx=4)
        ttk.Button(bar, text="环境信息", command=self.show_env).pack(side="left", padx=4)

        self.txt_over = tk.Text(self.tab_over, wrap="none", height=30,
                                font=("Consolas", 10))
        self.txt_over.pack(fill="both", expand=True, padx=8, pady=6)
        self.bind_all("<Control-s>", lambda e: self.save())
        self.show_env()

    # ------------------------------------------------------------- 快捷修改页
    def _build_quick(self):
        f = self.tab_quick

        # 金钱
        box = ttk.LabelFrame(f, text="金钱（Lock 包装，改值会同步修校验）")
        box.pack(fill="x", padx=8, pady=6)
        ttk.Label(box, text="当前：").grid(row=0, column=0, padx=6, pady=4)
        self.lbl_gold = ttk.Label(box, text="-", width=18)
        self.lbl_gold.grid(row=0, column=1, sticky="w")
        ttk.Label(box, text="改为：").grid(row=0, column=2, padx=6)
        self.var_gold = tk.StringVar()
        ttk.Entry(box, textvariable=self.var_gold, width=14).grid(row=0, column=3)
        ttk.Button(box, text="应用", command=self.apply_gold).grid(
            row=0, column=4, padx=6)
        self.lbl_lock = ttk.Label(box, text="")
        self.lbl_lock.grid(row=0, column=5, padx=6)

        # 角色
        box2 = ttk.LabelFrame(f, text="角色（选中后填新值再应用）")
        box2.pack(fill="both", expand=True, padx=8, pady=6)
        left = ttk.Frame(box2)
        left.pack(side="left", fill="both", expand=True)
        self.lst_actors = tk.Listbox(left, height=8)
        self.lst_actors.pack(fill="both", expand=True, padx=6, pady=4)
        self.lst_actors.bind("<<ListboxSelect>>", lambda e: self.sync_actor_fields())
        right = ttk.Frame(box2)
        right.pack(side="left", fill="y", padx=6)
        self.actor_vars = {}
        for i, (field, label) in enumerate([("@level", "等级"), ("@hp", "HP"),
                                            ("@mp", "MP"), ("@name", "名字")]):
            ttk.Label(right, text=label).grid(row=i, column=0, sticky="e", padx=4, pady=2)
            v = tk.StringVar()
            ttk.Entry(right, textvariable=v, width=18).grid(row=i, column=1, pady=2)
            self.actor_vars[field] = v
        ttk.Button(right, text="应用", command=self.apply_actor).grid(
            row=len(self.actor_vars), column=1, pady=6)

        # 开关 / 变量
        box3 = ttk.LabelFrame(f, text="开关 / 变量（编号从 0 开始）")
        box3.pack(fill="x", padx=8, pady=6)
        ttk.Label(box3, text="编号").grid(row=0, column=0, padx=4)
        self.var_idx = tk.StringVar(value="0")
        ttk.Entry(box3, textvariable=self.var_idx, width=8).grid(row=0, column=1)
        ttk.Label(box3, text="值").grid(row=0, column=2, padx=4)
        self.var_val = tk.StringVar()
        ttk.Entry(box3, textvariable=self.var_val, width=12).grid(row=0, column=3)
        ttk.Button(box3, text="设开关", command=lambda: self.apply_sw(True)).grid(
            row=0, column=4, padx=6)
        ttk.Button(box3, text="设变量", command=lambda: self.apply_sw(False)).grid(
            row=0, column=5, padx=6)

        # 防作弊 / 保存
        bar = ttk.Frame(f)
        bar.pack(fill="x", padx=8, pady=8)
        ttk.Button(bar, text="检查并修复防作弊校验", command=self.fix_locks).pack(side="left")
        ttk.Button(bar, text="保存 (Ctrl+S)", command=self.save).pack(side="left", padx=8)
        ttk.Button(bar, text="重新加载", command=lambda: self.load(self.doc.path if self.doc else None, quiet=True)).pack(side="left")

    # ------------------------------------------------------------- 快捷操作
    def refresh_quick(self):
        """刷新快捷面板。任何解析不了的文件（比如普通数据文件）都只是"不显示"。"""
        self.sv = None
        try:
            self.lst_actors.delete(0, "end")
        except Exception:
            pass
        try:
            self.lbl_gold.configure(text="-")
            self.lbl_lock.configure(text="")
        except Exception:
            return
        if not self.doc:
            return
        try:
            self.sv = xj_save.SaveDoc(self.doc.path)
            g = self.sv.gold()
            self.lbl_gold.configure(text=str(g))
            bad = self.sv.check_locks()
            self.lbl_lock.configure(
                text="防作弊校验：正常" if not bad
                else "防作弊校验：不一致 %d 处（可一键修复）" % len(bad))
            for aid, a in self.sv.actors():
                self.lst_actors.insert("end", "#%d %s" % (aid, self.sv.actor_summary(a)))
        except Exception as e:
            self.sv = None
            self.lbl_lock.configure(text="（此文件不是本作存档：%s）" % human(str(e))[:40])

    def _picked_actor(self):
        if not self.sv:
            return None
        sel = self.lst_actors.curselection()
        if not sel:
            return None
        return self.sv.actors()[sel[0]][1]

    def sync_actor_fields(self):
        a = self._picked_actor()
        if a is None:
            return
        for field, var in self.actor_vars.items():
            var.set(str(self.sv.actor_field(a, field)))

    def apply_gold(self):
        if not self.sv:
            return
        try:
            self.sv.set_gold(int(self.var_gold.get(), 0))
        except Exception as e:
            messagebox.showerror("修改失败", human(str(e)))
            return
        self.doc.dirty = True
        self.refresh_quick()
        self.log_over("\n".join(self.sv.summary_lines()))

    def apply_actor(self):
        a = self._picked_actor()
        if a is None:
            messagebox.showinfo("提示", "先在左边选一个角色。")
            return
        for field, var in self.actor_vars.items():
            raw = var.get().strip()
            if not raw:
                continue
            try:
                self.sv.set_actor_field(a, field, raw)
            except Exception as e:
                messagebox.showerror("修改失败", human(str(e)))
                return
        self.doc.dirty = True
        self.refresh_quick()

    def apply_sw(self, is_switch):
        if not self.sv:
            return
        try:
            idx = int(self.var_idx.get(), 0)
            if is_switch:
                v = self.var_val.get().strip().lower() in ("1", "true", "t", "y", "yes", "开")
                self.sv.set_switch(idx, v)
            else:
                self.sv.set_variable(idx, int(self.var_val.get(), 0))
        except Exception as e:
            messagebox.showerror("修改失败", human(str(e)))
            return
        self.doc.dirty = True
        self.refresh_quick()

    def fix_locks(self):
        if not self.sv:
            return
        bad = self.sv.check_locks()
        n = self.sv.repair_locks()
        if n:
            self.doc.dirty = True
        self.refresh_quick()
        messagebox.showinfo("防作弊校验",
                            "检查到不一致 %d 处，已修复 %d 处。\n（记得按 Ctrl+S 保存）"
                            % (len(bad), n))

    # ------------------------------------------------------------- 数据树页
    def _build_tree(self):
        top = ttk.Frame(self.tab_tree)
        top.pack(fill="x", padx=8, pady=4)
        ttk.Label(top, text="搜索:").pack(side="left")
        self.var_q = tk.StringVar()
        e = ttk.Entry(top, textvariable=self.var_q, width=28)
        e.pack(side="left", padx=4)
        ttk.Button(top, text="查找", command=self.search).pack(side="left")
        ttk.Button(top, text="改选中项…", command=self.edit_selected).pack(
            side="left", padx=8)
        ttk.Button(top, text="展开/折叠", command=self.toggle_all).pack(side="left")

        self.tree = ttk.Treeview(self.tab_tree, columns=("type", "value"),
                                 show="tree headings")
        self.tree.heading("#0", text="路径 / 字段")
        self.tree.heading("type", text="类型")
        self.tree.heading("value", text="值")
        self.tree.column("#0", width=420)
        self.tree.column("type", width=110)
        self.tree.column("value", width=460)
        self.tree.pack(fill="both", expand=True, padx=8, pady=4)
        self.tree.bind("<Double-1>", lambda e: self.edit_selected())

    # ------------------------------------------------------------- 说明页
    def _build_help(self):
        txt = tk.Text(self.tab_help, wrap="word", font=("Microsoft YaHei", 10))
        txt.pack(fill="both", expand=True, padx=8, pady=6)
        txt.insert("1.0", HELP_TEXT)
        txt.configure(state="disabled")

    # ------------------------------------------------------------- 加载
    def try_autoload(self):
        p = None
        if os.path.exists(LAST_TXT):
            p = open(LAST_TXT, encoding="utf-8").read().strip()
        if not p or not os.path.exists(p):
            p = xj_env.save_path()
        if p and os.path.exists(p):
            self.load(p, quiet=True)

    def open_save(self):
        p = xj_env.save_path()
        p = filedialog.askopenfilename(
            title="选择存档", initialdir=os.path.dirname(p or ""),
            filetypes=[("RPG Maker 存档", "*.rvdata2 *.rxdata *.bin"),
                       ("全部文件", "*.*")])
        if p:
            self.load(p)

    def open_any(self):
        p = filedialog.askopenfilename(title="选择文件",
                                       filetypes=[("全部文件", "*.*")])
        if p:
            self.load(p)

    def load(self, path, quiet=False):
        try:
            self.doc = xj_model.Doc(path)
        except Exception as e:
            self.doc = None
            msg = "%s\n\n%s" % (e, traceback.format_exc(limit=2))
            if not quiet:
                self.log_over("打开失败：\n" + msg)
                messagebox.showerror("打开失败", human(str(e)))
            return
        try:
            open(LAST_TXT, "w", encoding="utf-8").write(path)
        except OSError:
            pass
        self.log_over(self.doc.summary())
        self.fill_tree()
        self.refresh_quick()

    # ------------------------------------------------------------- 树
    def fill_tree(self):
        self.tree.delete(*self.tree.get_children())
        self.nodes.clear()
        if not self.doc:
            return
        for i, node in enumerate(self.doc.top_level()):
            label = "#%d %s" % (i, xj_model.describe(node))
            self.tree.insert("", "end", iid="r%d" % i, text=label,
                             values=("", ""), open=(i == 0))
            self.nodes["r%d" % i] = node
            self._fill(node, "r%d" % i, 0)

    def _fill(self, node, parent, depth):
        if depth > 4:
            return
        node = node.target if isinstance(node, M.LinkNode) and node.target is not None else node
        kids = []
        if isinstance(node, M.HashNode):
            for k, v in node.pairs:
                kids.append(("[%s]" % short(value_of(k)), v))
        elif isinstance(node, M.ArrayNode):
            for i, v in enumerate(node.items):
                kids.append(("[%d]" % i, v))
        elif isinstance(node, M.ObjNode):
            for name, v in node.ivars:
                kids.append((name, v))
        elif isinstance(node, M.StructNode):
            for name, v in node.ivars:
                kids.append((name, v))
        for label, kid in kids:
            iid = "%s_%d" % (parent, len(self.tree.get_children(parent)))
            self.tree.insert(parent, "end", iid=iid, text=label,
                             values=(kid.type if hasattr(kid, 'type') else '?',
                                     short(describe_value(kid))))
            self.nodes[iid] = kid
            self._fill(kid, iid, depth + 1)

    def toggle_all(self):
        def walk(iid, open_):
            for c in self.tree.get_children(iid):
                self.tree.item(c, open=open_)
                walk(c, open_)
        for r in self.tree.get_children(""):
            self.tree.item(r, open=True)
            walk(r, True)

    def search(self):
        q = self.var_q.get().strip().lower()
        if not q:
            return
        for iid, node in self.nodes.items():
            text = "%s %s" % (self.tree.item(iid, "text"),
                              describe_value(node))
            if q in text.lower():
                self.tree.see(iid)
                self.tree.selection_set(iid)
                return
        messagebox.showinfo("查找", "没找到：%s" % q)

    def edit_selected(self):
        sel = self.tree.selection()
        if not sel or not self.doc:
            return
        node = self.nodes.get(sel[0])
        if node is None:
            return
        node = node.target if isinstance(node, M.LinkNode) else node
        cur = value_of(node)
        if isinstance(cur, (list, tuple)):
            messagebox.showinfo("提示", "这是容器节点，请选它的子项。")
            return
        dlg = EditDialog(self, cur, node.type)
        self.wait_window(dlg)
        if dlg.result is None:
            return
        try:
            self.doc.set_value(node, dlg.result)
        except Exception as e:
            messagebox.showerror("修改失败", human(str(e)))
            return
        self.tree.set(sel[0], "value", short(describe_value(node)))
        self.log_over(self.doc.summary())

    # ------------------------------------------------------------- 动作
    def save(self):
        if not self.doc or not self.doc.dirty:
            messagebox.showinfo("保存", "没有改动。")
            return
        try:
            p = self.doc.save()
        except Exception as e:
            messagebox.showerror("保存失败", human(str(e)))
            return
        messagebox.showinfo("保存", "已写回：\n%s\n（原文件已自动备份为 .bak.<时间>）" % p)
        self.log_over(self.doc.summary())

    def selftest(self):
        try:
            ok, info, lines = xj_codec.selftest()
        except Exception as e:
            self.log_over("自检失败：%s" % human(str(e)))
            return
        self.log_over("加解密自检：%s\n%s" % ("通过" if ok else "失败",
                                          "\n".join(lines)))

    def show_env(self):
        g = xj_env.find_game_dir()
        self.log_over("\n".join([
            "游戏目录 : %s" % g,
            "main.dll : %s" % xj_env.main_dll(g),
            "默认存档 : %s" % xj_env.save_path(g),
            "自动存档 : %s" % xj_env.autosave_dir(g),
            "Python   : %s (%d bit)" % (sys.executable,
                                        64 if sys.maxsize > 2 ** 32 else 32),
            "宿主     : %s" % (xj_codec.HOST if os.path.exists(xj_codec.HOST) else "缺失！"),
        ]))

    def log_over(self, text):
        """概览页永远带上环境尾巴，方便一眼确认"现在改的是哪个游戏/哪个文件"。"""
        tail = ("\n\n" + "-" * 60 + "\n"
                "游戏目录 : %s\n" % xj_env.find_game_dir())
        if self.doc:
            tail += "当前文件 : %s%s\n" % (self.doc.path,
                                        "（有未保存改动）" if self.doc.dirty else "")
        self.txt_over.delete("1.0", "end")
        self.txt_over.insert("1.0", human(text) + tail)


class EditDialog(tk.Toplevel):
    def __init__(self, master, cur, ntype):
        tk.Toplevel.__init__(self, master)
        self.title("修改字段")
        self.result = None
        self.ntype = ntype
        ttk.Label(self, text="当前值：").grid(row=0, column=0, sticky="w", padx=8, pady=6)
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

    def ok(self):
        raw = self.var.get()
        try:
            if self.ntype in ('i', 'l'):
                self.result = int(raw, 0)
            elif self.ntype == 'f':
                self.result = float(raw)
            else:
                self.result = raw
        except ValueError:
            messagebox.showerror("输入有误", "这个字段需要数字。")
            return
        self.destroy()


def value_of(node):
    node = node.target if isinstance(node, M.LinkNode) and node.target is not None else node
    return getattr(node, 'value', None)


def describe_value(node):
    node = node.target if isinstance(node, M.LinkNode) and node.target is not None else node
    v = getattr(node, 'value', None)
    if v is not None:
        return v
    if isinstance(node, M.StrNode):
        return node.data
    if isinstance(node, M.SymbolNode):
        return ":" + node.name
    if isinstance(node, M.ArrayNode):
        return "<数组 %d 项>" % len(node.items)
    if isinstance(node, M.HashNode):
        return "<哈希 %d 项>" % len(node.pairs)
    if isinstance(node, M.ObjNode):
        return "<%s>" % node.cls
    if isinstance(node, M.LinkNode):
        return "-> 对象 #%d" % node.idx
    return getattr(node, 'text', lambda: '')() if callable(getattr(node, 'text', None)) else ''


def short(v, n=80):
    s = human(v)
    s = s.replace("\n", "\\n")
    return s if len(s) <= n else s[:n] + "…"


HELP_TEXT = """《画迹2：缘起凡尘》存档工具 v0.2

【游戏与引擎】
  引擎      RPG Maker VX Ace（RGSS301，Ruby 1.9 语义的 Marshal 4.8）
  存档      <游戏根>\\save.rvdata2
  自动存档  <游戏根>\\AutoSave\\save00..29.rvdata2
  脚本入口  Data\\main.rvdata2（明文，内容只有一句 qqeat 调用）
  加解密    System\\main.dll（MPRESS 加壳的自定义分组密码，8 字节分组 ECB）

【三个密钥（都已逆向出来并实测通过）】
  761205            Data\\*.rvdata2 数据库、System\\Game.md5
  imoutogadaisuki   Data\\Scripts.rvdata2（游戏脚本本体）
  tiyan_version     存档 save.rvdata2 / AutoSave\\*.rvdata2

  密钥不对时 main.dll 不报错，而是**输出 0 字节空文件** —— 本工具就靠这个
  判断命中，并且在猜不出文件名时会自动依次试这三个密钥。

【本工具怎么读文件】
  Python(64 位) --subprocess--> src\\XJCodec32.exe(32 位)
      --LoadLibrary--> System\\main.dll --decryption_file/encryption_file-->
  参数一律用 UTF-8 传给 DLL（DLL 内部做 UTF8→GBK 936 转换）。
  写回：明文 Marshal 重写 → 用同一密钥加密 → 覆盖原文件（自动留
  `*.bak.<时间戳>` 备份）。

【存档结构】
  header   = Marshal.dump({ :temp => nil })
  contents = Marshal.dump({ :system, :timer, :message, :switches, :variables,
                            :self_switches, :actors, :party, :troop, :map, :player })

【防作弊机制（重要）】
  游戏用 Lock 包装金钱等关键数值：

    class Lock
      def initialize(v); @value = v; @master = get_encryption(@value); end
      def seed; $game_system.seeds[:shield]; end
      def get_encryption(v); v * 91 + 45 + seed / 800; end   # Ruby 整除
      def show
        if get_encryption(@value) != @master
          msgbox '游戏异常！'; exit          # ← 直接改数值会踩这里
        end
        @value
      end
    end

  所以改 @value 必须同步重算 @master。本工具：
    * 快捷修改里改金钱会自动重算；
    * 「检查并修复防作弊校验」会扫描整个存档并修好所有 Lock。

【能做什么】
  ✔ 自动选密钥 → 解密 → 解析 → 浏览（概览 / 快捷修改 / 数据树）
  ✔ 改金钱（含防作弊校验）、角色等级/HP/MP/名字、开关、变量
  ✔ 任意标量字段就地改（区间补丁，不动其它字节）
  ✔ 一键检查并修复所有 Lock 校验
  ✔ 自动备份，写回前先自检能否重新解析

【注意】
  * 游戏运行中改存档没用：它只在存/读档时读文件，请先退出游戏再改。
  * 改完最好先进游戏读一次档确认；有问题可以用备份回滚。
"""


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")
    main()
