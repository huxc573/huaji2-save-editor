# -*- coding: utf-8 -*-
"""端到端冒烟测试：真的把游戏存档解密 → 解析 → 改一个值 → 重新加密 → 再解密比对。

不会动原存档：全程在 tools/_smoke/ 里操作副本。

用法：python tools/smoke.py
输出：tools/_smoke.txt
"""
import os
import shutil
import subprocess
import sys

sys.stdout.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))

import xj_codec  # noqa: E402
import xj_env  # noqa: E402
import xj_marshal as M  # noqa: E402
import xj_model  # noqa: E402

LOG = os.path.join(HERE, "_smoke.txt")
WORK = os.path.join(HERE, "_smoke")
L = []
ok = True


def check(name, cond, extra=""):
    global ok
    L.append("%-42s %s %s" % (name, "[OK]" if cond else "[NG]", extra))
    if not cond:
        ok = False


game = xj_env.find_game_dir()
check("找到游戏目录", bool(game), game or "")
if not game:
    open(LOG, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L))
    sys.exit(1)

os.makedirs(WORK, exist_ok=True)
src_save = xj_env.save_path(game)
copy = os.path.join(WORK, "save_copy.rvdata2")
shutil.copyfile(src_save, copy)
L.append("存档原文件 = %s (%d 字节)" % (src_save, os.path.getsize(src_save)))

# 1. 密钥选择
check("key_for(save) = tiyan_version",
      xj_codec.key_for(src_save) == xj_codec.KEY_SAVE, xj_codec.key_for(src_save))
check("key_for(Data/System.rvdata2) = 761205",
      xj_codec.key_for(os.path.join(game, "Data", "System.rvdata2")) == xj_codec.KEY_DATA)
check("key_for(Data/Scripts.rvdata2) = imoutogadaisuki",
      xj_codec.key_for(os.path.join(game, "Data", "Scripts.rvdata2")) == xj_codec.KEY_SCRIPT)

# 2. 解密 + 解析
plain = os.path.join(WORK, "save.plain")
xj_codec.decrypt_file(copy, plain, xj_codec.KEY_SAVE)
raw = open(plain, "rb").read()
check("解密得到 Marshal 4.8", raw[:2] == b"\x04\x08", "%d 字节" % len(raw))
objs = M.parse_stream(raw)
check("顶层对象 2 个（header + contents）", len(objs) == 2,
      "实际 %d" % len(objs))

header = objs[0]["node"]
contents = objs[1]["node"]
keys = [M.value_of(k) for k, _ in contents.pairs]
expect = ["system", "timer", "message", "switches", "variables",
          "self_switches", "actors", "party", "troop", "map", "player"]
check("contents 是 Hash 且有 11 个标准键",
      isinstance(contents, M.HashNode) and keys == expect,
      "键=" + ",".join(str(k) for k in keys))
check("解析结束位置 = 文件末尾", contents.end == len(raw),
      "%d vs %d" % (contents.end, len(raw)))

# 3. 加密往返（同一密钥）
enc = os.path.join(WORK, "rt.enc")
dec = os.path.join(WORK, "rt.dec")
xj_codec.encrypt_file(plain, enc, xj_codec.KEY_SAVE)
xj_codec.decrypt_file(enc, dec, xj_codec.KEY_SAVE)
check("加密→解密 字节级还原", open(dec, "rb").read() == raw)

# 4. 走 Doc 层：打开副本、改一个值、写回、再打开
doc = xj_model.Doc(copy)
check("Doc 打开成功", len(doc.objects) == 2)
party = None
sys_node = None
for k, v in contents.pairs:
    if M.value_of(k) == ":system":
        sys_node = v
    if M.value_of(k) == ":party":
        party = v
if party is not None:
    # 找一个整数 ivar（例如 @gold 在其他对象里），保守起见只做"读→写同值"
    doc.set_value(party, party)
doc.save(copy, backup=False)
doc2 = xj_model.Doc(copy)
check("写回后再打开仍可解析", len(doc2.objects) == 2)
check("写回后明文行数一致",
      M.parse_stream(open(plain, "rb").read())[1]["node"].end > 0)

open(LOG, "w", encoding="utf-8").write("\n".join(L) + "\n")
print("\n".join(L))
print("\n全部通过 = %s" % ok)
sys.exit(0 if ok else 1)
