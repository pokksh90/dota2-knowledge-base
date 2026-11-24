#!/usr/bin/env bash
# 一键把知识库推送到你的 GitHub 并生成可在线读取的 raw URL。
# 用法：
#   GITHUB_TOKEN=ghp_xxx GITHUB_USER=yourname [REPO_NAME=dota2-knowledge-base] bash scripts/push_to_github.sh
#
# 说明：
#   - GITHUB_TOKEN 需要 repo 权限（Personal Access Token, classic 需 repo 勾选；fine-grained 需 Repository contents: read/write）。
#   - 默认创建 public 仓库（raw URL 才能匿名读取）；如需私有，改 PRIVATE=true（私有 raw 需带 token 读取，不推荐给客户端）。
set -euo pipefail

: "${GITHUB_TOKEN:?请设置 GITHUB_TOKEN}"
: "${GITHUB_USER:?请设置 GITHUB_USER}"
REPO_NAME="${REPO_NAME:-dota2-knowledge-base}"
PRIVATE="${PRIVATE:-false}"

BASE="$(cd "$(dirname "$0")/.." && pwd)"
cd "$BASE"

echo "[1/4] 检查/创建仓库 $GITHUB_USER/$REPO_NAME ..."
if curl -fsSL -H "Authorization: token $GITHUB_TOKEN" \
     -H "Accept: application/vnd.github+json" \
     "https://api.github.com/repos/$GITHUB_USER/$REPO_NAME" >/dev/null 2>&1; then
  echo "      仓库已存在，直接推送"
else
  curl -fsSL -X POST -H "Authorization: token $GITHUB_TOKEN" \
     -H "Accept: application/vnd.github+json" \
     -d "{\"name\":\"$REPO_NAME\",\"private\":$PRIVATE}" \
     "https://api.github.com/user/repos" >/dev/null
  echo "      已创建仓库"
fi

echo "[2/4] 本地 git 初始化并提交 ..."
git init -b main >/dev/null 2>&1 || git init >/dev/null
git config user.name  "${GIT_AUTHOR_NAME:-dota2-kb}"
git config user.email "${GIT_AUTHOR_EMAIL:-kb@local}"
git add -A
git commit -m "Dota2 知识库快照 $(date +%Y-%m-%d' '%H:%M)" >/dev/null 2>&1 || echo "      无变更可提交"

echo "[3/4] 推送 ..."
git remote remove origin 2>/dev/null || true
git remote add origin "https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_USER}/${REPO_NAME}.git"
git push -u origin main --force

echo "[4/4] 清理 remote 中的 token ..."
git remote set-url origin "https://github.com/${GITHUB_USER}/${REPO_NAME}.git"

echo ""
echo "✅ 完成。在线读取地址（raw）："
echo "   https://raw.githubusercontent.com/${GITHUB_USER}/${REPO_NAME}/main/data/heroes.json"
echo "   https://raw.githubusercontent.com/${GITHUB_USER}/${REPO_NAME}/main/data/matchups.json"
echo "   https://raw.githubusercontent.com/${GITHUB_USER}/${REPO_NAME}/main/data/items.json"
echo "   https://raw.githubusercontent.com/${GITHUB_USER}/${REPO_NAME}/main/data/tactics.json"
echo "   https://raw.githubusercontent.com/${GITHUB_USER}/${REPO_NAME}/main/data/rules.json"
echo "   https://raw.githubusercontent.com/${GITHUB_USER}/${REPO_NAME}/main/data/inference.json"
echo "   https://raw.githubusercontent.com/${GITHUB_USER}/${REPO_NAME}/main/index.json"
