"""Predeclared tolerant acquisition policy. No fitted parameters or label inputs."""
import json
import math
from pathlib import Path
import numpy as np
from . import deployed_mirror as old

CONFIG=json.loads((old.FRONTEND/'toleranceConfig.json').read_text())
C=CONFIG
KEYS=tuple(C['features'])

def finite(v): return old.finite(v)
def median(a): return old.median(a)
def mad(a): return median([abs(v-median(a)) for v in a]) if a else None
def clamp(v): return max(0.,min(1.,v))

def weighted_median(values,weights):
    rows=sorted((float(v),float(w)) for v,w in zip(values,weights) if finite(v) and finite(w) and w>0)
    total=sum(w for _,w in rows);s=0.
    for i,(v,w) in enumerate(rows):
        s+=w
        if abs(s-total/2)<1e-12 and i+1<len(rows):return (v+rows[i+1][0])/2
        if s>=total/2:return v
    return None

def taper(v,full,soft,maximum):
    if not finite(v):return 0.
    if v<=full:return 1.
    if v<=soft:return 1-(1-C['softWeight'])*(v-full)/(soft-full)
    if v<=maximum:return C['softWeight']*(maximum-v)/(maximum-soft)
    return 0.

def pose_weight(pose):
    return C['missingPoseWeight'] if pose is None else taper(max(abs(pose[0]),abs(pose[1])),C['poseFull'],C['poseSoft'],C['poseMax'])
def speed_weight(speed): return taper(speed,C['speedFull'],C['speedSoft'],C['speedMax'])
def range_weight(v,low,high,ramp): return clamp(min((v-low)/ramp,(high-v)/ramp)) if finite(v) else 0.
def landmark_speed(points,previous,dt):
    if previous is None or not finite(dt) or dt<=0 or len(points)!=len(previous):return None
    a=np.asarray(points,float);b=np.asarray(previous,float)
    eye=float(np.linalg.norm(a[33,:2]-a[263,:2]))
    return float(np.linalg.norm(a[:,:2]-b[:,:2],axis=1).mean())/dt/eye if eye>1e-8 else float('inf')

def frame_weight(points,face_count,brightness,pose,speed=None,width=1,height=1):
    if face_count!=1 or len(points)<478:
        return dict(weight=0.,reason='multiple_faces' if face_count>1 else 'no_face',hint='One face only' if face_count>1 else 'Keep your face in the circle')
    p=np.asarray(points,float)
    if not np.isfinite(p).all() or width<=0 or height<=0:return dict(weight=0.,reason='tracking',hint='Keep your face visible')
    w=float(np.ptp(p[:,0]/width));h=float(np.ptp(p[:,1]/height))
    factors=dict(pose=pose_weight(pose),speed=1. if speed is None else speed_weight(speed),
        light=range_weight(brightness,C['lightMin'],C['lightMax'],C['lightRamp']),
        size=min(range_weight(w,C['widthMin'],C['widthMax'],C['sizeRamp']),range_weight(h,C['heightMin'],C['heightMax'],C['sizeRamp'])))
    reason=''
    if factors['light']<1:reason='too_dark' if brightness is not None and brightness<(C['lightMin']+C['lightMax'])/2 else 'too_bright'
    elif factors['size']<1:reason='too_far' if w<(C['widthMin']+C['widthMax'])/2 else 'too_close'
    elif factors['pose']<1:reason='turned_away'
    elif factors['speed']<1:reason='movement'
    hints=dict(too_dark='More light',too_bright='Reduce bright light',too_far='Move closer',too_close='Move back',turned_away='Face the camera a little more',movement='Small movements are fine; keep your face in view')
    weight=math.prod(factors.values())
    return dict(weight=0. if weight<C['minFrameWeight'] else weight,factors=factors,reason=reason,hint=hints.get(reason,''))

