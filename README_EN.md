# WorkBuddy Auto Check-in Assistant

> 📖 Language: **[简体中文 (Simplified Chinese)](./README.md)** · **[English](./README_EN.md)**

> A **fully automated points-collection** tool for WorkBuddy / CodeBuddy: daily check-in,
> Growth Center tasks, interactive mini-games, back-to-school events and more — **35 tasks**
> run in one click, with long-lived token support, a resident daemon, automatic failure
> retry, and self-adaptation to newly added tasks.

---

## ⚠️ Important Disclaimer

- This project is a **third-party reverse-engineered script**, **unrelated to WorkBuddy /
  Tencent officially**. The APIs it uses may break at any time, and long-term availability
  is not guaranteed.
- For **personal learning and research only**. Please comply with the relevant platform
  rules and local laws and regulations, and **do not use it for any violating or fraudulent
  purposes** (e.g. bypassing real donations to farm charity points).
- Any consequences of using this project are borne solely by the user.
- This repository **ships no account credentials** and never uploads any of your data.

---

## 📦 Feature Overview

| Category | Coverage | Notes |
|---|---|---|
| Daily check-in | ✅ streak / cumulative points | Auto-claim; supports streak exchange & catch-up cards |
| Growth Center (18) | 17 fully auto + 1 manual | Desktop chat, try hot skills, experience Library, experts, themes, templates, Buddy, night-owl, etc. |
| Interactive games (8) | ✅ | Lottery, blind box, cat traveler, streak exchange, catch-up, Buddy info, badges, gift compensation |
| Back-to-school (5) | 4 auto + big wheel | Share, AI chat, desktop chat, B2S expert, big-wheel lottery |
| Mini-program tasks (3) | ✅ | Mini-program chat, campus day, unknown mini-program auto-adapt |
| Client-specific tasks | ✅ fully automated | Mini-program / PC / App criteria all go through **official client channels + official event families + a real cloud session**, all on by default — works without your PC |
| Chat tasks | ✅ free-first | **Every task tries a free model first** (e.g. `hy3`); only on failure/rejection does it fall back to the task's required model |
| Cross-platform | ✅ out of the box | Same command on Windows / macOS / Linux / sandbox; stdlib only, no bash / systemd dependency |

**Implemented "unattended" capabilities:**

- 🔑 **Long-lived token**: `refreshToken` auto-rotates every run — configure once, use forever.
- 🤖 **Two-layer watchdog**: `python start.py` spawns watch + daemon in the background; daily
  **08:00 full run** + patrol every **2 hours**, **auto retry on miss/failure**, respawn within 15s.
- 🆕 **New-task self-adaptation**: uncovered tasks get a three-way fallback (expert chain /
  chat / generic activation) — newly launched tasks are recognized and attempted without code changes.
- 💡 **Points-saving chat**: every chat task tries a free model first and only falls back when needed.
- 🗂️ **Task catalog**: `python task_catalog.py` lists every task grouped by daily / one-off /
  limited event / sequential / games / catch-up / account & stats, with implementation pointers.

---

## 📁 Directory Structure

```
workbuddy-auto-checkin/
├── LICENSE              # MIT License (third-party copyright see NOTICE)
├── NOTICE               # Third-party sources & copyright attribution
├── README.md            # Chinese docs (Simplified)
├── README_EN.md         # English docs
├── .gitignore           # Excludes credentials / caches / logs
├── wb_engine.py         # [third-party derivative] core task engine (derived from the OSS projects below, with this repo's enhancements)
├── wb_upstream.py       # [this repo original] upstream capability layer (15 missing features, can be disabled)
├── workbuddy_auto.py    # [this repo original] unified entry / daemon scheduler / credential adapter
├── start.py             # [this repo original] cross-platform unattended launcher (win / mac / linux)
├── task_catalog.py      # [this repo original] task catalog index (locate code by category)
├── export_rt.py         # [this repo original] long-lived token exporter (run on the Windows client machine)
├── start.sh             # Unix-only fallback launcher (bash)
└── workbuddy-auto.service  # systemd unit (for bare-metal / VPS)
```

---

## 🧩 Third-party Sources (please read)

`wb_engine.py` is a **derivative work**, originally from the following MIT-licensed open-source
projects. This repository keeps the original authors' copyright notices and adds functional
merging and enhancements:

| Project | URL |
|---|---|
| xz0609/workbuddy-checkin-ql | https://github.com/xz0609/workbuddy-checkin-ql |
| L0NE-6/WorkBuddy-Daily | https://github.com/L0NE-6/WorkBuddy-Daily |

