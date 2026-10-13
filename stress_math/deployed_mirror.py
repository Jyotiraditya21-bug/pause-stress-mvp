"""Exact numerical port of the deployed QuickIndex and acquisition/reliability rules.

No fitting, detector imports, or changes to the frontend. Input points to geometry
are pixel coordinates; input points to assess_frame are normalized coordinates.
"""
import json
import math
from pathlib import Path
import numpy as np

FRONTEND = Path(__file__).resolve().parents[1] / 'frontend/src'
CANONICAL = json.loads((FRONTEND / 'faceReference.json').read_text())
KEYS = ('brow_furrow', 'lip_press', 'lip_corner', 'jaw_clench')
SPREADS = dict(zip(KEYS, (.06, .04, .06, .08)))
SCAN_RULES = dict(duration=10, settling=1, slotSeconds=.2, minCoverage=.8,
                  minWindows=8, maxScoreSpread=1, maxHalfDifference=.75,
                  maxPoseSpan=6, maxBrightnessSpan=30)


def finite(v):
    return isinstance(v, (float, int, np.number)) and not isinstance(v, (bool, np.bool_)) and math.isfinite(v)


def median(a):
    return float(np.median(a)) if len(a) else None


def span(a):
    return float(np.quantile(a, .9) - np.quantile(a, .1))


def reference_points():
    p = np.zeros((478, 2))
    p[CANONICAL['indices']] = CANONICAL['reference']
    return p


def normalize(points):
    p = np.asarray(points, float)
    ids = CANONICAL['indices']
    if len(p) < 478 or not np.isfinite(p[ids]).all():
        raise ValueError('Incomplete landmarks')
    centre = p[ids, :2].mean(axis=0)
    ref = np.asarray(CANONICAL['reference'], float)
    x = p[ids, :2] - centre
    y = ref - ref.mean(axis=0)
    dot = float(np.sum(x[:, 0]*y[:, 0] + x[:, 1]*y[:, 1]))
    cross = float(np.sum(x[:, 0]*y[:, 1] - x[:, 1]*y[:, 0]))
    angle = math.atan2(cross, dot)
    c, s = math.cos(angle), math.sin(angle)
    scale = float(np.linalg.norm(p[33, :2] - p[263, :2]))
    if scale < 1e-8:
        raise ValueError('Degenerate face geometry')
    return (p[:, :2]-centre) @ np.array([[c, s], [-s, c]]) / scale


def geometry(points):
    p = normalize(points)
    def d(a, b): return float(np.linalg.norm(p[a]-p[b]))
    def ear(a,b,c,e,f,g): return (d(b,g)+d(c,f))/(2*max(d(a,e),1e-8))
    width = max(d(61,291), 1e-8)
    down = np.array([-(p[263,1]-p[33,1]), p[263,0]-p[33,0]])
    down /= np.linalg.norm(down)
    if (p[152]-p[10]) @ down < 0: down = -down
    corner = (p[61]+p[291]-p[13]-p[14])/2
    return dict(ear=(ear(33,160,158,133,153,144)+ear(362,385,387,263,373,380))/2,
                mar=d(13,14)/width, lip_press=-(d(0,13)+d(14,17))/width,
                brow_furrow=-(d(107,336)+(d(105,158)+d(334,385))/2),
                lip_corner=math.atan2(float(corner@down),width/2),
                jaw_clench=d(234,454)/max(d(10,152),1e-8))


def head_pose(matrix):
    if not matrix or matrix.get('rows') != 4 or matrix.get('columns') != 4: return None
    d = matrix.get('data', [])
    if len(d) != 16 or not all(map(finite,d)): return None
    scale = math.hypot(*d[:3])
    if scale < 1e-8: return None
    return [math.degrees(math.atan2(d[6],d[10])),
            math.degrees(math.asin(max(-1,min(1,-d[2]/scale)))),
            math.degrees(math.atan2(d[1],d[0]))]


