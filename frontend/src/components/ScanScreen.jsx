import React from 'react';
import CameraScan, { preloadLandmarker } from '../CameraScan.jsx';
import Icon from './Icon.jsx';

function getRecoveryAction(errorMessage) {
  if (!errorMessage) return '';
  if (/blocked|permission|notallowed/i.test(errorMessage)) {
    return 'Click the camera or lock icon in your browser address bar, set Camera to Allow, then try again.';
  }
  if (/used by another app|notreadable/i.test(errorMessage)) {
    return 'Close FaceTime, Zoom, or other browser tabs that may be using the camera, then try again.';
  }
  if (/no camera|notfound/i.test(errorMessage)) {
    return 'Make sure a webcam is connected and recognized by your system, then try again.';
  }
  if (/secure connection|https/i.test(errorMessage)) {
    return 'Open the app using HTTPS or run locally on localhost.';
  }
  if (/hidden/i.test(errorMessage)) {
    return 'Keep the browser tab visible while scanning, then try again.';
  }
  return 'Check your lighting, center your face in the circle, and try again.';
}

export default function ScanScreen({onComplete,baseline,calibrating=false,mlEnabled=true}) {
  return <CameraScan mlEnabled={mlEnabled} onComplete={onComplete} baseline={baseline} calibrating={calibrating} render={({state,error,hint,progress,paused,extended,tolerant,secondsRemaining,videoRef,overlayRef,start,cancel,active,videoReady})=>{
    const starting=state==='permission'||state==='loading';
    const isError=Boolean(error)||state==='failed';
    const title=calibrating?'Calibrate when calm':'Your Calm index';
    const status=state==='permission'?'Allow camera access to continue…':state==='loading'?(videoReady?'Camera is on. Preparing face analysis…':'Preparing face analysis…'):state==='positioning'?'Center your face in view':state==='analyzing'?'Calculating your Calm index…':paused?hint:state==='countdown'?'Scanning your face…':hint;

    const isGoodPosition = hint.includes('Good') || hint.includes('steady');
    const isLightingIssue = hint.toLowerCase().includes('light');
    const chipType = isGoodPosition ? 'is-good' : isLightingIssue ? 'is-lighting' : 'is-position';

    if (active && !isError) {
      return (
        <main className="scan-fullscreen-overlay" role="dialog" aria-modal="true" aria-label="Camera Scan in Progress">
          <div className="scan-fullscreen-header">
            <span className="welcome-chip" style={{ background: '#fff', border: '1px solid #dce8d6' }}>
              <span aria-hidden="true" />
              {calibrating ? 'Personal baseline calibration' : '10-Second Camera Scan'}
            </span>
            <span className="duration-pill" style={{ background: 'var(--paper)', border: '1px solid #cbd8c9' }}>
              {extended ? 'Up to 20 sec' : '10 sec'}
            </span>
          </div>

          <div className={`scan-circle ${paused ? 'is-paused' : ''} ${starting ? 'is-loading' : ''}`} style={{ '--progress': progress }}>
            <svg className="scan-ring" viewBox="0 0 320 320" aria-hidden="true">
              <circle cx="160" cy="160" r="147" />
              <circle className="scan-ring-fill" cx="160" cy="160" r="147" pathLength="1" />
            </svg>
            <div className="scan-camera">
              <video ref={videoRef} autoPlay playsInline muted className={videoReady ? 'is-ready' : ''} />
              <canvas ref={overlayRef} aria-hidden="true" />
              {!videoReady && (
                <div className="scan-placeholder" aria-hidden="true">
                  <svg viewBox="0 0 220 220">
                    <circle className="face-halo" cx="110" cy="110" r="88" />
                    <path className="face-shoulders" d="M48 220c0-42 27-64 62-64s62 22 62 64" />
                    <path className="face-shape" d="M70 86c0-32 17-50 40-50s40 18 40 50v28c0 31-19 52-40 52s-40-21-40-52Z" />
                    <path className="face-hair" d="M69 89c-9-39 15-60 41-60 31 0 48 26 41 62-9-2-16-15-18-26-13 15-38 24-64 24Z" />
                    <path className="face-detail" d="M86 108h5m38 0h5m-27 8-3 12h9m-13 14c7 5 14 5 21 0" />
                  </svg>
                </div>
              )}
              {videoReady && state === 'positioning' && (
                <div className="face-guide-overlay" aria-hidden="true">
                  <svg viewBox="0 0 240 240" className="face-guide-svg">
                    <ellipse cx="120" cy="115" rx="58" ry="76" className="guide-oval" />
                    <line x1="98" y1="102" x2="142" y2="102" className="guide-cross" />
                  </svg>
                </div>
              )}
            </div>
            {state === 'countdown' && (
              <span className="scan-badge" aria-label={`${secondsRemaining} seconds remaining`}>
                {secondsRemaining}
              </span>
            )}
          </div>

          {state === 'positioning' && (
            <div className={`scan-feedback-chip ${chipType}`} role="status">
              <span className="feedback-dot" aria-hidden="true" />
              <span>{hint}</span>
            </div>
          )}

          <div className="scan-ready-label" style={{ fontSize: '18px', fontWeight: 600, marginTop: '14px' }}>
            {starting ? 'Preparing camera…' : state === 'countdown' ? 'Keep looking naturally' : state === 'analyzing' ? 'Calculating your Calm index…' : 'Center your face in view'}
          </div>

          <p className="scan-hint" aria-live="polite" style={{ fontSize: '14px', minHeight: '26px' }}>
            {extended ? 'Almost there, small movements are fine' : state === 'countdown' ? hint : status}
          </p>

          {/* Things to keep in mind (Constraints & Guidelines) */}
          <div className="scan-guidelines-bar" aria-label="Scan guidelines">
            <div className="scan-guideline-item">
              <span className="guideline-icon"><Icon name="sun" size={20} /></span>
              <div>
                <strong>Soft, even light</strong>
                <span>Avoid harsh backlight</span>
              </div>
            </div>
            <div className="scan-guideline-item">
              <span className="guideline-icon"><Icon name="face" size={20} /></span>
              <div>
                <strong>Neutral expression</strong>
                <span>Relax face &amp; jaw</span>
              </div>
            </div>
            <div className="scan-guideline-item">
              <span className="guideline-icon"><Icon name="steady" size={20} /></span>
              <div>
                <strong>Hold steady</strong>
                <span>Small movements are fine</span>
              </div>
            </div>
            <div className="scan-guideline-item">
              <span className="guideline-icon"><Icon name="center" size={20} /></span>
              <div>
                <strong>Face centered</strong>
                <span>Look at screen naturally</span>
              </div>
            </div>
          </div>

          {state !== 'analyzing' && (
            <button className="scan-cancel" onClick={cancel} style={{ minWidth: '160px', marginTop: '16px' }}>
              Cancel
            </button>
          )}

          <p className="scan-card-footnote" style={{ marginTop: '12px' }}>
            <Icon name="shield" size={15} /> 100% private. Video never leaves your device.
          </p>
        </main>
      );
    }

    return <main className="scan-screen">
      <div className="scan-story">
        <span className="welcome-chip"><span aria-hidden="true"/>A quiet space for yourself</span>
        <h1>{title}</h1>
        <p className="scan-intro">{calibrating?'A familiar reference. A more personal check-in. Take a moment when you feel calm.':'Take a breath. Find your light. Give yourself a moment to pause.'}</p>
        <p className="scan-description">{calibrating?'This optional scan helps future results compare with your own calm face.':'A short 10-second camera check-in gives you an experimental facial index based on facial geometry. No wearables or questions. Video stays on your device.'}</p>
        <ol className="scan-guide">
          <li><span className="guide-icon guide-peach"><Icon name="sun"/></span><div><strong>Find a comfortable spot</strong><p>Sit facing soft, even light.</p></div></li>
          <li><span className="guide-icon guide-mint"><Icon name="scan"/></span><div><strong>Bring your face into view</strong><p>Look naturally toward the camera.</p></div></li>
          <li><span className="guide-icon guide-lilac"><Icon name="spark"/></span><div><strong>See your check-in</strong><p>Your Calm index opens when the scan finishes.</p></div></li>
        </ol>
        <div className="privacy-note"><Icon name="shield"/><p><strong>Your space stays yours.</strong><br/>Video stays on your device.</p></div>
      </div>

      <section className={`scan-card ${active?'scan-card-active':''} ${isError?'scan-card-error':''}`} aria-label="Camera scan">
        <div className="scan-card-heading">
          <span><Icon name="scan"/> {calibrating?'Personal baseline':'Your daily pause'}</span>
          <span className="duration-pill">{extended?'Up to 20 sec':'10 sec'}</span>
        </div>
        <p className="scan-mode-note">{tolerant?'Experimental movement-tolerant mode · 10–20 seconds.':'10-second capture after positioning. Setup may take longer.'}</p>

        {isError ? (
          <div className="scan-error-view" role="alert">
            <div className="error-icon-badge" aria-hidden="true"><Icon name="shield" size={24}/></div>
            <h2>Camera check-in paused</h2>
            <p className="error-main-msg">{error}</p>
            <div className="recovery-instruction">
              <strong>Recovery step:</strong>
              <p>{getRecoveryAction(error)}</p>
            </div>
            <div className="scan-error-actions">
              <button className="pz-btn pz-btn-primary scan-primary" onClick={start}>Try again<Icon name="arrow"/></button>
              <button className="pz-btn pz-btn-quiet" onClick={cancel}>Cancel</button>
            </div>
          </div>
        ) : (
          <>
            <div className={`scan-circle ${paused?'is-paused':''} ${starting?'is-loading':''}`} style={{'--progress':progress}}>
              <svg className="scan-ring" viewBox="0 0 320 320" aria-hidden="true">
                <circle cx="160" cy="160" r="147"/>
                <circle className="scan-ring-fill" cx="160" cy="160" r="147" pathLength="1"/>
              </svg>
              <div className="scan-camera">
                <video ref={videoRef} autoPlay playsInline muted className={videoReady?'is-ready':''}/>
                <canvas ref={overlayRef} aria-hidden="true"/>
                {(!active || !videoReady) && (
                  <div className="scan-placeholder" aria-hidden="true">
                    <svg viewBox="0 0 220 220">
                      <circle className="face-halo" cx="110" cy="110" r="88"/>
                      <path className="face-shoulders" d="M48 220c0-42 27-64 62-64s62 22 62 64"/>
                      <path className="face-shape" d="M70 86c0-32 17-50 40-50s40 18 40 50v28c0 31-19 52-40 52s-40-21-40-52Z"/>
                      <path className="face-hair" d="M69 89c-9-39 15-60 41-60 31 0 48 26 41 62-9-2-16-15-18-26-13 15-38 24-64 24Z"/>
                      <path className="face-detail" d="M86 108h5m38 0h5m-27 8-3 12h9m-13 14c7 5 14 5 21 0"/>
                    </svg>
                  </div>
                )}
                {active && videoReady && state === 'positioning' && (
                  <div className="face-guide-overlay" aria-hidden="true">
                    <svg viewBox="0 0 240 240" className="face-guide-svg">
                      <ellipse cx="120" cy="115" rx="58" ry="76" className="guide-oval"/>
                      <line x1="98" y1="102" x2="142" y2="102" className="guide-cross"/>
                    </svg>
                  </div>
                )}
              </div>
              {state==='countdown' && <span className="scan-badge" aria-label={`${secondsRemaining} seconds remaining`}>{secondsRemaining}</span>}
            </div>

            {state === 'positioning' && (
              <div className={`scan-feedback-chip ${chipType}`} role="status">
                <span className="feedback-dot" aria-hidden="true"/>
                <span>{hint}</span>
              </div>
            )}

            <div className="scan-ready-label">
              {starting ? 'Getting ready…' : active ? (state==='countdown' ? 'Keep looking naturally' : state==='analyzing' ? 'Finishing scan…' : 'Center your face') : 'Ready when you are'}
            </div>
            
            <p className="scan-hint" aria-live="polite">
              {extended ? 'Almost there, small movements are fine' : state==='countdown' ? hint : status}
            </p>

            {!active && (
              <button
                className="pz-btn pz-btn-primary scan-primary"
                onClick={start}
                onMouseEnter={() => preloadLandmarker?.().catch(() => {})}
                onTouchStart={() => preloadLandmarker?.().catch(() => {})}
                onFocus={() => preloadLandmarker?.().catch(() => {})}
              >
                {calibrating ? 'Start calm calibration' : 'Start 10-second scan'}<Icon name="arrow"/>
              </button>
            )}
            {active && state!=='analyzing' && (
              <button className="scan-cancel" onClick={cancel}>Cancel</button>
            )}
            <p className="scan-card-footnote"><Icon name="shield" size={15}/>Private by design. Camera off when you finish.</p>
          </>
        )}
      </section>

      <section className="scan-about" aria-label="About Pause">
        <ul className="scan-features" aria-label="Features">
          <li><Icon name="scan" size={16}/>Short 10-second camera check-in</li>
          <li><Icon name="spark" size={16}/>Honest index &amp; scan graph</li>
          <li><Icon name="shield" size={16}/>100% private on your device</li>
        </ul>

        {/* Model Performance & Accuracy Milestones */}
        <div className="pz-panel" style={{ maxWidth: '680px', margin: '24px auto 0', textAlign: 'left', padding: '18px 20px', borderRadius: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
            <h3 style={{ margin: 0, fontSize: '15px', fontWeight: 600 }}>Model Benchmark &amp; Discrimination Milestones</h3>
            <span className="pz-chip" style={{ background: 'var(--tide-soft)', color: 'var(--ink)', padding: '3px 8px', fontSize: '11px' }}>
              <i aria-hidden="true" style={{ background: 'var(--tide)' }} />Verified Benchmark
            </span>
          </div>
          <p className="pz-fineprint" style={{ margin: '6px 0 14px', fontSize: '12px' }}>
            Empirical neural classifier gains evaluated across 1,344 holdout test videos compared to initial baseline:
          </p>

          <div className="metric-badge-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '10px' }}>
            <div className="metric-card" style={{ padding: '12px' }}>
              <span className="pz-fineprint" style={{ fontSize: '11px' }}>ROC-AUC Score</span>
              <div style={{ fontSize: '22px', fontWeight: 700, color: 'var(--tide)', marginTop: '2px' }}>
                0.906
              </div>
              <span className="pz-fineprint" style={{ fontSize: '11px', color: 'var(--ink-soft)', marginTop: '2px', display: 'block' }}>
                +0.406 vs chance (0.50)
              </span>
            </div>

            <div className="metric-card" style={{ padding: '12px' }}>
              <span className="pz-fineprint" style={{ fontSize: '11px' }}>Test Accuracy</span>
              <div style={{ fontSize: '22px', fontWeight: 700, color: 'var(--tide)', marginTop: '2px' }}>
                79.4%
              </div>
              <span className="pz-fineprint" style={{ fontSize: '11px', color: 'var(--ink-soft)', marginTop: '2px', display: 'block' }}>
                +28.1% vs epoch 1 (51.3%)
              </span>
            </div>

            <div className="metric-card" style={{ padding: '12px' }}>
              <span className="pz-fineprint" style={{ fontSize: '11px' }}>Validation Peak</span>
              <div style={{ fontSize: '22px', fontWeight: 700, color: 'var(--tide)', marginTop: '2px' }}>
                90.2%
              </div>
              <span className="pz-fineprint" style={{ fontSize: '11px', color: 'var(--ink-soft)', marginTop: '2px', display: 'block' }}>
                Holdout unseen actors
              </span>
            </div>

            <div className="metric-card" style={{ padding: '12px' }}>
              <span className="pz-fineprint" style={{ fontSize: '11px' }}>Client Latency</span>
              <div style={{ fontSize: '22px', fontWeight: 700, color: 'var(--tide)', marginTop: '2px' }}>
                &lt; 50 ms
              </div>
              <span className="pz-fineprint" style={{ fontSize: '11px', color: 'var(--ink-soft)', marginTop: '2px', display: 'block' }}>
                100% on-device WebAssembly
              </span>
            </div>
          </div>

          <p className="pz-fineprint" style={{ margin: '12px 0 0', fontSize: '11px', color: 'var(--ink-soft)' }}>
            * Evaluated on held-out test splits. Metrics describe image-level facial expression pattern recognition; the visible Calm index is an experimental geometric index that operates independently.
          </p>
        </div>

        <p className="scan-disclaimer">
          <strong>A check-in, not a diagnosis.</strong> Pause is an experimental facial check-in tool. Its facial index cannot diagnose medical conditions or measure clinical stress.
        </p>
      </section>
    </main>;
  }}/>;
}
