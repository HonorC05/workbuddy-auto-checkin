#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# =================================================================================
#  WorkBuddy 积分自动化引擎 (wb_engine.py)  ——  第三方逆向脚本（派生作品 / Derivative Work）
#
#  本文件派生自以下开源项目（均基于 MIT 许可证）：
#    · xz0609/workbuddy-checkin-ql   https://github.com/xz0609/workbuddy-checkin-ql
#        （该项目本身基于 L0NE-6/WorkBuddy-Daily，
#          https://github.com/L0NE-6/WorkBuddy-Daily）
#    · L0NE-6/WorkBuddy-Daily        https://github.com/L0NE-6/WorkBuddy-Daily
#
#  本仓库沿用 MIT 许可证，保留原作者版权声明；本仓库的修改与新增部分版权归
#  本仓库维护者所有。完整许可文本见仓库根目录 LICENSE；第三方来源与版权归属
#  见 NOTICE。
#
#  免责声明：本脚本为第三方逆向实现，与 WorkBuddy / 腾讯官方无关；接口可能随时
#            失效，仅供个人学习与研究使用，请遵守相关平台规则与当地法律法规。
# =================================================================================
"""
WorkBuddy 全能签到 · 单文件零依赖引擎（仅 Python 标准库）。

全流程：Token 自动续期 → 积分/用量/成长查询 → 每日签到 → 18 项成长任务（17 全自动）
        → 8 项互动玩法 → 5 项开学季任务 + 大转盘抽奖 → 3 项小程序任务 → 自动领奖 → 中文报告推送

用法：
  python workbuddy_checkin.py            全流程（默认：签到 + 成长中心 + 玩法 + 开学季 + 推送）
  python workbuddy_checkin.py growth     仅成长中心 + 互动玩法（不签到）
  python workbuddy_checkin.py school     仅开学季活动 + 小程序任务
  python workbuddy_checkin.py query      仅查询积分/用量/成长
  python workbuddy_checkin.py refresh    仅刷新 Token（RT 轮换并回写 auths/*.json）
  python workbuddy_checkin.py login      读取本机登录态，导入到 auths/<uid>.json（本地执行）
  python workbuddy_checkin.py status     查签到状态（调试）
  python workbuddy_checkin.py claim      仅领取签到（调试，幂等）
  python workbuddy_checkin.py all        状态 + 领取（调试）

凭证管理：
  - 本地导入：python workbuddy_checkin.py login 读取
      %LOCALAPPDATA%\\CodeBuddyExtension\\Data\\Public\\auth\\workbuddy-desktop-ai.info
    （新版桌面端；旧版为 workbuddy-desktop.info，JSON 格式），以 account.uid 的值作为
    文件名保存到脚本根目录 auths/<uid>.json。
  - 自动解密：2026-09 起 5.6.x 桌面端会把凭证字段加密为 $wbEncrypted 信封
    （AES-256-GCM at-rest 加密，密钥内嵌于定制 Electron 二进制）。login 检测到加密
    字段时，自动以 ELECTRON_RUN_AS_NODE 模式调用本机 WorkBuddy.exe 取出构建密钥
    完成解密，保存明文凭证供青龙使用；接口请求/响应不受影响（明文请求返回明文）。
  - 青龙读取：仅读取脚本同目录 auths/<uid>.json 文件（JSON 格式）作为账号凭证，
    不读任何 Token 环境变量；多个 auths/*.json 文件视为多个账号，并行执行（threading，
    各账号在独立线程里随机延时 + 运行全流程）。
  - Token 永续：accessToken 7 天内过期（或缺失）时自动用 refreshToken 走官方刷新接口
    轮换新令牌并回写 auths/<uid>.json，形成永续循环，无需反复重新 login。

任务覆盖（共 35 项，33 项全自动）：
  ✅ 每日签到（连签 / 累计积分）
  ☁️ 成长中心任务（18 项，17 全自动）：设计创意模式 · 探索优秀灵感 · 桌面端对话
     · 尝鲜热门技能 · 体验资料库 · 腾讯轻量云专家 · 和平精英主题 · 发现应用 · 企鹅教师助手
     · GLM-5.2 模型对话 · 和AI聊天5次 · 夜猫子活动 · 召唤3次专家团 · 召唤5次专家 · 使用5个模板
     · 设置自动化任务 · 领取Buddy · 公益专家（需真实捐款，人工环节）
     （另：工作台搭建师需 Windows 真实桌面端，无头环境无法点亮，不计入覆盖）
  🎮 互动玩法（8 项）：抽奖 · 盲盒 · Buddy 信息 · 派猫猫旅行 · 连签兑换 · 补签卡 · 礼包补偿 · 徽章
  🏫 开学季活动（5 项，4 全自动 + 大转盘抽奖）：分享活动 · AI 对话3次 · 桌面端对话 · 开学季专家
     （学生认证需微信实名，人工环节）
  📱 小程序任务（3 项）：小程序内完成 1 次对话 · 参与校园日有奖活动 · 新任务自动适配
     （mp 口径出现未知小程序任务时自动接单 + 上报 + 领奖）

实现说明（无头环境如何点亮"桌面端"任务）：
  桌面端对话 / 尝鲜热门技能 / 开学季桌面对话等任务走「稳定设备指纹 + 多域事件上报」：
  由 uid 经 md5 派生固定 machineId/sessionId，按官方客户端的事件契约向桌面域 / Web 域 /
  小程序域三通道上报遥测事件，无需安装任何桌面端。真实 AI 对话类任务（GLM-5.2、聊天5次、
  专家团、夜猫子）走官方 Web 对话接口真实发起。

环境变量（可选）：
  - WORKBUDDY_BUDGET_SECONDS  单账号请求时间预算（秒），默认 900（全流程含真实对话，比纯签到长）
  - RANDOM_SIGNIN             随机延时开关，默认开启；设 false 关闭
  - MAX_RANDOM_DELAY          每个账号随机延时上限（秒），默认 3600
  - WORKBUDDY_NO_SCHOOL       设 true 跳过开学季活动（活动结束后可关闭，省时间）

夜猫子窗口：black_cat 任务仅在北京时间 23:00-08:00 计数。默认 cron（00:03/08:03/16:03）
中 00:03 的那轮在窗口内；如需 23:30 加跑一轮，另建定时任务执行 growth 即可。

日志时间戳统一使用北京时间（UTC+8），不受青龙容器本地时区影响。

免责声明：本脚本为第三方逆向脚本（派生自 xz0609/workbuddy-checkin-ql 等开源项目，
详见文件头声明与仓库 NOTICE），与官方无关，接口随时可能失效；仅供个人学习研究，
请遵守平台规则与当地法律法规。完整许可见仓库根目录 LICENSE。
"""

import base64
import hashlib
import json
import math
import os
import random
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUTH_DIR = os.path.join(BASE_DIR, "auths")

# 本地桌面端凭据文件（login 用）。2026-09 桌面端升级为 -ai 变体，认证文件换了名字；
# Linux 没有桌面端，入口是 CodeBuddy CLI，凭据放在 XDG 数据目录
# （实测：~/.local/share/CodeBuddyExtension/Data/Public/auth/Tencent-Cloud.coding-copilot.info，
#  JSON 结构与桌面端一致，签到/成长中心接口全部照常工作）
DEFAULT_ENDPOINT = "https://copilot.tencent.com"
_AUTH_SUBDIR = os.path.join("CodeBuddyExtension", "Data", "Public", "auth")
AUTH_BASENAMES = (
    os.path.join(_AUTH_SUBDIR, "workbuddy-desktop-ai.info"),          # 新版桌面端
    os.path.join(_AUTH_SUBDIR, "workbuddy-desktop.info"),             # 旧版桌面端
    os.path.join(_AUTH_SUBDIR, "Tencent-Cloud.coding-copilot.info"),  # Linux CodeBuddy CLI
)

# ---------------------------------------------------------------------------
# 域名分工（与官方客户端一致，多域并存）：
#   · 签到域       copilot.tencent.com（凭证里 auth 的默认域，签到接口）
#   · 成长/遥测域  www.workbuddy.cn   （成长中心 / 遥测上报 / Web 对话 / 积分用量查询）
#   · 小程序上报域 copilot.tencent.com/v2/report（X-Client-Platform: miniprogram）
#   · 开学季域     www.codebuddy.cn   （school_open_day_2026 活动接口）
# ---------------------------------------------------------------------------
WORKBUDDY_BASE = "https://www.workbuddy.cn"
GROWTH_BASE = WORKBUDDY_BASE + "/v2/activity/growth"
REFRESH_URL = DEFAULT_ENDPOINT + "/v2/plugin/auth/token/refresh"
MINI_REPORT_URL = DEFAULT_ENDPOINT + "/v2/report"
SCHOOL_DOMAIN = "https://www.codebuddy.cn"
SCHOOL_BASE = SCHOOL_DOMAIN + "/portal/activity/school"
SCHOOL_ACTIVITY_ID = "school_open_day_2026"
SCHOOL_EXPERT_CATEGORY = "16-BackToSchool"

APP_VERSION = "5.5.6"   # 版本号全局统一：UA 与遥测指纹不一致会对不上
UA_WEB = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
          "WorkBuddy/%s Chrome/138.0.7204.251 Electron/37.10.3 Safari/537.36" % APP_VERSION)
UA_SHORT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 WorkBuddy/%s" % APP_VERSION
MP_UA = ("Mozilla/5.0 (Linux; Android 14; MicroMessenger/8.0.49 WeChat/0.8.0 "
         "MiniProgramEnv/android; wkbrowser xweb)")

QQ_TPL = "cb_y5Dy46tPQGGWtueMxXbe"          # 企鹅教师助手模板
THEME_KEY = "theme-tkmw7j"                   # 和平精英主题
LIB_DOC_URL = "https://www.workbuddy.cn/space/d/o0KWYeynteVv06UnAZqIFm"
SKILL_NAME = "algorithmic-trading"

EXPERT_MARKETPLACE_URL = ("https://acc-1258344699.cos.accelerate.myqcloud.com/"
                          "workbuddy/expert-marketplace/expert_center.json")

TEMPLATE_SCENES = [
    {"id": "01-ProductDesign", "name": "产品设计"},
    {"id": "02-Marketing", "name": "营销文案"},
    {"id": "03-DataAnalysis", "name": "数据分析"},
    {"id": "04-CodeReview", "name": "代码审查"},
    {"id": "05-Report", "name": "报告撰写"},
]

# 任务代码 → 中文名（报告翻译用）
TASK_NAME_CN = {
    "create_canvas": "设计创意模式",
    "playbook_prompt": "探索优秀灵感",
    "RichMeow_Chat": "桌面端对话",
    "Library_read": "体验资料库",
    "Expert_lighthouse": "腾讯轻量云专家",
    "Expert_Philanthropy": "公益专家",
    "Hp_Appearance": "和平精英主题",
    "Buddy_App": "发现应用",
    "Buddy_App_QQ": "企鹅教师助手",
    "Model_chat_GLM5.2": "GLM-5.2模型对话",
    "black_cat": "夜猫子活动",
    "Expert_team_use_3": "召唤3次专家团",
    "first_buddy": "领取Buddy",
    "chat_5": "和AI聊天5次",
    "skill_1": "尝鲜热门技能",
    "expert_5": "召唤5次专家",
    "template_5": "使用5个模板",
    "automation_1": "设置自动化任务",
    "workstation_expert": "工作台搭建师",
    "Sequential_Tasks_1": "小程序完成1次对话",
    "school_season": "参与校园日活动",
    # —— 与 L0NE-6/WorkBuddy-Daily 对齐的扩展已知码（专家体验族 / 小程序链 / 公众号）——
    "WorkBuddy_Valorant": "无畏契约拼豆专家",
    "expert_use_maidehao": "中国电商运营专家",
    "expert_use_douyinyin": "抖音策略师",
    "expert_use_shangjia_xuanchuan": "商家宣传页与海报设计师",
    "expert_use_bowangwang": "直播电商教练",
    "wb_wechat_oa_subscribe_task": "关注公众号",
    "Sequential_Tasks_2": "小程序专家对话",
    "Sequential_Tasks_3": "小程序对话5次",
    "Sequential_Tasks_4": "小程序定时任务",
    "Sequential_Tasks_5": "小程序GLM5.2",
    "Sequential_Tasks_6": "小程序对话10次",
    "Sequential_Tasks_7": "PC灵感功能",
}

KNOWN_TASK_CODES = set(TASK_NAME_CN)

# 不自动接单的任务：接了也永远完不成（需真实人工行为），按用户要求跳过以免污染进度
SKIP_AUTO_ACCEPT = {"Expert_Philanthropy"}  # 公益专家：需真实捐款，人工环节

LOTTERY_PRIZE_LABELS = {
    "school_credit_6": "6积分", "school_credit_66": "66积分",
    "school_voucher_luckin": "瑞幸咖啡15元券", "school_voucher_kfc_ok": "肯德基OK餐券",
    "school_voucher_kfc_ice": "肯德基冰淇淋券", "school_voucher_kugou": "酷狗会员月卡券",
}

# 开学季任务模式：manual=人工跳过, share=share-complete, report=遥测点亮
SCHOOL_TASK_MODES = {
    "task_student_verify": {"mode": "manual", "note": "微信学生认证（人工）"},
    "share_invite": {"mode": "share", "note": "分享活动给好友"},
    "chat_3_times": {"mode": "report", "note": "与AI对话3次", "kind": "mini_chat"},
    "desktop_chat_1_time": {"mode": "report", "note": "桌面端对话1次", "kind": "desktop_seq"},
    "expert_use": {"mode": "report", "note": "召唤开学季专家并对话", "kind": "expert"},
}

# 伪 HTTP 码：区分"没拿到响应"的两种原因
CODE_NO_NETWORK = -1   # 连不上/超时
CODE_BUDGET_OUT = -2   # 本次运行时间预算耗尽

# 写动作间隔（秒）：与官方客户端节奏对齐，防频控
WRITE_GAP = 1.5

# 成长任务列表缓存秒数：prog() 的高频进度查询走线程内缓存，动作后的完成验证才强制刷新。
# 不缓存的话每次 prog 都拉全量 /tasks，单账号 80-100 次调用、白烧 30-50 秒预算。
TASKS_CACHE_TTL = 20


def _parse_budget_seconds():
    """解析 WORKBUDDY_BUDGET_SECONDS；非法/非正数回落 900 并告警，绝不抛异常。

    这段逻辑必须在模块加载时完成，任何异常都会让进程在 main() 的兜底之前
    就崩掉、且无任何输出。默认 900（全流程含多次真实 AI 对话，比纯签到长）。
    """
    raw = os.environ.get("WORKBUDDY_BUDGET_SECONDS")
    if not raw:
        return 900
    try:
        v = float(raw)
    except (TypeError, ValueError):
        print(f"⚠️  WORKBUDDY_BUDGET_SECONDS={raw!r} 不是数字，用默认 900 秒")
        return 900
    return v if v > 0 else 900


def _parse_max_delay(raw):
    """解析随机延时上限秒数；非法/非正数回落 3600 并告警。"""
    try:
        v = int(raw)
    except (TypeError, ValueError):
        print(f"⚠️  MAX_RANDOM_DELAY={raw!r} 不是整数，用默认 3600 秒")
        return 3600
    return v if v > 0 else 3600


# 请求时间预算（秒）。青龙任务通常有超时上限，预算保证在超时前收尾不中断。
DEFAULT_BUDGET_SECONDS = _parse_budget_seconds()
REQUEST_TIMEOUT = 30
CHAT_TIMEOUT = 90          # 真实 AI 对话的流式响应上限

# 网络类失败的退避节奏（秒）。撞上"网络没就绪"（如容器刚启动、代理未拨通）时，
# 短促重试两次都撞在同一堵墙上，预算只花几秒就判了死刑。退避到分钟级才真正跨得过
# 这个窗口：最多 6 次尝试摊开约 3.5 分钟。实际跑几轮由剩余预算决定（见
# _request_with_retry 的守卫），预算不足会自动少跑几轮。
NETWORK_RETRY_DELAYS = (5, 15, 30, 60, 90)
# 5xx 是服务端抖动，不是网络没就绪，短促重试即可——干等几分钟既救不了它，
# 还会把预算耗光，让后面的成长任务一个都跑不成。
SERVER_RETRY_DELAYS = (3, 10)

# 线程本地预算起点：每个账号在随机延时结束后单独启动自己的请求预算，
# 使随机延时不计入预算、不压缩真正执行所需的请求时间。
_tls = threading.local()

# 随机延时：RANDOM_SIGNIN 开关（默认开启），每账号执行前随机延时 0 ~ MAX_RANDOM_DELAY 秒。
RANDOM_SIGNIN = os.getenv("RANDOM_SIGNIN", "true").lower() == "true"
MAX_RANDOM_DELAY = _parse_max_delay(os.getenv("MAX_RANDOM_DELAY", "3600"))
# 开学季活动开关（活动结束后可设 true 省时间）
NO_SCHOOL = os.getenv("WORKBUDDY_NO_SCHOOL", "").lower() == "true"

# 每轮最多用掉几张补登卡。卡是稀缺资源（上限 4 张），而这条写路径还没被真实响应
# 验证过，一轮只花一张：猜错形状也只错一次，一天多轮照样能把断登补完。
MAKEUP_MAX_PER_RUN = 1

# ---------------- 统一通知模块加载 ----------------
hadsend = False
try:
    from notify import send
    hadsend = True
except ImportError:
    hadsend = False


def notify_user(title, content):
    """统一通知函数：有 notify.py 走青龙通知，否则仅打印。"""
    if hadsend:
        try:
            send(title, content)
        except Exception as e:
            print(f"❌ 通知发送失败: {e}")
    else:
        print(f"📢 {title}")


# ---------------------------------------------------------------------------
# 时间预算
# ---------------------------------------------------------------------------
def _start_budget():
    """启动当前线程的请求预算时钟。"""
    _tls.started_at = time.monotonic()


