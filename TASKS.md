# MVP task tracker

Last updated: 2026-10-11

## Current scope and status — 2026-10-11

Current MVP: a deployed live experimental facial index, not an entered stress rating. The scale is reversed (0 high-stress end, 10 no-stress end), with baseline feature means at 5/10. Questionnaire/Gemini sections below document historical work; they are not the current browser flow. Training is outside the current scope. Datasets are test-only.

### Completed — 10 grouped work items

1. React/Vite frontend, FastAPI/SQLite foundation and project documentation.
2. Local MediaPipe camera processing, model/WASM assets and consent/lifecycle code.
3. Fixed mathematical facial features/index with normalization, sigma floor, gates and smoothing.
4. Browser live graph with 25-second baseline and removal of entered stress-rating results.
5. Graph review, optional browser saving, history and deletion implementation.
6. Test-only dataset/manifest loaders and landmark/score caching.
7. Math baseline comparisons, coverage exclusions, subject-bootstrap CIs and permutation reports.
8. Optional pretrained A/B loaders: dynamic labels, crops, 5fps, fp32, batch/MPS inference and lazy imports.
9. M0–M5 fixed fusion/comparison implementation, paired AUC differences, correlations, params and license/revision reporting code.
10. Synthetic tests/build checks and deployed live-graph UI verification. Model A actual dummy-image inference passed on MPS; optional dummy-classifier/processor test passed. No real dataset accuracy is established.

### Newly verified — 2026-10-11

- Actual Model B inference on MPS; all 18 Python tests and nine frontend tests pass.
- Actual model revision/license/parameter report generated; zero available labeled videos explicitly reported.
- Latest source archive and deployments verified.
- Real webcam initialization, calibration, live graph, finish, cancellation and navigation cleanup verified.
- Disposable graph save/reload/view/delete/reload verified with user consent; test graph removed.
- Narrow populated mobile layouts and keyboard graph/table access verified.
- Camera diagnostics on real inputs: about 9.2 processed frames/s, 21.1 ms mean landmark inference and 24.1 ms mean analysis processing in one session. These are efficiency measurements, not stress accuracy.
- Idle-page hidden warning fixed, initialization bounded, and late resources disposed after cancellation/timeout.
- Experiment tab blank screen resolved: added missing `React` import to `frontend/src/Experiment.jsx` and added top-level `ErrorBoundary` in `frontend/src/main.jsx`.
- Verified live deployment at https://jyotiraditya21-bug.github.io/pause-stress-mvp/: navigation to Experiment view successfully renders headings, instructions, and download links with zero console errors.
- Camera preview streamlined to clean circular viewfinder with SVG outline progress ring: removed extraneous sweep animations, brackets, and filters. Webcam background is fully retained, MediaPipe facial landmarks overlay directly as dots, and instant startup with movement/expression tolerance is verified across all unit (45/45) and Playwright E2E tests (18/18).
- Fast camera initialization & light background verification: eliminated default black HTML5 video flash via `#edf3e8` background and state-gated placeholder transition (`videoReady`). Preloaded FaceLandmarker immediately on page mount and parallelized stream acquisition and landmarker initialization via `Promise.all`.

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

## Production hardening — 2026-10-13

- [x] Create `prod-hardening`; keep `main` untouched by the production branch work.
- [x] Change generic mode to three dynamic geometry features and add versioned, expiring four-feature personal baselines.
- [x] Add MAD-based result ranges, nine explicit window values, actionable warnings, failure status and privacy-safe quality flags.
- [x] Add the quality-gated countdown, pause/resume hints, independent 25-second wall-clock cap, video-frame callback path and clean camera/model disposal.
- [x] Keep the Python deployed mirror and D0/D1 evaluator aligned with quick-2.0; deterministic JavaScript/Python parity passes within 1e-6.
- [x] Replace the main UI with the mobile-first Scan, Results and History flow; add onboarding, calibration/reset, settings, Privacy and About pages.
- [x] Add PWA precaching, lazy MediaPipe loading, error boundary, CSP/security headers, optional scrubbed Sentry and score-free Plausible events.
- [x] Add Playwright/axe/Lighthouse configuration, GitHub Actions jobs, Cloudflare deployment instructions and validation roadmap.
- [x] Verification: 27 frontend unit tests passed, production PWA build passed, and 36 Python tests passed with one optional HF dependency smoke test skipped.
- [x] Playwright: 10/10 main E2E checks passed, including zero serious/critical axe findings and no horizontal overflow at 360×640, 390×844, 768×1024 and 1280×800.
- [x] Production PWA: the app reloaded offline after its first cached load and initialized the camera scan from precached MediaPipe assets.
- [x] Mobile Lighthouse: Performance 98, Accessibility 100, Best Practices 100, SEO 100.
- [ ] No real labeled-dataset accuracy, repeatability PASS or model-licensing completion is claimed; all remain NOT DONE in `docs/VALIDATION_TODO.md`.

