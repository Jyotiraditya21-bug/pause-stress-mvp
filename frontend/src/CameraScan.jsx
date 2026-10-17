import React, {useEffect,useRef,useState} from 'react';
import {assessQuickFrame,faceBrightness} from './scanMetrics.js';
import {QuickIndex,geometry,headPose,SCAN_SECONDS} from './liveIndex.js';
import {awaitResource} from './resourceWait.js';
import {advanceScanState,createScanState,HARD_CAP_SECONDS} from './scanState.js';
import {trackEvent} from './monitoring.js';
import {TolerantScan,TOLERANCE_CONFIG,adaptiveState} from './tolerantScan.js';
import {getFaceBoundingBox,normalizePixelsToNCHW} from './mlInference.js';

let cachedLandmarker = null;
let landmarkerPromise = null;

export function preloadLandmarker() {
  if (cachedLandmarker) return Promise.resolve(cachedLandmarker);
  if (!landmarkerPromise) {
    landmarkerPromise = (async () => {
      const {FaceLandmarker,FilesetResolver} = await import('@mediapipe/tasks-vision');
      const base = import.meta.env.BASE_URL || '/';
      const wasmPath = base.endsWith('/') ? `${base}mediapipe/wasm` : `${base}/mediapipe/wasm`;
      const modelPath = base.endsWith('/') ? `${base}mediapipe/face_landmarker.task` : `${base}/mediapipe/face_landmarker.task`;
      const files = await FilesetResolver.forVisionTasks(wasmPath);
      const model = await FaceLandmarker.createFromOptions(files, {
        baseOptions: {modelAssetPath: modelPath, delegate: 'CPU'},
        runningMode: 'VIDEO',
        numFaces: 2,
        outputFacialTransformationMatrixes: true
      });
      cachedLandmarker = model;
      return model;
    })().catch(err => {
      landmarkerPromise = null;
      throw err;
    });
  }
  return landmarkerPromise;
}

if (typeof window !== 'undefined') {
  preloadLandmarker().catch(() => {});
}

async function loadLandmarker(isCurrent = () => true) {
  if (cachedLandmarker) return cachedLandmarker;
  const promise = preloadLandmarker();
  return awaitResource(promise, {isCurrent, message: 'Facial analysis did not start. Reload the page, then try again.'});
}

function cameraError(error) {
  if(!globalThis.isSecureContext)return 'Camera access needs a secure connection. Open the HTTPS site or use localhost.';
  if(error?.name==='NotAllowedError')return 'Camera access was blocked. Allow camera access in your browser settings, then start again.';
  if(error?.name==='NotFoundError')return 'No camera was found. Connect a camera, then start again.';
  if(error?.name==='NotReadableError')return 'The camera is being used by another app. Close that app, then start again.';
  return error?.message||'Facial analysis could not start. Reload the page, then try again.';
}

