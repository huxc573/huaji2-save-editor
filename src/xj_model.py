# -*- coding: utf-8 -*-
"""存档语义层：打开 → 解析 → 摘要 / 浏览 / 改值 → 写回。

《画迹2：缘起凡尘》是 RPG Maker VX Ace（RGSS301），存档是
`Marshal.dump` 的原始字节流（游戏把 header 和 contents **分两次 dump**
写进同一个文件，所以明文是两个 Marshal 顶层对象拼接）：

    {  :temp => nil }                       <- header
    {  :system => ...  :actors => ... }     <- contents

文件本身用 `main.dll` 的 `decryption_file` / `encryption_file` 加密，
密钥 = `tiyan_version`（见 xj_codec.KEY_SAVE），本模块会自动选密钥。

写回时先做 Marshal 重写 → 再加密，并且会备份 `*.bak.<时间戳>`。
"""
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import xj_backup  # noqa: E402
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
        self.plain_key = None          # 打开密文时用的密钥
        self.dirty = False
        self.structural = False        # 有没有"加减对象"的改动（见 save）：
        #                                标量改动走区间补丁；一旦新增/删除了对象，
        #                                就整档重新序列化（serialize_doc），
        #                                让 Ruby 的对象编号表重新排一遍。
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
            self.plain_key = xj_codec.key_used_for(path)
            self.raw = open(tmp, "rb").read()
            try:
                os.remove(tmp)
            except OSError:
                pass
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
        if self.structural:
            # 结构性改动（往背包塞物品、增删召唤兽…）：整条顶层对象按 Ruby 的规则
            # 重新编号。tools/test_roundtrip.py 证明"什么都不改"时能逐字节还原，
            # 所以除了我们动过的地方，其余字节完全不变。
            new = M.serialize_doc(self.objects)
        else:
            new = self.engine.apply()
        M.parse_stream(new)                    # 编不出来就别写，避免写坏档
        if backup and os.path.exists(path):
            # 备份放进 .huaji2-save-editor 目录，不再散落在存档同目录
            bak_dir = xj_backup.backup_dir(path)
            base = os.path.basename(path)
            bak = os.path.join(
                bak_dir, "%s.bak.%s" % (base, time.strftime("%Y%m%d-%H%M%S")))
            i = 1
            while os.path.exists(bak):
                i += 1
                bak = "%s-%d" % (bak, i) if not bak[-1].isdigit() \
                    else "%s-%d" % (bak.rsplit("-", 1)[0], i)
            shutil.copyfile(path, bak)
        if self.plain:
            open(path, "wb").write(new)
        else:
            tmp = path + ".xj_new"
            open(tmp, "wb").write(new)
            key = getattr(self, "plain_key", None) or xj_codec.key_used_for(path)
            xj_codec.encrypt_file(tmp, path, key)
            os.remove(tmp)
        self.raw = new
        self.engine = xj_edit.PatchEngine(new)
        self.objects = M.parse_stream(new)
        self.dirty = False
        self.structural = False
        return path

    # ------------------------------------------------------------------ 改值
    def set_value(self, node, value):
        xj_edit.PatchEngine.set_scalar(self.engine, node, value)
        self.dirty = True

    def mark_structural(self):
        """标记"动了对象个数"——保存时整档重写（节点值已经是最新的，不用补丁）。"""
        self.structural = True
        self.dirty = True

    def plain_bytes(self, structural=None):
        """按当前树生成明文（不写盘），方便自检 / 预览。"""
        if self.structural if structural is None else structural:
            return M.serialize_doc(self.objects)
        return self.engine.apply()


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
        return "Link(-> #%d)" % getattr(node, 'index', getattr(node, 'idx', -1))
    return getattr(node, 'text', lambda: t)()


def main():
    argv = sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help"):
        print("用法： python src/xj_model.py <存档文件>")
        print("       python src/xj_model.py --default      # 自动定位 <游戏根>\\save.rvdata2")
        return
    path = xj_env.save_path() if argv[0] == "--default" else argv[0]
    if not path:
        print("[NG] 没找到游戏目录/存档，请设 XJ_GAME")
        return
    print("存档 =", path)
    doc = Doc(path)
    print(doc.summary())


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")
    main()
