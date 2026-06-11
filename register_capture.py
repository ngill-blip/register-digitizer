"""
Register Capture — vision-backed digitizer for handwritten TB registers.

A focused upgrade over the Tesseract pipeline: instead of OCR + heuristics,
it sends each register photo to a cloud vision model with a TEMPLATE that
defines the exact columns of the register, and gets back clean structured
rows with a confidence score per cell.

Run:
    pip install -r requirements.txt
    export ANTHROPIC_API_KEY=sk-ant-...        # optional; without it, demo data is returned
    python register_capture.py
    open http://localhost:5060

Without an API key the /api/extract endpoint returns bundled SAMPLE rows,
so the whole capture + review UI is usable offline for demos.
"""

import os
import io
import csv
import json
import base64
from pathlib import Path
from datetime import datetime

from flask import Flask, request, jsonify, render_template, send_file
from PIL import Image, ImageOps

# ── Config ────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent
EXPORT_DIR = Path.home() / "Desktop" / "Claude (DND)" / "Form Exports"
try:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
except OSError:
    EXPORT_DIR = BASE_DIR / "exports"; EXPORT_DIR.mkdir(exist_ok=True)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
GEMINI_API_KEY    = os.environ.get("GEMINI_API_KEY", "").strip()   # FREE tier: aistudio.google.com/apikey
# Fallback: read a saved key file so a plain double-click launch works (no Terminal export needed).
if not GEMINI_API_KEY and (BASE_DIR / "gemini_key.txt").exists():
    GEMINI_API_KEY = (BASE_DIR / "gemini_key.txt").read_text().strip()
ANTHROPIC_MODEL   = os.environ.get("VISION_MODEL", "claude-sonnet-4-6")
GEMINI_MODEL      = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
MAX_IMG_DIM       = 2200          # downscale before upload (cost + speed)

# Prefer the free Gemini tier if its key is present, else Anthropic, else sample mode.
if GEMINI_API_KEY:
    PROVIDER, MODEL_NAME = "gemini", GEMINI_MODEL
elif ANTHROPIC_API_KEY:
    PROVIDER, MODEL_NAME = "anthropic", ANTHROPIC_MODEL
else:
    PROVIDER, MODEL_NAME = None, "sample"
HAS_KEY = PROVIDER is not None

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024

# ── Register templates ──────────────────────────────────────────────────────
# Each template lists the columns of a specific register. Add new registers
# (GeneXpert printout, spirometry, chest X-ray/CAD) by adding a TEMPLATE here.
TEMPLATES = {
    "tb_lab_register": {
        "label": "Presumptive TB / Microscopy / GeneXpert register",
        "columns": [
            ("date_collected",     "Date sample collected"),
            ("date_received",      "Date sample received & time in"),
            ("lab_no",             "Lab S/No"),
            ("name",               "Name (3 names) — REDACT to '[redacted]'"),
            ("tb_reg_no",          "TB Registration No. (for follow ups)"),
            ("sex",                "Sex (M/F)"),
            ("age",                "Age (years)"),
            ("patient_id_nemis",   "Patient ID No. / NEMIS"),
            ("address",            "Patient physical address"),
            ("phone",              "Patient/guardian phone number"),
            ("referring_facility", "Name of referring facility / department"),
            ("type_of_patient",    "Type of patient (P=Presumptive, N=New, F/Up=Follow-up)"),
            ("hiv_status",         "HIV status (Pos / Neg / ND)"),
            ("sample_appearance",  "Sample appearance (S=Saliva, M=Muco-purulent, B=Blood-stained)"),
            ("microscopy_result",  "Microscopy result ZN/FM (0=No AFB, scanty, 1+, 2+, 3+)"),
            ("tb_lamp",            "TB-LAMP (Pos/Neg/Invalid)"),
            ("lf_lam",             "LF-LAM (Pos/Neg/Invalid)"),
            ("genexpert_result",   "GeneXpert/TrueNat/XDR result (MTB detected/not detected; RIF)"),
            ("type_of_test",       "Type of test"),
            ("date_tested",        "Date tested"),
            ("time_out",           "Time out (results dispatch)"),
            ("tat",                "TAT (turn-around time)"),
            ("lab_officer",        "Laboratory officer's initials"),
            ("remarks",            "Remarks"),
        ],
    },
}

def build_prompt(template_key: str) -> str:
    t = TEMPLATES[template_key]
    cols = "\n".join(f'  - "{k}": {desc}' for k, desc in t["columns"])
    keys = [k for k, _ in t["columns"]]
    return f"""You are digitizing a photo of a handwritten Kenyan TB laboratory register
("{t['label']}"). The page is a ruled table; each data row is one patient/sample.

Extract EVERY data row you can see. For each row output an object whose keys are
exactly these column ids:
{cols}

Rules:
- Patient names are confidential: always output "[redacted]" for the "name" field.
- For every field, give BOTH the value and your confidence: "high", "medium" or "low".
- If a cell is blank, use value "" with confidence "high".
- Preserve codes exactly as written (e.g. "0", "1+", "ND", "MTB not detected", "F/up").
- Do not invent rows or values. Only transcribe what is visibly written.

Return STRICT JSON only, no prose, in this shape:
{{"rows": [ {{ {", ".join(f'"{k}": {{"v": "...", "c": "high"}}' for k in keys[:3])}, ... }} ]}}"""


