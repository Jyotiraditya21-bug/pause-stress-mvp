import React from 'react';

export default function Experiment() {
  return <>
    <p className="eyebrow">ABOUT THE MODEL &amp; METHODOLOGY</p>
    <h1>Understanding your stress check-in.</h1>
    <p className="intro">
      Pause uses an on-device computer vision model to observe facial micro-patterns and provide an indicative tension score. It is designed to foster everyday self-awareness and mindful pauses.
    </p>

    <section className="panel" style={{borderLeft:'4px solid #bc8a3c',background:'#fffdf9'}}>
      <h2 style={{color:'#6e4e1b',marginTop:0}}>Important Non-Diagnostic Notice</h2>
      <p style={{color:'#58482f',margin:'8px 0'}}>
        <strong>This application is not a medical or diagnostic instrument.</strong> It does not diagnose, treat, mitigate, or monitor clinical depression, generalized anxiety disorder, hypertension, burnout syndrome, or any other physiological or psychological condition.
      </p>
      <p style={{color:'#58482f',margin:'8px 0'}}>
        The generated scores and session graphs reflect real-time physical composure patterns relative to neutral baseline indicators. They are intended solely for personal wellness exploration and habit tracking. If you are experiencing persistent stress, fatigue, or health concerns, please consult a qualified healthcare or mental health professional.
      </p>
    </section>

    <section className="panel" style={{marginTop:'22px'}}>
      <h2>How the Stress Level is Estimated</h2>
      <p>
        Rather than relying on intrusive sensors or manual surveys, the model assesses physical tension through subtle visual cues during a brief 10-second check-in:
      </p>
      <div style={{display:'grid',gap:'16px',marginTop:'16px'}}>
        <div>
          <strong style={{color:'#183b36'}}>1. Real-Time Facial Dynamics</strong>
          <p style={{margin:'4px 0 0'}}>
            During the check-in, our computer vision model tracks key expressive landmarks around the upper and lower face—observing involuntary micro-movements, brow composure, mouth tension, and jaw alignment.
          </p>
        </div>
        <div>
          <strong style={{color:'#183b36'}}>2. Relative Baseline Calibration</strong>
          <p style={{margin:'4px 0 0'}}>
            Observed facial physical patterns are benchmarked against standardized neutral reference geometry to identify degrees of physical contraction versus relaxed expression.
          </p>
        </div>
        <div>
          <strong style={{color:'#183b36'}}>3. Continuous 10-Second Stability Scoring</strong>
          <p style={{margin:'4px 0 0'}}>
            Instead of capturing an instantaneous snapshot, the model continuously monitors facial changes across the full 10-second session. Spurious movements (such as blinks, head turns, or momentary twitches) are filtered out to compute a stable, aggregate score on an intuitive 0–10 scale:
          </p>
          <ul style={{margin:'8px 0',paddingLeft:'20px',color:'#64776b'}}>
            <li><strong>0 to 3:</strong> Elevated physical tension or micro-contraction</li>
            <li><strong>4 to 6:</strong> Neutral baseline composure (5 represents the neutral mean)</li>
            <li><strong>7 to 10:</strong> Relaxed, open facial expression</li>
          </ul>
        </div>
      </div>
    </section>

    <div className="cards">
      <article>
        <span>01 / NON-DIAGNOSTIC</span>
        <h2>Personal awareness</h2>
        <p>A quick, objective check-in tool to help you notice when work or screen time is creating unconscious facial tension.</p>
      </article>
      <article>
        <span>02 / PRIVACY FIRST</span>
        <h2>100% on-device</h2>
        <p>All vision processing occurs locally in your browser's private memory. Raw video is never stored, recorded, or sent to external servers.</p>
      </article>
      <article>
        <span>03 / OBJECTIVE METRICS</span>
        <h2>Consistent feedback</h2>
        <p>Provides a standardized, reproducible assessment across sessions without requiring wearable hardware or questionnaires.</p>
      </article>
    </div>

    <section className="panel">
      <h2>Privacy &amp; Security Guarantee</h2>
      <p>
        Your privacy is protected by design. The camera stream is held strictly in temporary client-side memory while the 10-second scan is active, and all camera tracks are immediately stopped and released when the session finishes or when you navigate away. No images, videos, audio, or biometric templates are transmitted over the network.
      </p>
    </section>
  </>;
}
