# Pause: how the scores are produced and how the model was trained

Verified against the current frontend, original executed Colab notebook, saved checkpoints, training logs and evaluation artifacts on 2026-10-20. This explains the implemented system, including its limitations. It does not claim validated stress measurement. No new training was performed to write this report.

## 1. Two separate score paths

| Output | What produces it | Was it trained on our face dataset? |
|---|---|---|
| Main Calm index, 0–10 | MediaPipe landmarks → normalized facial geometry → fixed reference comparison → mathematical formula → window consensus | **No.** The formula and acquisition rules are engineering choices. MediaPipe itself is a third-party pretrained landmark detector. |
| Optional neural dataset-class output, 0–100% | Face crop → ImageNet-pretrained MobileNetV3-Small → our trained classification head → softmax → smoothing/aggregation | **Yes.** We trained a head and tried partial backbone fine-tuning on the supplied labelled still images. |

The neural probability is **not used to calculate or correct the main Calm index**. They are not fused in the current scan. Self-reported stress does not set either output. A high Calm index and a high neural stress-class output can therefore disagree. Neither establishes what the participant actually feels.

## 2. System layout and privacy

- Frontend: React19, Vite7, JavaScript and CSS. MediaPipe runs face analysis; ONNX Runtime Web runs the optional classifier through WebAssembly.
- The GitHub Pages architecture is a static frontend. The live camera calculations do not require the historical FastAPI/SQLite backend or a cloud LLM. Local development uses a loopback server.
- Camera frames stay in browser memory. The app does not record or upload raw video, images or landmarks by default. Camera access is explicit and tracks are released on completion/cancellation/failure.
- Standard results are saved only through the Save action. The optional guided study requires an explicit Begin/consent action and then saves derived completed outcomes, including failures, in that browser. Its JSON download is a derived-data export, not a recording.
- The model/MediaPipe files are loaded as assets. Network loading of software assets is different from uploading camera data. Training images were separately uploaded to Colab/Drive for the authorized experiment.

## 3. Camera acquisition: what “10 seconds” means

1. Request camera video without audio, preferably640×480. Actual resolution depends on the camera/browser.
2. Load MediaPipe FaceLandmarker in VIDEO mode with CPU execution and facial transformation matrices. It can detect up to two faces so multiple-face scenes can be rejected.
3. Process a new video frame at most about once every95ms, roughly10 processed observations/second when the device keeps up. This is not the camera's native frame rate.
4. In the standard path, require approximately1 second of acceptable positioning before capture starts. A25 second wall-time cap bounds positioning/capture, after initialization. Permission/model startup may add separate delay.
5. Once started, the 10 second capture clock does not pause or compress bad periods. Invalid observations and missing time must not become repeated good frames.
6. Exclude the first capture second from geometric aggregation. The remaining9 seconds contain45 slots of 0.2 seconds and9one-second windows.
7. Compute the result, stop the camera, then display it. A failed scan returns no aggregate score.

The movement-tolerant path is separate and may run10–20 seconds. `tolerance=0` explicitly chooses the standard path; the prospective policy also forces that path. Do not combine these acquisition versions into one repeatability series.

## 4. Framing, brightness, pose and mouth checks

The following are fixed engineering gates, not learned medical thresholds:

| Check | Current standard-path rule |
|---|---|
| Face count | Exactly one visible face. |
| Brightness | A64×48sample estimates mean RGB brightness inside the face bounding box; the framing checks reject values below18 or above240 on the 0–255scale. This is not skin-tone or physiological measurement. |
| Face size | Normalized width≥0.15 and height≥0.20; width≤0.85 and height≤0.95. |
| Position | Face bounding-box centre within0.24of image centre on both normalized axes. |
| Movement | Face-centre displacement≤0.05between processed observations. This legacy check is per observation, not a validated motion metric. |
| Pose | Acquisition first checks absolute pitch≤45° and yaw≤35°. QuickIndex then checks absolute pitch≤38° and yaw≤30°. Both checks must pass when pose is present. |
| Mouth | QuickIndex drops rows with mouth aspect ratio>0.32. A separate mouthOpen display flag uses>0.50, so flags alone do not describe every rejected row. |

Missing pose is currently allowed by these strict-path checks; it is not reconstructed or guaranteed frontal. Blink/eye measurements may be computed as auxiliaries but do not enter the generic three-feature index. Ordinary blinking is not a stress measurement.

## 5. Landmark normalization and exact geometry

MediaPipe supplies478 landmarks. Convert x/y to pixel coordinates, then align the face with a fixed75-point canonical reference:

