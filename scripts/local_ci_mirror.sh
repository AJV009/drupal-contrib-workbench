#!/usr/bin/env bash
#
# local_ci_mirror.sh
#
# Mirror the Drupal CI pipeline jobs locally for a module that lives inside
# a DDEV project. Catches phpcs / phpstan / cspell / phpunit / composer
# failures before they reach the CI pipeline, so you do not ping-pong
# force-pushes on a drupal.org issue fork.
#
# Usage:
#   scripts/local_ci_mirror.sh <module_path> [options]
#
# <module_path> is relative to the DDEV project root (e.g.
# `web/modules/contrib/ai_agents`). The script walks up from the current
# working directory to find the DDEV root, so you can invoke it from
# anywhere inside the project.
#
# Options:
#   --only <jobs>     Comma-separated list of jobs to run (overrides default set)
#   --skip <jobs>     Comma-separated list of jobs to skip
#   --tests-only      Run only phpunit (faster feedback when iterating on tests)
#   --fast            Skip phpunit (run only the static-analysis jobs)
#   --json            Emit a JSON summary line after the normal output
#   -h, --help        Show this help and exit
#
# Known jobs: phpcs phpstan cspell phpunit composer stylelint eslint
#
# Behavior details:
#
#   - Jobs are skipped automatically if their configuration files are absent
#     (e.g. phpstan is skipped if <module>/phpstan.neon does not exist).
#   - If the module's .gitlab-ci.yml sets `allow_failure: true` on a job,
#     the script skips that job (matches CI: that job is informational only).
#   - If .gitlab-ci.yml variables contain `SKIP_ESLINT: 1` or
#     `SKIP_STYLELINT: 1`, those jobs are skipped.
#   - cspell is run with a temporary config that includes the module's
#     `.cspell-project-words.txt` as a dictionary, matching how the Drupal
#     CI template resolves it.
#
# Exit code:
#   0 if all run jobs passed
#   N where N is the number of failing jobs
#   2 on usage or environment errors
#
# Examples:
#   scripts/local_ci_mirror.sh web/modules/contrib/ai_agents
#   scripts/local_ci_mirror.sh web/modules/contrib/ai --skip eslint,stylelint
#   scripts/local_ci_mirror.sh web/modules/contrib/ai_agents --only phpcs,phpstan
#   scripts/local_ci_mirror.sh web/modules/contrib/ai_agents --fast
#   scripts/local_ci_mirror.sh web/modules/contrib/ai_agents --tests-only

set -u

#############################################
# Argument parsing
#############################################

print_help() {
  sed -n '3,48p' "$0" | sed -e 's/^# \{0,1\}//'
}

MODULE_PATH=""
ONLY=""
SKIP=""
TESTS_ONLY=0
FAST=0
JSON=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      print_help
      exit 0
      ;;
    --only)
      ONLY="${2:-}"
      shift 2
      ;;
    --skip)
      SKIP="${2:-}"
      shift 2
      ;;
    --tests-only)
      TESTS_ONLY=1
      shift
      ;;
    --fast)
      FAST=1
      shift
      ;;
    --json)
      JSON=1
      shift
      ;;
    --)
      shift
      ;;
    -*)
      echo "Unknown option: $1" >&2
      echo "Run with --help for usage." >&2
      exit 2
      ;;
    *)
      if [[ -z "$MODULE_PATH" ]]; then
        MODULE_PATH="$1"
      else
        echo "Unexpected positional arg: $1" >&2
        exit 2
      fi
      shift
      ;;
  esac
done

if [[ -z "$MODULE_PATH" ]]; then
  echo "Error: module path required." >&2
  echo "Usage: $0 <module_path> [options]" >&2
  echo "Run with --help for details." >&2
  exit 2
fi

#############################################
# Color helpers
#############################################

if [[ -t 1 ]]; then
  C_GREEN=$'\033[32m'
  C_RED=$'\033[31m'
  C_YELLOW=$'\033[33m'
  C_DIM=$'\033[2m'
  C_BOLD=$'\033[1m'
  C_RESET=$'\033[0m'
else
  C_GREEN=""
  C_RED=""
  C_YELLOW=""
  C_DIM=""
  C_BOLD=""
  C_RESET=""
fi

info()  { echo "${C_DIM}[local-ci]${C_RESET} $*"; }
pass()  { echo "${C_GREEN}pass${C_RESET} $*"; }
fail()  { echo "${C_RED}FAIL${C_RESET} $*"; }
skip_msg() { echo "${C_DIM}skip${C_RESET} $*"; }

#############################################
# Locate DDEV project root
#############################################

DDEV_ROOT=""
search_dir="$(pwd)"
while [[ "$search_dir" != "/" ]]; do
  if [[ -d "$search_dir/.ddev" ]]; then
    DDEV_ROOT="$search_dir"
    break
  fi
  search_dir="$(dirname "$search_dir")"
