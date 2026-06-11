# Register Digitizer

Vision-backed digitizer for handwritten TB lab registers (Kenya TB programme). Photograph a register page; an AI vision model reads each row into structured, reviewable data, and records are linked across the disconnected systems (microscopy, GeneXpert, chest X-ray/CAD, spirometry).

## Contents
- index.html - password-gated public demo (proof of concept; contains no patient-identifiable data).
- register_capture.py - vision-backed capture + review web app.
- app.py - earlier Tesseract baseline.
- templates/ - web UI.
- See REGISTER_CAPTURE_README.md to run.

## Data note
No patient data is committed. The demo image is blurred and phone numbers masked; .gitignore excludes uploads/ and exports/.
