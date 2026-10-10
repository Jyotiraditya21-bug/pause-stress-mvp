from pathlib import Path
import warnings
import pandas as pd

INSTRUCTIONS='UBFC-Phys: visit https://sites.google.com/view/ybenezeth/ubfc-phys, follow the access/license request on that page, download the authorized archive, extract it, then run --dataset ubfc_phys --root /path/to/extracted. Other datasets: obtain videos under their official access terms and supply --manifest sessions.csv.'

def load(root=None,manifest=None):
    rows=[]
    if manifest:
        path=Path(manifest)
        if not path.exists(): warnings.warn(f'Missing manifest: {path}. '+INSTRUCTIONS); return []
        table=pd.read_csv(path).fillna('')
        required={'video_path','subject_id','label','dataset'}
        if not required.issubset(table.columns): raise ValueError('Manifest requires '+', '.join(sorted(required)))
        for r in table.to_dict('records'):
            for key in ('video_path','baseline_video_path'):
                if r.get(key):
                    p=Path(str(r[key])).expanduser(); r[key]=str(p if p.is_absolute() else path.parent/p)
            rows.append(r)
    elif root and Path(root).exists():
        for p in sorted(Path(root).rglob('vid_s*_T*.avi')):
            subject,task=p.stem.removeprefix('vid_').split('_')
            baseline=p.with_name(f'vid_{subject}_T1.avi')
            rows.append(dict(video_path=str(p),subject_id=subject,label=int(task!='T1'),dataset='UBFC-Phys',baseline_video_path=str(baseline),condition=task,stressor_onset=0 if task!='T1' else ''))
    else: print(INSTRUCTIONS)
    valid=[]
    for r in rows:
        if not Path(r['video_path']).is_file(): warnings.warn(f"Missing video: {r['video_path']}"); continue
        if r.get('baseline_video_path') and not Path(r['baseline_video_path']).is_file():
            warnings.warn(f"Missing declared baseline: {r['baseline_video_path']}; skipping session"); continue
        valid.append(r)
    if not valid: print('No available videos. '+INSTRUCTIONS)
    return valid
