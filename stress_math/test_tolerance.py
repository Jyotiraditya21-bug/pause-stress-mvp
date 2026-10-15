import json,subprocess,unittest
from pathlib import Path
from .tolerant_scan import TolerantScan,frontalize,pose_weight,speed_weight,range_weight,weighted_median,adaptive_state

class ToleranceTests(unittest.TestCase):
    def assert_tree(self,a,b,path='result'):
        if isinstance(a,dict):
            self.assertEqual(set(a),set(b),path)
            for k in a:self.assert_tree(a[k],b[k],path+'.'+k)
        elif isinstance(a,list):
            self.assertEqual(len(a),len(b),path)
            for i,(x,y) in enumerate(zip(a,b)):self.assert_tree(x,y,path+f'[{i}]')
        elif isinstance(a,(float,int)) and not isinstance(a,bool):self.assertAlmostEqual(a,b,delta=1e-6,msg=path)
        else:self.assertEqual(a,b,path)
    def test_full_js_python_tolerant_parity(self):
        root=Path(__file__).resolve().parent
        payload=json.loads(subprocess.run(['node',str(root/'js_tolerance_parity.mjs')],capture_output=True,text=True,check=True).stdout)
        for entry in payload['output']:
            f=entry['fixture'];scan=TolerantScan(baseline=f['baseline'],frontalize3d=f['frontalize3d'])
            for r in f['frames']:scan.update(r['time'],r['points'],r['pose'],True,r['context'])
            self.assert_tree(entry['result'],scan.finish(len(f['frames'])/10),f['name'])
        r=payload['rotation'];points,applied=frontalize(r['points'],r['matrix'])
        self.assert_tree(r['result'],dict(points=points.tolist(),applied=applied),'rotation')
        probes=dict(pose=[pose_weight(p) for p in (None,[0,20,0],[0,30,0],[0,40,0],[0,45,0],[0,51,0])],speed=[speed_weight(v) for v in (0,.15,.4,.6,.8,1,1.1)],light=[range_weight(v,18,240,10) for v in (17,18,23,28,120,230,235,240,241)],median=weighted_median([None,1,5,9],[5,1,10,1]),adaptive=[adaptive_state(9,.8),adaptive_state(10,.3),adaptive_state(13,.6),adaptive_state(20,0)])
        self.assert_tree(payload['probes'],probes,'probes')

if __name__=='__main__':unittest.main()
