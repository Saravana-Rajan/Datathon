#!/usr/bin/env bash
# ----------------------------------------------------------------------------
# verify-deploy.sh — Post-deploy smoke tests for Yaksha (ksp-saathi)
#
# Reads deployed URLs from app/.env.deployed (written by deploy-backend.sh),
# hits each endpoint with a sanity-check payload, and asserts:
#   - HTTP 200
#   - expected JSON field(s) present in the response
#
# Exit code 0 = all pass, 1 = any fail.
# ----------------------------------------------------------------------------
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
DEPLOYED_ENV="${APP_DIR}/.env.deployed"
LOG_DIR="${APP_DIR}/.deploy-logs"
mkdir -p "${LOG_DIR}"
RUN_LOG="${LOG_DIR}/verify-$(date +%Y%m%d-%H%M%S).log"

if [[ -t 1 ]] && [[ "${NO_COLOR:-0}" != "1" ]]; then
  C_RESET=$'\033[0m'; C_BOLD=$'\033[1m'; C_DIM=$'\033[2m'
  C_RED=$'\033[31m'; C_GRN=$'\033[32m'; C_YLW=$'\033[33m'; C_BLU=$'\033[34m'; C_CYN=$'\033[36m'
else
  C_RESET=""; C_BOLD=""; C_DIM=""; C_RED=""; C_GRN=""; C_YLW=""; C_BLU=""; C_CYN=""
fi
say()  { printf '%s\n' "$*" | tee -a "${RUN_LOG}"; }
info() { say "${C_CYN}[verify]${C_RESET} $*"; }
ok()   { say "${C_GRN}[verify] PASS${C_RESET} $*"; }
warn() { say "${C_YLW}[verify] WARN${C_RESET} $*"; }
err()  { say "${C_RED}[verify] FAIL${C_RESET} $*" >&2; }
step() { say ""; say "${C_BOLD}${C_BLU}=== $* ===${C_RESET}"; }

DRY_RUN=0
TIMEOUT=15
AUTH_TOKEN="${VERIFY_AUTH_TOKEN:-}"

usage() {
  cat <<EOF
${C_BOLD}verify-deploy.sh${C_RESET} — Smoke-test deployed Yaksha endpoints

Usage:
  $(basename "$0") [--dry-run] [--timeout SECS]

Reads URLs from: ${DEPLOYED_ENV}

Env:
  VERIFY_AUTH_TOKEN  Bearer token for auth-gated endpoints (optional in dev)
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)  DRY_RUN=1; shift ;;
    --timeout)  TIMEOUT="${2}"; shift 2 ;;
    -h|--help)  usage; exit 0 ;;
    *)          err "Unknown arg: $1"; usage; exit 1 ;;
  esac
done

cleanup() {
  local rc=$?
  if [[ $rc -ne 0 ]]; then
    err "verify-deploy.sh exited ${rc}. See: ${RUN_LOG}"
  fi
  exit "$rc"
}
trap cleanup EXIT
trap 'err "Interrupted"; exit 130' INT TERM HUP

if [[ ! -f "${DEPLOYED_ENV}" ]]; then
  err "Missing ${DEPLOYED_ENV} — run scripts/deploy-backend.sh first"
  exit 2
fi
# shellcheck disable=SC1090
set -a; source "${DEPLOYED_ENV}"; set +a

if ! command -v curl >/dev/null 2>&1; then
  err "curl not found"; exit 2
fi
HAS_JQ=0
command -v jq >/dev/null 2>&1 && HAS_JQ=1

PASS=0; FAIL=0; SKIP=0
FAIL_NAMES=()