done

if [[ -z "$DDEV_ROOT" ]]; then
  echo "Error: no .ddev directory found walking up from $(pwd)." >&2
  echo "Run this script from inside a DDEV project." >&2
  exit 2
fi

# Strip trailing slash from module path.
MODULE_PATH="${MODULE_PATH%/}"
ABS_MODULE_PATH="$DDEV_ROOT/$MODULE_PATH"

if [[ ! -d "$ABS_MODULE_PATH" ]]; then
  echo "Error: module path not found: $ABS_MODULE_PATH" >&2
  exit 2
fi

# Path inside the DDEV container. DDEV mounts the project root at /var/www/html.
IN_CONTAINER_MODULE="/var/www/html/$MODULE_PATH"

info "DDEV root:       $DDEV_ROOT"
info "Module path:     $MODULE_PATH"
info "Container path:  $IN_CONTAINER_MODULE"

#############################################
# Parse .gitlab-ci.yml for job allowances
#############################################

# Returns 0 if $job has `allow_failure: true` set under its own block in
# the module's .gitlab-ci.yml. Returns 1 otherwise.
gitlab_job_allow_failure() {
  local job="$1"
  local ci_file="$ABS_MODULE_PATH/.gitlab-ci.yml"
  [[ -f "$ci_file" ]] || return 1
  # Find the job block, read until the next top-level block, check for
  # allow_failure: true.
  awk -v job="$job" '
    $0 ~ "^"job"[[:space:]]*:" { in_block=1; next }
    in_block && /^[^[:space:]]/ { in_block=0 }
    in_block && /allow_failure:[[:space:]]*true/ { found=1 }
    END { exit(found ? 0 : 1) }
  ' "$ci_file"
}

# Returns 0 if a SKIP_<TOOL> variable is set to 1 in the module .gitlab-ci.yml.
gitlab_skip_var() {
  local tool="$1"
  local ci_file="$ABS_MODULE_PATH/.gitlab-ci.yml"
  [[ -f "$ci_file" ]] || return 1
  grep -qE "^[[:space:]]*SKIP_${tool}[[:space:]]*:[[:space:]]*1\b" "$ci_file"
}

#############################################
# Job existence checks (files on disk)
#############################################

module_has_phpstan_config() {
  [[ -f "$ABS_MODULE_PATH/phpstan.neon" ]] || [[ -f "$ABS_MODULE_PATH/phpstan.neon.dist" ]]
}

module_has_composer_json() {
  [[ -f "$ABS_MODULE_PATH/composer.json" ]]
}

module_has_tests() {
  [[ -d "$ABS_MODULE_PATH/tests" ]]
}

module_has_js() {
  find "$ABS_MODULE_PATH" -name "*.js" -not -path "*/node_modules/*" -print -quit | grep -q .
}

module_has_css() {
  find "$ABS_MODULE_PATH" -name "*.css" -not -path "*/node_modules/*" -print -quit | grep -q .
}

# stylelint and eslint on d.o CI inherit their config from the Drupal CI
# template. Locally we can only run them if the module ships its own
# config file. Otherwise they would fail with ConfigurationError, giving
# a false positive that is not actionable for the contributor.
module_has_stylelint_config() {
  for f in .stylelintrc .stylelintrc.json .stylelintrc.yaml .stylelintrc.yml .stylelintrc.js stylelint.config.js stylelint.config.cjs; do
    [[ -f "$ABS_MODULE_PATH/$f" ]] && return 0
  done
  return 1
}

module_has_eslint_config() {
  # Only consider a module "has eslint config" if it ships the modern
  # flat-config format (eslint.config.js/cjs/mjs). Legacy .eslintrc.*
  # files are not runnable with `npx eslint` which defaults to v9+
  # (the flat-config-only major version). CI may still use an older
  # eslint to handle legacy configs, but we cannot reliably replicate
  # that locally. Skip rather than false-positive.
  for f in eslint.config.js eslint.config.cjs eslint.config.mjs; do
    [[ -f "$ABS_MODULE_PATH/$f" ]] && return 0
  done
  return 1
}

#############################################
# --only / --skip filter
#############################################

contains() {
  local needle="$1"
  shift
  local x
  for x in "$@"; do
    [[ "$x" == "$needle" ]] && return 0
  done
  return 1
}

IFS=',' read -r -a ONLY_ARR <<< "${ONLY}"
IFS=',' read -r -a SKIP_ARR <<< "${SKIP}"

