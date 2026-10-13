import CameraScan from '../CameraScan.jsx';

export default function ScanScreen({onComplete,baseline,calibrating=false}) {
  return <CameraScan onComplete={onComplete} baseline={baseline} calibrating={calibrating} render={({state,error,hint,progress,paused,secondsRemaining,videoRef,overlayRef,start,cancel,active})=>{
    const starting=state==='permission'||state==='loading';
    const title=calibrating?'Calibrate when calm':'Your Calm index';
    const status=error||starting?'Starting camera…':state==='positioning'?'Fit your face in the circle':state==='analyzing'?'Calculating…':paused?hint:state==='countdown'?'Scanning your face':hint;
    return <main className="scan-screen">
      <h1>{title}</h1>
      <p className="scan-intro">{calibrating?'Sit naturally while calm. This scan stays in your browser.':'A 10-second experimental facial index. Video stays on your device.'}</p>
      <div className={`scan-circle ${paused?'is-paused':''} ${starting?'is-loading':''}`} style={{'--progress':progress}}>
        <svg className="scan-ring" viewBox="0 0 320 320" aria-hidden="true"><circle cx="160" cy="160" r="147"/><circle className="scan-ring-fill" cx="160" cy="160" r="147" pathLength="1"/></svg>
        <div className="scan-camera"><video ref={videoRef} autoPlay playsInline muted/><canvas ref={overlayRef} aria-hidden="true"/>{!active&&<div className="scan-placeholder" aria-hidden="true">◎</div>}{state==='countdown'&&<div className="scan-sweep" aria-hidden="true"/>}</div>
        {state==='countdown'&&<span className="scan-badge">{secondsRemaining}</span>}
      </div>
      <p className="scan-hint" aria-live="polite">{error||status}</p>
      {!active&&<button className="pz-btn pz-btn-primary scan-primary" onClick={start}>{calibrating?'Start calm calibration':'Start 10-second scan'}</button>}
      {active&&state!=='analyzing'&&<button className="scan-cancel" onClick={cancel}>Cancel</button>}
    </main>;
  }}/>
}
