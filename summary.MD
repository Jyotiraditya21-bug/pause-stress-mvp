# Pause — complete project summary

**Snapshot:** 13 October 2026 · deployed source commit `cf428c5` · documentation based on the current repository, including newer local evaluation work that has not yet been published.

- **Live application:** https://jyotiraditya21-bug.github.io/pause-stress-mvp/
- **Repository:** https://github.com/Jyotiraditya21-bug/pause-stress-mvp
- **Local project:** `/Users/jimmycodes/Documents/Codex/2026-10-09/do/outputs/stress-mvp`

## 1. What we are building

Pause is a camera-based wellbeing MVP, initially inspired by Streffie. The intended experience is simple: a person sits in front of a camera for **10 seconds**, then automatically sees a score and graph. It was developed for a MacBook Air M1, with a browser deployment that does not require a server or GPU.

The current result is a **training-free, experimental facial index from 0 to 10**. Lower values represent greater deviation in the formula's stress-oriented direction; higher values represent less. It is **not a validated measurement of psychological stress**, a diagnosis, or a percentage of stress. Facial geometry cannot by itself establish how stressed someone feels.

There are three distinct systems in this repository:

| System | Purpose | Used by the deployed scan? |
|---|---|---|
| Browser application | Camera, landmarks, fixed mathematical index, graph and results | Yes |
| FastAPI backend | Earlier questionnaires, SQLite sessions and optional Gemini guidance | No, not in the current Pages scan flow |
| Python research tools | Dataset evaluation, pretrained comparators, legacy heuristics and experimental pulse analysis | No |

The browser score is computed locally. It does not copy a user-entered stress rating, call Gemini, run the Hugging Face stress models, or use a previous scan's result.

## 2. Current user journey

1. Open the site and select **Start 10-second scan**. This authorizes local camera processing; the browser may also ask for camera permission.
2. The application loads MediaPipe and opens the camera. These startup steps happen before the measurement countdown, so the total interaction can take longer than 10 seconds.
3. A circular camera preview displays an animated progress ring, scanning effects, countdown and framing guidance. Reduced-motion preferences are supported.
4. Camera frames are processed locally for 10 seconds. There is no separate calibration step or questionnaire.
5. The camera stops automatically and the application opens Results.
6. A usable scan shows its facial index and time graph. A limited scan shows a confidence warning. An unusable scan shows an actionable retry reason instead of inventing a number.

The interface includes Live, Overview, Results, History and Experiment. History can display and delete previously saved sessions. Storage helpers remain, but the current normal scan flow does not expose a save action; do not assume every new scan is automatically saved.

## 3. Architecture and technology

```text
Camera permission → local video frames → MediaPipe FaceLandmarker
                                          ↓
                           face landmarks + approximate pose
                                          ↓
                          quality checks + facial geometry
                                          ↓
                        fixed reference → mathematical index
                                          ↓
                         time windows + reliability checks
                                          ↓
                             score + graph + explanation
```

| Component | Technology / role |
|---|---|
| Frontend | React 19, JavaScript, CSS |
| Development/build | Vite 7, npm, Node.js; deployment uses Node 22 |
| Camera | Browser media APIs, video element and frame processing |
| Face detection | `@mediapipe/tasks-vision`, pretrained FaceLandmarker, local model/WASM assets |
| Browser scoring | Custom JavaScript geometry, normalization, medians and fixed quality rules |
| Historical local backend | Python, FastAPI, Uvicorn, Pydantic and SQLite |
| Historical AI guidance | Server-side Gemini integration with explicit consent and local fallback |
| Research core | NumPy, OpenCV, MediaPipe, SciPy, scikit-learn, pandas, Matplotlib |
| Optional pretrained comparators | PyTorch, Transformers, Hugging Face Hub, Pillow/torchvision |
| Hosting | GitHub Pages, built and deployed through GitHub Actions |

MediaPipe is the AI component in the deployed scan: it detects facial landmarks. **We did not train a stress-prediction model for the live application.** The mapping from landmarks to the displayed index is an engineering formula.

