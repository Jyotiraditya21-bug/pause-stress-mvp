"""OLD four-feature gates vs fixed tolerant policies on matched source segments.

No training or automatic parameter selection. Missing evidence fails adoption.
"""
from __future__ import annotations
import argparse,csv,json,math,time
from collections import defaultdict
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from . import deployed_mirror as old
from .tolerant_scan import TolerantScan,CONFIG as C,adaptive_state,finite
from .metrics import auc_value,paired_stats
from .validation_stats import clean

METHODS=('OLD','NEW','NEW_3D')
CONDITIONS=('still','natural_movement','talking','smiling','glasses','low_light')
SPLITS={'T1_vs_T2':('T1','T2'),'T1_vs_T3':('T1','T3')}

def interval(values):
    a=[v for v in values if finite(v)]
    return np.percentile(a,[2.5,97.5]).tolist() if a else None

def cluster_ci(groups,stat):
    if len(groups)<2:return None
    rng=np.random.default_rng(C['seed']);keys=list(groups)
    return interval([stat([groups[keys[i]] for i in rng.integers(0,len(keys),len(keys))]) for _ in range(C['bootstrapDraws'])])

def extract_video(path):
    """Same CPU Tasks model and facial transformation matrices as the browser."""
    import cv2,mediapipe as mp
    model=old.FRONTEND.parent/'public/mediapipe/face_landmarker.task'
    options=mp.tasks.vision.FaceLandmarkerOptions(base_options=mp.tasks.BaseOptions(model_asset_path=str(model)),
        running_mode=mp.tasks.vision.RunningMode.VIDEO,num_faces=2,output_facial_transformation_matrixes=True)
    cap=cv2.VideoCapture(str(path));fps=cap.get(cv2.CAP_PROP_FPS)
    if not cap.isOpened() or fps<=0:cap.release();raise ValueError(f'Cannot decode {path}')
    rows=[];i=0;last=-math.inf
    try:
        with mp.tasks.vision.FaceLandmarker.create_from_options(options) as detector:
            while True:
                ok,frame=cap.read()
                if not ok:break
                seconds=i/fps;i+=1
                if seconds-last<.1-1e-9:continue
                last=seconds;h,w=frame.shape[:2]
                found=detector.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB,data=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)),round(seconds*1000))
                faces=found.face_landmarks;pts=[];matrix=None;pose=None;brightness=None
                if faces:
                    pts=[[p.x*w,p.y*h,p.z*w] for p in faces[0]]
                    if found.facial_transformation_matrixes:
                        a=np.asarray(found.facial_transformation_matrixes[0]);matrix=dict(rows=4,columns=4,data=a.flatten(order='F').tolist());pose=old.head_pose(matrix)
                    thumb=cv2.cvtColor(cv2.resize(frame,(64,48)),cv2.COLOR_BGR2RGB)
                    rgba=np.dstack([thumb,np.full((48,64),255,np.uint8)])
                    brightness=old.face_brightness(rgba,64,48,[dict(x=p.x,y=p.y) for p in faces[0]])
                rows.append(dict(time=seconds,points=pts,pose=pose,context=dict(width=w,height=h,brightness=brightness,faceCount=len(faces),matrix=matrix)))
    finally:cap.release()
    return rows,(i/fps)

def strict_four():
    """Freeze OLD hard gates/aggregation with the same FOUR-feature formula."""
    scan=old.QuickIndex();scan.keys=old.BASELINE_KEYS;scan.reference=old.reference_rows(old.BASELINE_KEYS)
    scan.measurements=old.ScanReliability(old.BASELINE_KEYS,lambda row:old.score_row(row,scan.reference,old.BASELINE_KEYS),old.BASELINE_KEYS)
    return scan

