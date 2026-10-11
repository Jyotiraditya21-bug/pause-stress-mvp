# Training-free facial behavior experiment

Separate Python module. Existing frontend/backend and deployed Pages app are unchanged. This is an experimental **stress-associated facial behavior index**, not a percentage of stress or a diagnostic measurement. No training, fitting of prediction weights, fine-tuning, threshold optimization, or supervised parameter selection occurs. Test videos are used only for evaluation; the first 25 seconds of designated rest provide the requested personal baseline mean and standard deviation.

## Run on an M1 Mac

Use Python **3.11 or 3.12** (MediaPipe 0.10.21 supports the legacy Face Mesh API; Python 3.14 does not).

```sh
cd /path/to/unzipped-folder-or-repository
python3.12 -m venv stress_math/.venv
stress_math/.venv/bin/python -m pip install -r stress_math/requirements-core.txt
stress_math/.venv/bin/python -m unittest stress_math.test_math -v
stress_math/.venv/bin/python -m stress_math.evaluate --dataset ubfc_phys --root /path/to/UBFC-Phys
stress_math/.venv/bin/python -m stress_math.evaluate --manifest /path/to/sessions.csv
stress_math/.venv/bin/python -m stress_math.evaluate --live
```

The local verification environment was created from Codex's bundled Python 3.12 with inherited packages plus isolated compatible math dependencies. For portable setup, use the fresh environment command above.

`--live` asks for explicit recording consent, runs two minutes relaxed then two minutes timed arithmetic, overlays the index after 25-second calibration, and creates local video, actual-frame timestamp sidecar, and manifest. Press q to cancel. Terminal/Python requires macOS camera access. Record extra complete sessions with glasses, low light, and approximately +/-15 degree yaw; edit manifest `condition` to `glasses`, `low_light`, `yaw_plus15`, or `yaw_minus15`. Each condition needs both task labels for AUC. No recording is uploaded.

## Manifest

```csv
video_path,subject_id,label,baseline_video_path,dataset,start_seconds,end_seconds,stressor_onset,condition,self_report,au_path
videos/rest.avi,p01,0,videos/rest.avi,Own,25,120,,normal,2,
videos/task.avi,p01,1,videos/rest.avi,Own,0,120,0,normal,7,
```

Required columns: `video_path,subject_id,label,dataset`. Paths are relative to the manifest. Labels are binary task labels, never inferred from image names. Optional baseline defaults to the first 25 seconds of the same video, but a task recording's first segment is only a legitimate baseline if it contains rest. Use a separate rest video for stressed sessions. `start_seconds/end_seconds` define segments. AU validation accepts an additional CSV with seconds in `time` and intensity columns `AU4,AU23,AU12`, aligned to the video clock. DISFA/BP4D labels must be converted to that format using their declared original frame rate; do not manufacture AU intensities.

UBFC-Phys loader recognizes `vid_sX_T1.avi`, T2, T3 recursively. T1 is rest, T2/T3 are stress-task labels; all use the subject's T1 first 25 seconds. Obtain authorized data via https://sites.google.com/view/ybenezeth/ubfc-phys and follow its license/access instructions. No download credentials are embedded. Missing files are warned and skipped. Other video datasets use the manifest loader; this module does not automatically access restricted archives.

## Fixed rules

