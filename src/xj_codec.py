# -*- coding: utf-8 -*-
"""存档 / 数据文件的加解密层。

游戏用 `System\\main.dll`（MPRESS 加壳的自定义分组密码）加解密文件：

    encryption_file(输入路径, 输出路径, 第三参数) -> 0/1
    decryption_file(输入路径, 输出路径, 第三参数) -> 0/1

实测结论（见 docs/保护机制-QQEat.md）：

* 参数是 **UTF-8** 编码的 C 字符串（DLL 内部做 UTF8→GBK 936 转换）；
  传 ANSI 会让中文路径打不开文件。
* 密文 = 8 字节 **定长头块** + 明文按 8 字节分组 **ECB** 加密；
  密文长度 = 明文长度 + 8，且总是 8 的倍数；同明文同位置 -> 同密文（无随机量）。
* `System/main.dll` 是 32 位库，64 位 Python 加载不了 →
  随包带一个 32 位宿主 `src/XJCodec32.exe` 中转。

⚠ **已知限制（v0.1）**：`main.dll` 里的分组密码有**出厂密钥状态**，
本机（未运行游戏进程）下该状态与游戏写文件时使用的状态**不一致**，
所以直接解密游戏自身产生的 `Data\\*.rvdata2` / `save.rvdata2` 会得到 0 字节。
纯 Python 复刻该算法尚未完成，见 `docs/待解决问题.md`。
"""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import xj_env  # noqa: E402

HOST = os.path.join(HERE, "XJCodec32.exe")

# 明文 Ruby Marshal 4.8 的头
MARSHAL_MAGIC = b"\x04\x08"


class CodecError(Exception):
    """加解密失败。"""


def host_path():
    if not os.path.exists(HOST):
        raise CodecError(
            "缺少 32 位宿主 %s\n请先运行： python tools/build_host.py" % HOST)
    return HOST


def _run(args, timeout=300, cwd=None):
    p = subprocess.run([host_path()] + args, capture_output=True,
                       timeout=timeout, cwd=cwd or xj_env.find_game_dir() or HERE)
    txt = (p.stdout or b"").decode("utf-8", "replace") + \
          (p.stderr or b"").decode("utf-8", "replace")
    return p.returncode, txt


def parse_info(text):
    """把宿主输出解析成 dict。支持 `[INFO] k=v` 与 `[INFO] name  value` 两种。"""
    info = {}
    lines = []
    for ln in text.splitlines():
        ln = ln.strip()
        lines.append(ln)
        if not ln.startswith("[INFO] "):
            continue
        body = ln[7:]
        if "=" in body:
            k, v = body.split("=", 1)
            info[k.strip()] = v.strip()
            continue
        parts = body.split()
        if len(parts) >= 2 and (parts[1].startswith("0x") or parts[1].startswith("<")):
            info[parts[0]] = parts[1]
    return info, lines


def codec_info(main_dll=None):
    main_dll = main_dll or xj_env.main_dll()
    if not main_dll:
        raise CodecError("找不到 System/main.dll，请用环境变量 XJ_GAME 指定游戏目录")
    rc, txt = _run(["info", main_dll])
    info, lines = parse_info(txt)
    info["_rc"] = rc
    info["_lines"] = lines
    return info


def selftest(main_dll=None):
    """自检：随机数据 加密→解密 是否逐字节一致。"""
    main_dll = main_dll or xj_env.main_dll()
    if not main_dll:
        raise CodecError("找不到 System/main.dll")
    rc, txt = _run(["selftest", main_dll])
    info, lines = parse_info(txt)
    return rc == 0, info, lines


def _transform(mode, src, dst, key="", main_dll=None):
    main_dll = main_dll or xj_env.main_dll()
    if not main_dll:
        raise CodecError("找不到 System/main.dll，请用环境变量 XJ_GAME 指定游戏目录")
    if not os.path.exists(src):
        raise CodecError("找不到输入文件：%s" % src)
    rc, txt = _run([mode, main_dll, src, dst, key])
    info, lines = parse_info(txt)
    size = os.path.getsize(dst) if os.path.exists(dst) else 0
    return rc, size, info, lines


def decrypt_file(src, dst=None, key="", main_dll=None):
    """解密一个文件。成功返回 (明文路径, 字节数)；失败抛 CodecError。"""
    if dst is None:
        dst = src + ".plain"
    rc, size, info, lines = _transform("decrypt", src, dst, key, main_dll)
    if size <= 0:
        raise CodecError(
            "解密失败：main.dll 输出为空。\n"
            "原因：当前进程里 main.dll 的密钥状态与游戏写文件时不一致（见 docs/待解决问题.md）。\n"
            "原始输出：\n  " + "\n  ".join(lines))
    return dst, size


def encrypt_file(src, dst=None, key="", main_dll=None):
    """加密一个文件（用同一种状态，可用于把自己加密过的文件还原）。"""
    if dst is None:
        dst = src + ".enc"
    rc, size, info, lines = _transform("encrypt", src, dst, key, main_dll)
    if size <= 0:
        raise CodecError("加密失败：main.dll 输出为空。\n  " + "\n  ".join(lines))
    return dst, size


def looks_like_marshal(path, n=2):
    try:
        with open(path, "rb") as f:
            head = f.read(n)
        return head == MARSHAL_MAGIC
    except OSError:
        return False


def load_plaintext(path):
    """读入一个**明文**存档/数据文件（已经解密好的）。

    若文件是密文，会尝试解密到临时文件再读。
    """
    if looks_like_marshal(path):
        return open(path, "rb").read()
    tmp = os.path.join(tempfile.mkdtemp(prefix="xj_"), "plain.bin")
    dst, _ = decrypt_file(path, tmp)
    return open(dst, "rb").read()


def main():
    argv = sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        print("用法：")
        print("  python src/xj_codec.py info")
        print("  python src/xj_codec.py selftest")
        print("  python src/xj_codec.py decrypt <输入> [输出] [第三参数]")
        print("  python src/xj_codec.py encrypt <输入> [输出] [第三参数]")
        return
    mode = argv[0]
    if mode == "info":
        for k, v in codec_info().items():
            if k != "_lines":
                print("  %-12s %s" % (k, v))
        return
    if mode == "selftest":
        ok, info, lines = selftest()
        for ln in lines:
            print("  " + ln)
        print("[OK] 自检通过" if ok else "[NG] 自检失败")
        return
    if mode in ("decrypt", "encrypt"):
        src = argv[1]
        dst = argv[2] if len(argv) > 2 else None
        key = argv[3] if len(argv) > 3 else ""
        try:
            p, n = (decrypt_file if mode == "decrypt" else encrypt_file)(src, dst, key)
            print("[OK] %s -> %s (%d 字节)" % (src, p, n))
        except CodecError as e:
            print("[NG] %s" % e)
            sys.exit(1)
        return
    print("未知命令：%s" % mode)


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")
    main()