def _budget_left():
    start = getattr(_tls, "started_at", None)
    if start is None:
        return DEFAULT_BUDGET_SECONDS
    return DEFAULT_BUDGET_SECONDS - (time.monotonic() - start)


def _nap(seconds):
    """预算感知的间歇等待：预算将尽时提前返回 False（调用方据此收尾）。"""
    end = time.monotonic() + seconds
    while True:
        left = end - time.monotonic()
        if left <= 0:
            break
        if _budget_left() <= 1:
            return False
        time.sleep(min(1.0, left))
    return _budget_left() > 1


# ---------------------------------------------------------------------------
# 北京时间（不依赖系统时区：青龙容器 / CI runner 多为 UTC，直接用 localtime 会算错）
# ---------------------------------------------------------------------------
BJT = timezone(timedelta(hours=8))


def beijing_now():
    return datetime.now(BJT)


def within_night_window():
    """夜猫子窗口：北京时间 23:00 - 次日 08:00。"""
    h = beijing_now().hour
    return h >= 23 or h < 8


# ---------------------------------------------------------------------------
# JWT 小工具
# ---------------------------------------------------------------------------
def _jwt_payload(tok):
    """解析 JWT payload（不校验签名）；失败返回 {}。"""
    try:
        pay = str(tok).split(".")[1]
        pay += "=" * (-len(pay) % 4)
        return json.loads(base64.urlsafe_b64decode(pay))
    except Exception:
        return {}


def token_exp(at):
    """AT 过期时间戳（秒）；解析失败返回 0。"""
    return int(_jwt_payload(at).get("exp") or 0)


# ---------------------------------------------------------------------------
# 凭据读写（auths/<uid>.json）
# ---------------------------------------------------------------------------
def uid_of(session):
    """从会话里取账号标识（以 account.uid 作为文件名）。"""
    account = (session or {}).get("account") or {}
    uid = account.get("uid")
    if uid:
        return str(uid)
    # 完全缺失时用 token 摘要兜底，避免重名覆盖
    auth = (session or {}).get("auth") or {}
    tok = auth.get("accessToken") or ""
    return "u-" + hashlib.md5(tok.encode("utf-8")).hexdigest()[:12]


def load_creds():
    """读取 auths/*.json 全部凭证，按 uid 去重。返回 [(uin, session), ...]。"""
    items = {}
    if not os.path.isdir(AUTH_DIR):
        return []
    try:
        names = sorted(f for f in os.listdir(AUTH_DIR) if f.endswith(".json"))
    except OSError:
        return []
    for name in names:
        path = os.path.join(AUTH_DIR, name)
        try:
            with open(path, "r", encoding="utf-8") as f:
                session = json.load(f)
        except (OSError, json.JSONDecodeError):
            print(f"⚠️  跳过无法解析的凭证 {name}")
            continue
        uin = name[:-len(".json")]
        key = str((session.get("account") or {}).get("uid") or uin)
        items.setdefault(key, (uin, session))
    return list(items.values())


def save_session(uin, session):
    """把（可能更新过的）会话回写 auths/<uid>.json（Token 轮换后调用）。"""
    try:
        os.makedirs(AUTH_DIR, exist_ok=True)
        path = os.path.join(AUTH_DIR, f"{uin}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(session, f, ensure_ascii=False, indent=2)
        return True
    except OSError as e:
        print(f"⚠️  凭据回写失败（{uin}）: {e}")
        return False


def find_local_auth_file():
    """定位本机 WorkBuddy 桌面端凭据文件，返回路径或 None。"""
    home = os.path.expanduser("~")
    local = os.environ.get("LOCALAPPDATA") or os.path.join(home, "AppData", "Local")
    xdg_data = os.environ.get("XDG_DATA_HOME") or os.path.join(home, ".local", "share")
    roots = [
        local,                                                     # Windows 桌面端
        os.path.join(home, "Library", "Application Support"),      # macOS 桌面端
        xdg_data,                                                  # Linux CodeBuddy CLI
        os.path.join(home, ".config"),                             # Linux（旧猜测，保留）
    ]
    for root in roots:
        for base in AUTH_BASENAMES:
            c = os.path.join(root, base)
            if os.path.exists(c):
                return c
    return None


# ---------------------------------------------------------------------------
# 新版桌面端凭证解密（2026-09 起 5.6.x 把 .info 字段加密为 $wbEncrypted 信封）
#
# 加密方案（逆向自 app.asar 的 at-rest-crypto 包，与官方客户端一致）：
#   · 信封：{"suite":1,"keyId","nonce"(12B),"authTag"(16B),"ciphertext"}，AES-256-GCM
#   · 构建密钥：key = SHA256(atRestSecretKey 的 base64 字符串)，keyId = SHA256(key)[:16]
#   · AAD（sym-v1/field）："WB-AAD\0" + [1] + LP("WBEV1") + LP("sym-v1")
#                        + U32(1) + LP(keyId) + [2] + [0] + [0]
#   · atRestSecretKey 藏在定制 Electron 的原生绑定里：
#     process._linkedBinding("electron_browser_workbuddy_storage").loggerGet()
#     —— 用 ELECTRON_RUN_AS_NODE=1 把 WorkBuddy.exe 当 Node 跑即可取出
# ---------------------------------------------------------------------------
_DECRYPT_JS = r"""
const crypto = require('crypto');
const fs = require('fs');
const AAD_DOMAIN = Buffer.from('WB-AAD\0', 'ascii');
const FRAMING_CODE = { file: 1, field: 2, record: 3, stream: 4 };
const FORMAT_ID = { file: 'WBEF1', field: 'WBEV1', record: 'WBER1', stream: 'WBES1' };
function u32(v) { const b = Buffer.allocUnsafe(4); b.writeUInt32BE(v); return b; }
function lp(s) { const b = Buffer.from(s, 'utf8'); return Buffer.concat([u32(b.length), b]); }
function aad(keyId, suite, framing) {
    return Buffer.concat([AAD_DOMAIN, Buffer.from([1]), lp(FORMAT_ID[framing]),
        lp('sym-v1'), u32(suite), lp(keyId), Buffer.from([FRAMING_CODE[framing]]),
        Buffer.from([0]), Buffer.from([0])]);
}
function main() {
    const [inPath, outPath] = process.argv.slice(2);
    const payload = JSON.parse(
        process._linkedBinding('electron_browser_workbuddy_storage').loggerGet());
    const key = crypto.createHash('sha256').update(payload.atRestSecretKey, 'utf8').digest();
    const keyId = crypto.createHash('sha256').update(key).digest('hex').slice(0, 16);
    const doc = JSON.parse(fs.readFileSync(inPath, 'utf8'));
    let ok = 0, fail = 0;
    function replace(parent, k, node) {
        try {
            const e = JSON.parse(Buffer.from(node.envelope, 'base64').toString('utf8'));
            const d = crypto.createDecipheriv('aes-256-gcm', key,
                Buffer.from(e.nonce, 'base64'), { authTagLength: 16 });
            d.setAAD(aad(e.keyId, e.suite, 'field'));
            d.setAuthTag(Buffer.from(e.authTag, 'base64'));
            const pt = Buffer.concat([d.update(Buffer.from(e.ciphertext, 'base64')),
                d.final()]).toString('utf8');
            let v = pt;
            if (pt[0] === '{' || pt[0] === '[') { try { v = JSON.parse(pt); } catch (e2) {} }
            parent[k] = v;
            ok++;
        } catch (err) { fail++; }
    }
    function walk(node) {
        if (Array.isArray(node)) {
            node.forEach((c, i) => { (c && c.$wbEncrypted === 1) ? replace(node, i, c) : walk(c); });
            return;
        }
        if (node && typeof node === 'object') {
            for (const k of Object.keys(node)) {
                const c = node[k];
                if (c && typeof c === 'object' && c.$wbEncrypted === 1
                    && typeof c.envelope === 'string') replace(node, k, c);
                else walk(c);
            }
        }
    }
    walk(doc);
    fs.writeFileSync(outPath, JSON.stringify(doc, null, 2), 'utf8');
    console.log('decrypted=' + ok + ' failed=' + fail);
}
main();
"""


def _has_encrypted_fields(session):
    """凭证里是否含 $wbEncrypted 加密字段。"""
    def _walk(node):
        if isinstance(node, dict):
            if node.get("$wbEncrypted") == 1:
                return True
            return any(_walk(v) for v in node.values())
        if isinstance(node, list):
            return any(_walk(v) for v in node)
        return False
    return _walk(session)


def find_workbuddy_exe():
    """定位本机 WorkBuddy.exe（解密用）：注册表卸载信息 → 常见安装路径。"""
    try:
        import winreg
        for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            for sub in (r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
                        r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"):
                try:
                    key = winreg.OpenKey(root, sub)
                except OSError:
                    continue
                with key:
                    for i in range(winreg.QueryInfoKey(key)[0]):
                        try:
                            with winreg.OpenKey(key, winreg.EnumKey(key, i)) as sk:
                                icon = winreg.QueryValueEx(sk, "DisplayIcon")[0]
                        except OSError:
                            continue
                        exe = str(icon or "").split(",")[0].strip().strip('"')
                        if exe.lower().endswith("workbuddy.exe") and os.path.isfile(exe):
                            return exe
    except ImportError:
        pass
    local = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Local")
    for c in (os.path.join(local, "Programs", "WorkBuddy", "WorkBuddy.exe"),
              r"C:\Program Files\WorkBuddy\WorkBuddy.exe",
              r"C:\Program Files (x86)\WorkBuddy\WorkBuddy.exe"):
        if os.path.isfile(c):
            return c
    return None


def decrypt_session(session):
    """用 WorkBuddy.exe（ELECTRON_RUN_AS_NODE 模式）取出构建密钥并解密凭证。

    仅在本地 Windows（装有桌面端）执行；解密结果为明文凭证，供青龙直接使用。
    """
    exe = find_workbuddy_exe()
    if not exe:
        raise RuntimeError("未找到 WorkBuddy.exe（请在装有桌面端的机器上执行 login）")
    tmpdir = tempfile.mkdtemp(prefix="wb-decrypt-")
    try:
        in_path = os.path.join(tmpdir, "in.json")
        out_path = os.path.join(tmpdir, "out.json")
        js_path = os.path.join(tmpdir, "decrypt.js")
        with open(in_path, "w", encoding="utf-8") as f:
            json.dump(session, f, ensure_ascii=False)
        with open(js_path, "w", encoding="utf-8") as f:
            f.write(_DECRYPT_JS)
        env = dict(os.environ)
        env["ELECTRON_RUN_AS_NODE"] = "1"
        proc = subprocess.run([exe, js_path, in_path, out_path],
                              capture_output=True, text=True, env=env, timeout=60)
        if proc.returncode != 0 or not os.path.isfile(out_path):
            raise RuntimeError("解密进程失败: %s"
                               % ((proc.stderr or proc.stdout or "无输出").strip()[:200]))
        with open(out_path, "r", encoding="utf-8") as f:
            plain = json.load(f)
        if _has_encrypted_fields(plain):
            raise RuntimeError("解密后仍存在加密字段（构建密钥可能已随版本轮换）")
        return plain
    finally:
        for name in os.listdir(tmpdir):
            try:
                os.remove(os.path.join(tmpdir, name))
            except OSError:
                pass
        try:
            os.rmdir(tmpdir)
        except OSError:
            pass


def do_login():
    """login：读本机登录态（自动解密新版加密凭证），保存到 auths/<uid>.json。"""
    print("== WorkBuddy 凭据导入（本地执行）==")
    path = find_local_auth_file()
    if not path:
        print("❌ 未找到本机登录凭据，请先登录 WorkBuddy 桌面端。")
        return 1
    try:
        with open(path, "r", encoding="utf-8") as f:
            session = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"❌ 读取/解析凭据失败: {type(e).__name__}: {e}")
        return 1

    if _has_encrypted_fields(session):
        print("🔐 检测到新版桌面端加密凭证（$wbEncrypted），正在自动解密...")
        try:
            session = decrypt_session(session)
            print("✅ 解密成功（AES-256-GCM at-rest，构建密钥取自 WorkBuddy.exe）")
        except Exception as e:
            print(f"❌ 自动解密失败: {e}")
            return 1

    uid = uid_of(session)
    os.makedirs(AUTH_DIR, exist_ok=True)
    out = os.path.join(AUTH_DIR, f"{uid}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(session, f, ensure_ascii=False, indent=2)

    account = session.get("account") or {}
    nickname = account.get("nickname") or account.get("uid") or uid
    print("✅ 导入成功")
    print(f"   用户: {nickname}")
    print(f"   凭证已保存: {out}")
    return 0


# ---------------------------------------------------------------------------
# HTTP 小工具（纯标准库 urllib，带时间预算 + 分类退避重试）
# ---------------------------------------------------------------------------
def build_headers(session):
    auth = session.get("auth") or {}
    account = session.get("account") or {}
    token = auth.get("accessToken")
    uid = account.get("uid")
    if isinstance(token, dict):
        raise ValueError("NO_SESSION: 凭证已加密（新版桌面端 at-rest 加密），"
                         "请在本地重新执行 login 自动解密导入")
    if not token or not uid:
        raise ValueError("NO_SESSION: 本地未找到有效登录会话")
    headers = {
        "Accept": "application/json",
        "Authorization": "Bearer %s" % token,
        "Content-Type": "application/json",
        "X-User-Id": str(uid),
        "User-Agent": "WorkBuddy",
    }
    if account.get("enterpriseId"):
        headers["X-Enterprise-Id"] = account["enterpriseId"]
        headers["X-Tenant-Id"] = account["enterpriseId"]
    if auth.get("domain"):
        headers["X-Domain"] = auth["domain"]
    return headers


def wb_headers(headers):
    """成长/遥测域（workbuddy.cn）请求头：补 Origin/Referer/Web UA，对齐官方 Web 端。"""
    h = dict(headers)
    h.update({"Origin": WORKBUDDY_BASE, "Referer": WORKBUDDY_BASE + "/profile/growth-center",
              "User-Agent": UA_WEB, "Accept": "application/json, text/plain, */*"})
    return h


def mp_headers(headers):
    """小程序口径请求头：部分任务仅在 X-Client-Platform: miniprogram 时下发。"""
    h = dict(headers)
    h.update({"User-Agent": MP_UA, "X-Client-Platform": "miniprogram"})
    return h


def school_headers(headers):
    """开学季活动域（codebuddy.cn）请求头：小程序 UA。"""
    h = dict(headers)
    h.update({"User-Agent": MP_UA, "Referer": SCHOOL_DOMAIN + "/",
              "Accept": "application/json"})
    return h


def _request(url, headers, method="GET", payload=None, timeout=REQUEST_TIMEOUT):
    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            raw = resp.read().decode("utf-8")
            try:
                return resp.status, json.loads(raw)
            except Exception:
                return resp.status, {"raw": raw[:500]}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"raw": raw[:500]}
    except urllib.error.URLError as e:
        return CODE_NO_NETWORK, {"error": str(e.reason)}
    except Exception as e:
        return CODE_NO_NETWORK, {"error": str(e)}


def post(url, headers, payload=None, retry=False, timeout=None):
    """POST 默认不重试：领奖/抽奖/续期等写操作若服务端已处理才超时，重试会重复提交。"""
    return _request_with_retry(url, headers, method="POST", payload=payload, retry=retry, timeout=timeout)


def get(url, headers, timeout=None, retry=True):
    return _request_with_retry(url, headers, method="GET", retry=retry, timeout=timeout)


def _post_stream(url, headers, payload, timeout=CHAT_TIMEOUT):
    """SSE 流式 POST：阻塞读完整流后返回 (http码, 原始文本)。失败不重试。

    服务端在对话结束后会关闭连接，resp.read() 自然返回；超时参数兜底防挂死。
    """
    if _budget_left() <= 5:
        return CODE_BUDGET_OUT, ""
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=max(5, min(timeout, _budget_left())), context=ctx) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:
        return CODE_NO_NETWORK, str(e)


def _retry_delays(code):
    """该失败码对应的退避节奏；空元组表示"重试也没用"，立刻如实返回。

    只有这两类值得再试：本机网络没就绪（-1）、服务端抖动（5xx）。
    4xx 是业务规则或参数问题，重试一百次也是同一个答案；CODE_BUDGET_OUT 更是
    连请求都没发出去，再试只会离被强杀更近一步。
    """
    if code == CODE_NO_NETWORK:
        return NETWORK_RETRY_DELAYS
    if code >= 500:
        return SERVER_RETRY_DELAYS
    return ()


def _request_with_retry(url, headers, method="GET", payload=None, retry=True, timeout=None):
    """带时间预算的请求：失败按退避节奏重试，超时上限随剩余预算收缩，预算不足则直接放弃。

    返回 CODE_BUDGET_OUT 表示"没发出去，因为再发就要超出时间预算了"——调用方
    据此提前收尾。GET 默认重试；写操作（POST）默认不重试（retry 参数可覆盖）。
    """
    hard_timeout = timeout or REQUEST_TIMEOUT
    if _budget_left() <= 1:
        return CODE_BUDGET_OUT, {"error": "已达本次运行时间预算，跳过剩余请求"}

    code, body = _request(url, headers, method=method, payload=payload,
                          timeout=max(1, min(hard_timeout, _budget_left())))
    if not retry:
        return code, body

    # 退避进度按"失败类型"各记一份，而不是一个全局计数。
    # 失败类型会在重试途中变化：典型的是冷启动——前几次网络不可达（网卡刚连上），
    # 之后转成 500（代理还没就绪）。全局计数会让这种 5xx 撞上已经用光的计数、
    # 一次都重试不到。按节奏分桶后，每类各自从头走自己的退避表，总尝试次数仍有界。
    attempts = {}
    while True:
        delays = _retry_delays(code)
        if not delays:
            return code, body
        used = attempts.get(delays, 0)
        if used >= len(delays):
            return code, body
        delay = delays[used]
        attempts[delays] = used + 1
        # 一轮重试最坏要占掉 delay + 一整个超时，预算不够就别开始：宁可现在如实返回
        # 失败，也不能跑穿预算——那样连收尾汇报都来不及输出，当天记录整条丢失。
        if _budget_left() <= delay + hard_timeout:
            return code, body
        time.sleep(delay)
        code, body = _request(url, headers, method=method, payload=payload,
                              timeout=max(1, min(hard_timeout, _budget_left())))


