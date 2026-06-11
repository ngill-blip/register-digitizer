#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
#  Register Capture — LIVE meeting mode
#  Double-click to run the vision-backed app + a public tunnel
#  so attendees can scan register pages from their own phones.
# ─────────────────────────────────────────────────────────────
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

# 1. Vision key — use env var, else a saved key file, else prompt once and save it.
KEYFILE="$DIR/gemini_key.txt"
if [ -z "$GEMINI_API_KEY" ] && [ -f "$KEYFILE" ]; then
  GEMINI_API_KEY="$(tr -d '[:space:]' < "$KEYFILE")"
fi
if [ -z "$GEMINI_API_KEY" ] && [ -z "$ANTHROPIC_API_KEY" ]; then
  echo ""
  echo "  No vision key found yet."
  echo "  Get a FREE Gemini key (no credit card): https://aistudio.google.com/apikey"
  echo ""
  read -r -p "  Paste your Gemini API key (or press Enter for demo mode): " GEMINI_API_KEY
  if [ -n "$GEMINI_API_KEY" ]; then
    echo "$GEMINI_API_KEY" > "$KEYFILE"
    chmod 600 "$KEYFILE" 2>/dev/null || true
    echo "  ✅  Saved — future double-clicks will use this key automatically."
  fi
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
