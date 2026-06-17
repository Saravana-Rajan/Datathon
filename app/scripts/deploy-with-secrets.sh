#!/usr/bin/env bash
# =============================================================================
# Sarvik — deploy with secrets injected from .env (never committed)
#
# Pattern:
#   1. Back up each function's catalyst-config.json to .json.bak
#   2. Inject env_variables from app/backend/.env into each config (in memory)
#   3. catalyst deploy
#   4. Restore the .bak — committed files stay secret-free
#
# Usage:
#   bash app/scripts/deploy-with-secrets.sh [function_name|all]
#     all              → deploy all 9 functions (default)
#     <function_name>  → deploy just that one
# =============================================================================
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "$SCRIPT_DIR/../backend" && pwd)"
ENV_FILE="$BACKEND_DIR/.env"
TARGET="${1:-all}"

if [ ! -f "$ENV_FILE" ]; then
    echo "ERROR: $ENV_FILE not found. Run setup-env.sh first."
    exit 1
fi

ALL_FUNCTIONS=(hello intent-router sql-generator cypher-generator rag-retriever synthesizer audit-logger pdf-exporter orchestrator)

if [ "$TARGET" = "all" ]; then
    FUNCTIONS=("${ALL_FUNCTIONS[@]}")
else
    FUNCTIONS=("$TARGET")
fi

cleanup() {
    echo
    echo "→ Restoring clean catalyst-config.json files (no secrets)..."
    for fn in "${ALL_FUNCTIONS[@]}"; do
        BAK="$BACKEND_DIR/functions/$fn/catalyst-config.json.bak"
        if [ -f "$BAK" ]; then
            mv "$BAK" "$BACKEND_DIR/functions/$fn/catalyst-config.json"
        fi
    done
    echo "→ Verifying no secrets in catalyst-config.json files..."
    if grep -l "AQ\.Ab8RN\|neo4j.*databases.neo4j.io\|AIza" "$BACKEND_DIR"/functions/*/catalyst-config.json 2>/dev/null; then
        echo "⚠️  STILL LEAKED — investigate above files"
        exit 1
    fi
    echo "✓ committed files are clean"
}
trap cleanup EXIT

# Load .env into shell environment
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

echo "→ Injecting env_variables into catalyst-config.json (in memory)..."
for fn in "${FUNCTIONS[@]}"; do
    CONFIG="$BACKEND_DIR/functions/$fn/catalyst-config.json"
    if [ ! -f "$CONFIG" ]; then
        echo "  skip: $fn (no config)"
        continue
    fi
    # Backup the clean version
    cp "$CONFIG" "$CONFIG.bak"
    # Inject env vars from .env
    python <<PYEOF
import json, os
p = "$CONFIG"
cfg = json.load(open(p))
cfg.setdefault("deployment", {})["env_variables"] = {
    "GEMINI_API_KEY": os.environ.get("GEMINI_API_KEY", ""),
    "GEMINI_TEXT_MODEL": os.environ.get("GEMINI_TEXT_MODEL", "gemini-2.5-pro"),
    "GEMINI_EMBED_MODEL": os.environ.get("GEMINI_EMBED_MODEL", "gemini-embedding-001"),
    "GEMINI_LIVE_MODEL": os.environ.get("GEMINI_LIVE_MODEL", "gemini-live-2.5-flash-preview"),
    "CATALYST_PROJECT_ID": os.environ.get("CATALYST_PROJECT_ID", ""),
    "CATALYST_ORG_ID": os.environ.get("CATALYST_ORG_ID", ""),
    "CATALYST_API_DOMAIN": os.environ.get("CATALYST_API_DOMAIN", "https://www.zohoapis.in"),
    "CATALYST_API_BASE": os.environ.get("CATALYST_API_BASE", ""),
    "CATALYST_AUDIT_TABLE": os.environ.get("CATALYST_AUDIT_TABLE", "audit_log"),
    "CATALYST_SESSION_TABLE": os.environ.get("CATALYST_SESSION_TABLE", "session_state"),
    "NEO4J_URI": os.environ.get("NEO4J_URI", "PENDING"),
    "NEO4J_USERNAME": os.environ.get("NEO4J_USERNAME", "neo4j"),
    "NEO4J_PASSWORD": os.environ.get("NEO4J_PASSWORD", "PENDING"),
    "NEO4J_DATABASE": os.environ.get("NEO4J_DATABASE", "neo4j"),
    "GOOGLE_MAPS_API_KEY": os.environ.get("GOOGLE_MAPS_API_KEY", "PENDING"),
    "GOOGLE_CLOUD_PROJECT": os.environ.get("GOOGLE_CLOUD_PROJECT", ""),
    "LOG_LEVEL": os.environ.get("LOG_LEVEL", "INFO"),
}
json.dump(cfg, open(p, "w"), indent=2)
PYEOF
    echo "  injected: $fn"
done

echo
echo "→ Deploying to Catalyst (Sarvik)..."
cd "$BACKEND_DIR"
if [ "$TARGET" = "all" ]; then
    catalyst deploy --only functions
else
    catalyst deploy --only "functions:$TARGET"
fi

echo
echo "✓ Deploy complete. Cleanup runs next via EXIT trap."
