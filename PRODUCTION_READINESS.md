# Pause — final engineering and validation status

Reviewed 2026-10-20. **Experimental demo; validation release decision: HOLD.** This report supersedes earlier unqualified 'all phases complete' or 'production-ready' statements. No retraining, participant-score tuning, candidate adoption, Git push or deployment was performed in this completion pass.

| Phase | Outcome |
|---|---|
| Reporting corrections | Complete: explicit processed-observation validity and slot occupancy, recorded exclusions, observed range, non-confidence dispersion wording, failed-result diagnostic visibility. |
| Candidate policy definition | Complete: prospective-acquisition-1 frozen and fingerprinted. No optimization on pilot/test results. |
| Implementation and automated verification | Complete: opt-in JavaScript candidate, independent Python mirror, preserved legacy APIs/default, distinct history acquisition version, synthetic parity/boundary tests and production build. |
| Participant collection | Tooling and limited feasibility collection completed. Broader timed task/nuisance/participant validation remains pending; it cannot be completed by an unattended agent without real observations. No further informal retries are requested in this pass. |
| Evaluation and release decision | Available exported study analysed with the frozen rules. HOLD: insufficient participant/task/nuisance evidence. No validated reliability, clinical stress or production stress-measurement claim. |

## How scoring and training work

**There are two independent paths:** the main 0–10 Calm index uses a fixed mathematical formula on MediaPipe facial landmarks; the optional neural output uses an ImageNet-pretrained MobileNetV3-Small with our trained two-class head. The neural output does not set the main index, and neither uses the client's self-report as its target score.

The verified run extracted576-dimensional frozen image features, trained a74,370-parameter head for15 epochs with AdamW and cross-entropy, then tried5 epochs of partial fine-tuning. The head-only checkpoint won on validation and was exported; its architecture has1,001,378 parameters in total. Generic reference values, feature spreads, sigmoid mapping and acquisition cutoffs were not learned from this image dataset.

For the full camera-to-result equations, exact landmark definitions, reference construction, window/consensus rules, dataset cleaning/splits, model layers, optimizer settings, augmentation, actual Colab environment, checkpoint limitations, exports, browser preprocessing and known implementation gaps, read **[System and training details](training/SYSTEM_AND_TRAINING_DETAILS.md)**. That document is based on the executed notebook and saved artifacts, not just the earlier plan.

## Accuracy and ROC-AUC: what the results mean

**The image classifier scored 71.19% accuracy and 0.7938 ROC-AUC on the designated 2,464-image test split. These numbers describe matching the dataset's “stress”/“nostress” labels—not measuring a person's actual stress.** The geometric Calm index is a separate formula; it does not inherit the classifier's accuracy.

The selected model is MobileNetV3-Small with a trained classification head. Head training used 7,615 images, validation used 1,904 images, and the designated test split contained 2,464 images. The head-only model was selected using validation balanced accuracy; the fine-tuned alternative performed worse on validation. Our subsequent verification ran inference only, with no training or threshold tuning.

| Metric | Selected model: validation | Designated test split | Simple explanation |
|---|---:|---:|---|
| Accuracy | 74.21% | **71.19%** | Correct label on about 71 of every 100 test images. |
| Balanced accuracy | 74.25% | **71.17%** | Average of the success rates for the two labels, giving each label equal importance. |
| ROC-AUC | 0.8125 | **0.7938** | How well scores rank stress-labelled images above nostress-labelled images across decision thresholds. Higher is better; 0.5 is chance-level ranking and 1.0 is perfect ranking. |
| Precision | 72.42% | **70.54%** | Among images predicted “stress,” about 71 in 100 actually had that dataset label. |
| Recall / sensitivity | 76.97% | **73.39%** | Among stress-labelled images, about 73 in 100 were detected. |
| F1 | 74.63% | **71.94%** | One summary balancing precision and recall; higher is better. |
| Brier score | 0.1776 | **0.1862** | Average squared error of predicted probabilities against dataset labels; lower is better. This does not by itself prove that probabilities are calibrated. |

Accuracy, precision, recall and F1 use the fixed **0.50 decision threshold**. ROC-AUC considers ranking across thresholds. An AUC of 0.7938 means a randomly chosen stress-labelled image ranks above a randomly chosen nostress-labelled image about 79.38% of the time, with ties counted halfway. **It does not mean “79.38% accurate,” or that a user's stress estimate has 79.38% confidence.**

Validation was used for model selection, so its higher score is not an independent final accuracy claim. The original notebook's “test” output actually used the validation split; the table separates it from the later genuine inference run on the designated test images. We cannot establish whether those test images were inspected historically, so we do not claim a guaranteed untouched holdout.

### Where the test predictions were right and wrong

