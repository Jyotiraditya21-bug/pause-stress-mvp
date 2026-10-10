import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
from .hf_models import HFModel,target_indices,sample_indices,face_crop
from .hf_evaluate import calibrate,zscore,fuse,grouped,run
from .metrics import paired_method_auc_difference,method_correlations


class ComparatorTests(unittest.TestCase):
    def test_lazy_import(self):
        code="import sys;import stress_math.hf_models;assert not any(k in sys.modules for k in ('torch','transformers','huggingface_hub'));print('lazy')"
        p=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,check=True)
        self.assertEqual(p.stdout.strip(),'lazy')

    def test_labels_are_read_from_config_not_fixed_indices(self):
        self.assertEqual(target_indices({'0':'Stressed','1':'not_stressed'},'stress'),[0])
        self.assertEqual(target_indices({7:'anger',2:'fear',5:'sad',0:'disgust',1:'happy'},'emotion'),[7,2,5,0])
        with self.assertRaises(ValueError):target_indices({0:'LABEL_0',1:'LABEL_1'},'stress')
        with self.assertRaises(ValueError):target_indices({0:'stressed',1:'Stressed'},'stress')

    def test_revision_metadata_and_license_declaration(self):
        from types import ModuleType
        hub=ModuleType('huggingface_hub')
        info=SimpleNamespace(sha='immutable-sha',card_data={},siblings=[SimpleNamespace(rfilename='README.md')],safetensors=SimpleNamespace(total=123))
        hub.HfApi=lambda:SimpleNamespace(model_info=lambda *args,**kwargs:info)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder,'README.md');path.write_text('- **License:** MIT')
            hub.hf_hub_download=lambda *args,**kwargs:str(path)
            with patch.dict(sys.modules,{'huggingface_hub':hub}):
                model=HFModel('dummy/model','stress')
                metadata=model.metadata
                self.assertEqual(metadata['revision_hash'],'immutable-sha')
                self.assertEqual(metadata['license_id'],'MIT')
                self.assertEqual(metadata['license_text'],'- **License:** MIT')
                self.assertEqual(metadata['params_count'],123)
                self.assertIn('full license text absent',metadata['license_status'])

    def test_sampling_and_rgb_face_crop(self):
        import cv2
        times=np.arange(60)/30
        self.assertEqual(len(sample_indices(times)),10)
        self.assertEqual(len(sample_indices(np.arange(4)/2)),4)
        frame=np.zeros((100,100,3),np.uint8);frame[:]=[10,20,30]
        points=np.array([[20,20],[60,20],[60,60],[20,60]],float)
        crop=face_crop(frame,points)
        self.assertEqual(crop.shape,(52,52,3))
        self.assertTrue(np.array_equal(crop[0,0],[30,20,10]))
        self.assertIsNone(face_crop(frame,points*np.nan))
        self.assertIsNone(face_crop(frame,np.array([[20,20],[20,20],[20,20]])))

    def test_sigma_floor_and_fixed_fusion(self):
        base=calibrate([.5]*6)
        self.assertAlmostEqual(base['sigma'],.026)
        self.assertEqual(zscore([.5,100,-100],base).tolist(),[0,3,-3])
        baselines={k:{'mu':0,'sigma':1,'raw_sigma':1} for k in ('M0','M1','M2')}
        values=fuse(np.array([2.]),np.array([-1.]),np.array([0.]),baselines)
        self.assertEqual(values['M0'][0],2)
        z0=2/1.000001;za=-1/1.000001
        self.assertAlmostEqual(values['M3'][0],100/(1+np.exp(-(z0+za)/3)))
        self.assertAlmostEqual(values['M4'][0],100/(1+np.exp(-(z0+za)/2)))
        self.assertAlmostEqual(values['M5'][0],100/(1+np.exp(-z0/2)))
        self.assertIsNone(calibrate([.5]*4))

    def test_subject_paired_auc_differences_and_agreement(self):
        records=[dict(subject_id=str(i),label=label,excluded=False,methods={'M0':20+60*label,'M1':20+60*label,'M2':80-60*label}) for i in range(4) for label in (0,1)]
        same=paired_method_auc_difference(records,'M1')
        self.assertEqual(same['auc_difference'],0)
        self.assertEqual(same['subject_bootstrap_95ci'],[0,0])
        worse=paired_method_auc_difference(records,'M2')
        self.assertEqual(worse['auc_difference'],-1)
        rho=method_correlations(records)
        self.assertAlmostEqual(rho['M0_vs_M1']['spearman_r'],1)
        self.assertAlmostEqual(rho['M0_vs_M2']['spearman_r'],-1)

    def test_per_video_score_cache_and_revision_invalidation(self):
        import cv2
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'dummy.avi'
            out=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'MJPG'),20,(64,64))
            self.assertTrue(out.isOpened())
            for _ in range(20):out.write(np.zeros((64,64,3),np.uint8))
            out.release()
            data={'times':np.arange(20)/20,'landmarks':np.tile([[10.,10.],[50.,10.],[50.,50.],[10.,50.]],(20,1,1))}
            model=HFModel('dummy/model','stress',batch_size=2)
            model._metadata={'model_name':'dummy/model','revision_hash':'first','license_text':None}
            calls=[]
            model.load=lambda:None
            model.score_images=lambda images:(calls.append(len(images)) or np.full(len(images),.7))
            a=model.score_video(path,data,Path(folder)/'scores')
            b=model.score_video(path,data,Path(folder)/'scores')
            self.assertFalse(a['cached']);self.assertTrue(b['cached'])
            self.assertEqual(len(a['scores']),5);self.assertEqual(sum(calls),5)
            self.assertTrue(np.array_equal(a['scores'],b['scores']))
            model._metadata['revision_hash']='second'
            model.score_video(path,data,Path(folder)/'scores')
            self.assertEqual(len(list((Path(folder)/'scores').glob('*.npz'))),2)

    @unittest.skipUnless(importlib.util.find_spec('torch') and importlib.util.find_spec('transformers'),'optional torch/transformers not installed')
    def test_dummy_image_real_processor_and_no_grad_fp32_batch(self):
        import torch
        from transformers import AutoImageProcessor
        from PIL import Image
        with tempfile.TemporaryDirectory() as folder:
            Path(folder,'config.json').write_text(json.dumps({'model_type':'vit'}))
            Path(folder,'preprocessor_config.json').write_text(json.dumps({'image_processor_type':'ViTImageProcessor','do_resize':True,'size':{'height':32,'width':32},'do_normalize':True,'image_mean':[.5]*3,'image_std':[.5]*3,'do_rescale':True,'rescale_factor':1/255}))
            processor=AutoImageProcessor.from_pretrained(folder,use_fast=False,local_files_only=True)
            for mode,labels in [('stress',{0:'stressed',1:'not_stressed'}),('emotion',{0:'fear',1:'neutral',2:'sad',3:'happy',4:'surprise',5:'contempt',6:'disgust',7:'anger'})]:
                class DummyModel(torch.nn.Module):
                    def __init__(self):
                        super().__init__();self.config=SimpleNamespace(id2label=labels)
                    def forward(self,pixel_values):
                        self.assertions=(not torch.is_grad_enabled(),pixel_values.dtype==torch.float32)
                        logits=torch.arange(len(labels),device=pixel_values.device,dtype=torch.float32).expand(len(pixel_values),-1)
                        return SimpleNamespace(logits=logits)
                model=HFModel('unit-test-only',mode,batch_size=2)
                model._model=DummyModel().eval();model._processor=processor;model._torch=torch;model.device='cpu'
                scores=model.score_images([Image.new('RGB',(64,64),(128,128,128)) for _ in range(5)])
                expected=torch.softmax(torch.arange(len(labels),dtype=torch.float32),dim=0)[target_indices(labels,mode)].sum().item()
                self.assertTrue(np.allclose(scores,expected));self.assertEqual(len(scores),5)
                self.assertEqual(model._model.assertions,(True,True))

    def test_optional_report_on_shared_synthetic_timeline(self):
        class FakeHF:
            def __init__(self,name,mode,*args):
                self.name=name;self.mode=mode;self._metadata={'model_name':name,'revision_hash':'unit-test-sha','license_text':None,'params_count':10}
            @property
            def metadata(self):return self._metadata
            def score_video(self,path,data,cache):
                ids=sample_indices(data['times']);t=data['times'][ids]
                scores=.2+.03*np.sin(t)+np.where(t>=25,.15,0)
                return {'indices':ids,'scores':scores,'ms_per_sample':np.array(1.),'crop_decode_ms_per_sample':np.array(.5),'cached':False}
        rows=[{'time':i/10,'ear':.3,'gated':False,**{k:.2+.03*np.sin(i/10)+(.02 if i>=250 else 0) for k in ('blink_rate','brow_furrow','lip_press','lip_corner','jaw_clench','jitter')}} for i in range(350)]
        sessions=[dict(video_path=f'synthetic-{i}.avi',subject_id='p',label=label,dataset='unit-test',condition=condition) for i,label,condition in [(0,0,'T1'),(1,1,'T2')]]
        with tempfile.TemporaryDirectory() as folder:
            args=Namespace(live=False,root=None,manifest=None,cache=folder,output=folder,hf_cache=None,hf_batch_size=2,hf_revision_a=None,hf_revision_b=None)
            with patch('stress_math.hf_evaluate.load',return_value=sessions),patch('stress_math.hf_evaluate.HFModel',FakeHF),patch('stress_math.evaluate.read_video',return_value={'times':np.arange(350)/10,'ms_frame':np.array(1.)}),patch('stress_math.hf_evaluate.features',return_value=rows):run(args)
            result=json.loads(Path(folder,'metrics.json').read_text())
            self.assertEqual(len(result['records']),2)
            self.assertEqual(result['method_params_count']['M3'],20)
            for method in ('M0','M1','M2','M3','M4','M5'):
                self.assertEqual(result['pooled']['methods'][method]['n'],2)
                self.assertEqual(len(result['pooled']['permutations'][method]['null_auc_distribution']),1000)
                self.assertEqual(result['records'][0]['method_coverage_percent'][method],100)
            self.assertEqual(result['models']['M1']['revision_hash'],'unit-test-sha')
            self.assertIn('license_text',result['models']['M2'])
            for filename in ('summary.md','report.md','comparison.md','roc_pretrained.png','permutation_null_auc.png'):
                self.assertTrue(Path(folder,filename).exists())
            text=Path(folder,'report.md').read_text()
            self.assertIn('train/test overlap with UBFC-Phys cannot be excluded',text)
            self.assertIn('Fusion weights are equal and fixed a priori',text)

if __name__=='__main__':unittest.main()
