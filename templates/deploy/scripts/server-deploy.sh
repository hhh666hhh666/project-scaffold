#!/usr/bin/env bash
# 云上部署：拉取镜像仓库里指定版本的镜像，重启 server / web。
# 由发布流水线经 SSH 调用；也可在服务器上手动跑（回滚就是手动跑一个旧版本）。
#
#   bash server-deploy.sh <版本号> [web|server|all]      # 版本号不带 v，如 1.1.0
#
# 从部署脚本继承下来的设计（要改这里之前先读这几条）：
#   * mysql 永不重建：用 --no-deps 绕开 depends_on，它最多在「没在跑」时被拉起一次；
#   * up -d 之前先强制备份一次（第一道保险，备份脚本由你自己补）；
#   * 等 healthcheck（无 healthcheck 的容器退回看 State.Status）；
#   * 失败时打印日志尾部与回滚命令。
#
# ⚠️ 服务器上没有 git，版本号一律从参数拿。
# ⚠️ 必须显式 --env-file：云端 .env 不在 compose 所在目录，而 compose 默认只找自己所在的目录。
# ⚠️ 本文件必须是 LF 换行，CRLF 会让 bash 报 bad interpreter（见 .gitattributes）。
set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

COMPOSE_FILE="${COMPOSE_FILE:-../docker-compose.prod.yml}"
SERVER_ROOT="${SERVER_ROOT:-/srv/${PROJECT_NAME}}"
ENV_FILE="${ENV_FILE:-$SERVER_ROOT/.env}"
VERSION_FILE="${VERSION_FILE:-$SERVER_ROOT/compose/.current-version}"

RAW_VERSION="${1:-}"
SCOPE="${2:-all}"

case "$SCOPE" in
  all)    SERVICES=(${PROJECT_NAME}-server ${PROJECT_NAME}-web) ;;
  server) SERVICES=(${PROJECT_NAME}-server) ;;
  web)    SERVICES=(${PROJECT_NAME}-web) ;;
  *)      echo "用法：$0 <版本号，如 1.1.0> [web|server|all]" >&2; exit 1 ;;
esac

if [ -z "$RAW_VERSION" ]; then
  echo "用法：$0 <版本号，如 1.1.0> [web|server|all]" >&2
  echo "服务器上没有 git，版本号必须显式给（CI 传 tag 去掉 v 前缀之后的值）。" >&2
  exit 1
fi

# 镜像 tag 不带 v（git tag 带）。compose 不支持 ${VAR#v} 截断，所以剥前缀只能发生在这里。
APP_VERSION="${RAW_VERSION#v}"
export APP_VERSION

compose() { docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" "$@"; }

fail() {
  local reason="$1"; shift
  echo "" >&2
  echo "部署失败：$reason" >&2
  echo "" >&2
  echo "=== 容器日志尾部 ===" >&2
  compose logs --tail=100 "$@" >&2 || true
  echo "" >&2
  echo "=== 怎么回滚 ===" >&2
  local prev=""
  [ -f "$VERSION_FILE" ] && prev="$(cat "$VERSION_FILE")"
  if [ -n "$prev" ]; then
    echo "  回到上一个已上线版本（镜像仍在仓库里，不需要重新构建）：" >&2
    echo "    bash $0 $prev" >&2
  else
    echo "  没有记录到上一个版本（可能是首次部署）。手动给一个仓库里存在的 tag：" >&2
    echo "    bash $0 <旧版本号>" >&2
  fi
  echo "  数据在宿主机的 MYSQL_DATA_DIR（见 $ENV_FILE），不在容器里，不会被卷走。" >&2
  exit 1
}

# 等 healthcheck 跑到 healthy；没有 healthcheck 的容器（web）退回看 State.Status=running。
wait_ready() {
  local name="$1" limit="${2:-180}" elapsed=0 status=""
  while [ "$elapsed" -lt "$limit" ]; do
    status="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$name" 2>/dev/null || echo missing)"
    case "$status" in
      healthy|running) echo "    $name 就绪（$status，等了 ${elapsed}s）"; return 0 ;;
      missing)         echo "    $name 不存在" >&2; return 1 ;;
    esac
    sleep 5; elapsed=$((elapsed + 5))
  done
  echo "    等了 ${limit}s，$name 仍是 $status" >&2
  return 1
}

