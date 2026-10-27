# WorkBuddy 全自动积分助手

> 📖 语言 / Language: **[中文（默认）](./README.md)** · **[English](./README_EN.md)**

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
| 对话类任务 | ✅ 零成本优先 | **优先使用免费模型**（如 `hy3`），无免费则最便宜模型；强制模型的任务自动回退目标模型 |

**已实现的"无人值守"能力：**

- 🔑 **长效令牌**：`refreshToken` 每次运行自动轮换续期，配置一次长期可用。
- 🤖 **守护进程**：每日 **08:00 准点全量** + 每 2 小时巡逻（旅行到港即领 + 成长补领
  + 玩法），**漏跑 / 失败自动复查补拉**，进程异常自动重启。
- 🆕 **新任务自适应**：未覆盖的新任务按「专家链 / 对话 / 通用激活」三路兜底，新上线
  任务无需改代码即可被识别并尝试自动完成。
- 💡 **省积分对话**：所有"拉起对话"的成长任务默认走免费模型，将积分消耗降到最低。

---

## 📁 目录结构

```
workbuddy-auto/
├── LICENSE            # MIT 许可证（第三方版权归属见 NOTICE）
├── NOTICE             # 第三方来源与版权归属声明
├── README.md          # 本文件
├── .gitignore         # 忽略凭据 / 缓存 / 日志
├── wb_engine.py       # 【第三方派生】核心任务引擎（派生自下方开源项目，含本仓库增强）
├── workbuddy_auto.py  # 【本仓库原创】统一入口 / 守护调度 / 凭据适配
├── export_rt.py       # 【本仓库原创】长效令牌导出工具（Windows 客户端本机用）
├── start.sh           # 幂等拉起脚本（守护进程）
└── workbuddy-auto.service  # systemd 单元（真机 / VPS 常驻用，沙箱无 systemd 时作备份）
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

### 方式二：桌面客户端登录态（引擎原生格式）

在已登录的本机执行引擎自带的 `login` 命令，会自动把登录态导出到 `auths/<uid>.json`：

```bash
python wb_engine.py login
```

---

## 🖥️ 使用

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
| `RANDOM_SIGNIN` | `false`（守护内） | 多账号随机延时开关 |
| `MAX_RANDOM_DELAY` | `3600` | 单账号随机延时上限（秒） |
| `WORKBUDDY_NO_SCHOOL` | `false` | 设为 `true` 跳过开学季活动 |

---

## 💡 省积分对话说明

对话类任务（和 AI 聊天 5 次、夜猫子、专家团、GLM-5.2 模型对话等）的**真实对话**默认
优先使用当下免费模型（当前 `hy3`）。若某任务服务端强制要求特定模型（如
`GLM-5.2 模型对话` 必须走 `glm-5.2`），脚本会自动回退到目标模型，确保任务完成。

免费模型可随平台调整，编辑 `~/.workbuddy/chat_model.json` 即可：

```json
{"free": ["hy3"], "cheap": ["glm-5.2"]}
```

---

## 📜 许可证

本项目整体以 **MIT 许可证**发布。第三方原始代码版权与许可见 [`LICENSE`](./LICENSE)，
来源与归属见 [`NOTICE`](./NOTICE)。
