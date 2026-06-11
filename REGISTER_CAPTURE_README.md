# Register Capture (vision-backed)

The new, accurate path for handwritten TB registers. Replaces the Tesseract
pipeline with a cloud vision model that reads handwriting **and** understands
the register's table structure.

## Run

```bash
cd ~/Desktop/Claude\ \(DND\)/form-digitizer
source .venv/bin/activate            # or: python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Optional but recommended — turns on live reading of new photos:
export ANTHROPIC_API_KEY=sk-ant-xxxxxxxx
# export VISION_MODEL=claude-opus-4-8   # higher accuracy, higher cost (default: claude-sonnet-4-6)

python register_capture.py
```

Open **http://localhost:5060**.

- **With an API key** → photos you capture are read live by the vision model.
- **Without a key** → the app runs in **demo mode** and returns bundled sample
  rows, so the full capture + review UI works offline for demonstrations.

## How to capture (important)

These registers are A3 and ~17 columns wide — one photo of the whole spread is
too low-resolution to read. Capture **half a page at a time**:

1. Pick the register type and enter facility + page number.
2. Photograph the **left half** (IDs/demographics), then the **right half**
   (results). One half alone also works for a quick test.
3. Tap **Read this page** → review the table → correct any flagged cells →
   **Export to Excel/CSV**.

Cells the model is unsure about are colour-coded (amber = check, red = verify).
Editing a cell clears its flag. A row is highlighted red if it looks
smear-positive or MTB-detected.

## Adding more register types

Add an entry to `TEMPLATES` in `register_capture.py` with the column list for
that register (GeneXpert printout, spirometry report, chest X-ray/CAD). The
prompt and UI build themselves from the template.

## Data handling

With a key, page images are sent to the vision API for reading. For patient
data this carries Kenya Data Protection Act obligations (a Data Processing
Agreement, no-training guarantee, and program/governance sign-off). Patient
names are always returned as `[redacted]`. For production, plan a move to a
self-hosted / regional model to keep images in-country.