Enhancements added by this repository (free-model selection, expert-experience task family,
hot-skill CLOUD-domain fix, chat-task target-model fallback, three-way new-task fallback, etc.)
are marked with `[本仓库新增/增强]` inside `wb_engine.py`. Full details in
[`NOTICE`](./NOTICE); license text in [`LICENSE`](./LICENSE).

---

## 🧩 Upstream Capability Layer (wb_upstream.py)

After a feature-by-feature comparison against upstream `L0NE-6/WorkBuddy-Daily`
(v3.42~v3.50) and `xz0609/workbuddy-checkin-ql`, all capabilities missing locally are
implemented in a single `wb_upstream.py`; the core engine only attaches them with
exception isolation. Merged capabilities include:

- Account-state detection (enterprise accounts / restricted `11140` / channel block `11-128`)
- Growth-task snapshot across three endpoints + "not issued" guard, claim read-back confirmation, ready-task catch-up
- `accept` settlement fix, terminal-state correction, expiry reminders, **point delta statistics**
- Minute-level check-in retry queue, smart makeup-checkin candidates, one-off compensation / newcomer gift
- Mini-program campaign tasks (Starbucks / Reporter's Day), real `skill_share` channel, sequential tasks 2~7
- Daily activity reporting, conversation-count cleanup, multi-channel push (Bark / ServerChan / DingTalk / WeCom / WxPusher)

All additions are on by default and wrapped in per-item `try/except`, so a single failure never
affects the existing check-in and claim flow. Campaign sessions only send tokens to trusted
official HTTPS domains; state files never store credentials / UID / phone numbers.
Set `WORKBUDDY_UPSTREAM=0` to disable the whole layer.

> Read-only self-check (no task acceptance / claiming / reporting): `python wb_upstream.py probe`

---

## 🚀 Installation

Requires **Python 3.8+**, standard library only (engine has zero dependencies). The token
exporter `export_rt.py` additionally needs `cryptography` (only used on the Windows client machine):

```bash
pip install cryptography   # only needed when using export_rt.py
```

---

## 🔐 Credential Setup (choose one)

### Option 1: Long-lived token (recommended, set-and-forget)

1. On the **logged-in Windows desktop client** machine, run the token exporter:

   ```bash
   python export_rt.py
   ```

   It prints a long `refreshToken` to the screen — copy it.

2. Write the token into `~/.workbuddy/checkin-rt.json`:

   ```json
   {"refresh_token": "paste-your-refreshToken-here"}
   ```

   > The token auto-rotates and rewrites this file on every run, so configure once for long-term use.
   >
   > Privacy: `export_rt.py` only reads the **current local user's** client login state;
   > paths are derived from `LOCALAPPDATA` / `XDG_DATA_HOME` / `~` environment variables.
   > No code or docs contain any real username, absolute path, UID, email or token.
   > Decryption happens locally only — no network, no upload.

### Option 2: Desktop client login state (engine native format)

On the logged-in local machine, run the engine's built-in `login` command, which exports the
login state to `auths/<uid>.json`:

```bash
python wb_engine.py login
```

---

## 🖥️ Usage

### Cross-platform, out of the box (recommended)

One command on Windows / macOS / Linux / sandbox; stdlib only, no bash / nohup / systemd:

```bash
python start.py             # spawn two-layer watchdog in background (idempotent)
python start.py status      # show status
python start.py stop        # stop
python start.py once        # run one full round in the foreground
python start.py foreground  # stay in foreground (hand over to systemd / Task Scheduler)
```

`watch` self-checks every 15s and respawns `daemon` if it dies; `daemon` itself does the
daily 08:00 full run + 2h patrol + failure retry + crash self-heal. On Windows use Task
Scheduler at logon with `python start.py foreground`; on a Linux host use the shipped
`workbuddy-auto.service`.

### Unified entry (recommended)

```bash
# Resident daemon: daily 08:00 full run + patrol every 2h + failure retry
python workbuddy_auto.py daemon

# Run one full round immediately (check-in + growth + games + back-to-school)
python workbuddy_auto.py once

# Growth + games only (no check-in)
python workbuddy_auto.py once --mode growth

# Read-only query: points / usage / growth overview
python workbuddy_auto.py query
```

### Resident daemon (bare-metal / VPS)

```bash
# Option A: systemd (recommended, auto-start on boot)
sudo cp workbuddy-auto.service /etc/systemd/system/
# Edit WorkingDirectory / ExecStart in the file to point to your clone path first!
sudo systemctl enable --now workbuddy-auto

# Option B: start.sh background launch (sandbox / container / no-systemd environments)
bash start.sh
```

> In container / sandbox environments where the process gets reclaimed, just re-run
> `bash start.sh` to bring it back up.

### Run the engine directly (QingLong / debugging)

`wb_engine.py` stays a single runnable file (upstream-compatible), supporting multi-account parallelism:

```bash
python wb_engine.py auto      # full flow
python wb_engine.py growth    # growth + games only
python wb_engine.py school    # back-to-school + mini-program only
python wb_engine.py query     # query only
python wb_engine.py refresh   # refresh token only
```

---

## 🔧 Environment Variables (optional)

| Variable | Default | Description |
|---|---|---|
| `WORKBUDDY_BUDGET_SECONDS` | `900` | Per-round request time budget (seconds) |
| `WORKBUDDY_RT` | empty | Provide refreshToken via env var without writing it to disk (CI / containers) |
| `WORKBUDDY_STATE_DIR` | `~/.workbuddy` | State & lock dir (auto-created cross-platform, mode 0700) |
| `WORKBUDDY_UPSTREAM` | `1` | Set `0` to disable the whole upstream capability layer |
| `WORKBUDDY_UPSTREAM_BUDGET` | `300` | Per-round time box for the upstream layer (seconds) |
| `WORKBUDDY_SKIP_DESKTOP_SIM` | `false` | Set `true` to disable client-specific official-event / cloud-session criteria (on by default) |
| `WORKBUDDY_TASKS` | empty | Only run whitelisted tasks (comma-separated, for debugging) |
| `WORKBUDDY_SKIP_TASKS` | empty | Skip blacklisted tasks (comma-separated) |
| `WORKBUDDY_MP_GAP` | `45` | Mini-program event gap (seconds), human-like pacing to avoid risk control |
| `WORKBUDDY_UPSTREAM_NOTIFY` | `false` | Set `true` to enable multi-channel push (configure channels first) |
| `RANDOM_SIGNIN` | `false` (in daemon) | Multi-account random delay toggle |
| `MAX_RANDOM_DELAY` | `3600` | Max per-account random delay (seconds) |
| `WORKBUDDY_NO_SCHOOL` | `false` | Set `true` to skip back-to-school events |

---

## 💡 Points-saving Chat (free model first)

**Every chat-type task tries a free model first** (currently `hy3`) — including tasks that
nominally require a specific model, such as `GLM-5.2 model chat`. Only when the free-model
round does not reach the required progress, or is rejected by the server, does it fall back
to the task's required model for a second round. Zero point spend whenever possible, with no
loss of forced-model task credit.

Free models can change with the platform — edit `~/.workbuddy/chat_model.json`:

```json
{"free": ["hy3"], "cheap": ["glm-5.2"]}
```

---

## 🗂️ Task Catalog

`task_catalog.py` aggregates every task from the running code and groups it; any new task
without a category is listed explicitly so the index never drifts from the implementation:

```bash
python task_catalog.py                # print every category
python task_catalog.py --find chat    # search by code / name / category / client
python task_catalog.py --client       # only tasks requiring a specific client (MP / PC / App)
```

| Category | Meaning | Main implementation |
|---|---|---|
| Daily | Check-in, daily growth, activity heatmap | `run_full` / `run_daily_activity` |
| One-off | Newcomer tasks, compensation / gift, share channel | `run_benefits` / `run_skill_share` |
| Limited events | Starbucks / Reporter's Day / back-to-school | `run_campaigns` / `t_school` |
| Sequential | Mini-program Sequential 1~7 | `run_sequential` |
| Games | Travel / lottery / blind box / wheel / badges | `run_full` games section |
| Catch-up | Retry queue, ready-task catch-up, not-issued guard | `sign_retry_*` / `claim_ready_tasks` |
| Account & stats | Account state, point delta, terminal state, push | `preflight` / `finalize` |

---

## 📱 Client-specific Tasks & Account Safety

Some tasks only light up when a specific client (mini-program / PC desktop / App) is used.
This project **automates all of them by default** via three legitimate paths — no device
fingerprint forgery, no fabricated client-id counting:

1. **Official client channels**: send the task's required `X-Client-Platform` / UA headers;
2. **Official event families**: report the server-defined `eventCode` values (e.g.
   `playbook_prompt_send`, `expert_actual_use`, `chat_request_send`) with human-like pacing;
3. **Real cloud session**: App tasks actually run one AgentOS conversation; only a structured
   `end_turn` counts as success.

All calls use the account's own real token against official APIs. Claims are confirmed by
reading back `claimed_at` (idempotent, no duplicate POST); event gaps, failure backoff and a
per-round time box are enforced, and any anomaly stops the round and retries later — avoiding
high-frequency risk-control triggers. Tasks that genuinely require human action (e.g. real
donations, following an official account) are skipped by the existing rule and **never forged**.

---

## 📜 License

This project is released under the **MIT License** as a whole. Third-party original copyright
and license see [`LICENSE`](./LICENSE); sources and attribution see [`NOTICE`](./NOTICE).
