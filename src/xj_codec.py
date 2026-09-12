# -*- coding: utf-8 -*-
"""存档 / 数据文件的加解密层。

游戏用 `System\\main.dll`（MPRESS 加壳的自定义分组密码）加解密文件：

    encryption_file(输入路径, 输出路径, 密钥字符串) -> 0/1
    decryption_file(输入路径, 输出路径, 密钥字符串) -> 0/1

实测结论（见 docs/逆向过程.md）：

* 参数是 **UTF-8** 编码的 C 字符串（DLL 内部做 UTF8→GBK 936 转换）；
  传 ANSI 会让中文路径打不开文件。
* **第 3 个参数就是密钥**（反过来用不同密钥试可以自证：输出 0 字节）。
  密钥不对时不报错，而是**输出 0 字节的空文件** —— 这就是最好的“有没有命中”的判断依据。
* 密文 = 8 字节头块 + 明文按 8 字节分组 ECB；密文长度是 8 的倍数，无随机量。
* `System/main.dll` 是 32 位库，64 位 Python 加载不了 →
  随包带一个 32 位宿主 `src/XJCodec32.exe` 中转。

密钥（均已实测验证）见 KEY_761205 / KEY_SCRIPT / KEY_SAVE，`key_for()` 会按文件名猜。
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

# 打包成 exe 后（PyInstaller onefile）：宿主 exe 不在 src/ 里，
# 而是**平铺在 exe 旁边**或放在 dll/ 子目录（DLL 多的时候就丢里面）。
HOST_SUBDIRS = ("", "dll", "DLL", "bin", "依赖DLL")


def app_dir():
    """程序所在目录（打包后 = exe 所在目录）。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return HERE


def host_candidates():
    out = []
    env = os.environ.get("XJ_HOST")
    if env:
        out.append(env)
    for sub in HOST_SUBDIRS:
        out.append(os.path.join(app_dir(), sub, "XJCodec32.exe")
                   if sub else os.path.join(app_dir(), "XJCodec32.exe"))
    out.append(HOST)                      # 源码运行时的 src/XJCodec32.exe
    out.append(os.path.abspath("XJCodec32.exe"))
    return out


def find_host():
    for p in host_candidates():
        if os.path.exists(p):
            return p
    return None


# 明文 Ruby Marshal 4.8 的头
MARSHAL_MAGIC = b"\x04\x08"

# ---------------------------------------------------------------------------
# 密钥表（逆向出来的，都是 main.dll / 游戏脚本里写死的常量）
#   761205        —— Data\*.rvdata2 数据库、System\Game.md5
#   imoutogadaisuki —— Data\Scripts.rvdata2（游戏脚本，藏在 main.dll 里）
#   tiyan_version —— 存档 save.rvdata2 / AutoSave\*.rvdata2（写在游戏脚本 Config::File 里）
# ---------------------------------------------------------------------------
KEY_DATA = "761205"
KEY_SCRIPT = "imoutogadaisuki"
KEY_SAVE = "tiyan_version"
DEFAULT_KEY = KEY_DATA


def key_for(path):
    """根据文件路径猜出该用哪个密钥。"""
    name = os.path.basename(path or "").lower()
    p = (path or "").replace("/", "\\").lower()
    if name == "scripts.rvdata2":
        return KEY_SCRIPT
    if "\\autosave\\" in p or name.startswith("save") and name.endswith(".rvdata2"):
        return KEY_SAVE
    if name == "game.md5":
        return KEY_DATA
    if name.endswith(".rvdata2"):
        return KEY_DATA
    return DEFAULT_KEY


def is_encrypted_size(path):
    """密文长度总是 8 的倍数 —— 粗略判断一个文件是不是被加密过。"""
    try:
        n = os.path.getsize(path)
    except OSError:
        return False
    return n > 0 and n % 8 == 0


class CodecError(Exception):
    """加解密失败。"""


def host_path():
    p = find_host()
    if not p:
        raise CodecError(
            "缺少 32 位宿主 XJCodec32.exe\n"
            "源码运行请先跑： python tools/build_host.py\n"
            "打包运行请确认它和 exe 放在一起（或放 dll/ 子目录）\n"
            "找过这些地方：\n  " + "\n  ".join(host_candidates()[:4]))
    return p


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


def _transform(mode, src, dst, key=None, main_dll=None):
    main_dll = main_dll or xj_env.main_dll()
    if not main_dll:
        raise CodecError("找不到 System/main.dll，请用环境变量 XJ_GAME 指定游戏目录")
    if not os.path.exists(src):
        raise CodecError("找不到输入文件：%s" % src)
    if key is None:
        key = key_for(src)
    rc, txt = _run([mode, main_dll, src, dst, key])
    info, lines = parse_info(txt)
    size = os.path.getsize(dst) if os.path.exists(dst) else 0
    return rc, size, info, lines


ALL_KEYS = [KEY_DATA, KEY_SCRIPT, KEY_SAVE]


def key_candidates(path):
    """要试的密钥顺序：先按文件名猜，再试其它已知密钥。

    为什么不能只按文件名：备份文件叫 `save.rvdata2.bak.20260101-120000`，
    文件名里已经没有 `.rvdata2` 后缀了，猜不出来 —— 但内容一试就知道。
    """
    first = key_for(path)
    return [first] + [k for k in ALL_KEYS if k != first]


def decrypt_file(src, dst=None, key=None, main_dll=None):
    """解密一个文件。成功返回 (明文路径, 字节数)；失败抛 CodecError。

    `key=None` 时按文件名猜密钥，猜不中就**依次试已知密钥**
    （密钥不对时 DLL 只输出 0 字节空文件，所以判定很干净）。
    """
    if dst is None:
        dst = src + ".plain"
    keys = [key] if key else key_candidates(src)
    tried = []
    last = ([], "")
    for k in keys:
        rc, size, info, lines = _transform("decrypt", src, dst, k, main_dll)
        tried.append((k, size))
        last = (lines, k)
        if size > 0:
            _LAST_KEY[os.path.abspath(src)] = k
            return dst, size
    raise CodecError(
        "解密失败：main.dll 输出为空（密钥不对时它就是这么干的）。\n"
        "已试过的密钥：%s\n本文件：%s\n原始输出：\n  %s"
        % (", ".join("%s->%d 字节" % t for t in tried), src,
           "\n  ".join(last[0])))


# 记住"哪个文件用了哪个密钥"，写回时保证用同一个
_LAST_KEY = {}


def key_used_for(path):
    k = _LAST_KEY.get(os.path.abspath(path))
    return k or key_for(path)


def encrypt_file(src, dst=None, key=None, main_dll=None):
    """加密一个文件（用同一个密钥就能还原自己加密过的东西）。

    `key=None` 时会参考 `src` 对应的解密密钥（如果之前解过），
    否则按目标文件名猜。
    """
    if dst is None:
        dst = src + ".enc"
    if key is None:
        key = key_used_for(src) if os.path.abspath(src) in _LAST_KEY \
            else key_for(dst)
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
