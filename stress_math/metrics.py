import numpy as np
from scipy.stats import wilcoxon, spearmanr, pearsonr, rankdata
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, balanced_accuracy_score, confusion_matrix, roc_auc_score, average_precision_score

RESAMPLES = 1000

def basic(y,s):
    y=np.asarray(y,int); s=np.asarray(s,float)
    valid=np.isfinite(s); y=y[valid]; s=s[valid]
    if not len(s): return {'status':'unavailable','n':0}
    pred=s>50
    out=dict(n=len(s),accuracy=accuracy_score(y,pred),precision=precision_score(y,pred,zero_division=0),recall=recall_score(y,pred,zero_division=0),f1=f1_score(y,pred,zero_division=0),balanced_accuracy=balanced_accuracy_score(y,pred) if len(np.unique(y))==2 else None,confusion_matrix=confusion_matrix(y,pred,labels=[0,1]).tolist(),roc_auc=None,pr_auc=None)
    if len(np.unique(y))==2: out.update(roc_auc=roc_auc_score(y,s),pr_auc=average_precision_score(y,s))
    return out

def auc_value(y,s):
    y=np.asarray(y); s=np.asarray(s,float); pos=y==1
    n1=pos.sum(); n0=len(y)-n1
    if not n1 or not n0: return None
    return float((rankdata(s)[pos].sum()-n1*(n1+1)/2)/(n1*n0))

def paired_stats(diff):
    diff=np.asarray(diff,float)
    out={'pairs':len(diff),'cohen_dz':None,'wilcoxon_p':None}
    if len(diff)>=2:
        sd=diff.std(ddof=1)
        out['cohen_dz']=float(diff.mean()/sd) if sd>1e-12 else None
        out['wilcoxon_p']=float(wilcoxon(diff).pvalue) if np.any(diff) else 1.
    return out

def summarize(records,score_key='new'):
    usable=[r for r in records if not r.get('excluded',False) and np.isfinite(r.get(score_key,np.nan))]
    out=basic([r['label'] for r in usable],[r[score_key] for r in usable])
    if not usable: return out
    subjects=sorted(set(str(r['subject_id']) for r in usable)); rng=np.random.default_rng(42)
    grouped={s:[r for r in usable if str(r['subject_id'])==s] for s in subjects}
    y=np.array([r['label'] for r in usable]); scores=np.array([r[score_key] for r in usable])
    indices={s:np.array([i for i,r in enumerate(usable) if str(r['subject_id'])==s]) for s in subjects}
    diffs={}
    for s in subjects:
        a=[r[score_key] for r in grouped[s] if r['label']==0]; b=[r[score_key] for r in grouped[s] if r['label']==1]
        if a and b: diffs[s]=float(np.mean(b)-np.mean(a))
    out['within_subject']=paired_stats(list(diffs.values()))
    cis={k:[] for k in ('accuracy','f1','roc_auc','cohen_dz','wilcoxon_p')}
    for _ in range(RESAMPLES):
        draws=rng.choice(subjects,len(subjects),replace=True)
        idx=np.concatenate([indices[s] for s in draws]); yy=y[idx]; ss=scores[idx]; pp=ss>50
        tp=np.sum((yy==1)&pp); fp=np.sum((yy==0)&pp); fn=np.sum((yy==1)&~pp)
        values={'accuracy':float(np.mean(yy==pp)),'f1':float(2*tp/(2*tp+fp+fn)) if 2*tp+fp+fn else 0.,'roc_auc':auc_value(yy,ss)}
        # Duplicate subject draws must duplicate the paired difference, not merge IDs.
        values.update(paired_stats([diffs[s] for s in draws if s in diffs]))
        for k in cis:
            if values.get(k) is not None: cis[k].append(values[k])
    out['subject_bootstrap_95ci']={k:np.percentile(v,[2.5,97.5]).tolist() if v else None for k,v in cis.items()}
    out['bootstrap_valid_resamples']={k:len(v) for k,v in cis.items()}
    out['subjects']=len(subjects)
    out['primary']={k:{'value':out.get(k) if k=='roc_auc' else out['within_subject'][k], 'ci95':out['subject_bootstrap_95ci'][k]} for k in ('roc_auc','cohen_dz','wilcoxon_p')}
    out['secondary']={k:out.get(k) for k in ('accuracy','precision','recall','f1','balanced_accuracy','confusion_matrix')}
    out['secondary']['note']='S > 50; baseline = 50 by construction at feature means. This is not a clinical threshold.'
    out['condition_scores']={str(label):{'mean':float(scores[y==label].mean()),'std':float(scores[y==label].std())} for label in (0,1) if np.any(y==label)}
    reported=[r for r in usable if r.get('self_report') not in (None,'')]
    out['self_report_spearman']=None
    if len(reported)>=3:
        a=[float(r['self_report']) for r in reported]; b=[r[score_key] for r in reported]
        if np.std(a)>0 and np.std(b)>0:
            corr=spearmanr(a,b); out['self_report_spearman']={'r':float(corr.statistic),'p':float(corr.pvalue)}
    return out

