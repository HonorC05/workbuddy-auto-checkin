# WorkBuddy 全自动积分助手

> 📖 语言 / Language: **[简体中文](./README.md)** · **[English](./README_EN.md)**

> 一个面向 WorkBuddy / CodeBuddy 的**全自动积分领取**工具：每日签到、成长中心任务、
> 互动玩法、开学季活动等 **35 项任务**一键跑完，并支持长效令牌、守护进程常驻、失败
> 自动复查与新任务自适应。

---

## ⚠️ 重要声明

- 本项目是**第三方逆向脚本**，**与 WorkBuddy / 腾讯官方无关**。所用接口随时可能失效，
  项目不保证长期可用。
- 仅供**个人学习与研究**使用。请遵守相关平台规则与当地法律法规，**勿用于任何违规或
  欺诈用途**（例如绕过真实捐款骗取公益积分等行为）。
- 使用本项目的任何后果由使用者自行承担。
- 本仓库**不内置任何账号凭证**，也不会上传你的任何数据。

---

## 📦 功能概览

| 类别 | 覆盖 | 说明 |
|---|---|---|
| 每日签到 | ✅ 连签 / 累计积分 | 自动领取，支持连签兑换、补签卡 |
| 成长中心（18 项） | 17 项全自动 + 1 项需人工 | 桌面端对话、尝鲜热门技能、体验资料库、各类专家、主题、模板、Buddy、夜猫子等 |
| 互动玩法（8 项） | ✅ | 抽奖、盲盒、派猫猫旅行、连签兑换、补签、Buddy 信息、徽章、礼包补偿 |
| 开学季活动（5 项） | 4 项全自动 + 大转盘 | 分享、AI 对话、桌面对话、开学季专家、大转盘抽奖 |
| 小程序任务（3 项） | ✅ | 小程序对话、校园日、未知小程序任务自动适配 |
| 指定客户端任务 | ✅ 全自动化 | 小程序 / PC / App 判据统一走**官方客户端通道 + 官方事件族 + 真实云端会话**，默认全开，不带电脑也能完成 |
| 对话类任务 | ✅ 免费优先 | **所有任务一律先用免费模型**（如 `hy3`）；仅当免费模型失败 / 被拒才回退任务指定模型 |
| 跨平台 | ✅ 开箱即用 | Windows / macOS / Linux / 沙箱同一条命令启动，纯标准库，不依赖 bash / systemd |

**已实现的"无人值守"能力：**

- 🔑 **长效令牌**：`refreshToken` 每次运行自动轮换续期，配置一次长期可用。
- 🤖 **双层守护**：`python start.py` 后台拉起 watch + daemon；每日 **08:00 全量** +
  每 2 小时巡逻，**漏跑 / 失败自动复查补拉**，进程掉线 15 秒内自动重启。
- 🆕 **新任务自适应**：未覆盖的新任务按「专家链 / 对话 / 通用激活」三路兜底，新上线
  任务无需改代码即可被识别并尝试自动完成。
- 💡 **省积分对话**：所有对话任务先免费模型，失败才回退指定模型，积分消耗降到最低。
- 🗂️ **任务分类索引**：`python task_catalog.py` 按「每日 / 固定一次性 / 限时活动 /
  连续任务 / 互动玩法 / 补签兜底 / 账号与统计」列出全部任务及实现位置。

---

## 📁 目录结构

```
workbuddy-auto-checkin/
├── LICENSE              # MIT 许可证（第三方版权归属见 NOTICE）
├── NOTICE               # 第三方来源与版权归属声明
├── README.md            # 本文件（简体中文）
├── README_EN.md         # 英文文档
├── .gitignore           # 忽略凭据 / 缓存 / 日志
├── wb_engine.py         # 【第三方派生】核心任务引擎（派生自下方开源项目，含本仓库增强）
├── wb_upstream.py       # 【本仓库原创】上游能力合入层（15 类缺失功能，可整体关闭）
├── workbuddy_auto.py    # 【本仓库原创】统一入口 / 守护调度 / 凭据适配
├── start.py             # 【本仓库原创】跨平台无人值守启动器（win / mac / linux 通用）
├── task_catalog.py      # 【本仓库原创】任务分类索引（按类型定位代码实现）
├── export_rt.py         # 【本仓库原创】长效令牌导出工具（Windows 客户端本机用）
├── start.sh             # Unix 备用拉起脚本（bash）
└── workbuddy-auto.service  # systemd 单元（真机 / VPS 常驻用）
```

---

## 🧩 第三方来源（务必阅读）

`wb_engine.py` 为**派生作品（derivative work）**，原始代码来自以下以 MIT 许可证发布的
开源项目。本仓库在保留原作者版权声明的前提下，对其做了功能合并与增强：

| 项目 | 地址 |
|---|---|
| xz0609/workbuddy-checkin-ql | https://github.com/xz0609/workbuddy-checkin-ql |
| L0NE-6/WorkBuddy-Daily | https://github.com/L0NE-6/WorkBuddy-Daily |

