# -*- coding: utf-8 -*-
"""文档树：打开 → 解析 → 摘要 / 浏览 / 改值 → 写回。

与游戏无关的通用一层（下面两层都建在它上面）：
    doctree.py（本文档树） → save.py（存档语义） → game.py（游戏内容）

《画迹2：缘起凡尘》是 RPG Maker VX Ace（RGSS301），存档是
`Marshal.dump` 的原始字节流（游戏把 header 和 contents **分两次 dump**
写进同一个文件，所以明文是两个 Marshal 顶层对象拼接）：

    {  :temp => nil }                       <- header
    {  :system => ...  :actors => ... }     <- contents

文件本身用 `main.dll` 的 `decryption_file` / `encryption_file` 加密，
密钥 = `tiyan_version`（见 codec.KEY_SAVE），本模块会自动选密钥。

⚠ **内测版 V2.201 的存档格式不一样**（`save_v201.py`：AES-128-ECB + Zlib，
口令 `153ad4v3fbdgbgd` 零补齐 16 字节），由 `codec` 自动分流。
本模块用 `self.v201` 记住打开时是哪种格式 —— 保存时必须按**同一种**格式写回去，
选错会写出游戏读不了的坏档（而且不报错，是最坏的一类 bug）。

写回时先做Marshal 重写 → 再加密，并且会备份 `*.bak.<时间戳>`。
"""
import gc
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

# ⚠ 必须起别名：save() 有个布尔参数就叫 backup，它会把模块名遮蔽掉
#   （`backup.backup_dir` 会变成 'bool' object has no attribute ...）。
import backup as backup_mod  # noqa: E402
import codec  # noqa: E402
import patchwriter  # noqa: E402
import paths  # noqa: E402
import marshal_ruby as M  # noqa: E402
import save_v201  # noqa: E402


def parse_bytes(raw):
    """关着 GC 解析明文 Marshal。

    一份 27 万字节的档要建 **6 万多个节点对象**，CPython 的分代 GC 会在解析
    途中反复做全表扫描 —— 实测 0.21s → 0.16s，而且波动明显变小
    （2026-10-07 载入优化）。只在这段关掉，退出时按**原来的**开关恢复
    （调用方要是自己关了 GC，别被我们打开）。
    """
    on = gc.isenabled()
    gc.disable()
    try:
        return M.parse_stream(raw)
    finally:
        if on:
            gc.enable()