def permutation_test(records,score_key='new'):
    usable=[r for r in records if not r.get('excluded',False) and np.isfinite(r.get(score_key,np.nan))]
    y=np.array([r['label'] for r in usable]); scores=np.array([r[score_key] for r in usable]); observed=auc_value(y,scores)
    out={'seed':42,'shuffles':1000,'scheme':'shuffle task labels within subject, preserving each subject task counts','observed_auc':observed,'null_auc_distribution':[], 'null_auc_mean':None,'null_auc_95_interval':None,'p_value':None}
    if observed is None: out['status']='unavailable: two classes required'; return out
    subjects=sorted(set(str(r['subject_id']) for r in usable))
    groups=[np.array([i for i,r in enumerate(usable) if str(r['subject_id'])==s]) for s in subjects]
    if not any(len(set(y[g]))==2 for g in groups): out['status']='unavailable: no exchangeable within-subject labels'; return out
    rng=np.random.default_rng(42); null=[]
    for _ in range(1000):
        shuffled=y.copy()
        for g in groups: shuffled[g]=rng.permutation(y[g])
        null.append(auc_value(shuffled,scores))
    out.update(null_auc_distribution=null,null_auc_mean=float(np.mean(null)),null_auc_95_interval=np.percentile(null,[2.5,97.5]).tolist(),p_value=float((1+np.sum(np.array(null)>=observed))/1001))
    return out

def paired_auc_test(records):
    # Retained for API compatibility; OLD has no video scorer.
    r=[x for x in records if not x.get('excluded',False) and np.isfinite(x.get('old',np.nan)) and np.isfinite(x.get('new',np.nan))]
    if not r: return {'status':'unavailable: OLD has no video scorer'}
    subjects=sorted(set(str(x['subject_id']) for x in r)); rng=np.random.default_rng(42); delta=[]
    for _ in range(1000):
        sample=[x for s in rng.choice(subjects,len(subjects),replace=True) for x in r if str(x['subject_id'])==s]
        y=[x['label'] for x in sample]; a=auc_value(y,[x['new'] for x in sample]); b=auc_value(y,[x['old'] for x in sample])
        if a is not None and b is not None: delta.append(a-b)
    return {'delta_95ci':np.percentile(delta,[2.5,97.5]).tolist() if delta else None,'two_sided_bootstrap_p':min(1.,2*min(np.mean(np.array(delta)<=0),np.mean(np.array(delta)>=0))) if delta else None}

def au_validity(rows,path):
    import pandas as pd
    table=pd.read_csv(path); result={}
    for feature,au in [('brow_furrow','AU4'),('lip_press','AU23'),('lip_corner','AU12')]:
        if au not in table or table.empty: result[au]={'status':'missing/empty column'}; continue
        a=[]; b=[]
        for row in rows:
            idx=np.argmin(abs(table['time'].to_numpy()-row['time']))
            if abs(table.iloc[idx]['time']-row['time'])<.05 and np.isfinite(row.get(feature,np.nan)) and np.isfinite(table.iloc[idx][au]):
                a.append(row[feature]); b.append(table.iloc[idx][au])
        if len(a)>2 and np.std(a)>0 and np.std(b)>0:
            r=pearsonr(a,b); result[au]={'r':float(r.statistic),'p':float(r.pvalue),'n':len(a),'direction':'negative expected for AU12 (downward-corner feature)' if au=='AU12' else 'positive expected'}
        else: result[au]={'status':'insufficient aligned variable data'}
    return result