# ---- 1. 前置检查 ----
docker compose version >/dev/null 2>&1 || { echo "docker compose 用不了" >&2; exit 1; }
[ -f "$COMPOSE_FILE" ] || { echo "找不到 $COMPOSE_FILE" >&2; exit 1; }
[ -f "$ENV_FILE" ] || { echo "找不到 $ENV_FILE（云端 .env，模板见仓库 deploy/.env.cloud.example）" >&2; exit 1; }

echo "==> 部署 $APP_VERSION（范围：${SERVICES[*]}）"

# ---- 2. 保证 mysql 在跑，但绝不重建 ----
# 用 docker ps 判断而不是 compose：避免 up 因为 depends_on 把 mysql 一起拉进这次操作。
if docker ps --format '{{.Names}}' | grep -qx "${PROJECT_NAME}-mysql"; then
  echo "==> mysql 已在运行，跳过"
else
  echo "==> mysql 没在跑，拉起来"
  compose up -d mysql || fail "mysql 起不来" mysql
fi
wait_ready "${PROJECT_NAME}-mysql" 180 || fail "mysql 起不来" mysql

# ---- 3. up -d 之前先备份一次（脚本由你自己补；没有就删掉这一步，但要知道代价）----
if [ -x ./backup-mysql.sh ]; then
  echo "==> 部署前备份"
  ENV_FILE="$ENV_FILE" bash ./backup-mysql.sh || fail "备份失败，中止部署（不带着没备份的库去跑迁移）"
else
  echo "==> ⚠️ 没有 backup-mysql.sh，跳过部署前备份（建议补上）"
fi

# ---- 4. 拉取新镜像并替换业务容器 ----
# 先 pull 再 up：把「拉不到镜像」这类失败挡在替换之前。
echo "==> 拉取镜像 $APP_VERSION"
compose pull "${SERVICES[@]}" || fail "拉取镜像失败（仓库上有 $APP_VERSION 这个 tag 吗？）" "${SERVICES[@]}"

# --no-deps 是关键：跳过 depends_on，确保这一步碰不到 mysql
echo "==> 重建并启动：${SERVICES[*]}"
compose up -d --no-deps "${SERVICES[@]}" || fail "compose up 失败" "${SERVICES[@]}"

# ---- 5. 等健康检查 ----
echo "==> 等待容器就绪"
case "$SCOPE" in
  server|all) wait_ready "${PROJECT_NAME}-server" 180 || fail "后端未通过健康检查" ${PROJECT_NAME}-server ;;
esac
case "$SCOPE" in
  web|all)    wait_ready "${PROJECT_NAME}-web" 60    || fail "前端容器没起来" ${PROJECT_NAME}-web ;;
esac

# ---- 6. 探一下真实端口（只告警，不中断）----
if command -v curl >/dev/null 2>&1; then
  case "$SCOPE" in
    server|all)
      docker exec "${PROJECT_NAME}-server" curl -fsS --max-time 5 -o /dev/null http://127.0.0.1:8080/v3/api-docs \
        && echo "    后端 /v3/api-docs 正常" \
        || echo "    ⚠️ 后端探测失败，看容器日志" ;;
  esac
fi

# ---- 7. 记下已上线版本，供回滚读取 ----
# .current-version 是「现在跑的是谁」；.version-history 是追加的历史，回滚靠它推断「上一个」。
mkdir -p "$(dirname "$VERSION_FILE")"
echo "$APP_VERSION" > "$VERSION_FILE"
echo "$APP_VERSION" >> "${HISTORY_FILE:-$(dirname "$VERSION_FILE")/.version-history}"

echo ""
echo "==> 部署完成，当前状态"
compose ps
echo "已上线版本：$APP_VERSION（记录在 $VERSION_FILE）"
