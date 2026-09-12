# 画迹2 存档修改器（huaji2-save-editor）

> 《画迹2：缘起凡尘》[尝鲜版] 的存档编辑器 —— 解密 → 解析 → 改 → 加密写回，
> 连游戏自带的**防作弊校验**一起修好。
>
> 作者 **[@huxc573](https://github.com/huxc573)** · 开源协议 **MIT** · 当前版本 **v0.2**

`huaji1-save-editor` 的迭代作品（画迹1 的编辑器见 `!Tools\Github\huaji1-save-editor`）。
本作换了保护壳：`Data\*.rvdata2` 和存档都被 `System\main.dll` 加密，
v0.2 已经把三个密钥全部逆向出来，所以**现在是真的能用**。

---

## ✨ 能做什么

| 功能 | 状态 |
| --- | --- |
| 自动选密钥解密游戏原档 `save.rvdata2` / `AutoSave\*.rvdata2` | ✅ |
| 解析 Ruby Marshal 4.8（含中文字段名、类对象、对象链接） | ✅ |
| **改金钱**（自动同步防作弊校验和） | ✅ |
| 改角色等级 / HP / MP / 名字 | ✅ |
| 改开关 / 变量 | ✅ |
| 数据树浏览任意字段，标量就地改（区间补丁，不动其它字节） | ✅ |
| **一键检查并修复 `Lock` 防作弊校验** | ✅ |
| 写回前自检 + 自动 `*.bak.<时间戳>` 备份 | ✅ |
| 数据文件（System/Actors/Items/Map…）解密查看 | ✅ |
| 物品 / 装备增删、批量操作、打包成 exe | ⏳ 见 `docs\待解决问题.md` |

---

## 🚀 快速开始

```bat
:: 1) 需要 Python 3.8+（64 位），不用装任何第三方库
:: 2) 编译 32 位宿主（仓库里已经带了一份编译好的，改过 .cs 才需要重编）
python tools\build_host.py

:: 3) 跑测试（可选，但建议）
python tests\test_marshal.py
python tests\test_codec.py
python tests\test_model.py
python tests\test_gui.py
python tools\smoke.py
python tools\test_save_layer.py

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
python tools\decrypt_all.py      :: 把各文件解密到 tools\_plain\
```

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
  xj_viewer.py      tkinter 界面（概览 / 快捷修改 / 数据树 / 说明）
  xj_save.py        存档语义层（金钱、角色、开关变量、Lock 防作弊校验修复）
  xj_model.py       打开/摘要/写回
  xj_edit.py        区间补丁 + 自包含序列化
  xj_marshal.py     Ruby Marshal 4.8 解析 / 序列化
  xj_codec.py       加解密（调用 32 位宿主，自动选密钥）
  xj_codec32.cs     32 位宿主源码（LoadLibrary + 调用 main.dll 导出）
  XJCodec32.exe     编译产物
  xj_env.py         游戏目录 / 存档路径定位
tests\              test_marshal / test_codec / test_model / test_gui
tools\              逆向与验证脚本（爆破、导出脚本、hexdump、总体验证…）
docs\
  存档格式.md        文件位置 / 密钥 / 结构 / Lock 校验 / 解析的坑
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