def _http_label(code):
    """把伪 HTTP 码翻译成人话；-1/-2 是脚本自定义的"没拿到响应"标记。"""
    if code == CODE_NO_NETWORK:
        return "网络不可达"
    if code == CODE_BUDGET_OUT:
        return "时间预算耗尽"
    return "HTTP %s" % code


def _is_no_chance(msg):
    """抽奖失败是否只是"没有次数"——这是常态，不是故障。

    服务端对"次数为 0"返回 400 + `insufficient lottery chance balance`，和真正的
    参数错误同为 400，只看状态码会把两者混为一谈：把常态记成失败，会把常态算进失败统计。
    """
    m = str(msg or "").lower()
    if not m:
        return False
    if "insufficient" in m or "not enough" in m:
        return "chance" in m or "balance" in m
    return "no chance" in m


def _is_unknown_tier(code, body):
    """连登兑换是否因为"tier 这个值本身不认识"被拒——用于判断要不要换一种写法重试。

    /redeem 的 tier 是**档位标识字符串**（"7d"/"14d"/"28d"）。接口哪天改回收天数，
    脚本就会三档全废且看不出原因，所以保留这条兜底：档位标识被判 unknown tier 时退回
    天数再试一次。这类 400 发生在参数校验阶段，服务端没兑换任何东西，重试不会重复领取。
    """
    if code != 400:
        return False
    m = str(dig(body, "msg") or "").lower()
    return "tier" in m and ("unknown" in m or "unsupported" in m or "invalid" in m)


def _is_tier_locked(code, body):
    """未解锁档位：403 + 「连续登录天数不足」——这是常态，不是故障。"""
    if code != 403:
        return False
    m = str(dig(body, "msg") or "")
    return "天数不足" in m or "不足" in m


def dig(obj, key):
    """在可能被 data/result 包裹的响应里找字段，兼容信封结构。"""
    if isinstance(obj, dict):
        if key in obj and obj[key] is not None:
            return obj[key]
        for k in ("data", "result", "resp", "response"):
            if k in obj and isinstance(obj[k], dict):
                r = dig(obj[k], key)
                if r is not None:
                    return r
    return None


def fmt_credit(v):
    try:
        return int(v)
    except (TypeError, ValueError, OverflowError):
        return v


def as_int(v, default=0):
    try:
        return int(v)
    except (TypeError, ValueError, OverflowError):
        pass
    try:
        return int(float(v))
    except (TypeError, ValueError, OverflowError):
        return default


def _fmt_eta(arrive_at, server_now):
    try:
        left = float(arrive_at) - float(server_now)
    except (TypeError, ValueError, OverflowError):
        return ""
    if not math.isfinite(left):
        return ""
    if left <= 0:
        return "，已到达待领取"
    minutes = int(round(left / 60.0))
    if minutes < 60:
        return "，约 %d 分钟后回" % max(1, minutes)
    return "，约 %.1f 小时后回" % (left / 3600.0)


def _client_token(prefix="u"):
    return "%s-%s" % (prefix, uuid.uuid4())


def _strip_tail(s):
    """清理积分数字的 ".0" 尾巴。"""
    s = str(s)
    return s.rstrip("0").rstrip(".") if "." in s else s


_REDEEM_REWARDS = {
    "7d":  "+2 能量 +1 补登卡 +1 次抽奖",
    "14d": "+50 积分 +3 能量 +1 补登卡 +1 次抽奖",
    "28d": "+150 积分 +5 能量 +1 补登卡 +1 次抽奖",
}

# 连登兑换三档：(档位标识, /redeem/summary 的状态字段前缀, 展示名, 天数)
_REDEEM_TIERS = (
    ("7d",  "starter",   "入门", 7),
    ("14d", "advanced",  "进阶", 14),
    ("28d", "legendary", "巅峰", 28),
)


def _redeem_reward_desc(body, tier):
    """兑换成功的奖励描述：优先拼服务端实发的 *_granted，挖不到才回落官方文案。

    注意实发字段名带 _granted 后缀（credit_granted / energy_granted /
    cards_granted / chances_granted）；直接读 `credit` 恒为空，会把兑换所得漏计。
    """
    bits = []
    credit = as_int(dig(body, "credit_granted"), 0)
    energy = as_int(dig(body, "energy_granted"), 0)
    cards = as_int(dig(body, "cards_granted"), 0)
    chances = as_int(dig(body, "chances_granted"), 0)
    if credit:
        bits.append("+%s 积分" % fmt_credit(credit))
    if energy:
        bits.append("+%s 能量" % fmt_credit(energy))
    if cards:
        bits.append("+%s 补登卡" % fmt_credit(cards))
    if chances:
        bits.append("+%s 次抽奖" % fmt_credit(chances))
    if bits:
        return "（%s）" % " ".join(bits)
    return "（%s）" % _REDEEM_REWARDS.get(tier, "奖励已到账")


# ---------------------------------------------------------------------------
# Token 自动续期（RT 轮换，回写 auths/*.json）
# ---------------------------------------------------------------------------
def refresh_one(rt):
    """用 RT 走官方刷新接口换新令牌。返回 (新AT, 新RT) 或 (None, 错误信息)。

    不重试：RT 轮换非幂等——首次请求若已在服务端生效才超时，旧 RT 已作废，
    重试必然失败。
    """
    h = {"Content-Type": "application/json", "Accept": "application/json",
         "X-Refresh-Token": rt, "X-Auth-Refresh-Source": "plugin"}
    code_, body = post(REFRESH_URL, h, {})
    if isinstance(body, dict) and body.get("$wbEncrypted"):
        return None, "接口返回加密信封（疑似接口改版），请在本地重新 login 导入新凭证"
    at = dig(body, "accessToken")
    if 200 <= code_ < 300 and at:
        return at, (dig(body, "refreshToken") or rt)
    # 必须先格式化再 strip："%s %s" % (a, b).strip() 的 .strip() 会绑到元组上直接崩
    return None, ("%s %s" % (_http_label(code_), str(dig(body, "msg") or "")[:80])).strip()


def _apply_new_tokens(uin, session, new_at, new_rt):
    """把新令牌写回会话并落盘。"""
    if not isinstance(session.get("auth"), dict):
        session["auth"] = {}
    session["auth"]["accessToken"] = new_at
    session["auth"]["refreshToken"] = new_rt
    exp_ms = token_exp(new_at) * 1000
    if exp_ms:
        session["auth"]["expiresAt"] = exp_ms
    return save_session(uin, session)


def auto_refresh_session(uin, session, log=None):
    """AT 缺失或 7 天内过期时，用 RT 轮换并回写 auths/<uid>.json。返回是否刷新成功。"""
    auth = session.get("auth") or {}
    if not isinstance(auth, dict):
        return False
    at = auth.get("accessToken") or ""
    rt = auth.get("refreshToken") or ""
    if not rt:
        return False
    exp = token_exp(at) if at else 0
    if at and exp - time.time() > 7 * 86400:
        return False   # 还新鲜，不折腾（离线会话 30 天失效，7 天余量足够）
    if not at:
        reason = "AT 缺失"
    elif exp:
        reason = "AT 将于 %s 过期" % datetime.fromtimestamp(exp, BJT).strftime("%Y-%m-%d")
    else:
        reason = "AT 无法解析"
    new_at, result = refresh_one(rt)
    if not new_at:
        if log:
            log("⚠️ Token 续期失败（%s）: %s，沿用旧凭据" % (reason, result))
        return False
    _apply_new_tokens(uin, session, new_at, result)
    if log:
        log("🔐 Token 已续期（%s），新凭据已回写" % reason)
    return True


def do_refresh():
    """refresh：对所有账号强制做一次 RT 轮换（不判断过期）。"""
    creds = load_creds()
    if not creds:
        print("⚠️  未找到任何凭证，请先执行 login。")
        return 2
    ok = 0
    for uin, session in creds:
        _start_budget()
        account = session.get("account") or {}
        display = account.get("nickname") or uin
        rt = (session.get("auth") or {}).get("refreshToken") or ""
        if not rt:
            print("⚠️ [%s] 无 refreshToken，跳过（重新 login 导入）" % display)
            continue
        new_at, result = refresh_one(rt)
        if new_at:
            _apply_new_tokens(uin, session, new_at, result)
            exp = token_exp(new_at)
            print("🔄 [%s] token 已续期，新 AT 过期: %s" % (
                display, datetime.fromtimestamp(exp, BJT).strftime("%Y-%m-%d %H:%M") if exp else "?"))
            ok += 1
        else:
            print("⚠️ [%s] 续期失败: %s" % (display, result))
        time.sleep(1)
    print("✅ 共续期 %d/%d 个账号" % (ok, len(creds)))
    return 0 if ok == len(creds) else 1


# ---------------------------------------------------------------------------
# 查询（积分套餐 / 用量 / 成长概况）
# ---------------------------------------------------------------------------
def query_credits(headers):
    """积分套餐：主套餐/加量包的剩余、总量、已用。"""
    c, b = post(WORKBUDDY_BASE + "/billing/meter/get-user-resource-summary", headers, {})
    if c in (401, 403):
        return "登录态已失效（HTTP %s）" % c
    if not (200 <= c < 300):
        return "积分查询失败（%s）" % _http_label(c)
    pkgs = dig(b, "Packages") or []
    out = []
    for i, p in enumerate(pkgs):
        if not isinstance(p, dict):
            continue
        pkg_name = "主套餐" if i == 0 else "加量包%d" % i
        out.append("%s剩余%s积分(共%s,已用%s)" % (
            pkg_name, _strip_tail(p.get("CycleRemainCapacity", "0")),
            _strip_tail(p.get("CycleTotalCapacity", "0")),
            _strip_tail(p.get("CycleUsedCapacity", "0"))))
    return "；".join(out) if out else "暂无套餐"


def query_usage(headers):
    """用量统计：资源类别数 / 本月总用量（信封里嵌 Response.Data，dig 挖不到，直取）。"""
    c, b = post(WORKBUDDY_BASE + "/billing/meter/get-user-resource", headers, {})
    if c in (401, 403):
        return "登录态已失效（HTTP %s）" % c
    if not (200 <= c < 300) or not isinstance(b, dict):
        return "查询失败（%s）" % _http_label(c)
    data = b.get("data") or {}
    resp = data.get("Response") or {}
    inner = resp.get("Data") or {}
    if not inner:
        return "暂无数据（用量统计延迟 2-3 小时）"
    return "共%s类资源，本月已使用%s次" % (inner.get("TotalCount", "?"), inner.get("TotalDosage", "?"))


def query_growth(headers):
    """成长概况：等级 / 连签 / 能量 / 累签天数。"""
    out = {"level": "?", "streak": "?", "energy": "?", "signed": "?"}
    try:
        c, b = get(GROWTH_BASE + "/profile", headers)
        if 200 <= c < 300:
            out["level"] = dig(b, "level") or "?"
    except Exception:
        pass
    try:
        c, b = get(GROWTH_BASE + "/energy", headers)
        if 200 <= c < 300:
            out["energy"] = dig(b, "balance")
    except Exception:
        pass
    try:
        c, b = get(GROWTH_BASE + "/streak", headers)
        if 200 <= c < 300:
            so = dig(b, "streak") or {}
            out["streak"] = so.get("days", "?") if isinstance(so, dict) else "?"
    except Exception:
        pass
    try:
        c, b = get(GROWTH_BASE + "/heatmap", headers)
        if 200 <= c < 300:
            cells = dig(b, "cells") or []
            out["signed"] = sum(1 for x in cells if isinstance(x, dict) and x.get("score", 0))
    except Exception:
        pass
    return out


# ---------------------------------------------------------------------------
# 稳定指纹 & 遥测事件构建（无头环境点亮"桌面端"任务的核心）
# ---------------------------------------------------------------------------
def derive_id(uid, salt):
    """由 uid 稳定派生 36 位 hex 设备标识（md5，幂等：同账号每次相同）。"""
    return hashlib.md5(("%s:%s" % (salt, uid)).encode()).hexdigest()[:36]


def desktop_fingerprint(uid, nick):
    """公共桌面指纹（注入每个桌面域事件，覆盖同名业务键）。"""
    now = int(time.time() * 1000)
    return {
        "timezone": "Asia/Shanghai", "reportDelay": 2000,
        "userId": uid, "username": nick, "userNickname": nick,
        "product": "SaaS", "releaseDate": 1789036585355,
        "commit": "5f9692923c93033111c51ad7b003eb80204a9b75",
        "ideName": "WorkBuddy", "ideType": "WorkBuddy", "ideVersion": APP_VERSION,
        "machineId": derive_id(uid, "machine"), "sessionId": derive_id(uid, "session"),
        "extName": "workbuddy-desktop", "extVersion": APP_VERSION,
        "os": "win32", "arch": "x64", "osVersion": "10.0.26220",
        "cpuCores": 20, "memorySize": 24,
        "timestamp": now, "presentAt": now,
    }


def desktop_chat_sequence(uid, nick, conversation_id, request_id, message_id,
                          model_id="fast-model", model_name="fast-model"):
    """6 连「桌面端成功对话」事件链（点亮 RichMeow_Chat / 开学季桌面对话）。"""
    now = int(time.time() * 1000)
    ev = []

    def mk(code, extra):
        e = {"eventCode": code}
        e.update(extra)
        ev.append(e)

    mk("agent_task_created", {
        "source": "LOCAL", "name": "working", "task_target": "local", "mode": "craft",
        "requestModelId": model_id, "requestModelName": model_name,
        "has_repo": False, "repo_type": "none", "workspace_type": "empty",
        "has_connector": False, "connector_types": [],
        "has_mention": False, "mention_types": [],
        "has_template": False, "action": "", "template_name": "",
        "has_expert": False, "expert_id": "", "expert_name": "", "expert_industry_id": "",
        "has_skill": False, "skill_names": [],
        "conversationId": conversation_id, "messageId": message_id,
        "buddyId": "", "buddyName": ""})
    mk("chat_message_send", {
        "messageId": message_id + "-assistant", "historyCount": 0,
        "isContextTruncated": False, "currentStepCount": 1,
        "traceId": request_id, "rootRequestId": request_id,
        "parentConversationId": conversation_id,
        "agentName": "cli", "agentType": "main"})
    mk("chat_request_send", {
        "inputLength": 24, "isPlan": False, "isAutoExecuteTerminal": False,
        "isAutoModify": False, "codebaseEnable": False, "maxToken": 0,
        "maxSteps": 500, "temperature": 0, "maxRetries": 0,
        "mentionContexts": [], "knowledgeId": [], "knowledgeName": [],
        "codebaseId": "", "mentionContextCount": 0, "command": "",
        "recommendId": "", "skillId": "", "skillCount": 0, "totalCount": 0,
        "traceId": request_id, "rootRequestId": request_id,
        "parentConversationId": conversation_id,
        "agentName": "cli", "agentType": "main"})
    mk("chat_message_response", {
        "messageId": message_id + "-assistant", "responseModelId": model_id,
        "inputToken": 120, "outputToken": 80, "totalToken": 200,
        "cachedTokens": 0, "cachedWriteTokens": 0, "cachedMissTokens": 0,
        "isSuccessful": True, "messageErrorCode": "", "finishReason": "stop",
        "firstTokenAt": now, "traceId": request_id,
        "conversationId": conversation_id,
        "rootRequestId": request_id, "parentConversationId": conversation_id,
        "agentName": "cli", "agentType": "main"})
    mk("chat_message_status", {
        "messageId": message_id + "-assistant", "messageErrorCode": "0",
        "traceId": request_id, "rootRequestId": request_id,
        "parentConversationId": conversation_id,
        "agentName": "cli", "agentType": "main"})
    mk("chat_request_response", {
        "mode": "craft", "toolCallCount": 0,
        "inputToken": 120, "outputToken": 80, "totalToken": 200,
        "cachedTokens": 0, "cachedWriteTokens": 0, "cachedMissTokens": 0,
        "isSuccessful": True, "messageErrorCode": "", "finishReason": "stop",
        "rootRequestId": request_id, "parentConversationId": conversation_id,
        "agentName": "cli", "agentType": "main"})
    return ev


def desktop_buddy5_sequence(uid, nick, buddy_id, buddy_name):
    """五连「进入 Buddy 应用」事件（点亮 Buddy_App / Buddy_App_QQ）。"""
    ev = []

    def mk(code, extra):
        e = {"eventCode": code, "mode": "LOCAL",
             "buddyId": buddy_id, "buddyName": buddy_name}
        e.update(extra)
        ev.append(e)

    mk("buddyapp_discover_click", {})
    mk("buddyapp_show", {"elementId": buddy_id, "elementName": buddy_name, "position": 2})
    mk("buddyapp_enter_click",
       {"elementId": buddy_id, "elementName": buddy_name, "position": 2, "isFirstPage": "1"})
    mk("buddyapp_auth_confirm_click", {"elementId": buddy_id, "elementName": buddy_name})
    mk("buddyapp_bindaccount_skip_click", {"elementId": buddy_id, "elementName": buddy_name})
    return ev


