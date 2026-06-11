#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
#  Register Capture — LIVE meeting mode
#  Double-click to run the vision-backed app + a public tunnel
#  so attendees can scan register pages from their own phones.
# ─────────────────────────────────────────────────────────────
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

# 1. Vision key check (free Gemini preferred)
if [ -z "$GEMINI_API_KEY" ] && [ -z "$ANTHROPIC_API_KEY" ]; then
  echo ""
  echo "⚠️  No vision key set — the app will run in DEMO mode (sample data only)."
  echo ""
  echo "    FREE live reading (recommended): get a free key at"
  echo "        https://aistudio.google.com/apikey   (no credit card)"
  echo "    then run:"
  echo "        export GEMINI_API_KEY=AIza...        # paste your key"
  echo "    and double-click this file again."
  echo ""
  read -r -p "Press Enter to continue in demo mode, or Ctrl+C to cancel… "
fi

# 2. Start the app in a new Terminal tab (port 5060)
osascript <<EOF
tell application "Terminal"
  activate
  tell application "System Events" to keystroke "t" using command down
  delay 0.5
  do script "cd '$DIR' && source .venv/bin/activate 2>/dev/null || python3 -m venv .venv && source .venv/bin/activate; pip install -q -r requirements.txt; PORT=5060 GEMINI_API_KEY='$GEMINI_API_KEY' ANTHROPIC_API_KEY='$ANTHROPIC_API_KEY' python3 register_capture.py" in front window
end tell
EOF

# 3. Open the public tunnel (reuses your existing ngrok domain)
sleep 5
echo ""
echo "══════════════════════════════════════════════════════════"
echo "  🌐  Live link for the meeting:"
echo "      https://curled-routine-disarray.ngrok-free.dev"
echo "  🔑  Access password:  KenyaTB2026"
echo "  📷  A QR code appears on the page after unlocking —"
echo "      attendees scan it to open the tool on their phones."
echo "══════════════════════════════════════════════════════════"
echo ""
ngrok http --domain=curled-routine-disarray.ngrok-free.dev 5060