本仓库新增 / 增强的部分（免费模型选择、体验专家任务族、尝鲜技能 CLOUD 域修复、对话
任务目标模型兜底、新任务三路兜底等）均在 `wb_engine.py` 中以 `[本仓库新增/增强]`
标注。完整说明见 [`NOTICE`](./NOTICE)，许可文本见 [`LICENSE`](./LICENSE)。

---

## 🧩 上游能力合入层（wb_upstream.py）

对照上游 `L0NE-6/WorkBuddy-Daily`（v3.42~v3.50）与 `xz0609/workbuddy-checkin-ql`
逐项比对后，本地缺失的能力统一在 `wb_upstream.py` 实现，主引擎仅做带异常隔离的挂接。
合入的能力包括：

- 账号态识别（企业版账号 / 受限 `11140` / 渠道拦截 `11-128`）
- 成长任务三口径快照与「未下发」守卫、领奖回读确认与达标补领
- `accept` 落账修复、终态口径校正、有效期提醒、**积分增量统计**
- 签到分钟级补签队列、智能补签候选、一次性补偿 / 新手礼包
- 小程序活动任务（星巴克 / 记者节）、`skill_share` 真实分享渠道、连续任务 2~7
- 每日活跃上报、会话数上限清理、多通道推送（Bark / Server酱 / 钉钉 / 企业微信 / WxPusher）

所有新增能力默认开启、逐项 `try/except` 隔离，单项异常不影响既有签到与领奖链路；
活动会话只向受信任的官方 HTTPS 域名发送令牌，状态文件不保存凭据 / UID / 手机号。
可用 `WORKBUDDY_UPSTREAM=0` 整体关闭。

> 只读自检（不接单 / 不领奖 / 不上报）：`python wb_upstream.py probe`

---

## 🚀 安装

要求 **Python 3.8+**，仅依赖标准库（引擎零依赖）。令牌导出工具 `export_rt.py` 额外
需要 `cryptography`（仅 Windows 客户端本机使用）：

```bash
pip install cryptography   # 仅在使用 export_rt.py 时需要
```

---

## 🔐 凭据配置（二选一）

### 方式一：长效令牌（推荐，一劳永逸）

1. 在**已登录的 Windows 桌面客户端**本机运行令牌导出工具：

   ```bash
   python export_rt.py
   ```

   屏幕上会打印一长串 `refreshToken`，复制它。

2. 将令牌写入 `~/.workbuddy/checkin-rt.json`：

   ```json
   {"refresh_token": "粘贴你的refreshToken"}
   ```

   > 令牌每次运行会自动轮换并回写该文件，因此配置一次即可长期使用。
   >
   > 隐私：`export_rt.py` 只读取**本机当前用户**的客户端登录态，路径由
   > `LOCALAPPDATA` / `XDG_DATA_HOME` / `~` 等环境变量自动推导；代码与文档中不含任何
   > 真实用户名、绝对路径、UID、邮箱或令牌。解密仅在本机进行，不联网、不上传。

### 方式二：桌面客户端登录态（引擎原生格式）

在已登录的本机执行引擎自带的 `login` 命令，会自动把登录态导出到 `auths/<uid>.json`：

```bash
python wb_engine.py login
```

---

## 🖥️ 使用

### 跨平台开箱即用（推荐）

Windows / macOS / Linux / 沙箱 **同一条命令**，纯标准库，不依赖 bash / nohup / systemd：

```bash
python start.py             # 后台拉起双层守护（watch + daemon，幂等）
python start.py status      # 查看状态
python start.py stop        # 停止
python start.py once        # 前台立即跑一轮全量
python start.py foreground  # 前台常驻（交给 systemd / Windows 任务计划托管）
```

`watch` 每 15 秒自检，`daemon` 掉线自动重拉；`daemon` 自带每日 08:00 全量 +
每 2h 巡逻 + 失败复查 + 异常自愈。Windows 可在「任务计划程序」登录时运行
`python start.py foreground`，Linux 真机可用附带的 `workbuddy-auto.service`。

### 统一入口（推荐）

```bash
# 常驻守护：每日 08:00 全量 + 每 2h 巡逻 + 失败复查
python workbuddy_auto.py daemon

# 立即跑一轮全量（签到 + 成长 + 玩法 + 开学季）
python workbuddy_auto.py once

# 只跑成长 + 玩法（不含签到）
python workbuddy_auto.py once --mode growth

# 只读查询：积分 / 用量 / 成长概况
python workbuddy_auto.py query
```

### 守护进程常驻（真机 / VPS）

```bash
# 方式 A：systemd（推荐，开机自启）
sudo cp workbuddy-auto.service /etc/systemd/system/
sudo systemctl enable --now workbuddy-auto

# 方式 B：start.sh 直接后台拉起（沙箱 / 容器 / 无 systemd 环境）
bash start.sh
```

> 容器 / 沙箱环境若回收了进程，重新执行 `bash start.sh` 即可重新拉起。

### 引擎直跑（青龙江湖兼容 / 调试）

`wb_engine.py` 保持上游单文件可独立运行，支持多账号并行：