## Movement/expression tolerance — 2026-10-15

- [x] Add shared exported provisional configuration (`toleranceConfig.json` / `TOLERANCE_CONFIG`), soft pose/speed/light/size weights, weighted medians, and effective slot coverage. Keep the original four-feature canonical formula/spreads/sigma floor/z clipping in the tolerant comparator.
- [x] Mask mouth features individually and jaw geometry at high yaw without dropping brow observations. Windows require two valid features. Expose used feature counts, confidence, ranges and NORMAL/LIMITED/NONE tiers; NONE never emits a number.
- [x] Add timestamp-based One Euro smoothing, reset after face loss, optional inverse-rotation 3-D correction (OFF), and adaptive 10–20 second acquisition. Preserve true time gaps, first-second exclusion and camera cleanup.
- [x] Add the opt-in browser path `?tolerance=1`, extension progress/hints and result details. Keep the existing strict default pending actual adoption evidence. No main/deployed-site changes were made in this task.
- [x] Add independent Python mirror, shared Node fixtures, recursive 1e-6 parity, manifest-based OLD/NEW/NEW_3D comparison, condition/task metrics, cluster bootstrap CIs, acceptance–SD plot and fixed PASS/FAIL decisions. Missing evidence/extraction failures block adoption.
- [x] Add `docs/TOLERANCE.md`, manifest schema, run commands and implementation definitions. Existing tests encoding strict gates remain unchanged; new tests live in `tolerantScan.test.js`, `test_tolerance.py`, `test_tolerance_evaluation.py` and `e2e/tolerance.spec.js`.
- [x] Verification: 37 frontend tests passed; production PWA build passed. Python full discovery ran 41 tests: 40 passed, one optional Torch/Transformers smoke test skipped; affected tolerance tests were rerun after final edits. Browser suite: 12 passed, one separately configured offline test skipped; includes both tolerant cap/NONE and cancel cleanup checks.
- [x] Actual bundled MediaPipe Tasks model decoded a temporary blank video outside the sandbox. Full evaluator smoke on a 20-second blank recording returned NONE/no score for OLD, NEW and NEW_3D and FAIL adoption, with no extraction failures. Sandbox-only execution cannot create NSOpenGL; no real participant video was used.
- [ ] Authorized still/natural_movement/talking/smiling/glasses/low_light repeated recordings and UBFC-Phys data are absent. No empirical acceptance, AUC improvement or repeatability claim is made. `adopted=false` and `frontalize3d=false` remain in the shared configuration.

## Light, friendly UI redesign — 2026-10-15

- [x] Replace automatic dark tones with a consistent warm off-white, sage, peach and lavender theme; align mobile browser/PWA colors.
- [x] Add a desktop two-column scan layout, clear preparation steps, friendly SVG preview, compact icon navigation and privacy reassurance.
- [x] Add gentle entrance, breathing and scan animations with reduced-motion support. Keep text fully opaque throughout transitions for accessible contrast.
- [x] Update Results presentation and consolidate actions around Save this result, Scan again and optional calibration. Preserve every score, acquisition rule and camera lifecycle behavior.
- [x] Refine narrow/short mobile layouts; visually confirm the start button fits at 360×640 and light colors remain active under a dark system preference.
- [x] Verification: 37 frontend unit tests passed, production PWA build passed, and all 10 main Playwright checks passed, including Scan/Result/History axe checks and four viewport overflow checks. Desktop, phone and Results screenshots inspected. No scoring or Python research changes; no new dependencies.
- [x] Local development server remains available at `http://127.0.0.1:5173/?tolerance=1`. This UI revision was subsequently deployed with the October 17 release.

## Repository presentation — 2026-10-15

- [x] Rewrite README around the current experience, inspected UI preview, branch/deployment status, quick start, modes, privacy, checks and documentation index. Preserve honest validation and licensing status.
- [x] Move earlier setup/demo/validation guides and six phase screenshots into `docs/archive/`; retain historical assets and fix the current research-status reference.
- [x] Add contribution/security guidance, bug/feature issue forms and a pull-request template. Add read-only branch/PR CI for frontend tests/build and Python/parity tests.
- [x] Extend ignore rules for local environment variants, keys, logs and Python tooling artifacts while preserving `.env.example` templates.
- [x] Verify 22 current local documentation/image links and whitespace checks; tracked-path audit found no environment secrets, recordings, databases, caches or dependency/build directories.

## Live release — 2026-10-15

### Production hardening — 2026-10-17