# --------------------------------------------------------------------------
# probe NAME METHOD URL EXPECT_FIELDS [JSON_PAYLOAD]
#   - NAME           label for the report
#   - METHOD         GET | POST
#   - URL            full URL (use $URL_<NAME> from .env.deployed)
#   - EXPECT_FIELDS  space-separated list of top-level JSON keys to find
#   - JSON_PAYLOAD   optional JSON body for POST
# --------------------------------------------------------------------------
probe() {
  local name="$1" method="$2" url="$3" expect="$4" payload="${5:-}"

  if [[ -z "${url}" || "${url}" == *DRYRUN* ]]; then
    warn "${name} — URL missing or dry-run placeholder, skipping"
    SKIP=$(( SKIP + 1 )); return 0
  fi

  info "${name} -> ${method} ${url}"
  if [[ "${DRY_RUN}" == "1" ]]; then
    say "${C_DIM}\$ curl -X ${method} ${url} [payload: ${payload:-none}]${C_RESET}"
    PASS=$(( PASS + 1 )); return 0
  fi

  local headers=( -H "Content-Type: application/json" -H "Accept: application/json" )
  if [[ -n "${AUTH_TOKEN}" ]]; then
    headers+=( -H "Authorization: Bearer ${AUTH_TOKEN}" )
  fi

  local body_file status
  body_file="$(mktemp)"

  if [[ "${method}" == "POST" ]]; then
    status=$(curl -sS --max-time "${TIMEOUT}" -o "${body_file}" -w '%{http_code}' \
      -X POST "${headers[@]}" --data "${payload:-{}}" "${url}" || echo "000")
  else
    status=$(curl -sS --max-time "${TIMEOUT}" -o "${body_file}" -w '%{http_code}' \
      "${headers[@]}" "${url}" || echo "000")
  fi

  if [[ "${status}" != "200" ]]; then
    err "${name} — expected HTTP 200, got ${status}"
    say "${C_DIM}  body: $(head -c 400 "${body_file}")${C_RESET}"
    rm -f "${body_file}"
    FAIL=$(( FAIL + 1 )); FAIL_NAMES+=("${name}")
    return 1
  fi

  # Verify expected fields are present in the response
  local missing=()
  for field in ${expect}; do
    if [[ "${HAS_JQ}" == "1" ]]; then
      if ! jq -e --arg k "${field}" 'has($k) or (type=="object" and (.[$k] != null))' "${body_file}" >/dev/null 2>&1; then
        missing+=("${field}")
      fi
    else
      if ! grep -q "\"${field}\"" "${body_file}"; then
        missing+=("${field}")
      fi
    fi
  done

  if [[ ${#missing[@]} -gt 0 ]]; then
    err "${name} — 200 OK but missing fields: ${missing[*]}"
    say "${C_DIM}  body: $(head -c 400 "${body_file}")${C_RESET}"
    rm -f "${body_file}"
    FAIL=$(( FAIL + 1 )); FAIL_NAMES+=("${name}")
    return 1
  fi

  ok "${name} — HTTP 200, all expected fields present"
  rm -f "${body_file}"
  PASS=$(( PASS + 1 ))
}

step "verify-deploy.sh start — $(date -u +%FT%TZ)"
[[ "${HAS_JQ}" == "1" ]] || warn "jq not installed — falling back to grep-based field checks"

step "Smoke tests"

# 1. hello: health check
probe "hello"          "GET"  "${URL_HELLO:-}"          "status region"
# 2. intent-router (English)
probe "intent-router/en" "POST" "${URL_INTENT_ROUTER:-}" "intent confidence" \
  '{"query":"show all chain snatchings near Indiranagar metro last 30 days","language":"en"}'
# 3. intent-router (Kannada)
probe "intent-router/kn" "POST" "${URL_INTENT_ROUTER:-}" "intent confidence" \
  '{"query":"ಈ ಸಂಶಯಿತನ ಮೇಲೆ ಮೊದಲು ಎಷ್ಟು ಪ್ರಕರಣಗಳಿವೆ?","language":"kn"}'
# 4. sql-generator
probe "sql-generator"  "POST" "${URL_SQL_GENERATOR:-}"  "sql" \
  '{"query":"top 5 crime hotspots in Bengaluru this month","schema_hint":"firs"}'
# 5. cypher-generator
probe "cypher-generator" "POST" "${URL_CYPHER_GENERATOR:-}" "cypher" \
  '{"query":"co-accused network for case BNG-FIR-2026-00123","depth":2}'
# 6. rag-retriever
probe "rag-retriever"  "POST" "${URL_RAG_RETRIEVER:-}"  "chunks" \
  '{"query":"chain snatching modus operandi","top_k":3}'
# 7. synthesizer
probe "synthesizer"    "POST" "${URL_SYNTHESIZER:-}"    "answer" \
  '{"context":[{"text":"sample fir row"}],"query":"summarize","language":"en"}'
# 8. audit-logger
probe "audit-logger"   "GET"  "${URL_AUDIT_LOGGER:-}?limit=1" "audit_id"
# 9. pdf-exporter
probe "pdf-exporter"   "POST" "${URL_PDF_EXPORTER:-}"   "pdf_url" \
  '{"conversation_id":"smoke-test","format":"pdf"}'
# 10. orchestrator
probe "orchestrator"   "POST" "${URL_ORCHESTRATOR:-}"   "answer audit_id" \
  '{"query":"hotspots in Bengaluru this month","language":"en","user_id":"smoke@test"}'

# 11. frontend reachable
if [[ -n "${URL_FRONTEND:-}" && "${URL_FRONTEND}" != *DRYRUN* ]]; then
  info "frontend -> HEAD ${URL_FRONTEND}"
  if [[ "${DRY_RUN}" == "0" ]]; then
    front_status=$(curl -sS --max-time "${TIMEOUT}" -o /dev/null -w '%{http_code}' -I "${URL_FRONTEND}" || echo "000")
    if [[ "${front_status}" == "200" || "${front_status}" == "301" || "${front_status}" == "302" ]]; then
      ok "frontend — HTTP ${front_status}"; PASS=$(( PASS + 1 ))
    else
      err "frontend — HTTP ${front_status}"; FAIL=$(( FAIL + 1 )); FAIL_NAMES+=("frontend")
    fi
  else
    PASS=$(( PASS + 1 ))
  fi
else
  warn "URL_FRONTEND not set — skipping frontend reachability"; SKIP=$(( SKIP + 1 ))
fi

step "Summary"
TOTAL=$(( PASS + FAIL + SKIP ))
say "${C_BOLD}Results:${C_RESET} ${C_GRN}${PASS} PASS${C_RESET} / ${C_RED}${FAIL} FAIL${C_RESET} / ${C_YLW}${SKIP} SKIP${C_RESET}  (of ${TOTAL})"

if [[ ${FAIL} -gt 0 ]]; then
  err "Failed: ${FAIL_NAMES[*]}"
  exit 1
fi
ok "All smoke tests passed."
