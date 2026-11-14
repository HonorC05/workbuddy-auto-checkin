#!/usr/bin/env bash
# Unix 备用入口：委托跨平台启动器 start.py，避免维护两套守护逻辑。
# 若已有实例在跑，start.py 会幂等退出，不会重复请求。
# 用法：bash start.sh [start|status|stop|once|foreground]
set -u
cd "$(dirname "$0")" || exit 1
PY="$(command -v python3.11 || command -v python3 || command -v python)"
exec "$PY" start.py "$@"
