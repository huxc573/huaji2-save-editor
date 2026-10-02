# -*- coding: utf-8 -*-
r"""**内测版 V2.201** 的存档加解密（AES-128-ECB + Zlib），纯 Python、不依赖 32 位宿主。

⚠ 为什么要单独一个模块：**两个游戏版本的存档格式根本不一样**，不是换密钥就能共用
   同一套算法（详见下面「与尝鲜版的区别」）。所以这里独立实现，`codec.py` 负责
   按文件内容自动分流 —— 两条线互不干扰。

存档格式（2026-10-02 由 `!Tools\V2.201-Offline-Server` 资料包确证，并已实测往返）::

    写：marshal(header) + marshal(contents) → Zlib::Deflate → 零填充到16 → AES-128-ECB → save.rvdata2
    读：AES-128-ECB 解密 → data[0]=='x' 则 Inflate → Marshal.load ×2

与尝鲜版（v0.x 线）的区别 —— 三处都是硬的，改不动：

============  ==========================  ==============================
环节尝鲜版（main.dll 自定义 8 字节分组 ECB）  V2.201（内测版，本模块）
============  ==========================  ==============================
分组          8 字节                       16 字节（AES-128 标准）
压缩层        **无**（直接就是 marshal 流）有（Zlib::Deflate/Inflate）
密钥长度      6 字节等长串直接用            15 字符口令**零补齐**到 16 字节
============  ==========================  ==============================

⚠ **15 字符口令必须零补齐**（`153ad4v3fbdgbgd` + 一个 `\0` = 16 字节）。
   直接拿 15 字节当 AES 密钥会报 `ERR_CRYPTO_INVALID_KEYLEN` ——
   这正是「密钥明明对了却解不开」最常见的原因。

密钥出处：游戏脚本 `Config::File::SAVE_FILE_PASSWORD`。
出处记录见 `!Tools\V2.201-Offline-Server\docs\10-客户端本地化-离线启动已打通.md` §15.4。
"""
import os
import zlib

import aes as _game_aes      # 纯 Python AES（项目自带，无外部依赖）

try:  # 有 cryptography 就用（C 扩展，快很多）；没有就退回纯 Python
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    _HAVE_CRYPTO = True
except ImportError:
    _HAVE_CRYPTO = False

#: 存档口令（游戏脚本 Config::File::SAVE_FILE_PASSWORD，15 字符）
SAVE_PASSWORD = "153ad4v3fbdgbgd"

#: 文件名特征：这些名字的东西才会走 V2.201 这条路
_SAVE_HINTS = ("save", "autosave")


def save_key(password=None):
    """存档密钥：口令**零补齐**到 16 字节（AES-128 要 16/24/32）。"""
    p = (password or SAVE_PASSWORD).encode("utf-8")
    return p.ljust(16, b"\0")[:16]


def is_v201_save(path):
    """这个文件**看起来**是不是 V2.201 存档？

    判据：文件名像存档 + 长度 16 的倍数（两种格式都满足，故只能靠名字）。
    真正的确认在 `decode()` —— 那里会验 Inflate 是否成功。

    ⚠ **这只是启发式**，会漏掉改过名的文件（比如手工复制出来的 `xxx.rvdata2`）。
    所以 `codec.decrypt_file` 走的是「先按名字试→ 不行再无条件实测」，
    名字只用来决定**先试哪条路**，不是唯一判据。
    """
    name = os.path.basename(path or "").lower()
    p = (path or "").replace("/", "\\").lower()
    if "\\autosave\\" in p:
        return True
    if not name.endswith(".rvdata2"):
        return False
    stem = name[:-len(".rvdata2")]
    return any(stem == h or stem.startswith(h) for h in _SAVE_HINTS)


def is_v201_candidate(path):
    """值得一试 V2.201 通道吗？（名字像存档，**或**就是在 .rvdata2 里）

    比 `is_v201_save` 宽一档：任何 `.rvdata2` 都值得先试AES+Zlib ——
    反正试不中就回落，不花钱，而漏判的代价是「解不开」这个硬故障。
    """
    if is_v201_save(path):
        return True
    name = os.path.basename(path or "").lower()
    return name.endswith(".rvdata2")


