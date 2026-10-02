# 画迹2 存档修改器（huaji2-save-editor）

> **《画迹2》内测版（游戏版本 2.201）** 的存档编辑器 —— 解密 → 解析 → 改 → 加密写回。
>
> ⚠ **只适用于内测版2.201**。尝鲜版（v0.x 线）在 `main` 分支上，**两版存档格式
> 和加密算法完全不同、不能互换**（内测版是 AES-128-ECB+Zlib，尝鲜版是
> main.dll 的 8 字节分组 ECB）。用错工具会「打不开存档」。
>
> 作者**[@huxc573](https://github.com/huxc573)** · 开源协议 **MIT** · 当前版本 **v2.201-beta.8**

`huaji1-save-editor` 的迭代作品（画迹1 的编辑器见 `!Tools\Github\huaji1-save-editor`）。

本作在内测版换了保护壳，而且**内测版的 `System\main.dll` 加壳后导不出加解密函数**，
所以本工具**完全不走 dll**，两套算法都是纯 Python 复刻（零外部依赖）：

| 对象 | 算法 | 实现 |
| --- | --- | --- |
| 存档 `save.rvdata2` | **AES-128-ECB + Zlib**，口令 `153ad4v3fbdgbgd`（15 字符**零补齐**到 16 字节） | `src/save_v201.py` |
| 数据表 `Data\*.rvdata2` | **按文件名派生的 RC4**（`'9KQ1L0PWRESZV7HM'` + `b36(crc32(文件名))[0..13]`，取**后** 16 字符） | `src/data_v201.py` |
| 机器码 | `PhysicalDrive0` → `DeviceIoControl(0x2D1400)` → CRC32(1024B) | `src/machine_id_v201.py` |

实测：内测版 `Data` 下 **403/403** 个表全部解出；机器码读出 `630693299`。

---

## ✨ 能做什么

| 功能 | 状态 |
| --- | --- |
| 自动解密游戏原档 `save.rvdata2` / `AutoSave\*.rvdata2` | ✅ |
| 解析 Ruby Marshal 4.8（含中文字段名、类对象、对象链接） | ✅ |
| **改金钱**（超上限自动压到上限的 5/6）/ 步数 / 存档次数 / 战斗次数 | ✅ |
| 改角色等级 / HP / MP / 名字 / **获得经验** / 中文五维属性 | ✅ |
| **背包 4 页×20 格：改数量 / 清空 / 添加物品**（武器、防具同理） | ✅ |
| **物品模板列表 + 搜索 + 双击写进选中格子**（照画迹1） | ✅ |
| **背包体检 + 一键修复**（结构坏 / id 无效 / 数量 0 / 超上限 / 重复格 / **缺运行时内容**） | ✅ |
| **运行时内容（孵化蛋/礼包）自动生成或从同款克隆**，可指定“孵出哪只” | ✅ 孵化蛋抽取规则**待适配**（见下） |
| **`@attr` 键类型与游戏一致**（外层字符串键 `"data"`，旧档一键置换） | ✅ |
| **存档管理：备份（可填备注）/ 恢复选中 / 恢复最新 / 编辑备注 / 删除选中 / 删除无备注 / 删除非最新** | ✅ |
| **召唤兽：等级·气血·魔法·六项资质·五行·忠诚·寿命·成长·五维** + 预设（「全员忠诚满」一键全角色） | ✅ |
| **新增召唤兽（221 只可选）· 放生 · 设为出战 · 改名 · 技能** | ✅ 资质部分为**估算值**（见下） |
| **召唤兽技能克隆**：从存档里任意一只（别的角色身上的也行）整套复制，默认覆盖、可选合并 | ✅ |
| **机器码：读本机 / 存档记录的机器码，一键追加或替换**（换机器玩） | ✅ 纯 Python，不需管理员 |
| 背包格子带**「内容」列**（`蛋→狐狸精(37)`）+ **重抽/指定内容** | ✅ |
| 改开关 / 变量（带游戏自己的名字注释） | ✅ |
| 数据树浏览任意字段（懒加载 + 全局搜索 + 右键改值 + **中文注释**） | ✅ |
| **Lock 校验和体检 + 一键修复**（内测版唯一的校验层） | ✅ |
| 写回前自检 + 自动 `*.bak.<时间戳>` 备份（收进 `.huaji2-save-editor` 目录） | ✅ |
| **打包成 exe**（`tools\build.py`，自带 32 位宿主，**不弹黑框**） | ✅ |
| 技能 / 装备的可视化编辑 | ⏳ 见 `docs\待解决问题.md` |

### ⚠ 已知限制（内测版特有）

两处**如实说明**，都是因为 V2.201 的 `$baby` 表（召唤兽资质数据）
**在游戏里是运行时动态生成的**（脚本里只读不赋，`Data\` 下也没有 `Babies.rvdata2`），
静态分析拿不到真值：

1. **孵化蛋的抽取规则未适配** —— 游戏按 `$baby[i][:allow_lv]` 分三档动态筛，
   工具目前沿用尝鲜版的硬编码号段，抽出来的召唤兽**可能对不上**。
2. **「新增召唤兽」里 107 种的六项资质是估算值**（按 id 区间 +同档位近似），
   加出来后可在召唤兽页手动修正。

其余功能（改钱 / 改等级 / 背包 / 机器码 / 名字显示 / 存档管理）都实测通过。

### ⚠ 防作弊：内测版比尝鲜版**少两层**

V2.201 脚本里 `cheated` / `$jiance` / `security` 记账**全部不存在**
（实测 `grep` 零命中，存档里也没有 `@cheated` / `@keyword` 字段）。所以：

* 内测版**没有**周期检查、**没有**作弊标记、**没有**物品计数校验；
* 仅存的是 **Lock 校验和**（`@master = 值*91 + 45 + 种子/800`），工具改钱时自动重算；
* 上限常量仍在（等级 **155**、召唤兽 **165**、金钱 **9,999,999,999**、
  仓库 **12 页**），体检会提示超限，但**超了不会被游戏惩罚**。

### 界面（照画迹1 的编辑器重排，10 个页签）

```
概览 / 快捷修改   金钱·步数·存档次数·战斗次数 + Lock 校验和检测并修复
存档管理         备份 / 恢复选中 / **恢复最新** / 删除选中 / **删除非最新** + 打开备份目录
全部解析数据     懒加载数据树 + 全局搜索 + 节点详情（带中文说明）+ 右键改值
角色 / 属性      角色列表；等级/经验/五维；满级(155)/经验+10000/回血/属性+10
背包 / 物品      4 页×20 格；左边格子（含“内容”列）、右边物品模板（可搜索，
                 双击写进格子）；改数量/清空/本页全部 99/背包体检/一键修复/
                 重抽内容（自动同步计数校验）
召唤兽           选角色；召唤兽一览表（含★出战）+ 【新增召唤兽】【设为出战】
                 【放生】【恢复模板名】；字段编辑 + 预设；改名（改显示名；
                 基础名 @name 管立绘/音效，不提供修改）；
                 技能（学会/忘掉/清空/**从…克隆**，上限 12；搜索即时显示描述，下拉 ↑/↓
                 直接切换并刷新描述；「从…克隆」可把任意一只召唤兽（含别的角色身上的）
                 的技能整套复制过来，默认覆盖、勾选后合并）
开关 / 变量      双击即改（带游戏自己的名字：MAP_SCROLL / PLOTING …）
机器码           存档绑定：本机机器码 / 存档记录 / 追加·替换·清空
数据表 (CSV)     10 张 Data 表的预览 + 导出 CSV
说明 / 机制      密钥、存档结构、防作弊原理、CSV 用法
更新日志         打包进 exe（源码运行时读 CHANGELOG.md）
```

---

## 🚀 快速开始

```bat
:: 1) 需要 Python 3.8+（64 位），不用装任何第三方库
:: 2) 编译 32 位宿主（仓库里已经带了一份编译好的，改过 .cs 才需要重编）
python tools\build_host.py

:: 3) 跑测试（可选，但建议）—— 19 组
python tools\run_tests.py

:: 4) 开图形界面
python src/huaji2_save_editor.py

:: 5) 打包成 exe（需要 PyInstaller；会自动找仓库旁的 .venv）→ 顺带打出发行 zip
python tools\build.py
python tools\build.py --dll-dir     :: 宿主放进 dist\dll\ 子目录

:: 5.5) 发版前自检：缺宿主时确实用不了（A 组 NG）/ 连宿主一起拷时 OK（B 组）
python tools\check_pack.py

:: 6) 发 GitHub Release（附件按 ASCII 命名，需要 gh 已登录）
python tools\release.py
python tools\release.py --upload-only   :: Release 已存在，只重传附件
```

打包产物在 `dist\`：`画迹2存档工具.exe` + `XJCodec32.exe`（**必须挨着 exe**，
或放 `dll\` 子目录）+ `使用说明.txt`，最后自动打成
**`huaji2-save-editor-vX.Y.Z.zip`**（Release 上**只挂这一个附件**）。
`XJ_SELFTEST=1` 跑一次会写 `selftest_result.txt` 自检报告。

> 本地产物名**固定不带版本号**（`dist\画迹2存档工具.exe`），重复打包不会堆版本文件；
> 版本号只出现在发行 zip 名上。命名规则写在 `tools/build.py`
> （`EXE_NAME` / `ZIP_MEMBERS` / `RELEASE_ASSETS`），发版直接跑
> `python tools\release.py`。
>
> **为什么只发一个 zip**（2026-09-30）：宿主 `XJCodec32.exe` 不在 onefile 里
> （`codec.host_candidates()` 是在 **exe 所在目录**找它的），少了下它就弹
> 「打开失败 / 缺少依赖」，整个工具都用不了。以前挂 exe / USAGE.txt /
> XJCodec32.exe 三个附件，**总有人只下主程序** —— 和画迹1 v1.4.0 修掉的是同一个坑
> （画迹1 那边漏下的是 `TP.dll` / `Socket.dll`）。

界面会自动定位游戏目录和存档；找不到就设环境变量：

```bat
set XJ_GAME=D:\Life\Game\Local\MH\画迹\【画迹2：缘起凡尘】 [尝鲜版]
```

命令行也能用：

```bat
python src\save.py            :: 存档概览 + 防作弊校验状态
python src\save.py repair     :: 一键修好所有 Lock 并写回
python src\datatables.py              :: 列出 10 张 Data 表 + 行数
python src\datatables.py --out csv    :: 数据表转 CSV（utf-8-sig，Excel 直接开）
python tools\re\decrypt_all.py      :: 把各文件解密到 tools\_plain\
```

---
## 🩹 Ruby 里 `0` 是真值：清作弊标记写成整数 0 等于没清（v0.4.8）

游戏只判断一句 `if $game_system and $game_system.cheated`，而 Ruby 里**只有
`false` 和 `nil` 是假值 —— 整数 `0` 是真值**。

v0.4.7 把 `@cheated` 写成 `false` 时，落盘的字节其实是 Marshal 的整数 `0`
（`i\x00`），游戏读回来是 `0` → 条件成立 → 解档后照样
`v = Graphics.frame_count - 0`，跑够时间就弹「存档异常」退出。

v0.4.8 在序列化层修好了（节点里存的是 Python `bool` 就写 `T`/`F`），并且：

* 体检把整数 `0` 也算**有问题**（老版本写入的 `i0` 能被认出来并改成 `false`）；
* 新增**「清理所有存档（含 AutoSave）」** —— `AutoSave\save00..09` 也带着标记，
  读自动存档一样会被惩罚，只修主存档不够；
* 载入存档时若 `@cheated` 不是 `false`，会立刻弹窗提醒并问要不要顺手修好。

⚠ v0.5.1 起概览页的「防作弊检测并修复」会一次修齐 Lock 校验和、五类记账、
`@cheated`、`@keyword` 和机器码；也可以单独用「清除作弊标记」/
「清理所有存档」/ `python tools\clear_cheat.py --all` 清。

---
## ⚠️ 战斗里崩 `RGSSError: disposed sprite`（v0.4.7）

这是**游戏的作弊惩罚**在战斗里翻了车，不是存档数据坏了。脚本 29485-29495 行：

```ruby
if $game_system and $game_system.cheated
  v = Graphics.frame_count - $game_system.cheated
  if v > 60*60*25-123
    msgbox "存档异常！#{GET_HARD_DISK_CHARACTER.call}"; exit
  elsif v > 60*60*20-123 and !$timer.has?('cheating_circle')
    $timer.every(2, proc{|i| ... $game_player.sprite.zoom_x = rand(0.8..1.0); ... })
    $timer.every(300, proc{|i| s = $game_player.sprite; ... unless s.disposed? })
  end
end
```

`@cheated` 一旦被记下（周期检查发现超限，或物品计数校验对不上），20 分钟后开始
“惩罚”；而它去碰的 `$game_player.sprite` 在**战斗中已经被 dispose** → 报错。

处理：工具里「概览」→ **体检 → 一键按规则修复 → 清除作弊标记 → 同步物品计数校验**，
然后**在游戏里重新读一次档**（惩罚计时器只在内存里）。
v0.4.7 起 Ctrl+S **保存前会自动体检**，有问题会弹窗并问你要不要顺手修好。

---
## � 新增召唤兽 / 小孩怎么来（v0.4.6）

**结论：小孩（小精灵 #181、小毛头 #182、小魔头 #183、小仙灵 #184、小仙女 #185、
小丫丫 #186，以及善财童子 #187）正常玩法拿不到。** 它们在 `Data\Actors` 里的备注是
`data = :神兽资质3`，而所有开蛋道具只抽这些范围：

| 道具 | 抽出范围（脚本 `Game_Party#孵化蛋` / `#神兽蛋`） |
| --- | --- |
| 初级孵化蛋 #110 | `rand(21..23, 25..63)` |
| 中级孵化蛋 #111 | `rand(64..95, 127..134)` |
| 高级孵化蛋 #112 | `rand(96..126)` |
| 神兽孵化蛋 #113 | 备注池 `:神兽资质` ∪ `:神兽资质2` |
| 神兽蛋 #221 / #222 | `:神兽资质` / `:神兽资质2` |

`:神兽资质3` 在整个脚本里只有一处引用（资质配置表），没有任何道具/公共事件/商店
会用它；敌人备注的 116 条捉宠表里也没有 `baby_id = 181~186`。唯一直接发小孩的是
调试方法 `setup_battle_test_babys`（`(181..187).each{ add_baby(i) }`）。

现在用工具一键加：**召唤兽页 → 新增召唤兽 → 勾“只看小孩 181-187” → 加这只**。
加出来的对象完全按游戏 `Game_Baby.new` 造：

```
身份：名字/立绘/职业/等级 取 Data\Actors 模板
资质：普通 = 上限 − rand(201/401/301…)（变异 ×0.66）；神兽 = 定值
成长/寿命：普通 = 上限 − rand(6)/100、上限 − rand(13)×100；神兽 = 定值、寿命 :infinite
五维：普通 = 10+主人等级+rand(11)；神兽 = 20+主人等级；潜能 = 主人等级×5
技能：神兽 = 该职业全部技能；普通 = 每条 40%（上限 12）
气血/魔法：按 real_mhp = 体质×成长×6 + 体力资质×主人等级÷1000 等公式算满
链接：@master 指回主人、@attr.@master 指回自己
```

小孩（神兽资质3）的配置是全游戏最高档：**攻 2400 / 防 2400 / 体 7500 / 法 4800 /
速 2100 / 躲 2100、成长 1.8、永生**。

---

## �💾 存档管理：备份放哪儿（v0.4.5）

备份统一放在**存档旁边的子目录**里（规范化，不再散落）：

```
<游戏根>\save.rvdata2                        ← 当前存档
<游戏根>\.huaji2-save-editor\                ← 备份目录（名字带点，默认隐藏）
    save.2026-09-13_014530.rvdata2           ← 手动（「立即备份」）
    save.2026-09-13_021145.auto.rvdata2      ← 自动（Ctrl+S 前留一份，90 秒内不重复）
```

| 按钮 | 作用 |
| --- | --- |
| 立即备份 | 把当前存档复制一份进备份目录 |
| 恢复选中 | 用选中的备份覆盖存档，随后自动重新载入（双击一行也行） |
| **恢复最新** | 不用选，直接把存档换回**上一次修改之前**的状态（最新的一份备份） |
| 删除选中 | 删掉选中的备份（可多选） |
| **删除非最新** | 只留最新的一份，其余全删 |

恢复不再额外留“恢复前”备份（要多一个回头路就先点「立即备份」）。
老版本用过的 `huxji2-save-editor` / `huaji2-save-editor` 目录里的备份
**照样列得出来、照样能恢复/删除**，只是新备份不再往里写。
这一页只做文件复制/删除、**不解析存档**，存档已经改坏到打不开时也能靠它救回来。
核心逻辑：`src\backup.py`（测试：`tests\test_backup.py`）。

---

## 🥚 孵化蛋一用就报错？真凶是 `@attr` 的**键类型**（v0.4.4）

游戏的孵化代码（公共事件 24）读的是**字符串**键：

```ruby
$game_player.actor.add_baby($item_obj.data[:data][:id])   # item.data → @attr["data"]
```

游戏自己写的物品是 `@attr = { "data" => { :type => :baby_egg, :data => {:id=>57} } }`
（**外层字符串键**、内层符号），而老版本工具写成了符号键 `:data` →
游戏 `item.data` 得到 `nil` → `nil[:data]` → **`undefined method '[]' for nil:NilClass`**。

v0.4.4 修了三处：写入用字符串键（与游戏一致）；`hash_get()` 解引用 `I` 包装的键并识别
字节串（所以“游戏送的蛋”现在也读得出来）；背包体检新增“**键类型不对**”一项，
「一键修复」按原内容重写成字符串键（**内容一个不动**）。

> 已经用老版本改过的存档：打开「背包 / 物品」→「**背包体检**」→「**一键修复**」即可治好。

---

## �📊 数据表 → CSV（查 id / 找物品很方便）

`Data\*.rvdata2` **全都是加密的**（密钥 `761205`），工具会直接解密再转：

| 表 | 行数 | 表 | 行数 |
| --- | --- | --- | --- |
| `Items` 物品 | 300 | `Actors` 角色 | 300 |
| `Weapons` 武器 | 400 | `Classes` 职业 | 300 |
| `Armors` 防具 | 300 | `Enemies` 敌人 | 700 |
| `Skills` 技能 | 320 | `Troops` 敌人队伍（可选） | 310 |
| `States` 状态 | 120 | `CommonEvents` 公共事件（可选） | 100 |

`csv\Items_物品.csv` 的列：`ID, 名称, 说明, 效果, 伤害, 特性, 价格,
消耗品, 使用场合, 影响范围, 命中类型, 成功率, 使用次数, TP增加,
类别, 动画, 图标, 备注` —— 嵌套的 `@effects` / `@damage` / `@features`
已经翻成人话（`HP回复 +500%；解除状态#1 0%`）。

---

## 🔑 三个密钥（逆向结果，实测通过）

| 密钥 | 用途 |
| --- | --- |
| `761205` | `Data\*.rvdata2` 数据库、`System\Game.md5` |
| `imoutogadaisuki` | `Data\Scripts.rvdata2`（游戏脚本本体） |
| `tiyan_version` | 存档 `save.rvdata2` / `AutoSave\*.rvdata2` |

怎么找出来的（以及走过的弯路）见 `docs\逆向过程.md`。

---

## 🛡 防作弊是怎么被解决的

游戏把金钱这类关键数值包在 `Lock` 对象里，读的时候校验一个校验和：

```ruby
class Lock
  def get_encryption(v); v * 91 + 45 + seed / 800; end   # seed = $game_system.seeds[:shield]
  def show
    if get_encryption(@value) != @master
      msgbox '游戏异常！'; exit          # ← 直接改数值就会踩这里
    end
    @value
  end
end
```

所以本工具改 `@value` 时会**顺手把 `@master` 重算**，
另外提供「检查并修复防作弊校验」按钮，可以一次性修好整个存档里所有 `Lock`。

> 改存档 / 改 `Data` 都不会被 `Config.ini` 里那个 md5 校验发现
> —— 那份清单只包含 `Game.exe` 和 `System\main.dll`。

---

## 📁 仓库结构

```
src\
  huaji2_save_editor.py  主程序：tkinter 界面（9 个页签，照画迹1 的编辑器重排）
  doctree.py             文档树：打开 → 解析 → 摘要 / 浏览 / 改值 → 写回
  save.py                存档语义层：按游戏自己的数据结构提供「人话」接口
  game.py                游戏内容层：金钱 / 背包 / 经验 / 召唤兽 / 防作弊体检
  babies.py              召唤兽：新建 / 删除 / 出战 / 技能 / 改名
  codec.py               加解密（驱动 32 位宿主，自动选密钥）
  marshal_ruby.py        Ruby Marshal 4.8 解析 / 序列化
  patchwriter.py         区间补丁：只改「动过的字段」的字节区间
  datatables.py          Data\*.rvdata2 → CSV（10 张表 + 嵌套字段翻人话）
  paths.py               游戏目录 / 存档路径定位
  fieldnames.py          字段名的中文注释表
  nodetext.py            节点 → 人能看懂的文字（数据树与界面共用）
  itemattr.py            物品的运行时内容（@attr）
  backup.py              存档备份 / 恢复
  changelog.py           内置更新日志（由 tools/build.py 生成）
  tables\                游戏常量表（exp / sect / baby_aptitude / db_table，由 tools/gen_*.py 生成）
                          db_table.py = **内置名字表**（技能/物品/武器/防具/角色/门派），游戏目录读不到时兜底
  native\                XJCodec32.exe + codec32.cs（32 位宿主源码与编译产物）
tests\              全部回归测试（19 组）：
  test_marshal  test_codec  test_model  test_roundtrip  test_semantic_equal
  test_game_layer  test_backup  test_baby  test_save_layer  test_db_csv
  test_gui  test_gui_quick  test_actor_tab  test_save_files  test_dist
  test_db_embed（内置名字表）  test_bundle_db_table（打包版 + 坏 Data 端到端）
  smoke.py（全档冒烟）  verify_all.py（整档重写自检）
  probe_*.py          界面体检探针（只碰副本存档，跑完删）
tools\              日常工具
  run_tests.py        一键回归；build.py / build_host.py / release.py 打包发版
  gen_exp_table.py / gen_sect_table.py / gen_baby_data.py / gen_db_table.py   生成 src\tables\
  check_pack.py       发版前看门狗：验「只给主程序用不了、带上宿主才能用」
  clear_cheat.py      命令行清作弊标记    cleanup.py 清可重跑的中间产物
  normalize_eol.py    统一 LF    gitcheck.py 查行尾    pack_only.py 只打包不重编宿主
  re\                 逆向考古脚本（一次性探针，留着备查，平时不用）
probes\              最早的 32 位宿主 / 加密算法探针（编号 00–23，按顺序读）
csv\                数据表导出的 CSV（gitignore，随时可重导）
docs\
  存档格式.md        文件位置 / 密钥 / 结构 / Lock 校验 / Data 表 / 解析的坑
  逆向过程.md        保护机制怎么破的（含失败路线）
  开发指南.md        代码结构、扩展方式
  待解决问题.md      还没做的增强项
```

---

## ⚠ 注意

* 游戏**运行中**改存档无效：游戏只在存/读档时读文件，改之前请先退出游戏。
* 改完建议先进游戏读一次档确认（有问题可以用 `.bak.` 备份回滚）。
* 存档里存着本机硬盘码（`@config[:hard_disk_code]`），
  换机器玩请用游戏自己的存档功能。
* 本工具只做**离线存档编辑**，不含内存修改 / 反调试对抗。

## 📜 许可

MIT，见 `LICENSE`。仅用于单机游戏存档的互操作与备份，请勿用于传播游戏本体。
