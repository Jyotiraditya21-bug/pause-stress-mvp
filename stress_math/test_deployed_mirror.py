import json, math, subprocess, unittest
from pathlib import Path
import numpy as np
from . import deployed_mirror as py
ROOT=Path(__file__).resolve().parents[1]
class DeployedMirrorParity(unittest.TestCase):
    def fixture(self):
        base=py.reference_points()
        pixels=np.zeros((48,64,4),dtype=np.uint8);pixels[:,:,:3]=80;pixels[:,:,3]=255;pixels[12:36,16:48,:3]=120
        frames=[]
        for variant in (0.,.004,.008):
            p=base.copy();p[107,0]+=variant;p[336,0]-=variant/2;frames.append(p)
        seq=[]
        for i in range(100):
            t=i/10;p=frames[0] if t<4 else frames[1] if t<7 else frames[2]
            seq.append(dict(time=t,points=(p/[64,48]).tolist(),pose=[0,0,0],good=True,brightness=120.))
        matrix=[math.cos(math.radians(20)),0,-math.sin(math.radians(20)),0,0,1,0,0,math.sin(math.radians(20)),0,math.cos(math.radians(20)),0,0,0,0,1]
        stats={k:dict(median=float(py.geometry(base)[k]),mad=float(py.SPREADS[k]/1.4826)) for k in py.BASELINE_KEYS}
        common=dict(points=[[.25,.25],[.75,.75]],width=64,height=48,faceCount=1,pixels=pixels.reshape(-1).tolist(),previous=None,poseMatrix=dict(rows=4,columns=4,data=matrix),scan=seq)
        return [dict(common,mode='generic'),dict(common,mode='baseline',baseline=dict(algoVersion=py.ALGO_VERSION,features=stats))],frames
    def test_javascript_and_python_match_frontend_fixtures(self):
        fixtures,frames=self.fixture()
        js=subprocess.run(['node',str(ROOT/'stress_math/js_deployed_parity.mjs')],input=json.dumps(fixtures),text=True,capture_output=True,check=True)
        actuals=json.loads(js.stdout)
        points=[dict(x=.25,y=.25),dict(x=.75,y=.75)];brightness=py.face_brightness(fixtures[0]['pixels'],64,48,points)
        for fixture,actual in zip(fixtures,actuals):
            quality=py.assess_quick_frame(points,1,brightness);scan=py.QuickIndex(fixture.get('baseline'),fixture['mode'])
            pose=py.head_pose(fixture['poseMatrix'])
            for row in fixture['scan']:scan.update(row['time'],np.asarray(row['points'])*[64,48],row['pose'],row['good'],dict(brightness=row['brightness']))
            result=scan.finish();geom=py.geometry(frames[0])
            self.assertAlmostEqual(actual['brightness'],brightness,delta=1e-6);self.assertEqual(actual['quality']['good'],quality['good'])
            for a,b in zip(actual['pose'],pose):self.assertAlmostEqual(a,b,delta=1e-6)
            for key in ('ear','mar','lip_press','brow_furrow','lip_corner','jaw_clench'):self.assertAlmostEqual(actual['geometry'][key],geom[key],delta=1e-6)
            self.assertEqual(actual['result']['mode'],result['mode']);self.assertEqual(actual['result']['algoVersion'],result['algoVersion'])
            self.assertAlmostEqual(actual['result']['coveragePercent'],result['coveragePercent'],delta=1e-6);self.assertEqual(actual['result']['quality'],result['quality'])
            if result['average'] is not None:
                self.assertAlmostEqual(actual['result']['average'],result['average'],delta=1e-6)
                for a,b in zip(actual['result']['range'],result['range']):self.assertAlmostEqual(a,b,delta=1e-6)
            for a,b in zip(actual['result']['points'],result['points']):
                self.assertEqual(a['time'],b['time'])
                if a['value'] is not None:self.assertAlmostEqual(a['value'],b['value'],delta=1e-6)
if __name__=='__main__':unittest.main()
