"""Deterministic headless port. Landmarks are 478 pixel coordinates, frames BGR.
Only rest calibration is estimated; engineering weights never use task labels.
Temporal feature buffers remain the legacy 45-frame buffers; only score EMA is
made time-based. Consequently the entire extractor is NOT FPS invariant.
"""
import math
from collections import deque
import cv2
import numpy as np

REGIONS = {  # name: (indices, BGR colour, closed)
    "face_oval":   ([10,338,297,332,284,251,389,356,454,323,361,288,397,365,379,378,400,377,152,
                     148,176,149,150,136,172,58,132,93,234,127,162,21,54,103,67,109], (255,255,255), True),
    "r_eye":       ([33,7,163,144,145,153,154,155,133,173,157,158,159,160,161,246], (0,255,255), True),
    "l_eye":       ([362,382,381,380,374,373,390,249,263,466,388,387,386,385,384,398], (0,255,255), True),
    "r_brow":      ([70,63,105,66,107], (255,200,0), False),
    "l_brow":      ([336,296,334,293,300], (255,200,0), False),
    "lips_outer":  ([61,146,91,181,84,17,314,405,321,375,291,409,270,269,267,0,37,39,40,185], (0,0,255), True),
    "lips_inner":  ([78,95,88,178,87,14,317,402,318,324,308,415,310,311,312,13,82,81,80,191], (0,120,255), True),
    "nose":        ([168,6,197,195,5,4,1], (0,255,0), False),
    "jaw":         ([172,136,150,149,176,148,152,377,400,378,379,365,397], (255,0,255), False),
    "iris_r":      ([468,469,470,471,472], (255,255,0), True),
    "iris_l":      ([473,474,475,476,477], (255,255,0), True),
}
R_EAR = [33,160,158,133,153,144]
L_EAR = [362,385,387,263,373,380]
R_LOWER_LID = [33,7,163,144,145,153,154,155,133]
L_LOWER_LID = [362,382,381,380,374,373,390,249,263]
LIP_OUTER = REGIONS["lips_outer"][0]

# ----------------------------------------------------------------------------
# 2. FEATURE SPECS:  name: (direction, scale, weight, label)
#    direction +1 = stress when value RISES above baseline
#             -1 = stress when value FALLS below baseline
#              0 = stress on any deviation
#    scale     = size of change that counts as "full stress" for that feature
# ----------------------------------------------------------------------------
FEATURES = {
    # smile / mouth
    "smile_lift":       (-1, 0.012, 2.0, "Smile (corner lift)"),
    "mouth_width":      (-1, 0.040, 1.0, "Mouth width"),
    "cheek_raise":      (-1, 0.008, 1.0, "Cheek raise (Duchenne)"),
    "mouth_asym":       (+1, 0.010, 0.6, "Mouth asymmetry"),
    # lips
    "lip_compress":     (+1, 0.050, 1.5, "Lip compression"),
    "lip_thin":         (-1, 0.008, 1.2, "Lip thinning"),
    "lip_pallor":       (-1, 0.150, 0.8, "Lip pallor"),
    "jaw_clench":       (-1, 0.010, 0.8, "Chin/jaw tension"),
    # brows / forehead
    "brow_furrow":      (-1, 0.020, 1.8, "Brow furrow"),
    "brow_height":      ( 0, 0.010, 1.0, "Brow raise/drop"),
    "brow_asym":        (+1, 0.010, 0.5, "Brow asymmetry"),
    "forehead_wrinkle": (+1, 0.060, 1.5, "Forehead wrinkles"),
    "glabella_wrinkle": (+1, 0.080, 1.5, "Between-brow wrinkles"),
    "nose_wrinkle":     (+1, 0.080, 0.6, "Nose-bridge wrinkles"),
    "crowfeet":         (+1, 0.060, 0.5, "Crow's feet"),
    # eyes
    "eye_ear":          ( 0, 0.050, 1.2, "Eye openness (EAR)"),
    "eye_asym":         (+1, 0.040, 0.4, "Eye asymmetry"),
    "blink_rate":       (+1, 15.0,  1.0, "Blink rate /min"),
    "gaze_instab":      (+1, 0.040, 1.0, "Gaze instability"),
    # tears / skin around eyes
    "tear_red":         (+1, 0.050, 1.2, "Under-eye redness (tears)"),
    "tear_gloss":       (+1, 0.040, 1.0, "Under-eye gloss (tears)"),
    "undereye_dark":    (-1, 0.080, 0.6, "Under-eye darkness"),
    # nose / head
    "nostril_flare":    (+1, 0.015, 0.7, "Nostril flare"),
    "head_jitter":      (+1, 0.010, 1.0, "Head jitter"),
}
FIXED_BASE = {"blink_rate": 17.0}   # typical resting blink rate
GAIN = 4.0                          # sensitivity of the final 0-10 mapping
CAL_FRAMES = 90                     # ~3 s calibration