- Subtract the 75-point centre to remove translation.
- Use dot/cross alignment to remove in-plane rotation.
- Divide coordinates by the outer-eye distance between landmarks33and263 to reduce image-scale effects.

This is2D normalization. It does not fully remove out-of-plane head rotation, expression, perspective, detector error or differences in face shape.

Let `d(a,b)` be Euclidean distance between normalized landmarks and `w=d(61,291)` be mouth width. Tiny denominators are protected with a1e−8floor.

| Feature name in code | Exact construction | Interpretation limit |
|---|---|---|
| `brow_furrow` | `−[d(107,336)+(d(105,158)+d(334,385))/2]` | Geometry proxy, not measured muscle tension. |
| `lip_press` | `−[d(0,13)+d(14,17)]/w` | Lip geometry, not a force/pressure sensor. |
| `lip_corner` | `atan2(corner·down,w/2)`; corner is the mean mouth-corner position minus mean lip-centre position; down is the eye-line perpendicular oriented toward the chin | Expression/pose-sensitive angle. |
| `jaw_clench` | `d(234,454)/d(10,152)` | Face width/height ratio, not actual jaw-clenching force. Used only in personal-reference scoring, not generic scoring. |

Auxiliary MAR=`d(13,14)/w`. EAR averages left/right eye-opening ratios. No blood-pressure, cortisol, heart-rate, HRV or rPPG measurement enters this main browser formula.

## 6. Generic reference → z-scores →0–10 index

The generic reference is **not a person's relaxed baseline or a population-normal dataset**. It is constructed from the canonical mesh.

1. Compute each canonical feature value`c_i`.
2. Use hand-set spread parameters: brow 0.06, lip press0.04, lip corner 0.06; optional jaw 0.08.
3. Construct five reference rows: `c_i + f×spread_i`, with `f=[0,1,−1,0.5,−0.5]`.
4. Calculate reference mean`mu_i` and population standard deviation from those rows. Before flooring, that standard deviation is `spread_i×sqrt(0.5)`, not the spread parameter itself.
5. Apply the sigma floor: `sigma_i=max(raw_sigma_i,0.05×abs(mu_i)+0.001)`.
6. For a measured feature`x_i`, compute `z_i=clip((x_i−mu_i)/(sigma_i+0.000001),−3,3)`.
7. For`n`available scoring features, compute `r=sum(z_i)/sqrt(n)`.
8. Convert to the reversed display: `index=10×[1−1/(1+exp(−r))]`.

The generic path uses **three features**: brow, lip press and lip corner. Jaw is recorded for diagnostics but is not part of this generic score. If all feature deviations are zero, the index is5**by construction**. That is a formula midpoint, not an established stress threshold.

The fixed sigmoid mapping and spreads were not trained on the supplied images. They do not make the output a probability. The 0–10direction convention is a product choice, not proof that a value measures calmness.

For an optional saved personal reference, use its feature medians and `sigma=max(1.4826×MAD,0.05×abs(median)+0.001)`, then the same clipped-z/sigmoid structure over four features. The ordinary10 second generic scan does not require this calibration. The current calibration action obtains feature summaries through the scan flow; older offline modules also contain25 second rest-baseline experiments, which are a different protocol.

## 7. How frame measurements become one displayed score

- Within each0.2 second slot, take medians of valid feature observations.
- Within each1 second window, require at least two usable slots and take feature medians again.
- Calculate a fresh geometric index for each window. The current QuickIndex creates a fresh FixedIndex for each callback; the rolling/EMA state inside that class therefore does **not** smooth across QuickIndex windows. Other historical callers of FixedIndex may behave differently.
- Compute the median of measured window scores. Keep windows within1 point of that centre as the existing consensus.
- If acceptance passes, the displayed result is the median of those consensus window scores. It is not the index calculated from the overall feature medians shown in diagnostics.
- Keep all measured windows on the graph and identify stored exclusions. Missing windows remain missing.

The legacy rules can accept a scan with as few as35%occupied slots and3measured windows before additional visibility/consistency checks. Their80%slot/8window targets can produce warnings rather than rejection. They require a consensus containing at least60%of measured windows and compare early/late **filtered** medians within0.75 points.

This can mask terminal changes. Synthetic windows `[9,9,9,9,9,9,9,6,4]` produce9with limited acquisition status. Legacy slot occupancy also accepts a slot with any valid observation, so100%occupied slots need not mean100%valid observations.

The displayed within-scan variation uses `1.4826×MAD(all measured window scores)` around the final consensus score, clipped to0–10. It is robust dispersion, **not** a95%confidence interval, full observed range, physiological uncertainty or between-session repeatability bound. The UI now shows the full observed range separately.

