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
VISION_MODEL      = os.environ.get("VISION_MODEL", "claude-sonnet-4-6")
MAX_IMG_DIM       = 2200          # downscale before upload (cost + speed)

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


def call_vision(images_b64: list[str], template_key: str) -> dict:
    """Send images to the vision model and parse structured rows."""
    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    content = [{"type": "image",
                "source": {"type": "base64", "media_type": "image/jpeg", "data": b}}
               for b in images_b64]
    content.append({"type": "text", "text": build_prompt(template_key)})
    msg = client.messages.create(
        model=VISION_MODEL,
        max_tokens=8000,
        messages=[{"role": "user", "content": content}],
    )
    text = "".join(b.text for b in msg.content if b.type == "text").strip()
    if text.startswith("```"):
        text = text.split("```")[1].lstrip("json").strip()
    return json.loads(text)


# ── Sample fallback (so the UI works with no API key) ───────────────────────
SAMPLE_ROWS = json.loads((BASE_DIR / "sample_rows.json").read_text()) \
    if (BASE_DIR / "sample_rows.json").exists() else {"rows": []}


# ── Routes ──────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("capture.html",
                           templates=TEMPLATES,
                           has_key=bool(ANTHROPIC_API_KEY),
                           model=VISION_MODEL)


@app.route("/api/extract", methods=["POST"])
def extract():
    template_key = request.form.get("template", "tb_lab_register")
    files = request.files.getlist("images")
    if template_key not in TEMPLATES:
        return jsonify({"error": "Unknown register type"}), 400

    if not ANTHROPIC_API_KEY:
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
    return jsonify({"status": "ok", "vision_key": bool(ANTHROPIC_API_KEY), "model": VISION_MODEL})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5060))
    print(f"\n  Register Capture → http://localhost:{port}")
    print(f"  Vision: {'ON ('+VISION_MODEL+')' if ANTHROPIC_API_KEY else 'OFF — demo/sample mode (set ANTHROPIC_API_KEY)'}\n")
    app.run(host="0.0.0.0", port=port, debug=False)
