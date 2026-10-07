# -*- coding: utf-8 -*-
"""AES-128-ECB（游戏里 `AES_ECB` 模块的等价实现，零第三方依赖也能跑）。

为什么要它：游戏的 `Change` 类（`$game_system.security`）把"累计获得数量"
**逐位数字 AES-ECB 加密**后存进存档：

    class Change
      def initialize(v, c=nil)
        @value = (v||0).to_s.split(//).map{|i| AES_ECB.encrypt(i) }   # 每位一个密文
        @code = c                                                     # 用于自校验的 Ruby 片段
        inspect if v                                                  # 校验 show == eval(@code)
      end
      def show; load.map{|i| AES_ECB.decrypt(i) }.join.to_i; end
    end
    AES_ECB.set_key('admin_alskmcndfj')       # 脚本第 1843 行（V2.201；旧文档写的 1142 行/旧密钥已失效）

所以改背包数量之后，必须把对应物品的 `security[:items][id]` 计数一起改对，
否则游戏下次"合法获得"这件物品时会发现对不上，把存档标成作弊
（`$game_system.cheated = frame_count`，之后 20 分钟警告、25 分钟 `msgbox + exit`）。

参数（照抄游戏脚本）：
  * 密钥 `admin_alskmcndfj`（16 字节 → AES-128；V2.201 实际值）；
  * 填充 PKCS#7（`pad = 16 - len % 16`，补那么多个 pad 字节）；
  * 加密结果按十六进制小写字符串返回，解密时按 32 个字符一块。

⚠ 这是**算法实现**，不是"抄游戏素材"：AES 是公开标准，密钥来自游戏脚本里
明写的常量（本工具只用来读写自己的存档）。

--- 实现：三条路，结果逐字节一致 -------------------------------------------

存档那一层（`save_v201`）一次要解 **4 万多块**（70 KB 密文），纯 Python 走
朴素 S 盒实现时 1 毫秒/块 ⇒ 整档 4.6 秒，载入慢得离谱（2026-10-07 川报
「载入存档太慢」）。所以这里按快慢排三条路，`set_key` 时选一次：

1. **C 扩展**（pycryptodome `Crypto` / `cryptography`）—— 有就用，整段进整段出，
   微秒级；
2. **T 表纯 Python**（本文件）—— 每轮 4 次查表代替 16 次 `_mul`，比朴素快 ~20 倍；
3. 朴素实现已删除（`_mul` 仍保留，用来在 import 时算乘表）。

⚠ 项目**绝不允许**把「没有第三方库」变成「功能缺失」—— 第 1 条只是加速，
   拿掉也能正常读写（见 `docs/开发指南.md`）。所以别把 T 表那条路删了。
"""
KEY = b"admin_alskmcndfj"


