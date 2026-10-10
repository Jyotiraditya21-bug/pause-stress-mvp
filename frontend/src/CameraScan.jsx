import React, {useEffect,useRef,useState} from 'react';
import {FaceLandmarker,FilesetResolver} from '@mediapipe/tasks-vision';
import {assessFrame} from './scanMetrics';
import {LiveIndex,headPose,BASELINE_SECONDS} from './liveIndex';
import LiveGraph from './LiveGraph';

const MAX_SECONDS=300;
export default function CameraScan({onComplete}) {
  const [consent,setConsent]=useState(false),[state,setState]=useState('idle');
  const [error,setError]=useState(''),[feedback,setFeedback]=useState('');
  const [seconds,setSeconds]=useState(0),[good,setGood]=useState(false);
  const [points,setPoints]=useState([]),[reading,setReading]=useState(null),[phase,setPhase]=useState('baseline');
  const video=useRef(null),overlay=useRef(null),runtime=useRef({}),mounted=useRef(true);
  function stop() {
    const r=runtime.current;cancelAnimationFrame(r.frame);
    r.stream?.getTracks().forEach(t=>t.stop());r.model?.close();
    if(video.current) video.current.srcObject=null;
    runtime.current={};
  }
  useEffect(()=>{
    mounted.current=true;
    const hide=()=>{if(document.hidden){stop();setState('idle');setReading(null);setGood(false);setError('Camera stopped because this page was hidden. Start again to recalibrate.');}};
    document.addEventListener('visibilitychange',hide);
    return()=>{mounted.current=false;document.removeEventListener('visibilitychange',hide);stop();};
  },[]);
  function finish() {
    const r=runtime.current;
    if(!r.scan) return;
    const duration=Math.min(MAX_SECONDS,(performance.now()-r.scan.start)/1000);
    const coverage=r.scan.total ? 100*r.scan.valid/r.scan.total : 0;
    const scores=r.scan.points.map(p=>p.value).filter(Number.isFinite);
    const finalPoint=r.scan.points.at(-1);
    const summary={id:crypto.randomUUID(),created_at:new Date().toISOString(),source:'fixed-facial-index-v1',
      points:r.scan.points,coveragePercent:coverage,frames:r.scan.total,validFrames:r.scan.valid,
      durationSeconds:duration,quality:coverage>=40&&scores.length?'good':'poor',
      average:coverage>=40&&scores.length?scores.reduce((a,b)=>a+b,0)/scores.length:null,
      latest:coverage>=40&&Number.isFinite(finalPoint?.value)?finalPoint.value:null};
    stop();setState('done');setReading(null);onComplete(summary);
  }
  async function start() {
    stop();setError('');setPoints([]);setReading(null);setSeconds(0);setState('loading');setGood(false);
    const r=runtime.current;
    try {
      if(!navigator.mediaDevices?.getUserMedia) throw new Error('Camera access requires HTTPS or localhost and a supported browser.');
      r.stream=await navigator.mediaDevices.getUserMedia({audio:false,video:{facingMode:'user',width:{ideal:640},height:{ideal:480}}});
      if(!mounted.current||runtime.current!==r){r.stream.getTracks().forEach(t=>t.stop());return;}
      r.stream.getVideoTracks().forEach(track=>track.addEventListener('ended',()=>{
        if(mounted.current&&runtime.current===r){stop();setState('idle');setReading(null);setError('Camera disconnected. Reconnect it and start again.');}
      }));
      video.current.srcObject=r.stream;await video.current.play();
      if(!mounted.current||runtime.current!==r) return;
      const files=await FilesetResolver.forVisionTasks(`${import.meta.env.BASE_URL}mediapipe/wasm`);
      if(!mounted.current||runtime.current!==r) return;
      r.model=await FaceLandmarker.createFromOptions(files,{baseOptions:{modelAssetPath:`${import.meta.env.BASE_URL}mediapipe/face_landmarker.task`,delegate:'CPU'},runningMode:'VIDEO',numFaces:2,outputFacialTransformationMatrixes:true});
      if(!mounted.current||runtime.current!==r){r.model.close();return;}
      r.sampleCanvas=document.createElement('canvas');r.sampleCanvas.width=64;r.sampleCanvas.height=48;
      r.lastVideoTime=-1;r.lastRun=0;setState('ready');tick();
    } catch(e) {
      if(!mounted.current||runtime.current!==r) return;
      stop();setState('idle');
      setError(e.name==='NotAllowedError'?'Camera permission denied. Allow access in browser settings and retry.':e.name==='NotFoundError'?'No camera found. Connect a camera and retry.':e.name==='NotReadableError'?'Camera is busy. Close other camera apps and retry.':e.message||'Could not start facial analysis.');
    }
  }
  function tick() {
    const r=runtime.current,v=video.current;
    if(!r.model||!v||!mounted.current) return;
    const now=performance.now();
    if(r.scan&&(now-r.scan.start)/1000>=MAX_SECONDS){finish();return;}
    if(r.scan){
      const elapsed=(now-r.scan.start)/1000;setSeconds(Math.floor(elapsed));
      if(now-r.lastRun>1500){
        setReading(null);setGood(false);r.good=false;setFeedback('Reading paused: no fresh camera frames.');
        r.scan.index.previous=null;r.scan.index.closed=null;
        if(elapsed-r.scan.lastPlot>=1){r.scan.points.push({time:elapsed,value:null});r.scan.lastPlot=elapsed;setPoints([...r.scan.points]);}
      }
    }
    if(v.readyState>=2&&v.currentTime!==r.lastVideoTime&&now-r.lastRun>=100) {
      r.lastRun=now;r.lastVideoTime=v.currentTime;
      try {
        const result=r.model.detectForVideo(v,now);
        const ctx=r.sampleCanvas.getContext('2d',{willReadFrequently:true});ctx.drawImage(v,0,0,64,48);
        const pixels=ctx.getImageData(0,0,64,48).data;
        let brightness=0;for(let i=0;i<pixels.length;i+=4)brightness+=(pixels[i]+pixels[i+1]+pixels[i+2])/3;
        brightness/=pixels.length/4;
        const landmarks=result.faceLandmarks[0];
        const quality=assessFrame(landmarks,result.faceLandmarks.length,brightness,r.previous);
        r.previous=quality.center;
        const pose=headPose(result.facialTransformationMatrixes[0]);
        const facing=!!pose&&Math.abs(pose[0])<=35&&Math.abs(pose[1])<=35;
        r.good=quality.good&&facing;setGood(r.good);
        setFeedback(quality.good&&!facing?'Face the camera directly for a usable reading.':quality.reason);
        const canvas=overlay.current;
        if(canvas){
          canvas.width=v.videoWidth;canvas.height=v.videoHeight;
          const draw=canvas.getContext('2d');draw.clearRect(0,0,canvas.width,canvas.height);draw.fillStyle=r.good?'#b7e6a1':'#ffd49b';
          landmarks?.filter((_,i)=>i%5===0).forEach(p=>{draw.beginPath();draw.arc(p.x*canvas.width,p.y*canvas.height,1.8,0,Math.PI*2);draw.fill();});
        }
        if(r.scan) {
          const elapsed=(now-r.scan.start)/1000;
          const xy=landmarks?.map(p=>[p.x*v.videoWidth,p.y*v.videoHeight])||[];
          const observation=r.scan.index.update(elapsed,xy,pose,quality.good);
          setSeconds(Math.floor(elapsed));setPhase(observation.phase);setReading(observation.value);
          if(observation.reason)setFeedback(observation.reason);
          if(observation.phase==='failed'){stop();setState('idle');setError(observation.reason);return;}
          if(observation.phase==='live'){r.scan.total++;if(observation.valid)r.scan.valid++;}
          // One representative sample per second; rejected seconds remain explicit gaps.
          if(elapsed-r.scan.lastPlot>=1) {
            r.scan.points.push({time:elapsed,value:observation.value});r.scan.lastPlot=elapsed;
            setPoints([...r.scan.points]);
          } else if(observation.phase==='live'&&!observation.valid&&r.scan.points.length&&Number.isFinite(r.scan.points.at(-1).value)) {
            r.scan.points.push({time:elapsed,value:null});r.scan.lastPlot=elapsed;setPoints([...r.scan.points]);
          }
        }
      } catch {stop();setState('idle');setReading(null);setError('Facial analysis stopped unexpectedly. Please retry.');return;}
    }
    r.frame=requestAnimationFrame(tick);
  }
  function begin() {
    const r=runtime.current;if(!r.good)return;
    r.scan={start:performance.now(),index:new LiveIndex(),points:[],lastPlot:-1,total:0,valid:0};
    setSeconds(0);setPoints([]);setReading(null);setPhase('baseline');setState('scanning');
  }
  const active=['loading','ready','scanning'].includes(state);
  return <>
    <section className="panel">
      <h2>Your live camera session</h2>
      <p>Calibrate for 25 seconds while relaxed, then watch an experimental facial index change live. No questionnaire rating is used. Video stays in this browser; it is not recorded or uploaded.</p>
      <label className="consent"><input type="checkbox" checked={consent} disabled={active} onChange={e=>setConsent(e.target.checked)}/> I agree to local camera processing for this session.</label>
      <div className="live-layout"><div>
        <div className="camera"><video ref={video} autoPlay playsInline muted/><canvas ref={overlay} aria-hidden="true"/>{!active&&<div className="camera-placeholder">Camera stopped</div>}</div>
        <p role="status" className={good?'quality good':'quality'}>{state==='loading'?'Starting camera and facial analysis…':active?feedback:'Face the camera with even lighting and only one person in view.'}</p>
      </div><div className="live-reading">
        <p className="eyebrow">EXPERIMENTAL FACIAL INDEX</p>
        <p className="rating">{Number.isFinite(reading)?reading.toFixed(1):'—'}<small> / 10</small></p>
        <p>{state==='scanning'&&phase==='baseline'?`Calibrating · ${Math.max(0,BASELINE_SECONDS-seconds)} seconds remaining`:state==='scanning'?Number.isFinite(reading)?'Live camera-derived reading':'Paused · no usable reading':'Start a session to see live readings.'}</p>
        <p>0 = high stress<br/>10 = no stress</p>
        <p className="fine">Experimental scale labels. This is a facial behavior proxy, not a verified measurement of stress. Your personal baseline maps to 5/10.</p>
      </div></div>
      {error&&<p role="alert" className="camera-error">{error}</p>}
      {state==='scanning'&&<p>{seconds}s elapsed · Session ends at {MAX_SECONDS}s. {phase==='baseline'?'Stay relaxed and avoid speaking during calibration.':'Speaking, smiling and poor framing pause readings.'}</p>}
      {!active&&<button className="primary" disabled={!consent} onClick={start}>Enable camera</button>}
      {state==='ready'&&<button className="primary" disabled={!good} onClick={begin}>Calibrate and start live graph</button>}
      {state==='scanning'&&phase==='live'&&<button className="primary" onClick={finish}>Finish and review session</button>}
      {active&&<button className="secondary" onClick={()=>{stop();setState('idle');setReading(null);setSeconds(0);setPoints([]);}}>Cancel and stop camera</button>}
    </section>
    <LiveGraph points={points} live/>
  </>;
}
