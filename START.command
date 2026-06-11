#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
#  Form Digitizer — Double-click to launch
#  Opens the app + ngrok in two terminal tabs automatically
# ─────────────────────────────────────────────────────────────
DIR="$(cd "$(dirname "$0")" && pwd)"

# Open a new Terminal tab for the Flask app
osascript <<EOF
tell application "Terminal"
    activate
    tell application "System Events" to keystroke "t" using command down
    delay 0.5
    do script "cd '$DIR' && bash run.sh" in front window
end tell
EOF

# Wait for Flask to start, then launch ngrok in this window
sleep 4
echo ""
echo "══════════════════════════════════════════════"
echo "  🌐 Starting ngrok tunnel..."
echo "  Share: https://curled-routine-disarray.ngrok-free.dev"
echo "  Exports: https://curled-routine-disarray.ngrok-free.dev/exports"
echo "══════════════════════════════════════════════"
echo ""
ngrok http --domain=curled-routine-disarray.ngrok-free.dev 5050
