#!/usr/bin/env bash
# 安装 skills/ 下的技能到各工具的技能目录。
#
#   ./install.sh                     自动扫描所有已安装工具的 skills 目录，逐个安装（默认）
#   ./install.sh --list              只列出扫描到的安装位置，不安装
#   ./install.sh --auto --project    上面基础上再加上当前项目的工具级目录
#   ./install.sh --workbuddy         只装 ~/.workbuddy/skills（WorkBuddy，全工程可用）
#   ./install.sh --agents            只装 ~/.agents/skills（OpenClaw / Claude Code 风格）
#   ./install.sh --claude            只装 ~/.claude/skills
#   ./install.sh --codebuddy         只装 ~/.codebuddy/skills
#   ./install.sh --qoder             只装 ~/.qoder/skills
#   ./install.sh --dest /some/dir    只装到自定义目录
#   ./install.sh --only dify-workflow-dsl
#   ./install.sh --dry-run
#   ./install.sh --backup
#
# 已存在的同名技能会被覆盖；加 --backup 先备份到 <目标>/<name>.bak.<时间戳>。

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$REPO_ROOT/skills"
PROJECT_ROOT="$PWD"

DEST=""
ONLY=""
DRY_RUN=0
BACKUP=0
LIST=0
PROJECT=0
EXPLICIT=()

usage() {
  cat <<'EOF'
用法：
  ./install.sh [选项]

选项：
  （无参数时自动扫描所有已安装工具的 skills 目录并逐个安装）
  --list                只列出扫描结果，不安装
  --project             额外把当前项目下的工具级目录纳入扫描
  --workbuddy           只安装到 ~/.workbuddy/skills
  --agents              只安装到 ~/.agents/skills
  --claude              只安装到 ~/.claude/skills
  --codebuddy           只安装到 ~/.codebuddy/skills
  --qoder               只安装到 ~/.qoder/skills
  --dest <目录>         只安装到自定义目录
  --only <技能名>       只处理指定技能
  --dry-run             只打印将执行的操作
  --backup              覆盖前把旧版本备份为 <name>.bak.<时间戳>
  -h, --help            显示本帮助
EOF
  exit 1
}

while [ $# -gt 0 ]; do
  case "$1" in
    --workbuddy) EXPLICIT+=("$HOME/.workbuddy/skills"); shift ;;
    --agents)    EXPLICIT+=("$HOME/.agents/skills"); shift ;;
    --claude)    EXPLICIT+=("$HOME/.claude/skills"); shift ;;
    --codebuddy) EXPLICIT+=("$HOME/.codebuddy/skills"); shift ;;
    --qoder)     EXPLICIT+=("$HOME/.qoder/skills"); shift ;;
    --dest)      DEST="${2:?--dest 需要路径}"; shift 2 ;;
    --only)      ONLY="${2:?--only 需要技能名}"; shift 2 ;;
    --auto)      shift ;;     # 与默认行为相同，写出来只为可读
    --project)   PROJECT=1; shift ;;
    --list)      LIST=1; shift ;;
    --dry-run)   DRY_RUN=1; shift ;;
    --backup)    BACKUP=1; shift ;;
    -h|--help)   usage ;;
    *) echo "未知参数：$1" >&2; usage ;;
  esac
done

[ -d "$SRC_DIR" ] || { echo "找不到 $SRC_DIR" >&2; exit 1; }

# 常见工具的用户级 skills 目录。命中规则：目标父目录存在即认为该工具在用
#（可能还没建过 skills/ 子目录，安装时会创建）；父目录不存在则跳过，
# 不会凭空造出没装过的工具目录。
user_targets() {
  cat <<EOF
workbuddy|$HOME/.workbuddy/skills|WorkBuddy
agents|$HOME/.agents/skills|OpenClaw / Claude Code 风格通用目录
claude|$HOME/.claude/skills|Claude Code
codebuddy|$HOME/.codebuddy/skills|CodeBuddy
qoder|$HOME/.qoder/skills|Qoder Desktop
cursor|$HOME/.cursor/skills|Cursor
gemini|$HOME/.gemini/skills|Gemini CLI
codex|$HOME/.codex/skills|Codex CLI
EOF
}

# 项目级目录：只在当前工作区里存在才命中
project_targets() {
  cat <<EOF
project-agents|$PROJECT_ROOT/.agents/skills|项目级通用目录
project-claude|$PROJECT_ROOT/.claude/skills|项目级 Claude Code
project-codebuddy|$PROJECT_ROOT/.codebuddy/skills|项目级 CodeBuddy
project-workbuddy|$PROJECT_ROOT/.workbuddy/skills|项目级 WorkBuddy
project-qoder|$PROJECT_ROOT/.qoder/skills|项目级 Qoder
EOF
}

# Git Bash 下 /c/Users/... 不好看，转成 Windows 路径显示
pretty_path() {
  local p="$1"
  if command -v cygpath >/dev/null 2>&1 && [ "${p:0:1}" = "/" ]; then
    cygpath -w "$p"
  else
    printf '%s\n' "$p"
  fi
}

