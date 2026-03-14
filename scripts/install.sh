#!/usr/bin/env bash
# scripts/install.sh
# Install all Python dependencies and register BSP Knowledge Skills to ~/.claude/skills/
#
# Usage:
#   bash scripts/install.sh              # install + register to user-level ~/.claude/skills/
#   bash scripts/install.sh --project    # install + register to project-level .claude/skills/
#
# Requirements: Python >= 3.11

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILLS_SRC="${REPO_ROOT}/skills"

# ------------------------------------------------------------------
# Parse flags
# ------------------------------------------------------------------
PROJECT_LEVEL=false
for arg in "$@"; do
  case "$arg" in
    --project) PROJECT_LEVEL=true ;;
    *) echo "Unknown argument: $arg" >&2; exit 1 ;;
  esac
done

# ------------------------------------------------------------------
# 1. Install Python dependencies
# ------------------------------------------------------------------
echo "==> Installing Python dependencies..."
pip install -r "${REPO_ROOT}/requirements.txt"

# ------------------------------------------------------------------
# 2. Register skills
# ------------------------------------------------------------------
if [ "${PROJECT_LEVEL}" = true ]; then
  SKILLS_DEST="${REPO_ROOT}/.claude/skills"
  echo "==> Registering skills at project level: ${SKILLS_DEST}"
else
  SKILLS_DEST="${HOME}/.claude/skills"
  echo "==> Registering skills at user level: ${SKILLS_DEST}"
fi

mkdir -p "${SKILLS_DEST}"

REGISTERED=0
for skill_dir in "${SKILLS_SRC}"/*/; do
  skill_name="$(basename "${skill_dir}")"
  skill_file="${skill_dir}skill.md"

  if [ ! -f "${skill_file}" ]; then
    echo "    [skip] ${skill_name}: no skill.md found yet"
    continue
  fi

  dest_file="${SKILLS_DEST}/${skill_name}.md"
  # Use a symlink so edits to the source are reflected immediately
  ln -sf "${skill_file}" "${dest_file}"
  echo "    [ok]   ${skill_name} -> ${dest_file}"
  REGISTERED=$((REGISTERED + 1))
done

echo ""
echo "Done. ${REGISTERED} skill(s) registered to ${SKILLS_DEST}"
echo ""
echo "Next steps:"
echo "  1. Initialise the Kuzu knowledge graph:"
echo "       python knowledge-graph/schema/init_db.py"
echo "  2. Build the base knowledge graph:"
echo "       python scripts/build_base_graph.py"
echo "  3. Start the MCP tool server:"
echo "       python mcp/server.py"
echo "  4. Open Claude Code and invoke a skill with /skill-name"
