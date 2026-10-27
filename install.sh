#!/usr/bin/env bash
# 安装 skills/ 下的技能到各工具的技能目录。
#
#   ./install.sh                     # 默认装到 ~/.workbuddy/skills
#   ./install.sh --workbuddy         # ~/.workbuddy/skills（WorkBuddy，全工程可用）
#   ./install.sh --agents            # ~/.agents/skills（OpenClaw / Claude Code 风格）
#   ./install.sh --claude            # ~/.claude/skills
#   ./install.sh --codebuddy         # ~/.codebuddy/skills
#   ./install.sh --dest /some/dir    # 自定义目标
#   ./install.sh --only dify-workflow-dsl
#   ./install.sh --dry-run
#
# 已存在的同名技能会被覆盖；加 --backup 先备份到 <目标>/<name>.bak.<时间戳>。

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$REPO_ROOT/skills"
DEST=""
ONLY=""
DRY_RUN=0
BACKUP=0

usage() {
  sed -n '2,16p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
  exit 1
}

while [ $# -gt 0 ]; do
  case "$1" in
    --workbuddy) DEST="$HOME/.workbuddy/skills" ;;
    --agents)    DEST="$HOME/.agents/skills" ;;
    --claude)    DEST="$HOME/.claude/skills" ;;
    --codebuddy) DEST="$HOME/.codebuddy/skills" ;;
    --dest)      DEST="${2:?--dest 需要路径}"; shift ;;
    --only)      ONLY="${2:?--only 需要技能名}"; shift ;;
    --dry-run)   DRY_RUN=1 ;;
    --backup)    BACKUP=1 ;;
    -h|--help)   usage ;;
    *) echo "未知参数：$1" >&2; usage ;;
  esac
  shift
done

DEST="${DEST:-$HOME/.workbuddy/skills}"

[ -d "$SRC_DIR" ] || { echo "找不到 $SRC_DIR" >&2; exit 1; }

installed=0
for skill_path in "$SRC_DIR"/*/; do
  [ -f "$skill_path/SKILL.md" ] || continue
  name="$(basename "$skill_path")"
  [ -n "$ONLY" ] && [ "$name" != "$ONLY" ] && continue
  target="$DEST/$name"

  if [ "$DRY_RUN" -eq 1 ]; then
    echo "[dry-run] $name -> $target"
    installed=$((installed + 1))
    continue
  fi

  mkdir -p "$DEST"
  if [ -e "$target" ]; then
    if [ "$BACKUP" -eq 1 ]; then
      stamp="$(date +%Y%m%d-%H%M%S)"
      mv "$target" "$target.bak.$stamp"
      echo "已备份旧版本 -> $target.bak.$stamp"
    else
      rm -rf "$target"
    fi
  fi
  cp -R "$skill_path" "$target"
  echo "已安装 $name -> $target"
  installed=$((installed + 1))
done

if [ "$installed" -eq 0 ]; then
  echo "没有可安装的技能（检查 --only 或 skills/ 目录）" >&2
  exit 1
fi

echo "完成：$installed 个技能。重启或新开会话后生效。"