# --------------------------------------------------------------------------
# S 盒（AES 标准常量；逆 S 盒由它推出来）
# --------------------------------------------------------------------------
SBOX = [
    0x63, 0x7c, 0x77, 0x7b, 0xf2, 0x6b, 0x6f, 0xc5, 0x30, 0x01, 0x67, 0x2b,
    0xfe, 0xd7, 0xab, 0x76, 0xca, 0x82, 0xc9, 0x7d, 0xfa, 0x59, 0x47, 0xf0,
    0xad, 0xd4, 0xa2, 0xaf, 0x9c, 0xa4, 0x72, 0xc0, 0xb7, 0xfd, 0x93, 0x26,
    0x36, 0x3f, 0xf7, 0xcc, 0x34, 0xa5, 0xe5, 0xf1, 0x71, 0xd8, 0x31, 0x15,
    0x04, 0xc7, 0x23, 0xc3, 0x18, 0x96, 0x05, 0x9a, 0x07, 0x12, 0x80, 0xe2,
    0xeb, 0x27, 0xb2, 0x75, 0x09, 0x83, 0x2c, 0x1a, 0x1b, 0x6e, 0x5a, 0xa0,
    0x52, 0x3b, 0xd6, 0xb3, 0x29, 0xe3, 0x2f, 0x84, 0x53, 0xd1, 0x00, 0xed,
    0x20, 0xfc, 0xb1, 0x5b, 0x6a, 0xcb, 0xbe, 0x39, 0x4a, 0x4c, 0x58, 0xcf,
    0xd0, 0xef, 0xaa, 0xfb, 0x43, 0x4d, 0x33, 0x85, 0x45, 0xf9, 0x02, 0x7f,
    0x50, 0x3c, 0x9f, 0xa8, 0x51, 0xa3, 0x40, 0x8f, 0x92, 0x9d, 0x38, 0xf5,
    0xbc, 0xb6, 0xda, 0x21, 0x10, 0xff, 0xf3, 0xd2, 0xcd, 0x0c, 0x13, 0xec,
    0x5f, 0x97, 0x44, 0x17, 0xc4, 0xa7, 0x7e, 0x3d, 0x64, 0x5d, 0x19, 0x73,
    0x60, 0x81, 0x4f, 0xdc, 0x22, 0x2a, 0x90, 0x88, 0x46, 0xee, 0xb8, 0x14,
    0xde, 0x5e, 0x0b, 0xdb, 0xe0, 0x32, 0x3a, 0x0a, 0x49, 0x06, 0x24, 0x5c,
    0xc2, 0xd3, 0xac, 0x62, 0x91, 0x95, 0xe4, 0x79, 0xe7, 0xc8, 0x37, 0x6d,
    0x8d, 0xd5, 0x4e, 0xa9, 0x6c, 0x56, 0xf4, 0xea, 0x65, 0x7a, 0xae, 0x08,
    0xba, 0x78, 0x25, 0x2e, 0x1c, 0xa6, 0xb4, 0xc6, 0xe8, 0xdd, 0x74, 0x1f,
    0x4b, 0xbd, 0x8b, 0x8a, 0x70, 0x3e, 0xb5, 0x66, 0x48, 0x03, 0xf6, 0x0e,
    0x61, 0x35, 0x57, 0xb9, 0x86, 0xc1, 0x1d, 0x9e, 0xe1, 0xf8, 0x98, 0x11,
    0x69, 0xd9, 0x8e, 0x94, 0x9b, 0x1e, 0x87, 0xe9, 0xce, 0x55, 0x28, 0xdf,
    0x8c, 0xa1, 0x89, 0x0d, 0xbf, 0xe6, 0x42, 0x68, 0x41, 0x99, 0x2d, 0x0f,
    0xb0, 0x54, 0xbb, 0x16,
]
INV_SBOX = [0] * 256
for _i, _v in enumerate(SBOX):
    INV_SBOX[_v] = _i
RCON = [0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1B, 0x36,
        0x6C, 0xD8, 0xAB, 0x4D]


def _xtime(a):
    a <<= 1
    if a & 0x100:
        a = (a ^ 0x1B) & 0xFF
    return a & 0xFF


def _mul(a, b):
    r = 0
    for _ in range(8):
        if b & 1:
            r ^= a
        b >>= 1
        a = _xtime(a)
    return r & 0xFF


# --------------------------------------------------------------------------
# 乘法表 + T 表（import 时算一次，约 2 ms）
#
# T 表把"SubBytes + ShiftRows + MixColumns"整轮压成 4 次查表：
#   TE0[x] = pack(2·S[x], 1·S[x], 1·S[x], 3·S[x])   # 输入字节在**第 0 行**时
#   其余三张按 8 位循环右移（矩阵是循环矩阵，移位同时对齐字节位置与系数列）
# 解密侧同理用逆 S 盒 + 逆 MixColumns 系数（0e/09/0d/0b）。
# --------------------------------------------------------------------------
def _mk_mul(c):
    return [_mul(i, c) for i in range(256)]


MUL2, MUL3 = _mk_mul(2), _mk_mul(3)
MUL9, MUL11, MUL13, MUL14 = _mk_mul(9), _mk_mul(11), _mk_mul(13), _mk_mul(14)


def _rotr32(v, n):
    return ((v >> n) | (v << (32 - n))) & 0xFFFFFFFF