def score_segment(frames,duration):
    strict=strict_four();previous=None
    started=time.perf_counter()
    for r in frames:
        if r['time']>=C['duration']:break
        ctx=r['context'];p=r['points'];norm=[dict(x=v[0]/ctx['width'],y=v[1]/ctx['height']) for v in p]
        q=old.assess_quick_frame(norm,ctx['faceCount'],ctx['brightness'],previous);previous=q.get('center')
        strict.update(r['time'],p,r['pose'],q['good'],dict(brightness=ctx['brightness'],qualityReason=q['reason']))
    result=strict.finish();result['tier']='NONE' if result['average'] is None else 'LIMITED' if result['quality']=='limited' else 'NORMAL'
    result['ms_frame']=(time.perf_counter()-started)*1000/max(1,min(len(frames),int(C['duration']*10)))
    out={'OLD':result}
    for method in ('NEW','NEW_3D'):
        scan=TolerantScan(frontalize3d=method=='NEW_3D');started=time.perf_counter();elapsed=0.;processed=0;completed_at=None
        for r in frames:
            if r['time']>=C['maxDuration']:break
            elapsed=r['time'];scan.update(elapsed,r['points'],r['pose'],True,r['context']);processed+=1
            if adaptive_state(elapsed,scan.coverage())['state']=='analyzing':completed_at=elapsed;break
        completed_at=duration if completed_at is None else min(duration,completed_at)
        final=scan.finish(completed_at)
        final.update(ms_frame=(time.perf_counter()-started)*1000/max(1,processed),duration_seconds=completed_at)
        out[method]=final
    return out

def repeat_stats(rows,method):
    """Pooled within-subject/task SD; SEM=within SD; no between-face inflation."""
    groups=defaultdict(list)
    for r in rows:
        value=r['methods'][method]['average']
        if finite(value):groups[(r['subject_id'],r['task'])].append(value)
    groups={k:v for k,v in groups.items() if len(v)>=2}
    def estimate(samples):
        df=sum(len(v)-1 for v in samples)
        return math.sqrt(sum(float(np.sum((np.asarray(v)-np.mean(v))**2)) for v in samples)/df) if df else None
    value=estimate(list(groups.values()));subjects=defaultdict(list)
    for (subject,_),v in groups.items():subjects[subject].append(v)
    ci=cluster_ci(dict(subjects),lambda draws:estimate([v for g in draws for v in g]))
    return dict(within_condition_sd=value,sd_ci95=ci,sem=value,mdc95=1.96*math.sqrt(2)*value if value is not None else None,subjects_with_repeats=len(subjects),definition='Pooled residual SD within subject and task; SEM = single-scan within SD; MDC95 = 1.96*sqrt(2)*SEM.')

def condition_shift(rows,method,condition):
    differences={}
    for subject in sorted({r['subject_id'] for r in rows}):
        task_diffs=[]
        for task in sorted({r['task'] for r in rows if r['subject_id']==subject}):
            def vals(cond):return [r['methods'][method]['average'] for r in rows if r['subject_id']==subject and r['task']==task and r['condition']==cond and finite(r['methods'][method]['average'])]
            a,b=vals('still'),vals(condition)
            if a and b:task_diffs.append(float(np.mean(b)-np.mean(a)))
        if task_diffs:differences[subject]=float(np.mean(task_diffs))
    values=list(differences.values())
    return dict(mean_shift=float(np.mean(values)) if values else None,ci95=cluster_ci(differences,np.mean),
        mean_absolute_subject_shift=float(np.mean(np.abs(values))) if values else None,
        absolute_shift_ci95=cluster_ci(differences,lambda a:float(np.mean(np.abs(a)))),paired_subjects=len(values),definition='Subject-equal paired condition minus still, matched by task; adoption uses mean absolute subject shift to prevent cancellation.')

def task_metrics(rows,method,tasks):
    subjects={}
    for subject in sorted({r['subject_id'] for r in rows}):
        r=[r for r in rows if r['subject_id']==subject and r['task'] in tasks and finite(r['methods'][method]['average'])]
        rest=[10-v['methods'][method]['average'] for v in r if v['task']=='T1'];task=[10-v['methods'][method]['average'] for v in r if v['task']==tasks[1]]
        if rest and task:subjects[subject]=dict(auc=auc_value([0]*len(rest)+[1]*len(task),rest+task),difference=float(np.mean(task)-np.mean(rest)))
    values=list(subjects.values());diff=[v['difference'] for v in values]
    def dz(draws):return paired_stats([v['difference'] for v in draws])['cohen_dz']
    return dict(within_subject_auc=float(np.mean([v['auc'] for v in values])) if values else None,auc_ci95=cluster_ci(subjects,lambda a:float(np.mean([v['auc'] for v in a]))),cohen_dz=paired_stats(diff)['cohen_dz'],dz_ci95=cluster_ci(subjects,dz),subjects=len(subjects))

