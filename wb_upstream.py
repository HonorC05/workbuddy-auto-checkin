#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# =================================================================================
#  wb_upstream.py —— 上游能力合入层（Upstream merge layer）
#
#  本文件为本仓库原创（MIT，版权归 HonorC05 (workbuddy-auto-checkin)）。
#
#  来源：把 L0NE-6/WorkBuddy-Daily v3.42~v3.50（MIT）相对本仓库缺失的能力，
#        适配成本仓库的 HTTP 抽象（wb_engine.get/post 返回 (code, body)）后合入。
#        xz0609/workbuddy-checkin-ql 已由 wb_engine.py 全量覆盖，无需重复合入。
#        第三方声明见 NOTICE / LICENSE。
#
#  设计原则（确保"都能正常使用"、且不影响已跑通的主链路）：
#    1. 零侵入：主引擎只在 run_full 里加了几处 try/except 挂接；本文件任何
#       异常都被逐项隔离，绝不会中断签到 / 成长 / 旅行 / 领奖等既有链路。
#    2. 幂等 + 守卫：任务未下发、已领取、已锁定一律跳过；领奖以
#       "回读 claimed/claimed_at"为准，不重复 POST、不误报 +积分。
#    3. 指定客户端任务全自动化：所有要求特定客户端（小程序 / PC / App）的任务，
#       统一通过「官方客户端通道 header + 官方事件族上报 + 真实云端会话跑一轮」
#       完成，默认全部开启、不跳过；用户不带电脑也能照常拿奖励。
#    4. 安全护栏：始终使用账号自身的真实令牌调用官方接口；不伪造设备指纹、
#       不自造客户端 id 计数、不批量高频刷；事件带真人节奏间隔，失败退避、
#       领奖幂等回读、单轮时间盒，异常即停、下一轮再试（避免触发风控）。
#       状态文件按 UID 哈希隔离，不落任何凭据 / 手机号 / UID 明文。
#    5. 可回滚：环境变量 WORKBUDDY_UPSTREAM=0 可整体关闭本层。
#
#  合入清单（对应上游 v3.42~v3.50）：
#    A 账号态识别        企业版 / 账号受限(11140) / 渠道拦截(11-128)
#    B 任务快照 + 守卫    三口径 have/done/ready/locked + 未下发守卫 + 任务过滤
#    C 领奖回读确认      完成≠到账；按 progress 达标补领 + claimed_at 回读
#    D accept 落账修复    already_accepted 视为成功 + 回读 settled
#    E 终态口径 + 提醒    只认 claimed/确认回执；7 天内到期提醒
#    F 积分增量统计       数值化 before/after/delta（用户最关心的"增加量"）
#    G 签到补签队列       HTTP 500 + 10001 "稍后重试" → 第 10/40 分钟补签
#    H 一次性福利        补偿 / 新手礼包（billing 域，先查状态 + 本地防重）
#    I 小程序活动任务     星巴克协作 / 记者节福利（viewed→判据→claim→回读）
#    J 分享技能实链       skill_share：真实分享渠道 + 官方事件族 + 回读
#    K 小程序连续任务 2~7 mp 口径专家/对话×5/定时任务/GLM5.2/对话×10/PC灵感
#    L 智能补签候选       heatmap/streak 找漏签日（只读诊断，不重复扣卡）
#    M 会话数上限清理     10105 上限时停掉最旧活跃会话
#    N 每日活跃上报       点亮成长中心热力墙（签到不点热力墙）
#    O 多通道推送         企微/Bark/WxPusher/钉钉/Server酱（配置才生效）
# =================================================================================

import os
import re
import json
import time
import uuid
import math
import hashlib
import datetime
import urllib.parse

import wb_engine as E

# ---------------------------------------------------------------------------
# 域名与协议常量（对齐上游；本地 school 域已是同域）
# ---------------------------------------------------------------------------
CBDOMAIN = "https://www.codebuddy.cn"
CAMPAIGN_BASE = CBDOMAIN
MP_REPORT_URL = CBDOMAIN + "/v2/report"
APP_HOST = "https://copilot.tencent.com"
SKILL_SHARE_URL = ("https://open.workbuddy.cn/api/v2/open-platform/"
                   "asset-shares/c2c/channels")

MP_HEADER = {"X-Client-Platform": "miniprogram",
             "User-Agent": E.MP_UA}
MP_REPORT_HEADERS = {
    "Content-Type": "application/json", "Accept": "application/json",
    "X-Client-Product": "workbuddy-mp", "X-Client-Version": "2.4.0",
    "X-Client-Platform": "mp-weixin", "X-Platform": "wechatmp",
}
MP_EXPERT_CATEGORY = "16-BackToSchool"

UPSTREAM_ON = os.environ.get("WORKBUDDY_UPSTREAM", "1").strip().lower() not in ("0", "false", "no")
# 指定客户端判据（默认全开，用户不带电脑也能完成）：
#   · 活动 app：真跑一轮云端 agentos 对话（结构化 end_turn 才算成功）
#   · 记者节 desktop_same：官方 playbook_prompt_send 事件
#   · Sequential_Tasks_7 PC灵感：官方 playbook 事件族
# 与本项目既有 t_desktop_fingerprint / t_canvas_automation 同类，一律是
# 「真实令牌 + 官方接口 / 官方事件族 / 真实云端会话」，不伪造设备指纹。
# 可用 WORKBUDDY_SKIP_DESKTOP_SIM=1 手动关闭这三类主动判据；已达标 / 已完成的
# 任务无论开关如何都会自动领奖。
SKIP_DESKTOP_SIM = os.environ.get("WORKBUDDY_SKIP_DESKTOP_SIM", "0").strip().lower() in ("1", "true", "yes")

# 本层独立时间盒：入口 workbuddy_auto.py 直连 run_full 时引擎预算时钟不递减，
# 若只依赖 E._budget_left()，活动轮询 / 小程序真人节奏可能让单轮跑十几分钟。
# 本层所有等待与轮询统一受这里约束，超时即优雅收尾，交给下一轮继续。
LAYER_BUDGET_SECONDS = max(60.0, float(os.environ.get("WORKBUDDY_UPSTREAM_BUDGET", "300") or 300))
_LAYER_DEADLINE = 0.0


def _layer_left():
    if not _LAYER_DEADLINE:
        return LAYER_BUDGET_SECONDS
    return _LAYER_DEADLINE - time.monotonic()

# 状态目录：与 workbuddy_auto.WB_DIR 一致（目录由入口确保 0700）
STATE_DIR = os.path.expanduser(os.environ.get("WORKBUDDY_STATE_DIR", "") or "~/.workbuddy")
BENEFIT_STATE = os.path.join(STATE_DIR, "upstream_benefit_state.json")
SIGN_RETRY_STATE = os.path.join(STATE_DIR, "upstream_sign_retry.json")
ACTIVITY_STATE = os.path.join(STATE_DIR, "upstream_activity_state.json")
SIGN_RETRY_DELAYS = (10 * 60, 40 * 60)

# 任务过滤（默认全放行；设置后仅影响本层新增动作，不动既有链路）
def _parse_set(raw):
    return {x.strip() for x in (raw or "").replace("，", ",").split(",") if x.strip()}

TASK_ONLY = _parse_set(os.environ.get("WORKBUDDY_TASKS"))
TASK_SKIP = _parse_set(os.environ.get("WORKBUDDY_SKIP_TASKS"))
MP_CHAT_GAP = float(os.environ.get("WORKBUDDY_MP_GAP", "45") or 45)

# 活动判据轮询节奏（上游实测值；受本地时间预算约束）
CAMPAIGN_GAP, CAMPAIGN_POLL = 3, 6
CAMPAIGN_SLOW_GAP, CAMPAIGN_SLOW_POLL = 10, 6
CAMPAIGN_CLAIM_GAP, CAMPAIGN_CLAIM_POLL = 4, 5
CAMPAIGN_DESKTOP_WAIT, CAMPAIGN_DESKTOP_POLL = 60, 6
CAMPAIGN_APP_WAIT, CAMPAIGN_APP_POLL = 30, 5
CAMPAIGN_APP_BOX_DOMAINS = ("tencent.com", "codebuddy.cn", "workbuddy.cn",
                            "workbuddy.agentos-worker.net")

CAMPAIGN_SPECS = [
    {"code": "campaign_starbucks_2026", "label": "星巴克协作",
     "page": {"pageURL": "subpackages/secondary/starbucks-activity-428/index",
              "pageName": "starbucks_activity"},
     "tasks": [
         {"task": "ai_chat", "label": "与 AI 对话3次", "kind": "chat", "times": 3, "credit": 100},
         {"task": "expert", "label": "召唤专家并对话", "kind": "expert", "credit": 100},
         {"task": "app", "label": "解锁 App 强大能力", "kind": "app", "credit": 100},
     ]},
    {"code": "campaign_reporter_2026", "label": "记者节福利活动",
     "page": {"pageURL": "subpackages/journalist-benefit/index",
              "pageName": "journalist_benefit"},
     "tasks": [
         {"task": "expert_chat", "label": "体验「媒体工作助理」专家", "kind": "expert",
          "expert_id": "ex_NaiDbO06Adf3", "expert_name": "媒体工作助理", "credit": 50},
         {"task": "skill_use", "label": "体验「采访素材整理」技能", "kind": "skill",
          "skill_id": "skill_2117491159283752960",
          "skill_name": "interview-material-organizer", "credit": 50},
         {"task": "desktop_same", "label": "体验「内容发布排期」灵感", "kind": "desktop",
          "case_id": "content-calendar", "credit": 100},
     ]},
]
CAMPAIGN_CASES = {
    "content-calendar": {"event_id": "cnb-content-calendar", "name": "内容发布排期表",
                         "type": "table", "prompt_length": 359},
}

