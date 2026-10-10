import React, {useEffect, useRef, useState} from 'react';
import {FaceLandmarker, FilesetResolver} from '@mediapipe/tasks-vision';
import {assessFrame, summarize} from './scanMetrics';

const DURATION = 30;
export default function CameraScan({onComplete}) {
  const [consent, setConsent] = useState(false);
  const [state, setState] = useState('idle');
  const [error, setError] = useState('');
  const [feedback, setFeedback] = useState('');
  const [seconds, setSeconds] = useState(0);
  const [good, setGood] = useState(false);
  const video = useRef(null), overlay = useRef(null), runtime = useRef({});
  const mounted = useRef(true);
  function stop() {
    const r = runtime.current;
    cancelAnimationFrame(r.frame);
    r.stream?.getTracks().forEach(t => t.stop());
    r.model?.close();
    if (video.current) video.current.srcObject = null;
    runtime.current = {};
  }
  useEffect(() => {
    mounted.current = true;
    const hide = () => {if (document.hidden) {stop();setState('idle');setGood(false);}};
    document.addEventListener('visibilitychange', hide);
    return () => {mounted.current = false;document.removeEventListener('visibilitychange',hide);stop();};
  }, []);
  async function start() {
    stop(); setError(''); setState('loading');
    const r = runtime.current;
    try {
      if (!navigator.mediaDevices?.getUserMedia) throw new Error('Camera access requires localhost or HTTPS and a supported browser.');
      r.stream = await navigator.mediaDevices.getUserMedia({audio:false, video:{facingMode:'user', width:{ideal:640},height:{ideal:480}}});
      if (!mounted.current || runtime.current !== r) {r.stream.getTracks().forEach(t => t.stop()); return;}
      video.current.srcObject = r.stream;
      await video.current.play();
      if (!mounted.current || runtime.current !== r) return;
      const files = await FilesetResolver.forVisionTasks(`${import.meta.env.BASE_URL}mediapipe/wasm`);
      if (!mounted.current || runtime.current !== r) return;
      r.model = await FaceLandmarker.createFromOptions(files, {baseOptions:{modelAssetPath:`${import.meta.env.BASE_URL}mediapipe/face_landmarker.task`,delegate:'CPU'}, runningMode:'VIDEO',numFaces:2,outputFaceBlendshapes:true});
      if (!mounted.current || runtime.current !== r) {r.model.close(); return;}
      r.sampleCanvas = document.createElement('canvas'); r.sampleCanvas.width=64; r.sampleCanvas.height=48;
      r.lastVideoTime=-1; r.lastRun=0; setState('ready');
      tick();
    } catch (e) {
      if (!mounted.current || runtime.current !== r) return;
      stop(); setState('idle');
      setError(e.name === 'NotAllowedError' ? 'Camera permission was denied. Allow camera access in browser settings, then retry.' : e.name === 'NotFoundError' ? 'No camera found. Connect a camera and retry.' : e.name === 'NotReadableError' ? 'Camera is busy. Close other camera apps and retry.' : e.message || 'Could not start facial analysis. Please retry.');
    }
  }
  function tick() {
    const r = runtime.current, v = video.current;
    if (!r.model || !v || !mounted.current) return;
    const now = performance.now();
    if (r.scan && (now-r.scan.start)/1000 >= DURATION) {
      const summary=summarize(r.scan.samples,r.scan.total,(now-r.scan.start)/1000);
      stop(); setState('done'); onComplete(summary); return;
    }
    if (r.scan) setSeconds(Math.min(DURATION,Math.floor((now-r.scan.start)/1000)));
    if (v.readyState >= 2 && v.currentTime !== r.lastVideoTime && now-r.lastRun >= 100) {
      r.lastRun=now; r.lastVideoTime=v.currentTime;
      try {
        const result=r.model.detectForVideo(v,now);
        const ctx=r.sampleCanvas.getContext('2d',{willReadFrequently:true}); ctx.drawImage(v,0,0,64,48);
        const pixels=ctx.getImageData(0,0,64,48).data;
        let brightness=0; for(let i=0;i<pixels.length;i+=4) brightness+=(pixels[i]+pixels[i+1]+pixels[i+2])/3;
        brightness/=pixels.length/4;
        const points=result.faceLandmarks[0];
        const quality=assessFrame(points,result.faceLandmarks.length,brightness,r.previous);
        r.previous=quality.center; r.good=quality.good; setGood(quality.good); setFeedback(quality.reason);
        const canvas=overlay.current;
        if(canvas) {
          canvas.width=v.videoWidth; canvas.height=v.videoHeight;
          const draw=canvas.getContext('2d'); draw.clearRect(0,0,canvas.width,canvas.height);
          draw.fillStyle=quality.good ? '#b7e6a1' : '#ffd49b';
          points?.filter((_,i)=>i%5===0).forEach(p=>{draw.beginPath();draw.arc(p.x*canvas.width,p.y*canvas.height,1.8,0,Math.PI*2);draw.fill();});
        }
        if(r.scan) {
          r.scan.total++;
          if(quality.good) {
            const shapes=Object.fromEntries((result.faceBlendshapes[0]?.categories||[]).map(c=>[c.categoryName,c.score]));
            r.scan.samples.push({blink:((shapes.eyeBlinkLeft||0)+(shapes.eyeBlinkRight||0))/2,brow:((shapes.browDownLeft||0)+(shapes.browDownRight||0))/2,movement:quality.movement});
          }
          const elapsed=(now-r.scan.start)/1000; setSeconds(Math.min(DURATION,Math.floor(elapsed)));
          if(elapsed>=DURATION) {
            const summary=summarize(r.scan.samples,r.scan.total,elapsed);
            stop(); setState('done'); onComplete(summary); return;
          }
        }
      } catch {stop();setState('idle');setError('Facial analysis stopped unexpectedly. Please retry.');return;}
    }
    r.frame=requestAnimationFrame(tick);
  }
  function begin() {runtime.current.scan={start:performance.now(),samples:[],total:0};setSeconds(0);setState('scanning');}
  const active=['loading','ready','scanning'].includes(state);
  return <section className="panel">
    <h2>A private camera check-in</h2>
    <p>This 30-second scan samples facial movement. It does not measure stress or pulse. Video stays in your browser and is not recorded, uploaded, or saved.</p>
    <label className="consent"><input type="checkbox" checked={consent} disabled={active} onChange={e=>setConsent(e.target.checked)}/> I agree to local camera processing for this check-in.</label>
    <div className="camera"><video ref={video} autoPlay playsInline muted/><canvas ref={overlay} aria-hidden="true"/>{!active && <div className="camera-placeholder">{state==='done' ? 'Scan finished · camera stopped' : 'Your camera preview will appear here'}</div>}</div>
    <p role="status" className={good ? 'quality good' : 'quality'}>{state==='loading' ? 'Starting camera and loading facial analysis…' : active ? feedback : 'Sit facing a light source, with only your face in view.'}</p>
    {error && <p role="alert" className="camera-error">{error}</p>}
    {state==='scanning' && <><progress max={DURATION} value={seconds} aria-label="Scan progress"/><p>{seconds} / {DURATION} seconds · Only usable frames count toward quality.</p></>}
    {!active && <button className="primary" disabled={!consent} onClick={start}>{state==='done' ? 'Scan again' : 'Enable camera'}</button>}
    {state==='ready' && <button className="primary" disabled={!good} onClick={begin}>Start 30-second scan</button>}
    {active && <button className="secondary" onClick={()=>{stop();setState('idle');setSeconds(0);}}>Cancel and stop camera</button>}
    <p className="fine">Scan-quality thresholds are provisional engineering checks, not validated clinical measurements.</p>
  </section>;
}
