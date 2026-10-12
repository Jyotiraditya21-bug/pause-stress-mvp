# Live browser facial index

The UI no longer accepts or displays a questionnaire stress rating. Open Live, consent to local camera processing, enable the camera, then choose Calibrate and start live graph. Relax, face the camera and stay quiet for the first 25 seconds.

After calibration, a fixed mathematical facial index updates on camera frames at up to 10 Hz; the graph samples about once per second. The requested axis is 0 = high stress, 10 = no stress. These are experimental labels, not clinical measurements. The transformation is (100 - S)/10, so baseline feature means map to 5/10, not 10. Facial expression changes cannot establish how stressed an individual is.

The browser uses MediaPipe Face Landmarker, the canonical 75-point reference and a 2-D similarity alignment. Geometric features, blink events, and 5-second pose/landmark motion variability feed the fixed index. Effective sigma = max(raw sigma, 0.05 * abs(mu) + 1e-3), z clips to [-3,3], equal weights, rolling 5-second aggregation, alpha=.1 EMA. Pulse/HRV is omitted. Browser pose comes from the approximate MediaPipe transformation matrix rather than Python solvePnP, so full detector/pipeline parity is not established.

No reading is emitted before calibration. Baseline requires at least 30 usable frames and 40% usable coverage. Frames with poor brightness/framing, multiple/missing faces, absolute yaw/pitch >35 degrees, MAR>.35 or smile-corner gate are withheld. The graph breaks at unavailable readings. Aggregate results are withheld below 40% post-calibration coverage or without any score samples.

Sessions end on Finish, Cancel, navigation, tab hiding, errors, or the five-minute limit. Browser recording is never enabled; no video or landmarks are uploaded or persisted. Saving graph time/value samples and summary requires an explicit checkbox. These sessions use pause-camera-sessions-v2 storage, separate from existing pause-checkins-v1 questionnaire history, which is preserved. No Gemini call is made by the current UI.

Verification: six Node tests, synthetic Python/JavaScript geometric-feature and score parity, graph gap/label/accessibility rendering, and production build passed. Browser UI contains no stress-rating input and requires camera consent. Real webcam behavior and real-dataset accuracy remain unverified.

Run tests: node --test frontend/src/liveIndex.test.js

MediaPipe output/pose references: https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker/web_js and https://github.com/google-ai-edge/mediapipe/blob/master/mediapipe/framework/formats/matrix_data.proto. The derived canonical reference uses MediaPipe's Apache-2.0 asset; public/LICENSE.mediapipe includes its license.

2026-10-11 validation: real camera initialization, 25-second calibration, live graph, finish and pending-initialization cancellation passed in the in-app browser. Consented disposable graph saving, reload/history/view and deletion/reload passed. Populated history/results and keyboard access to exact values were checked at a narrow mobile viewport without horizontal page overflow. The test graph was deleted, and no video was saved. Idle-page hiding no longer emits a false camera error. Resource initialization now times out after 30 seconds and disposes of late streams/models; three lifecycle resource tests cover success, cancellation and late resolution. Session FPS, mean detector time and total processing time are now reported as technical diagnostics. Controlled robustness conditions and labeled accuracy evaluation remain pending.

## Current client flow — 2026-10-11

The default page is the camera scan. One Start button authorizes local camera
processing; after model/camera readiness, a 10-second countdown starts
immediately and automatically stops the camera and opens Results. No personal
calibration, questionnaire, manual finish button, or persistent saving is in
this flow. Results show the median of independent one-second geometric scores
and the scan graph. The first second settles acquisition inside the same ten
seconds; it is not used to estimate a personal reference. At least 80% of the
remaining 45 time slots and eight of nine one-second windows must be usable.
Each window uses per-slot feature medians, then a feature median across slots.
There is no cross-scan memory or anchoring to a previous score.

QuickIndex uses fixed canonical MediaPipe geometry as engineering reference
for four geometric channels. It uses no participant baseline, no blink-rate
or pulse estimate, and no learned stress model. It is unvalidated and anatomy,
expression and lighting can confound its result. The offline H0/H1/M0–M5
25-second rest evaluation protocol remains unchanged and does not validate the
new quick browser scoring method.


## Repeatability correction — 2026-10-11

QuickIndex v2 replaces the overlapping rolling average/EMA with independent
one-second windows and median aggregation. Canonical reference, geometric
features, sigma floors and the per-observation score formula are unchanged;
we did not flatten scores or fit parameters to make retests agree. Missing time
counts as missing coverage even if the few received frames are all valid.
The two-face detector remains enabled; explicit feature filtering supplies
noise suppression while preserving multiple-face rejection.

Fixed engineering acquisition rules: |yaw| and |pitch| <=15 degrees, tighter
framing, face-region brightness (rather than whole-frame/background brightness),
90th–10th percentile window-score spread <=1 point, early/late-window median
difference <=0.75, within-scan pose span <=6 degrees, and brightness span <=30
on the 0–255 scale. These are provisional quality rules, not clinical cutoffs.
A failed check produces a specific retry reason and withholds the score/graph.
Consistent systematic bias between scans can still pass these checks.

Verification: 19 frontend tests passed. Run the reproducible synthetic check:
`node frontend/scripts/repeatability.mjs`. Twenty synthetic repeats of the same
face geometry with seeded tracking noise and startup perturbations produced a
2.750-point range (SD 1.238) with the previous algorithm versus 0.310 (SD 0.083)
with v2; all twenty were accepted. This is a specific synthetic regression,
not an estimate of human performance, cross-device stability, or stress accuracy.
Real repeat scans 5–10 minutes apart still require participant verification.

## Unavailable-result correction — 2026-10-12

Ordinary pose/lighting variation is now a lower-confidence warning when the
geometric readings remain consistent, rather than an unconditional score veto.
Window consensus requires at least three and 60% of available windows within
one point of the scan median, with support in both early and late parts of the
scan and <=0.75 early/late consensus difference. Isolated outlier windows are
excluded from the final median. This uses only the current scan.

Existing minimum acquisition coverage (35%, at least three windows) remains;
80% coverage/eight windows identifies higher quality. Limited-quality usable
results display their score and graph with the warning. No-face, severely
contradictory, or insufficient scans still withhold numbers and show the actual
most frequent frame-rejection reason when available. Validation uses synthetic
regressions, not a claim of real stress accuracy or guaranteed retest stability.
