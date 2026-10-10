"""Optional inference-only HF comparators. Heavy dependencies are lazy imports."""
import hashlib
import json
import re
import time
import tempfile
from pathlib import Path
import numpy as np

MODEL_A = 'TheBgGirl/fer-stress-vit'
MODEL_B = 'HardlyHumans/Facial-expression-detection'
SAMPLE_FPS = 5.
MARGIN = .15
TARGETS = {'stress': ('stressed',), 'emotion': ('anger','fear','sad','disgust')}


def target_indices(id2label, mode):
    if mode not in TARGETS: raise ValueError('mode must be stress or emotion')
    labels = {int(i):str(label).strip().lower() for i,label in id2label.items()}
    selected=[]
    for target in TARGETS[mode]:
        matches=[i for i,label in labels.items() if label==target]
        if len(matches)!=1: raise ValueError(f'Expected exactly one {target!r} label in id2label, found {labels}')
        selected.extend(matches)
    return selected


def sample_indices(times):
    """First decoded frame in each 200ms bucket; never synthesize extra frames."""
    times=np.asarray(times,float)
    if times.ndim!=1: raise ValueError('Video timestamps must be a one-dimensional array')
    if not len(times): return np.array([],dtype=int)
    if not np.isfinite(times).all() or np.any(np.diff(times)<=0): raise ValueError('Video timestamps must be finite and strictly increasing')
    buckets=np.floor(times*SAMPLE_FPS+1e-8).astype(np.int64)
    return np.flatnonzero(np.r_[True,np.diff(buckets)>0])


def face_crop(frame,landmarks):
    import cv2
    p=np.asarray(landmarks,float)
    if p.ndim!=2 or len(p)<3 or not np.isfinite(p[:,:2]).all(): return None
    h,w=frame.shape[:2]; lo=p[:,:2].min(axis=0); hi=p[:,:2].max(axis=0)
    extent=hi-lo
    if np.any(extent<2): return None
    lo=np.floor(lo-MARGIN*extent).astype(int); hi=np.ceil(hi+MARGIN*extent).astype(int)
    x0,y0=max(0,lo[0]),max(0,lo[1]); x1,y1=min(w,hi[0]),min(h,hi[1])
    if x1<=x0 or y1<=y0: return None
    return cv2.cvtColor(frame[y0:y1,x0:x1],cv2.COLOR_BGR2RGB)


