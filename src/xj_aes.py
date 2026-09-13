# -*- coding: utf-8 -*-
"""纯 Python 的 AES-128-ECB（游戏里 `AES_ECB` 模块的等价实现）。

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
    AES_ECB.set_key('admin_1941344749')       # 脚本第 1142 行

所以改背包数量之后，必须把对应物品的 `security[:items][id]` 计数一起改对，
否则游戏下次"合法获得"这件物品时会发现对不上，把存档标成作弊
（`$game_system.cheated = frame_count`，之后 20 分钟警告、25 分钟 `msgbox + exit`）。

参数（照抄游戏脚本）：
  * 密钥 `admin_1941344749`（16 字节 → AES-128）；
  * 填充 PKCS#7（`pad = 16 - len % 16`，补那么多个 pad 字节）；
  * 加密结果按十六进制小写字符串返回，解密时按 32 个字符一块。

⚠ 这是**算法实现**，不是"抄游戏素材"：AES 是公开标准，密钥来自游戏脚本里
明写的常量（本工具只用来读写自己的存档）。
"""
import os

KEY = b"admin_1941344749"


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


class AES(object):
    """AES-128 单块加解密（state 按列优先，和标准一致）。"""

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

    def _round_keys(self, rnd):
        out = []
        for c in range(4):
            out.append(self.w[rnd * 4 + c])
        return out

    # ---- 基本变换
    @staticmethod
    def _add_round_key(state, rk):
        for c in range(4):
            for r in range(4):
                state[r][c] ^= rk[c][r]

    @staticmethod
    def _sub_bytes(state, table=SBOX):
        for r in range(4):
            for c in range(4):
                state[r][c] = table[state[r][c]]

    @staticmethod
    def _shift_rows(state):
        for r in range(1, 4):
            state[r] = state[r][r:] + state[r][:r]

    @staticmethod
    def _inv_shift_rows(state):
        for r in range(1, 4):
            state[r] = state[r][-r:] + state[r][:-r]

    @staticmethod
    def _mix_columns(state):
        for c in range(4):
            a = [state[r][c] for r in range(4)]
            state[0][c] = _mul(a[0], 2) ^ _mul(a[1], 3) ^ a[2] ^ a[3]
            state[1][c] = a[0] ^ _mul(a[1], 2) ^ _mul(a[2], 3) ^ a[3]
            state[2][c] = a[0] ^ a[1] ^ _mul(a[2], 2) ^ _mul(a[3], 3)
            state[3][c] = _mul(a[0], 3) ^ a[1] ^ a[2] ^ _mul(a[3], 2)

    @staticmethod
    def _inv_mix_columns(state):
        for c in range(4):
            a = [state[r][c] for r in range(4)]
            state[0][c] = (_mul(a[0], 14) ^ _mul(a[1], 11)
                           ^ _mul(a[2], 13) ^ _mul(a[3], 9))
            state[1][c] = (_mul(a[0], 9) ^ _mul(a[1], 14)
                           ^ _mul(a[2], 11) ^ _mul(a[3], 13))
            state[2][c] = (_mul(a[0], 13) ^ _mul(a[1], 9)
                           ^ _mul(a[2], 14) ^ _mul(a[3], 11))
            state[3][c] = (_mul(a[0], 11) ^ _mul(a[1], 13)
                           ^ _mul(a[2], 9) ^ _mul(a[3], 14))

    # ---- 单块
    def encrypt_block(self, block):
        state = [[block[4 * c + r] for c in range(4)] for r in range(4)]
        self._add_round_key(state, self._round_keys(0))
        for rnd in range(1, self.nr):
            self._sub_bytes(state)
            self._shift_rows(state)
            self._mix_columns(state)
            self._add_round_key(state, self._round_keys(rnd))
        self._sub_bytes(state)
        self._shift_rows(state)
        self._add_round_key(state, self._round_keys(self.nr))
        return bytes(state[r][c] for c in range(4) for r in range(4))

    def decrypt_block(self, block):
        state = [[block[4 * c + r] for c in range(4)] for r in range(4)]
        self._add_round_key(state, self._round_keys(self.nr))
        for rnd in range(self.nr - 1, 0, -1):
            self._inv_shift_rows(state)
            self._sub_bytes(state, INV_SBOX)
            self._add_round_key(state, self._round_keys(rnd))
            self._inv_mix_columns(state)
        self._inv_shift_rows(state)
        self._sub_bytes(state, INV_SBOX)
        self._add_round_key(state, self._round_keys(0))
        return bytes(state[r][c] for c in range(4) for r in range(4))


_DEFAULT = [None]


def aes(key=None):
    """拿一个 AES 实例（默认用游戏的密钥）。"""
    if key is None:
        if _DEFAULT[0] is None:
            _DEFAULT[0] = AES(KEY)
        return _DEFAULT[0]
    return AES(key)


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
    # 自测：把自己加密回来
    for d in "0123456789":
        h = encrypt_digit(d)
        back = decrypt_digit(h)
        print("  %s -> %s -> %s %s" % (d, h, back, "[OK]" if back == d else "[NG]"))
