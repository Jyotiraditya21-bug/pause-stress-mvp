"""Predeclared validation statistics; subject is the resampling unit."""
import itertools
import numpy as np
from scipy.stats import spearmanr
from .metrics import summarize, permutation_test, paired_method_auc_difference, auc_value

DRAWS=1000
SEED=42
METHODS=('D0','D1','D2')
NUISANCES=('brightness_0.6','brightness_1.4','320x240','jpeg40','rotation_-10','rotation_10')
SPLITS={'T1_vs_T2':('T1','T2'),'T1_vs_T3':('T1','T3'),'pooled':('T1','T2','T3')}


def finite(v):
    return v is not None and np.isfinite(v)


def clean(value):
    if isinstance(value,dict):return {str(k):clean(v) for k,v in value.items()}
    if isinstance(value,(list,tuple,np.ndarray)):return [clean(v) for v in value]
    if isinstance(value,(bool,np.bool_)):return bool(value)
    if isinstance(value,(int,np.integer)):return int(value)
    if isinstance(value,(float,np.floating)):return float(value) if np.isfinite(value) else None
    return value


def holm(tests):
    ordered=sorted((v['p_value_two_sided_centered_bootstrap'],k) for k,v in tests.items()
                   if finite(v.get('p_value_two_sided_centered_bootstrap')))
    previous=0.
    for i,(p,k) in enumerate(ordered):
        previous=max(previous,min(1.,p*(len(ordered)-i)))
        tests[k].update(raw_p_value=p,holm_adjusted_p_value=previous)
    for v in tests.values():
        v.setdefault('raw_p_value',None);v.setdefault('holm_adjusted_p_value',None)
        v['holm_family_size']=len(ordered)
    return tests


def within_subject_auc(records,method):
    """Equal-subject mean AUC; never compare different people's raw offsets."""
    values=[]
    for subject in sorted({r['subject_id'] for r in records}):
        rows=[r for r in records if r['subject_id']==subject and finite(r['methods'].get(method))]
        a=auc_value([r['label'] for r in rows],[r['methods'][method] for r in rows])
        if a is not None:values.append(a)
    if len(values)<2:return dict(auc=float(np.mean(values)) if values else None,ci95=None,subjects=len(values))
    rng=np.random.default_rng(SEED);a=np.asarray(values)
    draws=[np.mean(rng.choice(a,len(a),replace=True)) for _ in range(DRAWS)]
    return dict(auc=float(a.mean()),ci95=np.percentile(draws,[2.5,97.5]).tolist(),subjects=len(a),seed=SEED,draws=DRAWS)


def analyze(records,methods=METHODS):
    result={};pairs={}
    for split,tasks in SPLITS.items():
        selected=[r for r in records if r['task'] in tasks]
        reports={};nulls={}
        for m in methods:
            rows=[dict(r,s=r['methods'][m]) for r in selected if finite(r['methods'].get(m))]
            metrics=summarize(rows,'s')
            # Generic D0 has a canonical reference, not a personal baseline.
            # D2 is unbounded variance and has no fixed classification threshold.
            for k in ('accuracy','precision','recall','f1','balanced_accuracy','confusion_matrix','secondary'):
                metrics.pop(k,None)
            for k in ('subject_bootstrap_95ci','bootstrap_valid_resamples'):
                if k in metrics:metrics[k]={x:v for x,v in metrics[k].items() if x not in ('accuracy','f1')}
            metrics['within_subject_auc']=within_subject_auc(selected,m)
            eligible=[r for r in rows if not r.get('excluded',False)]
            metrics['coverage']=dict(total_clips=len(selected),accepted_clips=len(eligible),
                accepted_percent=100*len(eligible)/len(selected) if selected else None,
                mean_slot_coverage_percent=float(np.mean([r['coverage_percent'] for r in selected])) if selected else None,
                excluded_clips=[r['clip_id'] for r in selected if r.get('excluded',False) or not finite(r['methods'].get(m))])
            reports[m]=metrics;nulls[m]=permutation_test(rows,'s')
        for a,b in itertools.combinations(methods,2):
            paired=[r for r in selected if all(finite(r['methods'].get(m)) for m in (a,b))]
            diff=paired_method_auc_difference(paired,a,b);diff['paired_clips']=len(paired)
            pairs[split+'/'+a+'_vs_'+b]=diff
        result[split]=dict(methods=reports,permutations=nulls)
    return dict(task_splits=result,paired_auc_differences=holm(pairs))


def icc1(groups):
    """One-way random single-measure ICC(1,1), unequal-count ANOVA k0."""
    groups=[np.asarray(g,float) for g in groups if len(g)>=2]
    n=len(groups);N=sum(map(len,groups))
    if n<2 or N<=n:return dict(icc=None,subjects=n,observations=N)
    grand=np.concatenate(groups).mean()
    msb=sum(len(g)*(g.mean()-grand)**2 for g in groups)/(n-1)
    msw=sum(np.sum((g-g.mean())**2) for g in groups)/(N-n)
    k0=(N-sum(len(g)**2 for g in groups)/N)/(n-1)
    between=(msb-msw)/k0;den=between+msw
    return dict(icc=float(between/den) if den>0 else None,between_variance=float(between),
                within_variance=float(msw),subjects=n,observations=N,effective_repeats=k0,
                note='Untruncated ICC(1,1); negative estimates are retained, not interpreted as a negative physical variance.')