def _aes_ecb(data, key, decrypt):
    """AES-128-ECB 分组加解密，**零填充、无 PKCS#7**。

    ⚠ 刻意不用 `aes.py` 里的 `encrypt()/decrypt()` 高层接口 —— 它们会加/去
    PKCS#7 填充（游戏的 AES_ECB 语义）。存档这层是**零填充**，所以这里直接用
    底层的 `encrypt_block` / `decrypt_block` 自己按 16 字节切。

    优先走 `cryptography`（C 扩展，快）；没装就退回项目自带的纯 Python 实现 ——
    **必须能退回**，因为 GUI 跑在系统 Python 上，那边不一定有 cryptography，
    而源码运行的用户不该被「少个第三方库」卡住。
    """
    if len(data) % 16:
        raise ValueError("AES-128 分组要求 16 的倍数，现在 %d" % len(data))
    if _HAVE_CRYPTO:
        c = Cipher(algorithms.AES(key), modes.ECB())
        ctx = c.decryptor() if decrypt else c.encryptor()
        return ctx.update(data) + ctx.finalize()
    a = _game_aes.AES(key)
    step = a.decrypt_block if decrypt else a.encrypt_block
    return b"".join(step(data[i:i + 16]) for i in range(0, len(data), 16))


def decode(raw, password=None):
    """密文 → 明文（marshal 字节流）。

    ⚠ **不做任何补齐/容错**：解不出来就抛异常，让调用方明确知道「这不是
    V2.201 存档」，而不是悄悄返回半截数据把存档写坏。
    """
    if not raw or len(raw) % 16:
        raise ValueError("V2.201 存档长度必须是 16 的倍数，现在 %d" % len(raw))
    dec = _aes_ecb(raw, save_key(password), True)
    if dec[:1] != b"x":
        # AES-ECB 解出来的第一个字节必须是被压数据的起点 'x'（Zlib 流首字节）
        raise ValueError("密钥不对（AES 解出来首字节是 %r，不是 'x'）" % dec[:1])
    return zlib.decompress(dec)      # zlib 校验不过会自己抛 BadZipFile


def encode(plain, password=None):
    """明文（marshal 字节流）→ 密文。

    零填充到 16 的倍数是**游戏写档原本就在做的事**（AES 分组要求），
    解密侧靠 zlib 头自动忽略尾部零字节，所以填充不影响读取。
    """
    comp = zlib.compress(plain, 6)
    pad = (-len(comp)) % 16
    if pad:
        comp += b"\0" * pad
    return _aes_ecb(comp, save_key(password), False)


def decrypt_file(src, dst=None, password=None):
    """解密 V2.201 存档到文件。返回 `(明文路径, 字节数)`。"""
    with open(src, "rb") as f:
        raw = f.read()
    plain = decode(raw, password)
    if dst is None:
        dst = src + ".plain"
    with open(dst, "wb") as f:
        f.write(plain)
    return dst, len(plain)


def encrypt_file(src, dst=None, password=None):
    """把明文文件加密成 V2.201 存档。返回 `(密文路径, 字节数)`。"""
    with open(src, "rb") as f:
        plain = f.read()
    if plain[:2] != b"\x04\x08":
        raise ValueError("要加密的文件不是 Ruby Marshal 4.8（首两字节 %r）" % plain[:2])
    out = encode(plain, password)
    if dst is None:
        dst = src + ".enc"
    with open(dst, "wb") as f:
        f.write(out)
    return dst, len(out)


def looks_like_v201(path, password=None):
    """真去解一次，成功返回True（比 `is_v201_save` 的名字启发式可靠）。"""
    try:
        decode(open(path, "rb").read(), password)
        return True
    except Exception:
        return False


if __name__ == "__main__":
    import sys
    for p in sys.argv[1:]:
        if os.path.isdir(p):
            for n in sorted(os.listdir(p)):
                if is_v201_save(n):
                    print("%-40s %s" % (n, "OK" if looks_like_v201(os.path.join(p, n)) else "NG"))
        else:
            print(p, looks_like_v201(p))
