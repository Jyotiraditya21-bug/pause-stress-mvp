# Agent instructions — Pause MVP

## Scope

This project is a local, single-user wellbeing demo for a MacBook Air M1. The user authorized completion of the core MVP phases and deferred model training/testing on 2026-10-10. Do not resume dataset/model work unless requested. The user authorized GitHub Pages deployment; publish only the prepared frontend demo, never secrets or session databases.

Read TASKS.md for completed work, remaining tasks, and verification gaps. Update it after meaningful changes. User instructions take precedence over these project conventions.

## Architecture

- frontend/: React, Vite, JavaScript, and CSS.
- frontend/src/CameraScan.jsx: camera consent, MediaPipe processing, and lifecycle cleanup.
- frontend/src/scanMetrics.js: provisional frame-quality checks and feature summaries.
- frontend/src/Questionnaire.jsx: self-report form and saving.
- frontend/src/main.jsx: navigation, results, history, and backend status.
- frontend/public/mediapipe/: local pretrained model and WASM assets.
- backend/main.py: FastAPI, validated request models, SQLite migration, and session APIs.
- backend/requirements.txt: Python dependencies.
- backend/.env.example: configuration template only.

Preserve the existing stack. Gemini is the chosen guidance provider. No trained stress predictor is enabled. The user authorized a browser port of the fixed, unvalidated mathematical facial index and removal of the questionnaire rating from the current UI. Keep its experimental status and personal-baseline interpretation explicit.

## Product and scientific boundaries

- Keep self-reported stress, camera features, and AI guidance clearly separate.
- Do not translate facial coefficients into stress scores using arbitrary formulas.
- Do not describe blendshape coefficients as actual muscle tension or blink rate.
- Do not claim validated accuracy, diagnosis, burnout prediction, or physiological stress measurement without supporting evaluation.
- Treat scan-quality thresholds as provisional engineering checks.
- Keep poor-quality feature values suppressed in the UI.
- The short questionnaire is a custom self-report, not a standardized clinical assessment.
- An LLM may explain available information and suggest wellbeing actions; it must not create diagnoses or stress measurements.

## Privacy and credentials

- Require explicit consent before camera processing and local saving.
- Keep raw camera frames/video in browser memory; do not record, upload, or persist them by default.
- Stop camera tracks and dispose of MediaPipe on cancellation, unmount, completion, and failures.
- Before adding cloud guidance, show which information is sent to Google and require an explicit opt-in.
- Keep Gemini keys in backend/.env or server environment variables. Never print keys, copy them into chat, or bundle them into frontend code.
- Check credential presence using redacted checks only. Do not read secret-bearing files into ordinary tool output.
- Keep .env, databases, virtual environments, build outputs, and node_modules ignored.
- SQLite currently has no encryption or authentication. Keep servers bound to 127.0.0.1; do not expose them to the network as a production service.
- Use synthetic test data and clean up only the test records you created. Preserve existing user sessions.

## Development and verification

Run frontend commands from frontend/:

```sh
npm install
npm run dev
npm run build
```

Run backend commands from backend/:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Frontend preview: http://127.0.0.1:5173/. Vite proxies /api to port 8000. Backend changes require restarting uvicorn unless reload is enabled. Reuse running servers when possible; do not stop unrelated processes.

- Run the production frontend build after frontend changes.
- Validate backend bounds, consent enforcement, and persistence for API changes.
- Use participant-separated evaluation for future model experiments; never randomly split frames from the same person across train/test.
- Treat successful builds and API tests as distinct from real webcam/browser testing.
- Test cancellation and navigation while camera/model initialization is pending.
- Handle unavailable cameras, denied permission, poor scans, network failures, and invalid API responses clearly.
- Preserve accessible labels, keyboard interaction, responsive layout, and the established visual style.
- Document material limitations candidly in README.md and TASKS.md.

## Handoff

Report what changed, what was actually verified, what remains unverified, and the next phase. Keep progress updates concise. Do not request credentials in chat; direct the user to configure them privately when needed.