```bash
python wb_engine.py auto      # 全流程
python wb_engine.py growth    # 仅成长 + 玩法
python wb_engine.py school    # 仅开学季 + 小程序
python wb_engine.py query     # 仅查询
python wb_engine.py refresh   # 仅刷新 Token
```

---

## 🔧 环境变量（可选）

| 变量 | 默认值 | 说明 |
|---|---|---|
| `WORKBUDDY_BUDGET_SECONDS` | `900` | 单轮请求时间预算（秒） |
| `WORKBUDDY_RT` | 空 | 不落盘、直接用环境变量提供 refreshToken（适合 CI / 容器） |
| `WORKBUDDY_STATE_DIR` | `~/.workbuddy` | 状态与锁目录（跨平台自动创建，权限 0700） |
| `WORKBUDDY_UPSTREAM` | `1` | 设为 `0` 整体关闭上游能力合入层 |
| `WORKBUDDY_UPSTREAM_BUDGET` | `300` | 合入层单轮时间盒（秒），防止活动轮询阻塞主链路 |
| `WORKBUDDY_SKIP_DESKTOP_SIM` | `false` | 设为 `true` 关闭指定客户端的官方事件 / 云端会话判据（默认全开） |
| `WORKBUDDY_TASKS` | 空 | 仅跑白名单任务（逗号分隔），用于定位调试 |
| `WORKBUDDY_SKIP_TASKS` | 空 | 跳过黑名单任务（逗号分隔） |
| `WORKBUDDY_MP_GAP` | `45` | 小程序事件上报间隔（秒），真人节奏、避免触发风控 |
| `WORKBUDDY_UPSTREAM_NOTIFY` | `false` | 设为 `true` 启用多通道推送（需先配置推送渠道） |
| `RANDOM_SIGNIN` | `false`（守护内） | 多账号随机延时开关 |
| `MAX_RANDOM_DELAY` | `3600` | 单账号随机延时上限（秒） |
| `WORKBUDDY_NO_SCHOOL` | `false` | 设为 `true` 跳过开学季活动 |

---

## 💡 省积分对话说明（免费模型优先）

**所有对话类任务一律先使用免费模型**（当前 `hy3`），包括 `GLM-5.2 模型对话`这类原本
指定模型的任务。只有当免费模型跑完后进度未达标 / 被服务端拒绝时，才回退到任务指定
模型再跑一轮。这样既不消耗积分，也不会漏掉强制模型的任务判定。

免费模型可随平台调整，编辑 `~/.workbuddy/chat_model.json` 即可：

```json
{"free": ["hy3"], "cheap": ["glm-5.2"]}
```

---

## 🗂️ 任务分类索引

`task_catalog.py` 从运行代码动态汇总全部任务并分组，新增任务未归类会显式列出，
不会出现「清单与实现脱节」：

```bash
python task_catalog.py                # 打印全部分类
python task_catalog.py --find chat    # 按 code / 名称 / 类别 / 客户端查找
python task_catalog.py --client       # 只看需要指定客户端（小程序 / PC / App）的任务
```

| 类别 | 含义 | 主要实现位置 |
|---|---|---|
| 每日 | 签到、成长每日、热力墙 | `run_full` / `run_daily_activity` |
| 固定一次性 | 新手任务、补偿礼包、分享渠道 | `run_benefits` / `run_skill_share` |
| 限时活动 | 星巴克 / 记者节 / 开学季 | `run_campaigns` / `t_school` |
| 连续任务 | 小程序 Sequential 1~7 | `run_sequential` |
| 互动玩法 | 旅行 / 抽奖 / 盲盒 / 转盘 / 徽章 | `run_full` 玩法段 |
| 补签兜底 | 补签队列、达标补领、未下发守卫 | `sign_retry_*` / `claim_ready_tasks` |
| 账号与统计 | 账号态、积分增量、终态口径、推送 | `preflight` / `finalize` |

---

## 📱 指定客户端任务与账号安全

部分任务要求特定客户端（小程序 / PC 桌面端 / App）才会点亮。本项目**默认全部自动完成**，
统一采用三条合法路径，不伪造设备指纹、不自造客户端 id 计数：

1. **官方客户端通道**：按任务要求带对应的 `X-Client-Platform` / UA 等官方请求头；
2. **官方事件族上报**：按服务端定义的 `eventCode` 上报（如 `playbook_prompt_send`、
   `expert_actual_use`、`chat_request_send`），带真人节奏间隔；
3. **真实云端会话**：App 类任务真跑一轮 AgentOS 对话，只认结构化 `end_turn` 才算成功。

始终使用账号自身的真实令牌调用官方接口；领奖以回读 `claimed_at` 为准（幂等、不重复
POST），事件间隔 / 失败退避 / 单轮时间盒齐全，异常即停、下一轮再试，避免高频触发风控。
需要人工真实行为（如公益捐款、关注公众号）的任务按既有规则跳过，**不伪造**。

---

## 📜 许可证

本项目整体以 **MIT 许可证**发布。第三方原始代码版权与许可见 [`LICENSE`](./LICENSE)，
来源与归属见 [`NOTICE`](./NOTICE)。
