# 画迹2 存档修改器（huaji2-save-editor）

> 《画迹2：缘起凡尘》[尝鲜版] 的存档编辑器 —— 解密 → 解析 → 改 → 加密写回，
> 连游戏自带的**防作弊校验**一起修好。
>
> 作者 **[@huxc573](https://github.com/huxc573)** · 开源协议 **MIT** · 当前版本 **v0.4.1**

`huaji1-save-editor` 的迭代作品（画迹1 的编辑器见 `!Tools\Github\huaji1-save-editor`）。
本作换了保护壳：`Data\*.rvdata2` 和存档都被 `System\main.dll` 加密，
v0.2 已经把三个密钥全部逆向出来，所以**现在是真的能用**。

---

## ✨ 能做什么

| 功能 | 状态 |
| --- | --- |
| 自动选密钥解密游戏原档 `save.rvdata2` / `AutoSave\*.rvdata2` | ✅ |
| 解析 Ruby Marshal 4.8（含中文字段名、类对象、对象链接） | ✅ |
| **改存银**（游戏里就叫这个名）/ 步数 / 存档次数 / 战斗次数 | ✅ |
| 改角色等级 / HP / MP / 名字 / **获得经验** / 中文五维属性 | ✅ |
| **背包 4 页×20 格：改数量 / 清空 / 添加物品**（武器、防具同理） | ✅ |
| **物品模板列表 + 搜索 + 双击写进选中格子**（照画迹1） | ✅ |
| **背包体检 + 一键修复**（结构坏 / id 无效 / 数量 0 / 超上限 / 重复格 / **缺运行时内容**） | ✅ |
| **运行时内容（孵化蛋/礼包）自动生成或从同款克隆**，可指定“孵出哪只” | ✅ |
| **召唤兽：等级·气血·魔法·六项资质·忠诚·寿命·成长·五维** + 预设 | ✅ |
| **机器码：看本机 / 存档记录的机器码，一键追加（换机器玩）** | ✅ |
| 改开关 / 变量（带游戏自己的名字注释） | ✅ |
| 数据树浏览任意字段（懒加载 + 全局搜索 + 右键改值 + **中文注释**） | ✅ |
| **防作弊体检**：按游戏规则检查 + 一键修复 + 清除作弊标记 | ✅ |
| **物品计数校验自动同步**（`Change`，AES-ECB 按位加密） | ✅ |
| 写回前自检 + 自动 `*.bak.<时间戳>` 备份 | ✅ |
| **打包成 exe**（`tools\build.py`，自带 32 位宿主，**不弹黑框**） | ✅ |
| 技能 / 装备的可视化编辑 | ⏳ 见 `docs\待解决问题.md` |

### 界面（照画迹1 的编辑器重排，9 个页签）

```
概览 / 快捷修改   存银·步数·存档次数·战斗次数 + 防作弊体检（一键修复/清作弊标记）
                  + 机器码 / 存档绑定（本机机器码、加入存档）
全部解析数据     懒加载数据树 + 全局搜索 + 节点详情（带中文说明）+ 右键改值
角色 / 属性      角色列表；等级/经验/五维；满级(60)/经验+10000/回血/属性+10
背包 / 物品      4 页×20 格；左边格子、右边物品模板（可搜索，双击写进格子）；
                 改数量/清空/本页全部 99/背包体检/一键修复（自动同步计数校验）
召唤兽           等级·气血·魔法·TP·经验·六项资质·忠诚·寿命·成长·五维 + 预设
开关 / 变量      双击即改（带游戏自己的名字：MAP_SCROLL / PLOTING …）
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

:: 3) 跑测试（可选，但建议）—— 11 组
python tools\run_tests.py

:: 4) 开图形界面
python src\xj_viewer.py

:: 5) 打包成 exe（需要 PyInstaller；会自动找仓库旁的 .venv）
python tools\build.py
python tools\build.py --dll-dir     :: 宿主放进 dist\dll\ 子目录
```

打包产物在 `dist\`：`画迹2存档工具v0.4.1.exe` + `XJCodec32.exe`（**必须挨着 exe**，
或放 `dll\` 子目录）+ `使用说明.txt`。`XJ_SELFTEST=1` 跑一次会写
`selftest_result.txt` 自检报告。

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