## 4. How the current 10-second score works

### A. Acquire and validate frames

The camera requests a user-facing video stream, ideally 640 × 480, without audio. Landmark inference uses MediaPipe's CPU delegate and is scheduled at approximately 10 processed frames per second, depending on the device.

The detector permits two faces to be detected so the application can reject multiple-person frames. Exactly one face must pass the checks. Brightness is measured in the face region, rather than across the whole room.

Current provisional gates include:

| Check | Current rule |
|---|---|
| Face count | Exactly one |
| Face-region brightness | 18–240 on a 0–255 scale |
| Face width / image width | 0.15–0.85 |
| Face height / image height | 0.20–0.95 |
| Face-center offset | At most 0.24 on either normalized axis |
| Inter-frame center movement | At most 0.05 |
| Pose, when available | Absolute pitch ≤38°, yaw ≤30° |
| Mouth aspect ratio | ≤0.32 |

Missing pose is currently allowed in the quick path. These are permissive engineering checks, not proven stress-measurement criteria. Movement checks are also influenced by the actual frame cadence.

### B. Extract four geometry proxies

A selected 75-point canonical face reference is used for alignment. Translation, image-plane rotation and size are normalized with a 2-D similarity alignment and interocular scaling.

| Feature | Geometric basis |
|---|---|
| `brow_furrow` | Negative brow/brow-to-eye distances |
| `lip_press` | Negative visible lip thickness relative to mouth width |
| `lip_corner` | Mouth-corner angle relative to the mouth center |
| `jaw_clench` | Face-width to face-height ratio |

The names describe intended proxies. For example, `jaw_clench` does not directly measure muscle contraction. Natural facial anatomy, expression, camera perspective and pose still influence these values.

The quick score does **not** include heart rate, HRV, blink rate, skin texture, a pretrained stress classifier or a language model.

### C. Compare with a fixed canonical reference

There is no personal relaxed baseline in the current 10-second flow. The reference is generic canonical geometry with hand-set spreads:

```text
brow_furrow: 0.06
lip_press:  0.04
lip_corner: 0.06
jaw_clench: 0.08
```

Five artificial reference rows are constructed: the canonical values, plus/minus each spread and plus/minus half each spread. These are not measurements from a training dataset. The resulting standard deviations are calculated from those rows, then floored:

```text
sigma_i = max(raw_sigma_i, 0.05 × abs(mu_i) + 0.001)
z_i     = clip((feature_i − mu_i) / (sigma_i + 0.000001), −3, 3)
r       = sum(z_i) / sqrt(number_of_available_features)
index   = 10 × (1 − sigmoid(r))
```

A value of 5 corresponds to the formula's reference mean. It does not establish that this person is relaxed or that their real stress is 50%.

### D. Stabilize observations within the scan

- The first second is excluded to allow acquisition to settle, leaving nine seconds of evidence.
- Those nine seconds contain 45 slots of 0.2 seconds each.
- Each slot uses the median of available valid feature observations.
- Each one-second window needs at least two usable slots; its feature medians produce an independent score.
- There are up to nine scored windows. Quick scoring does not carry a previous scan's state forward.
- Windows within one point of the overall median form a consensus. The final result is the median of that consensus.

Minimum acceptance requires at least 35% slot coverage, three scored windows, evidence in both early and late portions, and consensus from at least three windows and 60% of scored windows. Early versus late consensus medians must differ by no more than 0.75 points.

Coverage below 80%, fewer than eight scored windows, discarded outliers, or excessive within-scan pose/brightness variation can produce a **limited-confidence result** instead of a total failure. Insufficient evidence still produces an incomplete scan. Missing periods remain gaps in the graph.

The internal field `average` is retained for compatibility, but now contains a **median-based** result. Graph points may include windows discarded from the final consensus.

### E. What repeatability improvements can and cannot do

The reference spreads, robust window medians, consensus and quality feedback reduce sensitivity to isolated bad frames. They do not prove biological accuracy or guarantee the same score five minutes later. Differences in expression, pose, lighting, camera distance, tracking and actual state can still change the result.

