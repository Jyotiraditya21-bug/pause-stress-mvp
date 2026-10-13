"""Evaluate the deployed 10 s index and fixed research comparators on video clips."""
from __future__ import annotations
import argparse,json,math,time
from pathlib import Path
import cv2,matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from . import deployed_mirror as mirror
from .datasets import load
from .validation_stats import analyze,clean,confounds,nuisance_summary,decision
METHODS=('D0','D1','D2')
NUISANCES=('brightness_0.6','brightness_1.4','320x240','jpeg40','rotation_-10','rotation_10')

def transform(frame,name):
 h,w=frame.shape[:2]
 if name.startswith('brightness_'):return cv2.convertScaleAbs(frame,alpha=float(name.split('_')[1]))
 if name=='320x240':return cv2.resize(cv2.resize(frame,(320,240)),(w,h))
 if name=='jpeg40':
  ok,b=cv2.imencode('.jpg',frame,[cv2.IMWRITE_JPEG_QUALITY,40]);return cv2.imdecode(b,cv2.IMREAD_COLOR) if ok else frame
 m=cv2.getRotationMatrix2D((w/2,h/2),float(name.removeprefix('rotation_')),1.)
 return cv2.warpAffine(frame,m,(w,h),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT_101)

def records_for_video(path,nuisance=None):
 import mediapipe as mp
 from .video import pose
 cap=cv2.VideoCapture(str(path));fps=float(cap.get(cv2.CAP_PROP_FPS) or 0)
 if not cap.isOpened() or fps<=0:cap.release();raise ValueError(f'Cannot decode video: {path}')
 duration=float(cap.get(cv2.CAP_PROP_FRAME_COUNT))/fps;result=[];i=0;last_detection=-float('inf')
 try:mesh=mp.solutions.face_mesh.FaceMesh(max_num_faces=2,refine_landmarks=True,min_detection_confidence=.5,min_tracking_confidence=.5)
 except RuntimeError as exc:
  cap.release();raise RuntimeError('MediaPipe Face Mesh could not initialize. Run on a host with a compatible MediaPipe runtime and usable OpenGL context.') from exc
 with mesh:
  while True:
   ok,frame=cap.read()
   if not ok:break
   t=i/fps;i+=1
   if t-last_detection<.1-1e-9:continue
   last_detection=t
   if nuisance:frame=transform(frame,nuisance)
   found_result=mesh.process(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB));found=found_result.multi_face_landmarks or []
   points=None;angles=None
   h,w=frame.shape[:2]
   if found:
    points=np.array([(v.x*w,v.y*h,v.z*w) for v in found[0].landmark])
    if len(points)>=478:angles=pose(points,frame.shape)
   thumbnail=cv2.resize(frame,(64,48),interpolation=cv2.INTER_LINEAR)
   result.append(dict(time=t,frame=thumbnail,size=(h,w),points=points,face_count=len(found),pose=angles,fps=fps,duration=duration))
 cap.release();return result

def frame_quality(rec,previous):
 pts=rec['points']
 if pts is None:return dict(good=False,reason='Position your face inside the camera view.'),None,float('nan')
 h,w=rec['size'];norm=pts[:,:2]/[w,h]
 rgb=cv2.cvtColor(rec['frame'],cv2.COLOR_BGR2RGB);rgba=np.dstack([rgb,np.full((48,64),255,np.uint8)])
 points=[dict(x=float(x),y=float(y)) for x,y in norm]
 brightness=mirror.face_brightness(rgba.reshape(-1,4),64,48,points)
 q=mirror.assess_quick_frame(points,rec['face_count'],brightness,previous)
 return q,q.get('center'),brightness

