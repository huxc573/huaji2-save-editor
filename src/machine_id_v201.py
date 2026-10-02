# -*- coding: utf-8 -*-
r"""机器码（`get_hard_disk_character`）的**纯 Python**实现，不依赖 main.dll / 32 位宿主。

⚠ **为什么需要它**：工具原来的读法是调`System\main.dll` 的导出函数
   （经 32 位宿主 `XJCodec32.exe` 中转）。但**内测版 V2.201 的 main.dll 加壳后
   导不出该函数**（实测宿主报 `[ERR] … = 126`，模块都加载不了），
   于是「读取本机机器码」按钮一点就报错。

   而机器码算法本身**跟游戏版本无关**（川确认：机器码算法、伪装器两个版本都一样）
   —— 所以直接用纯 Python 复刻即可，不必碰 dll。

算法（逆向自 `get_hard_disk_character`，RVA 0x0161A5）::

    CreateFileA("\\\\.\\PhysicalDrive0", desiredAccess=0)   # 0 是关键：不需要管理员
      → DeviceIoControl(0x2D1400 = IOCTL_STORAGE_QUERY_PROPERTY)
         → STORAGE_DEVICE_DESCRIPTOR，输出缓冲 **1024 字节**
    CRC32(整个 1024 字节缓冲)  → 十进制字符串

两个必须记住的坑：
  1. **参与 CRC 的是整个 1024 字节缓冲**（含尾部未写满的 0），不是某个字段；
  2. CRC32 参数就是 `zlib.crc32`（poly=0xEDB88320、init=0xFFFFFFFF、xorout=0xFFFFFFFF）。
     反汇编里读到 `init=0x7FFFFFFF`，但**实测init=0xFFFFFFFF 才命中** —— 以实测为准。

本机实测 = `630693299`，与游戏弹框 / 资料包记录的真实码一致。

移植自 `画迹\tools\机器码工具\machine_code_core.py`（那边是带 GUI 的独立工具）。
"""
import ctypes
import os
import struct
import zlib
from ctypes import wintypes

IOCTL_STORAGE_QUERY_PROPERTY = 0x2D1400
STORAGE_DESCRIPTOR_BUFFER_SIZE = 1024

_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
_k32.CreateFileA.restype = ctypes.c_void_p
_k32.CreateFileA.argtypes = [ctypes.c_char_p, wintypes.DWORD, wintypes.DWORD,
                             ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
                             ctypes.c_void_p]
_k32.DeviceIoControl.restype = wintypes.BOOL
_k32.DeviceIoControl.argtypes = [ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p,
                                 wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
                                 ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
_k32.CloseHandle.argtypes = [ctypes.c_void_p]

INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


def query_descriptor(index=0, bufsize=STORAGE_DESCRIPTOR_BUFFER_SIZE):
    """读第 index 块物理盘的 STORAGE_DEVICE_DESCRIPTOR，返回**完整 1024 字节缓冲**。

    返回 None = 这个盘号不存在 / 打不开。
    `desiredAccess=0` 是关键 —— 游戏也是这么开的，**不需要管理员权限**。
    """
    if os.name != "nt":
        return None
    path = ("\\\\.\\PhysicalDrive%d" % index).encode("ascii")
    h = _k32.CreateFileA(path, 0, 3, None, 3, 0, None)   # 0, FILE_SHARE_RW, OPEN_EXISTING
    if not h or h == INVALID_HANDLE_VALUE:
        return None
    try:
        # STORAGE_PROPERTY_QUERY{ PropertyId=0(StorageDeviceProperty),
        #                         QueryType=0(StandardQuery), AdditionalParameters[1] }
        inp = struct.pack("<II8s", 0, 0, b"\0" * 8)
        out = ctypes.create_string_buffer(bufsize)
        ret = wintypes.DWORD(0)
        ok = _k32.DeviceIoControl(ctypes.c_void_p(h), IOCTL_STORAGE_QUERY_PROPERTY,
                                  ctypes.c_char_p(inp), len(inp),
                                  out, bufsize, ctypes.byref(ret), None)
    finally:
        _k32.CloseHandle(ctypes.c_void_p(h))
    if not ok:
        return None
    return out.raw


def machine_code_from_buffer(buf):
    """CRC32(整个输出缓冲) → 十进制字符串。buf 必须是完整 1024 字节。"""
    if not buf:
        return None
    return str(zlib.crc32(buf) & 0xFFFFFFFF)


def read_machine_code():
    """游戏实际用的那个值（0 号物理盘）；取不到抛 RuntimeError。"""
    buf = query_descriptor(0)
    if buf is None:
        raise RuntimeError(
            "打不开 \\\\.\\PhysicalDrive0（没有物理盘，或被安全策略拦了）。\n"
            "这个值游戏自己也是这么取的，取不到就说明本机读不出机器码。")
    return machine_code_from_buffer(buf)


def parse_descriptor(buf):
    """解析 STORAGE_DEVICE_DESCRIPTOR 的常用字段（调试/展示用）。"""
    info = {"size": 0, "vendor": "", "product": "", "revision": "",
            "serial": "", "bus_type": -1, "removable": 0, "device_type": 0}
    if not buf or len(buf) < 36:
        return info

    def cstr(off):
        if not off:
            return ""
        end = buf.find(b"\0", off)
        if end < 0:
            end = len(buf)
        return buf[off:end].decode("latin-1", "replace").strip()

    try:
        _ver, size = struct.unpack_from("<II", buf, 0)
        info["device_type"] = buf[8]
        info["removable"] = buf[10]
        vend_off, prod_off, rev_off, serial_off, bus_type = struct.unpack_from(
            "<IIIII", buf, 12)
        info.update(size=size, bus_type=bus_type, vendor=cstr(vend_off),
                    product=cstr(prod_off), revision=cstr(rev_off),
                    serial=cstr(serial_off))
    except struct.error:
        pass
    return info


if __name__ == "__main__":
    print("本机机器码 =", read_machine_code())
