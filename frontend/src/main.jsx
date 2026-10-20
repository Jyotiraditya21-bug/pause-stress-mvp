import GuidedStudy from './components/GuidedStudy.jsx';
import './fonts.css';
import React,{Suspense,lazy,useEffect,useState} from 'react';
import {createRoot} from 'react-dom/client';
import './pause-ui.css';
import ScanScreen from './components/ScanScreen.jsx';
import ResultCard from './components/ResultCard.jsx';
import Icon from './components/Icon.jsx';
import {readCameraSessions,readCameraSessionState,repairCameraSessions,deleteRecoveryBackups,saveCameraSession,deleteCameraSession} from './cameraSessions.js';
import {readBaseline,resetBaseline,saveBaseline} from './baselineStorage.js';
import {initializeMonitoring} from './monitoring.js';
import {registerSW} from 'virtual:pwa-register';

const HistoryPage=lazy(()=>import('./pages/HistoryPage.jsx'));
const Experiment=lazy(()=>import('./Experiment.jsx'));
const PrivacyPage=lazy(()=>import('./pages/InfoPage.jsx').then(m=>({default:m.PrivacyPage})));
const AboutPage=lazy(()=>import('./pages/InfoPage.jsx').then(m=>({default:m.AboutPage})));
const ONBOARDING_KEY='pause.onboarded.v1';

function wasOnboarded(){try{return localStorage.getItem(ONBOARDING_KEY)==='1'}catch{return false}}
function setOnboarded(){try{localStorage.setItem(ONBOARDING_KEY,'1')}catch{}}

function ResultScreen({result,isSaved,onRetry,onDone,onSave,onCalibrate,baseline}){
  const flags=Object.entries(result.qualityFlags||{}).filter(([,value])=>value).map(([key])=>key);
  const usable=result.status!=='failed'&&Number.isFinite(result.average);
  const caption=usable&&<div className="result-caption">
      {result.acceptancePolicy&&<p className="mode-line">Prospective acquisition policy · experimental, not validated</p>}
      <p className="mode-line">{result.mode==='baseline'?'Compared with your calm baseline':result.mode==='calibration'?'Calm baseline saved':'Compared with a fixed generic face reference'}</p>
      {result.range&&<p className="range-line">Within-scan variation: {result.range[0].toFixed(1)}–{result.range[1].toFixed(1)} · not a confidence interval</p>}
    </div>;
  const actions=usable&&<>
      <button className="pz-btn pz-btn-primary" onClick={onSave} disabled={isSaved}>{isSaved?'Result saved':'Save this result'}</button>
      <button className="pz-btn pz-btn-quiet" onClick={onRetry}>Scan again</button>
      <button className="calibrate-link" onClick={onCalibrate}>{baseline?'Recalibrate when calm':'Calibrate when calm'}</button>
    </>;
  return <section className="result-screen"><h1>Calm index result</h1><ResultCard status={result.status||result.quality} score={result.average} windows={result.windowScores||result.points?.map(p=>p.value)||[]} reason={result.failReason||result.reason} warnings={result.warnings||[]} consensusMask={result.consensusWindowMask??result.windowDiagnostics?.windows?.map(w=>w.inConsensus)} coverageDetails={result.coverageDetails} onRetry={onRetry} onDone={onDone} caption={caption} actions={actions}>
    {usable&&
      <details className="pz-panel details"><summary>Details</summary><dl><dt>Mode</dt><dd>{result.mode}</dd><dt>Algorithm</dt><dd>{result.algoVersion}</dd>{result.mlResult&&<><dt>Experimental dataset-class output</dt><dd>{(result.mlResult.averageStressProbability*100).toFixed(1)}% for the stress class (dataset label: {result.mlResult.classification}); not a calibrated probability of your stress</dd></>}<dt>{result.coverageDetails?"Time-slot occupancy":"Legacy coverage (denominator not recorded)"}</dt><dd>{Number(result.coveragePercent||0).toFixed(0)}%</dd><dt>Quality flags</dt><dd>{flags.length?flags.join(', '):'None'}</dd>{result.tier&&<><dt>Tier</dt><dd>{result.tier}</dd><dt>Confidence</dt><dd>{result.confidence.toFixed(2)}</dd><dt>Features per window</dt><dd>{result.windowFeaturesUsed.join(', ')}</dd></>}</dl></details>
    }
    {new URLSearchParams(location.search).get('diagnostics')==='1'&&<details className="pz-panel details"><summary>Technical scan diagnostics</summary><pre style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{JSON.stringify({id:result.id,created_at:result.created_at,mode:result.mode,algoVersion:result.algoVersion,source:result.source,acquisitionVersion:result.acquisitionVersion,acceptancePolicy:result.acceptancePolicy,average:result.average,range:result.range,status:result.status,reason:result.reason,warnings:result.warnings,coveragePercent:result.coveragePercent,coverageDetails:result.coverageDetails,consensusWindowMask:result.consensusWindowMask,windowScores:result.windowScores,features:result.features,featureStats:result.featureStats,windowDiagnostics:result.windowDiagnostics??{status:"Not captured for this scan; detailed windows require a new standard scan with diagnostics=1."},reliability:result.reliability,mlResult:result.mlResult},null,2)}</pre></details>}
  </ResultCard></section>;
}

