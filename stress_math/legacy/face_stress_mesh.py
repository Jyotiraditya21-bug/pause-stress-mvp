"""
Live-camera Face Mesh Stress Index  (0 = HIGH stress, 10 = NO stress)
Training-free: pure landmark geometry + image-texture/colour statistics.

Install:  pip install opencv-python mediapipe numpy
Run:      python face_stress_mesh.py
Keys:     c = recalibrate (neutral face, 3 s) | m = toggle mesh | q = quit
Output:   stress_log.csv (timestamp, score, every feature value + contribution)
"""
import cv2, time, math, csv
import numpy as np
import mediapipe as mp
from collections import deque

mp_fm = mp.solutions.face_mesh
TESS = list(mp_fm.FACEMESH_TESSELATION)

# ----------------------------------------------------------------------------
# 1. LANDMARK GROUPS (MediaPipe 478-pt mesh)
# ----------------------------------------------------------------------------
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


# ----------------------------------------------------------------------------
# 4. ENGINE
# ----------------------------------------------------------------------------
class StressEngine:
    def __init__(self):
        self.reset()

    def reset(self):
        self.cal, self.base = [], None
        self.gaze_hist = deque(maxlen=45)
        self.nose_hist = deque(maxlen=45)
        self.blink_times = deque()
        self.eye_closed = False
        self.t0 = time.time()
        self.score = 10.0

    # ---- feature extraction ------------------------------------------------
    def extract(self, lm, frame):
        h, w = frame.shape[:2]
        pts = np.array([[l.x * w, l.y * h] for l in lm.landmark], dtype=np.float32)

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
        now = time.time()
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

    # ---- fusion --------------------------------------------------------------
    def update(self, f):
        if self.base is None:
            self.cal.append(f)
            if len(self.cal) >= CAL_FRAMES:
                self.base = {k: float(np.median([x[k] for x in self.cal])) for k in FEATURES}
                for k, v in FIXED_BASE.items():
                    self.base[k] = v
            return None, {}, True

        contrib, num, den = {}, 0.0, 0.0
        for name, (direction, scale, weight, _) in FEATURES.items():
            c = deviation(f[name], self.base[name], scale, direction)
            contrib[name] = c
            num += weight * c
            den += weight
        S = num / den
        relief = np.clip((f["smile_lift"] - self.base["smile_lift"]) / 0.02, 0, 1) * 0.15  # genuine smile lowers stress
        S = max(0.0, S - relief)
        S_adj = 1.0 - math.exp(-GAIN * S)
        raw = 10.0 * (1.0 - S_adj)
        self.score = 0.9 * self.score + 0.1 * raw                  # EMA smoothing
        return self.score, contrib, False


# ----------------------------------------------------------------------------
# 5. DRAWING
# ----------------------------------------------------------------------------
def draw_mesh(img, pts, full=True):
    p = pts.astype(np.int32)
    if full:
        for a, b in TESS:                                          # full tessellation loop
            cv2.line(img, tuple(p[a]), tuple(p[b]), (70, 70, 70), 1, cv2.LINE_AA)
    for name, (idx, col, closed) in REGIONS.items():               # per-region loop
        poly = np.array([p[i] for i in idx], np.int32)
        cv2.polylines(img, [poly], closed, col, 1, cv2.LINE_AA)
        for i in idx:                                              # per-landmark loop
            cv2.circle(img, tuple(p[i]), 1, col, -1)


def score_color(s):
    for limit, col in ((3.3, (0, 0, 255)), (6.6, (0, 165, 255)), (10.1, (0, 220, 0))):
        if s < limit:
            return col
    return (0, 220, 0)


def draw_hud(img, score, contrib, calibrating, n_cal):
    h, w = img.shape[:2]
    cv2.rectangle(img, (0, 0), (300, h), (20, 20, 20), -1)
    if calibrating:
        cv2.putText(img, "CALIBRATING", (15, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
        cv2.putText(img, "Keep a neutral face", (15, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)
        cv2.rectangle(img, (15, 85), (285, 100), (80, 80, 80), 1)
        cv2.rectangle(img, (15, 85), (15 + int(270 * n_cal / CAL_FRAMES), 100), (0, 255, 255), -1)
        return
    col = score_color(score)
    label = "HIGH STRESS" if score < 3.3 else "MODERATE" if score < 6.6 else "RELAXED"
    cv2.putText(img, "STRESS SCORE (0=high, 10=none)", (10, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)
    cv2.putText(img, f"{score:4.1f}", (15, 85), cv2.FONT_HERSHEY_SIMPLEX, 2.0, col, 4)
    cv2.putText(img, label, (150, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.6, col, 2)
    y = 120
    for name, c in sorted(contrib.items(), key=lambda kv: -kv[1])[:16]:   # top contributors loop
        cv2.putText(img, FEATURES[name][3], (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (220, 220, 220), 1)
        cv2.rectangle(img, (10, y + 4), (290, y + 12), (60, 60, 60), -1)
        cv2.rectangle(img, (10, y + 4), (10 + int(280 * c), y + 12), (0, int(255 * (1 - c)), int(255 * c)), -1)
        y += 30


# ----------------------------------------------------------------------------
# 6. MAIN LOOP
# ----------------------------------------------------------------------------
def main():
    cap = cv2.VideoCapture(0)
    eng = StressEngine()
    show_mesh = True
    log = []
    t_start = time.time()

    with mp_fm.FaceMesh(max_num_faces=1, refine_landmarks=True,
                        min_detection_confidence=0.5, min_tracking_confidence=0.5) as fm:
        while cap.isOpened():
            ok, frame = cap.read()
            if not ok:
                break
            frame = cv2.flip(frame, 1)
            res = fm.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

            canvas = frame.copy()
            score, contrib, calibrating = None, {}, False

            if res.multi_face_landmarks:
                f, pts = eng.extract(res.multi_face_landmarks[0], frame)
                score, contrib, calibrating = eng.update(f)
                if show_mesh:
                    draw_mesh(canvas, pts)
                if score is not None:
                    row = {"t": round(time.time() - t_start, 2), "score": round(score, 3)}
                    for k in FEATURES:
                        row[k] = round(f[k], 5)
                        row["c_" + k] = round(contrib[k], 4)
                    log.append(row)
            else:
                cv2.putText(canvas, "No face detected", (320, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

            view = np.hstack([np.zeros((canvas.shape[0], 300, 3), np.uint8), canvas])
            draw_hud(view, eng.score if score is not None else 10.0, contrib, calibrating or eng.base is None, len(eng.cal))
            cv2.imshow("Face Stress Index", view)

            k = cv2.waitKey(1) & 0xFF
            if k == ord("q"):
                break
            elif k == ord("m"):
                show_mesh = not show_mesh
            elif k == ord("c"):
                eng.reset()

    cap.release()
    cv2.destroyAllWindows()
    if log:
        with open("stress_log.csv", "w", newline="") as fh:
            wr = csv.DictWriter(fh, fieldnames=list(log[0].keys()))
            wr.writeheader()
            for row in log:
                wr.writerow(row)
        print(f"Saved {len(log)} rows to stress_log.csv | mean score = {np.mean([r['score'] for r in log]):.2f}")


if __name__ == "__main__":
    main()