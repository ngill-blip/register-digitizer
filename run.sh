#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
#  Form Digitizer — setup & launch script
#  Run: bash run.sh
# ─────────────────────────────────────────────────────────────────────────────
set -e
cd "$(dirname "$0")"

echo ""
echo "═══════════════════════════════════════════════"
echo "  📋 Form Digitizer — Setup & Launch"
echo "═══════════════════════════════════════════════"
echo ""

# 1. Check Python
python3 --version >/dev/null 2>&1 || { echo "❌  Python 3 not found. Install from https://python.org"; exit 1; }

# 2. Check / install Tesseract
if ! command -v tesseract &>/dev/null; then
  echo "⚙️  Tesseract not found. Attempting install…"
  if command -v apt-get &>/dev/null; then
    sudo apt-get install -y tesseract-ocr
  elif command -v brew &>/dev/null; then
    brew install tesseract
  else
    echo "❌  Please install Tesseract manually:"
    echo "    macOS:  brew install tesseract"
    echo "    Ubuntu: sudo apt install tesseract-ocr"
    echo "    Windows: https://github.com/UB-Mannheim/tesseract/wiki"
    exit 1
  fi
fi
echo "✅  Tesseract: $(tesseract --version 2>&1 | head -1)"

# 2b. Install language packs (African languages + Hindi/Urdu for India)
echo "⚙️  Checking language packs…"
if command -v brew &>/dev/null; then
  brew list tesseract-lang &>/dev/null || brew install tesseract-lang
  echo "✅  Language packs: OK (all languages via tesseract-lang)"
elif command -v apt-get &>/dev/null; then
  sudo apt-get install -y tesseract-ocr-swa tesseract-ocr-zul \
    tesseract-ocr-xho tesseract-ocr-afr tesseract-ocr-hin \
    tesseract-ocr-urd 2>/dev/null || true
  echo "✅  Language packs: OK"
fi

# 3. Check / install poppler (for PDF support)
if ! command -v pdftoppm &>/dev/null; then
  echo "⚙️  Poppler (PDF support) not found. Attempting install…"
  if command -v apt-get &>/dev/null; then
    sudo apt-get install -y poppler-utils
  elif command -v brew &>/dev/null; then
    brew install poppler
  else
    echo "⚠️  Poppler not installed — PDF upload will be disabled."
    echo "    macOS:  brew install poppler"
    echo "    Ubuntu: sudo apt install poppler-utils"
  fi
else
  echo "✅  Poppler (PDF): OK"
fi

# 4. Python virtual environment
if [ ! -d ".venv" ]; then
  echo "⚙️  Creating virtual environment…"
  python3 -m venv .venv
fi
source .venv/bin/activate

# 5. Install Python packages
echo "⚙️  Installing Python dependencies…"
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
echo "✅  Dependencies installed"

# 6. Launch
echo ""
echo "🚀  Starting server…"
echo "    Open: http://localhost:5050"
echo "    Stop: Ctrl+C"
echo ""
PORT=5050 python3 app.py