def comparison(rows):
    results={}
    for method in METHODS:
        per_condition={}
        for condition in CONDITIONS:
            selected=[r for r in rows if r['condition']==condition];counts={tier:sum(r['methods'][method]['tier']==tier for r in selected) for tier in ('NORMAL','LIMITED','NONE')}
            per_condition[condition]=dict(scans=len(selected),tier_counts=counts,tier_rates={k:v/len(selected) if selected else None for k,v in counts.items()},acceptance_rate=(counts['NORMAL']+counts['LIMITED'])/len(selected) if selected else None,
                shift_vs_still=condition_shift(rows,method,condition),**repeat_stats(selected,method),
                tasks={name:task_metrics(selected,method,tasks) for name,tasks in SPLITS.items()})
        # Task AUC comparison is specifically UBFC-Phys, never silently another dataset.
        ubfc=[r for r in rows if r['dataset'].lower().replace('-','_')=='ubfc_phys']
        results[method]=dict(conditions=per_condition,ubfc_tasks={name:task_metrics(ubfc,method,tasks) for name,tasks in SPLITS.items()})
    common=[r for r in rows if all(finite(r['methods'][m]['average']) for m in METHODS)]
    matched={m:dict(movement=repeat_stats([r for r in common if r['condition']=='natural_movement'],m),shift=condition_shift(common,m,'natural_movement')) for m in METHODS}
    auc_diffs={}
    for method in ('NEW','NEW_3D'):
        auc_diffs[method]={}
        for name,tasks in SPLITS.items():
            pairs=[r for r in rows if r['dataset'].lower().replace('-','_')=='ubfc_phys' and all(finite(r['methods'][m]['average']) for m in ('OLD',method))]
            a,b=task_metrics(pairs,method,tasks),task_metrics(pairs,'OLD',tasks)
            auc_diffs[method][name]=dict(old=b,new=a,auc_drop=b['within_subject_auc']-a['within_subject_auc'] if finite(a['within_subject_auc']) and finite(b['within_subject_auc']) else None)
    return dict(methods=results,matched_complete_case=matched,paired_ubfc_auc=auc_diffs,common_scans=len(common))

def adoption(stats,failed_videos=0):
    data=stats['methods'];new=data['NEW']['conditions'];criteria={}
    def record(name,value,ok,rule):criteria[name]=dict(value=value,status='PASS' if bool(ok) else 'FAIL',rule=rule)
    acceptance=new['natural_movement']['acceptance_rate'];record('movement_acceptance',acceptance,finite(acceptance) and acceptance>=C['acceptanceTarget'],'natural_movement acceptance >= 0.90')
    shift=new['natural_movement']['shift_vs_still'];mdc=data['OLD']['conditions']['still']['mdc95'];value=shift['mean_absolute_subject_shift']
    record('movement_shift',dict(shift=value,strict_still_mdc95=mdc),shift['paired_subjects']>=2 and finite(value) and finite(mdc) and value<=mdc,'mean absolute subject shift <= OLD still MDC95; >=2 paired subjects')
    matched=stats['matched_complete_case'];sd_old=matched['OLD']['movement']['within_condition_sd'];sd_new=matched['NEW']['movement']['within_condition_sd']
    record('movement_sd',dict(old=sd_old,new=sd_new),finite(sd_old) and finite(sd_new) and sd_new<=sd_old*(1+C['sdIncreaseMax']) and matched['OLD']['movement']['subjects_with_repeats']>=2,'common-cohort NEW movement SD <= 1.30 * OLD movement SD; >=2 repeated subjects')
    for split in SPLITS:
        item=stats['paired_ubfc_auc']['NEW'][split];drop=item['auc_drop'];record(split+'_auc_drop',drop,finite(drop) and drop<=C['aucDropMax'] and item['old']['subjects']>=2,'common-cohort UBFC-Phys within-subject AUC drop <= 0.02; >=2 subjects')
    record('video_extraction',failed_videos,failed_videos==0,'No failed video extractions may disappear from acceptance denominators')
    frontal={};a=matched['NEW']['shift']['mean_absolute_subject_shift'];b=matched['NEW_3D']['shift']['mean_absolute_subject_shift'];sd_b=matched['NEW_3D']['movement']['within_condition_sd']
    frontal['shift_reduction']=dict(status='PASS' if finite(a) and a>0 and finite(b) and b<=(1-C['frontalShiftReduction'])*a and matched['NEW']['shift']['paired_subjects']>=2 else 'FAIL',value=dict(without=a,with_3d=b),rule='>=25% smaller movement shift on complete cases; >=2 subjects')
    frontal['no_sd_increase']=dict(status='PASS' if finite(sd_new) and finite(sd_b) and sd_b<=sd_new and matched['NEW']['movement']['subjects_with_repeats']>=2 else 'FAIL',value=dict(without=sd_new,with_3d=sd_b),rule='Movement SD does not increase; >=2 repeated subjects')
    passed=all(v['status']=='PASS' for v in criteria.values())
    return dict(status='PASS' if passed else 'FAIL',criteria=criteria,frontalization=frontal,enable_frontalize3d=passed and all(v['status']=='PASS' for v in frontal.values()),adopt_new=passed,
        retained_setting='NEW eligible for explicit adoption' if passed else 'Keep OLD default. Failed or missing criteria retain strict settings; no automatic config rewrite.')

