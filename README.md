# 画迹2 存档工具（huaji2-save-editor）

> 针对 RPG Maker VX Ace 游戏《画迹2：缘起凡尘》（尝鲜版）的**存档工具**。
> 是《画迹1：落日情缘》存档工具（`huaji1-save-editor`）的迭代产品 ——
> 但引擎从 RMXP 换成了 VX Ace，加密也从 `tp.dll` 换成了 `System\main.dll`
> （QQEat / MPRESS 加壳），**两者不通用**。
>
> 作者 **[@huxc573](https://github.com/huxc573)** · 开源协议 **MIT** · 当前版本 **v0.1**

![platform](https://img.shields.io/badge/platform-Windows%20x64-lightgrey)
![python](https://img.shields.io/badge/python-3.10%2B-blue)
![license](https://img.shields.io/badge/license-MIT-green)

---

## ⚠ v0.1 的实话

这是**第一版脚手架 + 逆向成果**，还不是能直接改存档的成品：

| | 状态 |
|---|---|
| 逆向：引擎 / 存档位置 / 加密容器形态 / DLL 导出接口 | ✅ 已完成（见 `docs/存档格式.md`） |
| 32 位编解码宿主，能调通 `main.dll` 的加解密 | ✅ 已完成，往返自检通过 |
| Ruby Marshal（VX Ace）解析 / 区间补丁 / 序列化 | ✅ 已完成，回归测试通过 |
| 界面（概览 / 数据树 / 说明） | ✅ 骨架可用 |
| **直接解密游戏原来的密文存档** | ❌ **未完成**：`main.dll` 的密钥状态需继续逆向，见 `docs/待解决问题.md` |

也就是说：**现在能打开"已经解密好的明文存档"，能改、能写回；
但还不能解开游戏自己写的 `save.rvdata2`。** 这是 v0.2 的第一优先级。

---

## 目录

* [它是什么 / 能做什么](#它是什么--能做什么)
* [快速开始](#快速开始)
* [运行测试](#运行测试)
* [仓库结构](#仓库结构)
* [文档](#文档)
* [与画迹1工具的差异](#与画迹1工具的差异)
* [免责声明](#免责声明)

---

## 它是什么 / 能做什么

《画迹2：缘起凡尘》是 RPG Maker **VX Ace**（RGSS301）游戏：

```
<游戏根>\save.rvdata2                  ← 默认存档（密文）
<游戏根>\AutoSave\save00..29.rvdata2   ← 自动存档（密文）
<游戏根>\System\main.dll               ← 加密/防作弊库（MPRESS 加壳）
<游戏根>\Data\main.rvdata2             ← 明文引导脚本，只做一件事：
                                          Win32API.new('System/main','qqeat','v','v').call
```

工具做的事：

* 用 `main.dll` 自己的 `encryption_file` / `decryption_file` 加解密文件
  （64 位 Python 加载不了 32 位 DLL，所以带了一个 32 位宿主 `XJCodec32.exe` 中转）；
* 解析解密后的 Ruby Marshal 明文，树形浏览、改标量、区间补丁写回
  （**不会破坏 `@N` 对象链接**，这是 huaji1 时期踩过的大坑）；
* 自检 + 环境诊断，出错时说清原因而不是写坏存档。

---

## 快速开始

1. **依赖**：Windows 10/11、Python 3.10+、.NET Framework 4.x（Windows 自带，提供 `csc.exe`）。
2. **编译 32 位宿主**（仓库里已带编译好的，需要重编时用）：

   ```powershell
   python tools/build_host.py
   ```
3. **告诉脚本游戏在哪**（不设也能自动找到，找不到就设）：

   ```powershell
   $env:XJ_GAME = "D:\Life\Game\Local\MH\画迹\【画迹2：缘起凡尘】 [尝鲜版]"
   ```
4. **体检**：

   ```powershell
   python src/xj_codec.py info
   python src/xj_codec.py selftest      # 加密→解密 往返自检
   ```
5. **开界面**：

   ```powershell
   python src/xj_viewer.py
   ```

   v0.1 里"打开存档"对密文会明确报错（见上表），
   可以先用【打开文件…】打开明文样本（例如
   `Logs\Battle\<时间>\Battle.bt2`）体验浏览与修改。
6. **命令行加解密**（对自己加密过的文件有效）：

   ```powershell
   python src/xj_codec.py encrypt 某个明文.bin 输出.bin
   python src/xj_codec.py decrypt 输出.bin 还原.bin
   ```

---

## 运行测试

```powershell
python tools/build_host.py          # 先编宿主
python tests/test_marshal.py        # Marshal 解析/编码/边界
python tests/test_codec.py          # 加解密往返 + 环境 + 导出表（含"原档预期失败"检查）
python tests/test_model.py          # 语义层 / 区间补丁
python tests/test_gui.py            # 界面冒烟（无图形环境会自动跳过）
```

测试**只读**游戏目录里的文件；写回测试都在系统临时目录里做。

---

## 仓库结构

```
huaji2-save-editor/
├─ src/
│  ├─ xj_viewer.py        tkinter 界面（概览 / 数据树 / 说明）
│  ├─ xj_model.py         存档语义层 Doc：打开 / 摘要 / 改值 / 写回
│  ├─ xj_edit.py          区间补丁写入引擎（只改动过的字节）
│  ├─ xj_marshal.py       Ruby Marshal 4.8 解析/序列化（VX Ace 语义）
│  ├─ xj_codec.py         加解密层：驱动 XJCodec32.exe 调 main.dll
│  ├─ xj_env.py           定位游戏目录 / 存档 / main.dll
│  ├─ xj_codec32.cs       32 位宿主源码（XJCodec32.exe）
│  └─ XJCodec32.exe       编译好的 32 位宿主（随包分发）
├─ tools/
│  └─ build_host.py       用 csc.exe 编译 32 位宿主
├─ tests/                 独立回归测试（自带断言与统计，退出码即结果）
├─ probes/                逆向探针（本次全过程，可复现所有结论）
├─ docs/
│  ├─ 存档格式.md         格式结论（引擎 / 容器 / ECB / 导出表 / UTF-8 坑）
│  ├─ 逆向过程.md         时间线式记录 + 踩坑清单
│  └─ 待解决问题.md       v0.2 工作清单（密钥状态怎么继续挖）
├─ 使用说明.txt
├─ CHANGELOG.md
├─ LICENSE                MIT（只覆盖本仓库自己写的代码）
├─ NOTICE.md              授权范围与例外
└─ README.md
```

---

## 文档

| 文档 | 内容 |
|---|---|
| [`docs/存档格式.md`](docs/存档格式.md) | 引擎、存档位置、哪些文件加密、ECB 形态实测、`main.dll` 导出表与调用约定 |
| [`docs/逆向过程.md`](docs/逆向过程.md) | 解壳、差分实验、UTF-8 大坑、Windows 中文路径工具链备忘 |
| [`docs/待解决问题.md`](docs/待解决问题.md) | 密钥状态问题、已排除的假设、下一步路线（含风险提示） |

---

## 与画迹1工具的差异

| 项 | 画迹1（huaji1-save-editor） | 画迹2（本仓库） |
|---|---|---|
| 引擎 | RMXP（RGSS102J/103J） | **VX Ace**（RGSS301） |
| 存档位置 | `Audio\BGM\sy.ogg`（伪装成 BGM） | **`<根>\save.rvdata2`**（另有 `AutoSave\`） |
| 容器 | `0D 0F 3E 03` + 长度 + zlib(密文) | **没有容器**，直接是密文 |
| 加密 | `tp.dll` 的 `DS1/DS2`，口令 `xjy.11`，位置相关 | `System\main.dll`（QQEat，MPRESS），**ECB、位置无关、无口令** |
| 解密方式 | 直接调 `tp.dll`（成功） | 调 `main.dll`（能加解密，但**密钥状态不对**，v0.2 解决） |
| 复用 | — | `xj_marshal.py` 直接继承，其余重写 |

---

## 免责声明

* 本工具只操作**你自己机器上**的游戏存档。修改存档前请**自行备份**。
* 仓库里**不包含**游戏的任何素材、脚本或 `main.dll` ——
  宿主运行时从你本机的游戏目录里加载它。
* 请勿把本工具用于商业用途或在线排行等破坏公平性的场景。