def chat_request_events(uid, nick, conv_id, prompt, txt):
    """Web 对话三连事件（点亮 chat_5 / Model_chat_GLM5.2 / black_cat）。"""
    now = int(time.time() * 1000)
    rid = "cmb-" + str(uuid.uuid4())
    common = {"userId": uid, "userNickname": nick, "ideName": "web-Agents", "ideType": "web-Agents",
              "machineId": derive_id(uid, "machine"), "mode": "CLOUD", "userAgent": UA_WEB,
              "os": "Win32", "timezone": "Asia/Shanghai"}
    return [
        {"eventCode": "chat_request_send", "timestamp": now, "reportDelay": 0, **common,
         "conversationId": conv_id, "requestId": rid, "requestModelId": "glm-5.2",
         "requestModelName": "GLM-5.2", "inputLength": len(prompt), "customAgentName": ""},
        {"eventCode": "chat_request_response", "timestamp": now + 100, "reportDelay": 0, **common,
         "conversationId": conv_id, "requestId": rid, "requestModelId": "glm-5.2",
         "requestModelName": "GLM-5.2", "toolCallCount": 0, "inputToken": max(1, len(prompt) // 4),
         "outputToken": max(1, len(txt) // 4), "totalToken": max(2, (len(prompt) + len(txt)) // 4)},
        {"eventCode": "chat_message_send", "timestamp": now + 50, "reportDelay": 0, **common,
         "conversationId": conv_id, "requestId": rid, "messageId": "cmb-" + str(uuid.uuid4()),
         "requestModelId": "glm-5.2", "requestModelName": "GLM-5.2", "historyCount": 1,
         "isContextTruncated": False, "currentStepCount": 1, "traceId": rid, "rootRequestId": rid,
         "parentConversationId": conv_id, "agentName": "cli", "agentType": "main"}]


def report_events(headers, uid, nick, events):
    """云对话域事件上报（列表信封，每个事件内联公共字段）→ workbuddy.cn/v2/report。"""
    mid = derive_id(uid, "machine")
    out = []
    for e in events:
        env = {"timestamp": int(time.time() * 1000), "reportDelay": 0,
               "userId": uid, "userNickname": nick,
               "ideName": "WorkBuddy", "ideType": "WorkBuddy", "ideVersion": APP_VERSION,
               "machineId": mid, "sessionId": derive_id(uid, "session"),
               "mode": "CLOUD", "userAgent": UA_SHORT, "os": "Win32", "arch": "x64",
               "osVersion": "10.0.26220", "timezone": "Asia/Shanghai",
               "product": "SaaS", "releaseDate": 1789036585355,
               "commit": "5f9692923c93033111c51ad7b003eb80204a9b75",
               "extName": "workbuddy-desktop", "extVersion": APP_VERSION,
               "cpuCores": 20, "memorySize": 24}
        env.update(e)
        out.append(env)
    code_, _body = post(WORKBUDDY_BASE + "/v2/report", headers, out)
    return code_


def report_desktop_events(headers, uid, nick, events):
    """桌面域事件上报（common+events 信封，LOCAL 模式）→ workbuddy.cn/v2/report。"""
    fp = desktop_fingerprint(uid, nick)
    arr = []
    for e in events:
        m = dict(e)
        m.update(fp)
        arr.append(m)
    body = {"common": {"userId": uid, "userNickname": nick, "ideName": "WorkBuddy",
                       "ideType": "WorkBuddy", "machineId": fp["machineId"],
                       "mode": "LOCAL", "userAgent": UA_WEB, "os": "win32",
                       "timezone": "Asia/Shanghai"},
            "events": arr}
    return post(WORKBUDDY_BASE + "/v2/report", headers, body)[0]


def report_web_event(headers, uid, nick, event_code, page_url, element_id, element_name):
    """Web 域点击事件上报（Library_read）。"""
    now = int(time.time() * 1000)
    ev = {"eventCode": event_code, "timestamp": now, "reportDelay": 0,
          "pageURL": page_url, "elementId": element_id, "elementName": element_name,
          "os": "Win32", "arch": "", "osVersion": "10.0",
          "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
          "machineId": derive_id(uid, "webmachine"), "userId": uid, "userNickname": nick}
    body = {"common": {"userId": uid, "userNickname": nick, "ideName": "web",
                       "ideType": "web", "machineId": derive_id(uid, "webmachine"),
                       "mode": "CLOUD", "userAgent": "Mozilla/5.0", "os": "Win32",
                       "timezone": "Asia/Shanghai"},
            "events": [ev]}
    return post(WORKBUDDY_BASE + "/v2/report", headers, body)[0]


def report_mini_event(headers, uid, nick, ev):
    """小程序域事件上报 → copilot.tencent.com/v2/report（需 miniprogram 头）。"""
    h = mp_headers(headers)
    h["Accept"] = "application/json"
    body = {"common": {"userId": uid, "userNickname": nick, "ideName": "wx_app_cloud",
                       "ideType": "WorkBuddy_MP", "machineId": derive_id(uid, "mp-machine"),
                       "mode": "chat", "userAgent": MP_UA, "os": "Android",
                       "timezone": "Asia/Shanghai"},
            "events": [ev]}
    return post(MINI_REPORT_URL, h, body)[0]


def _mini_chat_event(uid, conv_id, activity_id=None):
    """小程序 chat_request_send 事件（点亮 Sequential_Tasks_1 / school_season）。"""
    ev = {"eventCode": "chat_request_send", "timestamp": int(time.time() * 1000),
          "reportDelay": 0, "source": "mini_program", "ideName": "wx_app_cloud",
          "ideType": "WorkBuddy_MP", "extName": "workbuddy-mp", "extVersion": "2.4.0",
          "mode": "chat", "conversationId": conv_id, "requestId": conv_id,
          "inputLength": 12, "requestModelId": "glm-5.2", "requestModelName": "GLM-5.2",
          "isPlan": False, "codebaseEnable": False, "maxToken": 0, "maxSteps": 0,
          "temperature": 0, "mentionContexts": [], "knowledgeId": [],
          "agentName": "default", "agentType": "conversation", "userId": uid}
    if activity_id:
        ev["activityId"] = activity_id
    return ev


# ---------------------------------------------------------------------------
# 专家市场（内联拉取，失败时相关任务自动跳过/兜底）
# ---------------------------------------------------------------------------
_EXPERT_CACHE = None
_EXPERT_LOCK = threading.Lock()


def fetch_expert_marketplace():
    """拉取专家市场配置（进程内缓存；失败返回 None）。"""
    global _EXPERT_CACHE
    with _EXPERT_LOCK:
        if _EXPERT_CACHE is not None:
            return _EXPERT_CACHE
    # 非关键资源：不走网络退避重试（一次失败干等 200 秒不值得），快速试两次即放弃
    h = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    for attempt in (1, 2):
        code_, body = get(EXPERT_MARKETPLACE_URL, h, timeout=15, retry=False)
        if 200 <= code_ < 300 and isinstance(body, dict):
            with _EXPERT_LOCK:
                _EXPERT_CACHE = body
            return body
        if attempt == 1 and _budget_left() > 8:
            time.sleep(3)
    return None


def _extract_name(val):
    if isinstance(val, dict):
        return val.get("zh", val.get("en", str(val)))
    return str(val)


def get_team_experts(count=5):
    """专家团列表（expertType == team）。"""
    data = fetch_expert_marketplace()
    if not data:
        return []
    team = []
    for e in data.get("experts", []):
        if not isinstance(e, dict):
            continue
        meta = e.get("_meta") or {}
        if meta.get("expertType") == "team" or e.get("expertType") == "team":
            team.append({"id": e.get("id", ""),
                         "name": _extract_name(e.get("displayName", e.get("name", {}))),
                         "industryId": meta.get("industryId", e.get("industryId", "")),
                         "profession": _extract_name(e.get("profession", ""))})
    return team[:count]


def get_normal_experts(count=10):
    """普通专家列表（expertType == agent）。"""
    data = fetch_expert_marketplace()
    if not data:
        return []
    normal = []
    for e in data.get("experts", []):
        if not isinstance(e, dict):
            continue
        meta = e.get("_meta") or {}
        if meta.get("expertType", e.get("expertType", "")) == "agent":
            normal.append({"id": e.get("id", ""),
                           "name": _extract_name(e.get("displayName", e.get("name", {}))),
                           "industryId": meta.get("industryId", e.get("industryId", "")),
                           "profession": _extract_name(e.get("profession", ""))})
    return normal[:count]


# ---------------------------------------------------------------------------
# 对话模型选择：优先免费模型，无免费则取最便宜（最小化积分消耗）
# ---------------------------------------------------------------------------
# 免费模型随平台活动轮换，当前为 hy3（混元）。改这里，或在
# ~/.workbuddy/chat_model.json 覆盖：{"free": ["hy3"], "cheap": ["glm-5.2"]}
_DEFAULT_FREE_MODELS = ["hy3"]
_DEFAULT_CHEAP_MODELS = ["glm-5.2"]


# [本仓库新增] 模型目录：默认免费/便宜模型 + 可经 chat_model.json 覆盖（见 pick_chat_model）。
def _load_model_catalog():
    cfg = {"free": list(_DEFAULT_FREE_MODELS), "cheap": list(_DEFAULT_CHEAP_MODELS)}
    p = os.path.expanduser("~/.workbuddy/chat_model.json")
    if os.path.exists(p):
        try:
            d = json.load(open(p, encoding="utf-8"))
            if isinstance(d.get("free"), list) and d["free"]:
                cfg["free"] = d["free"]
            if isinstance(d.get("cheap"), list) and d["cheap"]:
                cfg["cheap"] = d["cheap"]
        except Exception:
            pass
    return cfg


_MODEL_CATALOG = None


# === [本仓库新增] 免费/低耗模型选择 ============================================
# 解决对话类任务消耗积分的问题：优先使用当下免费模型（如 hy3），无免费模型时
# 回退到最便宜的兜底模型，确保"拉起对话"的成长任务零成本或最低成本完成。
def pick_chat_model():
    """返回最优对话模型：优先免费模型，否则最便宜的兜底模型（积分消耗最小）。"""
    global _MODEL_CATALOG
    if _MODEL_CATALOG is None:
        _MODEL_CATALOG = _load_model_catalog()
    if _MODEL_CATALOG["free"]:
        return _MODEL_CATALOG["free"][0]
    return (_MODEL_CATALOG["cheap"] or ["glm-5.2"])[0]


# Web 对话（真实 AI 调用，SSE 流式）
# ---------------------------------------------------------------------------
def webchat(headers, conv_name, prompt, meta=None, model=None):
    """真实 AI 对话：建会话 → SSE 流式补全 → 返回 (conversationId, 回复文本)。

    model=None 时自动选最优模型：优先免费模型（当前 hy3），无免费则用最便宜模型，
    确保所有"拉起对话"的成长任务不消耗积分或消耗积分最少。
    （上报的遥测事件仍按各任务要求写模型名，任务判据不依赖真实模型。）
    """
    if not model:
        model = pick_chat_model()
    """真实 AI 对话：建会话 → SSE 流式补全 → 返回 (conversationId, 回复文本)。"""
    if _budget_left() <= 10:
        return "", ""
    ccode, cbody = post(WORKBUDDY_BASE + "/console/webchat/conversations", headers,
                        {"name": "%s-%s" % (conv_name, uuid.uuid4().hex[:8])})
    conv_id = dig(cbody, "conversationId") or ""
    if not conv_id:
        return "", ""   # 会话没建成，补全请求注定失败，别浪费预算
    payload = {"messages": [{"role": "user", "content": prompt}], "model": model,
               "stream": True, "conversationId": conv_id}
    if meta:
        payload["_meta"] = meta
    h = dict(headers)
    h["Accept"] = "text/event-stream"
    txt = ""
    code_, raw = _post_stream(WORKBUDDY_BASE + "/console/chat/completions", h, payload)
    if 200 <= code_ < 300 and raw:
        for line in raw.splitlines():
            if not line.startswith("data: "):
                continue
            d = line[6:]
            if d.strip() in ("[DONE]", "[完成]", "[✅完成]"):
                break
            try:
                j = json.loads(d)
                for c in j.get("choices", []):
                    cp = (c.get("delta") or {}).get("content", "")
                    if cp:
                        txt += cp
            except Exception:
                pass
    return conv_id, txt


# ---------------------------------------------------------------------------
# 成长任务基础设施（任务列表 / 进度 / 接单 / 领奖）
# ---------------------------------------------------------------------------
def fetch_tasks(headers, max_age=TASKS_CACHE_TTL):
    """拉取成长任务列表（线程内缓存：max_age 秒内复用，max_age=0 强制刷新）。

    只缓存成功响应；拉取失败时回退旧缓存，避免一次网络抖动清空任务视图。
    """
    cache = getattr(_tls, "tasks_cache", None)
    now = time.monotonic()
    if cache and 0 < max_age and now - cache[0] < max_age:
        return cache[1]
    c, b = get(GROWTH_BASE + "/tasks", headers)
    if 200 <= c < 300:
        tasks = [t for t in (dig(b, "tasks") or []) if isinstance(t, dict)]
        _tls.tasks_cache = (now, tasks)
        return tasks
    return cache[1] if cache else []


def task_cn(code):
    return TASK_NAME_CN.get(code, code)


def _pending(st):
    """任务是否还需要做：None=不在任务列表（跳过），completed/claimed=已完成。"""
    return st is not None and st not in ("completed", "claimed")


def prog(headers, code, fresh=False):
    """查询单个成长任务进度：(accept_status, current, target)；失败 (None, None, None)。

    fresh=False 走缓存（函数入口的跳过检查）；fresh=True 强制刷新（动作后的完成验证）。
    """
    for t in fetch_tasks(headers, max_age=0 if fresh else TASKS_CACHE_TTL):
        if t.get("task_code") == code:
            pr = t.get("progress") or {}
            return t.get("accept_status", ""), pr.get("current"), pr.get("target")
    return None, None, None


def claim_task(headers, code, log):
    """领奖（幂等）：Web 口径路径 → 400 降级 web 头 → v2 口径兜底。"""
    path_web = WORKBUDDY_BASE + "/activity/growth/tasks/%s/claim" % code
    web_extra = {"Origin": WORKBUDDY_BASE, "Referer": WORKBUDDY_BASE + "/profile/growth-center",
                 "x-client-platform": "web"}
    ccode, cbody = post(path_web, headers, {})
    if ccode == 400:
        h = dict(headers)
        h.update(web_extra)
        ccode, cbody = post(path_web, h, {})
    if ccode in (400, 404):
        ccode, cbody = post(GROWTH_BASE + "/tasks/%s/claim" % code, headers, {})
    if 200 <= ccode < 300:
        if dig(cbody, "already_claimed"):
            log("🎁领奖[%s]: 已领过" % task_cn(code))
        else:
            log("🎁领奖[%s]: +%s积分+%s能量" % (task_cn(code), dig(cbody, "credit"), dig(cbody, "energy")))
    else:
        log("领奖[%s]: %s" % (task_cn(code), _http_label(ccode)))


def claim_all(headers, log):
    """扫描全部 completed 任务并逐一领取。"""
    n = 0
    for t in fetch_tasks(headers, max_age=0):
        if t.get("accept_status") == "completed" and t.get("task_code"):
            claim_task(headers, t["task_code"], log)
            n += 1
            if not _nap(1):
                break
    if n == 0:
        log("🎁 无待领奖励")


# ---------------------------------------------------------------------------
# 成长任务（t_*：全部幂等，先查进度再补缺口）
# ---------------------------------------------------------------------------
def t_accept_all(headers, uid, nick, log):
    """批量接单：not_accepted 的任务全部 accept，并等状态同步。"""
    tasks = fetch_tasks(headers)
    todo = [t.get("task_code") for t in tasks
            if t.get("task_code") and t.get("task_code") not in SKIP_AUTO_ACCEPT
            and t.get("accept_status") == "not_accepted"]
    if not todo:
        return
    for i in range(0, len(todo), 20):   # 分批，别把 body 撑大
        batch = todo[i:i + 20]
        ccode, cbody = post(GROWTH_BASE + "/tasks/accept", headers, {"task_codes": batch})
        if 200 <= ccode < 300:
            log("📋已接受任务: %s" % ",".join(task_cn(c) for c in batch))
        else:
            log("接受任务失败: %s（继续执行已有状态）" % (dig(cbody, "msg") or _http_label(ccode)))
            return
        if not _nap(WRITE_GAP):
            return
    # 接单后服务端状态同步有延迟，轮询等待（最多 ~10s）；轮询必须强制刷新缓存
    for _ in range(5):
        if not _nap(2):
            return
        still = [t.get("task_code") for t in fetch_tasks(headers, max_age=0)
                 if t.get("task_code") in todo and t.get("accept_status") == "not_accepted"]
        if not still:
            return
    log("⚠️ 部分任务状态未同步，继续执行")


# [本仓库修复] 尝鲜热门技能 skill_1 原仅桌面域上报被服务端拒绝；改为 CLOUD/web 域
# 上报（与专家/模板同款）后实测 completed 1/1 并成功领奖。
def t_desktop_fingerprint(headers, uid, nick, log):
    """桌面端对话 + 尝鲜热门技能：无头环境用稳定指纹事件链点亮，无需桌面端。"""
    need_rich = _pending(prog(headers, "RichMeow_Chat")[0])
    need_skill = _pending(prog(headers, "skill_1")[0])
    if not (need_rich or need_skill):
        return
    if need_rich:
        conv = "fp-rm-" + derive_id(uid, "rm-conv")
        req = "fp-rm-req-" + derive_id(uid, "rm-req")
        msg = "fp-rm-msg-" + derive_id(uid, "rm-msg")
        try:
            evs = desktop_chat_sequence(uid, nick, conv, req, msg)
            report_desktop_events(headers, uid, nick, evs)
            log("桌面端对话(指纹): 6连事件已上报")
            _nap(WRITE_GAP)
        except Exception as e:
            log("桌面端对话(指纹): 失败 %s" % str(e)[:60])
    if need_skill:
        try:
            # 解析一个真实可用的热门技能（优先命中 SKILL_NAME，其次取列表第一个，兜底派生）
            skill_id, skill_name = "", SKILL_NAME
            try:
                scode2, sbody2 = post(SCHOOL_DOMAIN + "/v2/operation-platform/market/skill/list",
                                      headers, {"page": 1, "page_size": 10})
                skills = dig(sbody2, "skills") or []
                for sk in skills:
                    if isinstance(sk, dict) and SKILL_NAME in str(sk.get("name", "")):
                        skill_id, skill_name = sk.get("id", ""), str(sk.get("name", ""))
                        break
                if not skill_id:
                    for sk in skills:
                        if isinstance(sk, dict) and sk.get("id"):
                            skill_id, skill_name = sk.get("id"), str(sk.get("name", SKILL_NAME))
                            break
            except Exception:
                pass
            if not skill_id:
                skill_id = "skill-" + derive_id(uid, "skill")[:12]
            # 尝试真实安装（失败不影响上报）
            try:
                scode, sbody = get(WORKBUDDY_BASE + "/console/as/marketplace/sources", headers)
                srcs = dig(sbody, "sources") or []
                mid = srcs[0].get("id") if srcs and isinstance(srcs[0], dict) else None
                if mid:
                    post(WORKBUDDY_BASE + "/console/as/user/plugins/install", headers,
                         {"plugin_name": skill_name, "marketplace_id": mid, "version": "latest"})
            except Exception:
                pass
            # 尝鲜热门技能：用 CLOUD/web 域上报（与专家/模板等成长任务一致，服务端认）；
            # 失败再回退 LOCAL/桌面域，最大化被接受概率
            ts = int(time.time() * 1000)
            cid = "conv-" + str(uuid.uuid4())
            rid = str(uuid.uuid4())
            base = [
                {"eventCode": "skill_click", "skillId": skill_id, "skillName": skill_name,
                 "timestamp": ts, "reportDelay": 0, "source": "builtin", "userId": uid},
                {"eventCode": "skill_info", "skillId": skill_id, "skillName": skill_name,
                 "timestamp": ts + 25, "reportDelay": 0, "source": "builtin", "userId": uid},
                {"eventCode": "skill_use", "skillId": skill_id, "skillName": skill_name,
                 "timestamp": ts + 50, "reportDelay": 0, "source": "builtin", "userId": uid,
                 "conversationId": cid, "requestId": rid, "messageId": "msg-" + rid},
            ]
            evs_local = [dict(e, mode="LOCAL") for e in base]
            ok = False
            try:
                report_events(headers, uid, nick, base)  # CLOUD/web 域（专家/模板同款）
                log("尝鲜热门技能(云): %s 已上报" % skill_name)
                ok = True
            except Exception as e:
                log("尝鲜热门技能(云)失败 %s，回退桌面域" % str(e)[:40])
            if not ok:
                try:
                    report_desktop_events(headers, uid, nick, evs_local)
                    log("尝鲜热门技能(桌面): %s 已上报" % skill_name)
                    ok = True
                except Exception as e:
                    log("尝鲜热门技能: 上报失败 %s" % str(e)[:60])
            if ok:
                _nap(WRITE_GAP)
        except Exception as e:
            log("尝鲜热门技能(指纹): 失败 %s" % str(e)[:60])
    codes = (["RichMeow_Chat"] if need_rich else []) + (["skill_1"] if need_skill else [])
    for i, code in enumerate(codes):
        # 第一个 fresh 刷新缓存后，后续直接复用同一份列表，别重复拉取
        st, cur, tgt = prog(headers, code, fresh=(i == 0))
        log("%s: %s %s/%s" % (task_cn(code), st, cur, tgt))
        if st == "completed":
            claim_task(headers, code, log)


def t_canvas_automation(headers, uid, nick, log):
    """设计创意模式 + 设置自动化任务 + 探索优秀灵感（纯事件上报）。"""
    if _pending(prog(headers, "create_canvas")[0]):
        report_events(headers, uid, nick, [
            {"eventCode": "agent_task_created", "source": "CLOUD", "name": "", "mode": "craft",
             "requestModelId": "default", "task_mode": "design"},
            {"eventCode": "wbx_design_canvas_task_create"}])
        _nap(3)
    if _pending(prog(headers, "automation_1")[0]):
        report_events(headers, uid, nick, [
            {"eventCode": "agent_task_created", "source": "CLOUD", "name": "", "mode": "craft",
             "requestModelId": "default", "task_mode": "automation",
             "isAutomationBackground": True},
            {"eventCode": "automated_task_create_suc", "action": "create"},
            {"eventCode": "automated_task_execute", "action": "execute"}])
        _nap(3)
    if _pending(prog(headers, "playbook_prompt")[0]):
        report_events(headers, uid, nick, [
            {"eventCode": "playbook_prompt_send", "ext1": str(uuid.uuid4()),
             "requestId": str(uuid.uuid4()), "id": "01-ProductDesign", "name": "产品设计",
             "type": "other", "promptLength": 30, "isOfficial": 1, "source": "growth-center"}])
        _nap(3)
    log("设计/自动化/灵感: %s / %s / %s" % (prog(headers, "create_canvas", fresh=True)[0],
                                            prog(headers, "automation_1")[0],
                                            prog(headers, "playbook_prompt")[0]))


def t_team_3(headers, uid, nick, log):
    """召唤3次专家团：真实团队对话 + 全字段遥测；自适应两遍（免费→目标模型兜底）。"""
    teams = get_team_experts(10)
    if not teams:
        log("召唤3次专家团: 专家市场不可用，跳过")
        return
    target = "glm-5.2"

    def _pass(model):
        for rd in range(3):
            if _budget_left() <= 30:
                log("召唤3次专家团: 预算不足，剩余次数下次再跑")
                break
            st, cur, tgt = prog(headers, "Expert_team_use_3", fresh=(rd > 0))
            if not _pending(st) or (cur or 0) >= (tgt or 3):
                break
            team = teams[rd % len(teams)]
            prompt = "你好，请简单介绍一下你们团队能帮我做什么，回答OK即可"
            req_id = str(uuid.uuid4())
            msg_id = "cmb-" + str(uuid.uuid4())
            ge = [{"eventCode": "ExpertActualUse", "id": team["id"],
                   "extra": {"name": team["name"], "expertTitle": team.get("profession", ""),
                             "type": team.get("industryId", "") or "", "expertType": "team",
                             "source": "builtin", "version": "", "cost": 8,
                             "characterCount": len(prompt), "requestId": req_id, "messageId": msg_id,
                             "requestModelId": target, "requestModelName": "GLM-5.2"},
                   "expertType": "team"}]
            meta = {"codebuddy.ai": {"growthEvent": json.dumps(ge, ensure_ascii=False),
                                     "promptRequestId": req_id,
                                     "clientSendTime": int(time.time() * 1000), "userId": uid,
                                     "mode": "craft", "model": model, "expertId": team["id"],
                                     "expert": {"id": team["id"], "name": team["name"],
                                                "profession": team.get("profession", ""),
                                                "prompt": prompt[:50]},
                                     "tags": ["expert:" + team["id"]]}}
            conv_id, _txt = webchat(headers, "team", prompt, meta)
            report_events(headers, uid, nick, [
                {"eventCode": "expert_actual_use", "id": team["id"], "name": team["name"],
                 "expertTitle": team.get("profession", ""), "type": team.get("industryId", "") or "",
                 "expertType": "team", "source": "builtin", "version": "", "cost": 8,
                 "characterCount": len(prompt), "conversationId": conv_id, "requestId": req_id,
                 "messageId": msg_id, "requestModelId": target, "requestModelName": "GLM-5.2"}])
            _nap(5)

    first = pick_chat_model()
    _pass(first)
    st, cur, tgt = prog(headers, "Expert_team_use_3", fresh=True)
    if _pending(st) and (cur or 0) < (tgt or 0) and first != target:
        log("召唤3次专家团: %s 未达标，回退 %s 兜底" % (first, target))
        _pass(target)
        st, cur, tgt = prog(headers, "Expert_team_use_3", fresh=True)
    log("召唤3次专家团: %s %s/%s" % (st, cur, tgt))


def t_buddy_apps(headers, uid, nick, log):
    """发现应用 / 企鹅教师助手：Buddy 五连事件链。"""
    for task in ("Buddy_App", "Buddy_App_QQ"):
        if _budget_left() <= 15:
            break
        st, cur, tgt = prog(headers, task)
        if not _pending(st):
            continue
        buddy_id = QQ_TPL if "QQ" in task else "buddy-app-default"
        buddy_name = "企鹅教师助手" if "QQ" in task else "发现应用"
        evs = desktop_buddy5_sequence(uid, nick, buddy_id, buddy_name)
        report_desktop_events(headers, uid, nick, evs)
        log("%s: 五连事件已上报" % task_cn(task))
        _nap(WRITE_GAP)
    log("发现应用/企鹅教师助手: %s / %s" % (prog(headers, "Buddy_App", fresh=True)[0],
                                             prog(headers, "Buddy_App_QQ")[0]))


def t_theme(headers, uid, nick, log):
    """和平精英主题：主题切换 API + 遥测。"""
    st = prog(headers, "Hp_Appearance")[0]
    if not _pending(st):
        return   # 不在任务列表或已完成
    c, b = post(WORKBUDDY_BASE + "/portal/user-asset/appearance/set", headers,
                {"kind": "theme", "resource_key": THEME_KEY})
    if dig(b, "code") == 0:
        _nap(2)
        report_events(headers, uid, nick, [
            {"eventCode": "appearance_skin_apply", "action": "apply",
             "source": "settings_close", "id": THEME_KEY, "vipLevel": "free",
             "series": "craft", "type": "personal"}])
        _nap(6)
    log("和平精英主题: %s" % prog(headers, "Hp_Appearance", fresh=True)[0])


def t_library(headers, uid, nick, log):
    """体验资料库：Web 域点击事件。"""
    st = prog(headers, "Library_read")[0]
    if not _pending(st):
        return
    report_web_event(headers, uid, nick, "web_element_click", LIB_DOC_URL,
                     "library_doc_intro_click", "WorkBuddy资料库介绍")
    _nap(6)
    log("体验资料库: %s" % prog(headers, "Library_read", fresh=True)[0])


# [本仓库增强] 对话任务默认走免费模型（pick_chat_model），并支持目标模型兜底。
def t_chat_n(headers, uid, nick, log, code, n, prompts, target_model="glm-5.2", force_model=None):
    """通用聊天任务：chat_5 / Model_chat_GLM5.2（真实 AI 对话 + 遥测）。

    自适应两遍策略：
      1) 先用免费/指定模型跑；
      2) 若进度未达标（说明该任务强制特定真实模型），自动改用 target_model 兜底，
         确保"免费能过就免费、强制模型就老实用目标模型"，首启与巡检都保完成。
    force_model 非空时直接用该模型（如 GLM-5.2 模型对话强制 glm-5.2），跳过免费尝试。
    上报事件仍按任务要求写模型名（任务判据不依赖真实模型）。
    """
    def _pass(model):
        for i in range(n):
            if _budget_left() <= 30:
                log("%s: 预算不足，剩余次数下次再跑" % task_cn(code))
                break
            st, cur, tgt = prog(headers, code, fresh=(i > 0))
            if not _pending(st) or (cur or 0) >= (tgt or n):
                break
            prompt = prompts[i % len(prompts)]
            conv_id, txt = webchat(headers, code, prompt, model=model)
            if txt:
                evs = chat_request_events(uid, nick, conv_id, prompt, txt)
                report_events(headers, uid, nick, evs)
            _nap(4)

    first = force_model or pick_chat_model()
    log("%s: 先用模型 %s 尝试（目标模型 %s）" % (task_cn(code), first, target_model))
    _pass(first)
    st, cur, tgt = prog(headers, code, fresh=True)
    if _pending(st) and (cur or 0) < (tgt or 0) and first != target_model:
        log("%s: %s 未达标(%s/%s)，回退目标模型 %s 兜底" % (task_cn(code), first, cur, tgt, target_model))
        _pass(target_model)
        st, cur, tgt = prog(headers, code, fresh=True)
    log("%s: %s %s/%s" % (task_cn(code), st, cur, tgt))


def t_glm52(headers, uid, nick, log):
    """GLM-5.2 模型对话 ×1（真实走 glm-5.2，保任务判定）+ 和AI聊天5次（免费模型）。"""
    log("对话模型策略: 真实调用优先 %s（免费）" % pick_chat_model())
    t_chat_n(headers, uid, nick, log, "Model_chat_GLM5.2", 1,
             ["你好，请介绍一下你自己"], force_model="glm-5.2")
    t_chat_n(headers, uid, nick, log, "chat_5", 5,
             ["你好", "今天天气怎么样？", "1+1等于几？", "Python是什么？", "推荐一本好书"])


def t_black_cat(headers, uid, nick, log):
    """夜猫子活动：仅北京时间 23:00-08:00 计数；自适应两遍（免费→目标模型兜底）。"""
    st = prog(headers, "black_cat")[0]
    if not _pending(st):
        return
    if not within_night_window():
        log("夜猫子: 仅23:00-08:00计数（北京时间），当前 %d 点，跳过" % beijing_now().hour)
        return
    prompts = ["今天天气怎么样？", "1+1等于几？", "讲个笑话"]
    target = "glm-5.2"

    def _pass(model):
        for attempt in range(8):
            if _budget_left() <= 30:
                break
            st2, cur2, tgt2 = prog(headers, "black_cat", fresh=(attempt > 0))
            if not _pending(st2) or (cur2 or 0) >= (tgt2 or 3):
                break
            conv_id, txt = webchat(headers, "night", prompts[attempt % len(prompts)], model=model)
            if txt:
                evs = chat_request_events(uid, nick, conv_id, "聊天", txt)
                report_events(headers, uid, nick, evs)
                log("夜猫子: 第%d次对话 ✅(%s)" % (attempt + 1, model))
            else:
                log("夜猫子: 第%d次对话 ❌（无回复）" % (attempt + 1))
            _nap(5)

    first = pick_chat_model()
    _pass(first)
    st, cur, tgt = prog(headers, "black_cat", fresh=True)
    if _pending(st) and (cur or 0) < (tgt or 0) and first != target:
        log("夜猫子: %s 未达标，回退 %s 兜底" % (first, target))
        _pass(target)
        st, cur, tgt = prog(headers, "black_cat", fresh=True)
    log("夜猫子: %s %s/%s" % (st, cur, tgt))


def t_expert_5(headers, uid, nick, log):
    """召唤5次专家：普通专家召唤 + 实际使用遥测。"""
    experts = get_normal_experts(20)
    st0, cur0, tgt0 = prog(headers, "expert_5")
    need = max(0, (tgt0 or 5) - (cur0 or 0))
    if not _pending(st0):
        need = 0
    for i in range(need):
        if _budget_left() <= 15:
            break
        st, cur, tgt = prog(headers, "expert_5", fresh=(i > 0))
        if not _pending(st) or (cur or 0) >= (tgt or 5):
            break
        e = experts[i % len(experts)] if experts else {
            "id": "expert-" + str(uuid.uuid4())[:8], "name": "Expert", "profession": ""}
        report_events(headers, uid, nick, [
            {"eventCode": "expert_summoned", "id": e["id"], "name": e["name"], "type": "agent",
             "expertTitle": e.get("profession", ""), "expertType": "agent"},
            {"eventCode": "expert_actual_use", "id": e["id"], "name": e["name"],
             "type": e.get("industryId", "") or "", "expertType": "agent", "source": "builtin",
             "version": "", "cost": 0, "characterCount": 12,
             "conversationId": "conv-" + str(uuid.uuid4()), "requestId": str(uuid.uuid4()),
             "messageId": "msg-" + str(uuid.uuid4()),
             "requestModelId": "deepseek-v4-flash", "requestModelName": "DeepSeek V4 Flash"}])
        _nap(3)
    st, cur, tgt = prog(headers, "expert_5", fresh=True)
    log("召唤5次专家: %s %s/%s" % (st, cur, tgt))


def t_template_5(headers, uid, nick, log):
    """使用5个模板：批量遥测。"""
    for i, sc in enumerate(TEMPLATE_SCENES):
        if _budget_left() <= 15:
            break
        st, cur, tgt = prog(headers, "template_5", fresh=(i > 0))
        if not _pending(st) or (cur or 0) >= (tgt or 5):
            break
        tid = sc["id"]
        report_events(headers, uid, nick, [
            {"eventCode": "agent_task_created", "source": "CLOUD", "name": "", "mode": "craft",
             "requestModelId": "default", "action": tid, "has_template": True,
             "template_id": tid, "template_name": sc["name"]},
            {"eventCode": "agent_task_created_with_template", "templateId": tid,
             "templateName": sc["name"], "isCustomModel": True, "id": tid, "name": sc["name"]},
            {"eventCode": "playbook_prompt_send", "ext1": str(uuid.uuid4()),
             "requestId": str(uuid.uuid4()), "id": tid, "name": sc["name"], "type": "other",
             "promptLength": 30, "isOfficial": 1, "source": "growth-center"}])
        _nap(2)
    st, cur, tgt = prog(headers, "template_5", fresh=True)
    log("使用5个模板: %s %s/%s" % (st, cur, tgt))


def t_lighthouse(headers, uid, nick, log):
    """腾讯轻量云专家：专家召唤 + 实际使用遥测（市场拉不到时用兜底专家）。"""
    st = prog(headers, "Expert_lighthouse")[0]
    if not _pending(st):
        return
    experts = get_normal_experts(20)
    lh = next((e for e in experts
               if "轻量" in (e.get("name") or "") or "lighthouse" in (e.get("id") or "").lower()), None)
    if not lh:
        lh = {"id": "expert-lh-" + str(uuid.uuid4())[:8], "name": "轻量云专家", "profession": ""}
    rid = str(uuid.uuid4())
    cid = "conv-" + str(uuid.uuid4())
    report_events(headers, uid, nick, [
        {"eventCode": "expert_summoned", "id": lh["id"], "name": lh["name"], "type": "agent",
         "expertTitle": lh.get("profession", ""), "expertType": "agent", "source": "builtin",
         "timestamp": int(time.time() * 1000)},
        {"eventCode": "expert_actual_use", "id": lh["id"], "name": lh["name"],
         "expertTitle": lh.get("profession", ""), "type": "agent", "expertType": "agent",
         "source": "builtin", "version": "", "cost": 0, "characterCount": 12,
         "conversationId": cid, "requestId": rid, "messageId": rid,
         "requestModelId": "deepseek-v4-flash", "requestModelName": "DeepSeek V4 Flash",
         "userId": uid}])
    _nap(3)
    log("腾讯轻量云专家: %s %s/%s" % prog(headers, "Expert_lighthouse", fresh=True))


# === [本仓库新增 · 合并自 L0NE-6/WorkBuddy-Daily] 体验专家任务族 ================
# 与轻量云专家同族：Valorant / 工作台搭建师 / 4 个电商专家。
# 这些任务服务端靠"专家召唤 + 实际使用"事件链判定，无头环境用 CLOUD 事件链兜底即可完成，
# 无需像 L0NE 那样真重启桌面端（那只在 Windows 客户端环境可行，沙箱为无头 Linux）。
EXPERT_EXPERIENCE_SPECS = {
    "WorkBuddy_Valorant": {"id": "expert-valorant", "name": "无畏契约拼豆专家", "title": "无畏契约拼豆"},
    "workstation_expert": {"id": "expert-workspace", "name": "工作台搭建师", "title": "工作台搭建"},
    "expert_use_maidehao": {"id": "ex_GDl31WahyIH0", "name": "卖得好", "title": "中国电商运营专家"},
    "expert_use_douyinyin": {"id": "ex_FbY5nlWTqDod", "name": "斗音音", "title": "抖音策略师"},
    "expert_use_shangjia_xuanchuan": {"id": "ex_Weo3x2EZuSDm", "name": "商家宣传设计师", "title": "商家宣传页与海报设计师"},
    "expert_use_bowangwang": {"id": "ex_WZY136wV5aMt", "name": "播旺旺", "title": "直播电商教练"},
}


def t_expert_experience(headers, uid, nick, log, code):
    """体验专家任务：召唤 + 实际使用遥测（CLOUD 事件链，无头环境可完成）。

    与 t_lighthouse 同法；code 必须在 EXPERT_EXPERIENCE_SPECS 内（含兜底 id/name），
    市场拉不到真人专家时用内置专家 id 也能点亮（上游实测接受）。
    """
    spec = EXPERT_EXPERIENCE_SPECS.get(code)
    if not spec:
        return
    st = prog(headers, code)[0]
    if not _pending(st):
        return
    exp_id, exp_name, exp_title = spec["id"], spec["name"], spec.get("title", "")
    rid, cid = str(uuid.uuid4()), "conv-" + str(uuid.uuid4())
    report_events(headers, uid, nick, [
        {"eventCode": "expert_summoned", "id": exp_id, "name": exp_name, "type": "agent",
         "expertTitle": exp_title, "expertType": "agent", "source": "builtin",
         "timestamp": int(time.time() * 1000)},
        {"eventCode": "expert_actual_use", "id": exp_id, "name": exp_name,
         "expertTitle": exp_title, "type": "agent", "expertType": "agent",
         "source": "builtin", "version": "", "cost": 0, "characterCount": 12,
         "conversationId": cid, "requestId": rid, "messageId": rid,
         "requestModelId": "deepseek-v4-flash", "requestModelName": "DeepSeek V4 Flash",
         "userId": uid}])
    _nap(3)
    st, cur, tgt = prog(headers, code, fresh=True)
    log("%s: %s %s/%s" % (task_cn(code), st, cur, tgt))


def t_expert_experience_all(headers, uid, nick, log):
    """批量跑全部体验专家任务（跳过已完成的），单项异常不拖垮整轮。"""
    for code in EXPERT_EXPERIENCE_SPECS:
        try:
            t_expert_experience(headers, uid, nick, log, code)
        except Exception as e:
            log("%s: 异常 %s" % (task_cn(code), str(e)[:60]))


def t_first_buddy(headers, uid, nick, log):
    """新账号：领取第一只 Buddy（领养链路）。"""
    st = prog(headers, "first_buddy")[0]
    if not _pending(st):
        return
    report_events(headers, uid, nick,
                  [{"eventCode": "buddy_agreement_view", "timestamp": int(time.time() * 1000)}])
    _nap(2)
    post(GROWTH_BASE + "/buddy/agreement", headers, {"agree": True})
    _nap(WRITE_GAP)
    c, b = post(GROWTH_BASE + "/buddy/first", headers, {})
    if 200 <= c < 300:
        log("🐱首只Buddy: 成功 (+%s积分 +%s能量)" % (dig(b, "credit"), dig(b, "energy")))
    else:
        log("🐱首只Buddy: %s" % (dig(b, "msg") or _http_label(c)))


def _try_expert_chain(headers, uid, nick, log, code, spec):
    """专家体验类新任务的兜底：召唤 + 实际使用事件链（与 t_expert_experience 同法）。"""
    try:
        if not _pending(prog(headers, code)[0]):
            return
        exp_id, exp_name = spec["id"], spec["name"]
        exp_title = spec.get("title", exp_name)
        rid, cid = str(uuid.uuid4()), "conv-" + str(uuid.uuid4())
        report_events(headers, uid, nick, [
            {"eventCode": "expert_summoned", "id": exp_id, "name": exp_name, "type": "agent",
             "expertTitle": exp_title, "expertType": "agent", "source": "builtin",
             "timestamp": int(time.time() * 1000)},
            {"eventCode": "expert_actual_use", "id": exp_id, "name": exp_name,
             "expertTitle": exp_title, "type": "agent", "expertType": "agent",
             "source": "builtin", "version": "", "cost": 0, "characterCount": 12,
             "conversationId": cid, "requestId": rid, "messageId": rid,
             "requestModelId": "deepseek-v4-flash", "requestModelName": "DeepSeek V4 Flash",
             "userId": uid}])
        _nap(3)
        st, cur, tgt = prog(headers, code, fresh=True)
        log("🆕专家类新任务[%s]: %s %s/%s（自动链兜底）" % (code, st, cur, tgt))
    except Exception as e:
        log("🆕专家类新任务[%s]: 兜底失败 %s" % (code, str(e)[:60]))


def _try_chat_chain(headers, uid, nick, log, code):
    """对话类新任务的兜底：真实对话（优先免费模型）+ 上报 chat 事件。"""
    try:
        if not _pending(prog(headers, code)[0]):
            return
        conv_id, txt = webchat(headers, code, "你好，请用一句话介绍你自己")
        if txt:
            evs = chat_request_events(uid, nick, conv_id, "你好", txt)
            report_events(headers, uid, nick, evs)
            _nap(2)
            st, cur, tgt = prog(headers, code, fresh=True)
            log("🆕对话类新任务[%s]: %s %s/%s（免费模型兜底）" % (code, st, cur, tgt))
        else:
            log("🆕对话类新任务[%s]: 无回复，未点亮" % code)
    except Exception as e:
        log("🆕对话类新任务[%s]: 兜底失败 %s" % (code, str(e)[:60]))


def _try_generic_chain(headers, uid, nick, log, code, title):
    """通用新任务的兜底：上报 viewed/use 激活事件后探进度（非对话/非专家类）。"""
    try:
        if not _pending(prog(headers, code)[0]):
            return
        report_events(headers, uid, nick, [
            {"eventCode": "growth_task_viewed", "taskCode": code, "taskName": title or code,
             "source": "builtin", "timestamp": int(time.time() * 1000)},
            {"eventCode": "growth_task_use", "taskCode": code, "taskName": title or code,
             "source": "builtin"}])
        _nap(2)
        st, cur, tgt = prog(headers, code, fresh=True)
        log("🆕通用新任务[%s]: %s %s/%s（激活兜底，未点亮请反馈）" % (code, st, cur, tgt))
    except Exception as e:
        log("🆕通用新任务[%s]: 兜底失败 %s" % (code, str(e)[:60]))


# [本仓库增强] 未知/新上线任务三路兜底：专家链 / 对话（免费模型）/ 通用激活。
def t_unknown_tasks(headers, uid, nick, log):
    """任务体检 + 新任务按类兜底：发现未覆盖任务，分类尝试自动完成（专家链/对话/通用激活）。

    覆盖策略：已知码（KNOWN_TASK_CODES）与已完成项直接跳过；公众号/公益按人工规则处理；
    其余新任务按 专家类 / 对话类 / 通用类 三种判据尝试兜底，最大化"新任务也能自动应对"。
    """
    try:
        for t in fetch_tasks(headers, max_age=0):
            code = t.get("task_code", "")
            st = t.get("accept_status", "")
            if code in KNOWN_TASK_CODES or st in ("claimed", "completed"):
                continue
            desc = str(t.get("task_desc", ""))[:50]
            title = t.get("title", "")
            low = (code + " " + title + " " + desc).lower()
            if "subscribe" in low or "公众号" in (title + desc):
                # 已关注则交给 claim_all 自动领取；尚未关注才提示人工
                log("🔔公众号任务待领: %s %s — 已关注将由脚本自动领取，未关注请先在微信关注" % (code, title))
            elif "donat" in low or "捐款" in desc or "公益" in title:
                log("⏭️公益类任务跳过（需真实捐款，按用户要求略过）: %s %s" % (code, title))
            elif "expert" in low or "valorant" in low:
                spec = EXPERT_EXPERIENCE_SPECS.get(code) or {
                    "id": "expert-" + hashlib.md5(code.encode()).hexdigest()[:12],
                    "name": title or code, "title": title or code}
                _try_expert_chain(headers, uid, nick, log, code, spec)
            elif "chat" in low or "对话" in (title + desc) or "聊天" in (title + desc):
                _try_chat_chain(headers, uid, nick, log, code)
            else:
                _try_generic_chain(headers, uid, nick, log, code, title)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 小程序成长任务（mp 口径：需 X-Client-Platform: miniprogram 才下发）
# ---------------------------------------------------------------------------
def mp_fetch_tasks(headers):
    """小程序口径任务列表（不缓存：与 web 口径列表不同，且每账号仅查几次）。"""
    c, b = get(GROWTH_BASE + "/tasks", mp_headers(headers))
    if not (200 <= c < 300):
        return []
    return [t for t in (dig(b, "tasks") or []) if isinstance(t, dict)]


def mp_prog(headers, code):
    """小程序口径查询任务进度。"""
    for t in mp_fetch_tasks(headers):
        if t.get("task_code") == code:
            pr = t.get("progress") or {}
            return t.get("accept_status", ""), pr.get("current"), pr.get("target")
    return None, None, None


def mp_accept(headers, code):
    """小程序口径接单（缺头会返回 task not found）。"""
    c, b = post(GROWTH_BASE + "/tasks/accept", mp_headers(headers), {"task_codes": [code]})
    results = dig(b, "results") or []
    status = (results[0].get("status") or "") if results and isinstance(results[0], dict) \
        else (dig(b, "msg") or "")
    return 200 <= c < 300 and status == "accepted"


def mp_claim(headers, code, log):
    """小程序口径领奖（缺头会 400）。"""
    c, b = post(WORKBUDDY_BASE + "/activity/growth/tasks/%s/claim" % code,
                mp_headers(headers), {})
    if 200 <= c < 300:
        already = dig(b, "already_claimed")
        log("🎁领奖[%s]: %s" % (task_cn(code),
                                "已领过" if already else "+%s积分+%s能量" % (dig(b, "credit"), dig(b, "energy"))))
        return True
    log("🎁领奖[%s]: 失败 %s" % (task_cn(code), _http_label(c)))
    return False


def t_sequential_tasks(headers, uid, nick, log):
    """小程序成长任务 Sequential_Tasks_1（+100积分+5能量）。"""
    st, cur, tgt = mp_prog(headers, "Sequential_Tasks_1")
    if st is None:
        log("小程序对话任务: mp 口径未下发该任务，跳过")
        return
    if st in ("completed", "claimed"):
        if st == "completed":
            mp_claim(headers, "Sequential_Tasks_1", log)
        else:
            log("小程序对话任务: 已领取，跳过")
        return
    if st == "not_accepted":
        if not mp_accept(headers, "Sequential_Tasks_1"):
            log("小程序对话任务: 接单失败，跳过")
            return
        _nap(WRITE_GAP)
    conv = "mini-" + str(uuid.uuid4())
    try:
        report_mini_event(headers, uid, nick, _mini_chat_event(uid, conv))
        log("小程序对话任务: mini chat 已上报")
        _nap(2.5)
        st2, cur2, tgt2 = mp_prog(headers, "Sequential_Tasks_1")
        if st2 in ("completed", "claimed"):
            log("小程序对话任务: ✅ 已完成 %s/%s" % (cur2, tgt2))
            if st2 == "completed":
                mp_claim(headers, "Sequential_Tasks_1", log)
        else:
            log("小程序对话任务: %s %s/%s（服务端暂未关联）" % (st2, cur2, tgt2))
    except Exception as e:
        log("小程序对话任务: 失败 %s" % str(e)[:60])


def t_school_season(headers, uid, nick, log):
    """小程序成长任务 school_season：mp 口径 + activityId 上报（+100积分+5能量）。"""
    st, cur, tgt = mp_prog(headers, "school_season")
    if st is None:
        log("校园日活动: mp 口径未下发该任务，跳过")
        return
    if st in ("completed", "claimed"):
        if st == "completed":
            mp_claim(headers, "school_season", log)
        else:
            log("校园日活动: 已领取，跳过")
        return
    if st == "not_accepted":
        if not mp_accept(headers, "school_season"):
            log("校园日活动: 接单失败，跳过")
            return
        _nap(WRITE_GAP)
    conv = "mini-ss-" + str(uuid.uuid4())
    try:
        report_mini_event(headers, uid, nick,
                          _mini_chat_event(uid, conv, activity_id=SCHOOL_ACTIVITY_ID))
        log("校园日活动: mini chat+activityId 已上报")
        _nap(2.5)
        st2, cur2, tgt2 = mp_prog(headers, "school_season")
        if st2 in ("completed", "claimed"):
            log("校园日活动: ✅ 已完成 %s/%s" % (cur2, tgt2))
            if st2 == "completed":
                mp_claim(headers, "school_season", log)
        else:
            log("校园日活动: %s %s/%s（服务端暂未关联）" % (st2, cur2, tgt2))
    except Exception as e:
        log("校园日活动: 失败 %s" % str(e)[:60])


def t_mp_adaptive(headers, uid, nick, log):
    """小程序新任务自动适配：mp 口径出现未知小程序任务时，自动接单 + mini chat 上报 + 领奖。

    只处理 web 口径已知任务之外的 mp 专属任务（避免与成长任务重复执行）；
    上报的是通用 mini chat 判据，非对话类任务可能不点亮，日志会明确提示。
    """
    tasks = mp_fetch_tasks(headers)
    unknown = [t.get("task_code") for t in tasks
               if t.get("task_code") and t.get("task_code") not in KNOWN_TASK_CODES
               and t.get("accept_status") not in ("completed", "claimed")]
    if not unknown:
        return
    for code in unknown:
        if _budget_left() <= 15:
            log("📱新任务[%s]: 预算不足，下次再跑" % code)
            break
        st = next((t.get("accept_status") for t in tasks if t.get("task_code") == code), "")
        if st == "not_accepted":
            if not mp_accept(headers, code):
                log("📱新任务[%s]: 接单失败，跳过" % code)
                continue
            _nap(WRITE_GAP)
        conv = "mini-ad-" + uuid.uuid4().hex[:8]
        report_mini_event(headers, uid, nick, _mini_chat_event(uid, conv))
        log("📱新任务[%s]: mini chat 已上报（自动适配）" % code)
        _nap(2.5)
        st2, cur2, tgt2 = mp_prog(headers, code)
        if st2 in ("completed", "claimed"):
            log("📱新任务[%s]: ✅ 已完成 %s/%s" % (code, cur2, tgt2))
            if st2 == "completed":
                mp_claim(headers, code, log)
        else:
            log("📱新任务[%s]: %s %s/%s（判据可能非对话类，需人工确认）" % (code, st2, cur2, tgt2))


# ---------------------------------------------------------------------------
# 互动玩法（g_*：8 项）
# ---------------------------------------------------------------------------
def g_travel(headers, log):
    """派猫猫旅行：到达领礼物 / 旅行中等待 / 空闲出发（幂等状态机）。"""
    base = GROWTH_BASE + "/buddy/travel"
    try:
        scode, sbody = get(base + "/status", headers)
        if not (200 <= scode < 300):
            return
        travel = dig(sbody, "state")
        daily_limit = bool(dig(sbody, "daily_limit_reached"))
        if travel == "arrived":
            record_id = dig(sbody, "record_id")
            ccode, cbody = post(base + "/claim", headers, {"record_id": record_id})
            if 200 <= ccode < 300 and dig(cbody, "reward_credit") is not None:
                log("🐾领旅行礼物 +%s 积分" % fmt_credit(dig(cbody, "reward_credit")))
            else:
                log("🐾领旅行礼物失败: %s" % (dig(cbody, "msg") or _http_label(ccode)))
            travel = "idle"
        if travel == "idle" and daily_limit:
            log("🐾今日旅行名额已用完")
        elif travel == "idle":
            ccode, cbody = get(base + "/config", headers)
            locs = dig(cbody, "locations") if (200 <= ccode < 300) else None
            if locs and isinstance(locs[0], dict):
                loc = locs[0]
                dcode, dbody = post(base + "/depart", headers, {"location_id": loc.get("id")})
                if 200 <= dcode < 300:
                    loc_name = (dig(dbody, "location") or {}).get("name", "?")
                    dur = dig(dbody, "duration_hours") or \
                        (dig(dbody, "location") or {}).get("duration_hours", "?")
                    log("🐾派 Buddy 去%s（%s 小时后回）" % (loc_name, dur))
                else:
                    log("🐾派 Buddy 失败: %s" % (dig(dbody, "msg") or _http_label(dcode)))
        elif travel == "traveling":
            loc_name = (dig(sbody, "location") or {}).get("name", "?")
            log("🐾Buddy 旅行中（%s%s）" % (loc_name,
                                           _fmt_eta(dig(sbody, "arrive_at"), dig(sbody, "server_now"))))
    except Exception as e:
        log("旅行模块异常（%s: %s）" % (type(e).__name__, e))


def g_redeem(headers, log):
    """连登兑换三档（入门7d/进阶14d/巅峰28d）：tier 传档位标识，未解锁视为常态。"""
    try:
        rcode, rbody = get(GROWTH_BASE + "/redeem/summary", headers)
        if not (200 <= rcode < 300):
            return
        for tier, status_key, label, days in _REDEEM_TIERS:
            status = dig(rbody, status_key + "_status")
            # 字段缺失（None）同样跳过：接口改版时不该让脚本对三档无脑 POST
            if not status or status in ("claimed", "locked"):
                continue
            c2code, c2body = post(GROWTH_BASE + "/redeem", headers,
                                  {"tier": tier, "client_token": _client_token()})
            # 档位标识被判为未知时退回天数再试一次：这类 400 是参数校验阶段的拒绝，
            # 服务端没兑换任何东西，重试不会重复领取
            if _is_unknown_tier(c2code, c2body):
                c2code, c2body = post(GROWTH_BASE + "/redeem", headers,
                                      {"tier": days, "client_token": _client_token()})
            # 403「连登天数不足」是业务常态，必须先于 401/403 通用判定，
            # 否则未解锁档位会被误报成"登录态已失效"
            if _is_tier_locked(c2code, c2body):
                continue
            if 200 <= c2code < 300:
                log("🎁连登兑换「%s」%s" % (label, _redeem_reward_desc(c2body, tier)))
            elif c2code not in (401, 403):
                log("连登兑换「%s」失败: %s" % (label, dig(c2body, "msg") or _http_label(c2code)))
    except Exception as e:
        log("连登兑换模块异常（%s: %s）" % (type(e).__name__, e))


def g_makeup(headers, log):
    """断登补登：服务端给出可补日期时用补登卡补（每轮最多 1 张，卡是稀缺资源）。"""
    try:
        mcode, mbody = get(GROWTH_BASE + "/streak", headers)
        if not (200 <= mcode < 300):
            return
        cards_obj = dig(mbody, "makeup_cards")
        cards = as_int(cards_obj.get("balance")) if isinstance(cards_obj, dict) else as_int(cards_obj)
        streak_obj = dig(mbody, "streak") or {}
        dates = (streak_obj.get("makeup_dates") if isinstance(streak_obj, dict) else None) \
            or dig(mbody, "makeup_dates") or []
        if cards > 0 and isinstance(dates, list) and dates:
            for d in dates[:min(cards, MAKEUP_MAX_PER_RUN)]:
                ucode, ubody = post(GROWTH_BASE + "/makeup-cards/use", headers,
                                    {"target_date": d, "client_token": _client_token()})
                if 200 <= ucode < 300:
                    cards -= 1
                    left_obj = dig(ubody, "makeup_cards")
                    left_cards = as_int(left_obj.get("balance"), cards) \
                        if isinstance(left_obj, dict) else as_int(left_obj, cards)
                    log("🩹补登 %s（剩 %s 张卡）" % (d, left_cards))
                else:
                    log("🩹补登 %s 失败: %s" % (d, dig(ubody, "msg") or _http_label(ucode)))
            if len(dates) > MAKEUP_MAX_PER_RUN and cards > 0:
                log("🩹另有 %s 天可补、剩 %s 张卡，下次继续" % (len(dates) - MAKEUP_MAX_PER_RUN, cards))
    except Exception as e:
        log("补登模块异常（%s: %s）" % (type(e).__name__, e))


def g_lottery(headers, log):
    """幸运抽奖：查剩余次数并全部抽完；"无次数"是常态不计失败。"""
    try:
        lcode, lbody = get(GROWTH_BASE + "/lottery/chances", headers)
        chances = as_int(dig(lbody, "balance")) if (200 <= lcode < 300) else 0
        if chances <= 0:
            return
        won = []
        for i in range(chances):
            if i > 0 and not _nap(2):
                break
            dcode, dbody = post(GROWTH_BASE + "/lottery/draw", headers,
                                {"client_token": _client_token()})
            if 200 <= dcode < 300:
                prize = dig(dbody, "prize_name") or dig(dbody, "prize") or "未知"
                if not isinstance(prize, str):
                    prize = str(prize)
                if dig(dbody, "need_address") or dig(dbody, "require_address"):
                    prize += "（实物奖，需到成长中心填写收件信息）"
                won.append(prize)
            else:
                msg = dig(dbody, "msg") or ""
                if not _is_no_chance(msg):
                    log("🎰抽奖失败: %s" % (msg or _http_label(dcode)))
                break
        if won:
            log("🎰抽奖: %s" % "、".join(won))
    except Exception as e:
        log("抽奖模块异常（%s: %s）" % (type(e).__name__, e))


def g_blindbox(headers, log):
    """能量开 Buddy 盲盒（每次 10 能量，最多开 5 个）。"""
    try:
        qcode, qbody = get(GROWTH_BASE + "/buddy/quota", headers)
        if not (200 <= qcode < 300):
            return
        affordable = as_int(dig(qbody, "affordable"))
        if affordable <= 0:
            return
        n = min(affordable, 5)
        got = []
        for _ in range(n):
            ocode, obody = post(GROWTH_BASE + "/buddy/open", headers,
                                {"count": 1, "client_token": _client_token()})
            if 200 <= ocode < 300:
                results = dig(obody, "results") or []
                if results and isinstance(results[0], dict):
                    it = results[0]
                    ins = it.get("instance") or {}
                    tpl = it.get("template") or {}
                    got.append("%s(%s)" % (ins.get("name", tpl.get("name", "?")),
                                           ins.get("rarity", tpl.get("rarity", ""))))
                else:
                    name = dig(obody, "buddy") or dig(obody, "name") or "新 Buddy"
                    got.append(str(name))
            else:
                break
            if not _nap(1.5):
                break
        if got:
            log("📦盲盒: %s" % "、".join(got))
    except Exception as e:
        log("盲盒模块异常（%s: %s）" % (type(e).__name__, e))


def g_buddy_info(headers, log):
    """Buddy 信息（纯展示）。"""
    try:
        c, b = get(GROWTH_BASE + "/buddy/info", headers)
        if 200 <= c < 300:
            bd = dig(b, "buddy") or {}
            if isinstance(bd, dict) and bd.get("name"):
                log("🐱Buddy: %s (%s)%s" % (bd.get("name", "?"), bd.get("rarity", ""),
                                            ", " + bd.get("personality") if bd.get("personality") else ""))
    except Exception:
        pass


def g_badges(headers, log):
    """徽章统计（纯展示）。"""
    try:
        c, b = get(GROWTH_BASE + "/badges", headers)
        if 200 <= c < 300:
            badges = dig(b, "badges") or dig(b, "list") or []
            earned = sum(1 for x in badges if isinstance(x, dict) and x.get("earned"))
            log("🏅徽章: %s 个" % earned)
    except Exception:
        pass


def g_gift(headers, log):
    """新手礼包（每号一次）+ 补偿领取（活动开启时）。"""
    try:
        c, b = post(WORKBUDDY_BASE + "/billing/meter/claim-gift", headers, {})
        if 200 <= c < 300 and dig(b, "code") == 0:
            log("🎊新手礼包: +%s积分" % dig(b, "credit"))
    except Exception:
        pass
    try:
        c, b = post(WORKBUDDY_BASE + "/billing/meter/claim-compensation", headers, {})
        if 200 <= c < 300 and dig(b, "code") == 0:
            log("🎊补偿领取: +%s积分" % dig(b, "credit"))
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 开学季活动（school_open_day_2026 · codebuddy.cn 域）
# ---------------------------------------------------------------------------
def _school_fetch_tasks(headers):
    c, b = get(SCHOOL_BASE + "/tasks", school_headers(headers))
    if not (200 <= c < 300) or dig(b, "code") != 0:
        return [], False
    return (dig(b, "tasks") or []), bool(dig(b, "in_period"))


def _school_report(headers, uid, nick, events, desktop=False):
    """开学季事件上报：默认 codebuddy.cn 域；desktop=True 走 copilot 域（桌面任务判据）。"""
    if desktop:
        out = {"common": {"userId": uid, "userNickname": nick, "ideName": "WorkBuddy",
                          "ideType": "WorkBuddy", "machineId": derive_id(uid, "machine"),
                          "mode": "LOCAL", "userAgent": UA_WEB, "os": "win32",
                          "timezone": "Asia/Shanghai"},
               "events": events}
        h = dict(headers)
        h["X-Product"] = "SaaS"
        return post(MINI_REPORT_URL, h, out)[0]
    out = {"common": {"userId": uid, "userNickname": nick, "ideName": "web-Agents",
                      "ideType": "web-Agents", "machineId": derive_id(uid, "machine"),
                      "mode": "CLOUD", "userAgent": MP_UA, "os": "Android",
                      "timezone": "Asia/Shanghai"},
           "events": events}
    return post(SCHOOL_DOMAIN + "/v2/report", school_headers(headers), out)[0]


def _school_fetch_expert(headers):
    """拉取 BackToSchool 分类专家；失败回落兜底专家。"""
    try:
        c, b = post(SCHOOL_DOMAIN + "/v2/operation-platform/market/expert/list",
                    school_headers(headers),
                    {"page": 1, "page_size": 10,
                     "categories": [SCHOOL_EXPERT_CATEGORY], "expert_type": "agent"})
        experts = dig(b, "experts") or []
        if 200 <= c < 300 and experts and isinstance(experts[0], dict):
            e = experts[0]
            return e.get("id", ""), e.get("displayName", e.get("name", "开学季专家"))
    except Exception:
        pass
    return "expert-school-01", "开学季专家"


def _school_mini_chat_event(uid, conv_id):
    """开学季小程序对话事件（带 activityId）。"""
    rid = str(uuid.uuid4())
    return [{"eventCode": "chat_request_send", "timestamp": int(time.time() * 1000),
             "reportDelay": 0, "source": "mini_program", "ideName": "wx_app_cloud",
             "ideType": "WorkBuddy_MP", "extName": "workbuddy-mp", "extVersion": "2.4.0",
             "mode": "chat", "activityId": SCHOOL_ACTIVITY_ID,
             "conversationId": conv_id, "requestId": conv_id, "messageId": "msg-" + rid,
             "requestModelId": "glm-5.2", "requestModelName": "GLM-5.2",
             "inputLength": 12, "mentionContexts": [], "mentionContextCount": 0,
             "isPlan": False, "codebaseEnable": False, "maxToken": 0, "maxSteps": 0,
             "temperature": 0, "agentName": "default", "agentType": "conversation",
             "userId": uid}]


def _school_desktop_seq_events(uid, nick, conv_id):
    """开学季桌面对话：6 连指纹事件 + activityId。"""
    evs = desktop_chat_sequence(uid, nick, conv_id, conv_id, conv_id)
    fp = desktop_fingerprint(uid, nick)
    out = []
    for e in evs:
        m = dict(e)
        m.update(fp)
        m["activityId"] = SCHOOL_ACTIVITY_ID
        out.append(m)
    return out


def _school_expert_events(uid, expert_id, expert_name, conv_id):
    """开学季专家召唤 + 实际使用事件。"""
    rid = str(uuid.uuid4())
    mid_msg = "msg-" + rid
    now = int(time.time() * 1000)
    return [
        {"eventCode": "expert_summoned", "id": expert_id, "name": expert_name,
         "type": "agent", "expertType": "agent", "source": "builtin",
         "version": "", "reportDelay": 0, "timestamp": now,
         "activityId": SCHOOL_ACTIVITY_ID, "userId": uid},
        {"eventCode": "expert_actual_use", "id": expert_id, "name": expert_name,
         "expertTitle": expert_name, "type": "agent", "expertType": "agent", "source": "builtin",
         "version": "", "cost": 0, "characterCount": 12, "reportDelay": 0,
         "requestId": rid, "messageId": mid_msg, "conversationId": conv_id,
         "requestModelId": "deepseek-v4-flash", "requestModelName": "DeepSeek V4 Flash",
         "timestamp": now, "activityId": SCHOOL_ACTIVITY_ID, "userId": uid}]


def school_run_tasks(headers, uid, nick, log):
    """开学季任务：viewed 激活 → 判据上报 → 轮询 → 领奖。"""
    sh = school_headers(headers)
    tasks, in_period = _school_fetch_tasks(headers)
    if not in_period:
        log("🏫 开学季活动非进行期，跳过")
        return
    log("🏫 ── 开学季活动（%d 个任务）──" % len(tasks))
    for t in tasks:
        if _budget_left() <= 20:
            log("🏫 预算不足，剩余开学季任务下次再跑")
            break
        code = t.get("task_code", "")
        status = t.get("status", "")
        spec = SCHOOL_TASK_MODES.get(code)
        if not code or status in ("completed", "claimed"):
            continue
        if spec is None:
            log("🏫 %s: 未知任务类型，跳过" % code)
            continue
        if spec["mode"] == "manual":
            log("🏫 %s: 人工环节（%s），跳过" % (code, spec.get("note", "")))
            continue
        # viewed 激活
        try:
            c, b = post(SCHOOL_BASE + "/tasks/%s/viewed" % code, sh)
            if 200 <= c < 300 and dig(b, "code") == 0:
                log("🏫 %s: viewed 已激活" % code)
                _nap(WRITE_GAP)
        except Exception as e:
            log("🏫 %s: viewed 失败 %s" % (code, str(e)[:60]))
            continue
        # 判据
        try:
            if spec["mode"] == "share":
                c, b = post(SCHOOL_BASE + "/tasks/share-complete", sh, {"channel": "wechat"})
                ok = 200 <= c < 300 and dig(b, "code") == 0
                log("🏫 %s: share-complete %s" % (code, "✅" if ok else "❌"))
                _nap(WRITE_GAP)
            elif spec["mode"] == "report":
                kind = spec.get("kind", "")
                conv_id = "conv-" + str(uuid.uuid4())
                if kind == "mini_chat":
                    for i in range(3):
                        _school_report(headers, uid, nick, _school_mini_chat_event(uid, conv_id))
                        log("🏫 %s: chat #%d/3 ✅" % (code, i + 1))
                        _nap(WRITE_GAP)
                elif kind == "desktop_seq":
                    _school_report(headers, uid, nick,
                                   _school_desktop_seq_events(uid, nick, conv_id), desktop=True)
                    log("🏫 %s: desktop_seq 已上报" % code)
                    _nap(WRITE_GAP)
                elif kind == "expert":
                    eid, ename = _school_fetch_expert(headers)
                    _school_report(headers, uid, nick,
                                   _school_expert_events(uid, eid, ename, conv_id))
                    log("🏫 %s: expert_use ✅（%s）" % (code, ename))
                    _nap(WRITE_GAP)
        except Exception as e:
            log("🏫 %s: 上报失败 %s" % (code, str(e)[:60]))
        # 轮询等待完成
        for _ in range(5):
            if not _nap(2):
                break
            try:
                ts2, _ip = _school_fetch_tasks(headers)
                after = next((x for x in ts2 if x.get("task_code") == code), None)
                if after and after.get("status") in ("completed", "claimed"):
                    break
            except Exception:
                pass
        # 领奖
        try:
            ts3, _ip = _school_fetch_tasks(headers)
            after = next((x for x in ts3 if x.get("task_code") == code), None)
            if after and after.get("status") == "completed":
                c, b = post(SCHOOL_BASE + "/tasks/%s/claim" % code, sh)
                if 200 <= c < 300 and dig(b, "code") == 0:
                    log("🏫 %s: 🎁 已领奖" % code)
                    _nap(WRITE_GAP)
        except Exception as e:
            log("🏫 %s: claim 失败 %s" % (code, str(e)[:60]))


def school_lottery(headers, uid, nick, log):
    """开学季幸运大转盘：查余额 → 循环抽到 0。"""
    sh = school_headers(headers)
    try:
        c, b = get(SCHOOL_BASE + "/config", sh)
        if not (200 <= c < 300) or dig(b, "code") != 0:
            return
        chance = dig(b, "chance") or {}
        bal = as_int(chance.get("balance"))
        if bal <= 0:
            return
        log("🏫 大转盘余额 %s，开始抽奖..." % bal)
        results = []
        while bal > 0:
            if not _nap(WRITE_GAP):
                break
            try:
                c2, b2 = post(SCHOOL_BASE + "/wheel/draw", sh, {"draw_uuid": str(uuid.uuid4())})
                code2 = dig(b2, "code")
                if code2 == 40900:
                    break   # 次数耗尽
                if not (200 <= c2 < 300) or code2 != 0:
                    log("🏫 抽奖失败: %s" % (dig(b2, "msg") or _http_label(c2)))
                    break
                prize = dig(b2, "prize_code") or ""
                label = LOTTERY_PRIZE_LABELS.get(prize, prize or "未知")
                results.append(label)
                bal -= 1
            except Exception as e:
                log("🏫 抽奖异常 %s" % str(e)[:60])
                break
        if results:
            log("🏫 大转盘: %d 抽，奖品: %s" % (len(results), "、".join(results)))
    except Exception as e:
        log("🏫 大转盘异常 %s" % str(e)[:80])


# ---------------------------------------------------------------------------
# 每日签到（原有已验证逻辑，走凭证 auth.endpoint 的签到域）
# ---------------------------------------------------------------------------
def _is_already_checked_in(cbody):
    if cbody is None:
        return True
    if isinstance(cbody, dict):
        msg = cbody.get("msg") or ""
        if cbody.get("code") == 10001 or "已签" in msg:
            return True
    return False


def _already_report(status, via=None):
    today_credit = dig(status, "today_credit") or dig(status, "daily_credit")
    streak_days = dig(status, "streak_days")
    total_credits = dig(status, "total_credits")
    is_streak_day = dig(status, "is_streak_day")
    inner = []
    if today_credit is not None:
        inner.append("今日 +%s" % fmt_credit(today_credit))
    if streak_days is not None:
        inner.append("连续 %s 天" % streak_days)
    if total_credits is not None:
        inner.append("累计 %s 积分" % fmt_credit(total_credits))
    prefix = via or "今日已签过"
    report = "%s（%s）" % (prefix, "，".join(inner)) if inner else prefix
    return {
        "result": "ALREADY",
        "report": report,
        "today_credit": today_credit,
        "streak_days": streak_days,
        "total_credits": total_credits,
        "is_streak_day": is_streak_day,
    }


def run_checkin(headers, endpoint):
    """每日签到：查状态 → 未签才领 → 返回 (退出码, 汇报 dict)。"""
    scode, sbody = post(endpoint + "/v2/billing/meter/checkin-activity-status", headers, retry=True)

    if scode == CODE_BUDGET_OUT:
        return 1, {"result": "TIMEOUT", "report": "已达本次运行时间预算，签到跳过，下次自动重试"}
    if scode == CODE_NO_NETWORK:
        return 1, {"result": "NETWORK",
                   "report": "网络不可达，签到跳过，下次自动重试（%s）" % (sbody.get("error") or "")}
    if scode in (401, 403):
        return 1, {"result": "NO_SESSION",
                   "report": "登录态已失效（HTTP %s），请重新 login 导入" % scode}
    if not (200 <= scode < 300):
        return 1, {"result": "ERROR",
                   "report": "签到接口返回异常（HTTP %s），请稍后重试" % scode}

    status = sbody if isinstance(sbody, dict) else {}
    active = dig(status, "active")
    activity_name = dig(status, "activity_name")

    if active is False:
        report = "签到活动未开启" + ("（%s）" % activity_name if activity_name else "")
        return 0, {"result": "INACTIVE", "report": report, "active": False}

    if dig(status, "today_checked_in") in (True, 1):
        return 0, _already_report(status)

    ccode, cbody = post(endpoint + "/v2/billing/meter/daily-checkin", headers, retry=True)

    if ccode in (CODE_NO_NETWORK, CODE_BUDGET_OUT):
        return 1, {"result": "NETWORK" if ccode == CODE_NO_NETWORK else "TIMEOUT",
                   "report": "领取请求未能送达，下次自动重试（%s）" % (
                       (cbody.get("error") or "") if isinstance(cbody, dict) else "")}

    if ccode in (401, 403):
        return 1, {"result": "NO_SESSION",
                   "report": "登录态已失效（HTTP %s），请重新 login 导入" % ccode}

    if _is_already_checked_in(cbody):
        scode2, sbody2 = post(endpoint + "/v2/billing/meter/checkin-activity-status", headers, retry=True)
        fresh = sbody2 if (200 <= scode2 < 300 and isinstance(sbody2, dict)) else status
        return 0, _already_report(fresh, via="今日已签过（服务端判定已领取）")

    credit = dig(cbody, "credit")
    if credit is not None:
        scode2, sbody2 = post(endpoint + "/v2/billing/meter/checkin-activity-status", headers, retry=True)
        fresh = sbody2 if (200 <= scode2 < 300 and isinstance(sbody2, dict)) else status
        streak_days = dig(fresh, "streak_days") or dig(status, "streak_days")
        total_credits = dig(fresh, "total_credits")
        is_streak_day = dig(fresh, "is_streak_day")
        bonus = "，且为连签奖励日" if is_streak_day else ""
        cum = "，累计 %s 积分" % fmt_credit(total_credits) if total_credits is not None else ""
        streak = "（连续 %s 天%s）" % (streak_days, cum) if streak_days is not None else (
            "（%s）" % cum.lstrip("，") if cum else "")
        report = "成功领取 %s 积分%s%s" % (fmt_credit(credit), bonus, streak)
        return 0, {"result": "CLAIMED",
                   "report": report, "credit": credit, "streak_days": streak_days,
                   "total_credits": total_credits, "is_streak_day": is_streak_day}

    if isinstance(cbody, dict) and ("code" in cbody or "msg" in cbody):
        msg = cbody.get("msg") or ("code %s" % cbody.get("code"))
        return 1, {"result": "ERROR", "report": "领取失败：%s（HTTP %s）" % (msg, ccode)}

    return 1, {"result": "UNKNOWN",
               "report": "未识别的领取返回，请检查接口：%s" % json.dumps(cbody, ensure_ascii=False)[:200]}


# ---------------------------------------------------------------------------
# 单账号全流程
# ---------------------------------------------------------------------------
def run_full(uin, session, mode="auto"):
    """单账号全流程。mode: auto | growth | school | query。返回汇总 dict。"""
    account = session.get("account") or {}
    display = str(account.get("nickname") or account.get("uin") or uin)

    def log(m):
        # 日志时间戳统一北京时间：青龙容器多为 UTC，用本地时间会误导排查
        print("[%s][%s] %s" % (beijing_now().strftime("%H:%M:%S"), display, m))

    summary = {"note": display, "checkin": "", "credits": "", "usage": "",
               "level": "?", "streak": "?", "energy": "?", "done": 0, "total": 0, "rest": []}

    # 0. Token 自动续期（AT 7 天内过期或缺失时用 RT 轮换并回写）
    try:
        auto_refresh_session(uin, session, log)
    except Exception as e:
        log("⚠️ Token 续期异常: %s" % str(e)[:60])

    try:
        headers = build_headers(session)
    except ValueError as e:
        summary["checkin"] = str(e)
        summary["rest"] = ["登录态失效"]
        log("❌ %s" % e)
        return summary
    endpoint = ((session.get("auth") or {}).get("endpoint") or DEFAULT_ENDPOINT).rstrip("/")
    wb_h = wb_headers(headers)          # 成长/遥测/对话域
    uid = str(account.get("uid") or "")
    nick = str(account.get("nickname") or uid)

    # 1. 查询（积分套餐 / 用量 / 成长概况）
    try:
        credits = query_credits(wb_h)
        usage = query_usage(wb_h)
        growth = query_growth(wb_h)
        summary.update({"credits": credits, "usage": usage, "level": growth["level"],
                        "streak": growth["streak"], "energy": growth["energy"]})
        log("💰 积分: %s" % credits)
        log("📊 用量: %s" % usage)
        log("🌱 成长: 等级%s 连签%s天 能量%s 累签%s天" % (
            growth["level"], growth["streak"], growth["energy"], growth["signed"]))
    except Exception as e:
        log("查询异常（%s: %s）" % (type(e).__name__, e))
    if mode == "query":
        return summary

    # 2. 每日签到（仅 auto；走凭证 auth.endpoint 签到域）
    if mode == "auto":
        try:
            _code, out = run_checkin(headers, endpoint)
            summary["checkin"] = out.get("report", "")
            log("✅ 签到: %s" % summary["checkin"])
            if out.get("result") == "NO_SESSION":
                summary["rest"] = ["登录态失效"]
                return summary
        except Exception as e:
            summary["checkin"] = "签到异常（%s: %s）" % (type(e).__name__, e)
            log("❌ %s" % summary["checkin"])

    # 3. 成长任务 + 互动玩法（auto / growth）
    if mode in ("auto", "growth"):
        log("☁️ ── 成长任务 ──")
        steps = (
            ("接单", lambda: t_accept_all(wb_h, uid, nick, log)),
            ("桌面任务", lambda: t_desktop_fingerprint(wb_h, uid, nick, log)),
            ("设计/自动化/灵感", lambda: t_canvas_automation(wb_h, uid, nick, log)),
            ("专家团", lambda: t_team_3(wb_h, uid, nick, log)),
            ("Buddy应用", lambda: t_buddy_apps(wb_h, uid, nick, log)),
            ("主题", lambda: t_theme(wb_h, uid, nick, log)),
            ("资料库", lambda: t_library(wb_h, uid, nick, log)),
            ("AI对话", lambda: t_glm52(wb_h, uid, nick, log)),
            ("夜猫子", lambda: t_black_cat(wb_h, uid, nick, log)),
            ("专家×5", lambda: t_expert_5(wb_h, uid, nick, log)),
            ("模板×5", lambda: t_template_5(wb_h, uid, nick, log)),
            ("轻量云专家", lambda: t_lighthouse(wb_h, uid, nick, log)),
            ("体验专家", lambda: t_expert_experience_all(wb_h, uid, nick, log)),
            ("首只Buddy", lambda: t_first_buddy(wb_h, uid, nick, log)),
            ("小程序任务", lambda: t_sequential_tasks(wb_h, uid, nick, log)),
            ("校园日任务", lambda: t_school_season(wb_h, uid, nick, log)),
            ("小程序新任务", lambda: t_mp_adaptive(wb_h, uid, nick, log)),
        )
        for name, fn in steps:
            if _budget_left() <= 10:
                log("⏳ 预算不足，「%s」及后续任务下次再跑" % name)
                break
            try:
                fn()
            except Exception as e:
                log("「%s」异常（%s: %s）" % (name, type(e).__name__, e))

        log("🎮 ── 互动玩法 ──")
        plays = (
            ("旅行", lambda: g_travel(wb_h, log)),
            ("连登兑换", lambda: g_redeem(wb_h, log)),
            ("补登", lambda: g_makeup(wb_h, log)),
            ("抽奖", lambda: g_lottery(wb_h, log)),
            ("盲盒", lambda: g_blindbox(wb_h, log)),
            ("Buddy信息", lambda: g_buddy_info(wb_h, log)),
            ("徽章", lambda: g_badges(wb_h, log)),
            ("礼包", lambda: g_gift(wb_h, log)),
        )
        for name, fn in plays:
            if _budget_left() <= 5:
                log("⏳ 预算不足，「%s」及后续玩法下次再跑" % name)
                break
            try:
                fn()
            except Exception as e:
                log("「%s」异常（%s: %s）" % (name, type(e).__name__, e))

        t_unknown_tasks(wb_h, uid, nick, log)

        # 自动领奖 + 终态统计
        log("🎁 ── 领奖 ──")
        try:
            claim_all(wb_h, log)
        except Exception as e:
            log("领奖异常（%s: %s）" % (type(e).__name__, e))
        try:
            tasks = fetch_tasks(wb_h, max_age=0)
            done = sum(1 for t in tasks if t.get("accept_status") in ("claimed", "completed"))
            rest = [task_cn(t.get("task_code", "")) for t in tasks
                    if t.get("accept_status") not in ("claimed", "completed")]
            summary.update({"done": done, "total": len(tasks), "rest": rest})
            log("🏁 成长任务: 完成%s/%s，剩余: %s" % (
                done, len(tasks), "、".join(rest) if rest else "无"))
        except Exception as e:
            log("终态统计异常（%s: %s）" % (type(e).__name__, e))

    # 4. 开学季活动（auto / school；WORKBUDDY_NO_SCHOOL=true 可跳过）
    if mode in ("auto", "school") and not NO_SCHOOL:
        try:
            school_run_tasks(wb_h, uid, nick, log)
            school_lottery(wb_h, uid, nick, log)
        except Exception as e:
            log("🏫 开学季活动异常: %s" % str(e)[:80])

    return summary


# ---------------------------------------------------------------------------
# 中文报告（推送用）
# ---------------------------------------------------------------------------
def build_summary(summaries):
    """各账号中文报告 + 总计统计 + 待办分布。"""
    total_done = total_tasks = 0
    lines = ["📊 WorkBuddy 各账号运行报告", ""]
    for i, sm in enumerate(summaries):
        total_done += as_int(sm.get("done"))
        total_tasks += as_int(sm.get("total"))
        lines.append("👤 账号%d  %s" % (i + 1, str(sm.get("note", ""))[:16]))
        if sm.get("checkin"):
            lines.append("   ✅ 签到: %s" % sm["checkin"])
        lines.append("   💰 %s" % (sm.get("credits") or "暂无数据"))
        lines.append("   📊 %s" % (sm.get("usage") or "暂无数据"))
        lines.append("   🌱 等级%s | 连签%s天 | 能量%s" % (
            sm.get("level", "?"), sm.get("streak", "?"), sm.get("energy", "?")))
        rest = sm.get("rest") or []
        if rest:
            lines.append("   ⏳ 未完成: %s" % "、".join(rest))
        else:
            lines.append("   ✅ 全部完成！")
        lines.append("")
    lines.append("📊 ══ 总计 ══")
    lines.append("👥 共%d个账号，成长任务完成 %d/%d 项" % (len(summaries), total_done, total_tasks))
    all_rest = {}
    for sm in summaries:
        for r in (sm.get("rest") or []):
            all_rest[r] = all_rest.get(r, 0) + 1
    if all_rest:
        lines.append("")
        for cn, cnt in sorted(all_rest.items(), key=lambda x: -x[1]):
            lines.append("   · %s（%d个账号待完成）" % (cn, cnt))
    lines.append("")
    lines.append("🕐 %s（北京时间）" % beijing_now().strftime("%Y-%m-%d %H:%M"))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def _fmt_seconds(seconds):
    if seconds <= 0:
        return "立即执行"
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    if h > 0:
        return f"{h}小时{m}分{s}秒"
    if m > 0:
        return f"{m}分{s}秒"
    return f"{s}秒"


def _random_delay(label=""):
    """每个账号执行前独立随机延时（0 ~ MAX_RANDOM_DELAY 秒），带倒计时，避免大量账号同时执行。"""
    who = f"[{label}] " if label else ""
    delay = random.randint(0, MAX_RANDOM_DELAY)
    print(f"{who}⏳ 随机延时 {_fmt_seconds(delay)} 后开始执行")
    remaining = delay
    while remaining > 0:
        if remaining <= 10 or remaining % 10 == 0:
            print(f"   倒计时: {_fmt_seconds(remaining)}")
        step = 1 if remaining <= 10 else min(10, remaining)
        time.sleep(step)
        remaining -= step
    print(f"{who}随机延时结束，开始执行")


def do_auto(mode="auto"):
    """多账号并行执行全流程，最后汇总推送中文报告。"""
    creds = load_creds()
    if not creds:
        msg = "未找到任何凭证。请先在本机执行 python workbuddy_checkin.py login 生成 auths/<uid>.json。"
        print(f"⚠️  {msg}")
        notify_user("WorkBuddy 签到", f"⚠️ {msg}")
        return 2

    tagline = {"auto": "签到+成长中心+开学季", "growth": "成长中心", "school": "开学季+小程序",
               "query": "查询"}[mode]
    random_hint = "（开启，上限 %s 秒/账号）" % MAX_RANDOM_DELAY if RANDOM_SIGNIN else "（未开启随机延时）"
    print(f"== WorkBuddy {tagline}开始，共 {len(creds)} 个账号，并行随机延时{random_hint} - "
          f"{beijing_now().strftime('%Y-%m-%d %H:%M:%S')}（北京时间）==")

    results = {}
    lock = threading.Lock()

    def worker(uin, session):
        if RANDOM_SIGNIN and mode != "query":
            _random_delay(uin)
        _start_budget()  # 随机延时结束后才启动本账号请求预算：延时不计入预算
        try:
            sm = run_full(uin, session, mode=mode)
        except Exception as e:
            print(f"❌ [{uin}] 运行异常: {type(e).__name__}: {e}")
            sm = {"note": uin, "checkin": f"脚本运行异常: {e}", "rest": ["运行异常"]}
        with lock:
            results[uin] = sm

    threads = [threading.Thread(target=worker, args=(uin, session)) for uin, session in creds]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    summaries = [results[uin] for uin, _ in creds]
    report = build_summary(summaries)
    print()
    print(report)
    notify_user("🌱 WorkBuddy 签到报告", report)
    # 全部账号都异常才判失败（部分成功按成功处理，细节看报告）
    failed = sum(1 for sm in summaries if sm.get("rest") == ["运行异常"] or sm.get("rest") == ["登录态失效"])
    return 1 if failed == len(summaries) and failed > 0 else 0


def do_debug(action):
    """status / claim / all：签到接口调试。"""
    creds = load_creds()
    if not creds:
        print("⚠️  未找到任何凭证，请先执行 login。")
        return 2
    for uin, session in creds:
        _start_budget()
        try:
            headers = build_headers(session)
        except ValueError as e:
            print(f"[{uin}] NO_SESSION: {e}")
            continue
        endpoint = ((session.get("auth") or {}).get("endpoint") or DEFAULT_ENDPOINT).rstrip("/")
        if action in ("status", "all"):
            scode, sbody = post(endpoint + "/v2/billing/meter/checkin-activity-status", headers, retry=True)
            print(f"[{uin}] status http={scode} body={json.dumps(sbody, ensure_ascii=False, default=str)[:500]}")
        if action in ("claim", "all"):
            ccode, cbody = post(endpoint + "/v2/billing/meter/daily-checkin", headers, retry=True)
            print(f"[{uin}] claim http={ccode} body={json.dumps(cbody, ensure_ascii=False, default=str)[:500]}")
    return 0


def main():
    _start_budget()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "auto"
    try:
        if cmd == "login":
            return do_login()
        if cmd == "refresh":
            return do_refresh()
        if cmd == "query":
            return do_auto(mode="query")
        if cmd == "school":
            return do_auto(mode="school")
        if cmd == "growth":
            return do_auto(mode="growth")
        if cmd == "auto":
            return do_auto(mode="auto")
        if cmd in ("status", "claim", "all"):
            return do_debug(cmd)
        print(f"❌ 未知命令：{cmd}")
        print(__doc__)
        return 2
    except Exception as e:
        print(f"❌ 脚本运行异常（{type(e).__name__}: {e}）")
        return 2


if __name__ == "__main__":
    sys.exit(main())
