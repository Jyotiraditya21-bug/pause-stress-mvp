"""Analyse explicitly consented candidate study JSON logs; no fitting or tuning."""
import argparse,json,math,hashlib
from collections import defaultdict
from datetime import datetime
from pathlib import Path
import numpy as np
from scipy.stats import wilcoxon
from sklearn.metrics import roc_auc_score
from .repeatability import icc21
from .prospective_mirror import FRONTEND
POLICY_SHA=hashlib.sha256((FRONTEND/'prospectivePolicy.json').read_bytes()).hexdigest()

TASKS=('rest','speech','arithmetic')
NUISANCES=('brightness_0.6','brightness_1.4','320x240','jpeg40','rotation_-10','rotation_10')
def timestamp(s):return datetime.fromisoformat(s.replace('Z','+00:00')).timestamp()
def ci(a):
    finite=[v for v in a if v is not None and np.isfinite(v)]
    return np.percentile(finite,[2.5,97.5]).tolist() if finite else None

def analyse(logs,nuisances=None):
    rng=np.random.default_rng(42);attempts=defaultdict(list);groups=defaultdict(list);invalid=[];seen=set()
    for log in logs:
        for pair in log.get('pairs',[]):
            subject=pair.get('subject_id');condition=pair.get('condition')
            if not subject or condition not in TASKS:raise ValueError('Each pair needs subject_id and rest/speech/arithmetic condition')
            records=[]
            for r in pair.get('records',[]):
                if r.get('id') in seen:continue
                seen.add(r.get('id'))
                if r.get('acceptancePolicy',{}).get('version')!='prospective-acquisition-1' or r.get('acceptancePolicy',{}).get('policySha256')!=POLICY_SHA:raise ValueError('Mixed acquisition policies are not a candidate validation set')
                attempts[condition].append(r);records.append(r)
            if len(records)!=2:
                invalid.append(dict(pair=pair.get('id'),reason='requires exactly two completed attempts'));continue
            delta=timestamp(records[1]['created_at'])-timestamp(records[0]['created_at'])
            if not 300<=delta<=600:
                invalid.append(dict(pair=pair.get('id'),reason='interval outside 5–10 minutes',interval_seconds=delta));continue
            if all(r.get('status') in ('ok','limited') and isinstance(r.get('average'),(int,float)) and np.isfinite(r['average']) for r in records):
                groups[(subject,condition)].append(records)
    report=dict(policy_sha256=POLICY_SHA,seed=42,bootstrap_draws=1000,minimum_subjects=20,invalid_pairs=invalid,coverage={},methods={},decision='NOT ESTABLISHED',clinical_validity=False)
    for task in TASKS:
        rows=attempts[task];accepted=sum(r.get('status') in ('ok','limited') and isinstance(r.get('average'),(int,float)) and np.isfinite(r['average']) for r in rows)
        report['coverage'][task]=dict(attempts=len(rows),accepted=int(accepted),percent=100*accepted/len(rows) if rows else None)
    for method in ('geometry','neural'):
        def score(r):
            if method=='geometry':return float(r['average'])
            p=r.get('mlResult',{}).get('averageStressProbability')
            return 10*(1-float(p)) if isinstance(p,(int,float)) and np.isfinite(p) else None
        values={};pairs={}
        for key,records in groups.items():
            # Predeclared: first valid timed pair per person/condition, no best-pair selection.
            a=[score(r) for r in records[0]]
            if all(v is not None for v in a):values[key]=a;pairs[key]=records[0]
        entry={'task_comparisons':{},'repeatability':{},'nuisance':{},'criteria':{}}
        for task in ('speech','arithmetic'):
            subjects=sorted({s for s,c in values if c=='rest' and (s,task) in values})
            aucs=[];effects=[]
            for s in subjects:
                rest=values[(s,'rest')];stress=values[(s,task)]
                aucs.append(roc_auc_score([0]*len(rest)+[1]*len(stress),[-v for v in rest+stress]))
                effects.append(np.mean(rest)-np.mean(stress))
            draws=[np.mean(rng.choice(aucs,len(aucs),replace=True)) for _ in range(1000)] if aucs else []
            bounds=ci(draws);effect=float(np.mean(effects)) if effects else None
            dz=float(np.mean(effects)/np.std(effects,ddof=1)) if len(effects)>1 and np.std(effects,ddof=1)>0 else None
            p=float(wilcoxon(effects).pvalue) if effects and any(v!=0 for v in effects) else (1. if effects else None)
            entry['task_comparisons'][task]=dict(subjects=len(subjects),within_subject_auc=float(np.mean(aucs)) if aucs else None,auc_ci95=bounds,mean_within_person_effect=effect,cohen_dz=dz,wilcoxon_p=p)
            entry['criteria'][task+'_auc']=bool(len(subjects)>=20 and bounds and bounds[0]>.60)
        for task in TASKS:
            subjects=sorted(s for s,c in values if c==task)
            x=np.array([values[(s,task)] for s in subjects])
            sd=float(np.sqrt(np.mean(np.var(x,axis=1,ddof=1)))) if len(x) else None
            icc=icc21(x) if len(x)>=2 else None
            bounds=ci([icc21(x[rng.choice(len(x),len(x),replace=True)]) for _ in range(1000)]) if len(x)>=2 else None
            mdc=1.96*math.sqrt(2)*sd if sd is not None else None
            entry['repeatability'][task]=dict(subjects=len(subjects),within_condition_sd=sd,single_measure_sem=sd,mdc95=mdc,icc21=icc,icc_ci95=bounds)
            entry['criteria'][task+'_repeatability']=bool(len(subjects)>=20 and mdc is not None and mdc<=1 and bounds and bounds[0]>=.75)
        for name in NUISANCES:
            rows=[r for r in (nuisances or []) if r.get('method')==method and r.get('nuisance')==name]
            for task in ('speech','arithmetic'):
                effect=entry['task_comparisons'][task]['mean_within_person_effect']
                # Consent-matched clips must identify subject and clip; unknown/failed transformations cannot pass.
                valid=[r for r in rows if r.get('subject_id') and r.get('clip_id') and r.get('accepted') is True and all(isinstance(r.get(k),(int,float)) and np.isfinite(r[k]) for k in ('baseline_score','perturbed_score'))]
                shift=float(np.mean([abs(r['perturbed_score']-r['baseline_score']) for r in valid])) if valid else None
                enough=len({r['subject_id'] for r in valid})>=20 and len(valid)==len(rows)
                passed=bool(enough and effect is not None and abs(effect)>0 and shift<.5*abs(effect))
                key=name+'_'+task;entry['nuisance'][key]=dict(matched_clips=len(valid),mean_absolute_shift=shift,stress_effect=effect)
                entry['criteria'][key]=passed
        entry['criteria']['coverage']=all(report['coverage'][t]['percent'] is not None and report['coverage'][t]['percent']>=80 for t in TASKS)
        entry['passed']=all(entry['criteria'].values())
        report['methods'][method]=entry
    report['decision']='PASS engineering pilot gates only' if all(v['passed'] for v in report['methods'].values()) else 'NOT ESTABLISHED / HOLD'
    report['notes']=['Task labels are not clinically measured stress.','Neural probability is shown as a reversed 0–10 display for same-scale repeatability only; never fused with geometry.','Failed and off-protocol attempts remain in acquisition coverage denominators. Off-protocol pairs are excluded from paired metrics, not an additional global release veto.','No threshold or model fitting performed.','Nuisance JSON uses method, nuisance, subject_id, clip_id, accepted, baseline_score and perturbed_score; scores on the respective 0–10 display scale.','SEM is single-measure within-condition SD, not SEM of a mean.']
    return report

def run(paths,output,nuisance=None):
    output=Path(output)
    if output.exists():raise FileExistsError('Preserve existing reports; choose a new output directory')
    logs=[json.loads(Path(p).read_text()) for p in paths]
    result=analyse(logs,json.loads(Path(nuisance).read_text()) if nuisance else None)
    output.mkdir(parents=True)
    (output/'metrics.json').write_text(json.dumps(result,indent=2,allow_nan=False))
    text=['# Prospective participant evaluation','',result['decision'],'','No data or undefined criteria never constitute a pass.','']
    for method,entry in result['methods'].items():
        text += ['## '+method,'']+[f"- {k}: {'PASS' if v else 'NOT ESTABLISHED / FAIL'}" for k,v in entry['criteria'].items()]+['']
    text+=result['notes'];(output/'report.md').write_text('\n'.join(text)+'\n')
    print(result['decision'])
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('logs',nargs='+');p.add_argument('--output',required=True);p.add_argument('--nuisance');a=p.parse_args();run(a.logs,a.output,a.nuisance)