We must measure repeatability across real repeated scans before claiming consistency. Forcing a result to match the previous score would conceal variation and is not implemented.

## 5. How the project was built

| Stage | Work completed / direction |
|---|---|
| Foundation | React/Vite interface, FastAPI service, SQLite storage and project documentation |
| Initial camera MVP | Local MediaPipe processing, consent, quality checks and camera cleanup |
| Check-in features | Questionnaire, self-report results, history and persistence |
| Guidance | Optional Gemini advice with validated output, explicit consent and fallback |
| Static deployment | Browser storage mode and GitHub Pages automation |
| Research expansion | Fixed mathematical index, dataset loaders, statistical evaluation and comparator models |
| Heuristic extension | Original supplied script preserved; headless H0/H1 variants, ablations and fusion |
| Simplified product | Questionnaire removed from current flow; personal calibration replaced by generic reference; automatic 10-second scan-to-result journey |
| Visual polish | Circular preview, scan animation, countdown, responsive layout and reduced-motion support |
| Reliability fixes | Window medians, reference variance, relaxed acquisition gates, consensus, limited-confidence results and clearer failures |

Earlier designs used longer scans and a 25-second personal baseline. Those APIs and historical documents remain, but they do not describe the current browser journey. Some older README/TASKS sections also describe questionnaire and source-download features that have since changed.

## 6. Offline research: `stress_math`

This separate Python package evaluates hypotheses on labeled recordings. It does not run inside the deployed website.

### Core mathematical method

The offline method can use blink rate, brow furrow, lip press, lip corner, jaw geometry, jitter and optional camera-derived heart-rate/RMSSD proxies. It uses the first 25 seconds of designated rest for each subject's baseline, the same sigma floor, clipped z-scores and fixed aggregation. It also has its own pose, speaking/smile gates and temporal processing.

The offline score runs **0–100, higher = more stress-oriented deviation**. This direction is opposite to the browser's 0–10 presentation. Offline evaluation results cannot automatically validate the quick browser formula: their features, baselines, durations and gates differ.

The original adapter continues to report **“OLD has no video scorer.”**

### Implemented comparison methods

| ID | Method |
|---|---|
| M0 | Fixed mathematical index |
| M1 | `TheBgGirl/fer-stress-vit`, probability of the configured “stressed” label, baseline-normalized |
| M2 | `HardlyHumans/Facial-expression-detection`, anger + fear + sad + disgust probabilities, baseline-normalized |
| M3 | Equal-weight fusion of M0, M1, M2 |
| M4 | Equal-weight fusion of M0, M1 |
| M5 | Equal-weight fusion of M0, M2 |
| H0 | Legacy heuristic: 90-frame median baseline, fixed blink baseline of 17/minute, no shared gates |
| H1 | Harmonized heuristic: first 25 seconds of rest, personal blink baseline, shared gates |
| F1 | Equal-weight fusion of M0, H1 |
| F2 | Equal-weight fusion of M0, H1, M1, M2 |

Fusion uses branch z-scores against rest, the sigma floor, clipping to ±3, an equal-weight mean and sigmoid to 0–100. Weights are fixed, not optimized against evaluation labels.

The HF comparators load lazily; the core does not require them. They use RGB face crops from landmark bounding boxes with 15% margin, the model's image processor and `id2label`, sampling at 5 FPS, batched fp32 inference, `torch.no_grad()`, and MPS when available, otherwise CPU. Landmark and model-score caches avoid repeated computation and include source/video fingerprints. Model metadata records revision and licensing information.

These are third-party pretrained models. We did not train them. The training data/splits of `fer-stress-vit` are undocumented, so overlap with UBFC-Phys cannot be excluded. Emotion probabilities are not stress measurements. Recorded model inspection found no published license for Model A; Model B declared MIT in its card. Licensing must be resolved before any intended redistribution or product integration.

### Legacy heuristic and ablations

