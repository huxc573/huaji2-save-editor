# 更新日志

## v0.4.3 — 2026-09-13

**主题：报错提示全中文 ＋ 背包能直接看到/重抽“运行时内容” ＋ 更新日志写进 exe ＋ 机器码单独一页。**

### 🈶 报错提示不再冒英文

以前某个操作抛异常时，弹框和状态栏会直接显示 Python 的英文消息
（`NoMethodError`、`object is not subscriptable`、`Access is denied` …），
看完又变回中文。现在两层翻译：

* `zh_error()`：按异常类型给中文说法（找不到对应的东西 / 文件被占用 /
  存档结构不对…），原文附在“技术细节”里；完整堆栈照旧写 `error.log`；
* `zh_text()`：字符串层面把常见英文短语换成中文（给那些直接显示 `str(e)` 的地方）。
* 宿主 `XJCodec32.exe` 里两句英文提示也改成了中文。

### 🎒 背包：“内容”列 + 重抽

* 格子列表新增 **“内容”列**，直接写出运行时内容摘要：
  `蛋→狐狸精(37)`、`技能书→高级必杀(113)`、`阵型→龙飞阵` ……一眼就能看出
  哪颗蛋缺“【诞生对象】”；
* 新增 **「给选中的格子重抽内容」** 按钮：按游戏脚本的规则重新生成一份
  （可以在“孵出/开出对象 id”里指定孵出哪只，留空就随机抽）。
* `GameEditor.set_payload()` / `payload_summary()`（新增 API）。

> 实测：`tools/probe_payload_now.py --fix` 在存档副本上跑「一键修复」，
> 初级孵化蛋 → `{id:37}`（诞生物：狐狸精）、神兽孵化蛋 → `{id:150}`（超级神牛）、
> 魔兽要诀 → `skill_code 113`，保存后重开依旧带内容。

### 📖 exe 的“更新日志”写死了

以前是去读运行目录的 `CHANGELOG.md` —— onefile 的 exe 运行在临时解包目录里，
读不到就成了空白。现在 `tools\build.py` 会把 `CHANGELOG.md` 生成成
`src\xj_changelog.py`（内置文本）编进 exe，同时仍然把 `CHANGELOG.md`
放进 `dist\`（想改文案不重编译也能看）。

### 🖥 机器码独立一页（照画迹1）

“概览”页底部只留一行概述，完整功能搬到新的 **「机器码」页**：
存档记录列表、本机机器码、输入框 + 按钮：
读取本机机器码 / 读存档里第一个 / 加入存档（追加，推荐）/ 替换成这个 /
用本机机器码替换 / 清空存档记录，右下角还有**操作记录**。

### ✅ 测试

* `tools\test_game_layer.py` 66 项（+ 内容摘要、重抽/指定、对空格子重抽报错）
* `tests\test_gui_quick.py` 77 项（+ 机器码页与四个按钮、内容列、重抽内容）
* `tests\test_gui.py` 25 项（页签变 10 个）

## v0.4.2 — 2026-09-13

**主题：修「工具加进去的孵化蛋一用就报错」＋ 背包里装备不显示名字。**

### 🥚 孵化蛋为什么会报错（根因）

游戏里这类东西的“内容”是**发给你的时候现抽的**，存在存档物件的 `@attr`（脚本里叫
`item.data`）：

```ruby
def 孵化蛋(item)
  i = item.id - 110
  item.data = { type: :baby_egg, data: { id: [ rand(21..23, 25..63), ... ][i] } }
