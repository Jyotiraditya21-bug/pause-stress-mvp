# Movement and expression tolerance

This is a provisional acquisition experiment. The strict production default is retained until the predeclared adoption decision passes on real recordings. No authorized condition recordings or UBFC-Phys videos were present when this extension was implemented. No acceptance, repeatability or AUC improvement is claimed.

## Try the implementation

Run `npm run dev` from `frontend/` and open `http://127.0.0.1:5173/?tolerance=1`. This selects the tolerant camera pipeline for that page only. Without the parameter, the existing strict pipeline remains active. The exported `TOLERANCE_CONFIG` in `frontend/src/tolerantScan.js` reads `toleranceConfig.json`; Python reads that same file. `adopted` and `frontalize3d` remain false. Do not change thresholds based on test outcomes outside the prescribed evaluation.

The tolerant experiment uses all four original features, the unchanged canonical means/spreads, five reference rows, sigma floor, z clipping and `sum(z)/sqrt(n)` reversed sigmoid formula. The existing strict browser generic mode is three-feature quick-2.0; it remains untouched. To isolate acquisition changes, the evaluation's OLD comparator uses the original four-feature formula with old hard gates and aggregation. It is explicitly not presented as a measurement of the current three-feature default's accuracy.

## Fixed acquisition definitions

- Frame weight is pose × raw landmark speed × face-region brightness × face size. Exactly one face is required. Weights below 0.1 contribute no observations.
- Pose is full through 20°, falls linearly to 0.2 at 40°, then linearly to zero at 50°. Missing pose weighs 0.6. Speed has the analogous 0.15 → 0.6 → 1.0 breakpoints, using elapsed frame timestamps and interocular distance. There is no threshold jump after the soft breakpoint.
- Light and size ramps lie **inside** their allowed ranges: weight is zero at/outside each bound and rises to one after 10 brightness units or 0.05 normalized size units. These choices resolve the unspecified ends of the requested ramps and remain provisional.
- Speed uses raw pixel landmarks before smoothing, so smoothing cannot hide rapid motion. One Euro filters operate independently on x/width, y/height, z/width and restore pixels before optional head rotation. They reset after more than 0.5 s without a tracked single face. Raw frames are never held through missing periods.
- Opening the mouth invalidates only lip press/corner. When frontalization is not actually applied, yaw over 25° also invalidates jaw geometry. A window needs at least two observed features and two populated slots.
- Slot feature values are weighted medians; a slot's evidence weight is its maximum frame weight. Window features use weighted medians across observed slots. Missing features remain missing. A weighted-median tie averages the two boundary observations.
- Effective coverage is accumulated slot weight / **45**, clipped to one. At ten seconds, coverage below 0.6 extends acquisition to at most twenty seconds; new slots add real evidence. The denominator is intentionally not enlarged. There are nine windows at ten seconds and up to nineteen when extended. The first second is always excluded. Early/late halves use the midpoint of the actual window timeline, including gaps.
- The live hint is nonblocking and appears when two-second rolling effective coverage is below 0.4. Extension displays “Almost there, small movements are fine”. Camera cleanup still applies to cancel, finish, errors, navigation and page hide.
- NORMAL and LIMITED require the specified consensus and early/late agreement. NONE returns `average`, `latest` and `range` as null. Confidence does not override the NONE tier or create a number.
- `pose_speed_variability = clip(max(population SD(max(|pitch|,|yaw|))/50, population SD(speed)/1.0), 0, 1)`. It uses observed timestamps only; missing measurements are not zero-filled. Confidence uses the requested 0.5/0.3/0.2 formula. The range is descriptive scan variability, not a medical confidence interval.
- `frontalize3d` remains off. When explicitly enabled for evaluation, each 3-D point is multiplied by the inverse head rotation after column-scale removal and centered orthographic projection, then passed to the original 2-D alignment. A missing/invalid matrix falls back to 2-D; jaw masking still applies in that case.

## Run the offline comparison

From the repository root:

```sh
stress_math/.venv/bin/python -m stress_math.evaluate_tolerance \
  --manifest stress_math/tolerance_manifest.example.csv \
  --output stress_math/results/tolerance
```

The supplied example is intentionally header-only: it produces unavailable metrics and a FAIL decision, never synthetic empirical results. Populate a copy with authorized videos. Required columns are `video_path,subject_id,condition,task,dataset`. Optional `start_seconds,end_seconds` restrict a segment. Relative paths resolve beside the CSV. `condition` must be `still`, `natural_movement`, `talking`, `smiling`, `glasses` or `low_light`; `task` must be T1 (rest), T2 (speech) or T3 (arithmetic). Label UBFC-Phys rows `dataset=ubfc_phys`. Do not infer movement or appearance metadata from filenames/faces. Conditions and tasks are separate columns.

Record repeated scans for each person/condition/task, plus matched still recordings. Use repeated source segments or separate recordings so SD/MDC95 can be estimated within a person and task. Natural movement should include the prescribed nodding/turning up to 20°. The evaluator uses the bundled CPU MediaPipe Tasks model and real transformation matrices. It does not download a detector, derive predictions from labels or use dummy landmarks.

Each disjoint source block is at most twenty seconds; all policies use the same block starts. OLD uses its first ten seconds; NEW may consume later frames only when coverage needs extension. The report lists actual durations and missing scores. Latency in JSON is aggregation/feature time; it excludes shared detector extraction time.

Outputs: `metrics.json`, `report.md`, `acceptance_vs_sd.png`. They contain per-condition tier acceptance, paired subject/task shifts and 1,000-draw subject-cluster 95% CIs (seed 42), residual within-condition SD/CIs, SEM/MDC95, and separate T1–T2/T1–T3 within-subject AUC and paired d_z/CIs. Score direction is reversed only for AUC. Equal subject weights prevent prolific participants from dominating shifts/AUC. No between-person facial-offset variation is called repeatability error.

Adoption requires movement acceptance ≥90%, mean absolute subject shift ≤ the **OLD still MDC95**, movement SD no more than 30% above OLD on common cases, and common-case UBFC AUC loss ≤0.02 for each task separately. At least two paired/repeated subjects are required. Extraction failures block adoption. A missing criterion is FAIL. The stricter setting remains the default; the runner never edits frontend configuration automatically. 3-D must additionally reduce movement shift by ≥25% with no SD increase on the same complete cases.

Tolerance trades bias for acceptance. Expressions and pose change true geometry. The tiers never fabricate a score.

## Verification

```sh
cd frontend
npm test
npm run build
npx playwright test e2e/tolerance.spec.js
```

From the repository root:

```sh
MPLCONFIGDIR=/tmp/pause-mpl stress_math/.venv/bin/python -m unittest \
  stress_math.test_tolerance stress_math.test_tolerance_evaluation -v
```

The parity test consumes the exact fixture generator used by frontend tests. It compares all result fields recursively within 1e-6 for still, movement, talking, missing face, extended scans, yaw, 3-D, personal baseline and reacquisition gaps, plus a nonidentity inverse rotation. Synthetic tests establish software behavior only.