The supplied `face_stress_mesh.py` is preserved under `stress_math/legacy/`. Its headless port keeps the 24 feature definitions, directions, scales, weights, smile relief and gain of 4. Legacy 0–10 output is reversed to `100 × (1 − score/10)`. EMA uses `1 − exp(−dt/0.316)` with video timestamps.

Groups are fixed:

- **Geometry, 13:** smile lift, mouth width, cheek raise, mouth asymmetry, lip compression, lip thinness, jaw clench, brow furrow/height/asymmetry, eye EAR/asymmetry, nostril flare.
- **Temporal, 3:** blink rate, gaze instability, head jitter.
- **Texture/colour, 8:** lip pallor, forehead/glabella/nose wrinkles, crowfeet, tear redness/gloss, undereye darkness.

Reports support groups alone/removed, per-feature AUC drops, and a mouth-feature removal experiment. Some legacy temporal buffers still use frame counts, so time-based EMA alone does not make every feature FPS-independent.

### Evaluation protocol

- UBFC-Phys T1 = rest, T2 = speech task, T3 = arithmetic task. These are task labels, not clinical measurements of stress.
- Compare the same videos and eligible time windows; exclude calibration from classification.
- Exclude videos with less than 40% valid coverage and list exclusions.
- Report per-video and per-task coverage, including speaking-related gating.
- Primary metrics: ROC-AUC, paired Cohen's d_z and Wilcoxon p, with subject-cluster bootstrap confidence intervals.
- Use 1,000 bootstrap draws and 1,000 shuffled-label permutations, seed 42; preserve subject structure.
- Threshold metrics at score >50 are secondary; 50 is a constructed baseline reference.
- Compare paired AUC differences and apply Holm correction across pairwise tests in the extended comparison.
- Report T1–T2, T1–T3 and pooled results; flag a pooled effect driven only by speech.
- Report conditions such as low light, glasses and yaw offsets only when provided in a manifest.
- Analyze skin-tone metadata only if supplied by the dataset; never infer it from faces.

Outputs include `metrics.json`, `report.md`, `comparison.md`, `summary.md`, ROC plots, task-split plots and group ablations. **No real labeled-dataset accuracy has been established in the recorded project work.** Empty or synthetic reports are not evidence of prediction quality.

### Pulse research branch

`pulse_features.py`, `pulse_evaluate.py` and `supervised_reference.py` add experimental camera-pulse processing and supervised reference comparisons. They are not part of the 10-second browser application, and their pulse windows are longer than the deployed scan.

The pulse runner now extracts real MediaPipe landmarks, face-valid flags, pose gates and speaking gates. It no longer creates M0/H1 values from target labels. Missing method scores stay missing and are excluded from that comparison. Rest-baseline windows must end within the first 25 seconds, evaluation windows start at or after 25 seconds, and fusion uses per-subject rest normalization with the shared sigma floor and clipped z-scores.

The pulse signal is estimated from forehead and cheek colour changes, filtered in a plausible cardiac band and converted into fixed heart-rate and variability features. These are webcam rPPG estimates, not ECG measurements. Very short LF/HRV estimates are especially unreliable. The supervised SVM/LDA runner remains a leakage-demonstration comparator and does train models when explicitly executed; it is not a deployed method. No pulse result has established real stress accuracy.

### Exact mirror of the deployed ten-second algorithm

`deployed_mirror.py` is a Python port of `frontend/src/liveIndex.js`, `scanReliability.js` and the relevant `scanMetrics.js` rules. It preserves the same acquisition gates, 75-point alignment, four features, canonical spreads, five constructed reference rows, sigma floor, z clipping, sigmoid mapping, first-second exclusion, 0.2-second slots, one-second windows, consensus rule, acceptance rules and limited-confidence rules.

A Node/Python parity test runs deterministic landmark fixtures through the JavaScript and Python implementations and requires equality within `1e-6`. This validates formula parity on those fixtures; it does not validate stress accuracy. Offline video extraction uses MediaPipe Face Mesh and OpenCV pose estimation, while the browser uses MediaPipe Tasks transform matrices, so borderline pose decisions can differ between environments.

