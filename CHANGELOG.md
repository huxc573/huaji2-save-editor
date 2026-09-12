# 更新日志

## v0.3 — 2026-09-13

**主题：界面照画迹1 重做，外加「Data → CSV」查表功能。**

### 🎨 界面（重写 `src/xj_viewer.py`）

照 `huaji1-save-editor` 的布局重排，8 个页签：

1. **概览 / 快捷修改** —— 金钱 / 步数 / 存档次数 / 战斗次数，一键应用
   + 「检查并修复防作弊校验」，旁边常显校验状态
2. **全部解析数据** —— 左侧懒加载树（3 列：字段 / 值 / 说明），右侧节点详情，
   右键「改值 / 复制 / 复制路径」，顶部**全局搜索**结果可双击跳转
3. **角色 / 属性** —— 角色列表 + 基础字段 + `Game_Actor_Attr` 的**中文五维**
   （体质/法力/力量/耐力/敏捷/潜能/人气/贡献/体力/活力），
   快捷按钮：满级(99) / 回满 HP·MP / 属性全 +10
4. **队伍 / 物品** —— 队伍成员 + 物品栏（名字取自 `Data\Items.rvdata2`）
5. **开关 / 变量** —— 双击切换 / 修改
6. **数据表 (CSV)** —— 10 张 Data 表的预览 + 导出 CSV（本轮新增）
7. **说明 / 机制** —— 密钥、存档结构、防作弊原理、CSV 使用方法
8. **更新日志** —— 直接读 `CHANGELOG.md`

其它：窗口 1220×800、`Ctrl+S` 保存、标题栏 `*` 表示有未保存修改、
作者/开源地址/许可证状态栏、上次打开的存档自动记住
（`~/.huaji2_save_editor_last.txt`）。

### 📊 新增 `src/xj_db.py`：Data\*.rvdata2 → CSV

`Data\*.rvdata2` **全都是加密的**（和存档同一套 main.dll，密钥 `761205`），
现在自动解密 + 解析 + 转 CSV（`utf-8-sig`，Excel 双击直接正常显示中文）：

| 默认导出 | 行数 | 可选导出 | 行数 |
| --- | --- | --- | --- |
| Items 物品 | 300 | Troops 敌人队伍 | 310 |
| Weapons 武器 | 400 | CommonEvents 公共事件 | 100 |
| Armors 防具 | 300 | | |
| Skills 技能 | 320 | | |
| States 状态 | 120 | | |
| Actors 角色 | 300 | | |
| Classes 职业 | 300 | | |
| Enemies 敌人 | 700 | | |

嵌套字段会翻成人话：

* 物品 `@effects` → `HP回复 +500%；解除状态#1 0%`
* 伤害 → `伤害:无 公式:0 浮动:20% 会心:否 属性:0`
* `@features` → `最大HP+50%；状态有效度#1…`
* 敌人 `@params` → `80/0/60/1/15/1/3/1`（列头已按"最大HP/MP/攻/防/魔攻/魔防/敏/运"排好）
* 敌人 `@drop_items` → `物品#1（掉率 1/100）`，没配的空槽不显示
* 职业 `@learnings` → `Lv1→技能#9`
* 使用场合 / 影响范围 / 命中类型 / 类别 / 行动限制 / 触发方式等枚举也翻了中文

命令行：

```bat
python src\xj_db.py                       :: 列出所有表 + 行数
python src\xj_db.py --out csv             :: 默认 8 张表全转
python src\xj_db.py --all --out csv       :: 连 Troops/CommonEvents 一起
python src\xj_db.py Items Skills --out csv
```

> 查"某个物品 id 是什么 / 有什么效果"直接开 `csv\Items_物品.csv` 就够用了，
> 所以 `Map` / `System` / `Scripts` / `Tilesets` / `Animations` 不做转换。

### 🐞 修复

* 数据树改成**懒加载**（每层最多 300 项，展开才生成）：
  之前打开真存档会 materialize 两万多个容器，界面直接卡死（用 `faulthandler`
  抓到栈顶是 `_fill`，现在按需加载 + 模型层搜索 + 路径展开跳转）
* 非本作存档（比如 `Logs\Battle\*\Battle.bt2`）不再假装成功：
  `SaveDoc` 是懒解析的，现在会校验必需分区，不是存档就只留「数据树」页可用
* 载入 / 保存后的**面板刷新逐步兜底**：某一个面板出错不再把数据树一起带下去，
  也不会再弹一个藏在窗口后面的模态框把界面挂住
* 合并进来的一次修复：改角色 `@name` 报 `'StrNode' object has no attribute 'value'`
  （`PatchEngine.set_scalar` 现在按节点类型赋值）

### ✅ 测试（总计 9 组 / 218 项，全绿）

