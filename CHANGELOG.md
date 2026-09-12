# 更新日志

## v0.1 — 2026-09-12

**定位**：脚手架 + 逆向成果版。第一版，先把"摸清对手"这件事做完。

### 新增

* **逆向结论**
  * 引擎确认为 RPG Maker VX Ace（RGSS301）；
  * 存档位置确认为 `<游戏根>\save.rvdata2`，另有 `AutoSave\save00..29.rvdata2`；
  * 找出保护体系：`Data\main.rvdata2`（明文）只有一句
    `Win32API.new('System/main','qqeat','v','v').call`，
    真正干活的是 MPRESS 加壳的 `System\main.dll`；
  * 密文形态实测：**8 字节定长头块 + ECB 分组**，密文长度 = 明文 + 8，
    确定性、无随机 IV（同明文同位置 → 同密文）；
  * 解出 `main.dll` 的导出表（36 个）与调用约定，包括
    `encryption_file/decryption_file`（3 参）、`encryption_buff/decryption_buff`（2 参）、
    `init_key/dispose_key/qqeat/get_md5/...`；
  * **关键坑**：DLL 期望的参数是 **UTF-8**（内部 `UTF8→GBK 936`），
    传 ANSI 会导致中文路径静默失败。
* **代码**
  * `src/xj_codec32.cs` + `src/XJCodec32.exe`：32 位宿主，
    通过 `LoadLibraryEx` + `GetProcAddress` 调用 `main.dll`；
    支持 `info / decrypt / encrypt / selftest`。
  * `tools/build_host.py`：用系统自带 `csc.exe` 一键编译宿主。
  * `src/xj_codec.py`：加解密层（自检、单文件加解密、明文直读）。
  * `src/xj_marshal.py`：Ruby Marshal 4.8 解析/序列化（从 huaji1 继承并适配）。
  * `src/xj_edit.py`：区间补丁写入引擎（只重编码改过的字段，
    同一节点重复修改以最后一次为准）。
  * `src/xj_model.py`：存档语义层（打开 / 摘要 / 改值 / 写回 + 自动备份）。
  * `src/xj_viewer.py`：tkinter 界面（概览 / 数据树 / 说明）。
  * `src/xj_env.py`：游戏目录 / `main.dll` / 存档定位。
* **文档**：`docs/存档格式.md`、`docs/逆向过程.md`、`docs/待解决问题.md`。
* **测试**：`tests/test_marshal.py`、`test_codec.py`、`test_model.py`、`test_gui.py`。
* **探针**：`probes/` 下 22 个可复现脚本，覆盖格式判定、解壳、差分实验、
  导出表分析、密钥候选爆破等。

### 已知限制（v0.2 目标）

* ❌ **还不能直接解密游戏原来的密文存档**：`main.dll` 里分组密码的"出厂密钥状态"
  与游戏进程内写文件时的状态不一致，外部调用时 `decryption_file` 会输出 0 字节。
  已排除：第三参数是口令、`init_key`、缺 `init()`、环境问题、标准算法。
  继续挖的路线见 `docs/待解决问题.md`。
* 因为上一条，界面目前只能打开**已经解密好的明文**文件。
