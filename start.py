#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# =================================================================================
#  start.py —— 跨平台无人值守启动器（Windows / macOS / Linux / 沙箱）
#
#  本文件为本仓库原创（MIT，版权归 HonorC05 (workbuddy-auto-checkin)）。
#  纯标准库、零第三方依赖；不依赖 bash / nohup / systemd / 任务计划程序，
#  用同一条命令在任何环境拉起双层守护（watch 自检 → daemon 主循环）。
#
#  用法（任何环境都一样）：
#    python start.py             # 后台拉起守护（幂等，已有实例不会重复）
#    python start.py status      # 查看守护状态
#    python start.py stop        # 停止守护
#    python start.py once        # 前台立即跑一轮全量
#    python start.py foreground  # 前台常驻（调试 / 交给 systemd 或任务计划托管）
# =================================================================================
"""跨平台无人值守启动器：双层守护 + 幂等拉起 + 状态查询。

主守护 workbuddy_auto.py daemon 自带异常自愈循环；本文件的 watch 层再兜一层，
进程被强杀 / 沙箱回收后 15 秒内自动重新拉起，无需任何 shell 脚本。

[修复] 子进程被 kill 后会短暂成为僵尸，os.kill(pid, 0) 对僵尸仍返回成功，
会让 watch 误判「主守护仍活着」而漏拉。这里同时用 Popen.poll() 回收僵尸
（poll 会 waitpid），并对 pid 探测补一层 /proc 僵尸状态识别。
"""

import os
import sys
import time
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ENTRY = os.path.join(HERE, "workbuddy_auto.py")
STATE_DIR = os.path.expanduser("~/.workbuddy")
WATCH_PID = os.path.join(STATE_DIR, "watch.pid")
DAEMON_PID = os.path.join(STATE_DIR, "daemon.pid")
LOG_FILE = os.path.join(STATE_DIR, "auto_guard.log")

# watch 进程持有主守护的 Popen 对象，poll() 能回收僵尸、精确判断存活。
_DAEMON_PROC = None

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def _read_pid(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return int(f.read().strip())
    except Exception:
        return 0


def _write_pid(path, pid):
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(str(pid))
        return True
    except Exception:
        return False


def _is_zombie(pid):
    """Linux：/proc/<pid>/stat 状态为 Z 的僵尸，os.kill(pid,0) 仍会成功。"""
    try:
        with open("/proc/%d/stat" % pid, "r") as f:
            line = f.read()
        return line.rsplit(")", 1)[1].strip().startswith("Z")
    except Exception:
        return False


def _alive(pid):
    if not pid:
        return False
    if os.name == "nt":
        try:
            import ctypes
            h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
            if h:
                ctypes.windll.kernel32.CloseHandle(h)
                return True
            return False
        except Exception:
            return True   # 探测不可用时保守视为存活，避免重复拉起
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    except Exception:
        return True
    return not _is_zombie(pid)


def _popen_args():
    """后台进程参数：Windows 完全脱离父控制台，Unix 新建会话。"""
    os.makedirs(STATE_DIR, exist_ok=True)
    try:
        os.chmod(STATE_DIR, 0o700)
    except Exception:
        pass
    log_fp = open(LOG_FILE, "a", encoding="utf-8")
    kw = {"cwd": HERE, "stdin": subprocess.DEVNULL,
          "stdout": log_fp, "stderr": subprocess.STDOUT}
    if os.name == "nt":
        kw["creationflags"] = (subprocess.CREATE_NEW_PROCESS_GROUP |
                               subprocess.DETACHED_PROCESS)
    else:
        kw["start_new_session"] = True
    return kw, log_fp


def _spawn_daemon():
    """拉起主守护并持有 Popen 对象，供 watch 用 poll() 精确判断存活。"""
    global _DAEMON_PROC
    kw, fp = _popen_args()
    try:
        p = subprocess.Popen([sys.executable, ENTRY, "daemon"], **kw)
        _DAEMON_PROC = p
        _write_pid(DAEMON_PID, p.pid)
        return p.pid
    finally:
        try:
            fp.close()
        except Exception:
            pass


def _spawn_watch():
    kw, fp = _popen_args()
    try:
        p = subprocess.Popen([sys.executable, os.path.abspath(__file__), "watch"], **kw)
        _write_pid(WATCH_PID, p.pid)
        return p.pid
    finally:
        try:
            fp.close()
        except Exception:
            pass


def _watch_loop():
    """前台 watch：15 秒自检，主守护掉线立即重新拉起。"""
    while True:
        try:
            proc = _DAEMON_PROC
            if proc is not None:
                if proc.poll() is not None:   # 已退出（poll 顺带回收僵尸）→ 重拉
                    _spawn_daemon()
            elif not _alive(_read_pid(DAEMON_PID)):
                _spawn_daemon()
        except Exception:
            pass
        time.sleep(15)


def _kill(pid):
    if not pid:
        return
    try:
        if os.name == "nt":
            subprocess.call(["taskkill", "/PID", str(pid), "/F", "/T"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            os.kill(pid, 15)
    except Exception:
        pass


def main():
    action = (sys.argv[1] if len(sys.argv) > 1 else "start").lower()
    if action == "watch":
        _watch_loop()
        return 0
    if action in ("once", "foreground"):
        args = ["once"] if action == "once" else ["daemon"]
        return subprocess.call([sys.executable, ENTRY] + args, cwd=HERE)
    if action == "status":
        w, d = _read_pid(WATCH_PID), _read_pid(DAEMON_PID)
        print("watch : %s (pid=%s)" % ("运行中" if _alive(w) else "未运行", w or "-"))
        print("daemon: %s (pid=%s)" % ("运行中" if _alive(d) else "未运行", d or "-"))
        print("日志  : %s" % LOG_FILE)
        return 0
    if action == "stop":
        _kill(_read_pid(WATCH_PID))     # 先停 watch，避免它立刻重拉 daemon
        time.sleep(0.5)
        _kill(_read_pid(DAEMON_PID))
        for p in (WATCH_PID, DAEMON_PID):
            try:
                os.remove(p)
            except Exception:
                pass
        print("已停止守护（watch + daemon）")
        return 0
    w = _read_pid(WATCH_PID)
    if _alive(w):
        print("守护已在运行（watch pid=%s），无需重复拉起。" % w)
        return 0
    new_pid = _spawn_watch()
    time.sleep(1.5)
    print("守护已拉起 watch pid=%s（%s）" % (
        new_pid, "确认运行中" if _alive(new_pid) else "待确认"))
    print("状态: python start.py status    停止: python start.py stop")
    print("日志: %s" % LOG_FILE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
