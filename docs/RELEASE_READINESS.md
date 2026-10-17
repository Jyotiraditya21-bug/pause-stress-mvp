# Pause release readiness — 2026-10-17

## Release scope

Pause is a static, on-device experimental facial check-in. GitHub Pages serves the frontend, local MediaPipe model and WASM; it does not host FastAPI, collect camera video, or train a stress model. This release hardens software behavior and preserves the existing fixed formulas, thresholds and opt-in tolerance policy. It does not establish psychological stress accuracy.

## Implemented safeguards

- Standard scans measure a fixed ten-second capture after positioning. Frame timestamps come from the video clock; rejected/dropped intervals remain missing. The 25-second acquisition safety cap remains. Tolerant mode remains explicit `?tolerance=1`, 10–20 seconds, with adoption and 3-D switches off.
- Capture-clock metadata separates new results from historical acquisitions. Personal baselines have an identity; older baselines use their creation timestamp. Calibration navigation resets correctly and baseline expiry is rechecked on return to Scan.
- Saved records are validated before rendering. Damaged records cannot crash History; reading never overwrites the original. Recovery requires a user action and a successful local backup before rewriting valid records. Backup deletion is separate from normal History deletion and documented in Privacy/Settings.
- Trends group by source, algorithm, acquisition version and baseline identity, exclude calibration scans and use actual date spacing. Older personalized results lacking identity are not joined together.
- UI retains the light palette and layout, with larger desktop presentation, feature information, non-diagnostic wording, reduced-motion support and explicit experimental-mode/duration notes.
- The historical API rejects non-loopback clients, non-local Host headers and non-local Origins. Requests are capped at 64 KiB and 120/minute per process, guidance at 6/minute, and session reads at 100 rows with an offset. SQLite transactions explicitly close their connections and roll back failures. This is not authentication: do not expose this API through a public reverse proxy. Multi-user accounts/ownership are outside the deployed static product.

## Verification

- 40 frontend unit tests and production PWA build passed.
- 18 Chromium browser checks, 6 WebKit UI checks and the separate offline PWA check passed. These use synthetic records/fake camera input; no participant footage or saved personal sessions were used.
- 9 isolated backend tests passed, including local boundary, rate/body limits, consent validation, pagination, rollback and connection closure.
- JavaScript/Python strict and tolerant parity passed within `1e-6`; the strict fixture now includes rejected intervals and dropped frames.
- Production npm audit reported zero known advisories at the time of checking; this is not a complete security audit.
- CI explicitly runs backend, frontend and research tests. Pages waits for Chromium, WebKit and offline checks before publishing.

## Evidence still required

Automated WebKit checks do not replace camera permission, interruptions, thermal performance and camera rendering tests on physical Safari/iPhone devices. Repeatability, nuisance sensitivity, participant-separated task discrimination and skin-tone/lighting effects remain unestablished without real participant evaluation. Keep all accuracy and clinical claims disabled. Do not interpret limited-confidence ranges as statistical confidence in a person's stress level.

Before expanding beyond the experimental static MVP, collect consented repeat sessions and run the existing fixed evaluation protocols. Do not tune the formula on the held-out evaluation data or force scans to match a previous score.