class HFModel:
    def __init__(self,name,mode,revision=None,cache_dir=None,batch_size=8):
        if mode not in TARGETS: raise ValueError('Invalid comparator mode')
        if batch_size<1: raise ValueError('batch_size must be positive')
        self.name=name; self.mode=mode; self.revision=revision
        self.cache_dir=str(cache_dir) if cache_dir else None; self.batch_size=batch_size
        self._metadata=None; self._model=None; self._processor=None; self._torch=None; self.device=None
        self.load_ms=0.

    @property
    def metadata(self):
        if self._metadata is not None: return self._metadata
        from huggingface_hub import HfApi, hf_hub_download
        info=HfApi().model_info(self.name,revision=self.revision)
        sha=info.sha
        if not sha: raise RuntimeError('Hub returned no immutable revision hash')
        card=info.card_data.to_dict() if hasattr(info.card_data,'to_dict') else (info.card_data or {})
        files=[s.rfilename for s in info.siblings]
        license_files=[f for f in files if Path(f).name.upper().startswith(('LICENSE','COPYING')) and Path(f).suffix.lower() in ('','.txt','.md','.rst')]
        documents=[]
        for filename in license_files:
            path=hf_hub_download(self.name,filename,revision=sha,cache_dir=self.cache_dir)
            documents.append({'file':filename,'text':Path(path).read_text(errors='replace')})
        declared=card.get('license')
        card_license=[]
        if 'README.md' in files:
            path=hf_hub_download(self.name,'README.md',revision=sha,cache_dir=self.cache_dir)
            text=Path(path).read_text(errors='replace')
            card_license=[line.strip() for line in text.splitlines() if re.search(r'\blicen[sc]e\s*:',line,re.I)]
            if not declared and card_license:
                declared=re.sub(r'^.*?licen[sc]e\s*:\s*','',card_license[0],flags=re.I).strip().strip('* _`')
        safetensors=info.safetensors
        params=safetensors.get('total') if isinstance(safetensors,dict) else getattr(safetensors,'total',None)
        self._metadata={'model_name':self.name,'revision_hash':sha,'requested_revision':self.revision or 'main',
                        'params_count':params,'params_source':'Hub safetensors metadata' if params is not None else 'unavailable until load',
                        'license_id':declared,'license_text':'\n\n'.join(d['text'] for d in documents) if documents else ('\n'.join(card_license) or None),
                        'license_documents':documents,
                        'license_status':'full repository license text' if documents else ('model-card declaration only; full license text absent' if declared else 'not documented'),
                        'model_url':f'https://huggingface.co/{self.name}/tree/{sha}',
                        'third_party_pretrained':True,'trained_by_us':False,'dtype':'float32','device':None}
        return self._metadata

    def load_processor(self):
        from transformers import AutoImageProcessor
        metadata=self.metadata
        try:
            return AutoImageProcessor.from_pretrained(self.name,revision=metadata['revision_hash'],cache_dir=self.cache_dir,trust_remote_code=False,use_fast=False)
        except ValueError:
            # HF model B serialized the deprecated ViTFeatureExtractor alias.
            # Transformers 4.41 defines it as a subclass of ViTImageProcessor.
            from huggingface_hub import hf_hub_download
            filename=hf_hub_download(self.name,'preprocessor_config.json',revision=metadata['revision_hash'],cache_dir=self.cache_dir)
            params=json.loads(Path(filename).read_text())
            if params.get('image_processor_type')!='ViTFeatureExtractor': raise
            params['image_processor_type']='ViTImageProcessor'
            compatibility={'legacy_class_alias':'ViTFeatureExtractor -> ViTImageProcessor','settings_preserved':True}
            if isinstance(params.get('do_resize'),str):
                compatibility['legacy_resize_flag']=params['do_resize']
                params['do_resize']=bool(params['do_resize'])
            config=hf_hub_download(self.name,'config.json',revision=metadata['revision_hash'],cache_dir=self.cache_dir)
            with tempfile.TemporaryDirectory(prefix='pause-processor-alias-') as folder:
                Path(folder,'preprocessor_config.json').write_text(json.dumps(params))
                Path(folder,'config.json').write_text(Path(config).read_text())
                processor=AutoImageProcessor.from_pretrained(folder,local_files_only=True,trust_remote_code=False,use_fast=False)
            self._metadata['processor_compatibility']=compatibility
            return processor

    def load(self):
        if self._model is not None: return
        import torch
        from transformers import AutoModelForImageClassification
        metadata=self.metadata; tick=time.perf_counter()
        self._torch=torch
        torch.manual_seed(42)
        self.device='mps' if torch.backends.mps.is_available() else 'cpu'
        self._processor=self.load_processor()
        model,loading=AutoModelForImageClassification.from_pretrained(self.name,revision=metadata['revision_hash'],cache_dir=self.cache_dir,trust_remote_code=False,use_safetensors=True,torch_dtype=torch.float32,output_loading_info=True)
        if loading.get('missing_keys') or loading.get('mismatched_keys') or loading.get('error_msgs'):
            raise RuntimeError('Incomplete pretrained checkpoint; refusing randomly initialized/mismatched prediction weights: '+str(loading))
        target_indices(model.config.id2label,self.mode)
        self._model=model.to(device=self.device,dtype=torch.float32).eval().requires_grad_(False)
        self._metadata.update(params_count=sum(p.numel() for p in self._model.parameters()),params_source='loaded model parameter count',device=self.device,id2label={str(k):v for k,v in self._model.config.id2label.items()})
        self.load_ms=(time.perf_counter()-tick)*1000

    def sync(self):
        if self.device=='mps' and self._torch is not None: self._torch.mps.synchronize()

    def score_images(self,images):
        if not len(images): return np.array([],float)
        self.load()
        from PIL import Image
        prepared=[image.convert('RGB') if isinstance(image,Image.Image) else Image.fromarray(np.asarray(image,dtype=np.uint8)).convert('RGB') for image in images]
        torch=self._torch; selected=target_indices(self._model.config.id2label,self.mode); scores=[]
        for offset in range(0,len(prepared),self.batch_size):
            inputs=self._processor(images=prepared[offset:offset+self.batch_size],return_tensors='pt')
            inputs={k:v.to(device=self.device,dtype=torch.float32 if v.is_floating_point() else v.dtype) for k,v in inputs.items()}
            with torch.no_grad():
                logits=self._model(**inputs).logits.float()
                if logits.ndim!=2 or max(selected)>=logits.shape[1]: raise ValueError('Logit shape disagrees with id2label')
                probabilities=torch.softmax(logits,dim=-1)
                scores.extend(probabilities[:,selected].sum(dim=1).detach().cpu().numpy().tolist())
        result=np.asarray(scores,float)
        if not np.isfinite(result).all(): raise ValueError('Model emitted non-finite probabilities')
        return result

    def score_video(self,path,landmark_data,cache):
        """One probability per sampled frame; missing crops remain NaN, no filling."""
        import cv2
        from .video import SOURCE_HASH
        path=Path(path); stat=path.stat(); metadata=self.metadata
        times=np.asarray(landmark_data['times'],float); indices=sample_indices(times)
        fingerprint={'path':str(path.resolve()),'size':stat.st_size,'mtime_ns':stat.st_mtime_ns,
                     'landmark_source':SOURCE_HASH,'hf_source':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                     'timestamps':hashlib.sha256(times.tobytes()).hexdigest(),
                     'landmark_values':hashlib.sha256(np.asarray(landmark_data['landmarks']).tobytes()).hexdigest(),
                     'model':self.name,'revision':metadata['revision_hash'],'mode':self.mode,'fps':5,'margin':MARGIN,'dtype':'float32','batch_size':self.batch_size}
        key=hashlib.sha256(json.dumps(fingerprint,sort_keys=True).encode()).hexdigest()
        cache=Path(cache); cache.mkdir(parents=True,exist_ok=True); target=cache/(key+'.npz')
        if target.exists():
            with np.load(target,allow_pickle=False) as saved:
                self._metadata.update(json.loads(str(saved['metadata'])))
                return {k:saved[k].copy() for k in ('indices','times','scores','ms_per_sample','ms_per_decoded_frame','crop_decode_ms_per_sample')} | {'cached':True}
        cap=cv2.VideoCapture(str(path))
        if not cap.isOpened(): cap.release(); raise ValueError(f'Cannot decode {path}')
        scores=np.full(len(indices),np.nan); crops=[]; positions=[]; lookup={int(index):n for n,index in enumerate(indices)}
        frame_index=0; inference_ms=0.; crop_decode_ms=0.; processed=0
        def flush():
            nonlocal inference_ms,processed
            if not crops: return
            self.load();self.sync(); tick=time.perf_counter()
            values=self.score_images(crops);self.sync();inference_ms+=(time.perf_counter()-tick)*1000
            scores[positions]=values;processed+=len(crops);crops.clear();positions.clear()
        try:
            while True:
                tick=time.perf_counter(); ok,frame=cap.read();crop_decode_ms+=(time.perf_counter()-tick)*1000
                if not ok: break
                if frame_index in lookup:
                    tick=time.perf_counter(); crop=face_crop(frame,landmark_data['landmarks'][frame_index]);crop_decode_ms+=(time.perf_counter()-tick)*1000
                    if crop is not None: crops.append(crop);positions.append(lookup[frame_index])
                    if len(crops)>=self.batch_size: flush()
                frame_index+=1
            if frame_index!=len(times): raise ValueError('Decoded frame count differs from landmark cache')
            flush()
        finally: cap.release()
        denominator=max(len(indices),1)
        data={'indices':indices,'times':times[indices],'scores':scores,
              'ms_per_sample':np.array(inference_ms/denominator),
              'ms_per_decoded_frame':np.array(inference_ms/max(len(times),1)),
              'crop_decode_ms_per_sample':np.array(crop_decode_ms/denominator)}
        np.savez_compressed(target,**data,metadata=np.array(json.dumps(self.metadata)),processed=np.array(processed))
        return data | {'cached':False}


def main():
    import argparse
    p=argparse.ArgumentParser(description='Inference-only dummy-image smoke test of requested pretrained models')
    p.add_argument('--smoke-test',action='store_true');p.add_argument('--model',choices=['A','B','both'],default='both');p.add_argument('--cache',default='stress_math/cache/hf_weights')
    args=p.parse_args()
    if not args.smoke_test: p.error('Use --smoke-test to run pretrained inference on a dummy RGB image')
    from PIL import Image
    image=Image.new('RGB',(224,224),(128,128,128))
    for letter,name,mode in [('A',MODEL_A,'stress'),('B',MODEL_B,'emotion')]:
        if args.model not in (letter,'both'): continue
        model=HFModel(name,mode,cache_dir=args.cache)
        value=model.score_images([image])[0]
        print(json.dumps({'model':name,'dummy_image_score':float(value),'metadata':model.metadata},indent=2))
        del model

if __name__=='__main__': main()
