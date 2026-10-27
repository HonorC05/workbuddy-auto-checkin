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
| Chat tasks | ✅ free-first | **Prefers free models** (e.g. `hy3`); falls back to the cheapest if none free; forced-model tasks auto-return to target model |

**Implemented "unattended" capabilities:**

- 🔑 **Long-lived token**: `refreshToken` auto-rotates every run — configure once, use forever.
- 🤖 **Resident daemon**: daily **08:00 full run** + patrol every **2 hours** (claim on cat
  arrival + growth catch-up + games), **auto retry on miss/failure**, auto-restart on crash.
- 🆕 **New-task self-adaptation**: uncovered tasks get a three-way fallback (expert chain /
  chat / generic activation) — newly launched tasks are recognized and attempted without code changes.
- 💡 **Points-saving chat**: all "launch a chat" growth tasks default to free models, minimizing point spend.

---

## 📁 Directory Structure

```
workbuddy-auto/
├── LICENSE            # MIT License (third-party copyright see NOTICE)
├── NOTICE             # Third-party sources & copyright attribution
├── README.md          # Chinese docs (default)
├── README_EN.md       # English docs
├── .gitignore         # Excludes credentials / caches / logs
├── wb_engine.py       # [third-party derivative] core task engine (derived from the OSS projects below, with this repo's enhancements)
├── workbuddy_auto.py  # [this repo original] unified entry / daemon scheduler / credential adapter
├── export_rt.py       # [this repo original] long-lived token exporter (run on the Windows client machine)
├── start.sh           # Idempotent launcher (daemon)
└── workbuddy-auto.service  # systemd unit (for bare-metal / VPS; backup when no systemd, e.g. sandbox)
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

### Option 2: Desktop client login state (engine native format)

On the logged-in local machine, run the engine's built-in `login` command, which exports the
login state to `auths/<uid>.json`:

```bash
python wb_engine.py login
```

---

## 🖥️ Usage

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
| `RANDOM_SIGNIN` | `false` (in daemon) | Multi-account random delay toggle |
| `MAX_RANDOM_DELAY` | `3600` | Max per-account random delay (seconds) |
| `WORKBUDDY_NO_SCHOOL` | `false` | Set `true` to skip back-to-school events |

---

## 💡 Points-saving Chat Notes

The **real chat** for chat-type tasks (chat 5 times, night-owl, expert squad, GLM-5.2 model
chat, etc.) defaults to the current free model (currently `hy3`). If a task's server forces a
specific model (e.g. `GLM-5.2 model chat` must use `glm-5.2`), the script auto-falls back to
the target model to ensure completion.

Free models can change with the platform — edit `~/.workbuddy/chat_model.json`:

```json
{"free": ["hy3"], "cheap": ["glm-5.2"]}
```

---

## 📜 License

This project is released under the **MIT License** as a whole. Third-party original copyright
and license see [`LICENSE`](./LICENSE); sources and attribution see [`NOTICE`](./NOTICE).
