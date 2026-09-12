# -*- coding: utf-8 -*-
"""存档语义层：打开 → 解析 → 摘要 / 浏览 / 改值 → 写回。

《画迹2：缘起凡尘》是 RPG Maker VX Ace（RGSS301），存档是
`Marshal.dump` 的原始字节流（VX Ace 的 DataManager 会把 header 和 data
分两次 dump 到同一个文件里，因此明文可能由多个 Marshal 顶层对象拼接而成）。

⚠ v0.1 状态：因为 main.dll 的密钥状态问题（见 docs/待解决问题.md），
   本模块默认只能处理**已经解密好的明文**；对密文会给出明确报错。
"""
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import xj_codec  # noqa: E402
import xj_edit  # noqa: E402
import xj_env  # noqa: E402
import xj_marshal as M  # noqa: E402


class Doc(object):
    """一份存档 / 数据文件。"""

    def __init__(self, path=None):
        self.path = path
        self.raw = b""                 # 打开时的字节（明文）
        self.engine = None             # PatchEngine
        self.objects = []              # [{'head':..,'node':..,'links':..}, ...]
        self.plain = False             # 打开时是不是明文
        self.dirty = False
        if path:
            self.load(path)

    # ------------------------------------------------------------------ 打开
    def load(self, path):
        self.path = path
        self.plain = xj_codec.looks_like_marshal(path)
        if self.plain:
            self.raw = open(path, "rb").read()
        else:
            tmp = path + ".xj_plain"
            xj_codec.decrypt_file(path, tmp)
            self.raw = open(tmp, "rb").read()
        self.engine = xj_edit.PatchEngine(self.raw)
        self.objects = M.parse_stream(self.raw)
        self.dirty = False
        return self

    # ------------------------------------------------------------------ 摘要
    def summary(self):
        lines = []
        lines.append("文件      : %s" % self.path)
        lines.append("形态      : %s" % ("明文 Marshal" if self.plain else "密文（已解密）"))
        lines.append("大小      : %d 字节" % len(self.raw))
        lines.append("顶层对象数: %d" % len(self.objects))
        for i, obj in enumerate(self.objects):
            node = obj['node']
            lines.append("  #%-2d 类型=%-8s 字节=%-8d %s" % (
                i, node.type, node.end - node.start, describe(node)))
        return "\n".join(lines)

    def top_level(self):
        return [o['node'] for o in self.objects]

    # ------------------------------------------------------------------ 写回
    def save(self, path=None, backup=True):
        path = path or self.path
        if not path:
            raise ValueError("没有保存路径")
        new = self.engine.apply()
        M.parse_stream(new)                    # 编不出来就别写，避免写坏档
        if backup and os.path.exists(path):
            bak = path + ".bak.%s" % time.strftime("%Y%m%d-%H%M%S")
            shutil.copyfile(path, bak)
        if self.plain:
            open(path, "wb").write(new)
        else:
            tmp = path + ".xj_new"
            open(tmp, "wb").write(new)
            xj_codec.encrypt_file(tmp, path)
            os.remove(tmp)
        self.raw = new
        self.engine = xj_edit.PatchEngine(new)
        self.objects = M.parse_stream(new)
        self.dirty = False
        return path

    # ------------------------------------------------------------------ 改值
    def set_value(self, node, value):
        xj_edit.PatchEngine.set_scalar(self.engine, node, value)
        self.dirty = True


def describe(node):
    """给节点一句人类可读的描述。"""
    t = node.type
    if t == '{':
        return "Hash(%d 项)" % len(node.pairs)
    if t == '[':
        return "Array(%d 项)" % len(node.items)
    if t == 'o':
        return "Object(%s, %d 个 @ivar)" % (node.cls, len(node.ivars))
    if t == '"':
        s = node.data[:40]
        return "String(%d): %s" % (len(node.data),
                                   s.decode('utf-8', 'replace').replace('\n', '\\n'))
    if t == ':':
        return "Symbol(%s)" % node.name
    if t in ('i', 'l'):
        return "Integer(%s)" % node.value
    if t == 'f':
        return "Float(%s)" % node.value
    if t == 'u':
        return "UserDef(%s, %d 字节)" % (getattr(node, 'cls', '?'),
                                         node.end - node.start)
    if t == '@':
        return "Link(-> #%d)" % node.idx
    return getattr(node, 'text', lambda: t)()


def main():
    argv = sys.argv[1:]
    if not argv:
        print("用法： python src/xj_model.py <存档文件>")
        return
    doc = Doc(argv[0])
    print(doc.summary())


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")
    main()