export default function CameraScan({onComplete,baseline=null,calibrating=false,render}) {
  const [state,setState]=useState('idle');
  const [error,setError]=useState(''),[hint,setHint]=useState('Center your face in view');
  const [progress,setProgress]=useState(0),[paused,setPaused]=useState(false);
  const [extended,setExtended]=useState(false);
  const [videoReady,setVideoReady]=useState(false);
  const tolerant=TOLERANCE_CONFIG.adopted||new URLSearchParams(location.search).get('tolerance')!=='0';
  const video=useRef(null),overlay=useRef(null),runtime=useRef({}),mounted=useRef(true);

  function cancelLoop(r){
    if(r.videoCallback&&video.current?.cancelVideoFrameCallback)video.current.cancelVideoFrameCallback(r.videoCallback);
    cancelAnimationFrame(r.frame);
  }
  function stop() {
    const r=runtime.current;cancelLoop(r);clearTimeout(r.timer);clearTimeout(r.completionTimer);
    r.stream?.getTracks().forEach(track=>track.stop());
    if(video.current){
      video.current.srcObject=null;
      video.current.onloadeddata=null;
      video.current.onplaying=null;
    }
    if(overlay.current){
      const ctx=overlay.current.getContext('2d');
      if(ctx)ctx.clearRect(0,0,overlay.current.width,overlay.current.height);
    }
    setVideoReady(false);
    runtime.current={};
  }
  function cancel(){stop();setState('idle');setProgress(0);setPaused(false);setHint('Center your face in view');}

  useEffect(()=>{
    mounted.current=true;
    // Preload face landmarker immediately so starting camera has zero WASM instantiation lag
    loadLandmarker().catch(()=>{});
    const hide=()=>{if(document.hidden&&(runtime.current.starting||runtime.current.stream)){cancel();setError('The camera stopped when the page was hidden. Return to this page and start again.');}};
    document.addEventListener('visibilitychange',hide);
    return()=>{mounted.current=false;document.removeEventListener('visibilitychange',hide);stop();};
  },[]);

  function complete(capped=false){
    const r=runtime.current;
    if(!r.scan||r.finishing)return;
    r.finishing=true;setState('analyzing');cancelLoop(r);
    const outcome=r.scan.index.finish(tolerant&&capped?TOLERANCE_CONFIG.maxDuration:r.scan.elapsed);
    const wall=(performance.now()-r.scan.wallStart)/1000;
    const summary={id:crypto.randomUUID(),created_at:new Date().toISOString(),source:tolerant?'quick-tolerant-index-v1':'quick-canonical-index-v3',...outcome,
      status:outcome.status,mode:calibrating?'calibration':outcome.mode,baselineId:baseline?.id||baseline?.createdAt||null,acquisitionVersion:'capture-clock-1',frames:r.scan.total,validFrames:r.scan.valid,
      durationSeconds:wall,capped,performance:{processedFrames:r.scan.allFrames,fps:r.scan.allFrames/Math.max(wall,.1),inferenceMs:r.scan.allFrames?r.scan.inferenceSum/r.scan.allFrames:null,processingMs:r.scan.allFrames?r.scan.processingSum/r.scan.allFrames:null}};
    if(!tolerant&&capped&&summary.status==='ok'){
      summary.status='limited';summary.quality='limited';summary.warnings=[...summary.warnings,'Keep your face in view so the scan finishes sooner.'];
    }
    if(r.enableML&&r.mlProbs?.length){
      const avgStress=r.mlProbs.reduce((a,b)=>a+b,0)/r.mlProbs.length;
      summary.mlResult={
        model:'MobileNetV3-Small-v1',
        samples:r.mlProbs.length,
        averageStressProbability:avgStress,
        classification:avgStress>=0.5?'stress':'nostress',
        confidence:Math.abs(avgStress-0.5)*2
      };
    }
    trackEvent(summary.status==='failed'?'scan_failed':'scan_result',{status:summary.status,reason:summary.status==='failed'?'acquisition_failed':summary.status==='limited'?'limited_confidence':'accepted'});
    // Release the camera before the brief result transition, including on cap.
    r.stream?.getTracks().forEach(track=>track.stop());
    r.completionTimer=setTimeout(()=>{
      if(!mounted.current||runtime.current!==r)return;
      stop();setState(summary.status==='failed'?'failed':'result');onComplete(summary);
    },250);
  }

  function schedule(r){
    const callback=()=>{tick();if(runtime.current===r&&r.model&&!r.finishing)schedule(r);};
    if(video.current?.requestVideoFrameCallback)r.videoCallback=video.current.requestVideoFrameCallback(callback);
    else r.frame=requestAnimationFrame(callback);
  }

  function tick(){
    const r=runtime.current,v=video.current;
    if(!r.model||!v||!mounted.current||r.finishing)return;
    const now=performance.now();
    if(v.readyState>=2&&!videoReady)setVideoReady(true);
    if(v.readyState<2||v.currentTime===r.lastVideoTime||now-r.lastRun<95)return;
    r.lastRun=now;r.lastVideoTime=v.currentTime;
    try{
      const processingStart=performance.now();
      const result=r.model.detectForVideo(v,now);
      const inferenceMs=performance.now()-processingStart;
      const ctx=r.sampleCanvas.getContext('2d',{willReadFrequently:true});ctx.drawImage(v,0,0,64,48);
      const pixels=ctx.getImageData(0,0,64,48).data;
      const landmarks=result.faceLandmarks[0];
      const brightness=faceBrightness(pixels,64,48,landmarks);
      const pose=headPose(result.facialTransformationMatrixes?.[0]);
      if(tolerant){
        r.scan.captureStart??=(performance.now()/1000);
        const elapsed=Math.min(TOLERANCE_CONFIG.maxDuration-1e-6,(performance.now()/1000)-r.scan.captureStart);
        r.scan.elapsed=elapsed;
        const xyz=landmarks?.map(p=>[p.x*v.videoWidth,p.y*v.videoHeight,p.z*v.videoWidth])||[];
        const observation=r.scan.index.update(elapsed,xyz,pose,true,{brightness,width:v.videoWidth,height:v.videoHeight,faceCount:result.faceLandmarks.length,matrix:result.facialTransformationMatrixes?.[0]});
        const machine=adaptiveState(elapsed,r.scan.index.coverage());
        r.scan.machine=machine;
        setState(machine.state);setProgress(machine.progress);setExtended(machine.extended);setPaused(false);
        setHint(machine.extended?'Almost there, small movements are fine':r.scan.index.rollingCoverage(elapsed)<TOLERANCE_CONFIG.hintCoverage?observation.reason||'Keep your face in view':'Scanning your face');
        r.scan.total++;if(observation.valid)r.scan.valid++;
      } else {
        const quality=assessQuickFrame(landmarks,result.faceLandmarks.length,brightness,r.previous);
        r.previous=quality.center;
        const poseGood=!pose||(Math.abs(pose[0])<=45&&Math.abs(pose[1])<=35);
        let mouthOpen=false,xy=[];
        if(landmarks){xy=landmarks.map(p=>[p.x*v.videoWidth,p.y*v.videoHeight]);try{mouthOpen=geometry(xy).mar>.50;}catch{}}
        const flags={...quality.qualityFlags,mouthOpen,pose:!poseGood};
        const good=quality.good&&poseGood;
        const specificHint=!poseGood?'Face the camera':quality.reason;
        const previous=r.scan.machine;
        r.scan.machine=advanceScanState(previous,now/1000,good);
        const machine=r.scan.machine;
        setState(machine.state);setProgress(machine.elapsed/SCAN_SECONDS);setPaused(machine.paused);
        setHint(machine.paused?specificHint:machine.state==='positioning'?(good?'Hold still':'Center your face in view'):specificHint);

        if(previous.state==='countdown'||machine.state==='countdown'||machine.state==='analyzing'){
          r.scan.captureStart??=(performance.now()/1000);
          r.scan.elapsed=(performance.now()/1000)-r.scan.captureStart;
          const observation=r.scan.index.update(r.scan.elapsed,xy,pose,good,{brightness,qualityReason:specificHint,qualityFlags:flags});
          r.scan.total++;if(observation.valid)r.scan.valid++;
        }
      }

      const canvas=overlay.current;
      if(canvas){
        canvas.width=v.videoWidth;canvas.height=v.videoHeight;
        const draw=canvas.getContext('2d');draw.clearRect(0,0,canvas.width,canvas.height);draw.fillStyle='#6cc3c6';
        landmarks?.filter((_,i)=>i%5===0).forEach(p=>{draw.beginPath();draw.arc(p.x*canvas.width,p.y*canvas.height,1.7,0,Math.PI*2);draw.fill();});
      }
      if(r.enableML&&landmarks&&r.mlCanvas&&r.predictStress&&!r.mlRunning){
        const box=getFaceBoundingBox(landmarks,v.videoWidth,v.videoHeight,0.15);
        if(box&&box.width>20&&box.height>20){
          r.mlRunning=true;
          const mlCtx=r.mlCanvas.getContext('2d',{willReadFrequently:true});
          mlCtx.drawImage(v,box.left,box.top,box.width,box.height,0,0,224,224);
          const rgba=mlCtx.getImageData(0,0,224,224).data;
          const tensor=normalizePixelsToNCHW(rgba);
          r.predictStress(tensor).then(res=>{
            if(runtime.current===r){
              r.mlRunning=false;
              if(Number.isFinite(res.smoothedStressProb)){
                r.mlProbs.push(res.smoothedStressProb);
              }
            }
          }).catch(()=>{if(runtime.current===r)r.mlRunning=false;});
        }
      }
      r.scan.allFrames++;r.scan.inferenceSum+=inferenceMs;r.scan.processingSum+=performance.now()-processingStart;
      if(r.scan.machine.state==='analyzing')complete(!!r.scan.machine.capped);
    }catch(error){
      const message=/wasm|webgl/i.test(String(error))?'Facial analysis could not load. Reload the page in an up-to-date browser, then try again.':'Facial analysis stopped. Reload the page, then try again.';
      stop();setState('failed');setError(message);
    }
  }

  async function start(){
    trackEvent('scan_started');
    stop();setError('');setProgress(0);setPaused(false);setExtended(false);setVideoReady(false);setState('permission');setHint('Starting camera…');
    const r=runtime.current;r.starting=true;const isCurrent=()=>mounted.current&&runtime.current===r;
    try{
      if(!navigator.mediaDevices?.getUserMedia)throw new Error('This browser does not support camera access. Use an up-to-date browser on HTTPS.');
      const streamPromise = awaitResource(navigator.mediaDevices.getUserMedia({audio:false,video:{facingMode:'user',width:{ideal:640},height:{ideal:480}}}),{isCurrent,dispose:stream=>stream.getTracks().forEach(track=>track.stop()),message:'Camera permission is still pending. Allow camera access, then start again.'});
      const modelPromise = loadLandmarker(isCurrent);

      const [stream, model] = await Promise.all([streamPromise, modelPromise]);
      if(!isCurrent())return;
      r.stream=stream;
      r.model=model;
      setState('loading');
      r.stream.getVideoTracks().forEach(track=>track.addEventListener('ended',()=>{if(isCurrent()){stop();setState('failed');setError('The camera disconnected. Reconnect it, then start again.');}}));
      if(video.current){
        video.current.srcObject=r.stream;
        video.current.onloadeddata=()=>{if(runtime.current===r)setVideoReady(true);};
        video.current.onplaying=()=>{if(runtime.current===r)setVideoReady(true);};
        try{await video.current.play();}catch{}
      }
      if(!isCurrent())return;
      r.sampleCanvas=document.createElement('canvas');r.sampleCanvas.width=64;r.sampleCanvas.height=48;
      const enableML=new URLSearchParams(location.search).get('ml')==='1'||localStorage.getItem('pause.ml.enabled')==='1';
      r.enableML=enableML;
      if(enableML){
        r.mlCanvas=document.createElement('canvas');
        r.mlCanvas.width=224;r.mlCanvas.height=224;
        r.mlProbs=[];
        r.mlRunning=false;
        import('./modelRunner.js').then(m=>{
          if(runtime.current===r){
            r.predictStress=m.predictFaceStress;
            m.resetMLScan();
          }
        }).catch(()=>{});
      }
      r.lastVideoTime=-1;r.lastRun=0;r.starting=false;
      r.scan={wallStart:performance.now(),captureStart:null,elapsed:0,index:tolerant?new TolerantScan({baseline}):new QuickIndex({baseline,mode:baseline?'baseline':'generic'}),total:0,valid:0,allFrames:0,inferenceSum:0,processingSum:0,machine:createScanState(performance.now()/1000)};
      r.timer=setTimeout(()=>{if(runtime.current===r&&mounted.current)complete(true)},(tolerant?TOLERANCE_CONFIG.maxDuration:HARD_CAP_SECONDS)*1000);
      setState(tolerant?'countdown':'positioning');setHint('Center your face in view');schedule(r);
    }catch(error){if(!isCurrent())return;stop();setState('failed');setError(cameraError(error));}
  }

  const view={state,error,hint,progress,paused,extended,tolerant,secondsRemaining:Math.max(0,Math.ceil((extended?TOLERANCE_CONFIG.maxDuration:SCAN_SECONDS)*(1-progress))),videoRef:video,overlayRef:overlay,start,cancel,active:['permission','loading','positioning','countdown','analyzing'].includes(state),hardCap:tolerant?TOLERANCE_CONFIG.maxDuration:HARD_CAP_SECONDS,calibrating,videoReady,setVideoReady};
  if(render)return render(view);
  return <section><h1>{calibrating?'Calibrate when calm':'Calm index scan'}</h1><video ref={video} autoPlay playsInline muted/><canvas ref={overlay}/><p aria-live="polite">{error||hint}</p>{!view.active?<button onClick={start}>Start 10-second scan</button>:<button onClick={cancel}>Cancel</button>}</section>;
}