def feature_mask(row,pose,frontalized=False):
    out=dict(row)
    if row['mar']>C['mouthMax']:out.update(lip_press=None,lip_corner=None)
    if not frontalized and pose is not None and abs(pose[1])>C['jawYawMax']:out['jaw_clench']=None
    return out

def frontalize(points,matrix):
    if not matrix or matrix.get('rows')!=4 or matrix.get('columns')!=4:return points,False
    d=matrix.get('data',[])
    if len(d)!=16 or not all(map(finite,d)):return points,False
    columns=np.array([[d[j*4+i] for i in range(3)] for j in range(3)])
    norms=np.linalg.norm(columns,axis=1)
    if np.any(norms<1e-8):return points,False
    rotation=columns/norms[:,None];p=np.asarray(points,float)
    if p.shape[1]==2:p=np.column_stack([p,np.zeros(len(p))])
    return (p-p.mean(axis=0))@rotation[:2].T,True

class OneEuro:
    def __init__(self):self.time=None;self.x=None;self.dx=0.;self.raw=None
    def update(self,value,time):
        if self.time is None:self.time=time;self.x=value;self.raw=value;return value
        dt=time-self.time
        if dt<=0:return self.x
        def alpha(cut):return 1/(1+1/(2*math.pi*cut*dt))
        a=alpha(C['dCutoff']);self.dx=a*(value-self.raw)/dt+(1-a)*self.dx
        b=alpha(C['minCutoff']+C['beta']*abs(self.dx));self.x=b*value+(1-b)*self.x
        self.raw=value;self.time=time;return self.x

class LandmarkFilter:
    def __init__(self):self.filters={};self.last_face=None
    def update(self,points,time):
        if self.last_face is not None and time-self.last_face>C['faceLossReset']:self.filters={}
        if not len(points):return []
        self.last_face=time
        out=[]
        for i,p in enumerate(points):
            row=[]
            for j,v in enumerate(p):
                key=i*3+j
                if key not in self.filters:self.filters[key]=OneEuro()
                row.append(self.filters[key].update(float(v),time))
            out.append(row)
        return out

def adaptive_state(elapsed,coverage):
    return dict(state='analyzing' if elapsed>=C['maxDuration'] or (elapsed>=C['duration'] and coverage>=C['normalCoverage']) else 'countdown',
        extended=elapsed>=C['duration'],progress=min(1.,elapsed/(C['maxDuration'] if elapsed>=C['duration'] and coverage<C['normalCoverage'] else C['duration'])),capped=elapsed>=C['maxDuration'])

def result_tier(points,coverage):
    scored=[p for p in points if finite(p['value'])];center=median([p['value'] for p in scored]);middle=len(points)/2
    def consensus(radius):
        rows=[p for p in scored if abs(p['value']-center)<=radius]
        early=[p['value'] for p in rows if p['window']<middle];late=[p['value'] for p in rows if p['window']>=middle]
        return dict(rows=rows,fraction=len(rows)/len(scored) if scored else 0.,difference=abs(median(early)-median(late)) if early and late else None)
    normal=consensus(C['normalRadius']);limited=consensus(C['limitedRadius'])
    if coverage>=C['normalCoverage'] and len(scored)>=C['normalWindows'] and normal['fraction']>=C['normalFraction'] and normal['difference'] is not None and normal['difference']<=C['normalDifference']:return dict(tier='NORMAL',**normal)
    if coverage>=C['limitedCoverage'] and len(scored)>=C['limitedWindows'] and limited['fraction']>=C['limitedFraction'] and limited['difference'] is not None and limited['difference']<=C['limitedDifference']:return dict(tier='LIMITED',**limited)
    return dict(tier='NONE',**limited)