# 真实专家规格（上游 v3.50；本地 EXPERT_EXPERIENCE_SPECS 的兜底 id 为占位值）
EXPERT_SPECS = {
    "expert_use_maidehao": {"id": "ex_GDl31WahyIH0", "name": "卖得好", "title": "中国电商运营专家"},
    "expert_use_douyinyin": {"id": "ex_FbY5nlWTqDod", "name": "斗音音", "title": "抖音策略师"},
    "expert_use_shangjia_xuanchuan": {"id": "ex_Weo3x2EZuSDm", "name": "商家宣传设计师", "title": "商家宣传页与海报设计师"},
    "expert_use_bowangwang": {"id": "ex_WZY136wV5aMt", "name": "播旺旺", "title": "直播电商教练"},
}


# ---------------------------------------------------------------------------
# 通用工具
# ---------------------------------------------------------------------------
def _ok(code):
    return code in (0, 200, "0", "200")


def _http_ok(code):
    return isinstance(code, int) and 200 <= code < 300


def want(*codes):
    """任务过滤：WORKBUDDY_TASKS 白名单 / WORKBUDDY_SKIP_TASKS 黑名单。"""
    if TASK_SKIP and any(c in TASK_SKIP for c in codes):
        return False
    if TASK_ONLY and not any(c in TASK_ONLY for c in codes):
        return False
    return True


def _new_conv():
    return str(uuid.uuid4())


def _new_msg():
    return "%012x%s" % (int(time.time() * 1000), uuid.uuid4().hex[:20])


def _uid_key(uid, prefix):
    """状态按 UID 哈希隔离，不落任何账号明文。"""
    return hashlib.sha256(("%s:%s" % (prefix, uid or "")).encode("utf-8")).hexdigest()[:16]


