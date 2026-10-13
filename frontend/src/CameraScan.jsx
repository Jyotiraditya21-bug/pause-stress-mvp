import React, {useEffect,useRef,useState} from 'react';
import {assessQuickFrame,faceBrightness} from './scanMetrics.js';
import {QuickIndex,geometry,headPose,SCAN_SECONDS} from './liveIndex.js';
import {awaitResource} from './resourceWait.js';
import {advanceScanState,createScanState,HARD_CAP_SECONDS} from './scanState.js';
import {trackEvent} from './monitoring.js';

function cameraError(error) {
  if(!globalThis.isSecureContext)return 'Camera access needs a secure connection. Open the HTTPS site or use localhost.';
  if(error?.name==='NotAllowedError')return 'Camera access was blocked. Allow camera access in your browser settings, then start again.';
  if(error?.name==='NotFoundError')return 'No camera was found. Connect a camera, then start again.';
  if(error?.name==='NotReadableError')return 'The camera is being used by another app. Close that app, then start again.';
  return error?.message||'Facial analysis could not start. Reload the page, then try again.';
}

export default function CameraScan({onComplete,baseline=null,calibrating=false,render}) {
  const [state,setState]=useState('idle');
  const [error,setError]=useState(''),[hint,setHint]=useState('Fit your face in the circle');
  const [progress,setProgress]=useState(0),[paused,setPaused]=useState(false);
  const video=useRef(null),overlay=useRef(null),runtime=useRef({}),mounted=useRef(true);

  function cancelLoop(r){
    if(r.videoCallback&&video.current?.cancelVideoFrameCallback)video.current.cancelVideoFrameCallback(r.videoCallback);
    cancelAnimationFrame(r.frame);
  }
  function stop() {
    const r=runtime.current;cancelLoop(r);clearTimeout(r.timer);
    r.stream?.getTracks().forEach(track=>track.stop());
    try{r.model?.close();}catch{}
    if(video.current)video.current.srcObject=null;
    runtime.current={};
  }
  function cancel(){stop();setState('idle');setProgress(0);setPaused(false);setHint('Fit your face in the circle');}

  useEffect(()=>{
    mounted.current=true;
    const hide=()=>{if(document.hidden&&(runtime.current.starting||runtime.current.stream)){cancel();setError('The camera stopped when the page was hidden. Return to this page and start again.');}};
    document.addEventListener('visibilitychange',hide);
    return()=>{mounted.current=false;document.removeEventListener('visibilitychange',hide);stop();};
  },[]);

  function complete(capped=false){
    const r=runtime.current;
    if(!r.scan||r.finishing)return;
    r.finishing=true;setState('analyzing');cancelLoop(r);
    const outcome=r.scan.index.finish();
    const wall=(performance.now()-r.scan.wallStart)/1000;
    const summary={id:crypto.randomUUID(),created_at:new Date().toISOString(),source:'quick-canonical-index-v3',...outcome,
      status:outcome.status,mode:calibrating?'calibration':outcome.mode,frames:r.scan.total,validFrames:r.scan.valid,
      durationSeconds:wall,capped,performance:{processedFrames:r.scan.allFrames,fps:r.scan.allFrames/Math.max(wall,.1),inferenceMs:r.scan.allFrames?r.scan.inferenceSum/r.scan.allFrames:null,processingMs:r.scan.allFrames?r.scan.processingSum/r.scan.allFrames:null}};
    if(capped&&summary.status==='ok'){
      summary.status='limited';summary.quality='limited';summary.warnings=[...summary.warnings,'Keep your face in view so the scan finishes sooner.'];
    }
    trackEvent(summary.status==='failed'?'scan_failed':'scan_result',{status:summary.status,reason:summary.status==='failed'?'acquisition_failed':summary.status==='limited'?'limited_confidence':'accepted'});
    setTimeout(()=>{
      if(!mounted.current)return;
      stop();setState(summary.status==='failed'?'failed':'result');onComplete(summary);
    },250);
  }

  function schedule(r){
    const callback=()=>{tick();if(runtime.current===r&&r.model)schedule(r);};
    if(video.current?.requestVideoFrameCallback)r.videoCallback=video.current.requestVideoFrameCallback(callback);
    else r.frame=requestAnimationFrame(callback);
  }

  function tick(){
    const r=runtime.current,v=video.current;
    if(!r.model||!v||!mounted.current||r.finishing)return;
    const now=performance.now();
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
      const quality=assessQuickFrame(landmarks,result.faceLandmarks.length,brightness,r.previous);
      r.previous=quality.center;
      const pose=headPose(result.facialTransformationMatrixes?.[0]);
      const poseGood=!pose||(Math.abs(pose[0])<=38&&Math.abs(pose[1])<=30);
      let mouthOpen=false,xy=[];
      if(landmarks){xy=landmarks.map(p=>[p.x*v.videoWidth,p.y*v.videoHeight]);try{mouthOpen=geometry(xy).mar>.32;}catch{}}
      const flags={...quality.qualityFlags,mouthOpen,pose:!poseGood};
      const good=quality.good&&poseGood&&!mouthOpen;
      const specificHint=mouthOpen?'Close your mouth':!poseGood?'Face the camera':quality.reason;
      const previous=r.scan.machine;
      r.scan.machine=advanceScanState(previous,now/1000,good);
      const machine=r.scan.machine;
      setState(machine.state);setProgress(machine.goodElapsed/SCAN_SECONDS);setPaused(machine.paused);
      setHint(machine.paused?specificHint:machine.state==='positioning'?(good?'Hold still':'Fit your face in the circle'):specificHint);

      if(previous.state==='countdown'||machine.state==='countdown'||machine.state==='analyzing'){
        const observation=r.scan.index.update(Math.min(machine.goodElapsed,SCAN_SECONDS-.000001),xy,pose,good,{brightness,qualityReason:specificHint,qualityFlags:flags});
        r.scan.total++;if(observation.valid)r.scan.valid++;
      }

      const canvas=overlay.current;
      if(canvas){
        canvas.width=v.videoWidth;canvas.height=v.videoHeight;
        const draw=canvas.getContext('2d');draw.clearRect(0,0,canvas.width,canvas.height);draw.fillStyle=good?'#6cc3c6':'#e4b05a';
        landmarks?.filter((_,i)=>i%5===0).forEach(p=>{draw.beginPath();draw.arc(p.x*canvas.width,p.y*canvas.height,1.7,0,Math.PI*2);draw.fill();});
      }
      r.scan.allFrames++;r.scan.inferenceSum+=inferenceMs;r.scan.processingSum+=performance.now()-processingStart;
      if(machine.state==='analyzing')complete(!!machine.capped);
    }catch(error){
      const message=/wasm|webgl/i.test(String(error))?'Facial analysis could not load. Reload the page in an up-to-date browser, then try again.':'Facial analysis stopped. Reload the page, then try again.';
      stop();setState('failed');setError(message);
    }
  }

  async function start(){
    trackEvent('scan_started');
    stop();setError('');setProgress(0);setPaused(false);setState('permission');setHint('Starting camera…');
    const r=runtime.current;r.starting=true;const isCurrent=()=>mounted.current&&runtime.current===r;
    try{
      if(!navigator.mediaDevices?.getUserMedia)throw new Error('This browser does not support camera access. Use an up-to-date browser on HTTPS.');
      r.stream=await awaitResource(navigator.mediaDevices.getUserMedia({audio:false,video:{facingMode:'user',width:{ideal:640},height:{ideal:480}}}),{isCurrent,dispose:stream=>stream.getTracks().forEach(track=>track.stop()),message:'Camera permission is still pending. Allow camera access, then start again.'});
      if(!isCurrent())return;
      setState('loading');
      r.stream.getVideoTracks().forEach(track=>track.addEventListener('ended',()=>{if(isCurrent()){stop();setState('failed');setError('The camera disconnected. Reconnect it, then start again.');}}));
      video.current.srcObject=r.stream;await video.current.play();
      const {FaceLandmarker,FilesetResolver}=await import('@mediapipe/tasks-vision');
      const files=await awaitResource(FilesetResolver.forVisionTasks(`${import.meta.env.BASE_URL}mediapipe/wasm`),{isCurrent,message:'Facial analysis files did not load. Check your connection, then start again.'});
      r.model=await awaitResource(FaceLandmarker.createFromOptions(files,{baseOptions:{modelAssetPath:`${import.meta.env.BASE_URL}mediapipe/face_landmarker.task`,delegate:'CPU'},runningMode:'VIDEO',numFaces:2,outputFacialTransformationMatrixes:true}),{isCurrent,dispose:model=>model.close(),message:'Facial analysis did not start. Reload the page, then try again.'});
      if(!isCurrent()){r.model?.close();return;}
      r.sampleCanvas=document.createElement('canvas');r.sampleCanvas.width=64;r.sampleCanvas.height=48;
      r.lastVideoTime=-1;r.lastRun=0;r.starting=false;
      r.scan={wallStart:performance.now(),index:new QuickIndex({baseline,mode:baseline?'baseline':'generic'}),total:0,valid:0,allFrames:0,inferenceSum:0,processingSum:0,machine:createScanState(performance.now()/1000)};
      r.timer=setTimeout(()=>{if(runtime.current===r&&mounted.current)complete(true)},HARD_CAP_SECONDS*1000);
      setState('positioning');setHint('Fit your face in the circle');schedule(r);
    }catch(error){if(!isCurrent())return;stop();setState('failed');setError(cameraError(error));}
  }

  const view={state,error,hint,progress,paused,secondsRemaining:Math.max(0,Math.ceil(SCAN_SECONDS-progress*SCAN_SECONDS)),videoRef:video,overlayRef:overlay,start,cancel,active:['permission','loading','positioning','countdown','analyzing'].includes(state),hardCap:HARD_CAP_SECONDS,calibrating};
  if(render)return render(view);
  return <section><h1>{calibrating?'Calibrate when calm':'Calm index scan'}</h1><video ref={video} autoPlay playsInline muted/><canvas ref={overlay}/><p aria-live="polite">{error||hint}</p>{!view.active?<button onClick={start}>Start 10-second scan</button>:<button onClick={cancel}>Cancel</button>}</section>;
}