- Detector: pretrained MediaPipe Face Mesh, refine_landmarks=True, 478 detector outputs; geometry uses the hardcoded 75-point subset. Fixed MediaPipe canonical face reference (468 vertices plus explicitly constructed iris references), independent of test subjects. 2-D similarity/Procrustes alignment and inter-ocular scaling. Head pose uses solvePnP, rejecting absolute yaw/pitch >35 degrees; this is approximate monocular pose.
- EAR threshold .20, blink durations .05–.8 s, rate over up to 20 s. MAR >.35 or downward-corner angle <-.12 rad gates scoring. These are provisional fixed engineering thresholds, not clinically validated rules.
- Lip press = negative visible lip thickness / mouth width; thinner lips increase this proxy. Brow furrow is negative inner-brow and brow-to-eye distances. Lip corner is downward angle. Jaw proxy is normalized jaw width / face height. Jitter combines pose variability and landmark velocity variability over 5 s. MAR and blink duration are reported features, not additional score terms.
- Green channel forehead/cheek ROIs, 25 s window, bandpass .7–3 Hz, Welch peak, rudimentary peak/noise gate. Skip below 15 FPS or inadequate/gapped/noisy data. RMSSD uses peak intervals; it is a **noisy camera pulse variability proxy**, not ECG-grade HRV. No unsupported HRV value is imputed.
- Before z-scoring, effective sigma = max(raw sigma, 0.05 * abs(mu) + 1e-3). Feature z clips to [-3,3] with denominator effective sigma+1e-6. Equal fixed weights, HRV negative and all other chosen stress-oriented proxies positive. Aggregate over available baseline-calibrated features, sigmoid to 0–100, rolling 5 s aggregation, alpha=.1 EMA updated at most 10 Hz. Gated/invalid scores are missing, not held values in evaluation. The initial baseline maps to 50; the decision is strictly S>50. This threshold has no clinical interpretation. The fixed sigma floor limits instability from near-zero baseline variance; it is not estimated from test outcomes.
- Giannakakis et al. (2017), DOI 10.1016/j.bspc.2016.06.020, motivates studying facial cues; **this formula and its equal weights are not claimed to reproduce that paper's validated method**. Reference: https://users.ics.forth.gr/ggian/publications/journals/2017%20Giannakakis%20Stress%20and%20anxiety%20detection%20using%20facial%20cues%20from%20videos.pdf
- Canonical asset source: https://github.com/google-ai-edge/mediapipe/blob/master/mediapipe/modules/face_geometry/data/canonical_face_model.obj (Apache-2.0; license included).

## Evaluation/output

One mean score per labeled video/segment is used. **Primary** metrics are ROC-AUC, paired Cohen d_z and Wilcoxon p, each with subject-cluster bootstrap 95% CI (1000, seed42). Duplicate subject draws preserve paired-difference multiplicity; undefined resamples are omitted, with valid counts recorded. Subject IDs are namespaced by dataset. Threshold metrics (S>50) are **secondary**: baseline =50 by construction at the feature means, not a clinical cutoff. Average precision PR-AUC, distributions, Spearman self-report, calm stability, latency and AU validation remain available.

Compare NEW with every single score feature alone, NEW without HR/RMSSD and NEW with all available features. Identical videos, frames, gates, normalization and fixed weights apply to every method. If a single feature cannot score any video in the fixed eligible cohort, that method's comparison is unavailable for the whole cohort; it does not silently use a smaller sample. All-available NEW may use fewer than eight features when pulse is missing; no imputation occurs.

Coverage is the percentage of all evaluation-segment frames remaining after no-face/pose rejection and speech/smile gating. The denominator includes rejected frames and excludes the calibration segment. Videos below **40%** are flagged, listed, and excluded from classification, ablations and permutation metrics for all methods; exactly 40% is eligible. Per-video coverage and macro/weighted means for T1/T2/T3, binary labels and other named conditions are reported, including excluded videos. Summary coverage is mean method-score availability over eligible videos.

Permutation freezes the NEW predictions and shuffles task labels **within subject** 1000 times, seed42, preserving each subject's label counts. The JSON includes all 1000 null AUC values, null mean/reference interval and one-sided p = (1 + count(null AUC >= observed AUC))/1001. No exchangeable within-subject labels means no valid permutation test. Nothing is trained or selected using these results.

Outputs: `results/metrics.json`, `summary.md` (one pooled methods table), `comparison.md` (primary estimates and CIs per dataset), `report.md`, `roc_new_vs_baselines.png`, `score_over_time.png`, `ablation_bar.png`, `permutation_null_auc.png`. The previous `roc_old_vs_new.png` filename is retained as an alias containing the new baseline plot. In the shuffled-label summary row, AUC brackets show a **null reference interval**, not a bootstrap CI; d_z and ms/frame are N/A. Full d_z and Wilcoxon CIs are in comparison.md/JSON. Empty inputs still produce outputs with unavailable values.