function App(){
  const lab=new URLSearchParams(location.search).get('lab')==='1';
  const fixture=import.meta.env.DEV&&new URLSearchParams(location.search).get('fixture')==='result'?{id:'e2e-result',created_at:'2026-01-01T00:00:00.000Z',average:6.2,status:'ok',quality:'good',mode:'generic',algoVersion:'quick-2.0',range:[5.8,6.6],windowScores:[6,6.1,6.2,6.3,6.2,6.1,6.2,6.3,6.4],coveragePercent:100,qualityFlags:{}}:null;
  const [screen,setScreen]=useState(()=>fixture?'Result':wasOnboarded()?'Scan':'Onboarding');
  const [result,setResult]=useState(fixture),[calibrating,setCalibrating]=useState(false);
  const [baseline,setBaselineState]=useState(()=>readBaseline());
  const [mlEnabled,setMlEnabled]=useState(()=>{try{return localStorage.getItem('pause.ml.enabled')==='1'}catch{return false}});
  const [sessions,setSessions]=useState(()=>{try{return readCameraSessions()}catch{return[]}});
  const [storageState,setStorageState]=useState(()=>readCameraSessionState());
  const [notice,setNotice]=useState(''),[error,setError]=useState('');
  function toggleML(){const next=!mlEnabled;setMlEnabled(next);try{localStorage.setItem('pause.ml.enabled',next?'1':'0')}catch{}setNotice(next?'Experimental Neural Model enabled for camera scans.':'Neural model disabled. Using geometric QuickIndex.');}
  useEffect(()=>{
    initializeMonitoring().catch(()=>{});registerSW({immediate:false});
  },[]);
  const navigate=(next,{calibration=false}={})=>{setCalibrating(calibration);if(next==='Scan')setBaselineState(readBaseline());setScreen(next);setNotice('');setError('')};
  function complete(session){
    const completeBaseline=['brow_furrow','lip_press','lip_corner','jaw_clench'].every(k=>Number.isFinite(session.featureStats?.[k]?.median)&&Number.isFinite(session.featureStats?.[k]?.mad));
    if(calibrating&&session.status!=='failed'&&completeBaseline){
      const saved=saveBaseline(session.featureStats);setBaselineState(saved);session.mode=saved?'calibration':'generic';
      setNotice(saved?'Your calm baseline is active.':'The baseline could not be saved in this browser.');
    }
    else if(calibrating){session.mode='generic';setNotice('No new baseline was saved. Calibrate with your mouth relaxed and your face toward the camera.');}
    setResult(session);setCalibrating(false);setScreen('Result');
  }
  function startCalibration(){setResult(null);navigate('Scan',{calibration:true})}
  function recoverHistory(){try{repairCameraSessions();setSessions(readCameraSessions());setStorageState(readCameraSessionState());setNotice('History recovered. Valid scans were kept and the original data was backed up in this browser.');setError('')}catch{setError('Recovery could not create a backup. Free some browser storage and try again. Your original data was kept.')}}
  function clearRecovery(){try{deleteRecoveryBackups();setNotice('Recovery backups deleted. Your saved scans were kept.')}catch{setError('Recovery backups could not be deleted. Check browser storage settings.')}}
  function save(){try{saveCameraSession(result);setSessions(readCameraSessions());setNotice('Result saved in this browser.')}catch{setStorageState(readCameraSessionState());setError('The result could not be saved. Check the history recovery notice or available browser storage, then try again.')}}
  function remove(id){try{deleteCameraSession(id);setSessions(readCameraSessions());setNotice('Saved result deleted.')}catch{setStorageState(readCameraSessionState());setError('The saved result could not be deleted. Check the history recovery notice or browser storage settings.')}}
  function clearBaseline(){if(resetBaseline()){setBaselineState(null);setNotice('Your calm baseline was reset.')}else setError('The baseline could not be reset. Check browser storage settings, then try again.')}
  const saved=!!result&&sessions.some(row=>row.id===result.id);
  return <div className="app-shell">
    <header className="site-header"><button className="brand" onClick={()=>navigate('Scan')} aria-label="Pause home"><span className="brand-mark" aria-hidden="true"><i/><i/></span>pause</button><nav className="main-nav" aria-label="Primary"><button aria-current={screen==='Scan'?'page':undefined} onClick={()=>navigate('Scan')}><Icon name="scan" size={17}/>Scan</button><button aria-current={screen==='History'?'page':undefined} onClick={()=>navigate('History')}><Icon name="history" size={17}/>History</button>{lab&&<button aria-current={screen==='Lab'?'page':undefined} onClick={()=>navigate('Lab')}>Lab</button>}</nav></header>
    {notice&&<p className="notice" role="status">{notice}</p>}{error&&<p className="error-banner" role="alert">{error}</p>}
    {(storageState.unreadable||storageState.invalidCount>0)&&<section className="notice" aria-label="History recovery"><p>Some saved history could not be read. Valid scans are still available. Recover history to back up the original data on this device and enable saving and deleting again.</p><button className="pz-btn pz-btn-quiet" onClick={recoverHistory}>Recover saved history</button></section>}
    {new URLSearchParams(location.search).get('study')==='1'&&new URLSearchParams(location.search).get('policy')==='prospective-1'&&<GuidedStudy result={result} onStart={()=>navigate('Scan')}/>}
    <div className="app-content"><Suspense key={screen} fallback={<main className="page"><p>Loading…</p></main>}>
      {screen==='Onboarding'&&<main className="page onboarding"><h1>A quiet moment to check in</h1><p>Pause gives you an experimental Calm index after a 10-second camera scan. Processing stays on your device, and the result cannot tell how stressed you feel.</p><button className="pz-btn pz-btn-primary" onClick={()=>{setOnboarded();navigate('Scan')}}>Continue to scan</button></main>}
      {screen==='Scan'&&<ScanScreen onComplete={complete} baseline={calibrating?null:baseline} calibrating={calibrating}/>} 
      {screen==='Result'&&result&&<ResultScreen result={result} isSaved={saved} onRetry={()=>navigate('Scan')} onDone={()=>navigate('History')} onSave={save} onCalibrate={startCalibration} baseline={baseline}/>} 
      {screen==='History'&&<HistoryPage sessions={sessions} onView={session=>{setResult(session);navigate('Result')}} onDelete={remove} onScan={()=>navigate('Scan')}/>} 
      {screen==='Settings'&&<main className="page settings"><h1>Settings</h1><section className="pz-panel"><h2>Personal baseline</h2><p>Calibrate when calm so future scores compare you with your own calm face.</p><button className="pz-btn pz-btn-primary" onClick={startCalibration}>{baseline?'Recalibrate when calm':'Calibrate when calm'}</button>{baseline&&<button className="pz-btn pz-btn-quiet" onClick={clearBaseline}>Reset baseline</button>}</section><section className="pz-panel"><h2>Experimental Neural Model (MobileNetV3)</h2><p>Trained exploratory image-level model (74.25% validation balanced accuracy, 0.8125 ROC-AUC). Evaluates face crops in real time with EMA smoothing. Runs 100% on-device in WebAssembly.</p><button className={`pz-btn ${mlEnabled?'pz-btn-primary':'pz-btn-quiet'}`} onClick={toggleML}>{mlEnabled?'Neural model enabled':'Enable neural model in scan'}</button><p className="note" style={{marginTop:'0.5rem',fontSize:'0.82rem',color:'#717672'}}>Statistical facial pattern recognition only. Training-image provenance and redistribution rights remain unknown. Image accuracy does not establish live stress accuracy. Not a medical measurement or clinical stress diagnosis.</p></section><section className="pz-panel"><h2>History recovery backups</h2><p>Recovery keeps an original copy on this device, including any scans later deleted from History. Delete recovery backups when you no longer need them. This leaves your current saved scans intact.</p><button className="pz-btn pz-btn-quiet" onClick={clearRecovery}>Delete recovery backups</button></section></main>}
      {screen==='Privacy'&&<PrivacyPage/>}{screen==='About'&&<AboutPage/>}{screen==='Lab'&&lab&&<main className="page lab-page"><h1>Lab</h1><Experiment/></main>}
    </Suspense></div>
    <footer className="site-footer"><span className="footer-note"><Icon name="shield" size={14}/>A private moment. A little more awareness.</span><div className="footer-links"><button onClick={()=>navigate('Privacy')}>Privacy</button><button onClick={()=>navigate('About')}>About this index</button><button onClick={()=>navigate('Settings')}>Settings</button></div></footer>
  </div>;
}

class ErrorBoundary extends React.Component{
  constructor(props){super(props);this.state={failed:false}}
  static getDerivedStateFromError(){return{failed:true}}
  componentDidCatch(error,info){console.error('Pause render error',error,info)}
  render(){return this.state.failed?<main className="page"><h1>Pause could not continue</h1><p>Reload the page to start again.</p><button className="pz-btn pz-btn-primary" onClick={()=>location.reload()}>Reload</button></main>:this.props.children}
}

createRoot(document.getElementById('root')).render(<ErrorBoundary><App/></ErrorBoundary>);