| Dataset label | Predicted nostress | Predicted stress |
|---|---:|---:|
| Nostress: 1,224 images | **844 correct** | 380 false alarms |
| Stress: 1,240 images | 330 missed | **910 correct** |

Overall, **1,754 predictions were correct and 710 were incorrect**. The false-alarm rate was 31.05% among nostress-labelled images; the miss rate was 26.61% among stress-labelled images. These describe dataset-label errors, not clinical false diagnoses. Because the labels are nearly balanced, always predicting the larger class would achieve about 50.32% accuracy.

### How uncertain are these estimates?

The test results include 95% bootstrap intervals, computed with 1,000 resamples and seed 42:

| Metric | Test estimate | 95% interval |
|---|---:|---:|
| Accuracy | 71.19% | 69.36–72.97% |
| Balanced accuracy | 71.17% | 69.34–72.96% |
| ROC-AUC | 0.7938 | 0.7771–0.8117 |
| Precision | 70.54% | 68.67–72.50% |
| Recall | 73.39% | 70.80–75.73% |
| F1 | 71.94% | 70.04–73.64% |
| Brier score | 0.1862 | 0.1776–0.1940 |

These intervals describe variation when resampling the available **images**. Subject identities were unavailable, so they are not participant-bootstrap intervals and may understate uncertainty if images from the same people are related. They also do not cover label mistakes, dataset bias, lighting/camera changes or the shift from small still images to live video. Exact duplicate removal does not prove participant separation.

### What is established for the live app?

- **Scan coverage:** whether acquisition rules accepted enough observations. Even 100% coverage does not establish correct stress estimates.
- **Within-scan variation:** dispersion during one scan, not a validated confidence interval or a promise that another scan will match.
- **Repeatability:** limited single-participant rest pairs have been collected. Population reliability, ICC and minimum detectable change are not established by this pilot.
- **Task discrimination:** valid multi-participant rest-versus-speech/arithmetic ROC-AUC, paired effect size (Cohen's d_z) and Wilcoxon comparisons are not established. Task labels themselves are not clinical stress ground truth.
- **Robustness:** matched lighting, resolution, compression and rotation effects remain unvalidated. Training-image preprocessing and live face cropping differ.
- **Speed and parity:** native CPU ONNX inference measured about 2.16 ms per image in one local run, excluding face detection, preprocessing and the rest of the scan. This is not end-to-end browser latency. Small numerical differences across PyTorch, ONNX and browser tests support implementation agreement, not stress accuracy.

**Release interpretation: promising image-label classification, but insufficient evidence for a reliable live stress-measurement product. The candidate remains experimental and the validation decision remains HOLD.**

## What was adjusted

- Scores are described as facial indices relative to a reference; band text does not assert observed calmness or tension.
- Neural output is explicitly a dataset-class output, not a calibrated probability of the user's stress.
- Legacy saved scores remain unchanged. Candidate remains opt-in; default behavior was not silently replaced.
- The evaluator no longer applies an undocumented global veto for any incomplete pair. Off-protocol pairs remain visible, count toward acquisition coverage, and are excluded from paired metrics. The predeclared release thresholds are unchanged; current study remains HOLD.
- Guided local study preserves consented derived outcomes, including failures, without recording/uploading camera media. Exports and personal reports stay outside Git.

## Verified evidence

- 59 frontend tests and production build pass.
- Four selected Python tests pass, covering candidate/legacy cross-language parity and study reporting, including positive/negative synthetic gate cases. Synthetic PASS fixtures are software tests, never participant results.
- Two frozen-export metric tests pass; frozen policy SHA-256 verifies unchanged.
- Earlier real artifact verification established chosen-weight lineage, matching Drive/app ONNX checksum, PyTorch/ONNX/TorchScript tensor parity and a synthetic native/browser parity check. These are implementation checks, not live stress validation.
- Image-classification results and their limitations are explained in the performance section above; the raw metrics are retained in the private verification outputs.
- Current consented study contains one participant, two eligible rest pairs, an incomplete pair and an off-protocol speech pair. These are feasibility observations, not evidence that the statistical release gates passed. Arithmetic and matched nuisance data are absent.

## Reproducibility and limitations

See [VERIFICATION.md](training/VERIFICATION.md), [CONSENSUS_REVIEW.md](training/CONSENSUS_REVIEW.md) and [the frozen candidate protocol](training/PROSPECTIVE_POLICY.md). Original model experiments did not save full optimizer/RNG/batch state; exact interrupted-training resumption cannot be certified retroactively. The live crop/resampling path differs from training-image preprocessing and still needs matched real-input validation.

Private final available-data outputs are under the workspace's sibling `outputs/training/pause_faces_v1/verification_2026-10-20/final_available_data_review` directory. They are not bundled with the site. The app remains usable for explicitly experimental local demonstrations; public deployment and a validated stress-product release are distinct decisions.
