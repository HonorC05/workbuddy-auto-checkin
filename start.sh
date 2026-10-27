#!/usr/bin/env bash
# WorkBuddy 全自动积分守护 —— 幂等拉起脚本
# 说明：若已有实例在跑（单实例锁），新进程会自动退出，不会重复请求。
# 用法：bash <仓库目录>/start.sh（脚本会自动切换到自身所在目录，路径无关）
set -u
cd "$(dirname "$0")"
PY="$(command -v python3.11 || command -v python3)"
LOG="$HOME/.workbuddy/auto_guard.log"
nohup "$PY" "$PWD/workbuddy_auto.py" daemon >>"$LOG" 2>&1 &
echo "守护已后台拉起 (pid $!)，日志: $LOG"
echo "查看实时日志：tail -f $LOG"
