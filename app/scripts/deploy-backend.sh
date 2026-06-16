#!/usr/bin/env bash
# ----------------------------------------------------------------------------
# deploy-backend.sh — Deploy Yaksha (ksp-saathi) backend to Zoho Catalyst.
#
# Datathon 2026 — Karnataka Police conversational AI
# Project ID  : 47060000000020001  (Catalyst PID, India DC)
# Org ID      : 60074155874
# Console     : https://console.catalyst.zoho.in/baas/60074155874/project/47060000000020001/Development
#
# What it does
#   1. Loads env from .env.deploy (source-controlled defaults, untracked overrides)
#   2. Verifies the catalyst CLI is installed + logged in
#   3. Verifies the active project ID matches EXPECTED_PROJECT_ID
#   4. For each function dir under app/backend/functions/: pip install + pytest
#   5. Deploys each function one at a time (catalyst deploy --only functions:<name>)
#   6. Captures deployed URLs and writes them to .env.deployed
#
# Flags
#   --dry-run    Print every step but don't actually deploy or install
#   --skip-tests Skip pytest (NOT recommended; CI gate)
#   --only NAME  Deploy only one function by name
#   -h | --help  Show usage
#
# Exit codes
#   0  success
#   1  generic failure / aborted
#   2  prerequisite missing (catalyst CLI, login, wrong project)
#   3  test failure
#   4  deploy failure
# ----------------------------------------------------------------------------
set -Eeuo pipefail

# ---------- paths -----------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
BACKEND_DIR="${APP_DIR}/backend"
FUNCTIONS_DIR="${BACKEND_DIR}/functions"
ENV_FILE="${SCRIPT_DIR}/.env.deploy"
DEPLOYED_ENV="${APP_DIR}/.env.deployed"
LOG_DIR="${APP_DIR}/.deploy-logs"
mkdir -p "${LOG_DIR}"
RUN_LOG="${LOG_DIR}/backend-$(date +%Y%m%d-%H%M%S).log"

# ---------- colour output ---------------------------------------------------
if [[ -t 1 ]] && [[ "${NO_COLOR:-0}" != "1" ]]; then
  C_RESET=$'\033[0m'; C_BOLD=$'\033[1m'; C_DIM=$'\033[2m'
  C_RED=$'\033[31m'; C_GRN=$'\033[32m'; C_YLW=$'\033[33m'
  C_BLU=$'\033[34m'; C_MAG=$'\033[35m'; C_CYN=$'\033[36m'
else
  C_RESET=""; C_BOLD=""; C_DIM=""; C_RED=""; C_GRN=""; C_YLW=""; C_BLU=""; C_MAG=""; C_CYN=""
fi
say()  { printf '%s\n' "$*" | tee -a "${RUN_LOG}"; }
info() { say "${C_CYN}[deploy-backend]${C_RESET} $*"; }
ok()   { say "${C_GRN}[deploy-backend] OK${C_RESET} $*"; }
warn() { say "${C_YLW}[deploy-backend] WARN${C_RESET} $*"; }
err()  { say "${C_RED}[deploy-backend] FAIL${C_RESET} $*" >&2; }
step() { say ""; say "${C_BOLD}${C_BLU}=== $* ===${C_RESET}"; }

# ---------- defaults / flags ------------------------------------------------
EXPECTED_PROJECT_ID="${EXPECTED_PROJECT_ID:-47060000000020001}"
EXPECTED_ORG_ID="${EXPECTED_ORG_ID:-60074155874}"
EXPECTED_REGION="${EXPECTED_REGION:-in}"
DRY_RUN=0
SKIP_TESTS=0
ONLY_FUNCTION=""

usage() {
  cat <<EOF
${C_BOLD}deploy-backend.sh${C_RESET} — Deploy Yaksha backend to Zoho Catalyst

Usage:
  $(basename "$0") [--dry-run] [--skip-tests] [--only <function-name>]

Options:
  --dry-run      Print actions without executing
  --skip-tests   Skip pytest (use only for emergency rollouts)
  --only NAME    Deploy a single function by directory name
  -h, --help     Show this help

Environment overrides (also read from ${ENV_FILE} if present):
  EXPECTED_PROJECT_ID   default ${EXPECTED_PROJECT_ID}
  EXPECTED_ORG_ID       default ${EXPECTED_ORG_ID}
  EXPECTED_REGION       default ${EXPECTED_REGION}
  CATALYST_CLI          catalyst CLI binary (default: catalyst)
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)    DRY_RUN=1; shift ;;
    --skip-tests) SKIP_TESTS=1; shift ;;
    --only)       ONLY_FUNCTION="${2:-}"; shift 2 ;;
    -h|--help)    usage; exit 0 ;;
    *)            err "Unknown argument: $1"; usage; exit 1 ;;
  esac
done

