import React,{useState} from 'react';
import {createRoot} from 'react-dom/client';
import './style.css';
import CameraScan from './CameraScan';
import LiveGraph from './LiveGraph';
import Experiment from './Experiment';
import {readCameraSessions,saveCameraSession,deleteCameraSession} from './cameraSessions';

function App() {
  const [screen,setScreen]=useState('Live'),[result,setResult]=useState(null);
  const [storageConsent,setStorageConsent]=useState(false),[notice,setNotice]=useState('');
  const [error,setError]=useState('');
  const [sessions,setSessions]=useState(()=>{try{return readCameraSessions();}catch{return[];}});
  function navigate(next){setNotice('');setError('');setScreen(next);}
  function completed(session){setResult(session);setStorageConsent(false);setScreen('Results');setNotice('Session finished. Camera stopped.');}
  function save(){
    if(!result||!storageConsent)return;
    try{saveCameraSession(result);setSessions(readCameraSessions());setNotice('Graph and summary saved in this browser.');setError('');}
    catch{setError('Browser storage is unavailable or full. Your session is still shown here.');}
  }
  function remove(id){
    if(!window.confirm('Delete this saved camera session permanently?'))return;
    try{deleteCameraSession(id);setSessions(readCameraSessions());setNotice('Session deleted.');}
    catch{setError('Could not delete this session. Please retry.');}
  }
  const isSaved=result&&sessions.some(s=>s.id===result.id);
  return <div className="shell">
    <header><a className="brand" href="#" onClick={()=>navigate('Overview')}>◉ pause<span>LIVE FACIAL CHECK-IN</span></a><div className="tag">On-device · Non-diagnostic</div></header>
    <nav aria-label="Main navigation">{['Overview','Live','Results','History','Experiment'].map(item=><button key={item} aria-current={screen===item?'page':undefined} className={screen===item?'active':''} onClick={()=>navigate(item)}>{item==='Experiment'?'About Model':item}</button>)}</nav>
    <main><p className="save-notice" role="status">{notice}</p>{error&&<p role="alert" className="camera-error">{error}</p>}
      {screen==='Overview'&&<>
        <p className="eyebrow">LIVE CAMERA · ON-DEVICE</p><h1>Pause. Watch.<br/><em>Explore your facial patterns.</em></h1>
        <p className="intro">Look at the camera for 10 seconds, then see your indicative tension score automatically.</p>
        <button className="primary" onClick={()=>navigate('Live')}>Open 10-second scan →</button>
        <div className="cards"><article><span>01 / SCAN</span><h2>Look at the camera</h2><p>One 10-second scan. No manual surveys or wearables.</p></article><article><span>02 / SCORE</span><h2>See your result</h2><p>Your score opens automatically when the scan ends.</p></article><article><span>03 / PRIVATE</span><h2>On your device</h2><p>Video is never recorded or uploaded.</p></article></div>
      </>}
      {screen==='Live'&&<><p className="eyebrow">REAL-TIME FACIAL BEHAVIOR</p><h1>Your 10-second scan.</h1><CameraScan onComplete={completed}/></>}
      {screen==='Results'&&<><p className="eyebrow">SESSION REVIEW</p><h1>Your score.</h1>{result?<>
        <p>{new Date(result.created_at).toLocaleString()} · {Math.round(result.durationSeconds)} seconds</p>
        <section className="panel"><h2>Facial index</h2><p className="rating">{Number.isFinite(result.average)?result.average.toFixed(1):'Scan incomplete'}{Number.isFinite(result.average)&&<small> / 10</small>}</p><p><strong>Scale:</strong> 0 = highest tension deviation · 5 = neutral baseline mean · 10 = most relaxed</p><p className="fine">{result.quality==='good'?'Calculated from 10-second on-device facial pattern analysis relative to a neutral baseline.':(result.reason||'Not enough usable camera frames. Try again with even lighting and your face in view.')}</p></section>
        {result.quality==='good'&&<section className="panel">
          <h2>Why scores can vary between scans</h2>
          <p>A score near 5 corresponds to neutral baseline composure. Scores moving toward 0 reflect subtle facial contraction (such as brow furrowing, lip compression, or jaw tightening). Engaging in focused screen work or reading over 5–10 minutes commonly introduces subconscious micro-tension or posture shifts.</p>
          {result.features&&<details>
            <summary style={{cursor:'pointer',fontWeight:600,padding:'6px 0'}}>View facial tension observations</summary>
            <div style={{marginTop:'12px',fontSize:'13px'}}>
              <p><strong>Upper face (brow & forehead):</strong> {result.features.brow_furrow > -0.56 ? 'Subtle furrowing or contraction detected' : 'Neutral / uncontracted'}</p>
              <p><strong>Lower face (mouth & lips):</strong> {result.features.lip_press > -0.26 ? 'Slight vertical compression detected' : 'Neutral / relaxed'}</p>
              <p><strong>Jaw & cheek composure:</strong> {result.features.jaw_clench > 0.92 ? 'Elevated tension detected across jaw region' : 'Neutral / relaxed'}</p>
              <p><strong>Expression symmetry:</strong> {Math.abs(result.features.lip_corner) > 0.08 ? 'Asymmetrical micro-expression' : 'Balanced composure'}</p>
              <p className="fine" style={{marginTop:'8px'}}>Qualitative behavioral pattern indicators for personal awareness. Not a clinical or diagnostic assessment.</p>
            </div>
          </details>}
        </section>}
        {Number.isFinite(result.average)&&<LiveGraph points={result.points}/>}
        <section className="panel">
          <h2>Save this session?</h2>
          <p>Only elapsed-time index samples and this summary are saved. Anyone using this browser profile can view them; clearing site data erases them.</p>
          {isSaved?<p>This session is saved.</p>:<>
            <label className="consent"><input type="checkbox" checked={storageConsent} onChange={e=>setStorageConsent(e.target.checked)}/> I agree to save this graph and summary in this browser.</label>
            <button className="primary" disabled={!storageConsent} onClick={save}>Save session</button>
          </>}
        </section>
        <button className="primary" onClick={()=>navigate('Live')}>Start another session →</button>
      </>:<><p>Finish a live session or choose a saved graph from History.</p><button className="primary" onClick={()=>navigate('Live')}>Open live camera</button></>}</>}
      {screen==='History'&&<><p className="eyebrow">SAVED CAMERA SESSIONS</p><h1>Your previous graphs.</h1><section className="panel"><h2>{sessions.length?sessions.length+' saved sessions':'No camera sessions saved yet'}</h2>{sessions.map(s=><div className="history-row" key={s.id}><div><strong>{Number.isFinite(s.average)?s.average.toFixed(1)+'/10 · average index':'Insufficient signal coverage'}</strong><p>{new Date(s.created_at).toLocaleString()} · {s.coveragePercent.toFixed(0)}% coverage</p></div><div><button className="secondary" onClick={()=>{setResult(s);navigate('Results');}}>View graph</button><button className="secondary" onClick={()=>remove(s.id)}>Delete</button></div></div>)}{!sessions.length&&<button className="primary" onClick={()=>navigate('Live')}>Start a live session</button>}</section></>}
      {screen==='Experiment'&&<Experiment/>}
    </main>
    <footer>Personal wellbeing check-in tool. Not a medical device or diagnostic test. Camera processing runs strictly on-device in temporary browser memory with zero video recording or uploads.</footer>
  </div>;
}

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }
  componentDidCatch(error, errorInfo) {
    console.error('App render error:', error, errorInfo);
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="shell">
          <header><a className="brand" href="./">◉ pause<span>ERROR</span></a></header>
          <main>
            <h1>Something went wrong.</h1>
            <p className="camera-error">{this.state.error?.message || 'An unexpected error occurred.'}</p>
            <button className="primary" onClick={() => window.location.reload()}>Reload app</button>
          </main>
        </div>
      );
    }
    return this.props.children;
  }
}

createRoot(document.getElementById('root')).render(
  <ErrorBoundary>
    <App/>
  </ErrorBoundary>
);