# 输出 "HIT<TAB>name<TAB>path<TAB>label" / "NEW<TAB>..." / "MISS<TAB>..."
# HIT = skills 目录已存在（覆盖更新）；NEW = 工具在用但还没建过 skills 子目录（新建）；
# MISS = 工具目录都不在（跳过，不凭空创建）
scan() {
  while IFS='|' read -r name path label; do
    if [ -z "$name" ]; then continue; fi
    if [ -d "$path" ]; then
      printf 'HIT\t%s\t%s\t%s\n' "$name" "$path" "$label"
    elif [ -d "$(dirname "$path")" ]; then
      printf 'NEW\t%s\t%s\t%s\n' "$name" "$path" "$label"
    else
      printf 'MISS\t%s\t%s\t%s\n' "$name" "$path" "$label"
    fi
  done
}

# 收集命中目标到 AUTO_TARGETS
AUTO_TARGETS=()
collect() {
  local list="$1" status name path label
  while IFS=$'\t' read -r status name path label; do
    if [ "$status" = "HIT" ] || [ "$status" = "NEW" ]; then AUTO_TARGETS+=("$path"); fi
  done < <(printf '%s\n' "$list" | scan)
}

report() {
  local scope="$1" list="$2"
  local hits=0 news=0 misses=0 status name path label
  echo "扫描到的 skills 安装位置（$scope）："
  while IFS=$'\t' read -r status name path label; do
    case "$status" in
      HIT)
        hits=$((hits + 1))
        printf '  [装] %-40s %s（已有，覆盖更新）\n' "$(pretty_path "$path")" "$label"
        ;;
      NEW)
        news=$((news + 1))
        printf '  [新] %-40s %s（工具在用，将新建 skills 子目录）\n' "$(pretty_path "$path")" "$label"
        ;;
      *)
        misses=$((misses + 1))
        printf '  [跳] %-40s %s（未检测到 %s）\n' "$(pretty_path "$path")" "$label" "$(pretty_path "$(dirname "$path")")"
        ;;
    esac
  done < <(printf '%s\n' "$list" | scan)
  echo "  命中 $hits 个，新建 $news 个，跳过 $misses 个"
}

# 最终要安装的目标列表：默认全量扫描，显式指定则只装那一处
TARGETS=()
if [ -n "$DEST" ]; then
  TARGETS+=("$DEST")
elif [ ${#EXPLICIT[@]} -gt 0 ]; then
  TARGETS=("${EXPLICIT[@]}")
else
  collect "$(user_targets)"
  if [ "$PROJECT" -eq 1 ]; then collect "$(project_targets)"; fi
  TARGETS=("${AUTO_TARGETS[@]}")
fi

if [ "$LIST" -eq 1 ]; then
  echo "用户级位置："
  report "用户级" "$(user_targets)"
  if [ "$PROJECT" -eq 1 ]; then
    echo
    echo "项目级位置："
    report "项目级" "$(project_targets)"
  fi
  echo
  echo "会安装到的目标："
  if [ ${#AUTO_TARGETS[@]} -eq 0 ]; then
    echo "  （无）"
  else
    for t in "${AUTO_TARGETS[@]}"; do echo "  $(pretty_path "$t")"; done
  fi
  exit 0
fi

if [ ${#TARGETS[@]} -eq 0 ]; then
  TARGETS=("$HOME/.agents/skills")
  echo "没有扫描到已安装工具的 skills 目录，回退到 $(pretty_path "$HOME/.agents/skills")。" >&2
fi

installed=0
for dest in "${TARGETS[@]}"; do
  echo "-> $(pretty_path "$dest")"
  for skill_path in "$SRC_DIR"/*/; do
    [ -f "$skill_path/SKILL.md" ] || continue
    name="$(basename "$skill_path")"
    [ -n "$ONLY" ] && [ "$name" != "$ONLY" ] && continue
    target="$dest/$name"

    if [ "$DRY_RUN" -eq 1 ]; then
      echo "  [dry-run] $name -> $(pretty_path "$target")"
      installed=$((installed + 1))
      continue
    fi

    mkdir -p "$dest"
    if [ -e "$target" ]; then
      if [ "$BACKUP" -eq 1 ]; then
        stamp="$(date +%Y%m%d-%H%M%S)"
        mv "$target" "$target.bak.$stamp"
        echo "  已备份旧版本 -> $(pretty_path "$target.bak.$stamp")"
      else
        rm -rf "$target"
      fi
    fi
    cp -R "$skill_path" "$target"
    echo "  已安装 $name -> $(pretty_path "$target")"
    installed=$((installed + 1))
  done
done

echo "完成：$installed 个技能。重启或新开会话后生效。"

if [ "$PROJECT" -eq 0 ] && [ "$DRY_RUN" -eq 0 ]; then
  echo "提示：--project 可额外装到当前项目下的工具级目录。"
fi