### Separate image-dataset preparation — 2026-10-17

- [x] User authorized cleaning only. **Do not start training until the user explicitly says to start.**
- [x] Create a copy at `../datasets/facesData-2-clean` from `/Users/jimmycodes/Downloads/facesData-2`; originals verified unchanged by SHA-256. Reproducible cleaner is `../../work/clean_faces_dataset.py` relative to this repository.
- [x] Retain 11,983 images (9,519 train / 2,464 test); exclude 284 duplicate copies and quarantine all 8 images in 4 conflicting-label groups. Keep test copies preferentially for same-label duplicate groups, never move images between splits.
- [x] Verify all retained images decode correctly, copies match original checksums, and no identical decoded image remains within or across cleaned splits. Save manifest, JSON report and README outside the application repository. Synthetic policy checks passed.
- [ ] Establish label provenance/license and subject identities if available; exact deduplication does not establish person-disjoint splits or remove all near-duplicates. No training, fitting, model export, upload or deployment performed for this dataset.
- [x] Freeze the cleaned dataset independently at `../training/pause_faces_v1` with per-file checksums and phase-0 completion metadata. Prepare deterministic proposed splits: 7,615 train / 1,904 validation / 2,464 existing test; no test membership changes.
- [x] Approval boundary: user explicitly authorized exploratory image-level experiment and continuous training across all phases. Generated and validated `training/Pause_Phases_4_to_9_Continuous.ipynb` with auto-pilot execution covering Phases 4 (head), 5 (fine-tune), 6 (evaluation), 7 (Grad-CAM), 8 (video validation), and 9 (browser export). All code cells pass AST syntax validation and atomic Drive checkpointing.
- [x] Colab cloud execution: All 9 phases successfully executed on Tesla T4 GPU (Drive run `0ab1b9f9924e655b`):
  - Phase 2 & 3: Extracted frozen 576-dim ImageNet MobileNetV3-Small representations on 7,615 train and 1,904 validation images.
  - Phase 4: Head-only classifier achieved 74.25% validation balanced accuracy (loss 0.2566).
  - Phase 5: Backbone fine-tuning achieved 68.03% validation balanced accuracy.
  - Phase 6: Automated selection picked Phase 4 (Head-Only) winner. Validation evaluation (1,904 images): 74.21% accuracy, 74.25% balanced accuracy, 72.42% precision, 76.97% recall, 74.63% F1, 0.8125 ROC-AUC, 0.1776 Brier score. Confusion matrix: 691 TN, 275 FP, 216 FN, 722 TP.
  - Phase 7: Grad-CAM saliency heatmaps generated and saved to `gradcam_explanations.png`.
  - Phase 8: Live-video temporal validation confirmed raw frame jitter (mean 0.304, max 0.827) reduced to 0.050 with EMA smoothing.
  - Phase 9: Model exported to ONNX (3.84 MB) and TorchScript (4.29 MB) with perfect numerical parity (0.00e+00 max discrepancy). All artifacts archived to Google Drive.
- [x] Client integration & verification (Phases 10–14):
  - Phase 10 (Staging): Staged `pause_stress_model.onnx` (SHA-256 `55a5cf41...`) and `model_spec.json` into `frontend/public/models/`.
  - Phase 11 (Inference Engine): Implemented `frontend/src/mlInference.js` (bounding box crop +15% margin, NCHW normalization, stable softmax, `TemporalEMAFilter` $\alpha=0.20$) and unit test suite `frontend/src/mlInference.test.js` (5 unit tests).
  - Phase 12 (Pipeline Hook): Integrated dynamic model runner `frontend/src/modelRunner.js` into `frontend/src/CameraScan.jsx`. Dynamically samples face crops during scan tick, runs forward passes when enabled, and includes `mlResult` in scan summaries.
  - Phase 13 (UI Toggle & Comparison): Added "Experimental Neural Model" toggle in Settings and URL search param `?ml=1` in `frontend/src/main.jsx`. Displays experimental stress probability and classification in Results details while preserving geometric QuickIndex as default.
  - Phase 14 (Verification & Build Hardening): Configured Vite PWA Workbox to exclude large ONNX WASM binaries from precache. Verified complete test matrix:
    - 45/45 frontend unit tests pass (`npm test`).
    - Vite production PWA build succeeds cleanly in ~2.2s.
    - 18/18 Playwright Chromium E2E tests pass (`npm run test:e2e`).
    - 1/1 Playwright Offline PWA test passes (`npm run test:offline`).
    - 6/6 Playwright WebKit tests pass (`npm run test:webkit`).
    - 9/9 backend unit tests pass (`backend/.venv`).
    - 40/41 stress_math tests pass (`stress_math/.venv`, 1 skipped).