class TolerantScan:
    def __init__(self,baseline=None,frontalize3d=C['frontalize3d']):
        self.baseline=baseline;self.frontalize3d=frontalize3d;self.filter=LandmarkFilter();self.previous=None;self.last_time=-math.inf
        self.slots={};self.reasons={};self.observations=[];self.elapsed=0.;self.reference=old.reference_rows(KEYS)
        self.quality_flags=dict(lowLight=False,offCenter=False,tooFar=False,tooClose=False,moving=False,multipleFaces=False,mouthOpen=False,pose=False)
    def score(self,row):
        if sum(finite(row.get(k)) for k in KEYS)<C['minFeatures']:return None
        if self.baseline is None:return old.score_row(row,self.reference,KEYS)
        return old.QuickIndex(self.baseline).score(row) if sum(finite(row.get(k)) and k in self.baseline['features'] for k in KEYS)>=C['minFeatures'] else None
    def update(self,time,points,pose,quality_good=True,context=None):
        if not finite(time) or time<=self.last_time or time<0 or time>=C['maxDuration']:return dict(valid=False,reason='',weight=0)
        self.last_time=time;self.elapsed=time;context=context or {};width=context.get('width',1);height=context.get('height',1)
        speed=landmark_speed(points,self.previous['points'] if self.previous else None,time-(self.previous['time'] if self.previous else time))
        self.previous=dict(points=points,time=time) if len(points)>=478 and context.get('faceCount',1)==1 else None
        quality=frame_weight(points,context.get('faceCount',1 if len(points)>=478 else 0),context.get('brightness'),pose,speed,width,height)
        normalized=[[p[0]/width,p[1]/height,(p[2] if len(p)>2 else 0)/width] for p in points]
        smooth=np.asarray(self.filter.update([] if quality['reason'] in ('no_face','multiple_faces','tracking') else normalized,time))
        if len(smooth):smooth=smooth*[width,height,width]
        row=None
        if quality['weight']>0 and len(smooth):
            try:
                corrected,applied=frontalize(smooth,context.get('matrix')) if self.frontalize3d else (smooth,False)
                row=feature_mask(old.geometry(corrected),pose,applied)
            except (ValueError,IndexError,TypeError,FloatingPointError):pass
        flags=dict(lowLight=quality['reason']=='too_dark',tooFar=quality['reason']=='too_far',tooClose=quality['reason']=='too_close',moving=quality.get('factors',{}).get('speed',1)<1,multipleFaces=quality['reason']=='multiple_faces',mouthOpen=row is not None and row['mar']>C['mouthMax'],pose=quality.get('factors',{}).get('pose',1)<1)
        for key,value in flags.items():self.quality_flags[key]=self.quality_flags[key] or bool(value)
        self.observations.append(dict(time=time,weight=quality['weight'] if row else 0.,pose=max(abs(pose[0]),abs(pose[1])) if pose is not None else None,speed=speed))
        if time>=C['settling']:
            if row is None or quality['reason']:
                reason=quality['reason'] or 'tracking';self.reasons[reason]=self.reasons.get(reason,0)+1
            slot=math.floor((time-C['settling'])/C['slotSeconds']+1e-8)
            self.slots.setdefault(slot,[])
            if row:self.slots[slot].append(dict(row=row,weight=quality['weight']))
        return dict(valid=row is not None,weight=quality['weight'] if row else 0.,reason=quality['hint'],phase='live')
    def usable_slots(self):
        return {i:dict(row={k:weighted_median([r['row'].get(k) for r in rows],[r['weight'] for r in rows]) for k in KEYS},weight=max(r['weight'] for r in rows)) for i,rows in self.slots.items() if rows}
    def coverage(self):return min(1.,sum(r['weight'] for r in self.usable_slots().values())/C['coverageSlots'])
    def rolling_coverage(self,time):
        weights={}
        for r in self.observations:
            if r['time']<=time-C['hintSeconds']:continue
            i=math.floor(r['time']/C['slotSeconds']);weights[i]=max(weights.get(i,0.),r['weight'])
        return sum(weights.values())/(C['hintSeconds']/C['slotSeconds'])
    def finish(self,duration=None):
        duration=min(C['maxDuration'],max(C['duration'],self.elapsed if duration is None else duration))
        slots=self.usable_slots();points=[];rows=[];count=math.floor((duration-C['settling'])/C['windowSeconds']+1e-8)
        for window in range(count):
            block=[s for i,s in slots.items() if math.floor(i*C['slotSeconds']/C['windowSeconds'])==window]
            row={k:weighted_median([b['row'][k] for b in block],[b['weight'] for b in block]) for k in KEYS}
            used=sum(finite(row[k]) for k in KEYS)
            value=self.score(dict(row,time=window+1.5)) if len(block)>=C['minWindowSlots'] and used>=C['minFeatures'] else None
            if finite(value):rows.append(row)
            points.append(dict(window=window,time=window+1.5,value=value,featuresUsed=used if finite(value) else 0))
        coverage=self.coverage();assigned=result_tier(points,coverage);none=assigned['tier']=='NONE'
        average=None if none else median([p['value'] for p in assigned['rows']]);values=[p['value'] for p in points if finite(p['value'])]
        spread=max(C['rangeFloor'],C['madScale']*mad(values))*(C['limitedWiden'] if assigned['tier']=='LIMITED' else 1) if values else None
        poses=[r['pose'] for r in self.observations if finite(r['pose'])];speeds=[r['speed'] for r in self.observations if finite(r['speed'])]
        variability=clamp(max(float(np.std(poses))/C['poseMax'] if poses else 0.,float(np.std(speeds))/C['speedMax'] if speeds else 0.))
        confidence=clamp(C['confidenceCoverage']*min(1.,coverage/C['normalCoverage'])+C['confidenceConsensus']*assigned['fraction']+C['confidenceStability']*(1-variability))
        top=max(self.reasons,key=self.reasons.get) if self.reasons else 'no_face'
        failures=dict(no_face='No face was tracked. Keep your face in the circle and retry.',multiple_faces='More than one face was visible. Scan with one person in view.',too_dark='Your face was too dark. Face a light source and retry.',too_bright='Your face was overexposed. Reduce bright light and retry.',too_far='Your face was too far away. Move closer and retry.',too_close='Your face was too close. Move back and retry.',turned_away='Your face was turned away. Face the camera and retry.',movement='Too much movement obscured the landmarks. Make smaller movements and retry.',tracking='The landmarks could not be tracked. Keep your face visible and retry.')
        fail_reason=('The readings did not agree enough. Keep a similar expression and retry.' if len(values)>=C['limitedWindows'] else failures[top]) if none else ''
        stats={}
        for k in KEYS:
            a=[r[k] for r in rows if finite(r[k])];stats[k]=dict(median=median(a),mad=mad(a))
        return dict(average=average,latest=None if none else points[-1]['value'] if points else None,tier=assigned['tier'],status='failed' if none else 'limited' if assigned['tier']=='LIMITED' else 'ok',quality='poor' if none else 'limited' if assigned['tier']=='LIMITED' else 'good',confidence=confidence,range=None if none else [max(0.,average-spread),min(10.,average+spread)],warnings=['Movement or expressions reduced reliability'] if assigned['tier']=='LIMITED' else [],reason=fail_reason or ('Movement or expressions reduced reliability' if assigned['tier']=='LIMITED' else ''),failReason=fail_reason,reasonCode=top if none else '',points=points,windowScores=[p['value'] for p in points],windowFeaturesUsed=[p['featuresUsed'] for p in points],effectiveCoverage=coverage,coveragePercent=100*coverage,features={k:s['median'] for k,s in stats.items()} if rows else None,featureStats=stats if rows else None,mode='baseline' if self.baseline else 'generic',algoVersion=C['version'],frontalize3d=self.frontalize3d,qualityFlags=dict(self.quality_flags),reliability=dict(usableSlots=len(slots),totalSlots=C['coverageSlots'],usableWindows=len(values),totalWindows=count,consensusFraction=assigned['fraction'],consensusHalfDifference=assigned['difference'],poseSpeedVariability=variability,rejectionReasons=self.reasons,ruleVersion=C['version']))