def assess_frame(points, face_count, brightness, previous=None):
    if face_count != 1 or not len(points):
        return dict(good=False, reason='Only one person should be in view.' if face_count>1 else 'Position your face inside the camera view.')
    p = np.array([[v['x'],v['y']] if isinstance(v,dict) else v[:2] for v in points])
    low, high = p.min(axis=0), p.max(axis=0)
    width, height = high-low
    x,y = (high+low)/2
    center = dict(x=float(x),y=float(y))
    reason = ''
    if brightness < 18: reason='Add more light in front of your face.'
    elif brightness > 240: reason='Reduce bright light or backlighting.'
    elif width < .15 or height < .20: reason='Move closer to the camera.'
    elif width > .85 or height > .95: reason='Move a little farther from the camera.'
    elif abs(x-.5) > .24 or abs(y-.5) > .24: reason='Move your face toward the centre.'
    movement = math.hypot(x-previous['x'],y-previous['y']) if previous else 0.
    if not reason and movement > .05: reason='Hold still for a clearer reading.'
    return dict(good=not reason, reason=reason or 'Good framing. Keep still and look toward the camera.',center=center,movement=movement)


def assess_quick_frame(points, face_count, brightness, previous=None):
    if not finite(brightness): return dict(good=False,reason='Position your face inside the circle.')
    # The extra quick checks in JS have identical thresholds and are unreachable
    # after assessFrame has passed. Preserve its exact output/reason.
    return assess_frame(points,face_count,brightness,previous)


def face_brightness(pixels,width,height,points):
    if not len(points): return float('nan')
    p=np.array([[v['x'],v['y']] if isinstance(v,dict) else v[:2] for v in points])
    if not np.isfinite(p).all(): return float('nan')
    x0,y0=np.maximum(0,np.floor(p.min(axis=0)*[width,height])).astype(int)
    x1,y1=np.minimum([width,height],np.ceil(p.max(axis=0)*[width,height])).astype(int)
    patch=np.asarray(pixels).reshape(height,width,4)[y0:y1,x0:x1,:3]
    return float(patch.mean()) if patch.size else float('nan')


def reference_rows():
    g=geometry(reference_points())
    return [{k:g[k]+f*SPREADS[k] for k in KEYS} for f in (0,1,-1,.5,-.5)]


def score_row(row,baseline):
    """Fresh FixedIndex per window, exactly as QuickIndex's callback."""
    z=[]
    for k in KEYS:
        a=[r[k] for r in baseline if finite(r.get(k))]
        if len(a)>=5 and finite(row.get(k)):
            mu=float(np.mean(a)); sigma=max(float(np.std(a)),.05*abs(mu)+.001)
            z.append(max(-3,min(3,(row[k]-mu)/(sigma+1e-6))))
    if row.get('gated') or not z: return None
    r=sum(z)/math.sqrt(len(z))
    return (100-100/(1+math.exp(-r)))/10