# ---------- signal handling -------------------------------------------------
TMP_FILES=()
cleanup() {
  local rc=$?
  if [[ ${#TMP_FILES[@]} -gt 0 ]]; then
    rm -f "${TMP_FILES[@]}" 2>/dev/null || true
  fi
  if [[ $rc -ne 0 ]]; then
    err "deploy-backend.sh exited with code ${rc}. See log: ${RUN_LOG}"
    say "${C_DIM}Last 20 lines of log:${C_RESET}"
    tail -n 20 "${RUN_LOG}" 2>/dev/null || true
  fi
  exit "$rc"
}
trap cleanup EXIT
trap 'err "Interrupted by signal"; exit 130' INT TERM HUP

# ---------- env loader ------------------------------------------------------
load_env() {
  if [[ -f "${ENV_FILE}" ]]; then
    info "Loading env from ${ENV_FILE}"
    # shellcheck disable=SC1090
    set -a; source "${ENV_FILE}"; set +a
  else
    warn "${ENV_FILE} not found — using defaults"
  fi
}

# ---------- runner ----------------------------------------------------------
run() {
  say "${C_DIM}\$ $*${C_RESET}"
  if [[ "${DRY_RUN}" == "1" ]]; then
    return 0
  fi
  "$@" 2>&1 | tee -a "${RUN_LOG}"
  return "${PIPESTATUS[0]}"
}

# ---------- preflight -------------------------------------------------------
preflight() {
  step "Preflight checks"

  CATALYST_CLI="${CATALYST_CLI:-catalyst}"
  if ! command -v "${CATALYST_CLI}" >/dev/null 2>&1; then
    err "catalyst CLI not found. Install: npm install -g zcatalyst-cli"
    exit 2
  fi
  ok "catalyst CLI present: $(${CATALYST_CLI} --version 2>/dev/null || echo unknown)"

  info "Checking catalyst login..."
  if ! "${CATALYST_CLI}" account list >/dev/null 2>&1; then
    err "catalyst CLI not logged in. Run: catalyst login   (pick India DC / accounts.zoho.in)"
    exit 2
  fi
  ok "catalyst account session active"

  if ! command -v python >/dev/null 2>&1 && ! command -v python3 >/dev/null 2>&1; then
    err "python not found (need 3.11+)"
    exit 2
  fi

  if ! command -v pip >/dev/null 2>&1 && ! command -v pip3 >/dev/null 2>&1; then
    err "pip not found"
    exit 2
  fi

  if [[ ! -f "${BACKEND_DIR}/catalyst.json" ]]; then
    err "Missing ${BACKEND_DIR}/catalyst.json — has 'catalyst init' been run?"
    exit 2
  fi

  # Verify the catalyst.json points at the expected project
  local actual_pid
  actual_pid=$(python -c "import json,sys; d=json.load(open(r'${BACKEND_DIR}/catalyst.json')); print(d.get('project_details',{}).get('id') or d.get('projectId') or d.get('id',''))" 2>/dev/null || echo "")
  if [[ -z "${actual_pid}" ]]; then
    warn "Could not parse project id from catalyst.json — skipping strict check"
  elif [[ "${actual_pid}" != "${EXPECTED_PROJECT_ID}" ]]; then
    err "Project ID mismatch. Expected ${EXPECTED_PROJECT_ID}, got ${actual_pid}"
    err "Re-run: cd app/backend && catalyst init  (pick project 'yaksha' / PID ${EXPECTED_PROJECT_ID})"
    exit 2
  else
    ok "Project ID matches: ${actual_pid}"
  fi
}

# ---------- discover functions ---------------------------------------------
list_functions() {
  if [[ ! -d "${FUNCTIONS_DIR}" ]]; then
    err "No functions directory at ${FUNCTIONS_DIR}"
    exit 2
  fi
  find "${FUNCTIONS_DIR}" -mindepth 1 -maxdepth 1 -type d \
    | sort \
    | while read -r d; do
        local name; name="$(basename "$d")"
        [[ "${name}" == "__pycache__" ]] && continue
        [[ "${name}" == .* ]] && continue
        echo "${name}"
      done
}

# ---------- install + test --------------------------------------------------
install_and_test_one() {
  local fn_name="$1"
  local fn_dir="${FUNCTIONS_DIR}/${fn_name}"

  step "Function: ${fn_name}"
  info "Working dir: ${fn_dir}"

  if [[ -f "${fn_dir}/requirements.txt" ]]; then
    info "Installing requirements..."
    (cd "${fn_dir}" && run pip install -q -r requirements.txt) \
      || { err "pip install failed for ${fn_name}"; return 1; }
    ok "deps installed for ${fn_name}"
  else
    warn "no requirements.txt in ${fn_dir} — skipping pip install"
  fi

  if [[ "${SKIP_TESTS}" == "1" ]]; then
    warn "Skipping tests for ${fn_name} (--skip-tests)"
    return 0
  fi

  # Detect any test files
  local has_tests
  has_tests=$(find "${fn_dir}" -maxdepth 2 -type f \( -name 'test_*.py' -o -name '*_test.py' \) | head -n1)
  if [[ -z "${has_tests}" ]]; then
    warn "No pytest files in ${fn_dir} — skipping tests"
    return 0
  fi

  info "Running pytest..."
  (cd "${fn_dir}" && run python -m pytest -q) \
    || { err "pytest failed for ${fn_name}"; return 3; }
  ok "tests pass for ${fn_name}"
}

# ---------- deploy ----------------------------------------------------------
deploy_one() {
  local fn_name="$1"
  info "Deploying function ${fn_name}..."

  local out_file
  out_file="$(mktemp)"
  TMP_FILES+=("${out_file}")

  if [[ "${DRY_RUN}" == "1" ]]; then
    say "${C_DIM}\$ (cd ${BACKEND_DIR} && ${CATALYST_CLI} deploy --only functions:${fn_name})${C_RESET}"
    echo "https://ksp-saathi-prod-DRYRUN.development.catalystserverless.in/server/${fn_name}/" > "${out_file}"
  else
    (cd "${BACKEND_DIR}" && "${CATALYST_CLI}" deploy --only "functions:${fn_name}") \
        2>&1 | tee "${out_file}" | tee -a "${RUN_LOG}" \
      || { err "catalyst deploy failed for ${fn_name}"; return 4; }
  fi

  # Extract URL — Catalyst CLI typically prints "<name>: https://...catalystserverless.in/..."
  local url
  url=$(grep -Eo 'https://[A-Za-z0-9.\-]+catalystserverless\.in/[A-Za-z0-9._/?=&-]*' "${out_file}" | head -n1 || true)

  if [[ -z "${url}" ]]; then
    # Fall back to a deterministic guess so the orchestrator at least has something
    url="https://ksp-saathi-prod.development.catalystserverless.in/server/${fn_name}/"
    warn "Could not parse deployed URL from CLI output; using fallback ${url}"
  fi

  ok "${fn_name} → ${url}"

  # Persist as upper-snake env var, e.g. URL_INTENT_ROUTER=https://...
  local key
  key="URL_$(echo "${fn_name}" | tr '[:lower:]-' '[:upper:]_')"
  echo "${key}=${url}" >> "${DEPLOYED_ENV}"
}

# ---------- main ------------------------------------------------------------
main() {
  step "deploy-backend.sh start — $(date -u +%FT%TZ)"
  info "Log: ${RUN_LOG}"
  info "Dry-run: ${DRY_RUN}   Skip-tests: ${SKIP_TESTS}   Only: ${ONLY_FUNCTION:-<all>}"

  load_env
  preflight

  # Reset .env.deployed (only on a non-dry-run full deploy)
  if [[ "${DRY_RUN}" == "0" && -z "${ONLY_FUNCTION}" ]]; then
    {
      echo "# Yaksha — backend deploy URLs"
      echo "# Generated $(date -u +%FT%TZ) by deploy-backend.sh"
      echo "# Project: ${EXPECTED_PROJECT_ID}  Org: ${EXPECTED_ORG_ID}  Region: ${EXPECTED_REGION}"
    } > "${DEPLOYED_ENV}"
  fi

  step "Discover functions"
  mapfile -t ALL_FUNCS < <(list_functions)
  info "Found ${#ALL_FUNCS[@]} function(s): ${ALL_FUNCS[*]}"

  local targets=()
  if [[ -n "${ONLY_FUNCTION}" ]]; then
    local matched=0
    for f in "${ALL_FUNCS[@]}"; do
      if [[ "${f}" == "${ONLY_FUNCTION}" ]]; then
        targets+=("${f}"); matched=1; break
      fi
    done
    if [[ "${matched}" -eq 0 ]]; then
      err "Function '${ONLY_FUNCTION}' not found under ${FUNCTIONS_DIR}"
      exit 2
    fi
  else
    targets=("${ALL_FUNCS[@]}")
  fi

  # Stage 1 — install + test every target before any deploy (fail fast)
  step "Install deps + run tests"
  for fn in "${targets[@]}"; do
    install_and_test_one "${fn}" || exit $?
  done
  ok "All deps installed + all tests pass"

  # Stage 2 — deploy one function at a time
  step "Deploy functions"
  local failed=()
  for fn in "${targets[@]}"; do
    if ! deploy_one "${fn}"; then
      failed+=("${fn}")
    fi
  done

  if [[ ${#failed[@]} -gt 0 ]]; then
    err "Failed deployments: ${failed[*]}"
    exit 4
  fi

  step "Backend deploy complete"
  ok "All functions deployed. URLs written to ${DEPLOYED_ENV}"
  if [[ -f "${DEPLOYED_ENV}" ]]; then
    say ""
    say "${C_BOLD}Deployed URLs:${C_RESET}"
    grep -E '^URL_' "${DEPLOYED_ENV}" | sed 's/^/  /'
  fi
}

main "$@"
