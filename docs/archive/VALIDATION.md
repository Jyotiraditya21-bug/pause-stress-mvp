# Verification record — 2026-10-11

> Historical snapshot. See the current [task log](../../TASKS.md) and [validation roadmap](../VALIDATION_TODO.md).

Verified:
- 18 Python math/HF tests passed, including actual AutoImageProcessor with the fixed dummy classifier.
- Actual third-party model A and model B fp32 dummy-image inference passed on Apple M1 MPS; no training or fine-tuning.
- Actual model revision/license/parameter metadata exported in stress_math/results/hf/metrics.json. Zero labeled video sessions: predictive metrics intentionally unavailable.
- GitHub Pages source extension deployment 3b48e2a succeeded, and the downloadable archive includes hf_models.py/hf_evaluate.py.
- User-consented real camera model initialization, 25-second calibration, live graph and finish succeeded. No video was recorded or uploaded.
- Cancellation and navigation while camera initialization was pending removed/stopped the preview; late-resource disposal is covered by unit tests.
- User-consented disposable graph saving, reload/history/view, deletion and subsequent reload succeeded. The disposable graph was removed; no user graph values are included in this record.
- Populated history/results were checked at a narrow mobile viewport without page overflow; keyboard activation of graph view and exact-values disclosure succeeded.
- Nine frontend math/resource tests passed, including late resource cleanup after cancellation and timeout. Production build passed.
- Idle page hiding no longer produces a misleading camera error. One real updated camera session measured approximately 9.2 processed frames/s, 21.1 ms mean landmark inference and 24.1 ms mean analysis processing; graph values were not saved. The fix and processing diagnostics deployed successfully as fe96964.
- Model B synthetic warm MPS backend benchmark: batch 8, five repeats, approximately 33.05 ms per image; peak process RSS approximately 358.72 MiB. This excludes model loading, camera/landmarks and GPU-driver memory, and is not an end-to-end real-video benchmark. Full details are private/local results/hf/backend-benchmark.json.

Still requires inputs/controlled testing:
- Authorized participant-labeled video datasets or explicitly consented recorded rest/stressor sessions. The live browser graph does not record video and cannot substitute for those recordings.
- Real M0–M5 accuracy/CI/permutation evaluation on those inputs, including dataset overlap/licensing limitations. One person's camera session is not accuracy validation.
- Controlled low-light/glasses/yaw/multiple-face conditions, real denied/busy camera paths, actual tab-background/five-minute automatic stop, and broader isolated CPU/memory/device profiling.

No model-card accuracy is presented as app accuracy. No user-derived graph or face image is published in this document.
