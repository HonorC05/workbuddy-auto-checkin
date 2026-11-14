#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# =================================================================================
#  task_catalog.py —— 任务分类索引（便于定位 / 查找 / 更新代码）
#
#  本文件为本仓库原创（MIT，版权归 HonorC05 (workbuddy-auto-checkin)）。
#  纯索引工具，不参与运行链路、不发起任何请求；清单从运行代码动态汇总，
#  避免手工文档与实现脱节。
#
#  用法：
#    python task_catalog.py                    # 打印全部分类
#    python task_catalog.py --find chat       # 按 code / 名称 / 类别 / 客户端查找
#    python task_catalog.py --client          # 只看需要指定客户端的任务
# =================================================================================
"""按「频率 / 触发方式」给全部任务分组并标注实现位置，方便后续定位与维护。"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import wb_engine as E
import wb_upstream as U

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ---------------------------------------------------------------------------
# 分类口径：按「什么时候做 / 做几次」划分，而不是按接口域
# ---------------------------------------------------------------------------
CATEGORIES = [
    ("每日", "每天可重复：签到、成长每日任务、热力墙活跃",
     "wb_engine.run_full · wb_upstream.run_daily_activity"),
    ("固定一次性", "只做一次：新手任务、补偿 / 礼包、分享渠道",
     "wb_upstream.run_benefits · run_skill_share"),
    ("限时活动", "活动期内有效：星巴克 / 记者节 / 开学季",
     "wb_upstream.run_campaigns · wb_engine.t_school"),
    ("连续任务", "小程序 Sequential_Tasks_2~7", "wb_upstream.run_sequential"),
    ("互动玩法", "旅行 / 抽奖 / 盲盒 / 转盘 / 连登兑换 / 徽章",
     "wb_engine.run_full 玩法段"),
    ("补签兜底", "漏签补签、达标补领、未下发守卫、异常自愈",
     "wb_upstream.sign_retry_* · claim_ready_tasks"),
    ("账号与统计", "账号态识别、积分增量、终态口径、推送",
     "wb_upstream.preflight · finalize"),
]

_SEQ_CODES = [row[0] for row in U.SEQUENTIAL]
_CAMPAIGN_CODES = [spec["code"] for spec in U.CAMPAIGN_SPECS]

# 已知 code → 类别。未列出的自动归入「其他（待归类）」，保证不漏、不编造。
CATEGORY_OF = {
    "checkin": "每日", "daily_activity": "每日", "chat_5": "每日",
    "Model_chat_GLM5.2": "每日", "Expert_team_use_3": "每日",
    "expert_5": "每日", "skill_1": "每日", "template_5": "每日",
    "automation_1": "每日", "black_cat": "每日",
    "skill_share": "固定一次性", "compensation": "固定一次性",
    "newcomer_gift": "固定一次性", "campaign": "限时活动",
    "sign_retry": "补签兜底", "claim_ready": "补签兜底", "makeup": "补签兜底",
    "credits_delta": "账号与统计", "preflight": "账号与统计",
    # 成长中心其余任务（全部归类，避免清单与实现脱节）
    "Sequential_Tasks_1": "连续任务", "school_season": "限时活动",
    "RichMeow_Chat": "每日", "Expert_lighthouse": "每日",
    "playbook_prompt": "每日", "create_canvas": "每日",
    "Buddy_App": "固定一次性", "Buddy_App_QQ": "固定一次性",
    "Expert_Philanthropy": "固定一次性", "Hp_Appearance": "固定一次性",
    "Library_read": "固定一次性", "first_buddy": "固定一次性",
    "wb_wechat_oa_subscribe_task": "固定一次性",
    "WorkBuddy_Valorant": "固定一次性", "workstation_expert": "固定一次性",
    "expert_use_bowangwang": "固定一次性", "expert_use_douyinyin": "固定一次性",
    "expert_use_maidehao": "固定一次性",
    "expert_use_shangjia_xuanchuan": "固定一次性",
}
for _c in _SEQ_CODES:
    CATEGORY_OF[_c] = "连续任务"
for _c in _CAMPAIGN_CODES:
    CATEGORY_OF[_c] = "限时活动"

# 需要指定客户端的任务 → 自动化通道（用户不带电脑也能完成）
CLIENT_OF = {"skill_share": "桌面 + 小程序（官方分享渠道 + 事件族）",
             "Sequential_Tasks_7": "PC（官方 playbook 事件族）",
             "Sequential_Tasks_1": "小程序（mp 口径官方事件族）",
             "school_season": "小程序（mp 口径官方事件族）",
             "RichMeow_Chat": "桌面端（官方指纹 / CLOUD 事件族）",
             "playbook_prompt": "PC（官方 playbook 事件族）",
             "create_canvas": "PC（官方事件族）",
             "workstation_expert": "桌面端（CLOUD 事件链兜底）"}
for _c in _SEQ_CODES:
    CLIENT_OF.setdefault(_c, "小程序（mp 口径官方事件族）")
for _c in _CAMPAIGN_CODES:
    CLIENT_OF[_c] = "小程序 + App 云端会话 / PC 官方事件"

# 引擎 TASK_NAME_CN 未收录、但属于链路关键节点的条目
EXTRA = {
    "checkin": "每日签到", "daily_activity": "每日活跃热力墙",
    "compensation": "补偿积分", "newcomer_gift": "新手礼包",
    "sign_retry": "签到分钟级补签队列", "claim_ready": "达标补领",
    "makeup": "智能补签候选", "credits_delta": "积分增量统计",
    "preflight": "账号态识别",
}


def _rows():
    names = dict(getattr(E, "TASK_NAME_CN", {}) or {})
    names.update(EXTRA)
    for code, label, *_ in U.SEQUENTIAL:
        names.setdefault(code, label)
    for spec in U.CAMPAIGN_SPECS:
        names.setdefault(spec["code"], spec["label"])
    out, seen = [], set()
    for code, cn in sorted(names.items()):
        if code in seen:
            continue
        seen.add(code)
        out.append({"code": code, "name": cn,
                    "category": CATEGORY_OF.get(code, "其他（待归类）"),
                    "client": CLIENT_OF.get(code, "任意（标准 Web 口径）")})
    return out


def _print(rows):
    grouped = {}
    for r in rows:
        grouped.setdefault(r["category"], []).append(r)
    order = [c[0] for c in CATEGORIES] + ["其他（待归类）"]
    for cat in order:
        items = grouped.get(cat)
        if not items:
            continue
        meta = next((c for c in CATEGORIES if c[0] == cat), None)
        print("\n== %s ==" % cat)
        if meta:
            print("   %s" % meta[1])
            print("   实现: %s" % meta[2])
        for r in items:
            print("   · %-30s %-16s %s" % (r["code"], r["name"], r["client"]))
    print("\n共 %d 项；按类别索引，未归类项显式列出，避免清单与实现脱节。" % len(rows))


def main():
    rows = _rows()
    args = sys.argv[1:]
    if args and args[0] == "--find" and len(args) > 1:
        kw = args[1].lower()
        rows = [r for r in rows if kw in " ".join(str(v) for v in r.values()).lower()]
    elif args and args[0] == "--client":
        rows = [r for r in rows if not r["client"].startswith("任意")]
        if len(args) > 1:
            kw = args[1].lower()
            rows = [r for r in rows if kw in r["client"].lower()]
    _print(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