`evaluate_deployed.py` cuts labeled task recordings into non-overlapping ten-second clips and evaluates:

| ID | Meaning |
|---|---|
| D0 | The deployed four-feature formula with its generic canonical reference |
| D1 | The same four features normalized against that subject's first 25 seconds of rest |
| D2 | Within-clip dynamics based on variance across one-second feature windows |

Clips that fail the deployed acceptance rules are excluded and their coverage is reported. D1 never evaluates on rest material used for its own baseline. Results are split into T1 vs T2, T1 vs T3 and pooled comparisons, with subject-cluster bootstrap confidence intervals, within-subject permutation nulls and Holm-corrected paired method comparisons.

The evaluator also measures two major risks:

- **Face-shape confounding:** on rest clips, ICC(1) compares between-person variation in D0 and D1, and Spearman correlations test whether average D0 follows static facial geometry.
- **Nuisance sensitivity:** the same clips are reprocessed with brightness ×0.6/×1.4, 320×240 resolution, JPEG quality 40 and ±10° rotation. D0/D1 score shifts are compared with the observed rest-versus-task effect.

These tools are complete and runnable, but no authorized labeled dataset was executed in the recorded work. There are therefore no legitimate AUC, repeatability or nuisance-resistance claims yet.

### Repeatability for our own sessions

`repeatability.py` accepts one row per completed scan with `subject_id, session_id, day, condition, score, self_report`. It reports within-condition SD, SEM, MDC95, ICC(2,1), Bland–Altman agreement and repeated-measures score/self-report correlation.

The pre-declared decision is deliberately strict: PASS requires the lower confidence bound of within-subject AUC to exceed 0.60 for rest-versus-arithmetic and rest-versus-speech separately, and every measured nuisance shift must stay below half of the corresponding stress-task effect. Missing evidence is a failed criterion, not an assumed pass. Nuisance evidence must contain the same participant IDs as the repeatability file.

This protocol answers the user's practical question—whether person A receives a similar score after 5–10 minutes under the same condition—without forcing a new result to resemble an old result. Smoothing across separate scans would hide instability and is not used.

## 7. Earlier backend, guidance and training work

The historical backend supports health/schema endpoints, session creation/list/deletion and session guidance. SQLite stores validated questionnaire/context data and optional camera summaries. It has no production authentication or database encryption and should remain bound to `127.0.0.1`.

Gemini guidance was implemented as an optional server-side feature with explicit disclosure/consent, constrained output, timeouts and deterministic fallback. It is intended to suggest wellbeing actions, not invent a stress measurement. Secrets belong in private server configuration and must never enter the frontend bundle. Gemini is not used by the current Pages scan; a live provider request remains unverified in the recorded work.

The `training/` folder contains an earlier feature-extraction/logistic-regression approach and a Colab notebook. Participant-separated splitting was planned, including half the subjects for training where appropriate. These are historical experiments, not the current deployed algorithm. Their earlier feature schema does not match today's four-feature quick score. No real dataset training or Colab run should be claimed as completed.

## 8. Privacy and lifecycle

- Current scans process video in browser memory; no video, audio or landmarks are uploaded or recorded by default.
- Camera tracks and model resources are cleaned up on completion, cancellation, navigation, hidden-page handling and errors. Initialization has a timeout and late-resource disposal.
- Browser session storage, when used, is local to that browser/profile; clearing site data removes it. It is not a cloud account or synchronized history.
- The separate Python `--live` research recorder explicitly records local video after consent. Its behavior is different from the browser scan.
- Datasets, local recordings, caches, secrets and session databases must remain private/ignored.
- Pages serves static frontend assets. It does not run Python, SQLite, Transformers or Gemini.

## 9. Main files

