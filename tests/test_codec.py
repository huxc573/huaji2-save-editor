# -*- coding: utf-8 -*-
"""加解密层回归测试。

* 自检：XJCodec32.exe 用 main.dll 做 加密→解密 是否逐字节一致
* 文件接口：encrypt_file / decrypt_file 的文件名返回与长度规律（+8）
* 环境：能否定位游戏目录与 main.dll

用法： python tests/test_codec.py
"""
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.stdout.reconfigure(errors="replace")

import xj_codec  # noqa: E402
import xj_env  # noqa: E402

OK = 0
NG = 0


def check(cond, msg):
    global OK, NG
    if cond:
        OK += 1
        print("  [OK] %s" % msg)
    else:
        NG += 1
        print("  [NG] %s" % msg)


def main():
    print("== 环境 ==")
    game = xj_env.find_game_dir()
    check(bool(game), "定位到游戏目录：%s" % game)
    mian = xj_env.main_dll(game)
    check(bool(mian), "找到 System/main.dll")
    if not mian:
        print("\n==== 通过 %d, 失败 %d ====" % (OK, NG))
        sys.exit(1)

    check(os.path.exists(xj_codec.HOST),
          "32 位宿主存在（缺失请运行 python tools/build_host.py）")

    print("\n== 导出表 ==")
    info = xj_codec.codec_info(mian)
    for k in ("encryption_file", "decryption_file", "qqeat"):
        check(k in info and info[k] != "<缺失>", "导出 %s = %s" % (k, info.get(k)))

    print("\n== 自检（加密→解密 往返） ==")
    ok, info2, lines = xj_codec.selftest(mian)
    check(ok, "往返一致")

    print("\n== 文件接口 ==")
    tmp = tempfile.mkdtemp(prefix="xj_test_")
    plain = os.path.join(tmp, "plain.bin")
    data = bytes(range(256)) * 4
    open(plain, "wb").write(data)
    enc, n1 = xj_codec.encrypt_file(plain, os.path.join(tmp, "enc.bin"), main_dll=mian)
    check(n1 == len(data) + 8, "密文长度 = 明文 + 8 (%d -> %d)" % (len(data), n1))
    dec, n2 = xj_codec.decrypt_file(enc, os.path.join(tmp, "dec.bin"), main_dll=mian)
    check(n2 == len(data) and open(dec, "rb").read() == data, "解密回原文")

    print("\n== 游戏原档（用逆向出来的密钥真解） ==")
    save = xj_env.save_path(game)
    if save and os.path.exists(save):
        p, n = xj_codec.decrypt_file(save, os.path.join(tmp, "save.out"), main_dll=mian)
        body = open(p, "rb").read()
        check(len(body) == n and body[:2] == b"\x04\x08",
              "存档解密出 Marshal 4.8 (%d 字节)" % n)
        check(xj_codec.key_for(save) == xj_codec.KEY_SAVE,
              "存档自动选到密钥 %s" % xj_codec.KEY_SAVE)
    data_files = ["Data/System.rvdata2", "Data/Actors.rvdata2",
                  "Data/Scripts.rvdata2"]
    for rel in data_files:
        f = os.path.join(game, rel.replace("/", os.sep))
        if not os.path.exists(f):
            continue
        p, n = xj_codec.decrypt_file(f, os.path.join(tmp, os.path.basename(f) + ".out"),
                                     main_dll=mian)
        body = open(p, "rb").read()
        check(body[:2] == b"\x04\x08",
              "%s 解密出 Marshal (%d 字节, key=%s)"
              % (rel, n, xj_codec.key_for(f)))
    # 错误密钥必须给出明确失败（不能悄悄写出垃圾）
    bad = os.path.join(tmp, "bad.bin")
    try:
        xj_codec.decrypt_file(save, bad, key="wrong-key", main_dll=mian)
        check(False, "错误密钥应当报错")
    except xj_codec.CodecError as e:
        check("输出为空" in str(e), "错误密钥被如实拒绝")
    shutil.rmtree(tmp, ignore_errors=True)

    print("\n==== 通过 %d, 失败 %d ====" % (OK, NG))
    sys.exit(1 if NG else 0)


if __name__ == "__main__":
    main()
