# Frozen-model verification — 2026-10-19

## Verified now

- Local frozen dataset: 7,615 training, 1,904 validation and 2,464 test images. All split hashes and all 11,983 image checksums match the freeze; no identical decoded-image ID crosses splits.
- Frozen ONNX SHA-256: `55a5cf41a63f71763127fc62e638975a7e35acf18d973c01591e1a658be36b5f`.
- Class 1 = stress, fixed probability threshold >0.5; official MobileNetV3-Small ImageNet V1 preprocessing. No training, threshold optimization or test-based model selection performed in this verification.
- Test-set ONNX results: ROC-AUC **0.79379 [0.77708, 0.81173]**, accuracy **71.185% [69.359%, 72.972%]**, balanced accuracy **71.171%**, precision **70.543%**, recall **73.387%**, F1 **71.937%**, Brier **0.18616**. Confusion matrix: TN 844, FP 380, FN 330, TP 910.
- CIs use 1,000 stratified **image** bootstrap draws, seed 42. Subject IDs are unavailable: these are not subject-cluster intervals or unseen-person results.
- Native CPU ONNX inference: approximately 2.16 ms/image, excluding preprocessing; hardware/session-specific, not browser scan throughput.
- Browser WASM and native ONNX agree on a synthetic RGB ramp: max absolute logit error `3.337860107421875e-6`, tolerance fixed at `1e-4`. This tests tensor normalization plus model inference, not face cropping or PyTorch equivalence.
- Browser test exposed missing JSEP assets and a Vite public-module import error. Runner now explicitly uses the WASM entry point and package-resolved module/binary URLs.

## Audit limitations

Historical `status.json` says all phases finished but also says training never started and data was never uploaded. TASKS.md and status.json disagree on reported validation metrics. Follow-up retrieval completed: 24 original artifacts and the executed notebook were downloaded directly from Drive. Original phase-6 JSON confirms validation_fallback (1,904 images), resolving the conflict in favor of 74.2522% validation balanced accuracy and 0.8125279 AUC. Local ONNX validation reproduction matches accuracy, balanced accuracy, F1 and AUC; Brier differs by only about 6.6e-8. The selected model exactly matches the saved Phase 4 head and saved pretrained backbone. Drive ONNX equals app ONNX by SHA-256. PyTorch versus ONNX passes on 20 seed-42 normalized random tensors (max logit error 6.3777e-6, fixed tolerance 1e-4); TorchScript error is zero. Native/browser synthetic parity also passes. Face crop/resampling parity and live-domain validity remain unverified.

The old notebook silently uses validation if test is absent and writes `test_predictions.csv` in both cases. Its Phase 8 uses 100 unrelated still images as a sequence, so EMA jitter reduction is **not real-video validation**. The actual saved temporal_gate_pass is **false** (SD 0.2701; smoothed mean jitter 0.05003); the final all-phases-complete banner ignored that failure. Its parity check compares PyTorch to TorchScript, not to ONNX/browser inference. Historical claims must be read subject to these qualifications.

Prior access to the held-out test set cannot be established. Results above are a frozen-export evaluation on the designated test split, not a guarantee of a previously untouched independent holdout. Dataset label provenance, license and participant separation remain unverified. These are dataset-label results, not clinical stress measurements.

## Reproduce without retraining

Install `training/requirements.txt` in a local virtual environment, then run from the repository root:

```sh
python training/verify_frozen_export.py --data /absolute/path/to/pause_faces_v1 --model frontend/public/models/pause_stress_model.onnx --out /absolute/path/to/new-private-results
python -m unittest discover -s training -p test_verify_frozen_export.py
```

Existing completed output directories are preserved and cannot be overwritten. Test predictions stay outside the repository. A rerun is verification, never permission to tune against the test results.

For the synthetic browser check, copy the generated `parity_fixture.json` to `frontend/public/verification-fixture.json`, run `npm run dev` in frontend, and open `/ml-verification.html`. The fixture contains no participant data. Full preprocessing parity still requires matched source-image/crop fixtures and the original PyTorch checkpoint.

## Remaining manual inputs

Artifact retrieval is completed automatically; no manual download is needed. Original files remain in Drive and a private local copy is under `outputs/training/pause_faces_v1/verification_2026-10-19/original_colab_artifacts` outside Git. No original predictions CSV was present in the run root; validation predictions have been reproduced locally.

Real participant sessions are still required for the protocol below. No camera recordings or uploads are authorized by this document itself. The user separately approved starting local, unrecorded sessions. Saving participant-derived scores needs explicit consent.

