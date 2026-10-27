#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# =================================================================================
#  WorkBuddy 全自动积分助手 —— 统一入口 / 守护调度 / 凭据适配  (workbuddy_auto.py)
#
#  本文件为本仓库原创（MIT，版权归本仓库维护者）。底层任务引擎 wb_engine.py 为
#  第三方派生作品，详见该文件头与仓库 NOTICE / LICENSE。
#
#  设计：仅负责「长效令牌适配 + 守护调度 + 日志 + 单实例锁」，不重复实现任务逻辑。
#  任务覆盖、接口、上报等核心实现均在 wb_engine.py。
# =================================================================================
"""
WorkBuddy 全自动积分助手 —— 统一入口 / 守护调度 / 凭据适配

设计：
  · 底层引擎 wb_engine.py 来自开源项目 xz0609/workbuddy-checkin-ql（MIT，
    基于 L0NE-6/WorkBuddy-Daily 修改），覆盖 35 项任务（签到/成长中心18/
    互动玩法8/开学季5/小程序3），含遥测上报、真实 AI 对话、专家召唤、
    抽奖/盲盒/转盘/连登兑换/补登 等白名单内外全部接口。
  · 本文件只负责「凭据适配 + 守护调度 + 日志 + 单实例锁」，不重复实现任务逻辑。

凭据（二选一，优先顺序）：
  1) ~/.workbuddy/checkin-rt.json  -> {"refresh_token": "..."}（本助手导出的长效令牌）
  2) auths/*.json                  -> 引擎原生格式（桌面客户端 login 导出）

用法：
  python workbuddy_auto.py daemon            # 常驻守护：每日 08:00 全量 + 每 2h 巡逻
  python workbuddy_auto.py once             # 立即跑一轮全量（auto）
  python workbuddy_auto.py once --mode growth   # 只跑成长+玩法（含旅行/抽奖）
  python workbuddy_auto.py once --mode school   # 只跑开学季+小程序
  python workbuddy_auto.py query             # 只读：积分/用量/成长概况
"""

import os
import sys
import time
import json
import fcntl
import argparse
import datetime

# ---- 必须在 import 引擎之前设置运行参数（引擎在 import 时读取这些环境变量）----
os.environ.setdefault("RANDOM_SIGNIN", "false")          # 守护内不随机延时
os.environ.setdefault("WORKBUDDY_BUDGET_SECONDS", "900")  # 单轮请求预算

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import wb_engine as E  # noqa: E402

WB_DIR = os.path.expanduser("~/.workbuddy")
RT_FILE = os.path.join(WB_DIR, "checkin-rt.json")
LOG_FILE = os.path.join(WB_DIR, "checkin.log")
STATE_FILE = os.path.join(WB_DIR, "auto_state.json")
LOCK_FILE = os.path.join(WB_DIR, "auto.lock")

FULL_HOUR = 8          # 每日全量触发小时（北京时间）
PATROL_HOURS = 2       # 巡逻间隔（小时）：旅行到港即领 + 成长补领 + 玩法

BJT = datetime.timezone(datetime.timedelta(hours=8))
_LOG_FP = None


# ---------------------------------------------------------------------------
# 日志 / 文件小工具
# ---------------------------------------------------------------------------
def _open_log():
    global _LOG_FP
    if _LOG_FP is None or _LOG_FP.closed:
        try:
            _LOG_FP = open(LOG_FILE, "a", encoding="utf-8")
        except Exception:
            _LOG_FP = None
    return _LOG_FP


def log(msg):
    ts = datetime.datetime.now(BJT).strftime("%Y-%m-%d %H:%M:%S")
    line = "[%s] %s" % (ts, msg)
    print(line, flush=True)
    fp = _open_log()
    if fp:
        fp.write(line + "\n")
        fp.flush()


def _read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _write_json(path, obj, mode=None):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        if mode is not None:
            try:
                os.chmod(path, mode)
            except Exception:
                pass
        return True
    except Exception:
        return False


def acquire_lock():
    try:
        fd = open(LOCK_FILE, "w")
        fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fd
    except Exception:
        return None


# ---------------------------------------------------------------------------
# 凭据适配：把 refresh_token 转成引擎需要的 session（AT + uid + nick）
# ---------------------------------------------------------------------------
def load_session():
    # 1) 优先 ~/.workbuddy/checkin-rt.json（长效令牌）
    rt_cfg = _read_json(RT_FILE) or {}
    rt = rt_cfg.get("refresh_token") or rt_cfg.get("rt")
    # 2) 环境变量兜底
    if not rt:
        rt = os.environ.get("WORKBUDDY_RT")
    # 3) 同目录 rt.txt 兜底（便于迁移）
    if not rt:
        p = os.path.join(HERE, "rt.txt")
        if os.path.exists(p):
            try:
                rt = open(p, "r", encoding="utf-8").read().strip()
            except Exception:
                rt = None
    if rt:
        at, new_rt = E.refresh_one(rt)
        if at:
            p = E._jwt_payload(at)
            uid = p.get("sub") or p.get("userId") or ""
            nick = p.get("nickname") or p.get("preferred_username") or "user"
            if new_rt and new_rt != rt:
                _write_json(RT_FILE, {"refresh_token": new_rt,
                                      "source": "auto_rotate",
                                      "updated_at": int(time.time())}, 0o600)
            return uid, {
                "auth": {"accessToken": at, "refreshToken": new_rt or rt,
                         "endpoint": E.DEFAULT_ENDPOINT},
                "account": {"uid": uid, "nickname": nick},
            }
        else:
            log("⚠️  refresh 失败：%s（令牌可能已失效，请重新导出）" % (new_rt or "未知"))
    # 4) 兼容引擎原生 auths/*.json
    creds = E.load_creds()
    if creds:
        return creds[0]
    return None, None


