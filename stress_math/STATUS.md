# Experiment status — 2026-10-11

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
- Real browser calibration/live/finish and pending-initialization cancellation verified; controlled robustness and Python recorded-session protocol still need verification.
- Authorized UBFC-Phys/other video dataset evaluation.
- Annotated AU validity and balanced robustness recordings.
- OLD adapter retained with "OLD has no video scorer"; OLD-vs-NEW comparison replaced by fixed baselines. Real predictive performance of all baseline methods remains unverified.

No training performed. No accuracy improvement established. The live browser graph is deployed. The Python module runs locally; verify publication of the latest optional HF package separately.

Optional HF extension:
- A/B inference and M0–M5 comparison/report code implemented with lazy dependencies; no fitting or training.
- Core suite: 17 passed, one optional-dependency test skipped; optional HF suite: all nine passed in the separate Torch/Transformers environment.
- Actual model A dummy-image inference passed on MPS at revision eef423100d32c018dac57c333100f4f5f7863fb1.
- Model B actual fp32/no-grad dummy-image inference passed on MPS at revision 32132bdc0b6c9ad71e47a905db5cdf0ae51de85d after disk space became available.
- Actual HF metadata report generated at results/hf/metrics.json: both immutable hashes, parameter counts and available license declarations recorded. Real-dataset metrics remain pending; zero labeled videos were evaluated.

Updated browser verification and remaining controlled/data-dependent work are recorded in ../VALIDATION.md and ../TASKS.md. Real camera processing diagnostics were verified after deployment; no labeled video evaluation has occurred.

Legacy extension (2026-10-11): supplied source copied unchanged to legacy/face_stress_mesh.py; headless H0/H1, fixed F1/F2, retained M0–M5 and math baselines, fixed ablations, UBFC task splits, manifest-only robustness and skin-tone groups, subject-bootstrap Holm comparisons, and requested plots/reports implemented. The 300-frame feature regression passes within 1e-6. Time-based score EMA is tested across 15/30/60fps; legacy 45-frame feature buffers intentionally remain frame-based. Full-rate gating and shared 5fps coverage are both reported; either below 40% excludes a video. Real labeled predictive evaluation remains pending (no authorized videos supplied).
Final verification: 24/24 Python tests passed with optional dependencies. Legacy source byte comparison passed. CLI help and no-dataset report/plot generation passed; existing module entry points remain compatible.
