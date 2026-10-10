import numpy as np
from scipy.special import expit
from scipy.signal import butter, sosfiltfilt, welch, find_peaks

SEED = 42
INDICES = (33,160,158,133,153,144,362,385,387,263,373,380,
           70,63,105,66,107,55,65,52,53,46,336,296,334,293,300,285,295,282,283,276,
           468,469,470,471,472,473,474,475,476,477,
           1,4,5,6,19,94,97,98,168,195,
           61,291,13,14,0,17,37,267,40,270,78,308,
           10,152,234,454,127,356,172,397,149,378,176)
assert len(INDICES) == len(set(INDICES)) == 75
KEYS = ('blink_rate','brow_furrow','lip_press','lip_corner','jaw_clench','jitter','hr','rmssd')
SIGNS = np.array([1,1,1,1,1,1,1,-1])
# MediaPipe canonical face, fixed independently of evaluation participants.
from pathlib import Path
_vertices = [list(map(float,line.split()[1:4])) for line in
             Path(__file__).with_name('canonical_face_model.obj').read_text().splitlines() if line.startswith('v ')]
REFERENCE = np.zeros((478,2))
REFERENCE[:468] = np.array(_vertices)[:,:2]*[1,-1]
for centre, corners in ((468,(33,133)),(473,(362,263))):
    c=REFERENCE[list(corners)].mean(axis=0)
    REFERENCE[centre]=c
    for offset, delta in enumerate(((.08,0),(0,-.08),(-.08,0),(0,.08)),1):
        REFERENCE[centre+offset]=c+delta

def normalize(points):
    p = np.asarray(points, float)[:, :2]
    ids = np.array(INDICES)
    x = p-p[ids].mean(axis=0)
    y = REFERENCE[ids]-REFERENCE[ids].mean(axis=0)
    u, _, vt = np.linalg.svd(x[ids].T@y)
    r = u@vt
    if np.linalg.det(r)<0:
        u[:,-1]*=-1; r=u@vt
    aligned=x@r
    return aligned/max(np.linalg.norm(aligned[33]-aligned[263]),1e-8)

def geometry(points):
    p=normalize(points)
    d=lambda a,b: float(np.linalg.norm(p[a]-p[b]))
    ear=lambda a,b,c,e,f,g: (d(b,g)+d(c,f))/(2*max(d(a,e),1e-8))
    width=max(d(61,291),1e-8)
    # Downward corner displacement relative to mouth centre, invariant to roll.
    eye_axis=p[263]-p[33]; eye_axis/=np.linalg.norm(eye_axis)
    down=np.array([-eye_axis[1],eye_axis[0]])
    if np.dot(p[152]-p[10],down)<0: down=-down
    corner=float(np.arctan2(np.dot((p[61]+p[291]-p[13]-p[14])/2,down),width/2))
    return dict(ear=(ear(33,160,158,133,153,144)+ear(362,385,387,263,373,380))/2,
                mar=d(13,14)/width,
                lip_press=-(d(0,13)+d(14,17))/width,
                brow_furrow=-(d(107,336)+(d(105,159 if 159 in INDICES else 158)+d(334,385))/2),
                lip_corner=corner, jaw_clench=d(234,454)/max(d(10,152),1e-8))

def pulse(times, green):
    if len(times)<2: return {}
    fps=1/np.median(np.diff(times))
    if fps<15 or times[-1]-times[0]<20: return {}
    t=np.arange(times[0],times[-1],1/fps)
    g=np.interp(t,times,green)
    if np.std(g)<1e-5: return {}
    signal=sosfiltfilt(butter(3,[.7,3],btype='bandpass',fs=fps,output='sos'),g)
    f,p=welch(signal,fs=fps,nperseg=min(len(signal),int(fps*12)))
    band=(f>=.7)&(f<=3)
    peak=np.max(p[band]); noise=np.median(p[band])
    if peak<5*max(noise,1e-12): return {}
    hr=float(f[band][np.argmax(p[band])]*60)
    peaks,_=find_peaks(signal,distance=int(fps*.3),prominence=np.std(signal)*.4)
    rr=np.diff(t[peaks])*1000
    rr=rr[(rr>=333)&(rr<=1429)]
    result={'hr':hr}
    if len(rr)>=10: result['rmssd']=float(np.sqrt(np.mean(np.diff(rr)**2)))
    return result

class Index:
    def __init__(self, baseline):
        self.mu={}; self.sd={}; self.raw_sd={}; self.ema=None; self.last_time=None; self.window=[]
        for k in KEYS:
            a=np.array([r.get(k,np.nan) for r in baseline],float); a=a[np.isfinite(a)]
            if len(a)>=5:
                self.mu[k]=float(a.mean()); self.raw_sd[k]=float(a.std())
                self.sd[k]=max(self.raw_sd[k], .05*abs(self.mu[k])+1e-3)
    def score(self,row,omit=None):
        keys=[k for k in KEYS if k!=omit and k in self.mu and np.isfinite(row.get(k,np.nan))]
        if not keys or row.get('gated',False): return np.nan
        z=np.array([np.clip((row[k]-self.mu[k])/(self.sd[k]+1e-6),-3,3)*SIGNS[KEYS.index(k)] for k in keys])
        now=float(row.get('time',0))
        raw=float(z.sum()/np.sqrt(len(keys)))
        self.window.append((now,raw))
        self.window=[v for v in self.window if v[0]>=now-5]
        s=float(100*expit(np.mean([v[1] for v in self.window])))
        if self.last_time is not None and now-self.last_time<.1: return self.ema
        self.last_time=now
        self.ema=s if self.ema is None else .1*s+.9*self.ema
        return self.ema