def scan(records,baseline=None):
 records=sample_records(records)
 idx=mirror.QuickIndex(baseline);previous=None;started=time.perf_counter()
 for rec in records:
  q,center,brightness=frame_quality(rec,previous);previous=center;p=rec['points'];angles=rec['pose']
  idx.update(rec['time'],[] if p is None else p[:,:2].tolist(),None if angles is None else [float(x) for x in angles],q['good'],dict(brightness=brightness,qualityReason=q['reason']))
 out=idx.finish();out['processed_ms_per_frame']=(time.perf_counter()-started)*1000/max(len(records),1);out['_feature_rows']=idx.measurements.feature_rows
 return out

def baseline_rows(records):
 records=sample_records([r for r in records if r['time']<25])
 rows=[];previous=None
 for rec in records:
  if rec['time']>=25:break
  q,center,_=frame_quality(rec,previous);previous=center;p=rec['points'];angles=rec['pose']
  if p is None or not q['good']:continue
  if angles is not None and (abs(angles[0])>38 or abs(angles[1])>30):continue
  try:
   row=mirror.geometry(p)
   if row['mar']<=.32:rows.append(row)
  except (ValueError,IndexError):continue
 return rows

def sample_records(records):
 """Mirror the browser's minimum 100 ms spacing between detections."""
 chosen=[];last=-float('inf')
 for rec in records:
  if rec['time']-last>=.1-1e-9:chosen.append(rec);last=rec['time']
 return chosen

def score_clip(records,rest_rows):
 d0=scan(records);d1=scan(records,rest_rows) if len(rest_rows)>=5 else None;rows=d0['_feature_rows']
 d2=float(np.mean([np.var([r[k] for r in rows]) for k in mirror.BASELINE_KEYS])) if len(rows)>=2 else None
 return dict(indices={'D0':d0['average'],'D1':None if d1 is None else d1['average'],'D2':d2},accepted=d0['average'] is not None,quality=d0['quality'],coverage_percent=d0['coveragePercent'],ms_frame=d0['processed_ms_per_frame'])

def clips_for_session(session,cache):
 path=session['video_path'];key=str(Path(path).resolve())
 if key not in cache:cache[key]=records_for_video(path)
 data=cache[key];duration=data[0]['duration'] if data else 0.
 task=str(session.get('condition') or session.get('task') or ('T1' if int(session['label'])==0 else 'T2'))
 if task not in ('T1','T2','T3'):task='T1' if int(session['label'])==0 else 'T2'
 label=0 if task=='T1' else 1
 start=float(session.get('start_seconds') or 0);end=min(duration,float(session.get('end_seconds') or duration))
 return [(float(left),task,label,[dict(r,time=r['time']-left) for r in data if left<=r['time']<left+10]) for left in np.arange(start,end-10+1e-9,10.)]

