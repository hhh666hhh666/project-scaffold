#!/usr/bin/env bash
# 部署前备份 MySQL：server-deploy.sh 在 up -d 之前调用它。
#
#   bash backup-mysql.sh
#
# 参数全部来自环境变量，默认值与项目约定一致：
#   ENV_FILE      服务器上的 .env，默认 /srv/<项目>/.env
#   SERVER_ROOT   服务器项目根，默认 /srv/<项目>
#   BACKUP_DIR    备份目录，默认 <SERVER_ROOT>/backups
#   BACKUP_KEEP   保留最近几份，默认 7
#   CONTAINER     MySQL 容器名，默认 <项目>-mysql
#
# 设计约束：
#   * 密码只通过 MYSQL_PWD 传给容器，不出现在命令行参数里（ps 看不到）；
#   * 逐行读取 .env，不 source——.env 是配置，不是可执行脚本；
#   * 先写 .part、gzip -t 校验通过后再改名，避免留下半截备份；
#   * 任何一步失败都返回非 0，让部署中止。
#
# ⚠️ 这是**本机备份**：防误操作、坏迁移和容器误删，不防磁盘损坏。
#    异地 / 对象存储备份需要按自己的基础设施另配。
# ⚠️ 本文件必须是 LF 换行，CRLF 会让 bash 报 bad interpreter（见 .gitattributes）。
set -euo pipefail

ENV_FILE="${ENV_FILE:-/srv/${PROJECT_NAME}/.env}"
SERVER_ROOT="${SERVER_ROOT:-/srv/${PROJECT_NAME}}"
BACKUP_DIR="${BACKUP_DIR:-$SERVER_ROOT/backups}"
BACKUP_KEEP="${BACKUP_KEEP:-7}"
CONTAINER="${CONTAINER:-${PROJECT_NAME}-mysql}"
VERSION_FILE="${VERSION_FILE:-$SERVER_ROOT/compose/.current-version}"

case "$BACKUP_KEEP" in
  ''|*[!0-9]*) echo "BACKUP_KEEP 必须是正整数，当前是：$BACKUP_KEEP" >&2; exit 1 ;;
esac
[ "$BACKUP_KEEP" -ge 1 ] || { echo "BACKUP_KEEP 至少为 1" >&2; exit 1; }

[ -f "$ENV_FILE" ] || { echo "找不到环境文件：$ENV_FILE" >&2; exit 1; }

# 只取需要的两个值；不执行文件里的任何内容。
env_value() {
  local key="$1"
  grep -E "^[[:space:]]*${key}=" "$ENV_FILE" \
    | tail -n 1 \
    | cut -d= -f2- \
    | sed -e 's/^["'\'']//' -e 's/["'\'']$//'
}

DB_PASSWORD="$(env_value MYSQL_ROOT_PASSWORD)"
MYSQL_DB="$(env_value MYSQL_DATABASE)"
[ -n "$DB_PASSWORD" ] || { echo "$ENV_FILE 里没有 MYSQL_ROOT_PASSWORD" >&2; exit 1; }
[ -n "$MYSQL_DB" ] || { echo "$ENV_FILE 里没有 MYSQL_DATABASE" >&2; exit 1; }

docker inspect "$CONTAINER" >/dev/null 2>&1 \
  || { echo "找不到容器：$CONTAINER（MySQL 必须先起来）" >&2; exit 1; }

mkdir -p "$BACKUP_DIR"
STAMP="$(date +%Y%m%d-%H%M%S)"
CURRENT_VERSION="$(cat "$VERSION_FILE" 2>/dev/null || echo unknown)"
TARGET="$BACKUP_DIR/$MYSQL_DB-${STAMP}-${CURRENT_VERSION}.sql.gz"
PARTIAL="${TARGET}.part"

echo "==> 备份 $MYSQL_DB 到 $TARGET"
docker exec -e MYSQL_PWD="$DB_PASSWORD" "$CONTAINER" \
  mysqldump --single-transaction --routines --triggers --set-gtid-purged=OFF \
  -uroot "$MYSQL_DB" | gzip -c > "$PARTIAL"

gzip -t "$PARTIAL" || { rm -f "$PARTIAL"; echo "备份文件校验失败" >&2; exit 1; }
mv "$PARTIAL" "$TARGET"
echo "    完成：$(du -h "$TARGET" | cut -f1)"

# 只保留最近 BACKUP_KEEP 份；文件名前缀限定为本库，避免误删同目录其他文件。
mapfile -t OLD_BACKUPS < <(
  ls -1t "$BACKUP_DIR/$MYSQL_DB"-*.sql.gz 2>/dev/null | tail -n +$((BACKUP_KEEP + 1))
)
if [ "${#OLD_BACKUPS[@]}" -gt 0 ]; then
  for file in "${OLD_BACKUPS[@]}"; do
    rm -f "$file"
    echo "    清理旧备份：$(basename "$file")"
  done
fi

echo "==> 备份完成"
