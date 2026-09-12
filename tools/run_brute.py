# -*- coding: utf-8 -*-
"""崩溃容忍的批量密钥试错驱动器。

main.dll 在遇到某些候选密钥时会把宿主进程直接搞崩（0xC0000005），
所以按批跑：一批崩了就跳过出事的那一个候选继续下一批。

用法（作为库）：
    from run_brute import run_brute
    run_brute(keys_file, [target...], out_prefix, log_path)
"""
import os
import re
import subprocess
import sys
import threading
import time

sys.stdout.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GAME = os.path.normpath(os.path.join(ROOT, "..", "..", ".."))
HOST = os.path.join(ROOT, "src", "XJCodec32.exe")
DLL = os.path.join(GAME, "System", "main.dll")

BATCH = 200
JOBS = 6

_lock = threading.Lock()


def _log(f, msg):
    with _lock:
        f.write(msg + "\n")
        f.flush()


def _worker(wid, keys_file, targ, out_prefix, seg_start, seg_end, log, hits, bad):
    pos = seg_start
    while pos < seg_end:
        cnt = min(BATCH, seg_end - pos)
        pfx = "%s_w%d" % (out_prefix, wid)
        cmd = [HOST, "brute", DLL, keys_file, pfx, targ, str(pos), str(cnt)]
        t0 = time.time()
        try:
            p = subprocess.run(cmd, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, cwd=GAME)
            rc = p.returncode
            txt = (p.stdout or b"").decode("utf-8", "replace")
        except Exception as e:
            rc, txt = -999, str(e)
        dt = time.time() - t0
        _log(log, "[W%d] 批 %d..%d rc=%d %.1fs" % (wid, pos, pos + cnt, rc, dt))
        for line in txt.splitlines():
            if "[HIT]" in line:
                _log(log, "[W%d] %s" % (wid, line))
                hits.append((wid, line))
        if rc in (0, 5):
            pos += cnt
        else:
            bad.append(pos)
            _log(log, "[W%d] !! 批 %d 异常(rc=%d)，跳过该批首个候选" % (wid, pos, rc))
            pos += 1


def run_brute(keys_file, targets, out_prefix, log_path, jobs=JOBS, batch=BATCH):
    keys = open(keys_file, encoding="utf-8").read().splitlines()
    n = len(keys)
    targ = ";".join(targets)
    per = (n + jobs - 1) // jobs
    hits, bad = [], []
    with open(log_path, "w", encoding="utf-8") as log:
        log.write("候选总数 = %d  并行 = %d  批次 = %d\n目标 = %s\n开始 %s\n"
                  % (n, jobs, batch, targ, time.strftime("%H:%M:%S")))
        log.flush()
        ts = []
        for w in range(jobs):
            a = w * per
            b = min(n, a + per)
            if a >= b:
                continue
            ts.append(threading.Thread(target=_worker,
                                       args=(w, keys_file, targ, out_prefix,
                                             a, b, log, hits, bad)))
        t0 = time.time()
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        log.write("结束 %s 用时 %.1fs  命中 %d  异常批 %d\n"
                  % (time.strftime("%H:%M:%S"), time.time() - t0,
                     len(hits), len(bad)))
        log.write("异常位置: %s\n" % bad[:80])
    return hits
