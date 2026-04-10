#!/usr/bin/env bash
# scripts/bd-helpers.sh — Centralized bd write/query CLI for the workbench.
#
# USAGE:
#   scripts/bd-helpers.sh <subcommand> [args...]
#
# All write subcommands are best-effort: bd failure is logged to stderr
# but never blocks the caller (exit 0). The query subcommand outputs JSON
# to stdout.
#
# This is the SINGLE SOURCE OF TRUTH for bd schema interactions.
# Skills MUST NOT inline bd commands — always call through this script.

set -euo pipefail

# Ensure bd is in PATH and we're in the workbench root (bd auto-discovers .beads/)
export PATH="$HOME/go/bin:$PATH"
export BEADS_DOLT_SHARED_SERVER=1

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
WORKBENCH="$(dirname "$SCRIPT_DIR")"
cd "$WORKBENCH"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
bd_warn() {
  echo "bd-helpers: $1 failed (best-effort, continuing)" >&2
}

# Look up bd issue ID by drupal nid label. Returns empty string if not found.
bd_lookup() {
  local nid="$1"
  bd list --label "drupal-$nid" --json 2>/dev/null \
    | jq -r '.[0].id // empty' 2>/dev/null || true
}

# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

cmd_ensure_issue() {
  local nid="$1" title="$2"
  local module="${3:-}"
  local bd_id
  bd_id=$(bd_lookup "$nid")
  if [[ -z "$bd_id" ]]; then
    local labels="drupal-$nid"
    [[ -n "$module" ]] && labels="$labels,module-$module"
    bd_id=$(bd q "$title" -l "$labels" 2>/dev/null) || { bd_warn "ensure-issue(create)"; bd_id=""; }
  else
    # Add module label if provided and not already present
    if [[ -n "$module" ]]; then
      bd label add "$bd_id" "module-$module" >/dev/null 2>&1 || true
    fi
  fi
  echo "$bd_id"
}

cmd_phase_classification() {
  local bd_id="$1" file="$2"
  [[ -z "$bd_id" ]] && return 0
  bd update "$bd_id" --metadata "$(cat "$file")" 2>/dev/null || bd_warn "phase-classification"
}

cmd_phase_resonance() {
  local bd_id="$1" file="$2"
  [[ -z "$bd_id" ]] && return 0
  local tmp
  tmp=$(mktemp)
  printf 'bd:phase.resonance\n\n' > "$tmp"
  cat "$file" >> "$tmp"
  bd comment "$bd_id" --file "$tmp" 2>/dev/null || bd_warn "phase-resonance"
  rm -f "$tmp"
}

cmd_phase_review() {
  local bd_id="$1" file="$2"
  [[ -z "$bd_id" ]] && return 0
  bd update "$bd_id" --body-file "$file" 2>/dev/null || bd_warn "phase-review"
}

cmd_phase_depth_pre() {
  local bd_id="$1" file="$2"
  [[ -z "$bd_id" ]] && return 0
  bd update "$bd_id" --design "$(cat "$file")" 2>/dev/null || bd_warn "phase-depth-pre"
}

cmd_phase_depth_post_fail() {
  local bd_id="$1" post_file="$2" brief_file="$3"
  [[ -z "$bd_id" ]] && return 0
  local tmp1 tmp2
  tmp1=$(mktemp); tmp2=$(mktemp)
  printf 'bd:phase.solution_depth.post.failed_revert\n\n' > "$tmp1"
  cat "$post_file" >> "$tmp1"
  printf 'bd:phase.solution_depth.attempt_2_start\n\n' > "$tmp2"
  cat "$brief_file" >> "$tmp2"
  bd comment "$bd_id" --file "$tmp1" 2>/dev/null || bd_warn "phase-depth-post-fail(post)"
  bd comment "$bd_id" --file "$tmp2" 2>/dev/null || bd_warn "phase-depth-post-fail(brief)"
  rm -f "$tmp1" "$tmp2"
}

cmd_phase_verification() {
  local bd_id="$1" file="$2"
  [[ -z "$bd_id" ]] && return 0
  local tmp
  tmp=$(mktemp)
  printf 'bd:phase.verification\n\n' > "$tmp"
  cat "$file" >> "$tmp"
  bd comment "$bd_id" --file "$tmp" 2>/dev/null || bd_warn "phase-verification"
  rm -f "$tmp"
}

