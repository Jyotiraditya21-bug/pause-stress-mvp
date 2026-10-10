# Pause MVP demo

## Start

Follow README.md to run FastAPI on 127.0.0.1:8000 and Vite on 127.0.0.1:5173. If both are already running, reuse them.

## Demo without a camera or API key

1. Open http://127.0.0.1:5173/ and choose Check-in.
2. Choose Skip camera → answer questions.
3. Enter your rating and context. Read and accept local-storage consent if appropriate.
4. Save the check-in. Results show your rating and context separately from camera signals.
5. Choose Use local suggestions. It makes no cloud request and is clearly labeled non-AI.
6. Open History, review the trend/table, and select View.
7. Reload: history remains in SQLite. Delete only sessions you wish to remove; the UI asks for confirmation.

## Camera route

Enable camera only after consent. Allow browser camera permission, position your face, and start the 30-second scan when quality is acceptable. The camera stops when the scan finishes, on cancellation/navigation, or when the page is hidden. Poor scans suppress feature values. Complete the questionnaire afterward. Real camera behavior still needs a test on the user's Mac.

## Optional Gemini route

Configure backend/.env privately and restart the backend. Select a saved check-in and explicitly opt in to sending questionnaire fields to Google; then select Get AI guidance. No raw video/facial metrics are sent. Failed requests return labeled local suggestions. Live key/model access has not been verified.

## Boundaries

This is a single-user local demo, with unencrypted SQLite storage and no login. Self-reported stress is not an AI measurement. Facial coefficients are experimental observations, not stress levels. No trained predictor or accuracy claim is included. Model training/testing is deferred.

## Verification

Frontend: npm run build in frontend/. Backend: .venv/bin/python -m unittest test_guidance test_sessions -v in backend/. Five backend checks passed; production build passed. Narrow-screen overflow and basic keyboard focus checked. Live camera, full keyboard journey, and live Gemini remain unverified.
