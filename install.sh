#!/usr/bin/env bash
set -euo pipefail

# ── ShadowDrive macOS Installer ──────────────────────────────────────────

INSTALL_DIR="$HOME/.local/share/shadowdrive"
VENV_DIR="$INSTALL_DIR/venv"
BIN_DIR="$HOME/.local/bin"
CONFIG_DIR="$HOME/.config/shadowdrive"
LOG_DIR="$CONFIG_DIR/logs"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
PLIST_NAME="com.shadowdrive.agent"

echo "╔══════════════════════════════════════════════════╗"
echo "║       ShadowDrive — Self-Hosted Encrypted Sync   ║"
echo "║              macOS Installer v1.0                 ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# 1. Check Python 3.10+
echo "→ Checking Python..."
if ! command -v python3 &>/dev/null; then
    echo "ERROR: Python 3 is required. Install from https://python.org"
    exit 1
fi

PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)
if [ "$PY_MAJOR" -lt 3 ] || ([ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]); then
    echo "ERROR: Python 3.10+ required. Found: $PY_VERSION"
    exit 1
fi
echo "  ✅ Python $PY_VERSION"

# 2. Create directories
echo "→ Creating directories..."
mkdir -p "$INSTALL_DIR" "$BIN_DIR" "$CONFIG_DIR" "$LOG_DIR" "$LAUNCH_AGENTS_DIR"

# 3. Copy client code
echo "→ Installing ShadowDrive client..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp -R "$SCRIPT_DIR/Client-Logic/"* "$INSTALL_DIR/"

# 4. Create virtual environment
echo "→ Setting up Python environment..."
python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet -r "$INSTALL_DIR/requirements.txt"

# 5. Create default config
if [ ! -f "$CONFIG_DIR/shadowdrive.yaml" ]; then
    echo "→ Creating default configuration..."
    cat > "$CONFIG_DIR/shadowdrive.yaml" << 'YAML'
server_url: "http://localhost:8000"
watch_folder: "~/ShadowDrive"
sync_interval_seconds: 10
chunk_size_bytes: 2097152
chunk_threshold_bytes: 5242880
compression: "zlib"
YAML
fi

# 6. Create wrapper script
echo "→ Creating shadowdrive command..."
cat > "$BIN_DIR/shadowdrive" << EOF
#!/usr/bin/env bash
cd "$INSTALL_DIR"
exec "$VENV_DIR/bin/python" -m main "\$@"
EOF
chmod +x "$BIN_DIR/shadowdrive"

# 7. Install launchd plist for auto-start
echo "→ Installing auto-start daemon..."
cat > "$LAUNCH_AGENTS_DIR/$PLIST_NAME.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$PLIST_NAME</string>
    <key>ProgramArguments</key>
    <array>
        <string>$VENV_DIR/bin/python</string>
        <string>-m</string>
        <string>main</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$INSTALL_DIR</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>
    <key>StandardOutPath</key>
    <string>$LOG_DIR/stdout.log</string>
    <key>StandardErrorPath</key>
    <string>$LOG_DIR/stderr.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>$VENV_DIR/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
EOF

# 8. Load the agent
launchctl unload "$LAUNCH_AGENTS_DIR/$PLIST_NAME.plist" 2>/dev/null || true
launchctl load "$LAUNCH_AGENTS_DIR/$PLIST_NAME.plist"

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║              Installation Complete! ✅            ║"
echo "╠══════════════════════════════════════════════════╣"
echo "║  Config: $CONFIG_DIR/shadowdrive.yaml"
echo "║  Logs:   $LOG_DIR/"
echo "║  Sync:   ~/ShadowDrive/"
echo "║                                                  ║"
echo "║  Usage:                                          ║"
echo "║    shadowdrive login                             ║"
echo "║    shadowdrive status                            ║"
echo "║    shadowdrive stop                              ║"
echo "╚══════════════════════════════════════════════════╝"