# ----------------------------------------------------------------------------
# 3. HELPERS
# ----------------------------------------------------------------------------
def d(a, b):
    return float(np.linalg.norm(a - b))


def ear(p, idx):
    p1, p2, p3, p4, p5, p6 = [p[i] for i in idx]
    return (d(p2, p6) + d(p3, p5)) / (2.0 * d(p1, p4) + 1e-6)


def crop(img, x1, y1, x2, y2):
    h, w = img.shape[:2]
    x1, x2 = int(max(0, min(x1, x2))), int(min(w, max(x1, x2)))
    y1, y2 = int(max(0, min(y1, y2))), int(min(h, max(y1, y2)))
    if x2 - x1 < 4 or y2 - y1 < 4:
        return None
    return img[y1:y2, x1:x2]


def bbox(pts_xy, idx, pad=0.0):
    xs = [pts_xy[i][0] for i in idx]
    ys = [pts_xy[i][1] for i in idx]
    return min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad


def edge_density(patch, axis=1, thr=60):
    """Fraction of strong edges (axis=1: horizontal lines, axis=0: vertical lines)."""
    if patch is None:
        return 0.0
    g = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
    g = cv2.GaussianBlur(g, (3, 3), 0).astype(np.float32)
    g = g / (g.mean() + 1e-6) * 128.0            # lighting normalisation
    s = cv2.Sobel(g, cv2.CV_32F, 1 - axis, axis, ksize=3)
    return float((np.abs(s) > thr).mean())


def color_stats(patch):
    """Returns (redness, gloss, luminance, saturation)."""
    if patch is None:
        return 0.0, 0.0, 0.0, 0.0
    b, g, r = [float(patch[..., c].mean()) for c in range(3)]
    redness = r / (g + b + 1e-6)
    gray = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY).astype(np.float32)
    gloss = float(((gray - gray.mean()) > 55).mean())
    sat = float(cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)[..., 1].mean())
    return redness, gloss, float(gray.mean()), sat


def deviation(v, base, scale, direction):
    x = (v - base) / scale
    x = abs(x) if direction == 0 else x * direction
    return float(np.clip(x, 0.0, 1.0))



GROUPS = {
    "G": ("smile_lift", "mouth_width", "cheek_raise", "mouth_asym", "lip_compress", "lip_thin", "jaw_clench", "brow_furrow", "brow_height", "brow_asym", "eye_ear", "eye_asym", "nostril_flare"),
    "T": ("blink_rate", "gaze_instab", "head_jitter"),
    "X": ("lip_pallor", "forehead_wrinkle", "glabella_wrinkle", "nose_wrinkle", "crowfeet", "tear_red", "tear_gloss", "undereye_dark"),
}
MOUTH = ("smile_lift", "mouth_width", "mouth_asym", "lip_compress", "lip_thin")
TAU = .316
THRESHOLD = 50.0  # Fixed before evaluation: S_h > 50, original score < 5.