def _state_load(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            v = json.load(f)
        return v if isinstance(v, dict) else {}
    except Exception:
        return {}


def _state_save(path, data):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            os.chmod(os.path.dirname(path), 0o700)
        except Exception:
            pass
        tmp = "%s.tmp-%s" % (path, os.getpid())
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
        os.chmod(path, 0o600)
        return True
    except Exception:
        return False


def _reward_value(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v > 0
    if isinstance(v, (list, tuple, dict, set)):
        return bool(v)
    if isinstance(v, str):
        s = v.strip()
        if not s or s in ("{}", "[]", "null", "None", "false", "False"):
            return False
        try:
            return float(s) > 0
        except ValueError:
            return True
    return v is not None


def _reward_fields(obj, keys):
    return any(_reward_value(obj.get(k)) for k in keys)


def _sleep(seconds, log=None):
    """预算感知等待；本层时间盒或引擎预算不足时返回 False，调用方据此收尾。"""
    if _layer_left() <= seconds + 2:
        return False
    try:
        if E._budget_left() <= seconds + 5:
            return False
    except Exception:
        pass
    time.sleep(max(0, seconds))
    return True


# ---------------------------------------------------------------------------
# A. 账号态识别（避免把 403 误报成"凭据失效"、避免对受限账号空发请求）
# ---------------------------------------------------------------------------
def is_enterprise_denial(code, body):
    blob = json.dumps(body, ensure_ascii=False).lower() if isinstance(body, dict) else str(body or "").lower()
    if code == 403:
        return ("growth system" in blob or "personal user" in blob
                or ("成长" in blob and "个人" in blob))
    biz = body.get("code") if isinstance(body, dict) else None
    if code in (400, None) and biz == 10001:
        return ("企业" in blob) or ("enterprise" in blob)
    return False


def is_account_restricted(code, body):
    """账号级风控 11140；排除模型级限流（同码不同义）。"""
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except Exception:
            return False
    if not isinstance(body, dict) or body.get("code") not in (11140, "11140"):
        return False
    msg = " ".join(str(body.get(k) or "") for k in ("msg", "message", "displayMsg", "displayTips")).lower()
    if not msg:
        return False
    if any(m in msg for m in ("rate-limiting", "rate limit", "too many requests", "限流", "请求过于频繁")):
        return False
    return any(m in msg for m in ("request illegal", "account restricted", "restricted account",
                                 "account illegal", "unusual activity", "账号受限", "账号被限制",
                                 "账号存在异常行为", "账号异常", "账户受限", "已被限制使用"))


def is_unapproved_channel(code, body):
    if isinstance(body, dict):
        if body.get("code") == "11-128":
            return True
        blob = json.dumps(body, ensure_ascii=False).lower()
    else:
        blob = str(body or "").lower()
    return any(m in blob for m in ("11-128", "unapproved channel", "渠道限制"))


def preflight(wb_h, log):
    """只读探测成长域；返回 None 表示正常，否则返回应写入 summary["rest"] 的原因。"""
    if not UPSTREAM_ON:
        return None
    try:
        c, b = E.get(E.WORKBUDDY_BASE + "/v2/activity/growth/profile", wb_h)
        if is_unapproved_channel(c, b):
            log("🚫 渠道指纹拦截（11-128）：本轮停止成长/互动任务，不重试")
            return "渠道拦截（11-128）"
        if is_account_restricted(c, b):
            log("🚫 账号受限（11140）：本轮停止，请先到官方客户端确认账号状态")
            return "账号受限（11140）"
        if is_enterprise_denial(c, b):
            log("🏢 企业版账号：无个人成长体系，跳过签到与成长/互动任务")
            return "企业版账号（无个人成长体系）"
    except Exception as e:
        log("🔎 账号态探测异常（%s: %s），按正常账号继续" % (type(e).__name__, str(e)[:60]))
    return None


# ---------------------------------------------------------------------------
# B. 任务快照（三口径合并）+ 未下发守卫
# ---------------------------------------------------------------------------
def _row_code(row):
    return str(row.get("task_code") or row.get("code") or "").strip() if isinstance(row, dict) else ""


def _row_status(row):
    return str(row.get("accept_status") or row.get("status") or "").strip().lower() if isinstance(row, dict) else ""


def _row_done(row):
    if not isinstance(row, dict):
        return False
    if _row_status(row) == "claimed" or row.get("claimed") is True or str(row.get("claimed")).lower() == "true":
        return True
    return _reward_fields(row, ("actual_credit", "credited_credit", "granted_credit",
                                "actual_energy", "credited_energy", "granted_energy"))


def _row_ready(row):
    if not isinstance(row, dict):
        return False
    if _row_status(row) == "completed":
        return True
    pr = row.get("progress") or {}
    cur, tgt = E.as_int(pr.get("current")), E.as_int(pr.get("target"))
    return tgt > 0 and cur >= tgt


def build_snapshot(ctx):
    """一次读取桌面/mp/等级三口径，产出调度快照。只读 GET，失败不抛。"""
    snap = {"have": set(), "done": set(), "ready": set(), "locked": {},
            "rows": {}, "sources": {}, "complete": False, "errors": []}
    wb_h, mp_h = ctx["wb_h"], ctx["mp_h"]
    sources = (("desktop", "桌面", wb_h, "/v2/activity/growth/tasks", True),
               ("mp", "小程序", mp_h, "/v2/activity/growth/tasks", True),
               ("level", "等级", wb_h, "/activity/growth/tasks", False))
    for key, label, hdr, path, required in sources:
        src = {"ok": False, "rows": [], "error": "", "required": required}
        try:
            c, b = E.get(E.WORKBUDDY_BASE + path, hdr)
            if not _http_ok(c) or not isinstance(b, dict):
                raise RuntimeError("HTTP %s" % c)
            if b.get("code") is not None and not _ok(b.get("code")):
                raise RuntimeError("code %s" % b.get("code"))
            rows = (b.get("data") or {}).get("tasks") or []
            if not isinstance(rows, list):
                raise RuntimeError("tasks 不是列表")
            src["ok"] = True
            for row in rows:
                if not isinstance(row, dict):
                    continue
                item = dict(row)
                item["_source"] = label
                src["rows"].append(item)
                code = _row_code(item)
                if not code:
                    continue
                snap["have"].add(code)
                if code not in snap["rows"] or label == "桌面":
                    snap["rows"][code] = item
                if _row_done(item):
                    snap["done"].add(code)
                elif _row_ready(item):
                    snap["ready"].add(code)
                if item.get("locked"):
                    snap["locked"][code] = str(item.get("valid_start") or "见任务页")[:10]
        except Exception as e:
            src["error"] = str(e)[:80]
            snap["errors"].append("%s: %s" % (label, src["error"]))
        snap["sources"][key] = src
    snap["complete"] = all(snap["sources"].get(k, {}).get("ok") for k in ("desktop", "mp"))
    return snap


def need_action(snap, code, ctx=None):
    """未下发守卫：任务未下发 / 已领 / 已达标 / 锁定 → 不动作（不发真实事件）。"""
    if not snap or not snap.get("sources", {}).get("desktop", {}).get("ok"):
        return True   # 快照不可用时保守沿用既有行为
    if code not in snap["have"]:
        return False
    if code in snap["done"] or code in snap["ready"]:
        return False
    if code in snap["locked"]:
        return False
    return True


# ---------------------------------------------------------------------------
# C. 领奖「完成≠到账」：回执确认 + 回读 claimed_at + 达标补领
# ---------------------------------------------------------------------------
CLAIM_REWARD_KEYS = ("credit", "energy", "reward_credit", "reward_energy", "reward", "rewards")


def claim_response_ok(code, body):
    """领奖回执必须带实际奖励 / claimed / 明确幂等已领。"""
    body = body if isinstance(body, dict) else {}
    data = body.get("data") if isinstance(body, dict) else {}
    data = data if isinstance(data, dict) else {}
    msg = str(body.get("msg") or "").lower()
    has = _reward_fields(data, CLAIM_REWARD_KEYS)
    claimed = data.get("claimed")
    success = (_http_ok(code) and _ok(body.get("code"))
               and (has or claimed is True or str(claimed).strip().lower() == "true"))
    already = _http_ok(code) and (bool(data.get("already_claimed"))
                                  or any(m in msg for m in ("already", "已领取", "已领过")))
    return bool(success or already), data, msg


def claim_readback(wb_h, mp_h, code):
    """领奖后回读任务表，只认 claimed / claimed=true / 实际到账字段。"""
    for hdr in (wb_h, mp_h):
        try:
            c, b = E.get(E.GROWTH_BASE + "/tasks", hdr)
            if not _http_ok(c) or not isinstance(b, dict) or not _ok(b.get("code")):
                continue
            for row in (b.get("data") or {}).get("tasks") or []:
                if not isinstance(row, dict) or _row_code(row) != code:
                    continue
                if _row_done(row):
                    return row
        except Exception:
            continue
    return None


def claim_confirmed(ctx, code, mp=False, receipts=None):
    """领奖并确认到账；返回 True 仅当回执或回读确认已领取。幂等，不重复空 claim。"""
    log = ctx["log"]
    wb_h, mp_h = ctx["wb_h"], ctx["mp_h"]
    receipts = ctx.setdefault("_receipts", {}) if receipts is None else receipts
    if receipts.get(code, {}).get("confirmed"):
        log("🎁领奖[%s]: 本轮已确认，跳过重复 POST" % E.task_cn(code))
        return True
    hdr = mp_h if mp else wb_h
    path = E.WORKBUDDY_BASE + "/activity/growth/tasks/%s/claim" % code
    c, b = E.post(path, hdr, {})
    if c == 400 and not mp:
        h = dict(hdr)
        h.update({"x-client-platform": "web", "Origin": E.WORKBUDDY_BASE,
                  "Referer": E.WORKBUDDY_BASE + "/profile/growth-center"})
        c, b = E.post(path, h, {})
    if c in (400, 404) and not mp:
        c, b = E.post(E.GROWTH_BASE + "/tasks/%s/claim" % code, hdr, {})
    ok, data, msg = claim_response_ok(c, b)
    if ok:
        receipts[code] = {"confirmed": True}
        credit = data.get("credit", data.get("reward_credit"))
        energy = data.get("energy", data.get("reward_energy"))
        if any(m in msg for m in ("already", "已领取", "已领过")) or data.get("already_claimed"):
            log("🎁领奖[%s]: 已领过" % E.task_cn(code))
        elif credit is None and energy is None:
            log("🎁领奖[%s]: 回执确认已领取" % E.task_cn(code))
        else:
            log("🎁领奖[%s]: +%s积分 +%s能量" % (E.task_cn(code), credit, energy))
        return True
    if _http_ok(c):
        _sleep(1)
        if claim_readback(wb_h, mp_h, code) is not None:
            receipts[code] = {"confirmed": True}
            log("🎁领奖[%s]: 回读确认已领取（回执未给到账额）" % E.task_cn(code))
            return True
        receipts[code] = {"unconfirmed": True}
        log("🎁领奖[%s]: 回执未确认到账，本轮不再重复空 claim" % E.task_cn(code))
        return False
    log("🎁领奖[%s]: %s %s" % (E.task_cn(code), E._http_label(c), str(msg)[:50]))
    return False


def claim_ready_tasks(ctx):
    """按 progress 达标补领（不依赖瞬时 accept_status），桌面+小程序双口径去重。"""
    log = ctx["log"]
    wb_h, mp_h = ctx["wb_h"], ctx["mp_h"]
    # 前一步 claim_all 可能刚领过，服务端异步落账；短暂等待后再扫，避免对
    # 同一任务重复 POST（claim 幂等，但重复请求会刷屏、也白发一次写操作）。
    _sleep(1.5)
    merged, done_codes = {}, set()
    for hdr, is_mp in ((wb_h, False), (mp_h, True)):
        try:
            c, b = E.get(E.GROWTH_BASE + "/tasks", hdr)
            if not _http_ok(c) or not isinstance(b, dict):
                continue
            for row in (b.get("data") or {}).get("tasks") or []:
                if not isinstance(row, dict):
                    continue
                code = _row_code(row)
                if not code or code in ctx.get("_campaign_codes", ()):
                    continue
                if _row_done(row):
                    done_codes.add(code)
                    continue
                ready = _row_ready(row) and not row.get("locked")
                old = merged.get(code)
                if old is None or (ready and not old["ready"]):
                    merged[code] = {"ready": ready, "mp": is_mp}
        except Exception as e:
            log("🎁 领奖扫描异常（%s: %s）" % (type(e).__name__, str(e)[:60]))
    n = 0
    for code, item in merged.items():
        if code in done_codes or not item["ready"]:
            continue
        if not want(code, "claim"):
            continue
        try:
            if claim_confirmed(ctx, code, mp=item["mp"]):
                n += 1
        except Exception as e:
            log("🎁领奖[%s]异常: %s" % (code, str(e)[:60]))
        _sleep(1)
    log("🎁 达标补领: %s 项%s" % (n, "" if n else "（无待领）"))
    return n


# ---------------------------------------------------------------------------
# D. accept 落账修复（already_accepted 视为成功，回读 settled）
# ---------------------------------------------------------------------------
def accept_with_verify(ctx, code):
    log = ctx["log"]
    wb_h = ctx["wb_h"]
    settled = ("accepted", "completed", "claimed")
    for attempt in (1, 2):
        try:
            c, b = E.post(E.GROWTH_BASE + "/tasks/accept", wb_h, {"task_codes": [code]})
            results = (E.dig(b, "results") or []) if isinstance(b, dict) else []
            status = (results[0].get("status") or "") if results and isinstance(results[0], dict) else ""
            st = E.prog(wb_h, code, fresh=True)[0]
            if _http_ok(c) and st not in settled:
                _sleep(1.5)
                st = E.prog(wb_h, code, fresh=True)[0]
            if _http_ok(c) and (st in settled or status == "already_accepted"):
                return True
        except Exception:
            pass
        if attempt < 2:
            _sleep(1.5)
    log("   ✗ 接单[%s]: 未确认落账" % code)
    return False


# ---------------------------------------------------------------------------
# E. 终态口径 + 有效期提醒
# ---------------------------------------------------------------------------
def summarize_completion(rows, receipts=None):
    """只认 claimed / claimed=true / 本轮确认回执；completed 未领仍算未完成。"""
    receipts = receipts if isinstance(receipts, dict) else {}
    done, rest = 0, []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        code = _row_code(row)
        if not code or code in ctx_campaign_codes():
            continue
        if _row_done(row) or receipts.get(code, {}).get("confirmed"):
            done += 1
        else:
            rest.append(code)
    return done, rest


def ctx_campaign_codes():
    return {s["code"] for s in CAMPAIGN_SPECS} | {"campaign"}


def expiry_reminders(rows, log, receipts=None):
    """终态任务表里 7 天内到期且未领奖的任务提醒；locked / 活动域不混入。"""
    import datetime as _dt
    receipts = receipts if isinstance(receipts, dict) else {}
    today = E.beijing_now().date()
    grouped = {}
    for row in rows or []:
        if isinstance(row, dict) and _row_code(row) and _row_code(row) not in ctx_campaign_codes():
            grouped.setdefault(_row_code(row), []).append(row)
    soon = []
    for code, items in grouped.items():
        if any(_row_done(r) for r in items) or receipts.get(code, {}).get("confirmed"):
            continue
        active = [r for r in items if not r.get("locked")]
        if not active:
            continue
        dates = []
        for r in active:
            v = str(r.get("valid_end") or "")[:10]
            try:
                dates.append((_dt.date(*[int(x) for x in v.split("-")]), v))
            except Exception:
                continue
        if not dates:
            continue
        expiry, v = min(dates, key=lambda x: x[0])
        left = (expiry - today).days
        if left < 0:
            soon.append((code, v, "已过期"))
        elif left <= 7:
            soon.append((code, v, "%d 天后到期" % left))
    if soon:
        log("   ⏰ 任务有效期提醒（未完成/未领奖）:")
        for code, v, when in soon[:6]:
            log("      · %s %s（%s）" % (E.task_cn(code), v, when))
    return soon


# ---------------------------------------------------------------------------
# F. 积分增量统计（数值化"剩余积分合计"）
# ---------------------------------------------------------------------------
def credits_remain(wb_h):
    """返回 (数值合计, 中文明细)；查询失败返回 (None, "")。"""
    try:
        c, b = E.post(E.WORKBUDDY_BASE + "/billing/meter/get-user-resource-summary", wb_h, {})
        if not _http_ok(c) or not isinstance(b, dict):
            return None, ""
        pkgs = (b.get("data") or {}).get("Packages") or []
        total, parts = 0.0, []
        for i, p in enumerate(pkgs):
            if not isinstance(p, dict):
                continue
            try:
                remain = float(p.get("CycleRemainCapacity", 0) or 0)
                allc = float(p.get("CycleTotalCapacity", 0) or 0)
                used = float(p.get("CycleUsedCapacity", 0) or 0)
            except (TypeError, ValueError):
                continue
            total += remain
            parts.append("%s剩余%s(共%s,已用%s)" % (
                "主套餐" if i == 0 else "加量包%d" % i,
                E.fmt_credit(remain), E.fmt_credit(allc), E.fmt_credit(used)))
        return total, "；".join(parts)
    except Exception:
        return None, ""


# ---------------------------------------------------------------------------
# G. 签到分钟级补签队列（跨进程状态，按 UID 哈希隔离，不存凭据）
# ---------------------------------------------------------------------------
def is_retryable_checkin_failure(code, body):
    if code != 500 or not isinstance(body, dict):
        return False
    if E.as_int(body.get("code"), -1) != 10001:
        return False
    return "稍后重试" in str(body.get("msg") or body.get("message") or "")


def sign_retry_maybe_queue(ctx, out):
    """run_checkin 返回后调用；命中 500+10001+稍后重试 则排队 10/40 分钟两轮。"""
    if not UPSTREAM_ON or not isinstance(out, dict):
        return
    raw = out.get("_raw")
    if not is_retryable_checkin_failure(out.get("_http"), raw):
        return
    uid, log = ctx["uid"], ctx["log"]
    key = _uid_key(uid, "sign-retry")
    today = E.beijing_now().date().isoformat()
    data = _state_load(SIGN_RETRY_STATE)
    data = {k: v for k, v in data.items() if isinstance(v, dict) and v.get("day") == today}
    now = int(time.time())
    rec = data.get(key) or {"day": today, "started_at": now, "round": 0}
    rnd = E.as_int(rec.get("round"))
    if rnd >= len(SIGN_RETRY_DELAYS):
        data.pop(key, None)
        log("⏳ 签到补签: 两轮机会已用完，本日不再排队")
    else:
        rec.update({"day": today, "started_at": E.as_int(rec.get("started_at"), now),
                    "round": rnd + 1,
                    "next_at": E.as_int(rec.get("started_at"), now) + SIGN_RETRY_DELAYS[rnd],
                    "last_failure_at": now})
        data[key] = rec
        log("⏳ 签到补签: 服务端「稍后重试」，已排第 %d 轮（约 %d 分钟后到点）"
            % (rnd + 1, SIGN_RETRY_DELAYS[rnd] // 60))
    _state_save(SIGN_RETRY_STATE, data)


def sign_retry_check(ctx):
    """每轮运行开始检查补签队列：到点则先查官方状态，已签即清状态，不再重复补签。"""
    if not UPSTREAM_ON:
        return
    uid, log = ctx["uid"], ctx["log"]
    key = _uid_key(uid, "sign-retry")
    today = E.beijing_now().date().isoformat()
    data = _state_load(SIGN_RETRY_STATE)
    rec = data.get(key)
    if not isinstance(rec, dict) or rec.get("day") != today:
        return
    now = int(time.time())
    if now < E.as_int(rec.get("next_at")):
        wait = max(1, int(math.ceil((E.as_int(rec.get("next_at")) - now) / 60.0)))
        log("⏳ 签到补签: 已排队，约 %d 分钟后到点" % wait)
        return
    try:
        c, b = E.post(ctx["endpoint"] + "/v2/billing/meter/checkin-activity-status", ctx["headers"], retry=True)
        status = (b.get("data") or {}) if isinstance(b, dict) else {}
        if _http_ok(c) and E.dig(b, "today_checked_in") in (True, 1):
            data.pop(key, None)
            _state_save(SIGN_RETRY_STATE, data)
            log("✅ 签到补签: 官方状态显示今日已签，队列已清空")
            return
        _code, out = E.run_checkin(ctx["headers"], ctx["endpoint"])
        log("⏳ 签到补签: 第 %d 轮执行 → %s" % (E.as_int(rec.get("round")) or 1,
                                              (out or {}).get("report", "无回执")))
        if (out or {}).get("result") in ("CLAIMED", "ALREADY"):
            data.pop(key, None)
            _state_save(SIGN_RETRY_STATE, data)
            log("✅ 签到补签: 已完成，队列清空")
        else:
            sign_retry_maybe_queue(ctx, {"_http": out.get("_http"), "_raw": out.get("_raw")})
    except Exception as e:
        log("⏳ 签到补签异常（%s: %s），下轮继续" % (type(e).__name__, str(e)[:60]))


# ---------------------------------------------------------------------------
# H. 一次性福利：补偿 / 新手礼包（billing 域，先查状态 + 本地防重）
# ---------------------------------------------------------------------------
def _benefit_status(wb_h, path):
    for base in (CBDOMAIN, E.WORKBUDDY_BASE):
        c, b = E.post(base + path, wb_h, {})
        if _http_ok(c) and isinstance(b, dict) and _ok(b.get("code")) and isinstance(b.get("data"), dict):
            return b["data"]
        if is_enterprise_denial(c, b):
            raise PermissionError("企业版账号不支持该福利")
    raise RuntimeError("状态回执不可用")


def _benefit_claim(wb_h, path):
    for base in (CBDOMAIN, E.WORKBUDDY_BASE):
        c, b = E.post(base + path, wb_h, {})
        if _http_ok(c):
            return c, b if isinstance(b, dict) else {}
    return 0, {}


def _benefit_guard(kind, uid, deadline):
    key = hashlib.sha256(("v1|%s|%s|%s" % (kind, uid, deadline or "unknown")).encode()).hexdigest()[:24]
    return _state_load(BENEFIT_STATE).get(key)


def _benefit_mark(kind, uid, deadline, result):
    key = hashlib.sha256(("v1|%s|%s|%s" % (kind, uid, deadline or "unknown")).encode()).hexdigest()[:24]
    data = _state_load(BENEFIT_STATE)
    data[key] = {"status": result, "at": int(time.time())}
    _state_save(BENEFIT_STATE, data)


def run_benefits(ctx):
    """补偿 + 新手礼包：只在 active 且未领且本期未处理过时提交一次。"""
    if not want("gift", "benefit"):
        return
    log, wb_h, uid = ctx["log"], ctx["wb_h"], ctx["uid"]
    specs = (("compensation", "/billing/meter/compensation-status",
              "/billing/meter/claim-compensation", "补偿积分"),
             ("gift", "/billing/meter/check-gift-claimed",
              "/billing/meter/claim-gift", "新手礼包"))
    for kind, qpath, cpath, label in specs:
        try:
            cur = _benefit_status(wb_h, qpath)
        except PermissionError:
            log("🏢 %s: 企业版账号不支持" % label)
            continue
        except Exception as e:
            log("⚠️ %s状态查询失败: %s" % (label, str(e)[:60]))
            continue
        if not cur.get("active") or cur.get("claimed"):
            continue
        num = E.as_int(cur.get("credit_num"))
        if num <= 0:
            continue
        deadline = str(cur.get("end_time") or "")
        if _benefit_guard(kind, uid, deadline):
            log("🎊 %s: 本期已处理，跳过重复领取（本地防重）" % label)
            continue
        log("🎊 %s待领取: %s积分%s" % (label, num, "（截止%s）" % deadline if deadline else ""))
        try:
            c, b = _benefit_claim(wb_h, cpath)
        except Exception as e:
            log("⚠️ %s领取请求失败（下轮重试）: %s" % (label, str(e)[:60]))
            continue
        data = b.get("data") if isinstance(b.get("data"), dict) else {}
        actual = data.get("credit")
        msg = str(b.get("msg") or "")
        if _http_ok(c) and _ok(b.get("code")):
            _benefit_mark(kind, uid, deadline, "processed")
            log("✅ %s: +%s积分" % (label, actual if actual is not None else num))
        elif any(m in msg.lower() for m in ("already", "已领取")) or data.get("already_claimed"):
            _benefit_mark(kind, uid, deadline, "already_claimed")
            log("🎊 %s: 已领取" % label)
        else:
            log("⚠️ %s领取未确认: %s（下轮重试）" % (label, msg[:60]))
        _sleep(1)


# ---------------------------------------------------------------------------
# 小程序上报（裸数组事件体，对齐上游 v3.45 修复；本地既有 report_mini_event
# 是 common+events 信封，两者口径不同，故这里单独实现，不动既有链路）
# ---------------------------------------------------------------------------
def _mp_base(uid, nick):
    return {"timestamp": int(time.time() * 1000), "ideType": "WorkBuddy_MP",
            "ideVersion": "2.4.0", "extName": "workbuddy-mp", "extVersion": "2.4.0",
            "product": "SaaS", "ideName": "wx_app_cloud", "platform": "mini_program",
            "source": "mini_program", "os": "android", "osVersion": "14", "arch": "arm64",
            "machineId": E.derive_id(uid, "mp-machine"), "timezone": "Asia/Shanghai",
            "userId": uid, "userNickname": nick}


def mp_report(ctx, events, env_extra=None):
    """裸数组上报 → www.codebuddy.cn/v2/report。返回 HTTP 码。"""
    base = _mp_base(ctx["uid"], ctx["nick"])
    if env_extra:
        base.update(env_extra)
    arr = []
    for ev in events:
        m = dict(base)
        m.update(ev)
        arr.append(m)
    hdr = dict(MP_REPORT_HEADERS)
    hdr["Authorization"] = ctx["headers"].get("Authorization", "")
    if ctx["uid"]:
        hdr["X-User-Id"] = ctx["uid"]
    try:
        return E.post(MP_REPORT_URL, hdr, arr)[0]
    except Exception:
        return 0


def mp_chat_event(conv=None, activity_id=None):
    conv = conv or _new_conv()
    rid = _new_msg()
    ev = {"eventCode": "chat_request_send", "mode": "chat", "inputLength": 12,
          "isPlan": False, "isAutoExecuteTerminal": False, "isAutoModify": False,
          "codebaseEnable": False, "maxToken": 0, "maxSteps": 500, "temperature": 0,
          "maxRetries": 0, "mentionContexts": [], "knowledgeId": [], "knowledgeName": [],
          "codebaseId": "", "mentionContextCount": 0, "command": "", "recommendId": "",
          "skillId": "", "skillCount": 0, "totalCount": 0, "requestId": rid, "traceId": rid,
          "rootRequestId": rid, "parentConversationId": conv, "conversationId": conv,
          "messageId": "msg-" + rid[-8:], "agentName": "mp", "agentType": "main",
          "codebuddy.session_id": conv, "codebuddy.conversation_request_id": rid}
    if activity_id:
        ev["activityId"] = activity_id
    return ev


def mp_expert_events(expert_id, expert_name, conv=None):
    conv = conv or _new_conv()
    rid = _new_msg()
    evs = [
        {"eventCode": "expert_summon_click", "id": expert_id, "name": expert_id,
         "expertTitle": expert_name, "type": MP_EXPERT_CATEGORY, "position": 0},
        {"eventCode": "expert_summoned", "id": expert_id, "name": expert_id,
         "expertTitle": expert_name},
        {"eventCode": "expert_actual_use", "id": expert_id, "name": expert_id,
         "expertTitle": expert_name, "type": MP_EXPERT_CATEGORY,
         "characterCount": 14, "expertType": "builtin"},
        {"eventCode": "chat_request_send", "inputLength": 14, "isPlan": False,
         "conversationId": conv, "parentConversationId": conv, "traceId": rid,
         "rootRequestId": rid, "messageId": "msg-" + rid[-8:], "expertId": expert_id,
         "expertName": expert_name, "codebuddy.session_id": conv,
         "codebuddy.conversation_request_id": rid},
    ]
    return evs


def mp_mini_expert_event(uid, expert_id, expert_name):
    return {"eventCode": "expert_actual_use", "timestamp": int(time.time() * 1000),
            "reportDelay": 0, "ideName": "wx_app_cloud", "ideType": "WorkBuddy_MP",
            "extName": "workbuddy-mp", "extVersion": "2.2.8", "product": "SaaS",
            "source": "mini_program", "os": "android", "osVersion": "14", "arch": "arm64",
            "timezone": "Asia/Shanghai", "userId": uid,
            "machineId": E.derive_id(uid, "mp-machine"),
            "id": expert_id, "name": expert_id, "expertTitle": expert_name,
            "type": "send_message", "characterCount": 12, "expertType": "agent"}


def mp_model_chat_event(conv=None, model=None):
    """指定模型对话事件：默认按免费模型上报，未达标才由调用方回退官方指定模型。"""
    ev = mp_chat_event(conv)
    m = model or E.pick_chat_model()
    ev["requestModelId"] = m
    ev["requestModelName"] = m
    return ev


def mp_automation_event():
    return [{"eventCode": "automated_task_create_suc", "mode": "CLOUD",
             "name": "每日读书提醒", "source": "manually", "skills": "", "skillCount": 0,
             "scheduleType": "daily"}]


def mp_playbook_events(case_id="01-ProductDesign", case_name="产品设计"):
    conv = _new_conv()
    base = {"id": case_id, "name": case_name, "type": "document", "categoryId": "",
            "categoryName": "", "skills": "", "skillNames": ""}
    cta = dict(base, eventCode="playbook_cta_click", source="discover", position=1, extVersion="2.2.8")
    send = dict(base, eventCode="playbook_prompt_send", source="discover", promptLength=96,
                isOfficial=1, conversationId=conv, extVersion="2.2.8")
    return [cta, send]


def _mp_pick_expert(ctx):
    body = {"edition_mode": "all,domestic", "page": 1, "page_size": 20,
            "sort_by": "use_count", "sort_order": "desc",
            "categories": [MP_EXPERT_CATEGORY], "expert_type": "agent"}
    try:
        c, b = E.post(CBDOMAIN + "/v2/operation-platform/market/expert/list", ctx["wb_h"], body)
        if _http_ok(c) and isinstance(b, dict):
            for e in ((b.get("data") or {}).get("experts") or []):
                eid = e.get("expert_id")
                if not eid:
                    continue
                dn = e.get("display_name_zh") or {}
                return eid, (dn.get("zh") if isinstance(dn, dict) else dn) or eid
    except Exception:
        pass
    return "WorkspaceBuilder", "工作台搭建师"


# ---------------------------------------------------------------------------
# I. 小程序活动任务（星巴克 / 记者节）
# ---------------------------------------------------------------------------
def _campaign_headers(ctx):
    hdr = dict(MP_REPORT_HEADERS)
    hdr["Authorization"] = ctx["headers"].get("Authorization", "")
    hdr["X-User-Id"] = ctx["uid"] or ""
    return hdr


def _campaign_call(ctx, method, path, body=None):
    hdr = _campaign_headers(ctx)
    if method == "GET":
        return E.get(CAMPAIGN_BASE + path, hdr)
    return E.post(CAMPAIGN_BASE + path, hdr, body or {})


def campaign_tasks(ctx, camp, log=None):
    c, b = _campaign_call(ctx, "GET", "/portal/activity/tasks?activity_code=" + camp)
    if c != 200 or not isinstance(b, dict) or b.get("code") not in (None, 0, "0"):
        if log:
            log("      ⚠️ 活动任务读取失败[%s]: %s %s" % (camp, E._http_label(c), str(b)[:60]))
        return {}
    data = b.get("data") or {}
    prog = {p.get("task_code"): p for p in (data.get("progress") or []) if isinstance(p, dict)}
    rows = {}
    for t in data.get("tasks") or []:
        if not isinstance(t, dict):
            continue
        code = t.get("task_code")
        p = prog.get(code) or {}
        rows[code] = {"target": t.get("target_count") or 0, "progress": p.get("progress") or 0,
                      "completed_at": p.get("completed_at"), "claimed_at": p.get("claimed_at"),
                      "need_view": t.get("need_view"), "credit": t.get("reward_credit") or 0}
    return rows


def _campaign_claim(ctx, camp, task, credit, log):
    c, b = _campaign_call(ctx, "POST",
                          "/portal/activity/tasks/%s/claim?activity_code=%s" % (task, camp))
    if not (c == 200 and isinstance(b, dict) and _ok(b.get("code"))):
        log("   ⚠️ 活动领奖[%s/%s]: %s %s" % (camp, task, E._http_label(c), str(b)[:60]))
        return False
    for i in range(CAMPAIGN_CLAIM_POLL):
        if i and not _sleep(CAMPAIGN_CLAIM_GAP):
            break
        row = campaign_tasks(ctx, camp, log).get(task) or {}
        if row.get("claimed_at"):
            log("   🎁 活动领奖[%s/%s]: +%s积分" % (camp, task, credit))
            return True
    log("   ⚠️ 活动领奖[%s/%s]: 已提交但未回读到 claimed_at，下轮重试" % (camp, task))
    return False


def _campaign_poll(ctx, camp, code, target, log, tries=None, gap=None):
    cur = 0
    for _ in range(tries or CAMPAIGN_POLL):
        if not _sleep(gap if gap is not None else CAMPAIGN_GAP):
            break
        row = campaign_tasks(ctx, camp, log).get(code) or {}
        cur = row.get("progress") or 0
        if row.get("completed_at") or cur >= target:
            return max(cur, target)
    return cur


def _campaign_skill_events(skill_id, skill_name):
    conv, rid = _new_conv(), _new_msg()
    info = {"eventCode": "skill_info", "id": skill_name, "skillId": skill_id,
            "skillName": skill_name, "skillType": "market", "skillSource": "market",
            "position": 0, "conversationId": conv}
    chat = {"eventCode": "chat_request_send", "inputLength": 14, "isPlan": False,
            "skillId": skill_id, "skillCount": 1, "traceId": rid, "rootRequestId": rid,
            "parentConversationId": conv, "conversationId": conv,
            "messageId": "msg-" + rid[-8:], "codebuddy.session_id": conv,
            "codebuddy.conversation_request_id": rid}
    return [info, chat]


def _campaign_desktop_events(case):
    return [{"eventCode": "playbook_prompt_send", "id": case.get("event_id") or "",
             "name": case.get("name") or "", "type": case.get("type") or "other",
             "promptLength": case.get("prompt_length") or 0, "isOfficial": 1,
             "source": "discover", "query": "", "ext1": "discover",
             "requestId": _new_conv(), "conversationId": _new_conv()}]


def _app_box_url(raw):
    raw = str(raw or "").strip().rstrip("/")
    try:
        p = urllib.parse.urlparse(raw)
        host = (p.hostname or "").rstrip(".").lower()
    except Exception:
        return ""
    if p.scheme != "https" or not host or p.username or p.password or p.port not in (None, 443):
        return ""
    if not any(host == d or host.endswith("." + d) for d in CAMPAIGN_APP_BOX_DOMAINS):
        return ""
    return raw


def _campaign_app_chat(ctx, log):
    """app 判据：真实跑完一轮云端 agentos 会话（不伪造设备 / 不绕过风控）。"""
    token = (ctx["headers"].get("Authorization") or "").replace("Bearer ", "").strip()
    if not token:
        return False
    uid, nick = ctx["uid"], ctx["nick"]
    app_hdr = {"Authorization": "Bearer " + token, "X-User-Id": uid,
               "User-Agent": "WorkBuddyApp/2.8.0", "X-Client-Version": "2.8.0",
               "X-Client-Product": "workbuddy-app", "X-Client-Platform": "android",
               "Accept": "application/json", "Content-Type": "application/json"}
    try:
        c, b = E.post(APP_HOST + "/v2/as/conversations/", app_hdr,
                      {"name": "开始新对话", "conversationOrigin": "agents"})
        sess = ((b.get("data") or {}).get("session") or {}) if isinstance(b, dict) else {}
        box, box_tok = sess.get("boxUrl") or "", sess.get("token") or ""
        if not _http_ok(c) or not box or not box_tok:
            log("      ✗ App 会话: 建会话失败 %s" % E._http_label(c))
            return False
        box = _app_box_url(box)
        if not box:
            log("      ✗ App 会话: boxUrl 非受信任官方域名，已拒绝发送令牌")
            return False
        info = {"ideType": "WorkBuddy_APP", "ideName": "app_cloud", "ideVersion": "2.8.0",
                "extName": "WorkBuddy_APP", "extVersion": "2.8.0",
                "machineId": hashlib.sha1(("workbuddy-app-machine:%s" % uid).encode()).hexdigest()[:8],
                "userId": uid, "userNickname": nick}
        meta = {"codebuddy.ai": {"telemetryClientInfo": info}}
        body = {
            "initialize": {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                           "params": {"protocolVersion": 1, "clientCapabilities": {},
                                      "clientInfo": {"name": "WorkBuddyApp", "version": "2.8.0"}}},
            "sessionNew": {"jsonrpc": "2.0", "id": 2, "method": "session/new",
                           "params": {"cwd": "/workspace", "mcpServers": [], "_meta": meta}},
            "prompt": {"jsonrpc": "2.0", "id": 3, "method": "session/prompt",
                       "params": {"prompt": [{"type": "text", "text": '你只需要回复"Hi"'}],
                                  "_meta": meta}},
        }
        bh = {"Authorization": "Bearer " + box_tok, "X-User-Id": uid,
              "User-Agent": "WorkBuddyApp/2.8.0", "X-Client-Version": "2.8.0",
              "X-Client-Product": "workbuddy-app", "X-Client-Platform": "android",
              "Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        c, text = E._post_stream(box + "/acp/bootstrap?includeUserEcho=true", bh, body,
                                 timeout=min(60, max(20, int(_layer_left() - 5))))
        if not _http_ok(c):
            log("      ✗ App 会话: bootstrap %s" % E._http_label(c))
            return False
        # 只认结构化 end_turn；EOF / 截断 / 超时 / 错误事件均判失败
        if re.search(r'"stopReason"\s*:\s*"end_turn"', text or "") and '"error"' not in (text or ""):
            log("      ✅ App 会话: 真跑完一轮对话（end_turn）")
            return True
        log("      ✗ App 会话: 未收到有效 end_turn，本轮不伪造判据")
        return False
    except Exception as e:
        log("      ✗ App 会话异常（%s），下轮重试" % type(e).__name__)
        return False


def _campaign_fire(ctx, spec, task, log):
    kind = task.get("kind")
    page = spec.get("page")
    if kind == "chat":
        return mp_report(ctx, [mp_chat_event()], env_extra=page) == 200
    if kind == "expert":
        eid, ename = task.get("expert_id"), task.get("expert_name")
        if not eid:
            eid, ename = _mp_pick_expert(ctx)
        return mp_report(ctx, mp_expert_events(eid, ename), env_extra=page) == 200
    if kind == "skill":
        return mp_report(ctx, _campaign_skill_events(
            task.get("skill_id"), task.get("skill_name")), env_extra=page) == 200
    if kind == "desktop":
        if SKIP_DESKTOP_SIM:
            log("      ⏭️ %s: 按 WORKBUDDY_SKIP_DESKTOP_SIM 跳过（需真机灵感）" % task["label"])
            return False
        case = CAMPAIGN_CASES.get(task.get("case_id") or "content-calendar")
        if not case:
            return False
        return E.report_events(ctx["wb_h"], ctx["uid"], ctx["nick"],
                               _campaign_desktop_events(case)) == 200
    if kind == "app":
        if SKIP_DESKTOP_SIM:
            log("      ⏭️ %s: 按 WORKBUDDY_SKIP_DESKTOP_SIM 跳过" % task["label"])
            return False
        return _campaign_app_chat(ctx, log)
    return False


def run_campaigns(ctx):
    """活动任务：完成≠到账，completed 后必须 claim 并回读 claimed_at。"""
    if not want("campaign"):
        return 0
    log = ctx["log"]
    ctx["_campaign_codes"] = ctx_campaign_codes()
    gained = 0
    for spec in CAMPAIGN_SPECS:
        camp = spec["code"]
        if not want("campaign", camp):
            continue
        try:
            rows = campaign_tasks(ctx, camp, log)
            if not rows:
                log("   ⏭️ %s: 活动任务未下发/已结束" % spec["label"])
                continue
            log("   🎪 %s（%s）" % (spec["label"], camp))
            for task in spec["tasks"]:
                code = task["task"]
                row = rows.get(code) or {}
                if not row:
                    log("      ⏭️ %s: 未下发/已下线" % task["label"])
                    continue
                target = row.get("target") or task.get("times") or 1
                credit = row.get("credit") or task.get("credit") or 0
                if row.get("claimed_at"):
                    log("      ✅ %s: 已领奖（%s/%s）" % (task["label"], target, target))
                    continue
                if row.get("completed_at"):
                    if _campaign_claim(ctx, camp, code, credit, log):
                        gained += credit
                    continue
                if row.get("need_view", True):
                    _campaign_call(ctx, "POST",
                                   "/portal/activity/tasks/%s/viewed?activity_code=%s" % (code, camp))
                cur = row.get("progress") or 0
                kind = task.get("kind")
                if kind in ("app", "desktop"):
                    if not _campaign_fire(ctx, spec, task, log):
                        log("      ⚠️ %s: 触发失败，下轮重试" % task["label"])
                        continue
                    wait = CAMPAIGN_APP_WAIT if kind == "app" else CAMPAIGN_DESKTOP_WAIT
                    poll = CAMPAIGN_APP_POLL if kind == "app" else CAMPAIGN_DESKTOP_POLL
                    cur = _campaign_poll(ctx, camp, code, target, log,
                                         tries=max(2, wait // poll), gap=poll)
                else:
                    for _ in range(max(1, target - cur)):
                        if cur >= target:
                            break
                        if not _campaign_fire(ctx, spec, task, log):
                            break
                        cur = _campaign_poll(ctx, camp, code, target, log)
                    if cur < target:
                        cur = _campaign_poll(ctx, camp, code, target, log,
                                             tries=CAMPAIGN_SLOW_POLL, gap=CAMPAIGN_SLOW_GAP)
                row = campaign_tasks(ctx, camp, log).get(code) or {}
                if not (row.get("completed_at") or cur >= target):
                    log("      ⏳ %s: 判据延迟未落库（%s/%s），下轮自动补领"
                        % (task["label"], cur, target))
                    continue
                log("      ✅ %s: completed %s/%s" % (task["label"], target, target))
                if _campaign_claim(ctx, camp, code, credit, log):
                    gained += credit
        except Exception as e:
            log("   ⚠️ %s 异常（%s: %s）" % (spec["label"], type(e).__name__, str(e)[:70]))
    if gained:
        log("   🎪 活动任务本轮入账 %s 积分" % gained)
    ctx.setdefault("extras", {})["campaign_credit"] = gained
    return gained


# ---------------------------------------------------------------------------
# J. 分享技能实链 skill_share
# ---------------------------------------------------------------------------
def _market_skill(ctx):
    c, b = E.post(CBDOMAIN + "/v2/operation-platform/market/skill/list",
                  ctx["wb_h"], {"page": 1, "page_size": 20})
    if not _http_ok(c) or not isinstance(b, dict) or not _ok(b.get("code")):
        return None
    for row in ((b.get("data") or {}).get("skills") or []):
        if not isinstance(row, dict):
            continue
        sid = str(row.get("skill_id") or row.get("id") or "").strip()
        name = str(row.get("display_name_zh") or row.get("name") or row.get("display_name_en") or "").strip()
        if sid and name:
            return {"id": sid, "name": name,
                    "description": str(row.get("description_zh") or row.get("description") or "")[:60]}
    return None


def _create_share_channel(ctx, skill):
    body = {"asset_kind": "skill", "asset_source": "market",
            "asset_ref": json.dumps({"asset_id": skill["id"]}, separators=(",", ":")),
            "ways": ["link", "wxacode", "wxapath"],
            "extra": {"name": skill.get("name") or "技能", "description": skill.get("description") or "",
                      "shareKey": skill["id"], "marketplaceSource": "builtin-market"}}
    hdr = {"Authorization": ctx["headers"].get("Authorization", ""),
           "X-User-Id": ctx["uid"] or "", "X-Domain": "copilot.tencent.com",
           "Content-Type": "application/json", "Accept": "application/json, text/plain, */*",
           "User-Agent": E.UA_SHORT}
    try:
        c, b = E.post(SKILL_SHARE_URL, hdr, body, timeout=30)
    except Exception as e:
        return {"success": False, "message": str(e)[:60]}
    if not _http_ok(c) or not isinstance(b, dict) or not _ok(b.get("code")):
        return {"success": False, "http": c, "message": str(b.get("msg") if isinstance(b, dict) else "")[:70]}
    data = b.get("data") or {}
    share_code = str(data.get("share_code") or "").strip()
    link = ""
    for w in data.get("ways") or []:
        if isinstance(w, dict) and w.get("share_way") == "link":
            link = str(w.get("resource_ref") or "").strip()
            break
    if not share_code or not link:
        return {"success": False, "message": "回执缺少 share_code/link"}
    return {"success": True, "shareCode": share_code}


def run_skill_share(ctx):
    """分享技能给好友：创建真实渠道 → 官方事件族 → 回读进度 → 只达标才领奖。"""
    if not want("skill_share"):
        return
    log, wb_h = ctx["log"], ctx["wb_h"]
    code = "skill_share"
    try:
        st, cur, tgt = E.prog(wb_h, code, fresh=True)
        if st is None:
            log("   分享技能: 桌面任务列表未下发，跳过")
            return
        if st in ("claimed",) or _row_done({"accept_status": st}):
            log("   分享技能: 已领取，跳过")
            return
        if st == "completed" or (E.as_int(cur) >= E.as_int(tgt) and E.as_int(tgt) > 0):
            log("   分享技能: 已达标，补领奖励")
            claim_confirmed(ctx, code)
            return
        if st in ("", "not_accepted") and not accept_with_verify(ctx, code):
            log("   分享技能: 接受任务失败，跳过")
            return
        skill = _market_skill(ctx)
        if not skill:
            log("   分享技能: 市场列表未返回可分享技能，不伪造分享")
            return
        res = _create_share_channel(ctx, skill)
        if not res.get("success"):
            log("   分享技能: 创建渠道失败 %s" % str(res.get("message") or "")[:60])
            return
        now = int(time.time() * 1000)
        common = {"skillId": skill["id"], "skillName": skill["name"], "skillType": "market"}
        events = [
            dict(common, eventCode="skill_share_channel_action", action="link",
                 panelAction="click", panelType="clipboard", isSuccessful=True,
                 cost=0, id=res["shareCode"], actionAt=now),
            dict(common, eventCode="skill_share_channel_action", action="link",
                 panelAction="success", panelType="clipboard", isSuccessful=True,
                 cost=0, id=res["shareCode"], actionAt=now),
        ]
        rc = E.report_desktop_events(wb_h, ctx["uid"], ctx["nick"], events)
        if not _http_ok(rc):
            log("   分享技能: 渠道已创建但事件上报失败 %s，不领奖" % E._http_label(rc))
            return
        for _ in range(4):
            st, cur, tgt = E.prog(wb_h, code, fresh=True)
            if st in ("completed", "claimed") or (E.as_int(tgt) > 0 and E.as_int(cur) >= E.as_int(tgt)):
                break
            if not _sleep(3):
                break
        if st == "completed" or (E.as_int(tgt) > 0 and E.as_int(cur) >= E.as_int(tgt)):
            log("   分享技能: ✅ %s %s/%s" % (skill["name"], cur, tgt))
            claim_confirmed(ctx, code)
        elif st == "claimed":
            log("   分享技能: 已领取")
        else:
            log("   分享技能: 已创建真实渠道，但进度未点亮 %s/%s，不领奖" % (cur, tgt))
    except Exception as e:
        log("   分享技能异常（%s: %s）" % (type(e).__name__, str(e)[:70]))


# ---------------------------------------------------------------------------
# K. 小程序连续任务 2~7（mp 口径，带真人节奏 + 预算守卫）
# ---------------------------------------------------------------------------
SEQUENTIAL = [
    ("Sequential_Tasks_2", "小程序专家对话", "expert_mini", 1, False),
    ("Sequential_Tasks_3", "小程序对话×5", "chat", 5, True),
    ("Sequential_Tasks_4", "小程序定时任务", "automation", 1, False),
    ("Sequential_Tasks_5", "小程序GLM5.2", "model", 1, True),
    ("Sequential_Tasks_6", "小程序对话×10", "chat", 10, True),
    ("Sequential_Tasks_7", "PC灵感功能", "playbook", 1, False),
]


def _seq_events(ctx, kind, model=None):
    """按任务类型构造官方事件；model=None 表示一律先用免费模型。"""
    if kind == "chat":
        return [mp_chat_event()]
    if kind == "expert_mini":
        eid, ename = _mp_pick_expert(ctx)
        return [mp_mini_expert_event(ctx["uid"], eid, ename)]
    if kind == "automation":
        return mp_automation_event()
    if kind == "model":
        return [mp_model_chat_event(model=model)]
    if kind == "playbook":
        return mp_playbook_events()
    return []


def _mp_task_row(ctx, code):
    c, b = E.get(E.GROWTH_BASE + "/tasks", ctx["mp_h"])
    if _http_ok(c) and isinstance(b, dict):
        for t in (b.get("data") or {}).get("tasks") or []:
            if isinstance(t, dict) and _row_code(t) == code:
                return t
    return None


def run_sequential(ctx):
    """mp 口径：未下发/已领/锁定/需真机判据一律跳过；达标即领奖。"""
    log = ctx["log"]
    for code, label, kind, fallback_target, pace in SEQUENTIAL:
        if not want(code, "sequential"):
            continue
        if kind == "playbook" and SKIP_DESKTOP_SIM:
            log("   %s: 按 WORKBUDDY_SKIP_DESKTOP_SIM 跳过（需 PC 灵感判据）" % label)
            continue
        try:
            row = _mp_task_row(ctx, code)
            if row is None:
                continue   # 未下发，静默跳过（避免刷屏）
            if row.get("locked"):
                log("   %s: 未到上线时间，跳过" % label)
                continue
            st = _row_status(row)
            pr = row.get("progress") or {}
            cur, tgt = E.as_int(pr.get("current")), E.as_int(pr.get("target"))
            if _row_done(row):
                continue
            if st == "completed" or (tgt > 0 and cur >= tgt):
                log("   %s: 已达标，补领奖励" % label)
                claim_confirmed(ctx, code, mp=True)
                continue
            if st in ("", "not_accepted"):
                c, b = E.post(E.GROWTH_BASE + "/tasks/accept", ctx["mp_h"], {"task_codes": [code]})
                results = E.dig(b, "results") or [] if isinstance(b, dict) else []
                status = (results[0].get("status") or "") if results and isinstance(results[0], dict) else ""
                if not (_http_ok(c) and status in ("accepted", "already_accepted")):
                    log("   %s: 接单未确认，跳过" % label)
                    continue
                _sleep(E.WRITE_GAP)
                row = _mp_task_row(ctx, code) or {}
                pr = row.get("progress") or {}
                cur, tgt = E.as_int(pr.get("current")), E.as_int(pr.get("target"))
            if tgt <= 0:
                tgt = fallback_target
            need = max(1, tgt - cur)
            sent = 0

            def _round(model):
                """按指定模型（None=免费模型优先）上报一轮，带真人节奏与时间盒。"""
                nonlocal sent
                for i in range(need):
                    if pace and MP_CHAT_GAP > 0 and not _sleep(MP_CHAT_GAP):
                        break
                    evs = _seq_events(ctx, kind, model)
                    if not evs:
                        break
                    rc = mp_report(ctx, evs)
                    if rc == 200:
                        sent += len(evs)
                    if i < need - 1 and not pace:
                        _sleep(E.WRITE_GAP)
                _sleep(2.5)

            def _readback():
                r = _mp_task_row(ctx, code) or {}
                p = r.get("progress") or {}
                return (_row_status(r), E.as_int(p.get("current")),
                        E.as_int(p.get("target")) or tgt)

            _round(None)   # 所有任务一律先按免费模型（E.pick_chat_model）
            st2, cur2, tgt2 = _readback()
            # 指定模型类任务：免费模型未达标才回退官方指定模型（与 t_chat_n 同策略）
            if kind == "model" and not (st2 == "completed" or (tgt2 > 0 and cur2 >= tgt2)):
                log("   %s: 免费模型未达标，回退指定模型 glm-5.2 补一轮" % label)
                _round("glm-5.2")
                st2, cur2, tgt2 = _readback()
            if st2 == "completed" or (tgt2 > 0 and cur2 >= tgt2):
                log("   %s: ✅ 已完成 %s/%s（上报 %d 事件）" % (label, cur2, tgt2, sent))
                claim_confirmed(ctx, code, mp=True)
            else:
                log("   %s: %s %s/%s（服务端暂未关联，下轮继续）" % (label, st2, cur2, tgt2))
        except Exception as e:
            log("   %s异常（%s: %s）" % (label, type(e).__name__, str(e)[:60]))


# ---------------------------------------------------------------------------
# L. 智能补签候选（只读诊断；实际用卡由本地 g_makeup 负责，避免双花）
# ---------------------------------------------------------------------------
def makeup_candidates(ctx):
    try:
        _, sb = E.get(E.GROWTH_BASE + "/streak", ctx["wb_h"])
        _, hb = E.get(E.GROWTH_BASE + "/heatmap", ctx["wb_h"])
        today = E.beijing_now().date()
        streak = E.dig(sb, "streak") or {}
        made_up = set()
        if isinstance(streak, dict):
            for v in streak.get("makeup_dates") or []:
                if isinstance(v, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
                    made_up.add(v)
        cells = E.dig(hb, "cells") or []
        scores = {}
        for cell in cells if isinstance(cells, list) else []:
            if not isinstance(cell, dict) or not cell.get("date"):
                continue
            try:
                d = datetime.date.fromisoformat(str(cell["date"])[:10])
                scores[d] = float(cell.get("score") or 0)
            except Exception:
                continue
        start = max(today.replace(day=1), datetime.date(2026, 6, 17))
        return sorted((d.isoformat() for d, s in scores.items()
                       if start <= d < today and s == 0 and d.isoformat() not in made_up), reverse=True)
    except Exception:
        return []


# ---------------------------------------------------------------------------
# M. 会话数上限清理（10105）
# ---------------------------------------------------------------------------
def prune_conversations(ctx):
    try:
        c, b = E.get(E.WORKBUDDY_BASE + "/console/webchat/conversations?page=1&pageSize=50", ctx["wb_h"])
        if not _http_ok(c) or not isinstance(b, dict):
            return 0
        rows = (b.get("data") or {}).get("conversations") or []
        active = [r for r in rows if isinstance(r, dict)
                  and str(r.get("status") or "").lower() in ("working", "creating", "pending")]
        if len(active) < 10:
            return 0
        active.sort(key=lambda r: str(r.get("createdAt") or ""))
        stopped = 0
        for r in active:
            if len(active) - stopped <= 8:
                break
            cid = r.get("conversationId") or r.get("id")
            if not cid:
                continue
            url = (E.WORKBUDDY_BASE + "/console/webchat/conversations/"
                   + urllib.parse.quote(str(cid), safe="") + "/stop")
            cc, _ = E.post(url, ctx["wb_h"], {})
            if _http_ok(cc):
                stopped += 1
        if stopped:
            ctx["log"]("🧹 会话清理: 停掉 %d 个最旧活跃会话（账号级上限）" % stopped)
        return stopped
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# N. 每日活跃上报（点亮成长中心热力墙；签到只给积分不点热力墙）
# ---------------------------------------------------------------------------
def run_daily_activity(ctx):
    if not want("activity"):
        return
    try:
        today = E.beijing_now().date().isoformat()
        key = _uid_key(ctx["uid"], "activity")
        state = _state_load(ACTIVITY_STATE)
        if state.get(key) == today:
            return
        ev = {"eventCode": "chat_request_send", "mode": "craft",
              "conversationId": _new_conv(), "requestId": _new_msg(),
              "inputLength": 12, "requestModelId": "deepseek-v4-flash",
              "requestModelName": "DeepSeek V4 Flash", "isPlan": False,
              "maxToken": 0, "maxSteps": 0, "temperature": 0}
        rc = E.report_events(ctx["wb_h"], ctx["uid"], ctx["nick"], [ev])
        if _http_ok(rc):
            state[key] = today
            _state_save(ACTIVITY_STATE, {k: v for k, v in state.items()
                                         if isinstance(v, str) and v >= E.beijing_now().date().replace(day=1).isoformat()})
            ctx["log"]("🔥 每日活跃: 已上报（点亮成长中心热力墙）")
        else:
            ctx["log"]("🔥 每日活跃: 上报 %s，下轮重试" % E._http_label(rc))
    except Exception as e:
        ctx["log"]("🔥 每日活跃异常（%s: %s）" % (type(e).__name__, str(e)[:60]))


# ---------------------------------------------------------------------------
# O. 多通道推送（配置才生效；未配置静默回落到本地 notify_user）
# ---------------------------------------------------------------------------
def notify_all(title, content):
    import urllib.request
    targets = []
    bark = os.environ.get("BARK_URL", "").strip()
    if bark:
        targets.append((bark.rstrip("/") + "/" + urllib.parse.quote(title) + "/"
                        + urllib.parse.quote(content[:1500]), None))
    sckey = os.environ.get("SERVERCHAN_KEY", "").strip()
    if sckey:
        targets.append(("https://sctapi.ftqq.com/%s.send" % sckey,
                        {"title": title, "desp": content}))
    dd = os.environ.get("DINGTALK_WEBHOOK", "").strip()
    if dd:
        targets.append((dd, {"msgtype": "text", "text": {"content": title + "\n\n" + content}}))
    wecom = os.environ.get("WECOM_WEBHOOK", "").strip()
    if wecom:
        targets.append((wecom, {"msgtype": "text", "text": {"content": title + "\n\n" + content}}))
    wx = os.environ.get("WXPUSHER_APP_TOKEN", "").strip()
    wx_uids = os.environ.get("WXPUSHER_UIDS", "").strip()
    if wx and wx_uids:
        targets.append(("https://wxpusher.zjiecode.com/api/send/message",
                        {"appToken": wx, "uids": [u.strip() for u in wx_uids.split(",") if u.strip()],
                         "content": title + "\n\n" + content, "contentType": 1}))
    if not targets:
        return 0
    sent = 0
    for url, payload in targets:
        try:
            data = None
            hdr = {"User-Agent": "WorkBuddy/Upstream"}
            if payload is not None:
                data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                hdr["Content-Type"] = "application/json"
            req = urllib.request.Request(url, data=data, headers=hdr,
                                         method="POST" if payload is not None else "GET")
            with urllib.request.urlopen(req, timeout=10) as resp:
                if 200 <= resp.status < 300:
                    sent += 1
        except Exception:
            pass
    return sent


# ---------------------------------------------------------------------------
# 主挂接：由 wb_engine.run_full 调用（每步独立隔离）
# ---------------------------------------------------------------------------
def run_extras(ctx):
    """成长任务之后、领奖之前：新增任务能力。单项异常绝不影响其他项。"""
    global _LAYER_DEADLINE
    if not UPSTREAM_ON:
        return
    log = ctx["log"]
    _LAYER_DEADLINE = time.monotonic() + LAYER_BUDGET_SECONDS
    steps = (
        ("每日活跃", run_daily_activity),
        ("一次性福利", run_benefits),
        ("分享技能", run_skill_share),
        ("小程序活动", run_campaigns),
        ("小程序连续任务", run_sequential),
        ("会话清理", lambda c: prune_conversations(c)),
        ("智能补签诊断", lambda c: log("🩹 可补签候选: %s" % ("、".join(makeup_candidates(c)[:5]) or "无")
                                   if makeup_candidates(c) else "🩹 可补签候选: 无漏签")),
    )
    try:
        for name, fn in steps:
            if _layer_left() <= 15 or E._budget_left() <= 15:
                log("⏳ 本轮时间盒将尽，「%s」及后续新增能力下轮再跑" % name)
                break
            try:
                fn(ctx)
            except Exception as e:
                log("「%s」异常（%s: %s）" % (name, type(e).__name__, str(e)[:80]))
    finally:
        _LAYER_DEADLINE = 0.0


def finalize(ctx, rows):
    """领奖之后：终态口径校正 + 有效期提醒 + 积分增量 + 推送。"""
    if not UPSTREAM_ON:
        return
    log, summary = ctx["log"], ctx["summary"]
    receipts = ctx.get("_receipts", {})
    try:
        expiry_reminders(rows, log, receipts)
    except Exception:
        pass
    try:
        after, detail = credits_remain(ctx["wb_h"])
        before = summary.get("credits_before")
        summary["credits_after"] = after
        if isinstance(before, (int, float)) and isinstance(after, (int, float)):
            delta = after - before
            summary["credits_delta"] = delta
            sign = "+" if delta >= 0 else ""
            log("💰 增量: %s%s 积分（%s → %s）%s" % (
                sign, E.fmt_credit(delta), E.fmt_credit(before), E.fmt_credit(after),
                "；" + detail if detail else ""))
        elif detail:
            log("💰 积分明细: %s" % detail)
    except Exception as e:
        log("💰 增量统计异常（%s: %s）" % (type(e).__name__, str(e)[:60]))
    try:
        if os.environ.get("WORKBUDDY_UPSTREAM_NOTIFY", "").strip() in ("1", "true"):
            title = "WorkBuddy 自动签到报告"
            body = "积分增量: %s\n%s" % (summary.get("credits_delta", "?"),
                                      summary.get("checkin", ""))
            n = notify_all(title, body)
            if n:
                log("📢 推送: %d 个渠道" % n)
    except Exception:
        pass


def self_probe(ctx):
    """只读自检：逐项验证合入能力依赖的接口是否可达（不接单/不领奖/不上报）。"""
    log, out = ctx["log"], []
    checks = (
        ("成长 profile", lambda: E.get(E.WORKBUDDY_BASE + "/v2/activity/growth/profile", ctx["wb_h"])[0]),
        ("成长任务(桌面)", lambda: E.get(E.GROWTH_BASE + "/tasks", ctx["wb_h"])[0]),
        ("成长任务(小程序)", lambda: E.get(E.GROWTH_BASE + "/tasks", ctx["mp_h"])[0]),
        ("等级任务", lambda: E.get(E.WORKBUDDY_BASE + "/activity/growth/tasks", ctx["wb_h"])[0]),
        ("积分套餐", lambda: E.post(E.WORKBUDDY_BASE + "/billing/meter/get-user-resource-summary", ctx["wb_h"], {})[0]),
        ("福利-补偿状态", lambda: E.post(CBDOMAIN + "/billing/meter/compensation-status", ctx["wb_h"], {})[0]),
        ("福利-礼包状态", lambda: E.post(CBDOMAIN + "/billing/meter/check-gift-claimed", ctx["wb_h"], {})[0]),
        ("技能市场", lambda: E.post(CBDOMAIN + "/v2/operation-platform/market/skill/list", ctx["wb_h"], {"page": 1, "page_size": 20})[0]),
        ("活动-星巴克", lambda: _campaign_call(ctx, "GET", "/portal/activity/tasks?activity_code=campaign_starbucks_2026")[0]),
        ("活动-记者节", lambda: _campaign_call(ctx, "GET", "/portal/activity/tasks?activity_code=campaign_reporter_2026")[0]),
        ("会话列表", lambda: E.get(E.WORKBUDDY_BASE + "/console/webchat/conversations?page=1&pageSize=50", ctx["wb_h"])[0]),
    )
    for name, fn in checks:
        try:
            c = fn()
            ok = _http_ok(c)
            out.append((name, ok, c))
            log("   %s %-18s %s" % ("✅" if ok else "❌", name, E._http_label(c)))
        except Exception as e:
            out.append((name, False, type(e).__name__))
            log("   ❌ %-18s %s: %s" % (name, type(e).__name__, str(e)[:40]))
    good = sum(1 for _, ok, _ in out if ok)
    log("🔎 上游合入自检: %d/%d 接口可达" % (good, len(out)))
    return out


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import workbuddy_auto as A
    E.DEFAULT_BUDGET_SECONDS = 900
    uin, session = A.load_session()
    if not session:
        print("NO_SESSION（未找到凭据）")
        sys.exit(0)
    headers = E.build_headers(session)
    acc = session.get("account") or {}
    ctx = {"headers": headers, "wb_h": E.wb_headers(headers), "mp_h": E.mp_headers(headers),
           "uid": str(acc.get("uid") or ""), "nick": str(acc.get("nickname") or uin),
           "endpoint": (session.get("auth") or {}).get("endpoint") or E.DEFAULT_ENDPOINT,
           "log": lambda m: print(m, flush=True), "mode": "query", "summary": {}}
    E._start_budget()
    action = sys.argv[1] if len(sys.argv) > 1 else "probe"
    if action == "probe":
        self_probe(ctx)
    elif action == "snapshot":
        print(json.dumps({k: (sorted(v) if isinstance(v, set) else v)
                          for k, v in build_snapshot(ctx).items()}, ensure_ascii=False, indent=2, default=str))
    else:
        print("用法: python3.11 wb_upstream.py [probe|snapshot]")