class Doc(object):
    """一份存档 / 数据文件。"""

    def __init__(self, path=None):
        self.path = path
        self.raw = b""                 # 打开时的字节（明文）
        self.engine = None             # PatchEngine
        self.objects = []              # [{'head':..,'node':..,'links':..}, ...]
        self.plain = False             # 打开时是不是明文
        self.plain_key = None          # 打开密文时用的密钥
        self.v201 = False              # 是不是内测版 V2.201 存档（AES+Zlib，见 save_v201）
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
        self.plain = codec.looks_like_marshal(path)
        self.v201 = False
        if self.plain:
            self.raw = open(path, "rb").read()
        else:
            # 先试内测版 V2.201 通道（AES-128-ECB+Zlib，纯 Python、不需要宿主）；
            # 认出来就记进 self.v201 —— 保存时必须按同一种格式写回去。
            plain = None
            v201_err = None
            if save_v201.is_v201_candidate(path):
                try:
                    plain = save_v201.decode(open(path, "rb").read())
                    self.v201 = True
                except Exception as e:
                    v201_err = e
            tmp = path + ".xj_plain"
            if plain is None:
                try:
                    codec.decrypt_file(path, tmp)
                except codec.CodecError:
                    # 两条路都解不开。**优先报 V2.201 那条的原因** ——
                    # 老路（main.dll）的报错永远是「输出为空 / 密钥不对」这种
                    # 套话，对 V2.201 存档毫无指向性（它压根不是那套格式），
                    # 只报它会让人以为是密钥问题，反复换密钥都是白忙。
                    if v201_err is not None:
                        raise ValueError(
                            "这个存档按内测版 V2.201 格式（AES-128-ECB + Zlib）"
                            "也解不开：%s\n"
                            "它可能既不是 V2.201 存档、也不是尝鲜版存档"
                            "（后者请用 main 分支的 v0.6.0 版本工具）。" % v201_err)
                    raise
                self.plain_key = codec.key_used_for(path)
                self.raw = open(tmp, "rb").read()
            else:
                self.raw = plain
            try:
                os.remove(tmp)
            except OSError:
                pass
        self.engine = patchwriter.PatchEngine(self.raw)
        self.objects = parse_bytes(self.raw)
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
            # 重新编号。tests/test_roundtrip.py 证明"什么都不改"时能逐字节还原，
            # 所以除了我们动过的地方，其余字节完全不变。
            new = M.serialize_doc(self.objects)
        else:
            new = self.engine.apply()
        # 守卫：重解析 → 重序列化必须逐字节还原。对象编号一旦错位
        # （如 Bignum 占编号的约定不一致），这一步必然对不上，把坏档
        # 拦在写盘之前 —— 游戏读那种档会直接 NoMethodError。
        # ⚠ 只解析一次：一份 46 万字节的存档 parse_stream 要 ~0.5s，
        #   以前这里解析两遍、末尾再解析一遍 = 1.5s 白花，保存卡就卡在这儿。
        try:
            objs = parse_bytes(new)
        except Exception as e:
            raise ValueError("保存前自检失败：重写的字节解析不出来（%s）"
                             "，已取消写入，原文件未动" % e)
        if M.serialize_doc(objs) != new:
            raise ValueError("保存前自检失败：重写的字节不自洽"
                             "（对象编号错位），已取消写入，原文件未动")
        if backup and os.path.exists(path):
            # 备份放进 .huaji2-save-editor 目录，不再散落在存档同目录
            bak_dir = backup_mod.backup_dir(path)
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
            #⚠ 内测版 V2.201 存档必须走 save_v201 通道（AES-128-ECB+Zlib）。
            #  `tmp` 是明文临时文件、名字里没有 save 字样，光看文件名判断不出
            #  该用哪种加密 —— 而选错会写出一个游戏读不了的坏档（且不报错）。
            #  `self.v201` 是 load() 当时认出来的，最可靠。
            if getattr(self, "v201", False):
                save_v201.encrypt_file(tmp, path)
            else:
                key = getattr(self, "plain_key", None) or codec.key_used_for(path)
                codec.encrypt_file(tmp, path, key)
            os.remove(tmp)
        self.raw = new
        self.engine = patchwriter.PatchEngine(new)
        self.objects = objs            # 复用自检那一次解析（同一个 new，语义一样）
        self.dirty = False
        self.structural = False
        return path

    # ------------------------------------------------------------------ 改值
    def set_value(self, node, value):
        # ⚠ 整数在 'i'（Fixnum，**不占**对象编号）与 'l'（大整数，**占**编号）
        #   之间切换，会改变整条流的"对象编号个数"——就地补丁改不了后面的
        #   '@N'，必须升级为整档重写（`mark_structural`）。
        #   （0.5.2 祈福池改成 9999999999 就是踩的这个。）
        # ⚠⚠ 判据必须看**盘上实际是 'i' 还是 'l'**，不能拿 `fits_fixnum(旧值)` 比：
        #   旧值只是节点里存的数，形态由**节点类型**决定（IntNode ⇒ 盘上是 'i'，
        #   不占编号；BignumNode ⇒ 盘上是 'l'，占编号）。
        #   2026-10-07 踩过：盘上是 `i`(17.18 亿) 的节点改写成 30 亿，两个值
        #   `fits_fixnum` 都是 False ⇒ 旧判据以为"没跨界"，走了就地补丁 ——
        #   结果写出 'l' 却按 'i' 的编号排，全档 '@N' 集体错位一格（召唤兽名字
        #   被读成大整数）。注意 `save()` 的自洽守卫**拦不住**这种"自洽但整体
        #   偏移一格"的错档，只有这里判准才行。
        if isinstance(node, (M.IntNode, M.NilNode, M.BignumNode)):
            # 盘上形态：BignumNode ⇒ 盘上是 'l'（占编号）；
            #           IntNode/NilNode ⇒ 盘上是 'i'/T/F/0（不占编号）。
            disk_numbered = isinstance(node, M.BignumNode)
            # 写出形态：和 `serialize()` 的规则**逐条对齐** ——
            #   BignumNode 永远写 'l'（哪怕值装得下 Fixnum，仍占编号）；
            #   IntNode/NilNode 装不下才写 'l'。
            out_numbered = isinstance(node, M.BignumNode) or (
                isinstance(value, int) and not isinstance(value, bool)
                and not M.fits_fixnum(value))
            if disk_numbered != out_numbered:
                patchwriter.PatchEngine.set_scalar(self.engine, node, value)
                self.mark_structural()
                return
        patchwriter.PatchEngine.set_scalar(self.engine, node, value)
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
        print("用法： python src/doctree.py <存档文件>")
        print("       python src/doctree.py --default      # 自动定位 <游戏根>\\save.rvdata2")
        return
    path = paths.save_path() if argv[0] == "--default" else argv[0]
    if not path:
        print("[NG] 没找到游戏目录/存档，请设 XJ_GAME")
        return
    print("存档 =", path)
    doc = Doc(path)
    print(doc.summary())


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")
    main()
