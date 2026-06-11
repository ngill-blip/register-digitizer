# Form Digitizer — Project Context

## What this is
A near-production web app for digitizing paper forms using open-source OCR. Built for CHAI (Clinton Health Access Initiative) for field use in India, Kenya, Zimbabwe and South Africa. Currently being tested with TB treatment forms (National TB Elimination Programme, India — mixed Hindi/English, handwritten).

## Tech stack
- **Backend**: Python Flask + OpenCV (preprocessing) + Tesseract OCR + langdetect
- **Frontend**: Single mobile-first HTML page (no framework)
- **Export**: openpyxl (Excel) + csv
- **Tunnel**: ngrok (permanent domain: `curled-routine-disarray.ngrok-free.dev`)

## File locations
All files live at: `~/Desktop/Claude (DND)/form-digitizer/`
Exports saved permanently to: `~/Desktop/Claude (DND)/Form Exports/`

```
form-digitizer/
├── app.py                      # Flask backend
├── run.sh                      # One-command setup & launch
├── START.command                # Double-click launcher (Mac)
├── requirements.txt
└── templates/
    ├── index.html               # Mobile-first scan UI
    └── exports.html             # Admin exports dashboard
```

## How to run
```bash
# Option 1: Double-click START.command on Desktop → Claude (DND) → form-digitizer
# Option 2: Manual
bash ~/Desktop/Claude\ \(DND\)/form-digitizer/run.sh          # Tab 1
ngrok http --domain=curled-routine-disarray.ngrok-free.dev 5050  # Tab 2
```

## Key features built

### Backend (app.py)
- **Image preprocessing pipeline**: EXIF rotation fix → deskew (Hough transform) → denoise → CLAHE contrast → adaptive threshold
- **Two-pass OCR**: Pass 1 English → langdetect → Pass 2 with correct language pack
- **Language support**: English, Hindi (`hin`), Urdu (`urd`), Swahili (`swa`), Zulu (`zul`), Xhosa (`xho`), Afrikaans (`afr`), Shona (`sna`), Ndebele (`nde`), French (`fra`), Portuguese (`por`)
- **Field extraction heuristics**: colon patterns, blank-fill lines, checkboxes, two-column layouts
- **Auto-save on every scan**: saves Excel to `~/Desktop/Claude (DND)/Form Exports/` the moment OCR completes — regardless of whether user clicks download
- **Routes**: `GET /`, `POST /api/process`, `POST /api/export`, `GET /exports`, `GET /exports/download/<file>`, `POST /exports/delete/<file>`, `GET /api/health`
- **Export filenames**: auto-saved use pattern `YYYY-MM-DD_HH-MM-SS_<uid8>.xlsx`; manual downloads use `<timestamp>_<name>.<fmt>`

### Frontend (index.html)
- **Live camera overlay**: `getUserMedia` camera with A4 document frame, corner bracket markers, rule-of-thirds grid, pulsing green alignment cue, crops image to frame on capture, falls back to native file input if camera API unavailable
- **Mobile-first layout**: full-screen hero camera button, card-based field review (no tables), sticky bottom bar
- **Bottom bar**: "Save & Scan Next" (green) + "Excel" (blue) — always visible
- **Scan Next FAB**: bouncing green button after results, resets to camera instantly
- **Inline editing**: tap any field value to edit before export
- **Language badge**: shows detected language (e.g. "🌐 Hindi") after extraction

### Exports dashboard (/exports)
- Shows all scans with timestamp, auto-saved vs manually downloaded badge
- Download or delete individual files
- Stats: total scans, auto-saved count, downloaded count
- Reads from permanent folder — survives app reinstalls/updates

## What still needs work (known gaps)
- Handwriting accuracy is ~85-95% — human review step is essential
- Tesseract struggles with very dense Hindi Devanagari on poor-quality photos
- No authentication — anyone with the ngrok URL can access it
- No multi-page form support (only first page of PDFs processed)
- Field extraction heuristics tuned for simple forms — complex tabular forms (like the TB NAAT lab form) may need template-specific rules
- ngrok only works while laptop is running — for always-on deployment, consider Railway/Render

## Production hardening checklist (not done yet)
- [ ] Add simple password or token-based auth
- [ ] Deploy to Railway/Render for always-on access
- [ ] Add multi-page PDF support
- [ ] Build template-specific extractors for known form types (TB treatment card, NAAT form, etc.)
- [ ] Add a "flag for review" button on low-confidence fields
- [ ] Store exports to Google Drive / S3 instead of local disk
