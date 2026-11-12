# Pause update log — 12 November 2026

## Published update

- **Live site:** [Pause · Calm index](https://jyotiraditya21-bug.github.io/pause-stress-mvp/)
- **Release commit:** `87504d33d7be0bed54d196f92c7f6c955bb45518`
- **GitHub Actions release:** [Deploy Pages demo run](https://github.com/Jyotiraditya21-bug/pause-stress-mvp/actions/runs/43199304658)
- **Status:** Pages deployment and final live smoke check passed.

## What changed

- Added a small-screen navigation hint, “Scroll for more,” which disappears after the visitor reaches the end of the navigation row.
- Reduced the app shell’s precache from about **42.6 MB** to about **704 KB**. MediaPipe files are cached after first use; optional neural-model and ONNX files are cached after first enabled use.
- Kept the existing neural-model default enabled and respected the saved opt-out setting.
- Updated offline test instructions: load the app online and warm MediaPipe once before expecting an offline scan to initialize.
- Updated the live smoke test to accept the History delete confirmation and to warm MediaPipe before its offline check.
- Updated README, device acceptance guidance, and the task log to reflect the new cache behavior.

## Verification

- Frontend unit tests: **63 passed**.
- Chromium end-to-end checks: **33 passed**, one offline-only test intentionally skipped in the regular suite.
- WebKit readiness checks: **14 passed**.
- Dedicated offline PWA check: **passed**.
- Lighthouse: **0.96 performance**, **1.00 accessibility**, **1.00 best practices**, **1.00 SEO**.
- Production build: **passed**.
- Final live smoke: **passed**, including the release version check, synthetic scan flow, History export/delete, 360 px layout, and offline initialization.

## Scope and limits

No stress-scoring formula or scientific claim changed in this update. Camera processing remains experimental and is not a diagnosis or validated stress measurement. The live smoke used a synthetic record and fake camera; real-camera testing on physical iPhone, Android, and Safari devices remains outstanding.
