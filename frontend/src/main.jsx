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
    <header><a className="brand" href="#" onClick={()=>navigate('Overview')}>◉ pause<span>LIVE FACIAL CHECK-IN</span></a><div className="tag">Experimental · on-device</div></header>
    <nav aria-label="Main navigation">{['Overview','Live','Results','History','Experiment'].map(item=><button key={item} aria-current={screen===item?'page':undefined} className={screen===item?'active':''} onClick={()=>navigate(item)}>{item}</button>)}</nav>
    <main><p className="save-notice" role="status">{notice}</p>{error&&<p role="alert" className="camera-error">{error}</p>}
      {screen==='Overview'&&<>
        <p className="eyebrow">LIVE CAMERA · NO QUESTIONNAIRE SCORE</p><h1>Pause. Watch.<br/><em>Explore your facial patterns.</em></h1>
        <p className="intro">Look at the camera for 10 seconds, then see your experimental score automatically.</p>
        <button className="primary" onClick={()=>navigate('Live')}>Open 10-second scan →</button>
        <div className="cards"><article><span>01 / SCAN</span><h2>Look at the camera</h2><p>One 10-second scan. No calibration or questionnaire.</p></article><article><span>02 / SCORE</span><h2>See your result</h2><p>Your score opens automatically when the scan ends.</p></article><article><span>03 / PRIVATE</span><h2>On your device</h2><p>Video is never recorded or uploaded.</p></article></div>
      </>}
      {screen==='Live'&&<><p className="eyebrow">REAL-TIME FACIAL BEHAVIOR</p><h1>Your 10-second scan.</h1><CameraScan onComplete={completed}/></>}
      {screen==='Results'&&<><p className="eyebrow">SESSION REVIEW</p><h1>Your score.</h1>{result?<>
        <p>{new Date(result.created_at).toLocaleString()} · {Math.round(result.durationSeconds)} seconds</p>
        <section className="panel"><h2>Facial index</h2><p className="rating">{Number.isFinite(result.average)?result.average.toFixed(1):'Unavailable'}{Number.isFinite(result.average)&&<small> / 10</small>}</p><p><strong>Scale:</strong> 0 = highest tension deviation · 5 = neutral baseline mean · 10 = most relaxed</p><p className="fine">{result.quality==='good'?'Calculated from 10-second facial landmark geometry relative to a generic reference.':(result.reason||'Not enough usable camera frames. Try again with even lighting and your face in view.')}</p></section>
        {result.quality==='good'&&<section className="panel">
          <h2>Why scores can vary between scans</h2>
          <p>A score near 5 corresponds to neutral baseline geometry. Deviations toward 0 occur when facial features contract (e.g., brow furrowing, lip compression, or jaw clenching). Staring at a screen, reading, or mental concentration over 5–10 minutes often introduces unconscious micro-tension or posture shifts.</p>
          {result.features&&<details>
            <summary style={{cursor:'pointer',fontWeight:600,padding:'6px 0'}}>View observed landmark geometry</summary>
            <div style={{marginTop:'12px',fontSize:'13px'}}>
              <p><strong>Brow furrow distance:</strong> {result.features.brow_furrow > -0.56 ? 'Contracted relative to reference' : 'Neutral / uncontracted'}</p>
              <p><strong>Lip vertical compression:</strong> {result.features.lip_press > -0.26 ? 'Compressed relative to reference' : 'Neutral / uncompressed'}</p>
              <p><strong>Jaw width ratio:</strong> {result.features.jaw_clench > 0.92 ? 'Wider than reference (tension)' : 'Neutral / relaxed'}</p>
              <p><strong>Lip corner angle:</strong> {Math.abs(result.features.lip_corner) > 0.08 ? 'Angled / asymmetrical' : 'Level'}</p>
              <p className="fine" style={{marginTop:'8px'}}>Experimental geometric coefficients, not clinical or physiological stress measurements.</p>
            </div>
          </details>}
        </section>}
        {result.quality==='good'&&<LiveGraph points={result.points}/>}
        <button className="primary" onClick={()=>navigate('Live')}>Start another session →</button>
      </>:<><p>Finish a live session or choose a saved graph from History.</p><button className="primary" onClick={()=>navigate('Live')}>Open live camera</button></>}</>}
      {screen==='History'&&<><p className="eyebrow">SAVED CAMERA SESSIONS</p><h1>Your previous graphs.</h1><section className="panel"><h2>{sessions.length?sessions.length+' saved sessions':'No camera sessions saved yet'}</h2>{sessions.map(s=><div className="history-row" key={s.id}><div><strong>{Number.isFinite(s.average)?s.average.toFixed(1)+'/10 · average experimental index':'Insufficient signal coverage'}</strong><p>{new Date(s.created_at).toLocaleString()} · {s.coveragePercent.toFixed(0)}% coverage</p></div><div><button className="secondary" onClick={()=>{setResult(s);navigate('Results');}}>View graph</button><button className="secondary" onClick={()=>remove(s.id)}>Delete</button></div></div>)}{!sessions.length&&<button className="primary" onClick={()=>navigate('Live')}>Start a live session</button>}</section></>}
      {screen==='Experiment'&&<Experiment/>}
    </main>
    <footer>Experimental facial behavior index, not a diagnosis or validated stress measurement. Camera processing stays in your browser. No video recording or upload.</footer>
  </div>;
}
createRoot(document.getElementById('root')).render(<App/>);