- [x] Camera UX & Movement/Expression Tolerance:
  - Immediate Camera Startup: Preload and cache `FaceLandmarker` so camera opens instantly without 3–4 second WASM re-initialization lag.
  - Natural Background Preserved: Replaced circular masking with an open 4:3 camera viewfinder card (`border-radius: 22px`, `object-fit: cover`) keeping the user's room and background 100% visible, with subtle semi-transparent face guide overlay and corner brackets.
  - Movement & Expression Tolerance Active: Enabled tolerant acquisition by default with soft weighting, OneEuro smoothing, and feature masking so head movement and natural expressions (smiles, talking, laughing) don't pause, abort, or fail the scan.
  - Steady 10-Second Scan: Uses synchronized elapsed time with a smooth progress bar and countdown badge, ensuring a full, stable 10-second check-in.

### Production hardening implementation

- [x] Fix standard capture timestamps, preserving gaps and a fixed ten-second acquisition; retain formula, gates and opt-in tolerance settings. Add gap/dropped-frame parity regression.
- [x] Reset calibration on normal navigation and refresh baseline expiry on returning to Scan.
- [x] Validate history records; offer explicit backup-before-repair recovery, separate backup deletion, and explanatory privacy copy. Preserve valid records and protect original data if backup fails.
- [x] Separate trend groups by algorithm, source, acquisition version and personal baseline identity; exclude calibration scans and use real date spacing.
- [x] Include the larger light UI, feature/non-diagnostic copy, subtle reduced-motion animations and experimental mode/duration labeling.
- [x] Enforce the historical backend's local-only boundary; add body/rate limits and pagination, fix SQLite connection leaks, and add explicit backend CI. Public multi-user backend hosting remains out of scope for the static product.
- [x] Verify 40 unit tests, production build, 18 Chromium checks, 6 WebKit UI checks, offline PWA, 9 backend tests and strict/tolerant parity. Production npm audit: zero known advisories. See docs/RELEASE_READINESS.md for physical-device and participant-evaluation gaps.
- [x] Merge PR #2 as `f8307b3`; Pages run `39015870990` passed Lighthouse, Chromium, WebKit, offline and deployment jobs. Public smoke check confirmed HTTP 200, no page errors/serious accessibility violations/overflow, successful model/WASM/PWA requests and fake-camera initialization/cancellation with all tracks stopped.

### Product review — 2026-10-17 (review only)

- [x] Recheck production build, 37 frontend tests, 5 isolated backend tests, 12 Chromium browser checks and the separate offline PWA test; all passed. No real-camera accuracy/repeatability or Safari validation performed.
- [x] Replace accumulated-good-time scoring with capture timestamps and verify gap-aware deployed/offline parity.
- [x] Reset calibration intent on ordinary navigation; add a regression for Settings → calibration → History → Scan.
- [x] Validate saved history records and offer recovery; add a regression for synthetic `[null]` alongside a valid record.
- [x] Separate history trends by algorithm/reference/baseline identity and use date spacing.
- [x] Show experimental tolerance mode and realistic duration explicitly.
- [x] Keep historical FastAPI local-only, add pagination/request limits and backend CI. Any future public multi-user API still requires authentication and session ownership; it is not part of this static deployment.
- [ ] Validate participant repeatability and physical-device camera behavior before making accuracy claims. Automated WebKit UI checks passed; they are not physical Safari/iPhone camera validation.

### Subsequent UI refinement (local preview)

- [x] Enlarge desktop content and circular preview by about 10%, retaining the palette and layout. Add a compact feature row and explicit non-diagnostic description.
- [x] Add subtle chip pulse, staggered feature entrances, button-arrow hover and active-card emphasis, respecting reduced motion.
- [x] Production build and 12 browser checks passed (one offline-only test intentionally skipped in this suite); desktop screenshot inspected. This UI refinement was subsequently included in the October 17 deployed hardening release.

- [x] Confirm no open GitHub issues; resolve PR #1 conflicts with the earlier main-branch UI revert, preserving the latest light interface and research code.
- [x] Require browser and offline checks before the Pages deployment job; update README for main-based releases.
- [x] Recheck 37 frontend unit tests and production build successfully after restoring supporting UI pages.
- [x] PR #1 merged as `590e66b`; Pages run `38776587447` passed browser/offline, Lighthouse and deployment jobs. Local browser suite: 12 passed plus the separate offline test; default-suite offline skip is intentional.
- [x] Verify the public site at a 390×844 viewport: HTTP 200, expected scan heading/button, no horizontal overflow, no page errors or serious/critical axe violations. Model, WASM, manifest and service worker each return HTTP 200. These checks do not establish stress accuracy or real-camera repeatability.