The executed training code differs from the proposed run configuration: it ran 15 head epochs and 5 fine-tune epochs. It saves best state dictionaries but not full optimizer/scheduler/RNG/batch state, so exact mid-epoch resumption is not established. These historical shortcomings cannot be repaired retroactively by relabeling phases.

## Fixed prospective real-scan protocol

This is an exploratory engineering pilot, not a clinical validation study. Freeze model, UI pipeline version, preprocessing, threshold and analysis code before collecting results. Never combine the geometric Calm index with neural probabilities into one analysis. Record them as separate methods; invert Calm index direction only when calculating stress discrimination.

- Target 20 consenting adults, two visits separated by 5–10 minutes under the same camera/light setup. Fewer participants may be reported as feasibility data, with no definitive pass claim. Voluntary speech/arithmetic tasks are task labels; users may stop at any time.
- At each visit collect two 10-second scans per condition: rest, neutral speech, arithmetic. Counterbalance task order across participants; allow a rest period between tasks. Record actual timestamps, task duration, camera/browser and algorithm/model hashes. Record self-report separately; never feed it into the predictor.
- Include unsuccessful scans with acceptance=false and reason, rather than silently dropping them. Report accepted/attempted coverage separately by participant, condition and method. No imputation or invented score.
- Store only consented derived scores and quality metadata by default. Any recording for matched nuisance transformations requires separate explicit recording consent and local-only storage. Use pseudonymous IDs; keep manifests outside Git.
- For matched clips, apply brightness ×0.6 and ×1.4, downscale to 320×240, JPEG quality 40 and rotations ±10°. Preserve timestamps and recompute the entire face/scan pipeline; do not perturb only the final score. Compare matched accepted clips and report acceptance changes too.
- Report within-subject ROC-AUC for rest vs speech and rest vs arithmetic separately, with 1,000 subject-cluster bootstrap draws, seed 42. Report within-condition pooled SD, single-measure SEM, MDC95, ICC(2,1) and Bland–Altman limits. Do not mistake SEM of an averaged score for single-scan SEM.
- Fixed discrimination gate: lower 95% CI bound >0.60 for **each** task comparison. Fixed nuisance gate: every mean absolute matched nuisance shift <0.5× the absolute within-person rest/task mean difference, for each task. A zero/undefined task effect cannot pass.
- Fixed repeatability engineering gate on the 0–10 display: MDC95 ≤1.0 point and ICC(2,1) lower 95% CI ≥0.75; accepted-scan coverage ≥80% in every condition. Neural probabilities must be reported on their native 0–1 scale (an optional ×10 display has no clinical meaning).
- Overall release gate requires all criteria plus full model/preprocessing parity. Missing data/uncertainty means **NOT ESTABLISHED**, never PASS. No threshold, gate, smoothing or weight changes based on these results; changes require a new model/pipeline version and fresh evaluation data.

Current decision: **NOT READY for a validated stress-measurement claim**. The experimental app can retain its explicit limitations; no deployment was performed by this verification.

Original-checkpoint inference parity can be reproduced without training:

```sh
python training/verify_checkpoint_parity.py --checkpoint /private/artifacts/chosen_model.pt --onnx frontend/public/models/pause_stress_model.onnx --torchscript /private/artifacts/pause_stress_model.pt --out /private/new-checkpoint-parity.json
```

Preprocessing/domain gap: original images use Resize(256) then CenterCrop(224). The live app selects a MediaPipe bounding box plus 15% margin and draws it directly into a 224×224 canvas. Tensor parity does not establish equivalence of those crop/resampling paths. Assess on matched real clips before changing the deployed preprocessing; no changes or tuning were made in this verification.

## Current completion decision

Artifact audit, original model lineage, image-test evaluation and normalized-tensor export checks are completed. Real scan validation has begun with explicit participant consent but has not produced an analyzable session. Aggregate scan/repeatability conclusions remain NOT ESTABLISHED. Consented personal outcomes are stored only in the private experiment directory, not this repository. No camera video, images or landmarks were saved/uploaded. Do not repeat scans until one succeeds and then discard earlier failures: retain all attempted outcomes in the denominator.

## Prospective window instrumentation

New standard scans at `?ml=1&tolerance=0&diagnostics=1` include nine derived window summaries in Technical scan diagnostics. Each includes features, score, consensus membership, usable-slot counts, and median/p10/p90 of pitch, yaw and face brightness over usable slots. Rejected/missing context remains unknown. Normal scan results do not retain this added payload. Raw video/images/landmarks are not included. Saving remains explicit. This does not alter scoring, acceptance or fusion and does not retroactively supply missing diagnostics for prior scans. Movement-tolerant mode is not covered by this new instrument.
