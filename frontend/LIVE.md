# Live Browser Facial Index — robust-10s-2.0

> [!NOTE]
> This document describes the active `robust-10s-2.0` client architecture in Pause. It supersedes earlier experimental documentation regarding the 25-second continuous calibration and live graph flow.

## Overview

Pause provides an experimental 10-second facial check-in that calculates a deterministic **Calm index** on a 0 to 10 scale (where 10 reflects minimal tension relative to a reference). All camera capture, computer vision, and computation execute 100% on-device in WebAssembly. No video, audio, or facial landmark coordinates are ever recorded, uploaded, or transmitted to any remote server.

## Current Client Flow (`robust-10s-2.0`)

1. **Camera Consent and Initialization**: The user explicitly taps "Start 10-second scan" to grant camera access. The camera stream starts immediately to show a live mirror preview while MediaPipe Vision loads in parallel.
2. **Movement-Tolerant Acquisition**: The scan executes for a nominal 10 seconds (adaptive up to a 20-second hard cap if evidence is degraded by motion or transient head movement).
3. **Observation Sampling**:
   - Time slots of 0.20s partition the scan post-settling (first 1.0 second discarded for acquisition settling).
   - Up to 45 nominal slots are monitored (`toleranceConfig.json`).
   - Weighted slot coverage accounts for face speed, head pose angle, face size, and lighting conditions.
   - 3D landmark frontalization corrects for minor out-of-plane head yaw.
   - One Euro filtering reduces high-frequency landmark jitter without introducing lag.
4. **Scoring & Window Consensus**:
   - Four normalized geometric ratios (brow furrow, lip press, lip corner depression, jaw clench proxy) are compared against a reference.
   - **Generic mode**: Compares geometry against a canonical 3D facial reference.
   - **Personal baseline mode**: Compares geometry against the user's saved calm baseline captured during an intentional calm calibration scan.
   - Independent 1-second evaluation windows are scored.
   - Robust median aggregation with outlier consensus filtering ensures isolated facial movements or momentary distractions do not skew the score.
5. **Results & Transparency**:
   - The final score is categorized into three honest bands: Low facial index (0–3.5), Mid-range facial index (3.5–6.5), and High facial index (6.5–10).
   - Within-scan spread (range) is displayed to describe dispersion; it is explicitly not a confidence interval.
   - Acquisition quality metrics (slot occupancy, valid processed frames, agreeing windows) are surfaced in the acquisition details panel.
6. **Optional Neural Comparator**:
   - An optional MobileNetV3 image classification model is available as an offline research comparator.
   - **Defaults to OFF** to protect battery, compute, and avoid unnecessary ~17 MB downloads.
   - When enabled by the user in Settings, it computes a parallel stress-class probability on cropped face frames. It does **not** alter or influence the visible Calm index score.

## Verification & Parity

- **Unit tests**: Cover coordinate normalization, One Euro filtering, weighted median aggregation, temporal window consensus, and coverage calculations (`npm test`).
- **Playwright E2E**: Test camera startup lifecycle, cancellation, permission denial, fixture results, history persistence, responsive layout (1280px down to 360px), and offline PWA service worker behavior (`npm run test:e2e`).
- **Accessibility & Performance**: Audited with Axe-core (zero serious/critical violations) and Lighthouse CI (Performance, Accessibility, Best Practices, and SEO >= 0.90).
