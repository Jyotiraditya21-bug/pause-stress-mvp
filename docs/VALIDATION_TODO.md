# Validation Roadmap and Pending Evidence

This document lists the mandatory empirical evidence and reviews required before making any claim of accuracy, validity, or clinical/psychological measurement for the Calm index.

> [!IMPORTANT]
> The current Calm index is a training-free mathematical facial geometry index (scale 0–10, where higher indicates less tension-like facial geometry compared with a reference). It is **not** a validated stress measurement, medical diagnostic tool, or psychological assessment.

---

## 1. Evaluation on an Authorized Labeled Dataset (D0 / D1 / D2)
- **Status**: [ ] **NOT DONE**
- **Requirements**:
  - Acquire or record an authorized, participant-separated video dataset featuring resting conditions and verified acute stressors (e.g., TSST, mental arithmetic, Stroop).
  - Run the evaluation protocol without mixing frames from the same individual across training/reference and evaluation splits.
  - Compute paired AUC differences, subject-cluster bootstrap 95% confidence intervals, and permutation null tests.
  - Evaluate D0 (3-feature generic mode: brow furrow, lip press, lip corner).
  - Evaluate D1 (4-feature personal baseline mode: including static facial aspect ratio / jaw clench).
  - Evaluate D2 (fusion / multi-modal extension if authorized).

---

## 2. Repeatability Protocol on Repeated Scans
- **Status**: [ ] **NOT DONE**
- **Requirements**:
  - Conduct repeat-scan trials under controlled resting conditions and under deliberate minor posture/lighting variations.
  - Calculate two-way random intraclass correlation coefficients (ICC(2,1)) across repeated 10-second acquisition windows.
  - Verify that repeated resting scans within the same session yield stable scores within the estimated MAD uncertainty band.
  - Measure within-subject vs. between-subject variance to establish personal-baseline discriminability.

---

## 3. Pretrained Model and Asset Licensing Review
- **Status**: [ ] **NOT DONE**
- **Requirements**:
  - Review open-source and commercial redistribution licenses for MediaPipe FaceLandmarker `.task` and WebAssembly bundles (`@mediapipe/tasks-vision`, Apache 2.0).
  - Confirm compliance with offline redistribution and client-side web application deployment constraints.
  - Ensure attribution notices and third-party license disclaimers remain embedded in deployment artifacts.
