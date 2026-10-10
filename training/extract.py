"""Resumable local-video feature extraction; labels come from a reviewed manifest."""
import argparse, csv, hashlib, json, math
from pathlib import Path
import cv2
import mediapipe as mp
import numpy as np

def quality(points, count, brightness, previous):
    if count != 1 or not points:
        return False, None, 0
    xs=[p.x for p in points]; ys=[p.y for p in points]
    w=max(xs)-min(xs); h=max(ys)-min(ys)
    center=((max(xs)+min(xs))/2,(max(ys)+min(ys))/2)
    movement=math.dist(center, previous) if previous else 0
    good=(45 <= brightness <= 225 and .18 <= w <= .8 and .22 <= h <= .9
          and abs(center[0]-.5)<=.2 and abs(center[1]-.5)<=.22 and movement<=.035)
    return good, center, movement

def extract(path, model_path):
    cap=cv2.VideoCapture(str(path))
    fps=cap.get(cv2.CAP_PROP_FPS)
    if not cap.isOpened() or not math.isfinite(fps) or fps<=0:
        cap.release(); raise ValueError('Unreadable video or invalid FPS')
    options=mp.tasks.vision.FaceLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(model_path)),
        running_mode=mp.tasks.vision.RunningMode.VIDEO,num_faces=2,output_face_blendshapes=True)
    windows={}; previous=None; index=0; next_sample=0
    try:
        with mp.tasks.vision.FaceLandmarker.create_from_options(options) as model:
            while True:
                success, frame=cap.read()
                if not success: break
                seconds=index/fps; index+=1
                if seconds+1e-8<next_sample: continue
                next_sample=seconds+.1
                rgb=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)
                result=model.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB,data=rgb),int(seconds*1000))
                small=cv2.resize(rgb,(64,48),interpolation=cv2.INTER_LINEAR)
                points=result.face_landmarks[0] if result.face_landmarks else None
                good,previous,movement=quality(points,len(result.face_landmarks),float(small.mean()),previous)
                window=windows.setdefault(int(seconds//30),{'total':0,'samples':[]})
                window['total']+=1
                if good:
                    shapes={c.category_name:c.score for c in result.face_blendshapes[0]}
                    window['samples'].append([(shapes.get('eyeBlinkLeft',0)+shapes.get('eyeBlinkRight',0))/2,
                        (shapes.get('browDownLeft',0)+shapes.get('browDownRight',0))/2,movement])
    finally: cap.release()
    duration=index/fps
    output=[]
    for number,w in windows.items():
        if duration < (number+1)*30: continue # discard incomplete windows
        ratio=len(w['samples'])/max(w['total'],1)
        good=ratio>=.75 and len(w['samples'])>=30
        output.append({'window':number,'usable_fraction':ratio,'accepted':good,
                       'features':np.mean(w['samples'],axis=0).tolist() if good else None})
    return output

def main():
    p=argparse.ArgumentParser(); p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--model',type=Path,required=True);p.add_argument('--checkpoint',type=Path,required=True)
    p.add_argument('--csv',type=Path,required=True);a=p.parse_args()
    a.checkpoint.mkdir(parents=True,exist_ok=True)
    with a.manifest.open() as handle: rows=list(csv.DictReader(handle))
    if not rows or not {'participant_id','video_path','label'}.issubset(rows[0]):
        raise ValueError('Manifest requires participant_id,video_path,label')
    if any(r['label'] not in ['0','1'] or not r['participant_id'] for r in rows):
        raise ValueError('Review all participant IDs and binary labels first')
    seen=set(); all_rows=[]; rejected=0
    for row in rows:
        identity=json.dumps(row,sort_keys=True)
        if identity in seen: raise ValueError('Duplicate manifest row')
        seen.add(identity)
        key=hashlib.sha256((identity+hashlib.sha256(a.model.read_bytes()).hexdigest()).encode()).hexdigest()
        checkpoint=a.checkpoint/(key+'.json')
        if checkpoint.exists(): windows=json.loads(checkpoint.read_text())
        else:
            windows=extract(Path(row['video_path']),a.model)
            temp=checkpoint.with_suffix('.tmp');temp.write_text(json.dumps(windows));temp.replace(checkpoint)
        for w in windows:
            if not w['accepted']: rejected+=1;continue
            all_rows.append([row['participant_id'],row['label'],*w['features']])
        a.csv.parent.mkdir(parents=True,exist_ok=True)
        with a.csv.open('w',newline='') as handle:
            writer=csv.writer(handle);writer.writerow(['participant_id','label','meanBlinkCoefficient','meanBrowCoefficient','meanMovement']);writer.writerows(all_rows)
        print('Completed manifest videos:',len(seen),'Accepted windows:',len(all_rows),'Rejected:',rejected)
    (a.csv.parent/'extraction_summary.json').write_text(json.dumps({'accepted_windows':len(all_rows),'rejected_windows':rejected,'sampling_hz_target':10,'window_seconds':30,'model_sha256':hashlib.sha256(a.model.read_bytes()).hexdigest(),'limitations':'Python/JS MediaPipe implementations and image resampling can differ; validate parity before deployment.'},indent=2))
if __name__=='__main__': main()