class StressEngine:
    def __init__(self, variant="H0", baseline=None, selected=None):
        if variant not in ("H0", "H1"):
            raise ValueError("variant must be H0 or H1")
        self.variant = variant
        self.selected = tuple(FEATURES if selected is None else selected)
        if not self.selected or set(self.selected)-set(FEATURES):
            raise ValueError("Select at least one known feature")
        self.reset(baseline)

    def reset(self, baseline=None):
        self.cal, self.base = [], None if baseline is None else dict(baseline)
        self.gaze_hist = deque(maxlen=45)
        self.nose_hist = deque(maxlen=45)
        self.blink_times = deque()
        self.eye_closed = False
        self.t0 = None
        self.last_timestamp = None
        self.last_score_timestamp = None
        self.score = 10.0

    def _timestamp(self, timestamp):
        timestamp = float(timestamp)
        if not math.isfinite(timestamp) or (self.last_timestamp is not None and timestamp < self.last_timestamp):
            raise ValueError("Finite monotonically increasing video/capture timestamps required")
        if self.t0 is None:
            self.t0 = timestamp
        self.last_timestamp = timestamp

    @staticmethod
    def rest_baseline(rows):
        if len(rows) < 5:
            raise ValueError("At least five usable rest frames required")
        return {k: float(np.median([r[k] for r in rows])) for k in FEATURES}

    def extract(self, landmarks, frame, timestamp):
        h, w = frame.shape[:2]
        pts = np.asarray(landmarks, dtype=np.float32)[:, :2].copy()
        if pts.shape != (478, 2) or not np.isfinite(pts).all():
            raise ValueError("Expected 478 finite pixel landmarks")
        self._timestamp(timestamp)

        # roll-compensated copy for geometry (head tilt invariant)
        c = pts[168]
        th = math.atan2(pts[263][1] - pts[33][1], pts[263][0] - pts[33][0])
        M = np.array([[math.cos(th), -math.sin(th)], [math.sin(th), math.cos(th)]], dtype=np.float32)
        pr = (pts - c) @ M

        fw = d(pr[234], pr[454]) + 1e-6
        fh = d(pr[10], pr[152]) + 1e-6
        f = {}

        # ---------- SMILE / MOUTH LOOPS ----------
        lip_cy = (pr[13][1] + pr[14][1]) / 2.0
        corner_y = (pr[61][1] + pr[291][1]) / 2.0
        f["smile_lift"] = (lip_cy - corner_y) / fh
        f["mouth_width"] = d(pr[61], pr[291]) / fw
        f["mouth_asym"] = abs(pr[61][1] - pr[291][1]) / fh
        cheek = 0.0
        for eye_low, cheek_pt in ((145, 50), (374, 280)):        # lower lid -> cheek
            cheek += d(pr[eye_low], pr[cheek_pt])
        f["cheek_raise"] = -(cheek / 2.0) / fh

        # ---------- LIP LOOPS ----------
        inner_gap = d(pr[13], pr[14])
        f["lip_compress"] = -inner_gap / (d(pr[61], pr[291]) + 1e-6)
        thick = 0.0
        for a, b in ((0, 13), (14, 17)):                          # upper + lower lip
            thick += d(pr[a], pr[b])
        f["lip_thin"] = thick / fh
        f["jaw_clench"] = d(pr[17], pr[152]) / fh

        # lip pallor: lip saturation vs cheek saturation
        mask = np.zeros((h, w), np.uint8)
        poly = np.array([pts[i] for i in LIP_OUTER], np.int32)
        cv2.fillPoly(mask, [poly], 255)
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        lip_sat = float(hsv[..., 1][mask > 0].mean()) if mask.any() else 0.0
        cheek_sat = []
        for cp in (50, 280):
            cx, cy, r = pts[cp][0], pts[cp][1], 0.04 * fw
            _, _, _, s = color_stats(crop(frame, cx - r, cy - r, cx + r, cy + r))
            cheek_sat.append(s)
        cheek_lum = []
        for cp in (50, 280):
            cx, cy, r = pts[cp][0], pts[cp][1], 0.04 * fw
            _, _, l, _ = color_stats(crop(frame, cx - r, cy - r, cx + r, cy + r))
            cheek_lum.append(l)
        f["lip_pallor"] = lip_sat / (np.mean(cheek_sat) + 1e-6)

        # ---------- BROW / FOREHEAD LOOPS ----------
        brow_eye = 0.0
        for brow_pt, eye_pt in ((105, 159), (334, 386)):
            brow_eye += d(pr[brow_pt], pr[eye_pt])
        f["brow_height"] = (brow_eye / 2.0) / fh
        f["brow_furrow"] = d(pr[107], pr[336]) / fw
        f["brow_asym"] = abs(pr[105][1] - pr[334][1]) / fh

        fx1, fx2 = pts[103][0], pts[332][0]
        fy1 = pts[10][1]
        fy2 = min(pts[105][1], pts[334][1]) - 0.01 * fh
        f["forehead_wrinkle"] = edge_density(crop(frame, fx1, fy1, fx2, fy2), axis=1)

        gx = 0.06 * fw
        f["glabella_wrinkle"] = edge_density(
            crop(frame, pts[9][0] - gx, pts[9][1] - 0.5 * gx, pts[9][0] + gx, pts[9][1] + 0.9 * gx), axis=0)
        f["nose_wrinkle"] = edge_density(
            crop(frame, pts[6][0] - gx, pts[6][1] - 0.6 * gx, pts[6][0] + gx, pts[6][1] + 0.8 * gx), axis=1)

        cf = 0.0
        for corner in (33, 263):                                   # crow's feet at outer corners
            sgn = -1 if corner == 33 else 1
            x0 = pts[corner][0]
            cf += edge_density(crop(frame, x0, pts[corner][1] - 0.6 * gx,
                                    x0 + sgn * 1.2 * gx, pts[corner][1] + 0.6 * gx), axis=0)
        f["crowfeet"] = cf / 2.0

        # ---------- EYE LOOPS ----------
        er, el = ear(pr, R_EAR), ear(pr, L_EAR)
        e_avg = (er + el) / 2.0
        f["eye_ear"] = e_avg
        f["eye_asym"] = abs(er - el)

        thr = 0.75 * self.base["eye_ear"] if self.base else 0.20
        closed = e_avg < thr
        now = float(timestamp)
        if closed and not self.eye_closed:
            self.blink_times.append(now)
        self.eye_closed = closed
        while self.blink_times and now - self.blink_times[0] > 60:
            self.blink_times.popleft()
        elapsed = min(60.0, now - self.t0)
        f["blink_rate"] = len(self.blink_times) * 60.0 / elapsed if elapsed >= 10 else FIXED_BASE["blink_rate"]

        gx_off, gy_off = [], []
        for iris, c_in, c_out, up, lo in ((468, 33, 133, 159, 145), (473, 362, 263, 386, 374)):
            gx_off.append((pr[iris][0] - pr[c_in][0]) / (pr[c_out][0] - pr[c_in][0] + 1e-6))
            gy_off.append((pr[iris][1] - pr[up][1]) / (pr[lo][1] - pr[up][1] + 1e-6))
        self.gaze_hist.append((np.mean(gx_off), np.mean(gy_off)))
        f["gaze_instab"] = float(np.std(np.array(self.gaze_hist), axis=0).mean()) if len(self.gaze_hist) > 10 else 0.0

        # ---------- TEAR / UNDER-EYE LOOPS ----------
        reds, gloss, lums = [], [], []
        for lid in (R_LOWER_LID, L_LOWER_LID):
            x1, y1, x2, y2 = bbox(pts, lid)
            ph = y2 - y1
            patch = crop(frame, x1, y2, x2, y2 + 0.9 * ph + 6)
            rd, gl, lu, _ = color_stats(patch)
            reds.append(rd); gloss.append(gl); lums.append(lu)
        f["tear_red"] = float(np.mean(reds))
        f["tear_gloss"] = float(np.mean(gloss))
        f["undereye_dark"] = float(np.mean(lums)) / (np.mean(cheek_lum) + 1e-6)

        # ---------- NOSE / HEAD LOOPS ----------
        f["nostril_flare"] = d(pr[49], pr[279]) / fw
        self.nose_hist.append(pts[1] / fw)
        f["head_jitter"] = float(np.std(np.array(self.nose_hist), axis=0).mean()) if len(self.nose_hist) > 10 else 0.0

        return f, pts


    def update(self, f, timestamp):
        self._timestamp(timestamp)
        dt = 1/30 if self.last_score_timestamp is None else timestamp-self.last_score_timestamp
        self.last_score_timestamp = float(timestamp)
        if self.base is None:
            self.cal.append(dict(f))
            if self.variant == "H0" and len(self.cal) >= CAL_FRAMES:
                self.base = self.rest_baseline(self.cal)
                self.base.update(FIXED_BASE)
            return None, {}, True
        contrib = {name: deviation(f[name], self.base[name], FEATURES[name][1], FEATURES[name][0]) for name in self.selected}
        num = sum(FEATURES[k][2]*v for k,v in contrib.items())
        den = sum(FEATURES[k][2] for k in self.selected)
        S = num/den
        # Relief is removed with smile_lift, so ablations cannot leak that feature.
        relief = float(np.clip((f["smile_lift"]-self.base["smile_lift"])/.02,0,1)*.15) if "smile_lift" in self.selected else 0.
        S = max(0., S-relief)
        S_adj = 1-math.exp(-GAIN*S)
        raw = 10*(1-S_adj)
        alpha = 1-math.exp(-max(dt,0.)/TAU)
        self.score = (1-alpha)*self.score+alpha*raw
        return self.score, contrib, False

    def process(self, landmarks, frame, timestamp, gated=False, pose_valid=True):
        self._timestamp(timestamp)
        if not np.isfinite(landmarks).all() or (self.variant == "H1" and (gated or not pose_valid)):
            return np.nan, None
        f, _ = self.extract(landmarks, frame, timestamp)
        score, _, _ = self.update(f, timestamp)
        return (np.nan if score is None else 100*(1-score/10)), f