## 8. What the prospective candidate changes

`policy=prospective-1` keeps the same numeric scoring function and adds fixed, versioned acquisition requirements:

- Each slot needs≥80%valid processed observations.
- Overall≥80%valid processed observations,≥45 observations after settling,≥80%slot occupancy and≥8measured windows.
- The unfiltered early/late median difference must be≤0.75 points.
- Reject when both first two or both last two measured window positions are outside the old consensus.
- Apply all existing rejection checks as well. Return no aggregate score/range on failure.

The policy is SHA-256fingerprinted, mirrored in Python and **not adopted by default**. Its cutoffs are unvalidated engineering priors, not parameters fitted to participant scores. History separates its acquisition version from legacy scans. Old pilot scans are not independent validation of this candidate.

## 9. Dataset preparation before neural training

Original supplied folder:12,275grayscale48×48 JPEGs, split into train/test and labelled`nostress`/`stress`.

1. Decode images and inspect dimensions/mode/corruption.
2. Group exact decoded-pixel duplicates using checksums, not filenames alone.
3. Quarantine all 8 images in4conflicting-label groups.
4. Remove284redundant same-label copies; prefer an existing test copy when a duplicate crosses the original split. Do not move test images into training.
5. Retain11,983 images. Verify copied-file checksums, decoded uniqueness and original-source preservation.
6. Split the cleaned9,519development images into training/validation through seed 42deterministic, within-label image-hash ranking. Preserve the 2,464existing test images separately.

| Frozen split | Nostress(0) | Stress(1) | Total |
|---|---:|---:|---:|
| Training |3,863|3,752|7,615|
| Validation |966|938|1,904|
| Designated test |1,224|1,240|2,464|

Images were user-supplied; label provenance, licensing and subject identities were not verified. Exact deduplication does not remove all near-duplicates or prove participant separation. The approved experiment was explicitly exploratory and image-level. Upscaling48×48 images cannot recover detail that was never captured.

## 10. Neural model architecture

We used **torchvision MobileNetV3-Small with ImageNet V1 pretrained weights**, not a model trained from scratch and not a vision-language model. ImageNet pretraining supplies general visual representations; it did not establish stress understanding.

```text
RGB image: 3×224×224, float32
  → MobileNetV3-Small convolutional features
  → global adaptive average pooling
  → flatten: 576 numbers
  → Linear(576→128)
  → BatchNorm1d(128)
  → ReLU
  → Dropout(p=0.20)
  → Linear(128→2)
  → two logits: [nostress, stress]
```

The backbone uses MobileNetV3's inverted residual/depthwise-convolution structure, nonlinearities and squeeze/excitation components. We removed its original ImageNet classifier and attached our head.

Verified parameter counts: backbone927,008; head74,370; total**1,001,378**learnable parameters in the architecture. The model also has non-parameter state such as BatchNorm running statistics. The 576 features are learned embeddings; they are not named brow, pulse or stress biomarkers.

## 11. Phase-by-phase training actually executed

### A. Frozen feature extraction—not stress training yet

- Convert grayscale files to three-channel RGB.
- Use official ImageNet V1preprocessing: resize shorter side to256, centre-crop224×224, convert pixels to0–1tensors, normalize channels with means`[0.485,0.456,0.406]`and standard deviations`[0.229,0.224,0.225]`.
- Run the pretrained backbone in evaluation/inference mode, frozen, without gradients.
- Batch size 64; output one 576-dimensional float32vector per image.
- Save training and validation feature chunks with image IDs, labels, input/model/environment fingerprints and checksums. Reuse only verified chunks after interruptions.

### B. Head-only supervised training—selected winner

| Setting | Actual executed value |
|---|---|
| Inputs | Cached576-dimensional embeddings from7,615 training images |
| Trained component | Custom head only:74,370 parameters |
| Epochs |15|
| Batch size |64; shuffled training loader, unshuffled validation loader |
| Loss |Unweighted CrossEntropyLoss on raw two-class logits |
| Optimizer |AdamW|
| Learning rate |0.001|
| Weight decay |0.01|
| Dropout |0.20 during training; disabled in evaluation |
| Validation frequency |After every epoch, on1,904 validation images |
| Checkpoint selection |Save head whenever validation balanced accuracy strictly improves |
| Learning-rate scheduler / early stopping / AMP |No such mechanisms appear in the executed loop; all 15 epochs ran |