| Path | Responsibility |
|---|---|
| `frontend/src/CameraScan.jsx` | Camera/model startup, frames, countdown, scan UI and cleanup |
| `frontend/src/liveIndex.js` | Geometry, fixed normalization and quick/historical index classes |
| `frontend/src/scanReliability.js` | Slots, windows, consensus and result quality |
| `frontend/src/scanMetrics.js` | Acquisition quality and metrics |
| `frontend/src/faceReference.json` | Selected canonical landmark reference |
| `frontend/src/main.jsx` | Navigation, result/history integration |
| `frontend/public/mediapipe/` | Face model and WASM assets |
| `backend/main.py`, `backend/guidance.py` | Earlier local APIs, storage and guidance |
| `stress_math/core.py`, `video.py` | Offline index, landmarks, feature extraction |
| `stress_math/evaluate.py`, `extended_evaluate.py` | Evaluation/report entry points |
| `stress_math/hf_models.py`, `hf_evaluate.py` | Optional pretrained comparators |
| `stress_math/heuristic_mesh.py`, `legacy/` | Headless heuristic and preserved original |
| `stress_math/pulse_evaluate.py`, `pulse_features.py` | Corrected real-landmark pulse experiment |
| `stress_math/deployed_mirror.py` | Python mirror of the deployed JavaScript score and reliability rules |
| `stress_math/evaluate_deployed.py` | Ten-second D0/D1/D2 dataset evaluator and nuisance/confound analysis |
| `stress_math/repeatability.py` | Repeated-session reliability statistics and fixed PASS/FAIL decision |
| `stress_math/validation_stats.py` | Shared bootstrap, permutation, effect and comparison statistics |
| `training/` | Earlier deferred supervised-training tooling |
| `.github/workflows/pages.yml` | Frontend test/build/deploy automation |
| `TASKS.md`, `AGENTS.md` | Work history and contributor instructions |

## 10. Running and deploying

### Frontend

```sh
cd /Users/jimmycodes/Documents/Codex/2026-10-09/do/outputs/stress-mvp/frontend
npm ci
npm run dev
```

Open `http://127.0.0.1:5173/`. For a Pages-like local run, use `VITE_STORAGE_MODE=browser npm run dev`. Camera access requires an appropriate secure context; localhost and the HTTPS Pages site support this.

```sh
npm test
npm run build
```

### Optional historical backend

```sh
cd /Users/jimmycodes/Documents/Codex/2026-10-09/do/outputs/stress-mvp/backend
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Vite proxies `/api` to the local backend. Keep any provider credentials private; they are unnecessary for the current browser-only scan.

### Offline research

From the repository root, use Python 3.11/3.12 for the pinned legacy MediaPipe dependency:

```sh
python3.12 -m venv stress_math/.venv
stress_math/.venv/bin/python -m pip install -r stress_math/requirements-core.txt
stress_math/.venv/bin/python -m unittest stress_math.test_math -v
stress_math/.venv/bin/python -m stress_math.evaluate --manifest /path/to/sessions.csv
```

For HF/legacy comparisons, install the larger optional environment:

```sh
stress_math/.venv/bin/python -m pip install -r stress_math/requirements.txt
stress_math/.venv/bin/python -m unittest stress_math.test_math stress_math.test_hf stress_math.test_heuristic -v
stress_math/.venv/bin/python -m stress_math.hf_models --smoke-test --model A
stress_math/.venv/bin/python -m stress_math.hf_models --smoke-test --model B
stress_math/.venv/bin/python -m stress_math.evaluate --legacy-heuristics --hf-models --manifest /path/to/sessions.csv --output stress_math/results/legacy_hf
```

A manifest requires `video_path,subject_id,label,dataset`. Stress-task recordings should explicitly reference the subject's separate rest recording using `baseline_video_path`. Obtain authorized datasets yourself; no private dataset credentials are bundled.

To verify frontend/Python formula parity and evaluate the exact deployed algorithm:

```sh
stress_math/.venv/bin/python -m unittest stress_math.test_deployed_mirror stress_math.test_validation_tools -v
stress_math/.venv/bin/python -m stress_math.evaluate_deployed --root /path/to/UBFC-Phys --output stress_math/results/deployed
# Or use a manifest:
stress_math/.venv/bin/python -m stress_math.evaluate_deployed --manifest /path/to/sessions.csv --output stress_math/results/deployed
```

To analyze repeatability from our own completed scans:

```sh
stress_math/.venv/bin/python -m stress_math.repeatability \
  --manifest /path/to/repeated_sessions.csv \
  --metrics stress_math/results/deployed/metrics.json \
  --output stress_math/results/repeatability