def _pack4(b0, b1, b2, b3):
    return (b0 << 24) | (b1 << 16) | (b2 << 8) | b3


TE0 = [_pack4(MUL2[s], s, s, MUL3[s]) for s in SBOX]
TE1 = [_rotr32(v, 8) for v in TE0]
TE2 = [_rotr32(v, 16) for v in TE0]
TE3 = [_rotr32(v, 24) for v in TE0]

TD0 = [_pack4(MUL14[s], MUL9[s], MUL13[s], MUL11[s]) for s in INV_SBOX]
TD1 = [_rotr32(v, 8) for v in TD0]
TD2 = [_rotr32(v, 16) for v in TD0]
TD3 = [_rotr32(v, 24) for v in TD0]


def _inv_mix_word(x):
    """对一个 32 位轮密钥字做 InvMixColumns（等价逆密码要用，见 FIPS-197 §5.3.5）。"""
    a0, a1, a2, a3 = (x >> 24) & 0xFF, (x >> 16) & 0xFF, (x >> 8) & 0xFF, x & 0xFF
    return _pack4(MUL14[a0] ^ MUL11[a1] ^ MUL13[a2] ^ MUL9[a3],
                  MUL9[a0] ^ MUL14[a1] ^ MUL11[a2] ^ MUL13[a3],
                  MUL13[a0] ^ MUL9[a1] ^ MUL14[a2] ^ MUL11[a3],
                  MUL11[a0] ^ MUL13[a1] ^ MUL9[a2] ^ MUL14[a3])


def _c_backend(key):
    """能用的 C 扩展就返回 `(整段加密, 整段解密)`，否则 None。

    ⚠ 只在这里做一次探测：两条 import 都可能因为「装了但后端坏掉」而抛
      **非 ImportError**（比如缺 libgcc / DLL 加载失败），所以一律 `except Exception`。
    """
    try:
        from Crypto.Cipher import AES as _pc
        ctx = _pc.new(bytes(key), _pc.MODE_ECB)
        return ctx.encrypt, ctx.decrypt
    except Exception:
        pass
    try:
        from cryptography.hazmat.primitives.ciphers import (
            Cipher as _Cipher, algorithms as _alg, modes as _modes)
        ctx = _Cipher(_alg.AES(bytes(key)), _modes.ECB())
        return ctx.encryptor().update, ctx.decryptor().update
    except Exception:
        return None