An epoch is one pass through the training embeddings. There are119 batches per epoch (last batch63 images), so15 epochs perform1,785optimizer steps. Validation has30 batches. Cross-entropy penalizes incorrect class predictions; backpropagation updates the head's weights through AdamW. It never learns a continuous0–10stress target.

Best checkpoint: **epoch3**, validation balanced accuracy74.2522%, validation accuracy74.2122%. Later head-training loss continued to fall while validation performance worsened overall—evidence of overfitting rather than a reason to select the last epoch. Saved best-head weights, not the final-epoch head, were used for selection.

### C. Partial fine-tuning—tested but not selected

- Reconstruct the backbone from the saved pretrained checkpoint and attach the best head.
- Freeze all backbone parameter gradients except the last two feature blocks; keep the head trainable.
- Those two blocks contain350,544 parameters; with the 74,370-parameter head,424,914 parameters have enabled gradients.
- Read raw training images; resize256, **random** crop224, random horizontal flip, tensor conversion and the same normalization.
- Validation keeps deterministic centre crops. No random augmentation is applied to validation/test images.
- Batch64, two data-loader workers, pinned memory, shuffled training/unshuffled validation.
- AdamW with backbone learning rate0.00002, head learning rate0.0001, weight decay0.01. Same cross-entropy loss. Run5 epochs, saving best validation balanced accuracy.
- `full_model.train()`also places BatchNorm layers in training mode: freezing gradients alone does not freeze their running-statistic buffers. This matters when reproducing the experiment.

Best fine-tuned validation balanced accuracy: **68.0310%**, below the head-only model's74.2522%. It was rejected. The selected deployed-export checkpoint was verified to contain the original pretrained backbone and the exact saved best Phase 4head.

### D. Environment and reproducibility

Saved Colab environment: Tesla T4, CUDA13.0, Python3.13.15, PyTorch2.11.0+cu130, torchvision0.26.0+cu130, NumPy2.1.3 and Pillow11.3.0. These are values recorded by that run, not recommendations for a new installation. Training used the CUDA device with ordinary float32 code; no mixed-precision context appears in the executed loop.

Dataset split and later bootstrap/permutation routines use seed 42 where recorded. **The executed training loop does not establish a complete training RNG seed/state history**; importing`random`is not equivalent to seeding it. We cannot promise identical retraining outcomes. Exact training wall-clock duration was not retained as a verified benchmark.

The initial proposed configuration differed from the executed notebook. Actual head/fine-tuning epochs were15/5; report the executed values. Feature extraction is chunk-resumable. Training saved best state dictionaries and epoch logs, but not complete optimizer/scheduler/scaler/RNG/batch-cursor state. Thus it preserves best weights without proving exact mid-epoch resumption.

## 12. Selection, evaluation, explainability and export

1. Compare the two models using validation balanced accuracy only. Select the head-only winner.
2. The original “one-shot test” notebook silently fell back to the validation CSV when the test CSV was absent. Its74.21%accuracy/0.8125AUC were validation results, not a fresh test result.
3. Later evaluate the frozen ONNX export on all 2,464designated test images without training or threshold changes. Results:71.19%accuracy,71.17%balanced accuracy,0.7938ROC-AUC; see the readiness report for all metrics/intervals. Historical test inspection cannot be excluded.
4. Generate Grad-CAM examples as an exploratory visualization of image regions influencing the classifier. They are not proof of stress mechanisms or validated feature importance.
5. Export the selected full model to TorchScript and ONNX. The notebook used ONNX opset14, named input`input`and output`output`, dynamic batch dimension and the legacy exporter (`dynamo=False`). The original artifacts are approximately3.84MiBONNX and4.29MiBTorchScript.
6. Verify checksums/lineage and inference agreement. Twenty fixed random normalized inputs gave max PyTorch/ONNX logit error6.38e−6at tolerance1e−4; TorchScript matched exactly. A synthetic browser RGBtest gave native/browser error3.34e−6. These check numerical execution, not prediction correctness.
7. The notebook's “video validation” was actually100unrelated validation stills presented as a sequence. Its temporal gate returnedfalse. The final completion banner did not establish real-video validation.

## 13. Live neural inference in the browser

Enable through Settings or`ml=1`; the main index remains separate.

