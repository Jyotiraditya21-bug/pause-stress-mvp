import hashlib, json, time
from collections import deque
from pathlib import Path
import cv2
import numpy as np
from .core import geometry, normalize, pulse, INDICES

VERSION='math-1.3-raw-count'
SOURCE_HASH=hashlib.sha256(Path(__file__).read_bytes()+Path(__file__).with_name('core.py').read_bytes()).hexdigest()
def pose(p,shape):
    h,w=shape[:2]
    model=np.array([(0,0,0),(0,-330,-65),(-225,170,-135),(225,170,-135),(-150,-150,-125),(150,-150,-125)],float)
    image=p[[1,152,33,263,61,291],:2]
    camera=np.array([[w,0,w/2],[0,w,h/2],[0,0,1]],float)
    ok,r,t=cv2.solvePnP(model,image,camera,np.zeros(4),flags=cv2.SOLVEPNP_ITERATIVE)
    if not ok: return None
    rotation=cv2.Rodrigues(r)[0]
    angles=np.array(cv2.RQDecomp3x3(rotation)[0])
    angles=(angles+180)%360-180
    # solvePnP uses a face convention rotated 180 degrees around x.
    angles[0]=((angles[0]+90)%180)-90
    return angles

def green_roi(frame,p):
    masks=[]
    for ids in ([10,109,108,9,337,338],[50,101,205,187],[280,330,425,411]):
        mask=np.zeros(frame.shape[:2],np.uint8)
        cv2.fillConvexPoly(mask,cv2.convexHull(p[ids,:2].astype(np.int32)),255)
        if mask.any(): masks.append(float(cv2.mean(frame[:,:,1],mask)[0]))
    return float(np.mean(masks)) if masks else np.nan

def extract(path,cache):
    import mediapipe as mp
    path=Path(path); stat=path.stat()
    key=hashlib.sha256(f'{path.resolve()}:{stat.st_size}:{stat.st_mtime_ns}:{VERSION}:{SOURCE_HASH}'.encode()).hexdigest()
    cache=Path(cache); cache.mkdir(parents=True,exist_ok=True); target=cache/(key+'.npz')
    if target.exists():
        with np.load(target,allow_pickle=False) as data: return {k:data[k] for k in data.files}
    cap=cv2.VideoCapture(str(path)); fps=cap.get(cv2.CAP_PROP_FPS)
    if not cap.isOpened() or fps<=0: cap.release(); raise ValueError(f'Cannot decode video: {path}')
    times=[]; landmarks=[]; raw_landmarks=[]; angles=[]; greens=[]; brightness=[]; face_counts=[]; start=time.perf_counter(); i=0
    with mp.solutions.face_mesh.FaceMesh(max_num_faces=2,refine_landmarks=True,min_detection_confidence=.5,min_tracking_confidence=.5) as mesh:
        while True:
            ok,frame=cap.read()
            if not ok: break
            times.append(i/fps); i+=1
            result=mesh.process(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB))
            p=np.full((478,3),np.nan); raw=p.copy(); a=np.full(3,np.nan); g=np.nan
            face_counts.append(len(result.multi_face_landmarks or []))
            if result.multi_face_landmarks:
                h,w=frame.shape[:2]
                p=np.array([(v.x*w,v.y*h,v.z*w) for v in result.multi_face_landmarks[0].landmark])
                raw=p.copy()
                a=pose(p,frame.shape)
                if a is None: a=np.full(3,np.nan)
                if len(result.multi_face_landmarks)==1 and np.all(np.isfinite(a)) and max(abs(a[0]),abs(a[1]))<=35: g=green_roi(frame,p)
                else: p[:]=np.nan
            landmarks.append(p); raw_landmarks.append(raw); angles.append(a); greens.append(g); brightness.append(frame.mean())
    cap.release()
    data=dict(times=np.array(times),landmarks=np.array(landmarks),raw_landmarks=np.array(raw_landmarks),pose=np.array(angles),green=np.array(greens),brightness=np.array(brightness),face_counts=np.array(face_counts),fps=np.array(fps),ms_frame=np.array((time.perf_counter()-start)*1000/max(i,1)))
    np.savez_compressed(target,**data)
    return data

def features(data):
    rows=[]; window=deque(); blink_events=deque(); green=deque(); closed=None; previous=None
    counts=data.get('face_counts',np.ones(len(data['times']),dtype=int))
    for t,p,a,g,face_count in zip(data['times'],data['landmarks'],data['pose'],data['green'],counts):
        row={'time':float(t)}
        if face_count!=1 or not np.isfinite(p).all(): rows.append(row); previous=None; closed=None; continue
        f=geometry(p); q=normalize(p)[list(INDICES)]
        if f['ear']<.2:
            if closed is None: closed=t
        elif closed is not None:
            if .05<=t-closed<=.8: blink_events.append((t,float(t-closed)))
            closed=None
        while blink_events and blink_events[0][0]<t-20: blink_events.popleft()
        velocity=0 if previous is None else np.linalg.norm(q-previous[1],axis=1).mean()/max(t-previous[0],1e-6)
        previous=(t,q); window.append((t,a,velocity)); green.append((t,g))
        while window and window[0][0]<t-5: window.popleft()
        while green and green[0][0]<t-25: green.popleft()
        f['blink_rate']=len(blink_events)*60/min(20,max(t,.1))
        f['blink_duration']=float(np.mean([b[1] for b in blink_events])) if blink_events else np.nan
        f['jitter']=float(np.std([v[1] for v in window],axis=0).mean()/180+np.std([v[2] for v in window]))
        f['gated']=bool(f['mar']>.35 or f['lip_corner']<-.12)
        # Reject discontinuous/noisy ROI windows; do not bridge lost-face gaps.
        if len(green)>1 and np.all(np.isfinite([v[1] for v in green])) and max(np.diff([v[0] for v in green]))<.15:
            f.update(pulse([v[0] for v in green],[v[1] for v in green]))
        row.update(f); rows.append(row)
    return rows
