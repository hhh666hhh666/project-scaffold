#!/usr/bin/env bash
# 服务器上的 compose 薄封装：把「项目名 + compose 文件 + env 文件」这串固定参数收在一处，
# 免得每次手敲还敲错。
#
#   bash server-compose.sh ps | up -d | down | logs [<服务>] | pull | restart <服务>
#
# ⚠️ 只在服务器上跑；本机开发不用它（本机只起数据库）。
# ⚠️ 本文件必须是 LF 换行（见 .gitattributes）。
set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

COMPOSE_FILE="${COMPOSE_FILE:-../docker-compose.prod.yml}"
SERVER_ROOT="${SERVER_ROOT:-/srv/${PROJECT_NAME}}"
ENV_FILE="${ENV_FILE:-$SERVER_ROOT/.env}"

[ -f "$ENV_FILE" ] || { echo "找不到 $ENV_FILE" >&2; exit 1; }

exec docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" "$@"
