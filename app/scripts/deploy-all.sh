#!/usr/bin/env bash
# ----------------------------------------------------------------------------
# deploy-all.sh — Orchestrator: deploy backend, then frontend.
#
# Datathon 2026 — Sarvik (ksp-saathi)
# Stops at the first failure with a clear "what to do next" message.
# ----------------------------------------------------------------------------
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
LOG_DIR="${APP_DIR}/.deploy-logs"
mkdir -p "${LOG_DIR}"
RUN_LOG="${LOG_DIR}/all-$(date +%Y%m%d-%H%M%S).log"

if [[ -t 1 ]] && [[ "${NO_COLOR:-0}" != "1" ]]; then
  C_RESET=$'\033[0m'; C_BOLD=$'\033[1m'; C_DIM=$'\033[2m'
  C_RED=$'\033[31m'; C_GRN=$'\033[32m'; C_YLW=$'\033[33m'; C_BLU=$'\033[34m'; C_MAG=$'\033[35m'; C_CYN=$'\033[36m'
else
  C_RESET=""; C_BOLD=""; C_DIM=""; C_RED=""; C_GRN=""; C_YLW=""; C_BLU=""; C_MAG=""; C_CYN=""
fi
say()  { printf '%s\n' "$*" | tee -a "${RUN_LOG}"; }
info() { say "${C_CYN}[deploy-all]${C_RESET} $*"; }
ok()   { say "${C_GRN}[deploy-all] OK${C_RESET} $*"; }
warn() { say "${C_YLW}[deploy-all] WARN${C_RESET} $*"; }
err()  { say "${C_RED}[deploy-all] FAIL${C_RESET} $*" >&2; }
step() { say ""; say "${C_BOLD}${C_BLU}=== $* ===${C_RESET}"; }

DRY_RUN_FLAG=""
SKIP_TESTS_FLAG=""
SKIP_VERIFY=0

usage() {
  cat <<EOF
${C_BOLD}deploy-all.sh${C_RESET} — full Sarvik deploy (backend then frontend)

Usage:
  $(basename "$0") [--dry-run] [--skip-tests] [--skip-verify]

Options:
  --dry-run      Pass through to child scripts (no real deploy)
  --skip-tests   Pass --skip-tests to backend deploy
  --skip-verify  Skip post-deploy smoke tests
  -h, --help     Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)     DRY_RUN_FLAG="--dry-run"; shift ;;
    --skip-tests)  SKIP_TESTS_FLAG="--skip-tests"; shift ;;
    --skip-verify) SKIP_VERIFY=1; shift ;;
    -h|--help)     usage; exit 0 ;;
    *)             err "Unknown arg: $1"; usage; exit 1 ;;
  esac
done

START_TS=$(date +%s)

abort() {
  local stage="$1"; shift
  local hint="$*"
  err "Aborting deploy at stage: ${stage}"
  say ""
  say "${C_BOLD}${C_YLW}What to do next:${C_RESET}"
  say "  ${hint}"
  say ""
  say "${C_DIM}Full log: ${RUN_LOG}${C_RESET}"
  exit 1
}

cleanup() {
  local rc=$?
  local elapsed=$(( $(date +%s) - START_TS ))
  if [[ $rc -eq 0 ]]; then
    say ""
    ok "${C_BOLD}deploy-all.sh complete in ${elapsed}s${C_RESET}"
  else
    err "deploy-all.sh failed after ${elapsed}s (exit ${rc})"
  fi
  exit "$rc"
}
trap cleanup EXIT
trap 'err "Interrupted"; exit 130' INT TERM HUP

step "Sarvik deploy-all start — $(date -u +%FT%TZ)"
info "Flags: dry-run=${DRY_RUN_FLAG:-no}  skip-tests=${SKIP_TESTS_FLAG:-no}  skip-verify=${SKIP_VERIFY}"

# ---------- Stage 1: backend -----------------------------------------------
step "Stage 1/3: Backend (functions + tests + deploy)"
if ! bash "${SCRIPT_DIR}/deploy-backend.sh" ${DRY_RUN_FLAG} ${SKIP_TESTS_FLAG}; then
  abort "backend" \
    "Backend deploy failed. Inspect ${RUN_LOG} and the backend log under ${LOG_DIR}/. \
Common causes: (a) catalyst CLI not logged in -> run 'catalyst login' against India DC; \
(b) wrong project ID -> rerun 'catalyst init' inside app/backend pointing at PID 47060000000020024; \
(c) pytest failure -> fix the failing test before redeploying; \
(d) Catalyst service quota -> check console.catalyst.zoho.in -> Settings -> Usage."
fi
ok "Backend deployed"

# ---------- Stage 2: frontend ----------------------------------------------
step "Stage 2/3: Frontend (npm build + deploy)"
if ! bash "${SCRIPT_DIR}/deploy-frontend.sh" ${DRY_RUN_FLAG}; then
  abort "frontend" \
    "Frontend deploy failed AFTER backend succeeded. Backend URLs are live; you only need to retry frontend: \
'bash app/scripts/deploy-frontend.sh'. Common causes: (a) 'npm run build' failure -> check Next.js build log; \
(b) catalyst.json missing in app/frontend -> run 'catalyst init' there; \
(c) NEXT_PUBLIC_API_BASE_URL not set at build time -> set it in app/.env.deploy and rerun."
fi
ok "Frontend deployed"

# ---------- Stage 3: verify ------------------------------------------------
if [[ "${SKIP_VERIFY}" == "1" || -n "${DRY_RUN_FLAG}" ]]; then
  warn "Skipping smoke tests (skip-verify=${SKIP_VERIFY}, dry-run=${DRY_RUN_FLAG:-no})"
else
  step "Stage 3/3: Smoke tests"
  if ! bash "${SCRIPT_DIR}/verify-deploy.sh"; then
    abort "verify" \
      "Smoke tests FAILED. The backend deployed but at least one endpoint did not return 200. \
Inspect verify-deploy log under ${LOG_DIR}/. Check Catalyst env vars in console -> Settings -> Environment Variables. \
You can re-run verification alone: 'bash app/scripts/verify-deploy.sh'."
  fi
  ok "Smoke tests passed"
fi

step "Summary"
if [[ -f "${APP_DIR}/.env.deployed" ]]; then
  say "${C_BOLD}Deployed endpoints:${C_RESET}"
  grep -E '^URL_' "${APP_DIR}/.env.deployed" | sed 's/^/  /'
fi
say ""
ok "Sarvik is live."