class AES(object):
    """AES-128/192/256 单块加解密（state 按列优先，和标准一致）。"""

    def __init__(self, key=None):
        self.set_key(key or KEY)

    # ---- 密钥扩展
    def set_key(self, key):
        key = bytes(key)
        if len(key) == 16:
            self.nk, self.nr = 4, 10
        elif len(key) == 24:
            self.nk, self.nr = 6, 12
        elif len(key) == 32:
            self.nk, self.nr = 8, 14
        else:
            raise ValueError("AES 密钥长度必须是 16/24/32 字节，现在是 %d"
                             % len(key))
        w = [list(key[4 * i:4 * i + 4]) for i in range(self.nk)]
        for i in range(self.nk, 4 * (self.nr + 1)):
            t = list(w[i - 1])
            if i % self.nk == 0:
                t = t[1:] + t[:1]                       # RotWord
                t = [SBOX[b] for b in t]                # SubWord
                t[0] ^= RCON[i // self.nk - 1]
            elif self.nk > 6 and i % self.nk == 4:
                t = [SBOX[b] for b in t]
            w.append([w[i - self.nk][j] ^ t[j] for j in range(4)])
        self.w = w
        self._rk = [_pack4(*x) for x in w]              # 轮密钥（每 4 个字一轮）
        self._drk = self._dec_keys()
        self._c = _c_backend(key)

    def _dec_keys(self):
        """等价逆密码的解密轮密钥：轮序倒过来，中间各轮先过一遍 InvMixColumns。"""
        nr, rk = self.nr, self._rk
        out = rk[4 * nr:4 * nr + 4]
        for r in range(1, nr):
            out += [_inv_mix_word(x) for x in rk[4 * (nr - r):4 * (nr - r) + 4]]
        return out + rk[:4]

    # ---- 单块
    def encrypt_block(self, block):
        if self._c:
            return self._c[0](bytes(block))
        return self._enc_block(block)

    def decrypt_block(self, block):
        if self._c:
            return self._c[1](bytes(block))
        return self._dec_block(block)

    # ---- 整段（存档用；C 扩展一次进一次出，纯 Python 才逐块）
    def ecb_encrypt(self, data):
        if self._c:
            return self._c[0](data)
        e = self._enc_block
        return b"".join(e(data[i:i + 16]) for i in range(0, len(data), 16))

    def ecb_decrypt(self, data):
        if self._c:
            return self._c[1](data)
        d = self._dec_block
        return b"".join(d(data[i:i + 16]) for i in range(0, len(data), 16))

    # ---- T 表实现
    def _enc_block(self, block):
        rk = self._rk
        s0 = int.from_bytes(block[0:4], "big") ^ rk[0]
        s1 = int.from_bytes(block[4:8], "big") ^ rk[1]
        s2 = int.from_bytes(block[8:12], "big") ^ rk[2]
        s3 = int.from_bytes(block[12:16], "big") ^ rk[3]
        for r in range(1, self.nr):
            o = 4 * r
            t0 = (TE0[s0 >> 24] ^ TE1[(s1 >> 16) & 0xFF]
                  ^ TE2[(s2 >> 8) & 0xFF] ^ TE3[s3 & 0xFF] ^ rk[o])
            t1 = (TE0[s1 >> 24] ^ TE1[(s2 >> 16) & 0xFF]
                  ^ TE2[(s3 >> 8) & 0xFF] ^ TE3[s0 & 0xFF] ^ rk[o + 1])
            t2 = (TE0[s2 >> 24] ^ TE1[(s3 >> 16) & 0xFF]
                  ^ TE2[(s0 >> 8) & 0xFF] ^ TE3[s1 & 0xFF] ^ rk[o + 2])
            t3 = (TE0[s3 >> 24] ^ TE1[(s0 >> 16) & 0xFF]
                  ^ TE2[(s1 >> 8) & 0xFF] ^ TE3[s2 & 0xFF] ^ rk[o + 3])
            s0, s1, s2, s3 = t0, t1, t2, t3
        o = 4 * self.nr
        u0 = (_pack4(SBOX[s0 >> 24], SBOX[(s1 >> 16) & 0xFF],
                     SBOX[(s2 >> 8) & 0xFF], SBOX[s3 & 0xFF])) ^ rk[o]
        u1 = (_pack4(SBOX[s1 >> 24], SBOX[(s2 >> 16) & 0xFF],
                     SBOX[(s3 >> 8) & 0xFF], SBOX[s0 & 0xFF])) ^ rk[o + 1]
        u2 = (_pack4(SBOX[s2 >> 24], SBOX[(s3 >> 16) & 0xFF],
                     SBOX[(s0 >> 8) & 0xFF], SBOX[s1 & 0xFF])) ^ rk[o + 2]
        u3 = (_pack4(SBOX[s3 >> 24], SBOX[(s0 >> 16) & 0xFF],
                     SBOX[(s1 >> 8) & 0xFF], SBOX[s2 & 0xFF])) ^ rk[o + 3]
        return (u0.to_bytes(4, "big") + u1.to_bytes(4, "big")
                + u2.to_bytes(4, "big") + u3.to_bytes(4, "big"))

    def _dec_block(self, block):
        drk = self._drk
        s0 = int.from_bytes(block[0:4], "big") ^ drk[0]
        s1 = int.from_bytes(block[4:8], "big") ^ drk[1]
        s2 = int.from_bytes(block[8:12], "big") ^ drk[2]
        s3 = int.from_bytes(block[12:16], "big") ^ drk[3]
        for r in range(1, self.nr):
            o = 4 * r
            # InvShiftRows 把第 r 行往右移 r 列 ⇒ 输出第 0 列的行 r 取自输入列 (4-r)%4
            t0 = (TD0[s0 >> 24] ^ TD1[(s3 >> 16) & 0xFF]
                  ^ TD2[(s2 >> 8) & 0xFF] ^ TD3[s1 & 0xFF] ^ drk[o])
            t1 = (TD0[s1 >> 24] ^ TD1[(s0 >> 16) & 0xFF]
                  ^ TD2[(s3 >> 8) & 0xFF] ^ TD3[s2 & 0xFF] ^ drk[o + 1])
            t2 = (TD0[s2 >> 24] ^ TD1[(s1 >> 16) & 0xFF]
                  ^ TD2[(s0 >> 8) & 0xFF] ^ TD3[s3 & 0xFF] ^ drk[o + 2])
            t3 = (TD0[s3 >> 24] ^ TD1[(s2 >> 16) & 0xFF]
                  ^ TD2[(s1 >> 8) & 0xFF] ^ TD3[s0 & 0xFF] ^ drk[o + 3])
            s0, s1, s2, s3 = t0, t1, t2, t3
        o = 4 * self.nr
        u0 = (_pack4(INV_SBOX[s0 >> 24], INV_SBOX[(s3 >> 16) & 0xFF],
                     INV_SBOX[(s2 >> 8) & 0xFF], INV_SBOX[s1 & 0xFF])) ^ drk[o]
        u1 = (_pack4(INV_SBOX[s1 >> 24], INV_SBOX[(s0 >> 16) & 0xFF],
                     INV_SBOX[(s3 >> 8) & 0xFF], INV_SBOX[s2 & 0xFF])) ^ drk[o + 1]
        u2 = (_pack4(INV_SBOX[s2 >> 24], INV_SBOX[(s1 >> 16) & 0xFF],
                     INV_SBOX[(s0 >> 8) & 0xFF], INV_SBOX[s3 & 0xFF])) ^ drk[o + 2]
        u3 = (_pack4(INV_SBOX[s3 >> 24], INV_SBOX[(s2 >> 16) & 0xFF],
                     INV_SBOX[(s1 >> 8) & 0xFF], INV_SBOX[s0 & 0xFF])) ^ drk[o + 3]
        return (u0.to_bytes(4, "big") + u1.to_bytes(4, "big")
                + u2.to_bytes(4, "big") + u3.to_bytes(4, "big"))


_INSTANCES = {}


def aes(key=None):
    """拿一个 AES 实例（默认用游戏的密钥）。按密钥缓存，重复调用不重算轮密钥。"""
    k = KEY if key is None else bytes(key)
    a = _INSTANCES.get(k)
    if a is None:
        a = _INSTANCES[k] = AES(k)
    return a


# --------------------------------------------------------------------------
# 和游戏 AES_ECB 一致的高层接口
# --------------------------------------------------------------------------
def pkcs7(data):
    pad = 16 - len(data) % 16
    return data + bytes([pad]) * pad


def encrypt(data, key=None):
    """和 `AES_ECB.encrypt(str)` 一样：返回**十六进制字符串**。"""
    if isinstance(data, str):
        data = data.encode("utf-8")
    a = aes(key)
    data = pkcs7(data)
    out = []
    for i in range(0, len(data), 16):
        out.append(a.encrypt_block(data[i:i + 16]).hex())
    return "".join(out)


def decrypt(hexstr, key=None):
    """和 `AES_ECB.decrypt(hex)` 一样：返回 **bytes**（去掉 PKCS#7 填充）。"""
    if isinstance(hexstr, bytes):
        hexstr = hexstr.decode("ascii")
    a = aes(key)
    raw = bytes.fromhex(hexstr)
    out = []
    for i in range(0, len(raw), 16):
        out.append(a.decrypt_block(raw[i:i + 16]))
    data = b"".join(out)
    if data:
        pad = data[-1]
        if 1 <= pad <= 16 and data[-pad:] == bytes([pad]) * pad:
            data = data[:-pad]
    return data


def encrypt_digit(d, key=None):
    """加密一位数字字符（游戏就是这么一位一位存的）。"""
    return encrypt(str(d), key)


def decrypt_digit(hexstr, key=None):
    """解密一位数字，返回 '0'..'9'；不是数字位就返回 None。"""
    try:
        s = decrypt(hexstr, key)
    except Exception:
        return None
    if len(s) == 1 and 0x30 <= s[0] <= 0x39:
        return s.decode("ascii")
    return None


def decrypt_token(hexstr, key=None):
    """解密一位字符：数字 '0'..'9' 或负号 '-'（记账可能为负）；否则 None。"""
    try:
        s = decrypt(hexstr, key)
    except Exception:
        return None
    if len(s) == 1 and (0x30 <= s[0] <= 0x39 or s[0] == 0x2D):
        return s.decode("ascii")
    return None


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(errors="replace")
    n = [0, 0]                              # [OK, NG]

    def ck(ok, msg):
        n[0 if ok else 1] += 1
        print("  %s %s" % ("[OK]" if ok else "[NG]", msg))

    # 1) 标准已知答案（FIPS-197 附录 B）—— 不依赖自己的实现互证
    ck(AES(bytes(range(16))).encrypt_block(
        bytes.fromhex("00112233445566778899aabbccddeeff")).hex()
       == "69c4e0d86a7b0430d8cdb78070b4c55a", "FIPS-197 AES-128 加密向量")
    ck(AES(bytes(range(16))).decrypt_block(
        bytes.fromhex("69c4e0d86a7b0430d8cdb78070b4c55a")).hex()
       == "00112233445566778899aabbccddeeff", "FIPS-197 AES-128 解密向量")
    # 密钥长度 24/32 也要活着（虽然游戏只用 128）
    for klen in (24, 32):
        a = AES(bytes(range(klen)))
        ck(a.decrypt_block(a.encrypt_block(b"0123456789abcdef"))
           == b"0123456789abcdef", "AES-%d 往返" % (klen * 8))
    # 2) 随机往返（T 表 / C 扩展两条路都过一遍）
    import os as _os
    blocks = [bytes(_os.urandom(16)) for _ in range(500)]
    for name, inst in (("T 表", AES(b"0123456789abcdef")),):
        inst._c = None                      # 强制走纯 Python
        ct = b"".join(inst.encrypt_block(b) for b in blocks)
        ck(all(inst.decrypt_block(c) == b for b, c in
               zip(blocks, [ct[i:i + 16] for i in range(0, len(ct), 16)])),
           "%s 500 块往返" % name)
    inst = aes()
    if inst._c is not None:
        ck(all(inst.decrypt_block(inst.encrypt_block(b)) == b for b in blocks),
           "C 扩展 500 块往返")
        print("  [--] C 扩展可用")
    else:
        print("  [--] 没有 C 扩展，走 T 表")
    # 3) 和游戏 AES_ECB 一致（自加密回来）
    for d in "0123456789":
        h = encrypt_digit(d)
        ck(decrypt_digit(h) == d, "数字 %s 往返" % d)
    # 4) 钉子：**游戏自己写的账**（AutoSave\_save.rvdata2 的 gold 账，值 13790）。
    # 密钥一旦被改错（历史上就是照脚本里作者 QQ 号猜的 `admin_1941344749`），
    # 这几位立刻解不出来 —— 用来防「密钥回退」。取样来源：script00:1843 的 key。
    for h, want in (("4dea3f29581a67232acee5e599d13810", "1"),
                    ("2f8eabf1a03916708c53f1ec416d762a", "3"),
                    ("7520b37734999c73b6003684e49d8557", "7"),
                    ("22a3126a7d9fdb5daec2b75da28698c3", "9"),
                    ("e7e794b9942d4a9e8191727faa25d465", "0")):
        ck(decrypt_digit(h) == want, "真档样本 %s… → %s" % (h[:8], want))
    print("== 汇总 [OK]=%d [NG]=%d ==" % (n[0], n[1]))
    sys.exit(1 if n[1] else 0)
