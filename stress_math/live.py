"""Explicitly consented local recording of a four-minute own-session protocol."""
import csv,time,uuid
from pathlib import Path
import cv2
from .core import Index
from .video import features
import numpy as np

def record(root):
    import mediapipe as mp
    from .video import pose,green_roi
    root=Path(root); root.mkdir(parents=True,exist_ok=True)
    print('This records identifiable webcam video locally. No uploads. Baseline 120s, then 120s timed arithmetic. Press q to cancel. Experimental index, not clinical stress.')
    if input('Type RECORD to consent: ').strip()!='RECORD': return None
    subject='own-'+uuid.uuid4().hex[:8]; path=root/(subject+'.avi')
    cap=cv2.VideoCapture(0)
    if not cap.isOpened(): cap.release(); raise RuntimeError('Camera unavailable; grant camera permission to your terminal/Python.')
    ok,first=cap.read()
    if not ok: cap.release(); raise RuntimeError('Cannot read camera')
    h,w=first.shape[:2]; fps=cap.get(cv2.CAP_PROP_FPS)
    if fps<1 or fps>120: fps=30
    writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'MJPG'),fps,(w,h))
    if not writer.isOpened(): cap.release(); raise RuntimeError('Cannot create recording')
    timestamps=[]; points=[]; poses=[]; green=[]; baseline=[]; model=None; score=np.nan
    start=time.monotonic(); last_update=-1; last_scored=24.999; completed=False
    try:
        with mp.solutions.face_mesh.FaceMesh(refine_landmarks=True,max_num_faces=1) as mesh:
            while True:
                ok,frame=cap.read()
                if not ok: break
                t=time.monotonic()-start
                if t>=240: completed=True; break
                writer.write(frame); timestamps.append(t)
                p=np.full((478,3),np.nan); a=np.full(3,np.nan); g=np.nan
                detected=mesh.process(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB))
                if detected.multi_face_landmarks:
                    p=np.array([(l.x*w,l.y*h,l.z*w) for l in detected.multi_face_landmarks[0].landmark]); a=pose(p,frame.shape)
                    if a is None: a=np.full(3,np.nan)
                    if np.isfinite(a).all() and max(abs(a[0]),abs(a[1]))<=35: g=green_roi(frame,p)
                    else: p[:]=np.nan
                points.append(p); poses.append(a); green.append(g)
                if t-last_update>=1:
                    cut=max(0,int(np.searchsorted(timestamps,t-30)))
                    data={'times':np.array(timestamps[cut:]),'landmarks':np.array(points[cut:]),'pose':np.array(poses[cut:]),'green':np.array(green[cut:])}
                    rows=features(data)
                    if model is None and t>=25:
                        baseline=[r for r in rows if r['time']<25 and not r.get('gated',False)]; model=Index(baseline)
                    if model:
                        for row in rows:
                            if row['time']>last_scored:
                                score=model.score(row); last_scored=row['time']
                    last_update=t
                prompt='RELAX: breathe normally' if t<120 else f'ARITHMETIC: 1000 minus 7 repeatedly ({max(0,1000-7*int((t-120)//3))})'
                cv2.putText(frame,prompt,(10,30),cv2.FONT_HERSHEY_SIMPLEX,.55,(0,255,255),1)
                cv2.putText(frame,f'{t:.0f}/240 s | experimental index: {score:.1f}',(10,60),cv2.FONT_HERSHEY_SIMPLEX,.55,(0,255,255),1)
                cv2.imshow('Own session - q cancels',frame)
                if cv2.waitKey(1)&255==ord('q'): break
    finally: cap.release(); writer.release(); cv2.destroyAllWindows()
    if not completed:
        print(f'Cancelled; partial recording retained privately at {path}. No evaluation labels created.'); return None
    # OpenCV containers assume constant FPS. Sidecar preserves actual capture timestamps.
    np.save(path.with_suffix('.timestamps.npy'),np.array(timestamps))
    manifest=root/'sessions.csv'; exists=manifest.exists()
    with manifest.open('a',newline='') as f:
        fields=['video_path','subject_id','label','baseline_video_path','dataset','start_seconds','end_seconds','stressor_onset','condition']
        writer=csv.DictWriter(f,fieldnames=fields)
        if not exists: writer.writeheader()
        for label,start,end in [(0,25,120),(1,120,240)]:
            writer.writerow(dict(video_path=path.name,subject_id=subject,label=label,baseline_video_path=path.name,dataset='Own',start_seconds=start,end_seconds=end,stressor_onset=120,condition='normal'))
    return str(manifest)