class ScanReliability:
    def __init__(self,keys=KEYS,score=None):
        self.keys=keys; self.score=score or (lambda r:score_row(r,reference_rows()))
        self.slots={}; self.last_time=-math.inf; self.feature_rows=[]

    def add(self,time,row,context=None):
        if not finite(time) or time<=self.last_time or time<0 or time>=10: return False
        self.last_time=time
        if time<1: return False
        slot=min(44,math.floor((time-1)/.2+1e-8))
        sample=(row,context or {}) if row and all(finite(row.get(k)) for k in self.keys) else None
        self.slots.setdefault(slot,[]).append(sample)
        return True

    def usable_slots(self):
        slots={}
        for i,samples in self.slots.items():
            valid=[s for s in samples if s is not None]
            if not valid: continue
            row={k:median([s[0][k] for s in valid]) for k in self.keys}
            context={}
            for k in ('pitch','yaw','brightness'):
                a=[s[1][k] for s in valid if finite(s[1].get(k))]
                if a:context[k]=median(a)
            slots[i]=(row,context)
        return slots

    def finish(self):
        slots=self.usable_slots(); points=[]; contexts=[]; rows=[]
        for window in range(9):
            block=[slots[i] for i in range(window*5,(window+1)*5) if i in slots]
            value=None
            if len(block)>=2:
                row={k:median([b[0][k] for b in block]) for k in self.keys}
                value=self.score(dict(row,time=window+1.5)); rows.append(row)
            contexts.extend(b[1] for b in block)
            points.append(dict(time=window+1.5,value=value))
        self.feature_rows=rows
        values=[p['value'] for p in points if finite(p['value'])]
        coverage=len(slots)/45
        first=[p['value'] for p in points[:4] if finite(p['value'])]
        last=[p['value'] for p in points[5:] if finite(p['value'])]
        spread=span(values) if values else None
        half=abs(median(first)-median(last)) if first and last else None
        centre=median(values)
        consistent=[p for p in points if finite(p['value']) and abs(p['value']-centre)<=1]
        early=[p['value'] for p in consistent if p['time']<5]
        late=[p['value'] for p in consistent if p['time']>=6]
        difference=abs(median(early)-median(late)) if early and late else None
        fatal=''; warning=''
        if coverage<.35 or len(values)<3:
            fatal='Not enough clear camera signal. Keep your face inside the circle for the full scan and retry.'
        elif not first or not last:
            fatal='Your face was not visible throughout the scan. Keep it inside the circle and retry.'
        elif len(consistent)<max(3,math.ceil(len(values)*.6)) or difference is None or difference>.75:
            fatal='The scan contained conflicting readings. Keep your face still and retry.'
        else:
            warnings=[]
            if coverage<.8 or len(values)<8:warnings.append('Some camera frames were unclear.')
            if len(consistent)<len(values):warnings.append('Brief unusual readings were filtered out.')
            for k in ('pitch','yaw','brightness'):
                a=[c[k] for c in contexts if finite(c.get(k))]
                if a and span(a)>(30 if k=='brightness' else 6):
                    warnings.append('Lighting varied during the scan.' if k=='brightness' else 'Head position varied during the scan.')
            if warnings:warning=' '.join(warnings)+' Treat this estimate with lower confidence.'
        return dict(quality='poor' if fatal else 'limited' if warning else 'good',reason=fatal or warning,
            average=None if fatal else median([p['value'] for p in consistent]),latest=None if fatal else points[-1]['value'],
            points=points,coveragePercent=100*coverage,
            features={k:median([r[k] for r in rows]) for k in self.keys} if rows else None,
            reliability=dict(usableSlots=len(slots),totalSlots=45,usableWindows=len(values),totalWindows=9,
                scoreSpread=spread,halfDifference=half,consistentWindows=len(consistent),consensusHalfDifference=difference,ruleVersion='window-quality-v2'))


class QuickIndex:
    def __init__(self,baseline=None):
        self.reference=reference_rows() if baseline is None else baseline
        self.measurements=ScanReliability(KEYS,lambda row:score_row(row,self.reference))
        self.rejections={}

    def update(self,time,points,pose,quality_good,context=None):
        context=context or {}; row=None; reason=''
        facing=pose is None or (all(map(finite,pose)) and abs(pose[0])<=38 and abs(pose[1])<=30)
        if quality_good and facing:
            try:
                row=dict(geometry(points),time=time)
                if row['mar']>.32:row=None;reason='Keep your mouth relaxed and avoid speaking.'
            except (ValueError,IndexError,TypeError,FloatingPointError):row=None
        elif quality_good:reason='Face straight ahead for a repeatable scan.'
        if row is None and time>=1:
            reason=reason or context.get('qualityReason') or 'The face could not be tracked clearly.'
            self.rejections[reason]=self.rejections.get(reason,0)+1
        self.measurements.add(time,row,dict(context,pitch=pose[0] if pose is not None else None,yaw=pose[1] if pose is not None else None))
        return dict(value=None,phase='live',valid=row is not None,reason=reason)

    def finish(self):
        result=self.measurements.finish()
        result['reliability']['rejectionReasons']=dict(self.rejections)
        if result['average'] is None and result['reason'].startswith('Not enough clear') and self.rejections:
            result['reason']=max(self.rejections,key=self.rejections.get)+' Then retry the 10-second scan.'
        return result
