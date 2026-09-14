# -*- coding: utf-8 -*-
"""从游戏脚本里抽出经验表，生成 `src/xj_exps.py`。

    python tools/gen_exp_table.py           # 生成（没有解出的脚本会自动先解密）
    python tools/gen_exp_table.py --check   # 只核对生成结果和脚本里的表是否一致

背景：这个游戏的升级经验**不是公式算的**，是脚本里硬编码的一张表：

    $exps = { :actor => [0, 110, 237, ...], :baby => [...] }
    class Game_Actor
      def exp_for_level(level) = $exps[:actor][level-1]
      def next_level_exp       = exp_for_level(@level + 1) = $exps[:actor][@level]

所以「升级所需经验」= `ACTOR_EXP[当前等级]`（**下标就是等级**，40 级 → 第 40 项），
游戏界面上显示的那个数就是它。工具以前把 `@limit_exp` 当成「升级所需经验」，
那是错的 —— 它只是「累计获得经验」的计数器（体验版超过 202123741 就不再发经验）。

游戏换版本后重跑一次这个脚本即可。
"""
import io
import os
import re
import subprocess
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCRIPTS = os.path.join(HERE, "_scripts")
OUT = os.path.join(ROOT, "src", "xj_exps.py")


def find_script_file():
    """找装着 $exps 的那个脚本段。"""
    if not os.path.isdir(SCRIPTS):
        return None
    for n in sorted(os.listdir(SCRIPTS)):
        if not n.endswith(".rb"):
            continue
        p = os.path.join(SCRIPTS, n)
        try:
            txt = open(p, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        if "$exps = {" in txt:
            return p
    return None


def extract(txt):
    i = txt.find("$exps = {")
    if i < 0:
        raise SystemExit("脚本里找不到 `$exps = {`")
    j = txt.find("};", i)
    block = txt[i:j]

    def table(name):
        k = block.find(":%s => [" % name)
        if k < 0:
            raise SystemExit("找不到 :%s 表" % name)
        end = block.find("]", k)
        return [int(x) for x in re.findall(r"-?\d+", block[k:end])]

    return table("actor"), table("baby")


def wrap(name, nums, per=16):
    """把数字列表排成整齐的多行。"""
    lines = ["%s = [" % name]
    for i in range(0, len(nums), per):
        lines.append("    " + " ".join("%d," % v for v in nums[i:i + per]))
    lines[-1] = lines[-1].rstrip(",") if lines[-1].endswith(",") else lines[-1]
    lines.append("]")
    return "\n".join(lines)


def gen(actor, baby):
    head = '''# -*- coding: utf-8 -*-
"""升级经验表（**自动生成，别手改** —— 改了跑 `python tools/gen_exp_table.py`）。

来源：游戏脚本里硬编码的 `$exps`（不是公式）。
用法见 `xj_game.exp_for_level()`：

    升级所需经验 = ACTOR_EXP[当前等级]      # 下标就是等级，40 级 → 第 40 项
    召唤兽同理解 BABY_EXP

游戏里对应的脚本：

    def exp_for_level(level) = $exps[:actor][level-1]
    def next_level_exp       = exp_for_level(@level + 1) == $exps[:actor][@level]

⚠ 别把 `@limit_exp` 当升级所需经验：那是「累计获得经验」计数器，
  体验版超过 202123741 就不再发经验（见游戏脚本 Game_Actor#gain_exp）。
"""
'''
    body = "\n\n".join([wrap("ACTOR_EXP", actor), wrap("BABY_EXP", baby)])
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(head + "\n" + body + "\n")
    print("已生成 %s（actor %d 项 / baby %d 项）" % (OUT, len(actor), len(baby)))


def main():
    argv = sys.argv[1:]
    p = find_script_file()
    if p is None:
        print("没解出脚本，先跑：python tools/dump_scripts.py")
        if "--auto" not in argv:
            return 1
        r = subprocess.run([sys.executable, os.path.join(HERE, "dump_scripts.py")])
        if r.returncode != 0:
            return r.returncode
        p = find_script_file()
        if p is None:
            return 1
    txt = open(p, encoding="utf-8", errors="replace").read()
    actor, baby = extract(txt)
    if "--check" in argv:
        sys.path.insert(0, os.path.join(ROOT, "src"))
        import xj_exps
        same = (list(xj_exps.ACTOR_EXP) == actor and list(xj_exps.BABY_EXP) == baby)
        print("一致" if same else "不一致，重新生成")
        return 0 if same else 1
    gen(actor, baby)
    print("  actor[40] =", actor[40], "（40 级的升级所需经验）")
    print("  baby[40]  =", baby[40])
    return 0


if __name__ == "__main__":
    sys.exit(main())