Efficiency per method includes the shared extraction/feature pass plus that method's scoring time; pulse is computed once for all methods, so these timings do not measure an optimized pulse-free extractor. Null permutations reuse scores and have no inference timing. Cache stores identifiable landmarks/ROI summaries; keep it private. Extraction timings may come from cache. Source fingerprint/video path-size-mtime invalidates the cache; delete cache to force regeneration after replacing videos or timestamps.

**OLD limitation:** `frontend/src/scanMetrics.js` reports scan quality and mean coefficients; it does not assign video stress scores. `old_adapter.score_video` therefore returns missing scores on the same extracted frame timeline. The adapter still reports "OLD has no video scorer"; primary comparisons now use NEW versus fixed feature baselines. No questionnaire self-report is substituted for OLD predictions. This limitation is recorded in every report.

Speech/smile gating can suppress much of T2; inspect coverage. Accuracy on task labels would not establish accuracy at measuring a person's stress. Camera operation and real dataset performance require real recordings and are not established by synthetic unit tests. This Python experiment does not run on GitHub Pages.

## Optional third-party pretrained comparators

Install the optional full requirements only when using pretrained inference:

```sh
stress_math/.venv/bin/python -m pip install -r stress_math/requirements.txt
stress_math/.venv/bin/python -m stress_math.evaluate --hf-models --dataset ubfc_phys --root /path/to/UBFC-Phys --output stress_math/results/hf
stress_math/.venv/bin/python -m stress_math.evaluate --hf-models --manifest /path/to/sessions.csv --hf-batch-size 8 --output stress_math/results/hf
stress_math/.venv/bin/python -m stress_math.hf_models --smoke-test --model A
stress_math/.venv/bin/python -m stress_math.hf_models --smoke-test --model B
stress_math/.venv/bin/python -m unittest stress_math.test_math stress_math.test_hf -v
```

The standard evaluator and core tests still work without torch, transformers or huggingface_hub. They are lazy imports in the optional inference module. Existing APIs and CLI commands are retained; `--hf-models` selects the additional protocol. `--hf-cache` sets the model-artifact directory; score caches live under the usual cache/hf_scores directory. `--hf-revision-a` and `--hf-revision-b` accept exact commits or refs; the resolved immutable hash is recorded and used for every model/processor download.

Models: A = TheBgGirl/fer-stress-vit, softmax P(stressed); B = HardlyHumans/Facial-expression-detection, softmax P(anger)+P(fear)+P(sad)+P(disgust). Indices are read from the loaded config.id2label, matched case-insensitively; missing/ambiguous labels fail explicitly. RGB crops use the MediaPipe face box plus 15% margin on each side. Sampling uses the first decoded frame per 200ms bucket (at most 5fps). AutoImageProcessor preprocessing, fp32 batch inference, eval mode, torch.no_grad(), MPS if available else CPU. Missing pretrained prediction weights are rejected rather than randomly initialized.

Compare M0 existing math S; M1/M2 100*sigmoid of each pretrained probability's personal rest-baseline z; M3 = 100*sigmoid(mean(z_M0,z_M1,z_M2)); M4/M5 use the corresponding two z values. Scalar z_M0 for fusion is calibrated against math S during rest. Every scalar normalization uses max(raw sigma, .05*abs(mu)+.001) and clips z to [-3,3]. All weights are equal, fixed in code; no training or label-based tuning occurs.

All methods use the same sampled frames, windows and complete-case intersection after pose and speaking/smiling gates. Rest calibration uses the shared first 25 seconds. Missing predictions/insufficient baselines or common coverage below 40% exclude the video from every comparison. Per-component coverage before intersection is recorded so the cause is visible. This is deliberately more restrictive than the math-only cohort; compare M0 with others **within this optional report**, not with the earlier full-frame report on a potentially different cohort.

