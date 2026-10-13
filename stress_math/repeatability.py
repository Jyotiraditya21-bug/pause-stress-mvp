"""Within-person repeatability analysis for own-session CSV manifests."""
from __future__ import annotations
import argparse,csv,json
from collections import defaultdict
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.stats import pearsonr
from .validation_stats import decision,auc_value

def finite(x):
 try:return x is not None and np.isfinite(float(x))
 except (TypeError,ValueError):return False

def icc21(matrix):
 """Two-way random, absolute agreement, single-measure ICC(2,1)."""
 x=np.asarray(matrix,float);n,k=x.shape
 if n<2 or k<2:return None
 gm=x.mean();msr=k*np.sum((x.mean(1)-gm)**2)/(n-1);msc=n*np.sum((x.mean(0)-gm)**2)/(k-1)
 mse=np.sum((x-x.mean(1)[:,None]-x.mean(0)[None,:]+gm)**2)/((n-1)*(k-1))
 den=msr+(k-1)*mse+k*(msc-mse)/n
 return float((msr-mse)/den) if den else None

def repeated_measures_corr(rows):
 by=defaultdict(list)
 for r in rows:
  if finite(r.get('score')) and finite(r.get('self_report')):by[r['subject_id']].append((float(r['score']),float(r['self_report'])))
 pairs=[v for v in by.values() if len(v)>=2]
 if len(pairs)<2:return dict(r=None,p=None,n_subjects=len(pairs),observations=sum(map(len,pairs)))
 sx=[];sy=[]
 for v in pairs:
  a=np.asarray(v);sx.extend(a[:,0]-a[:,0].mean());sy.extend(a[:,1]-a[:,1].mean())
 if np.std(sx)==0 or np.std(sy)==0:return dict(r=None,p=None,n_subjects=len(pairs),observations=len(sx))
 r=pearsonr(sx,sy)
 return dict(r=float(r.statistic),p=float(r.pvalue),n_subjects=len(pairs),observations=len(sx),definition='Pearson correlation after removing each subject mean.')

def condition_stats(rows):
 grouped=defaultdict(lambda:defaultdict(list))
 for r in rows:
  if finite(r.get('score')):grouped[r['condition']][r['subject_id']].append(float(r['score']))
 out={}
 for cond,subjects in grouped.items():
  within=[float(np.std(v,ddof=1)) for v in subjects.values() if len(v)>=2]
  pooled=float(np.sqrt(np.mean(np.square(within)))) if within else None
  reps=float(np.mean([len(v) for v in subjects.values() if len(v)>=2])) if within else None
  sem=pooled/np.sqrt(reps) if pooled is not None and reps else None
  out[cond]=dict(subjects=len(subjects),subjects_with_repeats=len(within),within_subject_sd=pooled,mean_repeats=reps,sem=sem,mdc95=1.96*np.sqrt(2)*sem if sem is not None else None,individual_within_sd={s:float(np.std(v,ddof=1)) for s,v in subjects.items() if len(v)>=2})
 return out

def complete_iccs(rows):
 result={}
 for condition in sorted({r['condition'] for r in rows}):
  by=defaultdict(list)
  for r in rows:
   if r['condition']==condition and finite(r.get('score')):by[r['subject_id']].append(r)
  seq={s:[float(r['score']) for r in sorted(v,key=lambda x:(str(x.get('day','')),x['session_id']))] for s,v in by.items()}
  repeats=min((len(v) for v in seq.values()),default=0);matrix=[v[:repeats] for v in seq.values()] if repeats>=2 else []
  result[condition]=dict(icc21=icc21(matrix) if matrix else None,complete_subjects=len(matrix),repeat_columns=list(range(1,repeats+1)),note='Complete subjects aligned by within-condition repeat order; ICC(2,1), absolute agreement.')
 return result

def own_within_subject_auc(rows):
 aliases={'rest':0,'t1':0,'relaxed':0,'arithmetic':1,'t3':1,'speech':2,'speaking':2,'t2':2}
 normalized=[]
 for r in rows:
  label=aliases.get(str(r['condition']).strip().lower())
  if label is not None:normalized.append((r['subject_id'],label,10-float(r['score'])))
 result={}
 for task,label in (('T1_vs_T3',1),('T1_vs_T2',2)):
  vals=[]
  for subject in sorted({x[0] for x in normalized}):
   chosen=[x for x in normalized if x[0]==subject and x[1] in (0,label)]
   auc=auc_value([int(x[1]==label) for x in chosen],[x[2] for x in chosen])
   if auc is not None:vals.append(auc)
  if vals:
   rng=np.random.default_rng(42);a=np.asarray(vals);draws=[np.mean(rng.choice(a,len(a),replace=True)) for _ in range(1000)]
   result[task]=dict(auc=float(a.mean()),ci95=np.percentile(draws,[2.5,97.5]).tolist(),subjects=len(vals),seed=42,draws=1000)
  else:result[task]=dict(auc=None,ci95=None,subjects=0)
 return result

