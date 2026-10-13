# MVP task tracker

Last updated: 2026-10-13

## Current scope and status — 2026-10-13

Current MVP: a production-ready, deployed PWA featuring a 10-second on-device camera scan that outputs an experimental Calm index (0-10, higher = calmer) with personal-baseline support, MAD spread bounds, and strict privacy guarantees. Merged into `main` and deployed live to GitHub Pages.

### Completed — Production hardening & deployment (2026-10-13)

1. **Step 1: Hardened scan logic & personal baselines**:
   - Switched default generic reference to 3 robust facial features (`brow_furrow`, `lip_press`, `lip_corner`) with `jaw_clenching` isolated to exploratory diagnostics.
   - Built optional personal baseline mode (`pause.baseline.v1`) stored strictly in localStorage.
   - Replaced pseudo-confidence intervals with median absolute deviation (MAD) spread bounds.
   - Cleaned up state machine with 10-second countdown and 60% valid-frame gate.
   - Full Python parity mirror (`stress_math/deployed_mirror.py`) verified against browser scoring.
2. **Step 2: Calm UI redesign**:
   - Replaced busy developer graph with calm, accessible UI (`pause-ui.css`).
   - Integrated `ResultCard`, `ScanScreen`, `HistoryPage`, and `InfoPage` with subtle motion, dark mode support, and WCAG AA contrast.
3. **Step 3: PWA offline support, monitoring stubs, & CI automation**:
   - Configured `vite-plugin-pwa` with offline caching of app shell and MediaPipe model.
   - Hardened Content Security Policy (CSP) headers and added Sentry/Plausible telemetry stubs.
   - Added Playwright end-to-end tests (`frontend/e2e/pause.spec.js`) with `@axe-core/playwright` accessibility audits.
   - Added mobile Lighthouse CI configuration (`lighthouserc.json`) achieving Performance: 99, Accessibility: 94, Best Practices: 100, SEO: 91.
4. **Step 4: Honest Calm index documentation & claims**:
   - Updated `README.md` and `docs/VALIDATION_TODO.md` to ensure zero clinical or physiological stress claims are made.