def write_report(result,output):
    out=Path(output);out.mkdir(parents=True,exist_ok=True)
    (out/'metrics.json').write_text(json.dumps(clean(result),indent=2,allow_nan=False))
    lines=['# Tolerance evaluation','','Tolerance trades bias for acceptance; expressions and pose change true geometry; the tiers never fabricate a score. Task labels are not clinically measured stress. No training, tuning or fitting on test labels. All constants were fixed in toleranceConfig.json before evaluation.','','OLD retains hard frame/mouth gates and uses the same four-feature canonical formula as NEW. The production strict generic mode still uses three features; it is not the OLD four-feature comparator. NEW and NEW_3D use the same source-segment starts, actual timestamps and first-second exclusion.','','Weighted coverage accumulates evidence against a fixed 45-slot target (clamped to 1). Extension adds genuinely new slots and up to 19 one-second windows; it never holds or duplicates observations. The ten-second denominator is intentionally unchanged.','','LOW evidence and failed video extraction produce FAIL. A passing report does not silently rewrite production settings.','','| Method | Condition | N | NORMAL % | LIMITED % | NONE % | Shift [95% CI] | Within SD | MDC95 |','|---|---|---:|---:|---:|---:|---|---:|---:|']
    def fmt(v):return 'unavailable' if v is None else f'{v:.4f}'
    for method in METHODS:
        for condition,r in result['comparison']['methods'][method]['conditions'].items():
            shift=r['shift_vs_still'];rates=r['tier_rates'];ci=shift['ci95']
            lines.append(f"| {method} | {condition} | {r['scans']} | {fmt(None if rates['NORMAL'] is None else rates['NORMAL']*100)} | {fmt(None if rates['LIMITED'] is None else rates['LIMITED']*100)} | {fmt(None if rates['NONE'] is None else rates['NONE']*100)} | {fmt(shift['mean_shift'])} [{', '.join(map(fmt,ci)) if ci else 'unavailable'}] | {fmt(r['within_condition_sd'])} | {fmt(r['mdc95'])} |")
    lines+=['','SD removes between-person and task offsets. Shift pairs subject and task. The adoption shift uses absolute per-subject shifts, not cancellation of signed effects. Methods compare AUC and SD on complete cases; the condition acceptance denominator includes NONE. All source failures are listed and block adoption. Full within-condition SD CIs are in metrics.json.','','## Per-condition task splits','','| Method | Condition | Split | Within-subject AUC [CI] | d_z [CI] | Subjects |','|---|---|---|---|---|---:|']
    for method in METHODS:
        for condition,r in result['comparison']['methods'][method]['conditions'].items():
            for split,m in r['tasks'].items():
                lines.append(f"| {method} | {condition} | {split} | {fmt(m['within_subject_auc'])} {m['auc_ci95']} | {fmt(m['cohen_dz'])} {m['dz_ci95']} | {m['subjects']} |")
    lines+=['','## UBFC-Phys task splits','','| Method | Split | Within-subject AUC [CI] | d_z [CI] | Subjects |','|---|---|---|---|---:|']
    for method in METHODS:
        for split,r in result['comparison']['methods'][method]['ubfc_tasks'].items():
            lines.append(f"| {method} | {split} | {fmt(r['within_subject_auc'])} {r['auc_ci95']} | {fmt(r['cohen_dz'])} {r['dz_ci95']} | {r['subjects']} |")
    lines+=['','## Fixed decision','',result['decision']['status'],'']
    for name,criterion in result['decision']['criteria'].items():lines.append(f"- {name}: **{criterion['status']}** — {criterion['rule']}; value={criterion['value']}")
    for name,criterion in result['decision']['frontalization'].items():lines.append(f"- frontalize3d {name}: **{criterion['status']}** — {criterion['rule']}; value={criterion['value']}")
    lines+=['',result['decision']['retained_setting'],'','## Extraction failures','',json.dumps(result['failed_videos'],indent=2),'','No real-data accuracy or adoption claim follows from synthetic tests or an empty manifest.']
    (out/'report.md').write_text('\n'.join(lines)+'\n')
    fig,ax=plt.subplots(figsize=(8,5));plotted=False
    for method in METHODS:
        for condition,r in result['comparison']['methods'][method]['conditions'].items():
            if finite(r['acceptance_rate']) and finite(r['within_condition_sd']):ax.scatter(r['within_condition_sd'],100*r['acceptance_rate']);ax.annotate(method+'/'+condition,(r['within_condition_sd'],100*r['acceptance_rate']),fontsize=7);plotted=True
    if not plotted:ax.text(.5,.5,'No repeated-condition evidence available',ha='center',transform=ax.transAxes)
    ax.set(xlabel='Within-condition SD (index points)',ylabel='Acceptance (NORMAL + LIMITED), %',title='Acceptance–SD trade-off');fig.tight_layout();fig.savefig(out/'acceptance_vs_sd.png',dpi=150);plt.close(fig)

