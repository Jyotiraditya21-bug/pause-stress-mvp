import React,{useState} from 'react';
import {createRoot} from 'react-dom/client';
import './style.css';
import CameraScan from './CameraScan';
import LiveGraph from './LiveGraph';
import Experiment from './Experiment';
import {readCameraSessions,saveCameraSession,deleteCameraSession} from './cameraSessions';

function App() {
  const [screen,setScreen]=useState('Overview'),[result,setResult]=useState(null);
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
        <p className="intro">A live camera graph powered by a fixed mathematical facial index. Calibrate while relaxed for 25 seconds, then follow changes on a 0–10 scale.</p>
        <button className="primary" onClick={()=>navigate('Live')}>Start live camera graph →</button>
        <div className="cards"><article><span>01 / CALIBRATE</span><h2>Your personal baseline</h2><p>Start relaxed, face the camera, and stay quiet for 25 seconds.</p></article><article><span>02 / FOLLOW</span><h2>A graph that updates live</h2><p>0 is the high-stress end; 10 is the no-stress end. Baseline maps to 5. The scale is an experimental proxy, not measured stress.</p></article><article><span>03 / REVIEW</span><h2>Keep your session private</h2><p>Review the graph and optionally save it in this browser. Video is never recorded or uploaded.</p></article></div>
        <section className="status"><strong>What drives the graph?</strong><p>Blink events, brow and lip geometry, jaw geometry, and head-motion jitter relative to your baseline. Fixed weights and a sigma floor are used. Pulse/HRV is excluded. No entered stress rating drives the result.</p></section>
      </>}
      {screen==='Live'&&<><p className="eyebrow">REAL-TIME FACIAL BEHAVIOR</p><h1>Your live session.</h1><CameraScan onComplete={completed}/></>}
      {screen==='Results'&&<><p className="eyebrow">SESSION REVIEW</p><h1>Your camera-derived graph.</h1>{result?<>
        <p>{new Date(result.created_at).toLocaleString()} · {Math.round(result.durationSeconds)} seconds</p>
        <div className="cards"><article><h2>Average index</h2><p className="rating">{Number.isFinite(result.average)?result.average.toFixed(1):'—'}<small> / 10</small></p><p>Experimental facial index. No questionnaire rating is used.</p></article><article><h2>Last plotted reading</h2><p className="rating">{Number.isFinite(result.latest)?result.latest.toFixed(1):'—'}<small> / 10</small></p><p>0 = high-stress end · 10 = no-stress end. Baseline feature means = 5.</p></article><article><h2>Usable signal coverage</h2><p className="rating">{result.coveragePercent.toFixed(0)}<small>%</small></p><p>{result.quality==='good'?'At least 40% of post-calibration frames were usable.':'Below the fixed coverage minimum or no usable scores. Aggregate readings are withheld.'}</p></article></div>
        <LiveGraph points={result.points}/>
        <section className="panel"><h2>Save this graph?</h2><p>Only elapsed-time index samples and this summary are saved. Anyone using this browser profile can view them; clearing site data erases them.</p>{isSaved?<p>This session is saved.</p>:<><label className="consent"><input type="checkbox" checked={storageConsent} onChange={e=>setStorageConsent(e.target.checked)}/> I agree to save this graph and summary in this browser.</label><button className="primary" disabled={!storageConsent} onClick={save}>Save session</button></>}</section>
        <button className="primary" onClick={()=>navigate('Live')}>Start another session →</button>
      </>:<><p>Finish a live session or choose a saved graph from History.</p><button className="primary" onClick={()=>navigate('Live')}>Open live camera</button></>}</>}
      {screen==='History'&&<><p className="eyebrow">SAVED CAMERA SESSIONS</p><h1>Your previous graphs.</h1><section className="panel"><h2>{sessions.length?sessions.length+' saved sessions':'No camera sessions saved yet'}</h2>{sessions.map(s=><div className="history-row" key={s.id}><div><strong>{Number.isFinite(s.average)?s.average.toFixed(1)+'/10 · average experimental index':'Insufficient signal coverage'}</strong><p>{new Date(s.created_at).toLocaleString()} · {s.coveragePercent.toFixed(0)}% coverage</p></div><div><button className="secondary" onClick={()=>{setResult(s);navigate('Results');}}>View graph</button><button className="secondary" onClick={()=>remove(s.id)}>Delete</button></div></div>)}{!sessions.length&&<button className="primary" onClick={()=>navigate('Live')}>Start a live session</button>}</section></>}
      {screen==='Experiment'&&<Experiment/>}
    </main>
    <footer>Experimental facial behavior index, not a diagnosis or validated stress measurement. Camera processing stays in your browser. No video recording or upload.</footer>
  </div>;
}
createRoot(document.getElementById('root')).render(<App/>);