cmd_phase_push_gate() {
  local bd_id="$1" file="$2"
  [[ -z "$bd_id" ]] && return 0
  local tmp
  tmp=$(mktemp)
  printf 'bd:phase.push_gate (%s)\n\n' "$(date -Iseconds)" > "$tmp"
  cat "$file" >> "$tmp"
  bd note "$bd_id" --file "$tmp" 2>/dev/null || bd_warn "phase-push-gate"
  rm -f "$tmp"
}

cmd_remember_maintainer() {
  local module="$1" maintainer="$2" pref="$3"
  bd remember "$pref" --key "module.${module}.maintainer_pref.${maintainer}" 2>/dev/null \
    || bd_warn "remember-maintainer"
}

cmd_remember_lore() {
  local module="$1" topic="$2" insight="$3"
  bd remember "$insight" --key "module.${module}.lore.${topic}" 2>/dev/null \
    || bd_warn "remember-lore"
}

cmd_query_prior_knowledge() {
  local module="$1"
  local result='{"prior_issues":[],"maintainer_prefs":[],"module_lore":[]}'

  # 1. Prior issues in this module
  local issues
  issues=$(bd list --label "module-$module" --all --json 2>/dev/null || echo "[]")
  if [[ "$issues" != "[]" ]] && [[ -n "$issues" ]]; then
    result=$(echo "$result" | jq --argjson i "$issues" '.prior_issues = $i' 2>/dev/null || echo "$result")
  fi

  # 2. Maintainer preferences
  local prefs
  prefs=$(bd memories "module.$module.maintainer_pref" 2>/dev/null || echo "")
  if [[ -n "$prefs" ]]; then
    result=$(echo "$result" | jq --arg p "$prefs" \
      '.maintainer_prefs = ($p | split("\n") | map(select(. != "")))' 2>/dev/null || echo "$result")
  fi

  # 3. Module lore
  local lore
  lore=$(bd memories "module.$module.lore" 2>/dev/null || echo "")
  if [[ -n "$lore" ]]; then
    result=$(echo "$result" | jq --arg l "$lore" \
      '.module_lore = ($l | split("\n") | map(select(. != "")))' 2>/dev/null || echo "$result")
  fi

  echo "$result"
}

# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------
subcmd="${1:-help}"
shift || true

case "$subcmd" in
  ensure-issue)            cmd_ensure_issue "$@" ;;
  phase-classification)    cmd_phase_classification "$@" ;;
  phase-resonance)         cmd_phase_resonance "$@" ;;
  phase-review)            cmd_phase_review "$@" ;;
  phase-depth-pre)         cmd_phase_depth_pre "$@" ;;
  phase-depth-post-fail)   cmd_phase_depth_post_fail "$@" ;;
  phase-verification)      cmd_phase_verification "$@" ;;
  phase-push-gate)         cmd_phase_push_gate "$@" ;;
  remember-maintainer)     cmd_remember_maintainer "$@" ;;
  remember-lore)           cmd_remember_lore "$@" ;;
  query-prior-knowledge)   cmd_query_prior_knowledge "$@" ;;
  help|-h|--help)
    sed -n '2,14p' "$0"
    echo ""
    echo "Subcommands:"
    echo "  ensure-issue <nid> <title> [module]"
    echo "  phase-classification <bd-id> <file>"
    echo "  phase-resonance <bd-id> <file>"
    echo "  phase-review <bd-id> <file>"
    echo "  phase-depth-pre <bd-id> <file>"
    echo "  phase-depth-post-fail <bd-id> <post-file> <brief-file>"
    echo "  phase-verification <bd-id> <file>"
    echo "  phase-push-gate <bd-id> <file>"
    echo "  remember-maintainer <module> <maintainer> <pref>"
    echo "  remember-lore <module> <topic> <insight>"
    echo "  query-prior-knowledge <module>"
    ;;
  *)
    echo "unknown subcommand: $subcmd" >&2
    exit 2
    ;;
esac