def run(manifest,output,extractor=extract_video):
    path=Path(manifest)
    with path.open(newline='') as f:entries=list(csv.DictReader(f))
    cache={};rows=[];failed=[]
    for entry in entries:
        if not all(entry.get(k) for k in ('video_path','subject_id','condition','task','dataset')):raise ValueError('Manifest requires video_path,subject_id,condition,task,dataset')
        if entry['condition'] not in CONDITIONS or entry['task'] not in ('T1','T2','T3'):raise ValueError('Invalid condition or task')
        video=Path(entry['video_path']);video=video if video.is_absolute() else path.parent/video
        try:
            key=str(video.resolve())
            if key not in cache:
                # Bound memory on an M1: retain at most one video's landmarks.
                cache.clear();cache[key]=extractor(video)
            records,duration=cache[key]
            start=float(entry.get('start_seconds') or 0);end=min(duration,float(entry.get('end_seconds') or duration))
            if end-start<C['duration']:raise ValueError('Segment is shorter than 10 seconds')
            # Fixed disjoint 20 s source blocks; OLD uses their first 10 s.
            for left in np.arange(start,end-C['duration']+1e-8,C['maxDuration']):
                available=min(C['maxDuration'],end-left)
                frames=[dict(r,time=r['time']-left) for r in records if left<=r['time']<left+available]
                scores=score_segment(frames,available)
                rows.append(dict(subject_id=entry['dataset']+':'+entry['subject_id'],dataset=entry['dataset'],task=entry['task'],condition=entry['condition'],clip_id=f'{video.name}@{left:g}',source_duration=available,methods=scores))
        except (OSError,ValueError,RuntimeError) as exc:failed.append(dict(video_path=str(video),subject_id=entry['subject_id'],condition=entry['condition'],error=str(exc)))
    stats=comparison(rows);result=dict(config=C,records=rows,comparison=stats,decision=adoption(stats,len(failed)),failed_videos=failed)
    write_report(result,output);return result

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest',required=True);p.add_argument('--output',default='stress_math/results/tolerance');args=p.parse_args()
    r=run(args.manifest,args.output);print(f"{r['decision']['status']}: {args.output}/report.md ({len(r['records'])} clips, {len(r['failed_videos'])} failed videos)")

if __name__=='__main__':main()