5. **Merge & Live Deployment**:
   - Fast-forward merged `prod-hardening` into `main` and pushed to `origin/main`.
   - GitHub Actions workflow run [#38369855652](https://github.com/Jyotiraditya21-bug/pause-stress-mvp/actions/runs/38369855652) completed green across `deploy`, `e2e`, and `lighthouse` jobs.
   - Live GitHub Pages site at https://jyotiraditya21-bug.github.io/pause-stress-mvp/ verified active and delivering production assets.

### Remaining — 3 groups (inputs or controlled tests required)

1. Obtain authorized labeled rest/stressor videos or explicit consent for local recorded sessions, then run actual M0–M5 comparisons/accuracy/CIs/permutations and optional AU validation. No labeled videos are available locally. The browser check-ins were not recorded and do not supply this protocol.
2. Controlled low-light/glasses/yaw/multiple-face and denied/busy camera checks; actual tab-background and five-minute automatic-stop checks. Synthetic quality/pose and resource handling tests are distinct from these physical conditions.
3. Broader CPU/memory/multi-device characterization. Real frame-rate/latency and one synthetic pretrained-backend memory/latency benchmark are complete; per-tab CPU/memory isolation and larger-session measurements are not.

Optional/out of current scope: re-enable/test Gemini guidance with credentials. No training or fine-tuning is planned.

The sections below retain earlier implementation history and may include superseded UI milestones.

## Phase 1 — Foundation: completed

- [x] Set up React/Vite frontend and FastAPI backend.
- [x] Create Overview, Check-in, Results, and History screens.
- [x] Initialize SQLite session storage.
- [x] Define result and session fields.
- [x] Add private Gemini environment configuration template and key-presence status.
- [x] Install dependencies and verify frontend build and API startup.
- [ ] Configure a real Gemini API key locally; presence does not establish validity.

## Phase 2 — Camera analysis: implemented, live testing pending

- [x] Require consent before enabling camera processing.
- [x] Implement live preview and local MediaPipe landmarks/blendshapes.
- [x] Serve model and WASM assets locally.
- [x] Add provisional brightness, framing, movement, and multiple-face checks.
- [x] Implement 30-second feature sampling and usable-frame summary.
- [x] Suppress feature values for poor scans in the results UI.
- [x] Stop camera tracks on cancellation, navigation, and scan completion.
- [x] Verify build and quality/summary calculations with synthetic inputs.
- [ ] Test real camera permission, model loading, full scan, and camera shutdown on the Mac.
- [ ] Test poor lighting, motion, multiple faces, denied permissions, and busy camera.
- [ ] Benchmark frame rate, responsiveness, and CPU/memory on M1.

No video is recorded or uploaded. Sampled coefficients are not validated stress measurements, blink rates, or muscle tension.

## Phase 3 — Questionnaire and persistence: completed

- [x] Add current stress rating, sleep hours, workload, caffeine, and recent exercise fields.
- [x] Allow camera-free check-ins.
- [x] Require local storage consent.
- [x] Validate request fields in the backend.
- [x] Add create/list/delete session APIs and migrate existing SQLite schema.
- [x] Display saved results and history with View/Delete controls.
- [x] Verify invalid-input rejection and create/read/delete flow using disposable synthetic data.
- [x] Inspect questionnaire UI in browser; verify frontend build.
- [x] Verify browser form submission and local guidance display with synthetic inputs.
- [ ] Verify reload persistence and browser deletion interaction.

The questionnaire is a custom self-report, not a validated clinical scale. Storage has no authentication or encryption; run only as a single-user loopback demo.

## Phase 4 — AI guidance: implemented; credentials and live verification pending

- [ ] Configure Gemini credentials securely in backend/.env.
- [x] Confirm current generateContent structured-output contract; default to configurable gemini-3.8-flash. Model access remains unverified without credentials.
- [x] Add explicit user consent describing which session fields are sent to Google.
- [x] Send only necessary structured questionnaire/context data; keep raw video local.
- [x] Implement server-side Gemini requests; keep credentials out of frontend bundles and logs.
- [x] Validate structured output: summary, suggested actions, and limitations.
- [x] Prevent prompts/output from inventing stress scores or diagnoses.
- [x] Add timeouts, failure handling, retry controls, and clearly labeled non-AI fallback guidance.
- [x] Integrate guidance into results and persist its source/status.
- [x] Mock provider success, malformed responses, missing keys, timeouts, rate limits, and no-consent behavior.
- [x] Verify local guidance API persistence and browser result display; synthetic test records removed.
- [ ] Verify a live Gemini request with configured credentials and authorized data.

## Phase 5 — Results and history polish: implemented

- [x] Display reported stress separately from experimental camera metrics.
- [x] List dated sessions and provide view/delete actions.
- [x] Add self-reported stress trend chart with accessible text equivalent.
- [x] Improve empty, loading, saved, and error states.
- [x] Display complete questionnaire context and guidance source.
- [ ] Complete browser mobile and keyboard verification.
- [x] Verify trend rendering for empty, single, multiple, and more than 20 sessions.

## Phase 6 — Final verification and demo handoff: core checks completed; live checks noted

- [ ] Complete real-camera and full browser journey tests.
- [ ] Test backend outage, Gemini outage, malformed output, and repeat submission.
- [x] Review privacy boundaries, consent, deletion, and secret handling.
- [x] Source review: no raw camera upload, MediaRecorder, or persisted video path; local MediaPipe assets and no external font request.
- [ ] Verify live-camera network behavior during a real scan.
- [x] Verify build and API checks after final changes.
- [x] Update README with startup instructions and known limitations.
- [x] Prepare reproducible demo and screenshots without personal data.

## Phase 7 — Model research: deferred by user (2026-10-10)

- [ ] Obtain appropriately licensed labeled data; resolve commercial-use rights.
- [x] Prepare participant-separated half-training/half-testing pipeline with inner group cross-validation.
- [ ] Verify UBFC task labels and extract matching browser features.
- [ ] Train a lightweight classifier and compare against simple baselines.
- [ ] Report recall, precision, balanced accuracy, calibration, subgroup results, and confidence intervals.
- [ ] Add experimental predictions only if supported by evaluation.

## Working locations

- Frontend: frontend/
- Backend: backend/main.py
- Local database: backend/sessions.sqlite3 (ignored)
- Credential template: backend/.env.example
- Setup and behavior documentation: README.md
- Agent instructions: AGENTS.md

Update this checklist after each phase. Distinguish implementation from live verification; do not mark untested behavior as verified.

### Dataset acquisition status

UBFC-Phys selected as a camera-compatible candidate. Official downloads require authorized access; raw recordings exceed available internal disk space (about 2.4 GiB at inspection). training/train.py and training/README.md prepared; only Python syntax checked, dependencies not installed and no real-data training run. Need external storage/compute or an authorized compact feature table before training. Published paper accuracy is not app accuracy.

### Colab deliverable

- [x] Create training/Pause_training.ipynb with installation, Drive checkpointing, reviewed-label gates, extraction, training and compact export.
- [x] Add training/extract.py matching the current app feature definitions and provisional quality rules.
- [x] Validate notebook JSON and Python cell/script syntax.
- [ ] Obtain authorized data and validate labels/licence.
- [ ] Execute notebook on real recordings in Colab and verify resume behavior.
- [ ] Validate Python/browser feature parity and assess reported test metrics.
- [ ] Integrate the learned artifact only after reviewing actual results.

Notebook preparation completes the training deliverable, not actual training or Phase 6 live verification.

## Final MVP handoff

User deferred all model training/testing. No learned stress score is enabled. Final production frontend build and five backend checks passed (isolated session lifecycle/validation and mocked guidance behavior). Checked the running interface at 493px with no horizontal overflow and verified Tab reaches the brand link. Full keyboard journey and populated-chart mobile testing remain unverified. Camera initialization now stops cleanly across asynchronous cancellation; hiding the page also stops the camera. Form duplicate submission is guarded.

Live webcam verification and live Gemini verification remain pending; they are not blockers to using the questionnaire/local-guidance demo. Current server status reports Gemini key not configured. See DEMO.md for the reproducible walkthrough.

## GitHub Pages deployment

- [x] Fix Vite and MediaPipe paths for repository subpaths.
- [x] Add optional browser-only storage/local guidance mode; local FastAPI mode preserved.
- [x] Add Pages Actions workflow and verify browser-mode production build.
- [x] Authenticate GitHub; create Jyotiraditya21-bug/pause-stress-mvp.
- [x] Push frontend-only source, enable Pages, verify successful deployment and live HTML.

## Training-free experiment publication

- [x] Add separate stress_math experiment with fixed sigma floor, baseline comparisons, coverage exclusions and primary bootstrap metrics. Nine synthetic tests passed.
- [x] Prepare Pages Experiment tab linking code, guide and a source-only download. Python execution remains local.
- [x] Verify source-only archive, upstream license inclusion, and browser-mode production build.
- [x] Verify successful Pages deployment of commit 54aa59b (workflow 38065333465).

## Live browser graph — 2026-10-10

- [x] Remove questionnaire/self-reported rating from the current UI.
- [x] Port the fixed geometry-only index and sigma floor to JavaScript, with 25-second calibration and reversed (100-S)/10 scale.
- [x] Add live graph, unavailable-frame gaps, session review and consented graph-only browser persistence. Preserve older records.
- [x] Stop camera on cancel, finish, navigation, hide, error and five-minute limit.
- [x] Pass six Node tests, synthetic Python/JS feature/score parity and graph rendering checks; production build passed.
- [x] Inspect browser UI: no stress-rating input; camera disabled before consent; no desktop horizontal overflow.
- [ ] Verify real webcam operation and real-dataset accuracy.
- [x] Deploy live-graph update (20145ca) to GitHub Pages; workflow succeeded and published Live UI verified.

## Pretrained comparators extension — 2026-10-10

- [x] Create `stress_math/hf_models.py` with Model A (`TheBgGirl/fer-stress-vit`) and Model B (`HardlyHumans/Facial-expression-detection`) using dynamic `id2label` matching.
- [x] Implement face cropping (+15% margin), 5fps sampling, batch inference on `mps`/`cpu`, `torch.no_grad()`, fp32, and fingerprint-based score caching.
- [x] Create `stress_math/hf_evaluate.py` comparing M0 (math), M1 (Model A), M2 (Model B), M3 (M0+M1+M2 fusion), M4 (M0+M1 fusion), and M5 (M0+M2 fusion) with fixed equal weights and z-score baseline calibration.
- [x] Report ROC-AUC [95% CI], Cohen's d_z, Wilcoxon p, coverage %, ms/frame, param counts, paired AUC differences vs M0, and Spearman score correlations.
- [x] Include mandatory disclaimers in `report.md` regarding third-party pretrained status, undocumented UBFC-Phys splits, non-stress emotion probabilities, and fixed equal fusion weights.
- [x] Implement recording model names, resolved revision hashes, and available license text in comparator metrics output.
- [ ] Generate actual comparator report/model metadata; the existing metrics.json is the zero-session math report.
- [x] Update `stress_math/requirements.txt` (`transformers`, `torch`, `huggingface_hub`, `torchvision`, `pillow`) and add `--smoke-test` CLI option.
- [x] Pass unit tests across math and HF modules without modifying existing core APIs.


## Pending-work validation progress — 2026-10-11

- [x] All 18 Python math/HF tests passed in the optional-dependency environment.
- [x] Actual Model B pretrained dummy-image inference passed on MPS; no training or fitting.
- [x] Latest HF source deployment succeeded (38070272247) and its downloadable archive includes both comparator modules.
- [x] Generate HF report with actual hashes/licenses/parameter metadata. It explicitly has zero labeled video sessions; accuracy remains unavailable.
- [x] Real browser camera initialization, 25-second calibration, live graph and finish verified with user participation.
- [x] Pending-initialization cancellation verified; video stream detached.
- [x] User-consented disposable graph save, reload, history/view, delete and reload verified. Only that test session was deleted.
- [x] Narrow populated history/result layouts and keyboard opening of graph/exact values verified without horizontal page overflow.
- [x] Fix misleading idle-page hidden error and add bounded initialization with late-resource cleanup. Nine frontend tests passed.
- [x] Add measured FPS/inference/processing diagnostics for device benchmarking.
- [x] Verify deployment of the idle-camera fix and diagnostics (fe96964); real camera diagnostics measured.
- [ ] Controlled lighting/glasses/yaw/multiple-face and permission/busy-camera robustness checks.
- [ ] CPU/memory benchmark and broader multi-session/device characterization.
- [ ] Obtain authorized labeled videos or explicitly consented recorded sessions, then run actual M0–M5 accuracy evaluation. No training is planned.

See VALIDATION.md for verified checks and remaining input-dependent work. Model B warm synthetic MPS benchmark measured about 33.05 ms/image; this is not a complete real-video CPU/memory benchmark.

## Legacy heuristic extension — 2026-10-11

- [x] Preserve supplied legacy camera script unchanged; deterministic headless 24-feature port.
- [x] H0 original calibration and H1 rest/pose/expression harmonization; time-based EMA.
- [x] Keep existing M0–M5; add H0/H1/F1/F2 and retain math baselines.
- [x] Group/per-feature/mouth ablations; task splits and speaking-gate coverage.
- [x] Paired subject-bootstrap comparisons with Holm correction; condition and provided-only skin-tone analysis.
- [x] JSON/Markdown reports and three requested plots; documented run commands.
- [ ] Run real labeled-video evaluation: authorized rest/task videos are still required. Synthetic regression is not accuracy evidence.
- Verification: all 24 Python tests passed in the optional Torch/Transformers environment, including byte-compatible feature-table checks, 300-frame parity, real synthetic-video decoding, both HF-enabled/disabled report paths, 36%/40% exclusion boundary, and time-based EMA equivalence. Reports generated locally with zero real labeled sessions; no predictive accuracy claimed.

## Client flow correction — 2026-10-11

- [x] Default to scan page; single Start action, 10-second scan, automatic Results navigation and camera shutdown.
- [x] Remove personal calibration and manual start/finish steps; simplify Results to score and graph.
- [x] Separate fixed-reference QuickIndex from unchanged offline rest-calibrated evaluation methods.
- [x] Ten frontend tests pass, including immediate scores with no baseline and invalid-frame rejection.
- [x] Real-camera check: automatic 10-second completion, numeric result, Results navigation and stopped camera verified. No video or graph was saved. This checks flow, not stress accuracy.

- [x] Circular camera preview, 10-second animated progress ring, scan sweep/grid and pulsing dots; reduced-motion support. Scan text reads “Scanning your face…”. Production build and idle browser preview verified; scan timing/result flow preserved.


## Repeatability correction — 2026-10-11

- [x] Replace startup-sensitive overlapping score averages with equally weighted time windows and robust feature/score medians.
- [x] Keep the ten-second scan; settle acquisition in its first second without personal calibration.
- [x] Tighten framing/pose, use face brightness, and require 80% time coverage plus eight usable windows.
- [x] Withhold contradictory, sparse, drifting-light or drifting-pose scans with a specific retry reason.
- [x] 19 frontend tests and production build pass; seeded 20-scan synthetic range reduced from 2.750 to 0.310 points without anchoring to previous scores.
- [x] Stabilize QuickIndex feature variance: calibrate canonical baseline reference dispersion to realistic anatomical ranges to prevent microscopic angular shifts (e.g. lip corner) from plunging scores from 5 to 2.
- [x] Surface session feature summary, score scale explanation (0 high tension, 5 baseline mean, 10 relaxed), and posture consistency guidance on scan and results screens.
- [ ] Participant repeatability verification 5–10 minutes apart; fixed reference can still introduce systematic biases. No validated stress accuracy claim.

## Pulse branch extension (Maaoui et al. 2020) — 2026-10-11

- [x] Create `stress_math/pulse_features.py`: skin ROI forehead + cheeks, CIE L*u*v* u* channel (default) and green channel, linear detrending, 4th-order zero-phase Butterworth bandpass (0.65–3.0 Hz), optional CWT cleaning, find_peaks instantaneous HR resampled to 30 Hz, 30 s sliding windows (2 s step), 7 features (`meanHR`, `StdHR`, `DerHR`, `RMSSD`, `LF`, `HF`, `LF/HF`) + `RMSSD_rr`, quality gate (FPS >= 15, valid frames >= 80%, SNR >= 2.0).
- [x] Implement training-free personal rest baseline (first 25 s), sigma floor `max(raw_sd, 0.05 * abs(mu) + 1e-3)`, z-clip [-3, 3], fixed signs (meanHR +, StdHR +, DerHR +, RMSSD -, HF -, LF +, LF/HF +), 0–100 sigmoid scale.
- [x] Create `stress_math/supervised_reference.py`: Leave-One-Subject-Out (LOSO) vs. random window split using SVM (RBF) and LDA on the 7 pulse features, standardized inside fold, default hyperparameters; quantifies leakage gap.
- [x] Create `stress_math/pulse_evaluate.py`: evaluation comparing M0, P, M0+P, H1, H1+P, bootstrap CIs, 1000-shuffle within-subject permutation nulls, Holm correction, Table 2 ablations, and generated plots (`roc_all_methods.png`, `pulse_feature_ablation.png`, `leakage_gap.png`).
- [x] Create `stress_math/test_pulse.py` with 5 unit tests: (a) synthetic 1.2 Hz sinusoid + noise returns ~72 bpm within 2 bpm, (b) sign and baseline z logic, (c) LOSO subject isolation, (d) quality gates and missing data handling, (e) end-to-end report and plot generation with mandatory disclaimers.
- [x] Update `stress_math/requirements.txt` (scipy, scikit-learn), `stress_math/README.md`, and packaged source archive. All 29 tests pass.

## Repeated Unavailable results — 2026-10-12

- [x] Make pose/lighting variability advisory when usable window measurements agree.
- [x] Filter isolated outlier windows; preserve rejection of contradictory scan halves and missing faces.
- [x] Display limited-quality scores/graphs with warnings; provide specific dominant rejection instructions for failed acquisition.
- [x] Production build and regression tests cover normal variation, outliers, multiple-face failure and no-data rejection.

## Project summary — 2026-10-12

- [x] Added `summary.MD`: current 10-second workflow, exact quick-index rules, architecture, development history, research comparators, privacy, setup/deployment and verification limits (source snapshot `cf428c5`).
- [x] Audited and fixed the pulse evaluation runner: real tracked faces and gates, missing branch scores, non-overlapping baseline/evaluation windows, and per-subject baseline z-scored fusion. See the later verification note for runtime limitations.

## Deployed algorithm evaluation and pulse fixes — 2026-10-12

- [x] Added Python port of QuickIndex geometry, fixed reference spreads, gates, 10-second windows, consensus and coverage rules; Node/Python fixture parity checked within 1e-6.
- [x] Reworked pulse runner to use real MediaPipe landmarks, exact-one-face validity, pose/speaking gates and separate windows that cannot cross the 25-second baseline cutoff. Removed label-derived M0/H1 scores; missing branches stay missing. Added overlap and missing-score regression tests.
- [x] Added `evaluate_deployed.py`: non-overlapping 10-second clips, D0/D1/D2, task splits, cluster bootstrap/permutation comparisons, Holm correction, T1 geometry confounds, nuisance perturbations and a fixed decision report.
- [x] Added `repeatability.py`: per-condition within-person SD/SEM/MDC95, ICC(2,1), Bland–Altman, repeated-measures correlation, subject-bootstrap AUC checks and explicit PASS/FAIL report.
- [x] Updated stress_math README and dependencies documentation; frontend source unchanged.
- [x] Verification: 36 Python tests passed, one optional HF inference test skipped because Torch/Transformers are absent in this environment. Pulse smoke and the new Node/Python parity tests passed.
- [ ] Real-video evaluation remains unverified: no labeled evaluation videos were provided in this worktree. The local MediaPipe detector smoke attempt could not create an NSOpenGL context in this execution environment. Offline pose estimates use OpenCV solvePnP, so frames near browser pose thresholds may classify differently.
