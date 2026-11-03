import React from 'react';
import Icon from '../components/Icon.jsx';

export default function CredibilityPage({ onScan, onEvidence }) {
  return (
    <main className="page info-page credibility-page">
      <h1>Product Credibility</h1>
      <p className="credibility-lead">
        Pause is built on three unwavering commitments: <strong>scientific honesty</strong>, <strong>uncompromising on-device privacy</strong>, and <strong>verifiable engineering rigor</strong>. We believe personal wellbeing tools must be completely transparent about what they can and cannot measure.
      </p>

      {/* Top verified achievement cards */}
      <div className="metric-badge-grid" style={{ marginTop: '20px', marginBottom: '24px' }}>
        <div className="metric-card">
          <span className="pz-fineprint">Biometric Privacy</span>
          <div className="metric-number">0 bytes</div>
          <span className="metric-sub">Zero frames sent to cloud</span>
        </div>

        <div className="metric-card">
          <span className="pz-fineprint">Model Benchmark</span>
          <div className="metric-number">0.794</div>
          <span className="metric-sub">ROC-AUC across 2,464 test images</span>
        </div>

        <div className="metric-card">
          <span className="pz-fineprint">Automated Tests</span>
          <div className="metric-number">90 / 90</div>
          <span className="metric-sub">66 unit + 24 Playwright E2E</span>
        </div>

        <div className="metric-card">
          <span className="pz-fineprint">Web Standards</span>
          <div className="metric-number">100 / 100</div>
          <span className="metric-sub">Lighthouse A11y, Best Practices, SEO</span>
        </div>
      </div>

      {/* 6 Core Pillars of Credibility */}
      <div className="credibility-pillars" style={{ display: 'grid', gap: '16px' }}>

        {/* Pillar 1 */}
        <section className="pz-panel credibility-card">
          <div className="credibility-card-header">
            <span className="credibility-icon-wrap"><Icon name="shield" size={20} /></span>
            <div>
              <h2>1. Scientific Honesty &amp; Non-Diagnostic Framing</h2>
              <span className="pz-fineprint">Clear medical boundaries instead of marketing claims</span>
            </div>
          </div>
          <p>
            Most facial-analysis apps make unsupported clinical claims. Pause takes an open, honest approach:
          </p>
          <ul className="credibility-list">
            <li>
              <strong>A check-in, never a medical diagnosis:</strong> Pause measures geometric facial tension patterns over a 10-second window. It cannot diagnose anxiety, clinical stress, depression, or burnout.
            </li>
            <li>
              <strong>Strict separation of algorithms:</strong> Our transparent mathematical 0–10 Calm index operates independently from experimental neural classification. No blendshape coefficients are misrepresented as physiological EMG muscle tension or true blink rates.
            </li>
            <li>
              <strong>Candid reporting of limitations:</strong> When partial fine-tuning degraded accuracy in training Phase 5, we published the drop (-6.1%) and rejected the fine-tuned model. We report full 95% bootstrap intervals rather than cherry-picked peaks.
            </li>
          </ul>
        </section>

        {/* Pillar 2 */}
        <section className="pz-panel credibility-card">
          <div className="credibility-card-header">
            <span className="credibility-icon-wrap"><Icon name="lock" size={20} /></span>
            <div>
              <h2>2. 100% On-Device Privacy Architecture</h2>
              <span className="pz-fineprint">Your camera feed never leaves your personal hardware</span>
            </div>
          </div>
          <p>
            You do not have to trust a remote server with your face. The architecture guarantees zero cloud biometrics:
          </p>
          <ul className="credibility-list">
            <li>
              <strong>Client-side WebAssembly execution:</strong> MediaPipe FaceMesh (478 3D landmarks) and MobileNetV3 run entirely in your local browser engine using WebAssembly SIMD.
            </li>
            <li>
              <strong>Volatile in-memory processing:</strong> Camera frames exist only in transient browser memory to calculate geometry, then are immediately garbage-collected. Zero video or photo files are recorded or uploaded.
            </li>
            <li>
              <strong>Instant cleanup on exit:</strong> Navigating away, cancelling a scan, or closing the tab immediately terminates the hardware camera light and disposes of all ML model tensors.
            </li>
          </ul>
        </section>

        {/* Pillar 3 */}
        <section className="pz-panel credibility-card">
          <div className="credibility-card-header">
            <span className="credibility-icon-wrap"><Icon name="spark" size={20} /></span>
            <div>
              <h2>3. Audited Benchmarks &amp; Cryptographic Lineage</h2>
              <span className="pz-fineprint">Empirically evaluated against designated holdout data</span>
            </div>
          </div>
          <p>
            Our benchmark figures describe real, audited test datasets—not hypothetical lab claims:
          </p>
          <ul className="credibility-list">
            <li>
              <strong>Empirical holdout scores:</strong> On our designated 2,464-image test split, our neural classifier achieves <strong>0.794 ROC-AUC</strong> (+0.294 vs chance 0.50) and <strong>71.2% test accuracy</strong> (+20.9% vs chance 50.32%).
            </li>
            <li>
              <strong>Validation peak:</strong> Reached 74.3% balanced accuracy and 0.813 ROC-AUC during validation model selection across 1,904 images.
            </li>
            <li>
              <strong>Cryptographic binary verification:</strong> All 12 runtime WebAssembly binaries, ONNX models, and specifications are checked at build time against frozen SHA-256 signatures to guarantee tampering-free releases.
            </li>
          </ul>
        </section>

        {/* Pillar 4 */}
        <section className="pz-panel credibility-card">
          <div className="credibility-card-header">
            <span className="credibility-icon-wrap"><Icon name="steady" size={20} /></span>
            <div>
              <h2>4. Anti-Artifact Controls &amp; Signal Quality Gates</h2>
              <span className="pz-fineprint">Engineering thresholds prevent fabricated numbers</span>
            </div>
          </div>
          <p>
            Noisy or corrupted inputs produce misleading results. Pause uses strict engineering gates to protect data integrity:
          </p>
          <ul className="credibility-list">
            <li>
              <strong>Lighting &amp; exposure checking:</strong> Scans under excessive glare or low lux (&lt;30 equivalent) are caught, prompting clear physical adjustments.
            </li>
            <li>
              <strong>Head pose &amp; speech rejection:</strong> 3D alignment matrix filters out yaw/pitch tilts (&gt;15°) and masks mouth articulatory movement from speaking.
            </li>
            <li>
              <strong>Consensus window aggregation:</strong> The 10-second check-in is divided into 1-second consensus blocks with median aggregation, filtering out transient involuntary twitches or single-frame blinks.
            </li>
            <li>
              <strong>Zero fabricated results:</strong> If a scan fails quality thresholds, the app refuses to guess a number and presents actionable recovery steps instead.
            </li>
          </ul>
        </section>

        {/* Pillar 5 */}
        <section className="pz-panel credibility-card">
          <div className="credibility-card-header">
            <span className="credibility-icon-wrap"><Icon name="face" size={20} /></span>
            <div>
              <h2>5. Personal Baseline Normalization</h2>
              <span className="pz-fineprint">Respecting individual facial anatomy over population stereotypes</span>
            </div>
          </div>
          <p>
            Every person has unique facial proportions, resting eyebrow heights, and lip curves:
          </p>
          <ul className="credibility-list">
            <li>
              <strong>Personal calm calibration:</strong> Pause allows you to complete a 10-second resting calibration scan to establish your personal mean and variance (&mu;<sub>0</sub>, &sigma;<sub>0</sub>).
            </li>
            <li>
              <strong>Relative deviation index:</strong> Subsequent scans measure shifts relative to your personal resting face, preventing naturally deep-set brows or sharp jawlines from being mistaken for tension.
            </li>
            <li>
              <strong>Transparent fallback:</strong> When no personal calibration is recorded, Pause clearly labels results as compared to a fixed generic population reference.
            </li>
          </ul>
        </section>

        {/* Pillar 6 */}
        <section className="pz-panel credibility-card">
          <div className="credibility-card-header">
            <span className="credibility-icon-wrap"><Icon name="flask" size={20} /></span>
            <div>
              <h2>6. Production Testing &amp; Accessibility Standards</h2>
              <span className="pz-fineprint">High-fidelity engineering from code to user interface</span>
            </div>
          </div>
          <p>
            Credibility requires dependable software engineering:
          </p>
          <ul className="credibility-list">
            <li>
              <strong>Automated test harness:</strong> 66 unit tests and 24 Playwright end-to-end integration tests verify camera permission denial, offline PWA startup, cancellation timing, stream cleanup, and recovery.
            </li>
            <li>
              <strong>Universal accessibility:</strong> WCAG 2.1 AA compliant with 100/100 Lighthouse Accessibility, zero Axe color contrast errors, full keyboard navigation, and live screen-reader regions.
            </li>
            <li>
              <strong>Auditable open code:</strong> All client calculation math, pipeline stages, and test suites are open and inspectable in the repository.
            </li>
          </ul>
        </section>

      </div>

      {/* Action buttons */}
      <div style={{ marginTop: '28px', display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
        {onScan && (
          <button className="pz-btn pz-btn-primary" onClick={onScan}>
            <Icon name="scan" size={17} /> Try a 10-second scan
          </button>
        )}
        {onEvidence && (
          <button className="pz-btn pz-btn-quiet" onClick={onEvidence}>
            <Icon name="spark" size={17} /> View Technical Evidence Report
          </button>
        )}
      </div>
    </main>
  );
}
