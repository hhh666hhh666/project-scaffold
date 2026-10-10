#!/usr/bin/env bash
# 回滚到**上一个已上线版本**（镜像仍在仓库里，不需要重新构建）。
#
#   bash server-rollback.sh            # 回到 .current-version 之前记录的那个版本
#   bash server-rollback.sh 1.0.3      # 显式指定一个仓库里存在的版本
#
# ⚠️ 它**不回滚数据库**：迁移是不可逆的，回滚只换代码。要回滚数据只能靠备份，
#    这就是为什么部署前必须先备份。
# ⚠️ 本文件必须是 LF 换行（见 .gitattributes）。
set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

VERSION_FILE="${VERSION_FILE:-/srv/${PROJECT_NAME}/compose/.current-version}"
HISTORY_FILE="${HISTORY_FILE:-/srv/${PROJECT_NAME}/compose/.version-history}"

TARGET="${1:-}"

if [ -z "$TARGET" ]; then
  # 历史文件的最后一行是「当前」，倒数第二行才是上一个
  [ -f "$HISTORY_FILE" ] || { echo "没有 $HISTORY_FILE，无法推断上一个版本；显式给一个：$0 <版本号>" >&2; exit 1; }
  TARGET="$(grep -v '^$' "$HISTORY_FILE" | tail -2 | head -1)"
  [ -n "$TARGET" ] || { echo "历史里只有一个版本，没有可回滚的目标；显式给一个：$0 <版本号>" >&2; exit 1; }
fi

echo "==> 回滚到 $TARGET"
bash ./server-deploy.sh "$TARGET" all