should_run() {
  local job="$1"

  if [[ $TESTS_ONLY -eq 1 ]]; then
    [[ "$job" == "phpunit" ]] && return 0 || return 1
  fi
  if [[ $FAST -eq 1 && "$job" == "phpunit" ]]; then
    return 1
  fi

  if [[ -n "$ONLY" ]]; then
    contains "$job" "${ONLY_ARR[@]}" || return 1
  fi
  if [[ -n "$SKIP" ]]; then
    contains "$job" "${SKIP_ARR[@]}" && return 1
  fi

  # Respect gitlab-ci allow_failure: true and SKIP_* variables.
  if gitlab_job_allow_failure "$job"; then
    return 1
  fi

  # Map job name to the SKIP_<TOOL> convention.
  case "$job" in
    eslint)
      gitlab_skip_var "ESLINT" && return 1
      module_has_js || return 1
      module_has_eslint_config || return 1
      ;;
    stylelint)
      gitlab_skip_var "STYLELINT" && return 1
      module_has_css || return 1
      module_has_stylelint_config || return 1
      ;;
    phpstan)
      module_has_phpstan_config || return 1
      ;;
    composer)
      module_has_composer_json || return 1
      ;;
    phpunit)
      module_has_tests || return 1
      ;;
  esac
  return 0
}

#############################################
# Job runners
#############################################

declare -A RESULTS
declare -A REASONS
PASS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0

run_job() {
  local name="$1"
  shift
  local description="$1"
  shift

  if ! should_run "$name"; then
    skip_msg "$name ($description)"
    RESULTS[$name]="skip"
    SKIP_COUNT=$((SKIP_COUNT + 1))
    return 0
  fi

  echo ""
  echo "${C_BOLD}=== $name ===${C_RESET}"
  info "$description"

  if "$@"; then
    pass "$name"
    RESULTS[$name]="pass"
    PASS_COUNT=$((PASS_COUNT + 1))
  else
    fail "$name"
    RESULTS[$name]="fail"
    FAIL_COUNT=$((FAIL_COUNT + 1))
  fi
}

#############################################
# Individual job commands
#############################################

job_phpcs() {
  # Drupal CI runs phpcs with:
  # - ignore_warnings_on_exit=1 so warnings are reported but do not fail
  # - --extensions limited to PHP-style files, since stylelint/eslint
  #   cover CSS and JS. Scanning JS with phpcs produces false errors
  #   (e.g. JavaScript's lowercase `true`/`false` hitting the Drupal
  #   "TRUE/FALSE must be uppercase" rule).
  (
    cd "$DDEV_ROOT" && \
    ddev exec /var/www/html/vendor/bin/phpcs \
      --standard=Drupal,DrupalPractice \
      --extensions=php,module,install,inc,test,profile,theme,info,txt,yml \
      --runtime-set ignore_warnings_on_exit 1 \
      "$IN_CONTAINER_MODULE"
  )
}

job_phpstan() {
  (
    cd "$DDEV_ROOT" && \
    ddev exec bash -c "cd '$IN_CONTAINER_MODULE' && /var/www/html/vendor/bin/phpstan analyse src/ --configuration=phpstan.neon --no-progress --memory-limit=1G"
  )
}

job_composer_validate() {
  (
    cd "$DDEV_ROOT" && \
    ddev exec bash -c "cd '$IN_CONTAINER_MODULE' && composer validate --no-check-all --no-check-publish"
  )
}

job_phpunit() {
  (
    cd "$DDEV_ROOT" && \
    ddev exec bash -c "cd /var/www/html/web && SIMPLETEST_DB=sqlite://localhost//tmp/test.sqlite SIMPLETEST_BASE_URL=http://localhost ../vendor/bin/phpunit -c core/phpunit.xml.dist '../$MODULE_PATH/tests/'"
  )
}