| 测试 | 项数 |
| --- | --- |
| `tests\test_marshal.py` | 27 |
| `tests\test_codec.py` | 15 |
| `tests\test_model.py` | 12 |
| `tests\test_gui.py`（重写：8 页签 + 懒加载 + 表预览） | 23 |
| `tests\test_gui_quick.py`（重写：42 项，含改钱/角色/开关变量/修校验/存盘/CSV） | 42 |
| `tools\test_db_csv.py`（新增：10 张表解析 + CSV 编码/行数/中文表头） | 56 |
| `tools\smoke.py` | 12 |
| `tools\test_save_layer.py` | 14 |
| `tools\verify_all.py` | 17 |

一键跑：`python tools\run_tests.py`

---

## v0.2 — 2026-09-13

**主题：把保护机制彻底破掉，让编辑器真的能用。**

### 🔑 逆向：三个密钥全部拿到

* `761205` —— `Data\*.rvdata2` 数据库、`System\Game.md5`
  （用 32 位宿主内置的批量试密钥模式，在 main.dll 解壳镜像的字符串表里爆破命中）
* `imoutogadaisuki` —— `Data\Scripts.rvdata2`
  （在 `761205` 附近的常量区取子串 + 变形爆破命中）
* `tiyan_version` —— 存档 `save.rvdata2` / `AutoSave\*.rvdata2`
  （解开脚本本体后，直接读 `Config::File::SAVE_FILE_PASSWORD`）

关键认识：`decryption_file` 的第三个参数**就是密钥字符串**；
密钥不对时 DLL 只写 0 字节空文件（不报错），这正是爆破的判定依据。
v0.1 里"main.dll 有出厂密钥状态、解不开游戏文件"的结论是**错的**。

### 🛠 新增

* `src/xj_save.py` —— 存档语义层：
  * `gold()` / `set_gold()`（自动重算 `Lock` 校验和）
  * `check_locks()` / `repair_locks()` —— 防作弊校验检查与一键修复
  * 角色 `@level/@hp/@mp/@name`、开关、变量、队伍成员、物品读写
  * `shield_seed()` / `lock_master()` —— 复刻 `v*91+45+seed/800`
* GUI 新增「快捷修改」页签（金钱 / 角色 / 开关变量 / 防作弊修复 / 保存）
* 自动选密钥：`key_for()` 按文件名猜，猜不出就**依次试三个密钥**
  （这样连 `save.rvdata2.bak.20260913-120000` 这种备份也能直接打开）
* 工具链：`run_brute.py`（崩溃容忍 + 多进程并行爆破）、`genkeys.py`、`probe_near.py`、
  `dump_scripts.py`、`parse_diag.py`、`hexdump.py`、`verify_all.py`、
  `test_save_layer.py`、`decrypt_all.py`、`cleanup.py`
* 文档：`docs/存档格式.md`（重写）、`docs/逆向过程.md`（重写）、
  `docs/待解决问题.md`（重写）、`README.md`、`使用说明.txt`

### 🐞 修复（Marshal 解析器）

* 支持 `}`（带默认值的 Hash）、`C`（String/Array/Hash 子类）、
  `c`/`m`（类 / 模块对象，**且它们要占对象编号**）
* 支持 `I` 包装的**非 ASCII 符号**（本作实例变量名是中文：`@体质`、`@法力`…），
  且 `I` 包装**不额外**占对象编号
* 加严格校验开关（链接越界 / 类名 / 实例变量名），配合 `tools/parse_diag.py`
  可以打印出错时的递归容器链，定位错位快很多

修完后：17 个明文文件（含 3 个存档、560 KB 的 `Classes.rvdata2`）全部完整解析，
解析终点与文件末尾逐字节对齐，重写自洽（`tools/verify_all.py`）。

### ✅ 测试

* 单测 61 项全绿：`test_marshal` 27 / `test_codec` 15 / `test_model` 12 / `test_gui` 7
* 新增冒烟：`tools/smoke.py`（解密→解析→加密往返，14 项）
* 新增语义层回归：`tools/test_save_layer.py`（改金钱/开关/变量/角色 + 防作弊校验修复，14 项）

---

## v0.1 — 2026-09-12

* 建立仓库骨架与 git 历史；`src/` 拆分出 `xj_env` / `xj_codec` / `xj_marshal` /
  `xj_edit` / `xj_model` / `xj_viewer`，附 32 位宿主 `xj_codec32.cs`
* 完成 Ruby Marshal 4.8 解析 / 序列化 / 区间补丁；tkinter 界面（概览 / 数据树 / 说明）
* 摸清 `main.dll`：MPRESS 加壳、导出表、参数必须 UTF-8、8 字节分组 ECB、
  密文长度是 8 的倍数
* 文档：`docs/存档格式.md`、`docs/逆向过程.md`、`docs/待解决问题.md`
* **已知限制（v0.2 已解决）**：当时误判为"main.dll 出厂密钥状态与游戏不一致"，
  因此解不开游戏自己的密文文件