def evaluate(sessions,output_dir):
 cache={};clips=[];source={};rest_paths=[];uses={}
 for s in sessions:
  rest_path=s.get('baseline_video_path')
  if not rest_path and (s.get('condition')=='T1' or int(s['label'])==0):rest_path=s['video_path']
  if not rest_path:
   candidates=[r for r in sessions if str(r['subject_id'])==str(s['subject_id']) and r.get('dataset')==s.get('dataset') and (r.get('condition')=='T1' or int(r.get('label',1))==0)]
   if len(candidates)==1:rest_path=candidates[0]['video_path']
  rest_paths.append(rest_path)
  for item in (s['video_path'],rest_path):
   if item:
    key=str(Path(item).resolve());uses[key]=uses.get(key,0)+1
 for session_index,s in enumerate(sessions):
  rest_path=rest_paths[session_index]
  rest=[]
  if rest_path:
   rk=str(Path(rest_path).resolve())
   if rk not in cache:cache[rk]=records_for_video(rest_path)
   rest=baseline_rows(cache[rk])
  for start,task,label,rows in clips_for_session(s,cache):
   scored=score_clip(rows,rest);clip_id=f"{Path(s['video_path']).stem}@{start:g}"
   raw_features={k:float(np.mean([r[k] for r in rest])) for k in mirror.BASELINE_KEYS} if rest else None
   indices=dict(scored['indices'])
   # The first 25 s define D1's baseline and cannot also be its evaluation data.
   if task=='T1' and start<25:indices['D1']=None
   clips.append(dict(subject_id=f"{s.get('dataset','unknown')}:{s['subject_id']}",session_id=str(s.get('session_id',Path(s['video_path']).stem)),clip_id=clip_id,dataset=s.get('dataset','unknown'),task=task,label=label,indices=indices,raw_features=raw_features,accepted=scored['accepted'],quality=scored['quality'],coverage_percent=scored['coverage_percent'],ms_frame=scored['ms_frame'],nuisances={}))
   source[clip_id]=(s['video_path'],start,rest)
  for item in (str(Path(s['video_path']).resolve()),str(Path(rest_path).resolve()) if rest_path else None):
   if item:
    uses[item]-=1
    if uses[item]<=0:cache.pop(item,None)
 for path in sorted({source[c['clip_id']][0] for c in clips if c['accepted']}):
  group=[c for c in clips if c['accepted'] and source[c['clip_id']][0]==path]
  for name in NUISANCES:
   altered_all=records_for_video(path,name)
   for clip in group:
    _,start,rest=source[clip['clip_id']]
    altered=[dict(r,time=r['time']-start) for r in altered_all if start<=r['time']<start+10]
    clip['nuisances'][name]=score_clip(altered,rest)['indices'] if altered else {m:None for m in METHODS}
 records=[]
 for c in clips:
  vals=dict(c['indices']);vals['D0']=None if vals['D0'] is None else 10-float(vals['D0']);vals['D1']=None if vals['D1'] is None else 10-float(vals['D1'])
  records.append(dict(subject_id=c['subject_id'],label=c['label'],task=c['task'],clip_id=c['clip_id'],excluded=not c['accepted'] or c['coverage_percent']<35,coverage_percent=c['coverage_percent'],methods=vals))
 stats=analyze(records);shape=confounds(clips);nuis=nuisance_summary(clips);gate=decision(stats['task_splits'],nuis,'D0')
 result=dict(protocol=dict(trained=False,clip_seconds=10,overlap_seconds=0,first_second_excluded=True,labels='T1 rest=0, T2/T3 task=1; labels are not clinical stress',coverage_exclusion_percent=35,auc_orientation='D0/D1 inverted for AUC; displayed index remains 0 high deviation, 10 relaxed',pose_source='OpenCV solvePnP estimate; the browser uses MediaPipe facial transformation matrices, so pose values are approximate and not part of feature-level parity equality.',nuisance_transforms=list(NUISANCES),seed=42,bootstrap_draws=1000,permutations=1000),records=clips,task_splits=stats['task_splits'],paired_auc_differences=stats['paired_auc_differences'],face_shape_confounds=shape,nuisance_sensitivity=nuis,decision=gate)
 out=Path(output_dir);out.mkdir(parents=True,exist_ok=True);(out/'metrics.json').write_text(json.dumps(clean(result),indent=2));write_report(result,out);return result

