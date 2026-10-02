# -*- coding: utf-8 -*-
r"""**内测版 V2.201** 的 Data 表解密（RC4，纯 Python、无外部依赖）。

⚠ 为什么和尝鲜版不是一套：尝鲜版的 `Data\*.rvdata2` 用 `main.dll` 的
   8 字节分组 ECB（密钥 `761205`）；V2.201 换成了**按文件名派生的 RC4**，
   完全不同的算法。所以这里独立实现，`codec` 负责自动分流。

算法（来自游戏脚本原文，出处见
`!Tools\V2.201-Offline-Server\docs\09-客户端本地化路线-实测结论与方案评估.md` §7）::

    pwd  = '9KQ1L0PWRESZV7HM' + Zlib.crc32(File.basename(name)).to_s(36)[0..12]
    真正生效的 = pwd[-16..-1]        # ⚠ 是**后** 16 个字符，不是前 16 个
    数据       = Base64.read(文件)   # IO.binread 后直接 RC4，没有 Base64 层

实测（2026-10-02）：`Data` 下 **403 / 403** 个表全部解出 `\x04\x08` Marshal 头。

⚠ **两个必须记住的坑**
   1. `crc32` 取的是**带扩展名**的文件名（`Actors.rvdata2`），不是 `Actors`；
   2. 密钥取 `[-16:]`（**后** 16），不是 `[:16]`（前 16）——
      前 16 恒等于 `"9KQ1L0PWRESZV7HM"` 这段常量，**对所有文件都一样**，
      于是谁也解不开。这正是第一次尝试失败的原因（看起来对、其实全错）。

例外只有两个（实测确认，**不要**用本模块去解）：
    `main.rvdata2`   —— 本身是明文脚本骨架（662B 真引导段 + 填充）
    `Scripts.rvdata2` —— RC4 也解不开，内容是空壳脚本档
"""
import os
import zlib

#: 派生用的常量前缀（游戏脚本里写死）
KEY_BASE = "9KQ1L0PWRESZV7HM"

#: 不能用本模块解的两个文件
EXCLUDE = ("main.rvdata2", "Scripts.rvdata2")

#: Marshal 4.8 的头，用来判定「解对了」
MARSHAL_MAGIC = b"\x04\x08"


def _b36(n):
    """Ruby `Integer#to_s(36)`：0-9a-z，小写，**无前导零**。"""
    if n == 0:
        return "0"
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    out = []
    while n:
        n, r = divmod(n, 36)
        out.append(digits[r])
    return "".join(reversed(out))


def key_for(name):
    """按**文件名**（带扩展名）派生 RC4 密钥。"""
    base = os.path.basename(name or "").replace("\\", "/").split("/")[-1]
    crc = zlib.crc32(base.encode("utf-8")) & 0xFFFFFFFF
    return (KEY_BASE + _b36(crc)[0:13])[-16:]


def rc4(data, key):
    """RC4 加解密（同一函数对称，用两遍即可）。"""
    kb = key.encode("utf-8") if isinstance(key, str) else key
    s = list(range(256))
    j = 0
    for i in range(256):
        j = (j + s[i] + kb[i % len(kb)]) % 256
        s[i], s[j] = s[j], s[i]
    out = bytearray(len(data))
    i = j = 0
    for n, b in enumerate(data):
        i = (i + 1) % 256
        j = (j + s[i]) % 256
        s[i], s[j] = s[j], s[i]
        out[n] = b ^ s[(s[i] + s[j]) % 256]
    return bytes(out)


def decrypt(data, name):
    """按文件名解密一个表。"""
    return rc4(data, key_for(name))


def looks_like_table(name):
    """这个名字该不该走本模块（排除两个特例）。"""
    if not name.lower().endswith(".rvdata2"):
        return False
    return os.path.basename(name) not in EXCLUDE


def decrypt_file(src, dst=None, name=None):
    """解密一个 Data 表到文件。返回 `(明文路径, 字节数)`。"""
    with open(src, "rb") as f:
        raw = f.read()
    plain = decrypt(raw, name or os.path.basename(src))
    if dst is None:
        dst = src + ".plain"
    with open(dst, "wb") as f:
        f.write(plain)
    return dst, len(plain)


if __name__ == "__main__":
    import sys
    # 用法：python data_v201.py <Data目录>
    d = sys.argv[1] if len(sys.argv) > 1 else r"D:\Life\Game\Local\MH\画迹\【画迹2】内测版\Data"
    names = [n for n in sorted(os.listdir(d))
             if n.lower().endswith(".rvdata2") and n not in EXCLUDE]
    hit = 0
    for n in names:
        with open(os.path.join(d, n), "rb") as f:
            if decrypt(f.read(), n)[:2] == MARSHAL_MAGIC:
                hit += 1
            else:
                print("NG  %s" % n)
    print("命中 %d / %d" % (hit, len(names)))
