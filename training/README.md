# Labeled camera training experiment

Status: pipeline prepared; no real training or dataset download completed.

## Selected candidate

UBFC-Phys has 56 people, video, BVP/EDA, task conditions, and pre/post anxiety reports. Author access page: https://sites.google.com/view/ybenezeth/ubfc-phys . Official downloads are access-protected. Dataset repository lists noncommercial terms: verify rights before commercial training or distribution.

Raw video occupies hundreds of GB. This Mac had approximately 2.4 GiB free during inspection. Do not launch full or half-dataset downloads to its internal drive.

## Data preparation required

Obtain official recordings through authorized access on external storage or compute. Extract the same MediaPipe features as frontend/src/CameraScan.jsx: means of left/right eyeBlink and browDown coefficients, plus mean consecutive face-centre displacement. Match the browser sampling rate (~10 Hz), quality checks, model version and 30-second windows. Reject poor windows; track rejection rates. Do not substitute wearable BVP/EDA values as camera features.

Required CSV columns:

```text
participant_id,label,meanBlinkCoefficient,meanBrowCoefficient,meanMovement
```

Use documented labels. Rest-versus-stressor task classification is an experimental proxy, not a directly measured stress rating. UBFC speech and arithmetic tasks have differing conditions; verify protocol/group labels before assigning targets. Speech may be an easy confound. Pre/post anxiety ratings must not be treated as per-frame stress labels.

Use half the participants for training and the remaining half for held-out testing. For all 56 people, that is 28/28. The trainer tunes regularization through group CV inside the training half. Participants must include both class conditions; no overlapping subject recordings across train/test. A request for only half the total dataset instead would require selecting 28 people and splitting those into train/test; that is a different experiment.

## Run once real features and rights are ready

Use a separate environment on storage with sufficient capacity:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python train.py --csv features.csv --dataset-name UBFC-Phys --label-definition 'Describe verified task labels here' --license-note 'Describe granted research/commercial rights here' --output artifacts
```

Outputs: metrics.json and model.json. Report includes accuracy, balanced accuracy, precision, recall, F1, ROC-AUC, Brier score, confusion matrix, dummy baseline, and participant-bootstrap confidence interval. Brier score measures probability error; logistic probabilities are not independently calibrated. Lab metrics cannot be advertised as real-world app accuracy.

No current app accuracy baseline exists because no stress classifier was previously enabled. Improved accuracy must be demonstrated against a baseline, not inferred from training or copied from a paper. Integrate model.json only after reviewing results and completing a matched-feature inference implementation.

## Colab notebook

Open Pause_training.ipynb using Colab File → Upload notebook. Run installation and Drive setup, obtain authorized recordings, and create manifest.csv in MyDrive/pause-training. Its columns are participant_id,video_path,label. Fill LICENSE_NOTE and LABEL_DEFINITION before extraction.

extract.py samples videos in 30-second windows and writes resumable per-video checkpoints plus features.csv to Drive. Process one small batch at a time and retain the full manifest; completed files use checkpoints even if their temporary video was removed. Do not change source contents under an existing path without invalidating its checkpoint. Train after sufficient participants are processed, then download pause-model.zip.

Notebook and scripts passed JSON/Python syntax checks only. Colab dependency installation, real-data extraction, browser/Python feature parity, runtime duration, and trained accuracy remain unverified. The current app has no learned stress predictor enabled.

## Frozen image-model verification

The earlier pipeline status above concerns the historical feature pipeline. For the separate `pause_faces_v1` image classifier, see [VERIFICATION.md](VERIFICATION.md) for the 2026-10-19 artifact audit, actual frozen-ONNX test results, runnable verification commands, manual Colab inputs and fixed prospective real-scan protocol. Historical “all phases complete” records do not establish live stress validity.

## Prospective acquisition candidate

See [PROSPECTIVE_POLICY.md](PROSPECTIVE_POLICY.md) for the frozen opt-in rules, unchanged legacy baseline and predeclared real-data protocol. The guided study and analysis commands are in the repository README. Candidate synthetic tests establish implementation behavior, not stress accuracy. Old participant scores are not new-policy validation data.
