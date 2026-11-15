#!/bin/bash
set -euo pipefail

# Entrypoint for MiniDLNA + Web UI container
# Initializes config if needed, then starts supervisord

CONFIG_FILE="/config/minidlna.conf"
TEMPLATE_FILE="/etc/minidlna.conf.template"
PID_DIR="/run/minidlna"
LOG_DIR="/config/log"
CACHE_DIR="/config/cache"

echo "=== MiniDLNA + Web UI Entrypoint ==="

# Ensure directories exist with correct permissions
mkdir -p "$PID_DIR" "$LOG_DIR" "$CACHE_DIR" /media
chown -R appuser:appuser "$PID_DIR" "$LOG_DIR" "$CACHE_DIR" /media /config 2>/dev/null || true

# Create default minidlna.conf if not exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Creating default minidlna.conf from template..."
    cp "$TEMPLATE_FILE" "$CONFIG_FILE"
    chown appuser:appuser "$CONFIG_FILE"
fi

# Ensure PID file directory is writable
chown -R appuser:appuser "$PID_DIR"

# Fix permissions on config dir (in case of volume mount)
chown -R appuser:appuser /config 2>/dev/null || true

echo "Starting supervisord..."
exec "$@"