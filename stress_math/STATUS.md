# Experiment status — 2026-10-10

Completed:
- Separate stress_math module; existing application code unchanged.
- Fixed 75 landmarks, canonical alignment, geometry features, pose rejection, blink tracking, pulse proxies, calibrated fixed index and temporal smoothing/gates.
- UBFC-Phys and generic manifest loaders; privacy-consented four-minute live recording with timestamp sidecar.
- Test-only evaluator with NEW vs each single feature, no-rPPG and all-available features on a fixed comparison cohort.
- Fixed sigma floor max(raw sigma, 0.05 * abs(mu) + 1e-3), with raw/effective sigma recorded.
- Fixed <40% coverage exclusions, per-video and T1/T2/T3/binary-label coverage, and explicit exclusion lists.
- Primary AUC/d_z/Wilcoxon p with subject-bootstrap CIs; threshold metrics secondary.
- 1000 within-subject label permutations, seed42; full null AUC distribution and corrected one-sided p.
- summary.md methods table plus updated report, plots, ablations, AU support and per-method timings.
- Nine synthetic unit/integration tests passed; includes <1% geometric feature change under random 2-D rotation/scale/translation.
- MediaPipe Face Mesh initialization verified on Apple M1 outside graphics-restricted sandbox.
- Generated-video decoding, no-face rejection, and cached reload passed (12 synthetic frames).
- Missing-dataset report generation verified: zero real videos, metrics unavailable.

Remaining verification:
- Real consenting webcam protocol and live index behavior.
- Authorized UBFC-Phys/other video dataset evaluation.
- Annotated AU validity and balanced robustness recordings.
- OLD adapter retained with "OLD has no video scorer"; OLD-vs-NEW comparison replaced by fixed baselines. Real predictive performance of all baseline methods remains unverified.

No training performed. No accuracy improvement established. No changes pushed or deployed to GitHub Pages; this Python module runs locally.
