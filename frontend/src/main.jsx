import {api, browserOnly} from './api';
import React, {useEffect, useState} from 'react';
import {createRoot} from 'react-dom/client';
import './style.css';
import CameraScan from './CameraScan';
import Questionnaire from './Questionnaire';
import Guidance from './Guidance';
import TrendChart from './TrendChart';

function App() {
  const [step, setStep] = useState('camera');
  const [result, setResult] = useState(null);
  const [deleting, setDeleting] = useState(null);
  const [historyError, setHistoryError] = useState('');
  const [scan, setScan] = useState(null);
  const [screen, setScreen] = useState('Overview');
  const [health, setHealth] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState('');
  async function load() {
    setLoading(true); setError('');
    await Promise.all(['/api/health', '/api/sessions'].map(async url => {
      const response = await api(url);
      if (!response.ok) throw new Error('Backend unavailable');
      return response.json();
    })).then(([status, history]) => {setHealth(status); setSessions(history.sessions);})
      .catch(() => setError('Cannot connect to the backend. Start FastAPI on port 8000.'))
      .finally(()=>setLoading(false));
  }
  useEffect(() => {load();}, []);
  function saved(session) {setNotice('Check-in saved on this Mac.');setResult(session); setSessions(previous => [session, ...previous]); setScreen('Results'); setStep('camera'); setScan(null);}
  async function remove(id) {
    if (!window.confirm('Delete this saved check-in permanently?')) return;
    setDeleting(id); setHistoryError('');
    try {
      const response=await api('/api/sessions/'+id,{method:'DELETE'});
      if(!response.ok && response.status!==404) throw new Error('Could not delete. Please retry.');
      setNotice('Check-in deleted.');
      setSessions(previous=>previous.filter(item=>item.id!==id));
      if(result?.id===id) setResult(null);
    } catch(e) {setHistoryError(e.message);} finally {setDeleting(null);}
  }
  const displayedScan = result?.camera_metrics;
  return <div className="shell">
    <header><a className="brand" href="#" onClick={() => setScreen('Overview')}>◉ pause<span>WELLBEING CHECK-IN</span></a><div className="tag">{browserOnly ? 'Browser demo' : 'Local MVP · Ready'}</div></header>
    <nav aria-label="Main navigation">{['Overview', 'Check-in', 'Results', 'History'].map(item => <button key={item} aria-current={screen === item ? 'page' : undefined} className={screen === item ? 'active' : ''} onClick={() => setScreen(item)}>{item}</button>)}</nav>
    <main><p className="save-notice" role="status">{notice}</p>
    {screen === 'Overview' && <><p className="eyebrow">A MOMENT FOR YOURSELF</p><h1>Pause. Check in.<br/><em>Understand your patterns.</em></h1><p className="intro">A private space to reflect on how you feel, explore experimental camera signals, and follow your wellbeing over time.</p><button className="primary" onClick={() => setScreen('Check-in')}>Explore your check-in →</button><div className="cards"><article><span>01 / REFLECT</span><h2>How are you feeling?</h2><p>A brief self-report gives your experience a voice.</p></article><article><span>02 / OBSERVE</span><h2>Explore camera signals</h2><p>Facial movement will be shown separately from your reported stress.</p></article><article><span>03 / ACT</span><h2>Find your next step</h2><p>Choose optional AI guidance or local suggestions after your check-in.</p></article></div></>}
    {screen === 'Check-in' && <><p className="eyebrow">YOUR CHECK-IN</p><h1>Take a moment to pause.</h1>{step === 'camera' ? <><CameraScan onComplete={value=>{setScan(value);setStep('questionnaire');}}/><button className="secondary" onClick={()=>{setScan(null);setStep('questionnaire');}}>Skip camera · answer questions</button></> : <><Questionnaire scan={scan} onSaved={saved}/><button className="secondary" onClick={()=>{setScan(null);setStep('camera');}}>Back to camera</button></>}</>}
    {screen === 'Results' && <><p className="eyebrow">CLEAR, SEPARATE RESULTS</p><h1>Evidence before estimates.</h1>{result && <p>Saved {new Date(result.created_at).toLocaleString()}</p>}<div className="cards"><article><h2>Reported stress</h2>{result ? <><p className="rating">{result.self_reported_stress}<small> / 10</small></p><p>Your rating, not an AI prediction.</p><p>Sleep: {result.context?.sleep_hours} hours<br/>Workload: {result.context?.workload ?? 'Not recorded'}<br/>Caffeine: {result.context?.caffeine == null ? 'Not recorded' : result.context.caffeine ? 'Yes' : 'No'}<br/>Recent exercise: {result.context?.recent_exercise == null ? 'Not recorded' : result.context.recent_exercise ? 'Yes' : 'No'}</p></> : <><p>No saved check-in selected.</p><button className="secondary" onClick={()=>setScreen('History')}>Choose from History</button></>}</article><article><h2>Camera signals</h2><p>{displayedScan ? `Scan quality: ${displayedScan.quality} · ${displayedScan.usablePercent}% usable frames` : 'No camera metrics in this check-in.'}</p>{displayedScan?.quality==='good' ? <><p>Mean blink coefficient: {displayedScan.meanBlinkCoefficient?.toFixed(3)}<br/>Mean brow coefficient: {displayedScan.meanBrowCoefficient?.toFixed(3)}<br/>Mean movement: {displayedScan.meanMovement?.toFixed(4)}</p><p>These coefficients are not stress scores.</p></> : displayedScan && <p>Poor-quality scan. Feature values are withheld.</p>}</article><article><Guidance key={result?.id || "empty"} session={result} onUpdate={updated=>{setResult(previous=>previous?.id===updated.id ? updated : previous);setSessions(previous=>previous.map(item=>item.id===updated.id ? updated : item));}}/></article></div><button className="primary" onClick={()=>{setStep('camera');setScan(null);setScreen('Check-in');}}>New check-in →</button></>}
    {screen === 'History' && <><p className="eyebrow">YOUR PATTERNS</p><h1>A little perspective.</h1>{loading ? <p role="status">Loading your saved check-ins…</p> : error ? <p>History is unavailable until the backend reconnects.</p> : <TrendChart sessions={sessions}/>}<section className="panel"><h2>{sessions.length ? `${sessions.length} saved check-ins` : 'No check-ins yet'}</h2>{historyError && <p role="alert">{historyError}</p>}{sessions.map(item=><div className="history-row" key={item.id}><div><strong>{item.self_reported_stress} / 10 · reported stress</strong><p>{new Date(item.created_at).toLocaleString()} · Camera: {item.scan_quality}</p></div><div><button className="secondary" onClick={()=>{setResult(item);setScreen('Results');}}>View</button><button className="secondary" disabled={deleting===item.id} onClick={()=>remove(item.id)}>{deleting===item.id ? 'Deleting…' : 'Delete'}</button></div></div>)}{!sessions.length && !loading && !error && <><p>Your saved check-ins will appear here.</p><button className="primary" onClick={()=>setScreen('Check-in')}>Create your first check-in →</button></>}</section></>}
    <section className="status" aria-live="polite"><strong>System status</strong>{error ? <><p role="alert">{error}</p><button className="secondary" disabled={loading} onClick={load}>Reconnect</button></> : <p>{health ? `${browserOnly ? 'Browser storage ready' : 'Backend connected · SQLite ready'} · Gemini key ${health.gemini_configured ? 'configured' : 'not configured'}` : 'Connecting to local backend…'}</p>}</section>
    </main><footer>Wellbeing exploration, not medical diagnosis. Camera processing stays in your browser. No video recording or AI stress prediction.</footer>
  </div>;
}
createRoot(document.getElementById('root')).render(<App/>);