```

The repeated-session CSV requires `subject_id,session_id,day,condition,score,self_report`. Use repeated measurements under rest, speech and arithmetic conditions. The deployed evaluator and repeatability tool generate Markdown/JSON reports and plots; they do not silently manufacture values when evidence is unavailable.

### Deployment

Pushes to `main` trigger GitHub Actions, which installs frontend dependencies, runs tests, builds with the repository base path and browser storage mode, and publishes `frontend/dist` to Pages. Manual workflow dispatch is also supported.

The last verified deployment in the recorded work was commit `cf428c5`, run `38202772380`. Current deployment no longer packages a Python source archive into the site. Source is available through the repository, separately from the frontend runtime.

## 11. What has actually been verified

| Area | Evidence and limits |
|---|---|
| Latest frontend change | 22 tests and production build passed in the preceding implementation work |
| Deployment | Latest recorded Pages workflow succeeded |
| Camera journey | Real local camera scan, automatic result navigation and camera stop were checked on earlier versions |
| Latest reliability change | Regression-tested; fresh user confirmation on real repeated scans is still needed |
| Legacy port | 300-frame feature parity within 1e-6 and time-based EMA checks recorded |
| Research tests | Latest full recorded run: 36 Python tests passed; one optional real-HF smoke test skipped because its heavy dependencies were absent in that environment |
| HF loading | Both models passed actual dummy-image inference smoke checks in the optional MPS environment |
| Deployed mirror | Node/JavaScript and Python fixture parity passed to within `1e-6` |
| Baseline isolation | Unit coverage enforces baseline windows ending by 25 seconds and evaluation beginning at or after 25 seconds |
| Pulse runner | Label-derived fallbacks removed; real landmarks/gates and per-subject fusion normalization implemented and unit-tested |
| Real offline video extraction | A synthetic-video detector initialization attempt failed because MediaPipe could not create an NSOpenGL context in the execution environment; real dataset execution remains unverified |
| Real stress accuracy | Not established |
| Cross-person fairness and repeatability | Not established |
| Dataset evaluation | D0/D1/D2, pulse, heuristic and pretrained evaluation code exists, but no real labeled-dataset metrics were produced in the recorded work |

These are historical verification records, not a claim that all tests or live camera sessions were rerun while writing this summary. Successful tests validate selected software behavior, not clinical usefulness.

## 12. Remaining priorities

1. **Verify the current scan with real repeated sessions:** track acceptance, coverage, warnings and within-person score differences under controlled conditions, then repeat across devices and people.
2. **Resolve remaining scan failures from evidence:** distinguish camera/model errors from insufficient valid frames; do not replace missing evidence with a made-up score.
3. **Keep product claims accurate:** clearly label the result as an experimental facial index. Geometry, facial emotion and psychological stress are different quantities.
4. **Obtain an authorized labeled video dataset and execute the deployed D0/D1/D2 protocol:** report uncertainty, rejected clips, task-specific confounds, face-shape dependence and nuisance shifts.
5. **Collect repeated scans from the same participants:** use fixed lighting, distance and instructions first, then deliberate nuisance conditions; run the repeatability PASS/FAIL protocol.
6. **Run pulse, heuristic and pretrained comparators only as separate research experiments:** they do not validate D0 and do not execute on GitHub Pages.
7. **Review model licensing and provenance before integration:** especially undocumented training overlap and missing license information.
8. **Publish the local evaluation additions only after reviewing the current uncommitted changes:** the deployed commit predates these newer research files.

The MVP's scan-to-result experience is implemented and deployed. The main remaining challenge is establishing that its index is repeatable and meaningfully related to the intended outcome; that requires evidence beyond a working interface and passing code tests.
