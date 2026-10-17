import React from 'react';
import CameraScan from '../CameraScan.jsx';
import Icon from './Icon.jsx';

export default function ScanScreen({onComplete,baseline,calibrating=false}) {
  return <CameraScan onComplete={onComplete} baseline={baseline} calibrating={calibrating} render={({state,error,hint,progress,paused,extended,tolerant,secondsRemaining,videoRef,overlayRef,start,cancel,active})=>{
    const starting=state==='permission'||state==='loading';
    const title=calibrating?'Calibrate when calm':'Your Calm index';
    const status=error||starting?'Starting camera…':state==='positioning'?'Fit your face in the circle':state==='analyzing'?'Calculating…':paused?hint:state==='countdown'?'Scanning your face':hint;
    return <main className="scan-screen">
      <div className="scan-story">
        <span className="welcome-chip"><span/>A little space for yourself</span>
        <h1>{title}</h1>
        <p className="scan-intro">{calibrating?'A familiar reference. A more personal check-in. Take a moment when you feel calm.':'Take a breath. Find your light. Give yourself a moment to pause.'}</p>
        <p className="scan-description">{calibrating?'This optional scan helps future results compare with your own calm face.':'A short camera scan gives you an experimental facial index. No questions, no wearables. Just you.'}</p>
        <ol className="scan-guide">
          <li><span className="guide-icon guide-peach"><Icon name="sun"/></span><div><strong>Find a comfortable spot</strong><p>Sit facing soft, even light.</p></div></li>
          <li><span className="guide-icon guide-mint"><Icon name="scan"/></span><div><strong>Bring your face into view</strong><p>Look naturally toward the camera.</p></div></li>
          <li><span className="guide-icon guide-lilac"><Icon name="spark"/></span><div><strong>See your check-in</strong><p>Your Calm index opens when the scan finishes.</p></div></li>
        </ol>
        <div className="privacy-note"><Icon name="shield"/><p><strong>Your space stays yours.</strong><br/>Video stays on your device.</p></div>
      </div>
      <section className={`scan-card ${active?'scan-card-active':''}`} aria-label="Camera scan">
      <div className="scan-card-heading"><span><Icon name="scan"/> {calibrating?'Personal baseline':'Your daily pause'}</span><span className="duration-pill">{extended?'Up to 20 sec':'10 sec'}</span></div>
      <p className="scan-mode-note">{tolerant?'Experimental movement-tolerant mode · 10–20 seconds.':'10-second capture after positioning. Setup may take longer.'}</p>
      <div className={`scan-circle ${paused?'is-paused':''} ${starting?'is-loading':''}`} style={{'--progress':progress}}>
        <svg className="scan-ring" viewBox="0 0 320 320" aria-hidden="true"><circle cx="160" cy="160" r="147"/><circle className="scan-ring-fill" cx="160" cy="160" r="147" pathLength="1"/></svg>
        <div className="scan-camera"><video ref={videoRef} autoPlay playsInline muted/><canvas ref={overlayRef} aria-hidden="true"/>{!active&&<div className="scan-placeholder" aria-hidden="true"><svg viewBox="0 0 220 220"><circle className="face-halo" cx="110" cy="110" r="88"/><path className="face-shoulders" d="M48 220c0-42 27-64 62-64s62 22 62 64"/><path className="face-shape" d="M70 86c0-32 17-50 40-50s40 18 40 50v28c0 31-19 52-40 52s-40-21-40-52Z"/><path className="face-hair" d="M69 89c-9-39 15-60 41-60 31 0 48 26 41 62-9-2-16-15-18-26-13 15-38 24-64 24Z"/><path className="face-detail" d="M86 108h5m38 0h5m-27 8-3 12h9m-13 14c7 5 14 5 21 0"/></svg><span className="face-target target-one"/><span className="face-target target-two"/></div>}{state==='countdown'&&<div className="scan-sweep" aria-hidden="true"/>}</div>
        {state==='countdown'&&<span className="scan-badge">{secondsRemaining}</span>}
      </div>
      <div className="scan-ready-label">{starting?'Getting ready':active?'A moment just for you':'Ready when you are'}</div>
      <p className="scan-hint" aria-live="polite">{error||(extended?'Almost there, small movements are fine':state==='countdown'?hint:status)}</p>
      {!active&&<button className="pz-btn pz-btn-primary scan-primary" onClick={start}>{calibrating?'Start calm calibration':'Start 10-second scan'}<Icon name="arrow"/></button>}
      {active&&state!=='analyzing'&&<button className="scan-cancel" onClick={cancel}>Cancel</button>}
      <p className="scan-card-footnote"><Icon name="shield" size={15}/>Private by design. Camera off when you finish.</p>
      </section>
      <section className="scan-about" aria-label="About Pause">
        <ul className="scan-features" aria-label="Features">
          <li><Icon name="scan" size={16}/>Short camera check-in</li>
          <li><Icon name="spark" size={16}/>Index &amp; scan graph</li>
          <li><Icon name="shield" size={16}/>Save history on your device</li>
        </ul>
        <p className="scan-disclaimer"><strong>A check-in, not a diagnosis.</strong> Pause is not a diagnostic app. Its experimental facial index cannot measure how stressed you feel or diagnose a health condition.</p>
      </section>
    </main>;
  }}/>
}
