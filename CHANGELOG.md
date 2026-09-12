# 更新日志

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
