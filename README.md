# 画迹2 存档修改器（huaji2-save-editor）

> 《画迹2：缘起凡尘》[尝鲜版] 的存档编辑器 —— 解密 → 解析 → 改 → 加密写回，
> 连游戏自带的**防作弊校验**一起修好。
>
> 作者 **[@huxc573](https://github.com/huxc573)** · 开源协议 **MIT** · 当前版本 **v0.3**

`huaji1-save-editor` 的迭代作品（画迹1 的编辑器见 `!Tools\Github\huaji1-save-editor`）。
本作换了保护壳：`Data\*.rvdata2` 和存档都被 `System\main.dll` 加密，
v0.2 已经把三个密钥全部逆向出来，所以**现在是真的能用**。

---

## ✨ 能做什么

| 功能 | 状态 |
| --- | --- |
| 自动选密钥解密游戏原档 `save.rvdata2` / `AutoSave\*.rvdata2` | ✅ |
| 解析 Ruby Marshal 4.8（含中文字段名、类对象、对象链接） | ✅ |
| **改金钱**（自动同步防作弊校验和）/ 步数 / 存档次数 / 战斗次数 | ✅ |
| 改角色等级 / HP / MP / 名字 / **中文五维属性** | ✅ |
| 改开关 / 变量（界面双击即改） | ✅ |
| 数据树浏览任意字段（懒加载 + 全局搜索 + 右键改值），标量就地改 | ✅ |
| **一键检查并修复 `Lock` 防作弊校验** | ✅ |
| **`Data\*.rvdata2` 解密 + 转 CSV**（物品/武器/防具/技能/状态/角色/职业/敌人…） | ✅ |
| 写回前自检 + 自动 `*.bak.<时间戳>` 备份 | ✅ |
| 物品 / 装备 / 技能的图形化增删、打包成 exe | ⏳ 见 `docs\待解决问题.md` |

### 界面（照画迹1 的编辑器重排，8 个页签）

```
概览 / 快捷修改   金钱·步数·存档次数·战斗次数；一键修复防作弊校验
全部解析数据     懒加载数据树 + 全局搜索 + 节点详情 + 右键改值
角色 / 属性      角色列表；基础字段 + Game_Actor_Attr 中文五维；满级/回血/属性+10
队伍 / 物品      队伍成员 + 物品栏（名字取自 Data\Items.rvdata2）
开关 / 变量      双击切换开关、双击改变量
数据表 (CSV)     10 张 Data 表的预览 + 导出 CSV
说明 / 机制      密钥、存档结构、防作弊原理、CSV 用法
更新日志         直接读 CHANGELOG.md
```

---

## 🚀 快速开始

```bat
:: 1) 需要 Python 3.8+（64 位），不用装任何第三方库
:: 2) 编译 32 位宿主（仓库里已经带了一份编译好的，改过 .cs 才需要重编）
python tools\build_host.py

:: 3) 跑测试（可选，但建议）—— 9 组 218 项
python tools\run_tests.py

:: 4) 开图形界面
python src\xj_viewer.py
```

界面会自动定位游戏目录和存档；找不到就设环境变量：

```bat
set XJ_GAME=D:\Life\Game\Local\MH\画迹\【画迹2：缘起凡尘】 [尝鲜版]
```

命令行也能用：

```bat
python src\xj_save.py            :: 存档概览 + 防作弊校验状态
python src\xj_save.py repair     :: 一键修好所有 Lock 并写回
python src\xj_db.py              :: 列出 10 张 Data 表 + 行数
python src\xj_db.py --out csv    :: 数据表转 CSV（utf-8-sig，Excel 直接开）
python tools\decrypt_all.py      :: 把各文件解密到 tools\_plain\
```

---

## 📊 数据表 → CSV（查 id / 找物品很方便）

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
  xj_viewer.py      tkinter 界面（8 个页签，照画迹1 的编辑器重排）
  xj_db.py          Data\*.rvdata2 → CSV（10 张表 + 嵌套字段翻人话）
  xj_save.py        存档语义层（金钱、角色、开关变量、Lock 防作弊校验修复）
  xj_model.py       打开/摘要/写回
  xj_edit.py        区间补丁 + 自包含序列化
  xj_marshal.py     Ruby Marshal 4.8 解析 / 序列化
  xj_codec.py       加解密（调用 32 位宿主，自动选密钥）
  xj_codec32.cs     32 位宿主源码（LoadLibrary + 调用 main.dll 导出）
  XJCodec32.exe     编译产物
  xj_env.py         游戏目录 / 存档路径定位
tests\              test_marshal / test_codec / test_model / test_gui / test_gui_quick
tools\              逆向与验证脚本 + run_tests.py（一键回归）/ test_db_csv.py
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