def _mirror_rt(session):
    """把引擎可能轮换后的 refreshToken 回写到 checkin-rt.json（保持单一来源）。"""
    new_rt = (session.get("auth") or {}).get("refreshToken")
    if not new_rt:
        return
    cur = _read_json(RT_FILE) or {}
    if cur.get("refresh_token") != new_rt:
        _write_json(RT_FILE, {"refresh_token": new_rt, "source": "auto_rotate",
                              "updated_at": int(time.time())}, 0o600)


# ---------------------------------------------------------------------------
# 一轮运行（透传引擎 run_full，stdout 同时落盘日志）
# ---------------------------------------------------------------------------
class _Tee(object):
    def __init__(self, *streams):
        self._streams = streams

    def write(self, s):
        for st in self._streams:
            try:
                st.write(s)
            except Exception:
                pass

    def flush(self):
        for st in self._streams:
            try:
                st.flush()
            except Exception:
                pass


def run_once(mode="auto"):
    uin, session = load_session()
    if not session:
        log("❌ 未找到任何凭据（checkin-rt.json / auths/*.json）。")
        return None
    t0 = time.time()
    log("▶ 开始运行（模式=%s）" % mode)
    real_stdout = sys.stdout
    fp = _open_log()
    tee = _Tee(real_stdout, fp) if fp else real_stdout
    sys.stdout = tee
    try:
        summary = E.run_full(uin, session, mode=mode)
    except Exception as e:
        log("❌ 运行异常：%s: %s" % (type(e).__name__, e))
        summary = None
    finally:
        sys.stdout = real_stdout
    _mirror_rt(session)
    log("■ 结束（耗时 %.0f 秒）" % (time.time() - t0))
    return summary


# ---------------------------------------------------------------------------
# 守护调度：每日全量 + 定期巡逻（旅行到港即领 + 成长补领 + 玩法）
# ---------------------------------------------------------------------------
def daemon():
    """全自动守护：
      · 每天 08:00 准点全量；未跑/跑失败则每分钟复查补拉，直到今天成功跑完。
      · 全量完成后每 2h 巡逻（成长补领 + 旅行到港即领 + 盲盒/抽奖等玩法）。
    """
    log("[daemon] 全自动守护启动：每日 %02d:00 全量 + 每 %dh 巡逻（失败/漏跑自动复查）" % (FULL_HOUR, PATROL_HOURS))
    state = _read_json(STATE_FILE) or {}
    last_patrol = 0
    while True:
        try:
            now = datetime.datetime.now(BJT)
            today = now.date().isoformat()
            full_done = state.get("last_full") == today

            # 每日全量：08:00 起的窗口内，今天还没成功跑过 → 触发（准点/漏跑/失败复查统一在此）
            if not full_done and FULL_HOUR <= now.hour < FULL_HOUR + 15:
                summary = run_once("auto")
                ok = summary is not None and "登录态失效" not in (summary.get("rest") or [])
                if ok:
                    state["last_full"] = today
                    _write_json(STATE_FILE, state)
                    last_patrol = time.time()
                    log("[daemon] 今日全量完成 ✓")
                else:
                    log("[daemon] 全量未成功（%s），60s 后复查再拉起" % (
                        "登录态失效" if summary is None else "异常"))
                time.sleep(120)
                continue

            # 巡逻：仅全量完成后进行，旅行到港即领 + 成长补领 + 盲盒/抽奖
            if full_done and time.time() - last_patrol >= PATROL_HOURS * 3600:
                log("[daemon] 触发巡逻（成长+玩法）")
                run_once("growth")
                last_patrol = time.time()
                _write_json(STATE_FILE, state)
        except Exception as e:
            log("[daemon] 循环异常：%s" % str(e)[:200])
        time.sleep(60)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="WorkBuddy 全自动积分助手")
    ap.add_argument("cmd", nargs="?", default="once",
                    choices=["once", "daemon", "dry", "query", "growth", "school"])
    ap.add_argument("--mode", default="auto",
                    choices=["auto", "growth", "school", "query"])
    args = ap.parse_args()

    if args.cmd == "daemon":
        # 外层自愈：守护进程若异常退出，自动重启，确保常驻
        while True:
            try:
                daemon()
            except Exception as e:
                log("[daemon] 守护异常退出，5s 后自重启：%s" % str(e)[:200])
                time.sleep(5)

    if args.cmd == "dry":
        return run_once("query")

    if args.cmd in ("query", "growth", "school"):
        return run_once(args.cmd)

    # once
    return run_once(args.mode)


if __name__ == "__main__":
    fd = acquire_lock()
    if fd is None:
        print("⚠️  已有实例在运行（%s），退出避免重复请求。" % LOCK_FILE)
        sys.exit(0)
    try:
        main()
    finally:
        try:
            fcntl.lockf(fd, fcntl.LOCK_UN)
            fd.close()
        except Exception:
            pass