# ── Image helpers ─────────────────────────────────────────────────────────
def prep_image(file_storage) -> str:
    """EXIF-rotate, downscale, return base64 JPEG."""
    im = Image.open(file_storage.stream)
    im = ImageOps.exif_transpose(im)
    w, h = im.size
    if max(w, h) > MAX_IMG_DIM:
        s = MAX_IMG_DIM / max(w, h)
        im = im.resize((int(w * s), int(h * s)), Image.LANCZOS)
    buf = io.BytesIO()
    im.convert("RGB").save(buf, "JPEG", quality=82)
    return base64.b64encode(buf.getvalue()).decode()


def _parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.lstrip().startswith("json"):
            text = text.lstrip()[4:]
    return json.loads(text.strip())


def _ssl_context():
    """Use certifi's CA bundle — avoids macOS 'CERTIFICATE_VERIFY_FAILED' with python.org builds."""
    import ssl
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def call_gemini(images_b64: list[str], template_key: str) -> dict:
    """FREE tier (Google AI Studio). Reads via the Gemini REST API, with 429 backoff."""
    import urllib.request, urllib.error, time
    parts = [{"inline_data": {"mime_type": "image/jpeg", "data": b}} for b in images_b64]
    parts.append({"text": build_prompt(template_key)})
    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {"maxOutputTokens": 8192, "responseMimeType": "application/json"},
    }
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}")
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=120, context=_ssl_context()) as r:
                data = json.loads(r.read().decode())
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            return _parse_json(text)
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 3:
                time.sleep(6 * (attempt + 1))   # free-tier per-minute limit — wait and retry
                continue
            if e.code == 429:
                raise RuntimeError("Free-tier rate limit reached. Wait ~60s and retry, "
                                   "or enable billing on the API key for higher limits.")
            raise


def call_anthropic(images_b64: list[str], template_key: str) -> dict:
    """Paid (no-training tier available). Best handwriting accuracy."""
    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    content = [{"type": "image",
                "source": {"type": "base64", "media_type": "image/jpeg", "data": b}}
               for b in images_b64]
    content.append({"type": "text", "text": build_prompt(template_key)})
    msg = client.messages.create(
        model=ANTHROPIC_MODEL, max_tokens=8000,
        messages=[{"role": "user", "content": content}],
    )
    text = "".join(b.text for b in msg.content if b.type == "text")
    return _parse_json(text)


def call_vision(images_b64: list[str], template_key: str) -> dict:
    """Dispatch to whichever provider has a key (free Gemini preferred)."""
    if PROVIDER == "gemini":
        return call_gemini(images_b64, template_key)
    return call_anthropic(images_b64, template_key)


# ── Sample fallback (so the UI works with no API key) ───────────────────────
SAMPLE_ROWS = json.loads((BASE_DIR / "sample_rows.json").read_text()) \
    if (BASE_DIR / "sample_rows.json").exists() else {"rows": []}


# ── Routes ──────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("capture.html",
                           templates=TEMPLATES,
                           has_key=HAS_KEY,
                           model=MODEL_NAME)


@app.route("/api/extract", methods=["POST"])
def extract():
    template_key = request.form.get("template", "tb_lab_register")
    files = request.files.getlist("images")
    if template_key not in TEMPLATES:
        return jsonify({"error": "Unknown register type"}), 400

    if not HAS_KEY:
        # Demo mode — return bundled sample so the UI is fully usable offline.
        return jsonify({"mode": "sample",
                        "columns": TEMPLATES[template_key]["columns"],
                        **SAMPLE_ROWS})

    if not files:
        return jsonify({"error": "No images uploaded"}), 400
    try:
        imgs = [prep_image(f) for f in files]
        result = call_vision(imgs, template_key)
        result["mode"] = "vision"
        result["columns"] = TEMPLATES[template_key]["columns"]
        return jsonify(result)
    except Exception as e:
        app.logger.exception("extract failed")
        return jsonify({"error": str(e)}), 500


@app.route("/api/export", methods=["POST"])
def export():
    body = request.get_json(force=True)
    rows = body.get("rows", [])
    cols = body.get("columns", [])
    if not rows:
        return jsonify({"error": "No rows"}), 400
    keys   = [c[0] for c in cols] or list(rows[0].keys())
    labels = {c[0]: c[1] for c in cols}
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow([labels.get(k, k) for k in keys])
    for r in rows:
        w.writerow([(r.get(k) or {}).get("v", "") if isinstance(r.get(k), dict) else r.get(k, "") for k in keys])
    data = out.getvalue().encode("utf-8-sig")
    fn = f"{datetime.now():%Y%m%d_%H%M%S}_register.csv"
    (EXPORT_DIR / fn).write_bytes(data)
    return send_file(io.BytesIO(data), mimetype="text/csv",
                     as_attachment=True, download_name=fn)


@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "vision_key": HAS_KEY,
                    "provider": PROVIDER or "none", "model": MODEL_NAME})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5060))
    print(f"\n  Register Capture → http://localhost:{port}")
    if HAS_KEY:
        print(f"  Vision: ON — {PROVIDER} ({MODEL_NAME})\n")
    else:
        print("  Vision: OFF — demo/sample mode.")
        print("  Free live reading: set GEMINI_API_KEY (free at aistudio.google.com/apikey)\n")
    app.run(host="0.0.0.0", port=port, debug=False)
