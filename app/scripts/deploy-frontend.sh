#!/usr/bin/env bash
# ----------------------------------------------------------------------------
# deploy-frontend.sh — Deploy Sarvik Next.js frontend to Catalyst Web Client.
#
# Datathon 2026 — Karnataka Police conversational AI
# Project ID : 47060000000020024 (India DC)
# Workflow   : npm install -> npm run build -> catalyst deploy --only web-client-hosting
# ----------------------------------------------------------------------------
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
FRONTEND_DIR="${APP_DIR}/frontend"
ENV_FILE="${SCRIPT_DIR}/.env.deploy"
DEPLOYED_ENV="${APP_DIR}/.env.deployed"
LOG_DIR="${APP_DIR}/.deploy-logs"
mkdir -p "${LOG_DIR}"
RUN_LOG="${LOG_DIR}/frontend-$(date +%Y%m%d-%H%M%S).log"

if [[ -t 1 ]] && [[ "${NO_COLOR:-0}" != "1" ]]; then
  C_RESET=$'\033[0m'; C_BOLD=$'\033[1m'; C_DIM=$'\033[2m'
  C_RED=$'\033[31m'; C_GRN=$'\033[32m'; C_YLW=$'\033[33m'; C_BLU=$'\033[34m'; C_CYN=$'\033[36m'
else
  C_RESET=""; C_BOLD=""; C_DIM=""; C_RED=""; C_GRN=""; C_YLW=""; C_BLU=""; C_CYN=""
fi
say()  { printf '%s\n' "$*" | tee -a "${RUN_LOG}"; }
info() { say "${C_CYN}[deploy-frontend]${C_RESET} $*"; }
ok()   { say "${C_GRN}[deploy-frontend] OK${C_RESET} $*"; }
warn() { say "${C_YLW}[deploy-frontend] WARN${C_RESET} $*"; }
err()  { say "${C_RED}[deploy-frontend] FAIL${C_RESET} $*" >&2; }
step() { say ""; say "${C_BOLD}${C_BLU}=== $* ===${C_RESET}"; }

EXPECTED_PROJECT_ID="${EXPECTED_PROJECT_ID:-47060000000020024}"
DRY_RUN=0
SKIP_BUILD=0
CATALYST_CLI="${CATALYST_CLI:-catalyst}"

usage() {
  cat <<EOF
${C_BOLD}deploy-frontend.sh${C_RESET} — Deploy Sarvik frontend to Catalyst Web Client Hosting

Usage:
  $(basename "$0") [--dry-run] [--skip-build]

Options:
  --dry-run     Print actions, do not run npm install / build / deploy
  --skip-build  Reuse existing out/ build artifacts
  -h, --help    Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)   DRY_RUN=1; shift ;;
    --skip-build) SKIP_BUILD=1; shift ;;
    -h|--help)   usage; exit 0 ;;
    *)           err "Unknown arg: $1"; usage; exit 1 ;;
  esac
done

cleanup() {
  local rc=$?
  if [[ $rc -ne 0 ]]; then
    err "deploy-frontend.sh exited with code ${rc}. See log: ${RUN_LOG}"
    tail -n 20 "${RUN_LOG}" 2>/dev/null || true
  fi
  exit "$rc"
}
trap cleanup EXIT
trap 'err "Interrupted"; exit 130' INT TERM HUP

run() {
  say "${C_DIM}\$ $*${C_RESET}"
  if [[ "${DRY_RUN}" == "1" ]]; then return 0; fi
  "$@" 2>&1 | tee -a "${RUN_LOG}"
  return "${PIPESTATUS[0]}"
}

step "deploy-frontend.sh start — $(date -u +%FT%TZ)"
info "Log: ${RUN_LOG}"

if [[ -f "${ENV_FILE}" ]]; then
  info "Loading env from ${ENV_FILE}"
  # shellcheck disable=SC1090
  set -a; source "${ENV_FILE}"; set +a
fi

step "Preflight"
command -v node >/dev/null 2>&1 || { err "node not found (need 20+)"; exit 2; }
command -v npm  >/dev/null 2>&1 || { err "npm not found"; exit 2; }
command -v "${CATALYST_CLI}" >/dev/null 2>&1 || { err "catalyst CLI missing"; exit 2; }
"${CATALYST_CLI}" account list >/dev/null 2>&1 || { err "catalyst not logged in (run: catalyst login)"; exit 2; }

if [[ ! -d "${FRONTEND_DIR}" ]]; then
  err "frontend dir missing: ${FRONTEND_DIR}"; exit 2
fi
if [[ ! -f "${FRONTEND_DIR}/catalyst.json" ]]; then
  err "missing ${FRONTEND_DIR}/catalyst.json — run 'catalyst init' inside app/frontend"
  exit 2
fi

ok "node $(node --version), npm $(npm --version)"
ok "catalyst CLI logged in"

step "npm install"
if [[ "${SKIP_BUILD}" == "1" ]]; then
  warn "Skipping npm install (--skip-build)"
else
  (cd "${FRONTEND_DIR}" && run npm install --no-fund --no-audit) \
    || { err "npm install failed"; exit 3; }
  ok "deps installed"
fi

step "npm run build"
if [[ "${SKIP_BUILD}" == "1" ]]; then
  warn "Skipping build (--skip-build)"
else
  (cd "${FRONTEND_DIR}" && run npm run build) \
    || { err "next build failed"; exit 3; }
  ok "build complete"
fi

step "catalyst deploy --only web-client-hosting"
DEPLOY_OUT="$(mktemp)"
trap 'rm -f "${DEPLOY_OUT}"' EXIT
if [[ "${DRY_RUN}" == "1" ]]; then
  echo "https://ksp-saathi-prod-DRYRUN.development.catalystserverless.in/app/" > "${DEPLOY_OUT}"
else
  (cd "${FRONTEND_DIR}" && "${CATALYST_CLI}" deploy --only web-client-hosting) \
      2>&1 | tee "${DEPLOY_OUT}" | tee -a "${RUN_LOG}" \
    || { err "catalyst frontend deploy failed"; exit 4; }
fi

URL=$(grep -Eo 'https://[A-Za-z0-9.\-]+catalystserverless\.in[/A-Za-z0-9._?=&-]*' "${DEPLOY_OUT}" | head -n1 || true)
if [[ -z "${URL}" ]]; then
  URL="https://ksp-saathi-prod.development.catalystserverless.in/app/"
  warn "Could not parse deployed URL — using fallback ${URL}"
fi

# Append to .env.deployed (don't wipe backend URLs)
if [[ "${DRY_RUN}" == "0" ]]; then
  touch "${DEPLOYED_ENV}"
  # Strip any prior URL_FRONTEND= line, then append
  if grep -qE '^URL_FRONTEND=' "${DEPLOYED_ENV}" 2>/dev/null; then
    grep -vE '^URL_FRONTEND=' "${DEPLOYED_ENV}" > "${DEPLOYED_ENV}.tmp" || true
    mv "${DEPLOYED_ENV}.tmp" "${DEPLOYED_ENV}"
  fi
  echo "URL_FRONTEND=${URL}" >> "${DEPLOYED_ENV}"
fi

step "Frontend deploy complete"
ok "Frontend live at: ${URL}"
say ""
say "${C_BOLD}Next steps:${C_RESET}"
say "  1. Visit ${URL} and check the login screen renders"
say "  2. Run scripts/verify-deploy.sh to smoke-test backend endpoints"
say "  3. Confirm NEXT_PUBLIC_* env vars baked into this build are the production ones"