def write_report(result,out):
 lines=['# Deployed 10-second algorithm evaluation','','Non-overlapping 10-second clips are classified using T1 rest=0 and T2 speech/T3 arithmetic=1. These are task-based labels, not clinically measured stress. D0 is the deployed generic-reference formula. Offline personalized methods do not validate D0. Nothing is fitted on test data.','D0 uses the three deployed generic geometry features (brow furrow, lip press and lip corner) with the fixed canonical reference. D1 uses those three plus jaw geometry with the first 25 seconds of subject rest as baseline; baseline-overlapping T1 clips are missing for D1. D2 is the mean variance of the four features across one-second windows.','D0/D1 scores are inverted for ROC AUC so larger values indicate the task label. Invalid scans are excluded; unavailable method scores remain missing.','Pose gates use the same numeric limits, with OpenCV solvePnP estimates in this Python evaluator; the browser obtains pose from MediaPipe transformation matrices. Results near pose cutoffs may therefore differ.','']
 for split,entry in result['task_splits'].items():
  lines += [f"## {split}",'', '| Method | AUC [95% CI] | d_z [95% CI] | Wilcoxon p [95% CI] | Permutation null AUC [95%], p | accepted / total | mean coverage |','|---|---:|---:|---:|---:|---:|---:|']
  for m,v in entry['methods'].items():
   auc=v.get('roc_auc');ci=v.get('subject_bootstrap_95ci',{}).get('roc_auc');af='N/A' if auc is None else f"{auc:.3f} [{ci[0]:.3f}, {ci[1]:.3f}]" if ci else f'{auc:.3f} [N/A]'
   p=v.get('within_subject',{});ci_map=v.get('subject_bootstrap_95ci',{});dz=p.get('cohen_dz');dzci=ci_map.get('cohen_dz');wp=p.get('wilcoxon_p');wpci=ci_map.get('wilcoxon_p')
   dzs='N/A' if dz is None else f"{dz:.3f} [{dzci[0]:.3f}, {dzci[1]:.3f}]" if dzci else f'{dz:.3f} [N/A]'
   wps='N/A' if wp is None else f"{wp:.4f} [{wpci[0]:.4f}, {wpci[1]:.4f}]" if wpci else f'{wp:.4f} [N/A]'
   null=entry['permutations'].get(m,{});nci=null.get('null_auc_95_interval');nv=null.get('null_auc_mean')
   ns='N/A' if nv is None else f"{nv:.3f} [{nci[0]:.3f}, {nci[1]:.3f}], p={null.get('p_value')}"
   c=v.get('coverage',{})
   lines.append(f"| {m} | {af} | {dzs} | {wps} | {ns} | {c.get('accepted_clips')} / {c.get('total_clips')} | {c.get('mean_slot_coverage_percent')}% |")
  lines.append('')
 lines+=['## Paired AUC differences (Holm corrected)','','| Split / method pair | Difference [95% CI] | Raw p | Holm p |','|---|---:|---:|---:|']
 for k,v in result['paired_auc_differences'].items():
  diff=v.get('auc_difference');ci=v.get('subject_bootstrap_95ci');formatted='N/A' if diff is None else f"{diff:.3f} [{ci[0]:.3f}, {ci[1]:.3f}]" if ci else f'{diff:.3f} [N/A]'
  lines.append(f"| {k} | {formatted} | {v.get('raw_p_value')} | {v.get('holm_adjusted_p_value')} |")
 lines+=['## Face-shape confound (T1 only)','','ICC(1) and Spearman associations with subject mean normalized geometry.','',json.dumps(result['face_shape_confounds'],indent=2),'','## Nuisance sensitivity','',json.dumps(result['nuisance_sensitivity'],indent=2),'','## Predeclared decision','',f"**{result['decision']['status']}** for D0."]
 for k,v in result['decision']['criteria'].items():lines.append(f"- {'PASS' if v['pass_'] else 'FAIL'} — {k}: {v.get('value')} ({v['rule']})")
 (out/'report.md').write_text('\n'.join(lines)+'\n')
 rows=result['face_shape_confounds']['subject_means'];fig,ax=plt.subplots(figsize=(7,5))
 for k in mirror.KEYS:
  if rows:ax.scatter([r['geometry'][k] for r in rows],[r['D0'] for r in rows],label=k)
 ax.set(xlabel='Mean normalized geometry',ylabel='Mean D0 index',title='Rest face-shape confounds');ax.legend();fig.tight_layout();fig.savefig(out/'face_shape_confound.png',dpi=150);plt.close(fig)

def main():
 p=argparse.ArgumentParser();p.add_argument('--root');p.add_argument('--manifest');p.add_argument('--output',default='stress_math/results/deployed')
 a=p.parse_args();sessions=load(a.root,a.manifest)
 if not sessions:raise SystemExit('No labeled video sessions found.')
 evaluate(sessions,Path(a.output))
if __name__=='__main__':main()
