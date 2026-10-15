# Pause

Pause is an experimental, privacy-first web application that provides a 10-second **Calm index** (0–10, higher indicating less tension-like geometry relative to a reference). Processing runs entirely on-device inside your browser using MediaPipe FaceLandmarker; video never leaves your device.

> [!CAUTION]
> **Scientific and Medical Disclaimer**: The Calm index is an experimental geometrical indicator, **not** a validated psychological stress measure or medical diagnostic test. It cannot tell how stressed you feel. Do not use Pause for clinical diagnosis or treatment decisions. See [docs/VALIDATION_TODO.md](docs/VALIDATION_TODO.md) for required evidence before making any accuracy claims.

---

## Current Architecture & Two Operating Modes

1. **Generic Mode (Default)**:
   - Measures 3 dynamic facial geometry ratios: `brow_furrow`, `lip_press`, and `lip_corner`. Static facial aspect ratio (`jaw_clench`) is excluded from generic scoring to prevent anatomy from biasing cross-user scores.
   - Normalizes points against a generic canonical neutral face model, aggregates standard-normal z-scores ($r = \sum z / \sqrt{n}$), and transforms them via a reversed sigmoid scale into a score from 0 to 10.
2. **Personal Baseline Mode (Calibrate When Calm)**:
   - An optional 10-second calibration scan under relaxed conditions records your personal neutral feature distributions (`median` and `MAD` across all 4 features, including `jaw_clench`).
   - Stored in browser `localStorage` (`pause.baseline.v1`) with versioning (`algoVersion: "quick-2.0"`) and 30-day automatic expiration.
   - Subsequent scans score deviations relative to your personal resting baseline rather than an average face.

---

## Repository Structure

- `frontend/`: Production client-side static application (React 19, Vite 7, PWA, Playwright, Node 22). Deployed to GitHub Pages.
- `stress_math/`: Research and offline verification tools, benchmarking scripts, and Python mathematical parity mirrors (`deployed_mirror.py`).
- `backend/`: Historical FastAPI / SQLite prototype from early explorations (not used in the production web scan).
- `docs/`: Deployment guides ([DEPLOY.md](docs/DEPLOY.md)) and validation roadmaps ([VALIDATION_TODO.md](docs/VALIDATION_TODO.md)).

---

## Running the Web App Locally

Prerequisites: Node.js 22+.

```sh
cd frontend
npm ci
npm run dev
```

Open `http://127.0.0.1:5173/` in your browser. Camera access requires `localhost` or HTTPS.

### Production Build & Preview

```sh
npm run build
npm run preview
```

---

## Testing & Quality Assurance

### Frontend Unit Tests
Runs 27 isolated unit tests validating geometry invariance, baseline storage, uncertainty range MAD calculation, and state machine transitions:

```sh
cd frontend
npm test
```

### End-to-End & Accessibility Tests
Runs Playwright e2e tests on Chromium with simulated media streams, testing permissions, scan flows, History save/delete, and verifying zero axe accessibility violations (`@axe-core/playwright`):

```sh
cd frontend
npm run test:e2e
npm run test:offline
```

### Mobile Lighthouse CI
Evaluates the idle scan screen against Performance, Accessibility, Best Practices, and SEO:

```sh
cd frontend
npm run test:lighthouse
```

The recorded production-hardening run scored 98 Performance, 100 Accessibility, 100 Best Practices and 100 SEO on the mobile Lighthouse profile. These are software-quality scores, not evidence that the Calm index measures stress accurately.

### Python Mirror & Mathematical Parity Tests
Runs all unit tests in `stress_math/`, including automated parity tests verifying Node.js and Python mirror outputs match within $10^{-6}$:

```sh
stress_math/.venv/bin/python -m unittest discover -s stress_math -t .
```

---

## Deployment

The provisional movement-tolerant scan can be tried locally with `?tolerance=1`. It uses weighted acquisition, per-feature masks, adaptive 10–20 second capture and NORMAL/LIMITED/NONE tiers. It remains opt-in until authorized condition recordings and UBFC-Phys evaluation meet the fixed adoption criteria. See [docs/TOLERANCE.md](docs/TOLERANCE.md) for the shared configuration, manifest and evaluation commands. The existing strict default is retained; no tolerance accuracy is claimed.

The frontend deploys as a static Progressive Web App (PWA) to GitHub Pages or Cloudflare Pages. See [docs/DEPLOY.md](docs/DEPLOY.md) for full deployment instructions and custom domain setup.