def bland_altman(rows,path):
 pairs=[];by=defaultdict(list)
 for r in rows:
  if finite(r.get('score')):by[(r['subject_id'],r['condition'])].append(r)
 for key,vals in by.items():
  def order(x):
   try:return (0,float(x.get('day','')),x['session_id'])
   except (TypeError,ValueError):return (1,str(x.get('day','')),x['session_id'])
  vals=sorted(vals,key=order)
  for a,b in zip(vals,vals[1:]):pairs.append((key[1],(float(a['score'])+float(b['score']))/2,float(b['score'])-float(a['score'])))
 fig,ax=plt.subplots(figsize=(8,5))
 for cond in sorted({p[0] for p in pairs}):
  part=[p for p in pairs if p[0]==cond]
  if part:ax.scatter([p[1] for p in part],[p[2] for p in part],label=cond,alpha=.75)
 diffs=[p[2] for p in pairs]
 if diffs:
  mean=float(np.mean(diffs));sd=float(np.std(diffs,ddof=1)) if len(diffs)>1 else 0.
  ax.axhline(mean,color='black',label=f'Mean bias {mean:.2f}');ax.axhline(mean+1.96*sd,color='gray',linestyle='--');ax.axhline(mean-1.96*sd,color='gray',linestyle='--')
 ax.set(xlabel='Mean of adjacent repeat scores',ylabel='Later minus earlier score',title='Bland–Altman repeatability');ax.legend();fig.tight_layout();fig.savefig(path,dpi=150);plt.close(fig)
 return dict(pairs=len(pairs),mean_bias=float(np.mean(diffs)) if diffs else None,limits95=[float(np.mean(diffs)-1.96*np.std(diffs,ddof=1)),float(np.mean(diffs)+1.96*np.std(diffs,ddof=1))] if len(diffs)>1 else None)

def run(manifest,output,metrics_path=None):
 path=Path(manifest)
 with path.open(newline='') as f:rows=list(csv.DictReader(f))
 required={'subject_id','session_id','day','condition','score','self_report'}
 if not rows or not required.issubset(rows[0]):raise ValueError('CSV requires subject_id, session_id, day, condition, score, self_report')
 if any(not finite(r['score']) for r in rows):raise ValueError('Each row needs a numeric score')
 for r in rows:r['score']=float(r['score'])
 output=Path(output);output.mkdir(parents=True,exist_ok=True)
 conditions=condition_stats(rows);icc=complete_iccs(rows);rmcorr=repeated_measures_corr(rows);ba=bland_altman(rows,output/'bland_altman.png')
 aucs=own_within_subject_auc(rows)
 task_splits={'T1_vs_T2':{'methods':{'D0':{'within_subject_auc':{'ci95':aucs['T1_vs_T2']['ci95']}}}},'T1_vs_T3':{'methods':{'D0':{'within_subject_auc':{'ci95':aucs['T1_vs_T3']['ci95']}}}}}
 nuisance={};nuisance_source='missing; nuisance criteria fail'
 if metrics_path:
  evaluation=json.loads(Path(metrics_path).read_text())
  evaluated_ids={str(r.get('subject_id','')).split(':')[-1] for r in evaluation.get('records',[])}
  manifest_ids={str(r['subject_id']) for r in rows}
  if manifest_ids and manifest_ids.issubset(evaluated_ids):
   nuisance=evaluation.get('nuisance_sensitivity',{});nuisance_source='evaluation records contain every manifest subject ID'
  else:nuisance_source='rejected: evaluation records do not contain the manifest subjects'
 gate=decision(task_splits,nuisance,'D0')
 result=dict(manifest=str(path),n_sessions=len(rows),conditions=conditions,icc21=icc,repeated_measures_correlation=rmcorr,within_subject_auc=aucs,nuisance_evidence=nuisance_source,bland_altman=ba,decision=gate)
 (output/'metrics.json').write_text(json.dumps(result,indent=2,allow_nan=False))
 lines=['# Own-session repeatability report','',f"Sessions: {len(rows)}",'','## Within-condition repeatability','','| Condition | Subjects | Repeats | Within-subject SD | SEM | MDC95 |','|---|---:|---:|---:|---:|---:|']
 for c,v in conditions.items():lines.append(f"| {c} | {v['subjects']} | {v['subjects_with_repeats']} | {v['within_subject_sd']} | {v['sem']} | {v['mdc95']} |")
 lines+=['','## Within-subject AUC and 95% CI','',json.dumps(aucs,indent=2),'','## ICC(2,1) by condition','',json.dumps(icc,indent=2),'','## Score/self-report repeated-measures correlation','',json.dumps(rmcorr,indent=2),'','## Bland–Altman','','Plot: bland_altman.png','',json.dumps(ba,indent=2),'','## Predeclared decision rule','','PASS requires lower within-subject AUC 95% CI >0.60 for rest vs arithmetic and rest vs speech, and every D0 nuisance shift <half the corresponding stress effect. Nuisance evidence is accepted only when the evaluation metrics contain every subject in this manifest. SEM = pooled within-subject SD divided by the square root of mean repeat count; MDC95 = 1.96 × square-root-of-2 × SEM.']
 lines.append('Nuisance evidence: '+nuisance_source+'.')
 for k,v in gate['criteria'].items():lines.append(f"- {'PASS' if v['pass_'] else 'FAIL'} — {k}: {v.get('value')} ({v['rule']})")
 lines+=['',f"**Overall: {gate['status']}**"];(output/'report.md').write_text('\n'.join(lines)+'\n')
 return result

def main():
 p=argparse.ArgumentParser();p.add_argument('--manifest',required=True);p.add_argument('--metrics');p.add_argument('--output',default='stress_math/results/repeatability');a=p.parse_args();run(a.manifest,a.output,a.metrics)
if __name__=='__main__':main()