Each method has AUC/paired d_z/Wilcoxon subject-bootstrap CIs, coverage, ms per 5fps comparison sample, learned parameter count, and its own 1000 within-subject label permutations. Paired subject-bootstrap AUC differences vs M0 and descriptive Spearman agreement between session means of M0/M1/M2 are included. Counts exclude the shared MediaPipe detector. Timings compose the shared extraction/feature pass with relevant model crop/decode/inference and scoring costs; one-time loading and baseline calibration are excluded. Cached timings refer to their original inference run. AUC-difference bootstrap p-values are approximate and centred under the null.

Model names, resolved revision hashes, full repository license text when present, otherwise published license declarations or null, are recorded in metrics.json. Model A's card does not document training data/participant splits sufficiently to exclude train/test overlap with UBFC-Phys. Model B predicts emotions; emotion probabilities are not stress measurements. These are third-party pretrained weights, not trained by us. No model-card benchmark number is presented as this app's accuracy.

Weights total roughly 687 MB for the two fp32 ViTs, in addition to Python libraries/caches and dataset storage. Use a cache on a disk with enough space. Local videos/crops are never uploaded for inference. The dummy-image smoke CLI downloads real pretrained weights; the unit dummy-image test uses a fixed test-only classifier with the real AutoImageProcessor and torch, and does not establish pretrained accuracy.

This optional Python comparator path is not included in the browser live score or executed on GitHub Pages.

## Legacy heuristic comparison (fixed, no training)

The supplied `legacy/face_stress_mesh.py` is preserved byte-for-byte. Run the
headless experiment from the repository root with Python 3.11/3.12:

```sh
stress_math/.venv/bin/python -m pip install -r stress_math/requirements-core.txt
stress_math/.venv/bin/python -m stress_math.evaluate --legacy-heuristics --dataset ubfc_phys --root /path/to/authorized/UBFC-Phys --output stress_math/results/legacy
# Optional pretrained M1–M5 and F2; installs dependencies but never trains:
stress_math/.venv/bin/python -m pip install -r stress_math/requirements.txt
stress_math/.venv/bin/python -m stress_math.evaluate --legacy-heuristics --hf-models --manifest /path/to/sessions.csv --output stress_math/results/legacy_hf
stress_math/.venv/bin/python -m unittest stress_math.test_math stress_math.test_hf stress_math.test_heuristic -v
```

Without `--hf-models`, M0/H0/H1/F1 and ablations run without Transformers;
pretrained methods are explicitly unavailable. With the flag, every comparator
uses the same complete-case 5fps frames and videos. Existing evaluation commands
and module APIs continue to work. The unchanged legacy camera script requires
MediaPipe and opens a camera only when explicitly executed as a script; it is
never imported by the port or evaluator.

Manifest required columns: `video_path,subject_id,label,dataset`. Optional:
`baseline_video_path,start_seconds,end_seconds,condition,task,skin_tone`.
For UBFC use `task=T1|T2|T3` when `condition` describes `normal`, `low_light`,
`glasses`, `yaw_plus15`, or `yaw_minus15`; standard UBFC filenames also identify
these tasks. Only actually supplied condition/skin-tone metadata is analyzed.
No skin tone is inferred. When the video is its own rest baseline, evaluation
starts no earlier than 25 seconds even if an earlier segment start is supplied.

Outputs: `metrics.json`, `comparison.md`, `report.md`, one-table `summary.md`,
`group_ablation.png`, `task_split_auc.png`, `roc_all_methods.png`. JSON includes
all primary bootstrap intervals, secondary threshold metrics, per-video and
per-label coverage, speaking-gate percentages, excluded and failed videos,
1000-shuffle null distributions, Holm-adjusted pairwise AUC differences, model
provenance/licenses/parameter counts, correlations and feature ablations.
Existing single-feature and no-rPPG math baselines are retained on the same
comparison cohort. Missing videos produce unavailable metrics, not results.

H0/H1 weights/scales are unvalidated engineering priors. Texture/colour depends
on lighting and skin tone; mouth features depend on speech; task labels are
not clinical stress measurements. The 0.316-second EMA is time-based, but the
legacy gaze/jitter features intentionally retain 45-frame windows for parity.
Feature ablations remove smile relief when smile_lift is removed. H0 extracts
without gates; comparison masking is applied afterward for fair paired metrics.
The deployed browser index is unchanged by this offline extension.
