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

# Disable user-site on Windows Store Python — Catalyst's `pip install --target`
# fails with "Can not combine '--user' and '--target'" otherwise.
export PYTHONNOUSERSITE=1
export PIP_USER=0

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
        CONFIG="$BACKEND_DIR/functions/$fn/catalyst-config.json"
        if [ -f "$BAK" ]; then
            # Use cp + rm rather than mv so we overwrite even if Windows
            # has a stale handle on $CONFIG. Without -f, mv can silently
            # leave the dirty file in place on Git Bash.
            cp -f "$BAK" "$CONFIG"
            rm -f "$BAK"
        fi
    done
    echo "→ Removing vendored shared/ from each function (keeps repo clean)..."
    for fn in "${ALL_FUNCTIONS[@]}"; do
        VENDORED="$BACKEND_DIR/functions/$fn/shared"
        # Sanity: only delete if it has the marker we vendor; never nuke a user dir
        if [ -d "$VENDORED" ] && [ -f "$VENDORED/.vendored" ]; then
            rm -rf "$VENDORED"
        fi
    done
    echo "→ Verifying no env_variables remain in catalyst-config.json files..."
    LEAK_FOUND=0
    for fn in "${ALL_FUNCTIONS[@]}"; do
        CONFIG="$BACKEND_DIR/functions/$fn/catalyst-config.json"
        if [ -f "$CONFIG" ] && grep -q '"env_variables"' "$CONFIG"; then
            echo "  STILL DIRTY: $CONFIG"
            LEAK_FOUND=1
        fi
    done
    if [ "$LEAK_FOUND" -ne 0 ]; then
        echo "STILL LEAKED — investigate above files"
        exit 1
    fi
    echo "committed files are clean"
}
trap cleanup EXIT

# ---------------------------------------------------------------------------
# Vendor shared/ into each function dir so Catalyst's per-function zip bundle
# contains `shared/` next to index.py. Catalyst only zips the function dir,
# so `from shared.xxx import yyy` will ImportError without this step.
# We tag the vendored copy with a .vendored marker so cleanup() only removes
# our copy, never a user-authored shared/ dir.
# ---------------------------------------------------------------------------
SHARED_SRC="$BACKEND_DIR/shared"
if [ ! -d "$SHARED_SRC" ]; then
    echo "ERROR: $SHARED_SRC not found — cannot vendor shared/ into functions."
    exit 1
fi
echo "→ Vendoring shared/ into each function dir..."
for fn in "${FUNCTIONS[@]}"; do
    FN_DIR="$BACKEND_DIR/functions/$fn"
    if [ ! -d "$FN_DIR" ]; then
        continue
    fi
    DEST="$FN_DIR/shared"
    # If a non-vendored shared/ already exists (unlikely), bail loudly.
    if [ -d "$DEST" ] && [ ! -f "$DEST/.vendored" ]; then
        echo "  WARN: $DEST exists and is not ours — refusing to overwrite."
        continue
    fi
    rm -rf "$DEST"
    cp -r "$SHARED_SRC" "$DEST"
    # Strip __pycache__ from the vendored copy
    find "$DEST" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    touch "$DEST/.vendored"
    echo "  vendored: $fn"
done

# Load .env into shell environment
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

echo "→ Injecting env_variables into catalyst-config.json (in memory)..."
# On Git Bash for Windows, paths like /c/Users/... are POSIX and break native
# Python. Convert to a Windows path when cygpath is available.
to_native_path() {
    if command -v cygpath >/dev/null 2>&1; then
        cygpath -w "$1"
    else
        printf '%s' "$1"
    fi
}
for fn in "${FUNCTIONS[@]}"; do
    CONFIG="$BACKEND_DIR/functions/$fn/catalyst-config.json"
    if [ ! -f "$CONFIG" ]; then
        echo "  skip: $fn (no config)"
        continue
    fi
    # Backup the clean version
    cp "$CONFIG" "$CONFIG.bak"
    CONFIG_NATIVE="$(to_native_path "$CONFIG")"
    # Inject env vars from .env
    CONFIG_PATH="$CONFIG_NATIVE" python <<'PYEOF'
import json, os
p = os.environ["CONFIG_PATH"]
cfg = json.load(open(p))
# Catalyst's PutEnvVariables endpoint rejects "reserved keywords" —
# specifically any var starting with CATALYST_ or X_ZOHO_ (platform-set),
# and any blank value. Functions can read X_ZOHO_CATALYST_PROJECT_ID
# etc. that the platform injects automatically at runtime.
raw = {
    "GEMINI_API_KEY": os.environ.get("GEMINI_API_KEY", ""),
    "GEMINI_TEXT_MODEL": os.environ.get("GEMINI_TEXT_MODEL", "gemini-2.5-pro"),
    "GEMINI_EMBED_MODEL": os.environ.get("GEMINI_EMBED_MODEL", "gemini-embedding-001"),
    "GEMINI_LIVE_MODEL": os.environ.get("GEMINI_LIVE_MODEL", "gemini-live-2.5-flash-preview"),
    "AUDIT_TABLE": os.environ.get("CATALYST_AUDIT_TABLE", "audit_log"),
    "SESSION_TABLE": os.environ.get("CATALYST_SESSION_TABLE", "session_state"),
    "NEO4J_URI": os.environ.get("NEO4J_URI", ""),
    "NEO4J_USERNAME": os.environ.get("NEO4J_USERNAME", "neo4j"),
    "NEO4J_PASSWORD": os.environ.get("NEO4J_PASSWORD", ""),
    "NEO4J_DATABASE": os.environ.get("NEO4J_DATABASE", "neo4j"),
    "MAPS_API_KEY": os.environ.get("GOOGLE_MAPS_API_KEY", ""),
    "LOG_LEVEL": os.environ.get("LOG_LEVEL", "INFO"),
}
# Strip blanks + "PENDING" sentinels — Catalyst rejects empty values
# and reserved keywords. Functions read os.getenv with safe defaults.
RESERVED_PREFIXES = ("CATALYST_", "X_ZOHO_", "ZOHO_")
cfg.setdefault("deployment", {})["env_variables"] = {
    k: v for k, v in raw.items()
    if v and v != "PENDING" and not any(k.startswith(p) for p in RESERVED_PREFIXES)
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