end
```

以前工具是照 `Data\Items.rvdata2` 的模板“凭空造”，`@attr` 只能是空 Hash，
游戏一用就 `item.data[:data][:id]` → **`undefined method '[]' for nil:NilClass`**
（就是你看到的那张报错图）。

现在做对了三件事：

1. **优先克隆存档里已有的同款**（连运行时内容一起拄）——最保险；
2. 存档里没有同款时，**按游戏脚本里的生成规则现造一份**
   （新增 `src\xj_payload.py`，把脚本 `Game_Party#孵化蛋/神兽蛋/鬼谷子/进阶石/
   制造指南书/百炼精铁/魔兽要诀/上古锻造图策/天眼珠/人参果/真知棒/石头/元宵/
   导航旗 ` 的规则照抄成 Python）；
3. 背包页新增「**孵出/开出对象 id**」输入框（留空＝按游戏规则随机），
   写入时也会在提示行提醒“这件东西属于运行时内容”。
4. **已经加坏的能修**：「背包体检」会把 `@attr` 是空的这类格子列出来，
   「一键修复」直接补上内容（实测你的存档里有 4 件：初级孵化蛋×2、
   神兽孵化蛋×99、魔兽要诀×2）。

### 🎽 背包里的装备不显示名字

背包（`@items`）里是**道具/武器/防具混装**的（召唤兽装备也是武器/防具），
以前统一拿 `Items.rvdata2` 查名字，查不到就成 `?`。现在按**物件自己的类**选表：
`RPG::Weapon` → Weapons、`RPG::Armor` → Armors，再退到对象自带的 `@name`。
实测：槽 13 `RPG::Weapon id=183` → 铁骨扇、槽 15 `RPG::Armor id=192` → 竹编护腕。

### ✅ 测试

* `tools\test_game_layer.py` 59 项（新增：识别运行时内容物品、自动/指定生成的孵化
  蛋内容、克隆同款、坏蛋体检 + 一键修复、混装武器装备名字）
* 其余组不变，一键全绿：`python tools\run_tests.py`

## v0.4.1 — 2026-09-13

**主题：修「重新载入会闪一下 XJCodec32.exe 黑框」＋ 背包功能照画迹1 补齐 ＋ 机器码。**

### 🪟 不再闪黑框

打包成 exe 后，每次加解密都要起一次 32 位宿主，Windows 会给它弹一个控制台窗口
（`--windowed` 的主程序 + 控制台子进程），所以「重新载入」时闪一下。
画迹1 的编辑器也是这么解决的：**`CREATE_NO_WINDOW` + `STARTF_USESHOWWINDOW`**，
现在 `xj_codec._run()` 一律静默启动宿主。

### 🎒 背包（照画迹1 的编辑器的功能补齐）

画迹1 的背包页是「左边格子列表 + 右边可搜索的物品模板 + 写入/清空/异常修复」，
现在画迹2 也齐了：

| 功能 | 说明 |
| --- | --- |
| **物品模板列表 + 搜索** | 右边列出 `Data\Items.rvdata2`（武器/防具同理）的 300 件物品，按名字/说明/id 过滤 |
| **写入选中的格子** | 双击模板（或点按钮）＝把那一格**换成**这件物品；原有数量会保留 |
| **放进第一个空格子** | 不用先挑格子 |
| **选中格子自动回填** | 点格子会把 id / 数量填进输入框（画迹1 的 `load_pack_edit`） |
| **本页全部 99** | 批量把当前页已有格子的数量设成 99 |
| **背包体检** | 结构坏 / 物品 id 在 Data 表里不存在 / 数量 0 / 超单格上限 / **同一件东西占两格** |
| **一键修复** | 重复格合并数量、超上限截断到 99、坏格子清空，并同步物品计数校验 |

顺带真抓到一个问题：这份存档里 **9 号格（佛手×1）和 0 号格（佛手×13）重复**，
游戏按 id 取数量时会算不清 —— 点「一键修复」就会合并成 14 个。

### 🖥 机器码（存档绑定）

游戏用 `main.dll!get_hard_disk_character()` 取本机机器码，存在
`$game_system.config[:hard_disk_code]`（**数组**），启动时 `include?` 比对，
不在里面就弹「存档异常」—— 所以存档拷到别的电脑会打不开。

* 宿主新增 `machine` 模式：调 `get_hard_disk_character` 取本机机器码
  （实测这就是存档里那个值：`630693299`）；
* 界面「概览 / 快捷修改」新增**机器码面板**：显示本机机器码 / 存档记录的机器码、
  是否匹配，按钮「读取本机机器码」「用本机机器码填上」
  **「加入存档（追加，推荐）」**「直接替换成这个（只留一个）」；
* 「防作弊体检」多一项「机器码」，不匹配会标红；
  「一键按规则修复」也会自动把本机机器码**追加**进存档；
* `docs\存档格式.md` 补了机器码那一节。

### ✅ 测试

* `tools\test_game_layer.py` 52 项（新增：机器码读/追加/替换/恢复、模板表与搜索、
  `set_item` 换物品、批量改数量、背包体检+修复）
* `tests\test_gui_quick.py` 70 项（新增：模板列表/搜索过滤、双击模板写格子、
  选中回填、批量、体检修复、机器码面板四个按钮）
* 其余组不变，一键全绿：`python tools\run_tests.py`

## v0.4 — 2026-09-12

**主题：把"玩法数据"也做出来（背包 / 召唤兽 / 经验）＋ 把游戏的反作弊整明白了 ＋ 能打包成 exe。**

### 🎒 新的可改内容（都是实测数据结构）

| 页签 | 能改什么 |
| --- | --- |
| 概览 / 快捷修改 | **存银**（游戏里就叫这个名，就是金钱）＋ 步数 / 存档次数 / 战斗次数 |
| 背包 / 物品 | **4 页 × 20 格**：看、改数量、清空、**添加物品**（道具 / 武器 / 防具分开） |
| 角色 / 属性 | 加了**获得经验**（`@exp`）与**升级所需经验**（`@limit_exp`） |
| 召唤兽 | 等级·气血·魔法·TP·经验·**六项资质**·**忠诚**·寿命·成长·五维/潜能 + 常用预设 |
| 开关 / 变量 | 补上游戏自己的名字（`MAP_SCROLL` / `PLOTING` / `CHOICS_COLUMN` / `DIALOGUE`） |

背包为什么能"加"东西：游戏的容器是 `{槽号 => [RPG::Item 对象, 数量]}`，
**物件本体就存在存档里**（不是只存 id），所以加物品要从 `Data\Items.rvdata2`
复制一份模板，再补上游戏自己加的 5 个字段
（`@result_note` / `@attr` / `@update` / `@new` / `@transaction_code`）。

### 🛡 反作弊：这次是真的搞清楚了（三重）

1. **`Lock` 校验和**（v0.2 已解决）：金钱 `@master = @value*91+45+种子/800`。
2. **周期检查**（v0.4 新发现）：脚本 29455 行起，**每 300 帧**查一次
   ```
   $jiance = [MAX_LEVEL_ACTOR*761205, MAX_LEVEL_BABY*761205,
              MAX_GOLD*654321,     MAX_WAREHOUSE[1]*159753]
   角色等级 > 60 / 出战召唤兽等级 > 65 / 存银 > 30,000,000 /
   仓库页号 > 3 / 五维总点数 > 等级*10+500      → $game_system.cheated = 帧号
   ```
   一旦被标记：游戏内 20 分钟后弹警告、**25 分钟后 `msgbox "存档异常！<硬盘码>"` 并 exit**。
   ⇒ 新增「防作弊体检」页签：列出每一项的当前值/上限、**一键按规则修复**
   （把超限的压回上限）、**清除作弊标记**（`@cheated = false` + 去掉 keyword 里的 `VNE`）。
   ⇒ 界面里的预设也相应改成合法上限（"满级(60)"、"召唤兽满级(65)"）。
   ⚠ 顺便发现**当前这份存档 `@cheated` 已经是 134700**（说明之前就被判过作弊）——
   工具里点一下「清除作弊标记」就干净了。
3. **物品计数校验**（v0.4 新发现）：`$game_system.security[:items][id]` 是 `Change` 对象，
   把"这件物品累计获得过几个"**逐位数字 AES-ECB 加密**存着（脚本 322 行 +
   `AES_ECB.set_key('admin_1941344749')`，1142 行）。
   改背包数量后如果不同步，游戏下次**合法获得**同一件物品时会发现对不上 → 记作弊。
   ⇒ `src/xj_aes.py` 用纯 Python 复刻了它的 AES-128-ECB（PKCS#7 填充、按位加密），
   **改数量/加物品时自动把计数一起改对**；缺条目的按游戏模板补一个 `Change`；
   另外提供「同步物品计数校验」按钮全量对齐。
   验证方式很硬：拿存档里 7 个真实 `Change` 的密文反解，位数字全对得上。

### 🧩 能"加减对象"了：整档重写（v0.4 的地基）

以前只能做**等宽标量补丁**，因为 Ruby Marshal 的 `@N` 对象链接一旦成员数变了就会整体错位。
这次把序列化器补齐，可以**整条顶层对象按 Ruby 的规则重新编号**：

* `xj_marshal.serialize_doc(objects)`：每个顶层对象各带 `04 08` 头、各自独立的
  **对象表 + 符号表**；
* 符号要复刻 Ruby 的写法，否则**静默坏档**：定义时非 ASCII 才带
  `I :@体质 <1 ivar> :E T` 包装，**链接（`;N`）不带包装**；
* `tools/test_roundtrip.py`：17 个游戏明文（含 `save.rvdata2`、`AutoSave\save00`，
  300 KB+）**逐字节还原** ✅ —— 什么都不改时输出与原文完全一致，
  所以整档重写不会引入任何意外差异。

### 📦 打包成 exe

`tools/build.py`（照 huaji1 的路子）：

* `csc /platform:x86` 编自带的 32 位宿主 `XJCodec32.exe`；
* `dist/` 里：`画迹2存档工具v0.4.exe` + **`XJCodec32.exe`**（必须挨着 exe；
  `--dll-dir` 可以改成放 `dll/` 子目录，`xj_codec` 会按 目录 → dll/ → bin/ 找）
  + `使用说明.txt` / `README.md`；
* **不放**游戏的 `System\main.dll`（版权 + 运行期就从用户自己的游戏目录加载）；
* tcl/tk 脚本库要 `--add-data` 带上，并在 `import tkinter` 之前设 `TCL_LIBRARY`；
* 打包后自带自检：`XJ_SELFTEST=1` 或 `--selftest` → 写 `selftest_result.txt`
  （依赖查找、明文 MD5、背包/召唤兽/防作弊体检、整档重写自检）；
* 崩溃会写 `error.log`（`--windowed` 没控制台）。

### ✅ 测试（13 组 / 370+ 项，全绿）

| 测试 | 项数 | 说明 |
| --- | --- | --- |
| `tests\test_marshal.py` | 27 | |
| `tests\test_codec.py` | 15 | |
| `tests\test_model.py` | 12 | |
| `tests\test_gui.py` | 24 | 9 个页签都建得起来 |
| `tests\test_gui_quick.py` | 57 | 含背包改数量/加物品/清空、召唤兽、防作弊体检 |
| `tools\test_db_csv.py` | 56 | |
| **`tools\test_game_layer.py`** | 35 | **新**：背包 / 经验 / 召唤兽 / 计数校验同步 |
| **`tools\test_roundtrip.py`** | 18 | **新**：逐字节还原（`tools\_plain\*.bin` 全过） |
| **`tools\test_semantic_equal.py`** | 39 | **新**：整档重写的语义等价（含对象共享关系） |
| `tools\smoke.py` | 12 | |
| `tools\test_save_layer.py` | 14 | |
| `tools\verify_all.py` | 17 | |
| **`tools\test_dist.py`** | — | **新**：把 `dist\` 拷到临时目录跑 exe 自检 |

一键跑：`python tools\run_tests.py`

### 🧰 逆向用的新工具

`dump_scripts.py`（游戏脚本全解成一整份 Ruby）、`grep_scripts.py`（中文关键词走
`tools/_keys.txt`、结果直接写 UTF-8 文件，绕开 GBK 终端）、`probe_v04_*.py`
（背包/召唤兽/属性结构）、`probe_security.py`（`Change` 密文）、`probe_attrs.py`。

---

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
