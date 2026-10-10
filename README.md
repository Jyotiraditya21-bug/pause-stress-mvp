# Pause — stress check MVP

Phase 2: Local camera consent and preview, MediaPipe facial landmarks/blendshapes, provisional scan-quality feedback, and a 30-second feature sample. React/Vite, FastAPI, SQLite, and Gemini configuration are ready. Phase 3 adds questionnaire submission, SQLite persistence, results, and view/delete session actions. Phase 4 adds optional Gemini-selected guidance and local fallback suggestions. No trained stress prediction is enabled.

## Run locally

Backend (terminal 1, from this directory):

```sh
cd backend
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Frontend (terminal 2, from this directory):

```sh
cd frontend
npm install
npm run dev
```

Open the Vite local URL. API docs: http://127.0.0.1:8000/docs.

## Gemini setup

Copy `backend/.env.example` to `backend/.env`, then enter your Gemini API key locally in `GEMINI_API_KEY`. Do not paste credentials into chat or frontend code. The backend reports presence only; it does not test validity or make requests. The model defaults to gemini-3.8-flash and can be set with GEMINI_MODEL. Restart the backend after configuration; model access and key validity require a live test.

## Screen and result contract

- Overview: purpose, boundaries, system status.
- Check-in: consent and camera (Phase 2), questionnaire (Phase 3).
- Results: self-reported stress 0–10, experimental camera metrics, scan quality, guidance.
- History: dated sessions and trends (Phase 5).

SQLite is initialized on backend startup at `backend/sessions.sqlite3`. Sessions reserve an ID, UTC timestamp, self-reported rating, scan quality, camera metrics JSON, and guidance JSON. No raw video column is included. Storage is local and not encrypted; do not collect sensitive production data before implementing the later privacy controls.

## Next phases

2. Completed: camera permission, consent, MediaPipe feature extraction and quality checks.
3. Completed: questionnaire validation and save/delete session endpoints.
4. Implemented: Gemini structured guidance with output validation and fallback; live testing pending.
5. Results, trends and deletion UI.
6. Integration, failure and performance checks.

Camera signals must remain separate from reported stress. Any learned stress estimate needs labeled data and participant-separated evaluation before use.

## Camera scan

Open Check-in, agree to local processing, enable the camera, and start when framing is acceptable. Cancel, navigation, and scan completion stop camera tracks. A usable-frame ratio below 75% or fewer than 30 usable samples marks the scan poor and suppresses feature values. These provisional checks use scene brightness and face position; they do not validate stress accuracy. No raw video is recorded or transmitted; features remain in memory until Phase 3 storage is added. Model and WASM files are served locally from frontend/public/mediapipe.

## Questionnaire and storage

After scanning, answer the short self-report; or skip the camera. Choose current stress (0–10), sleep hours (0–24), workload, caffeine, and recent exercise. Explicit local-storage consent is required. This custom questionnaire is not a validated clinical scale. POST /api/sessions validates fields and returns the stored result; GET lists sessions; DELETE /api/sessions/{id} removes a session. History includes View and Delete. No authentication or encryption is implemented: keep the server bound to loopback and use this as a single-user local demo. A schema migration preserves existing session rows.

## AI guidance (Phase 4)

Save a check-in or select one from History. Results offers an explicit cloud consent checkbox and Get AI guidance. Only the stress rating, sleep hours, workload, caffeine and exercise answers are sent to Google. No video, camera metrics, session identifiers, timestamps or history are sent. Consent is not remembered for new requests. Local suggestions requires no cloud consent and makes no provider request.

Gemini selects 2–3 distinct actions and one focus from approved lists; the application constructs the summary and limitations. This avoids exposing free-form diagnoses or fabricated stress scores. Provider failure, invalid output, or missing credentials returns labeled local suggestions. The request timeout is 20 seconds; there is no automatic retry. Concurrent guidance requests are rejected with 409. Source, status, generation timestamp and cloud consent are saved with the session.

Protocol reference: https://ai.google.dev/api/generate-content and https://ai.google.dev/gemini-api/docs/structured-output . This integration has been tested with mocks; no live Gemini request has been verified.

Run backend guidance checks: `.venv/bin/python -m unittest test_guidance -v` from backend/.

## Phase 5 — Results and history

History charts the latest 20 self-reported ratings against recording timestamps. A collapsible exact-values table provides a text equivalent. Results display all questionnaire context and guidance source/time. Loading, save/delete notices, empty-state actions, and reconnect controls are included. No clinical interpretation is attached to the trend.

## Final demo handoff

Core MVP implementation is ready. See DEMO.md for camera-free and optional camera/Gemini walkthroughs. Model experiments are deferred at user request; no trained stress score is displayed. Run `.venv/bin/python -m unittest test_guidance test_sessions -v` from backend for isolated checks. Camera/model initialization cleanup, hidden-page camera shutdown, and duplicate form submission guards are included. Live camera and live Gemini testing remain pending.

## Current browser UI

The questionnaire rating flow has been replaced by a live, experimental facial behavior graph with 25-second calibration. See frontend/LIVE.md for the fixed rules, reversed scale, privacy and verification limits. This is not a validated stress measurement.