# cspell is tricky to mirror perfectly because the Drupal CI template
# ships its own base dictionary (with Drupal-standard terms like
# `langcode`, `vid`, `tid`, etc.) that we cannot easily replicate
# locally. A naive `npx cspell` against the whole module produces
# dozens of false positives from pre-existing terms.
#
# Pragmatic approach: run cspell only against files that have uncommitted
# or commit-local changes (files we are about to push). This catches
# NEW unknown words introduced by the current work, which is the failure
# mode we care about, without false-positiving on pre-existing
# Drupal-standard vocabulary in unchanged files.
#
# The project's `.cspell-project-words.txt` is loaded as a dictionary so
# words that CI accepts are also accepted locally.
job_cspell() {
  local words_file="$ABS_MODULE_PATH/.cspell-project-words.txt"

  # Collect changed files: uncommitted changes plus commits ahead of the
  # tracking upstream (or origin/HEAD if no upstream is set).
  local changed_files
  changed_files="$(cd "$ABS_MODULE_PATH" && {
    # Uncommitted changes (staged and unstaged).
    git diff --name-only HEAD 2>/dev/null || true
    # Commits ahead of upstream.
    local upstream
    upstream="$(git rev-parse --abbrev-ref '@{upstream}' 2>/dev/null || true)"
    if [[ -n "$upstream" ]]; then
      git diff --name-only "$upstream"...HEAD 2>/dev/null || true
    fi
    # Files created but not tracked.
    git ls-files --others --exclude-standard 2>/dev/null || true
  } | sort -u | grep -vE '\.(png|jpg|jpeg|gif|svg|ico|woff2?|ttf|eot|min\.(js|css)|map)$' || true)"

  if [[ -z "$changed_files" ]]; then
    info "No changed files detected, nothing to check with cspell."
    return 0
  fi

  # Build the temporary config. The dictionary path MUST be absolute
  # because cspell resolves relative dictionary paths against the config
  # file location, not the CWD.
  local tmp_config
  tmp_config="$(mktemp -t cspell-local-XXXXXX.json)"
  {
    echo "{"
    echo '  "version": "0.2",'
    echo '  "language": "en",'
    if [[ -f "$words_file" ]]; then
      echo '  "dictionaryDefinitions": ['
      printf '    {"name": "project-words", "path": "%s", "addWords": true}\n' "$words_file"
      echo '  ],'
      echo '  "dictionaries": ["project-words"],'
    fi
    echo '  "ignorePaths": ['
    echo '    "node_modules/**", "vendor/**", ".git/**",'
    echo '    ".cspell-project-words.txt",'
    echo '    "**/*.min.js", "**/*.min.css",'
    echo '    "tests/assets/**",'
    echo '    "tests/resources/**",'
    echo '    "**/*.map"'
    echo '  ]'
    echo "}"
  } > "$tmp_config"

  info "Scanning $(echo "$changed_files" | wc -l) changed file(s) with cspell."

  local rc=0
  (
    cd "$ABS_MODULE_PATH" && \
    echo "$changed_files" | xargs -r npx --yes cspell --no-progress --config "$tmp_config" 2>&1
  ) || rc=$?
  rm -f "$tmp_config"

  if [[ $rc -ne 0 ]]; then
    echo ""
    info "Note: cspell only scanned changed files. Pre-existing vocabulary in"
    info "unchanged files is not verified locally (it is checked on CI)."
  fi
  return $rc
}

job_stylelint() {
  (
    cd "$ABS_MODULE_PATH" && \
    npx --yes stylelint "**/*.css" 2>&1
  )
}

job_eslint() {
  (
    cd "$ABS_MODULE_PATH" && \
    npx --yes eslint "**/*.js" 2>&1
  )
}

#############################################
# Run jobs
#############################################

# Fast static analysis first (fail early, cheapest).
run_job phpcs "PHP Coding Standards (Drupal,DrupalPractice)" job_phpcs
run_job phpstan "PHPStan static analysis" job_phpstan
run_job cspell "cspell with project-words dictionary" job_cspell
run_job stylelint "stylelint (CSS)" job_stylelint
run_job eslint "eslint (JS)" job_eslint
run_job composer "composer validate" job_composer_validate
# Slowest last.
run_job phpunit "phpunit (module tests)" job_phpunit

#############################################
# Summary
#############################################

echo ""
echo "${C_BOLD}=== SUMMARY ===${C_RESET}"
for job in phpcs phpstan cspell stylelint eslint composer phpunit; do
  status="${RESULTS[$job]:-not-run}"
  case "$status" in
    pass) printf "  %spass%s  %s\n" "$C_GREEN" "$C_RESET" "$job" ;;
    fail) printf "  %sFAIL%s  %s\n" "$C_RED" "$C_RESET" "$job" ;;
    skip) printf "  %sskip%s  %s\n" "$C_DIM" "$C_RESET" "$job" ;;
    *)    printf "  %sn/a%s   %s\n" "$C_YELLOW" "$C_RESET" "$job" ;;
  esac
done
echo ""
echo "Passed: $PASS_COUNT  Failed: $FAIL_COUNT  Skipped: $SKIP_COUNT"

if [[ $JSON -eq 1 ]]; then
  printf '{"passed":%d,"failed":%d,"skipped":%d,"results":{' "$PASS_COUNT" "$FAIL_COUNT" "$SKIP_COUNT"
  first=1
  for job in phpcs phpstan cspell stylelint eslint composer phpunit; do
    status="${RESULTS[$job]:-not-run}"
    [[ $first -eq 0 ]] && printf ','
    printf '"%s":"%s"' "$job" "$status"
    first=0
  done
  printf '}}\n'
fi

if [[ $FAIL_COUNT -eq 0 ]]; then
  echo ""
  echo "${C_GREEN}${C_BOLD}All scoped jobs passed. Safe to push.${C_RESET}"
  exit 0
fi

echo ""
echo "${C_RED}${C_BOLD}$FAIL_COUNT job(s) failed. Do NOT push until fixed.${C_RESET}"
exit "$FAIL_COUNT"