def confounds(records):
    rests=[r for r in records if r['task']=='T1']
    out={};subject_rows=[]
    for m in ('D0','D1'):
        # Same complete-case subjects/clips for an interpretable ICC comparison.
        paired=[r for r in rests if all(finite(r['indices'].get(k)) for k in ('D0','D1'))]
        out[m]=icc1([[r['indices'][m] for r in paired if r['subject_id']==s]
                     for s in sorted({r['subject_id'] for r in paired})])
    for subject in sorted({r['subject_id'] for r in rests}):
        rows=[r for r in rests if r['subject_id']==subject and finite(r['indices'].get('D0')) and r.get('raw_features')]
        if rows:
            subject_rows.append(dict(subject_id=subject,D0=float(np.mean([r['indices']['D0'] for r in rows])),
                geometry={k:float(np.mean([r['raw_features'][k] for r in rows])) for k in rows[0]['raw_features']}))
    correlations={}
    for k in ('brow_furrow','lip_press','lip_corner','jaw_clench'):
        x=[r['geometry'][k] for r in subject_rows];y=[r['D0'] for r in subject_rows]
        corr=spearmanr(x,y) if len(x)>=3 and np.std(x)>0 and np.std(y)>0 else None
        correlations[k]=dict(r=float(corr.statistic) if corr else None,p=float(corr.pvalue) if corr else None,n_subjects=len(x))
    return dict(icc=out,spearman=correlations,subject_means=subject_rows)


def stress_effect(records,method,task):
    differences=[]
    for s in sorted({r['subject_id'] for r in records}):
        a=[r['indices'][method] for r in records if r['subject_id']==s and r['task']=='T1' and finite(r['indices'].get(method))]
        b=[r['indices'][method] for r in records if r['subject_id']==s and r['task']==task and finite(r['indices'].get(method))]
        if a and b:differences.append(np.mean(a)-np.mean(b))
    return float(np.mean(differences)) if differences else None


def nuisance_summary(records):
    result={}
    for m in ('D0','D1'):
        effects={t:stress_effect(records,m,t) for t in ('T2','T3')}
        shifts={}
        for name in NUISANCES:
            pairs=[r for r in records if finite(r['indices'].get(m)) and finite(r.get('nuisances',{}).get(name,{}).get(m))]
            by_subject=[];signed=[]
            for s in sorted({r['subject_id'] for r in pairs}):
                d=[r['nuisances'][name][m]-r['indices'][m] for r in pairs if r['subject_id']==s]
                by_subject.append(float(np.mean(np.abs(d))));signed.append(float(np.mean(d)))
            shift=float(np.mean(by_subject)) if by_subject else None
            shifts[name]=dict(mean_absolute_shift=shift,mean_signed_shift=float(np.mean(signed)) if signed else None,
                max_absolute_shift=max((abs(r['nuisances'][name][m]-r['indices'][m]) for r in pairs),default=None),
                paired_clips=len(pairs),original_accepted_clips=sum(finite(r['indices'].get(m)) for r in records),
                retention_percent=100*len(pairs)/max(1,sum(finite(r['indices'].get(m)) for r in records)),
                shift_to_stress_effect={t:shift/abs(e) if shift is not None and e is not None and abs(e)>0 else None for t,e in effects.items()})
        result[m]=dict(stress_effect_index_points=effects,perturbations=shifts,
                      definition='Equal-subject mean absolute paired index shift; stress effect = subject mean(rest minus task), in index points, not standardized d_z. Failed perturbed clips are reported separately.')
    return result


def decision(task_splits,nuisance,method='D0'):
    criteria={}
    for task in ('T1_vs_T2','T1_vs_T3'):
        ci=task_splits.get(task,{}).get('methods',{}).get(method,{}).get('within_subject_auc',{}).get('ci95')
        ok=bool(ci and ci[0] is not None and ci[0]>.60)
        criteria[task+'_within_subject_auc']=dict(pass_=ok,value=ci,rule='lower 95% CI > 0.60',reason=None if ci else 'missing paired-subject evidence')
    data=nuisance.get(method,{})
    for name in NUISANCES:
        entry=data.get('perturbations',{}).get(name,{})
        for task in ('T2','T3'):
            ratio=entry.get('shift_to_stress_effect',{}).get(task)
            # No PASS by dropping every difficult perturbed clip. Complete paired
            # retention is predeclared as required evidence for this criterion.
            retained=entry.get('paired_clips',0)==entry.get('original_accepted_clips',-1) and entry.get('paired_clips',0)>0
            ok=finite(ratio) and ratio<.5 and retained
            criteria[name+'_vs_'+task]=dict(pass_=bool(ok),value=ratio,rule='absolute shift < 0.5 × absolute stress effect, with complete paired evidence',
                reason=None if retained and finite(ratio) else 'missing shift/effect or rejected perturbed clips')
    return dict(status='PASS' if all(v['pass_'] for v in criteria.values()) else 'FAIL',method=method,criteria=criteria)