1. On a processed video tick with landmarks, take their bounding box, expand toward a square with 15%margin on each side, and clip it to the image boundary. Near boundaries the clipped crop need not remain square.
2. Draw the crop into a224×224canvas. Read RGBfromRGBApixels.
3. Divide by255, apply the ImageNet channel means/stds, and arrange float32data as NCHW`[1,3,224,224]`.
4. Load the selected ONNX file through ONNX Runtime Web's WASM backend, one WASMthread. Run inference without training/backpropagation.
5. Obtain logits`l0,l1`; compute numerically stable softmax: `p_stress=exp(l1−max(l0,l1))/[exp(l0−max)+exp(l1−max)]`.
6. Smooth inference outputs with `EMA_t=0.20×p_t+0.80×EMA_previous`; initialize with the first probability. Reset for a new scan.
7. Save the arithmetic mean of the collected **smoothed** probabilities as`averageStressProbability`. Classify stress when this mean≥0.50, otherwise nostress. The displayed percentage is100 times that mean.

Important implementation details:

- This neural path is not guaranteed to sample a fixed5 fps. It attempts inference on processed ticks when no previous inference is running; throughput varies with the device.
- The EMA coefficient is per inference, so its effective smoothing duration changes with inference rate. It is not a fixed physiological time constant.
- Neural collection is outside the geometric accepted-row branch. It can include positioning/settling ticks and face crops whose geometric row was rejected; it is not guaranteed to cover exactly the same9 seconds/windows as the mathematical score. It also aggregates available neural samples rather than requiring one sample per geometric slot.
- Live crop→direct224resize is different from the training-image resize256→centre-crop224pipeline. Tensor parity tests do not prove that these preprocessing paths are equivalent.
- The stored neural`confidence=2×abs(mean_probability−0.5)`is just distance from the class boundary. It is not calibrated uncertainty, accuracy or probability of being right.
- HFtransformer comparators and historical pulse/legacy experiments exist in the research code but are not this browser classifier and were not fused into the current result.

## 14. Why one person's scores can change

The geometric output responds to measured facial shape relative to an artificial reference. Mouth configuration, head pose/perspective, lighting-dependent tracking, camera position and detector noise can change those measurements without any actual stress change. Temporal consensus reduces some within-scan outliers; it does not establish between-scan repeatability.

The neural model learned associations with low-resolution dataset labels. Different expressions/crops/exposure and the still-image→video domain shift can change its probabilities. Matching scores would not by itself prove correctness either. We must not anchor a new score to an earlier one or adjust weights merely to make this participant's results agree.

## 15. Evidence still needed and current conclusion

The guided study checks5–10 minute completion intervals, retains failures and separates candidate/legacy acquisition versions. It records task labels and derived measurements after explicit consent. For evaluation, use the first eligible timed pair per person/condition as declared; preserve later pairs descriptively rather than choosing the best-looking one.

There is limited single-participant rest feasibility data, but not enough eligible multi-participant speech/arithmetic data, matched nuisance clips or reliability estimates to pass the frozen release gates. Speech/arithmetic are task conditions, not clinical stress labels. No valid live-app accuracy percentage follows from the still-image test.

**What is complete:** runnable MVP, two explained scoring paths, selected trained/exported image classifier, verified image metrics and numerical execution, transparent diagnostics, an opt-in versioned acquisition candidate, and study/evaluation tooling.

**What is not established:** clinically meaningful0–10stress levels, population repeatability, robust task discrimination, physiological interpretation, live calibration of neural probabilities, or readiness for a validated stress-measurement release. The release decision remains HOLD.

## 16. Source map

| Component | Source |
|---|---|
| Camera, sampling, gating and neural collection | `frontend/src/CameraScan.jsx` |
| Geometry/reference/z-score/index | `frontend/src/liveIndex.js`, `faceReference.json` |
| Acquisition clock | `frontend/src/scanState.js` |
| Legacy windows/consensus/dispersion | `frontend/src/scanReliability.js` |
| Prospective gates and frozen cutoffs | `frontend/src/prospectiveReliability.js`, `prospectivePolicy.json` |
| Neural crop/normalization/softmax/EMA | `frontend/src/mlInference.js` |
| ONNX/WASMloading and inference | `frontend/src/modelRunner.js` |
| Optional personal-reference storage | `frontend/src/baselineStorage.js` |
| Guided consent/timing/derived logs | `frontend/src/components/GuidedStudy.jsx`, `guidedStudy.js` |
| Python candidate mirror/evaluation | `stress_math/prospective_mirror.py`, `evaluate_prospective_study.py` |
| Original executed notebook and checkpoints | Private `outputs/training/pause_faces_v1/verification_2026-10-19/original_colab_artifacts/`; never bundled into the site |
| Dataset cleaning/freeze/feature extraction | Private preparation artifacts and manifests; exact hashes retained in verification outputs |

Private artifacts were inspected locally. Personal study data, model-training images and private checkpoints are outside Git. The public-facing report contains architecture, aggregate experiment statistics and limitations, not participant recordings.
