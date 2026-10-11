"""Webcam PPG pulse feature extraction and scoring.

Inspired by Maaoui, Bousefsaf & Pruski (2020) webcam PPG stress detection.
Training-free pulse branch using skin ROI spatial averaging, 4th-order zero-phase
Butterworth filtering, peak-to-peak instantaneous HR resampling to 30 Hz,
and 7 sliding-window physiological features + RMSSD_rr.
"""
from __future__ import annotations
import math
from typing import Dict, List, Optional, Tuple, Sequence, Any
import cv2
import numpy as np
from scipy import signal
from scipy.special import expit
try:
    from scipy.integrate import trapezoid
except ImportError:
    trapezoid = np.trapz

# 7 pulse features mirroring Table 2 in Maaoui et al. (2020)
PULSE_FEATURES = (
    'meanHR',   # Mean heart rate (bpm)
    'StdHR',    # Standard deviation of heart rate (bpm)
    'DerHR',    # Mean first difference of heart rate trace (bpm)
    'RMSSD',    # Root mean square of successive differences of HR trace
    'LF',       # Low frequency power (0.04 - 0.15 Hz) via Welch PSD
    'HF',       # High frequency power (0.15 - 0.35 Hz) via Welch PSD
    'LF_HF',    # Ratio of LF to HF power
)

# Feature groups for ablation analysis
TIME_FEATURES = ('meanHR', 'StdHR', 'DerHR', 'RMSSD')
FREQ_FEATURES = ('LF', 'HF', 'LF_HF')

# Direction of stress response fixed in code:
# Increased stress -> higher HR, higher variability/derivatives, lower RMSSD/HF (vagal withdrawal), higher LF and LF/HF.
PULSE_SIGNS: Dict[str, float] = {
    'meanHR': 1.0,
    'StdHR': 1.0,
    'DerHR': 1.0,
    'RMSSD': -1.0,
    'HF': -1.0,
    'LF': 1.0,
    'LF_HF': 1.0,
}

# Quality gate constants
MIN_FPS = 15.0
MIN_VALID_RATIO = 0.80
SNR_MIN = 2.0  # Minimum spectral peak SNR in the cardiac band (0.65 - 3.0 Hz)
CARDIAC_BAND = (0.65, 3.0)  # 39 to 180 bpm

# MediaPipe landmark indices for skin ROIs
ROI_FOREHEAD = (10, 109, 108, 9, 337, 338)
ROI_LEFT_CHEEK = (50, 101, 205, 187)
ROI_RIGHT_CHEEK = (280, 330, 425, 411)


def extract_roi_signal(frame: np.ndarray, landmarks: np.ndarray, channel: str = 'u') -> float:
    """Extract spatial average over skin ROI (forehead + both cheeks) from MediaPipe landmarks.
    
    channel: 'u' (CIE L*u*v* u* channel, default) or 'green' (BGR green channel).
    """
    if landmarks is None or not np.all(np.isfinite(landmarks)):
        return np.nan
    h, w = frame.shape[:2]
    pts = landmarks[:, :2].astype(np.int32)
    pts[:, 0] = np.clip(pts[:, 0], 0, w - 1)
    pts[:, 1] = np.clip(pts[:, 1], 0, h - 1)
    
    mask = np.zeros((h, w), dtype=np.uint8)
    for ids in (ROI_FOREHEAD, ROI_LEFT_CHEEK, ROI_RIGHT_CHEEK):
        hull = cv2.convexHull(pts[list(ids)])
        if len(hull) >= 3:
            cv2.fillConvexPoly(mask, hull, 255)
            
    if not np.any(mask):
        return np.nan
        
    if channel.lower() == 'green':
        return float(cv2.mean(frame[:, :, 1], mask=mask)[0])
    else:
        # CIE L*u*v* conversion: channel 1 is u*
        luv = cv2.cvtColor(frame, cv2.COLOR_BGR2Luv)
        return float(cv2.mean(luv[:, :, 1], mask=mask)[0])


def cwt_clean_signal(sig: np.ndarray, fps: float, freqs: Optional[np.ndarray] = None) -> np.ndarray:
    """Optional continuous-wavelet cleaning via Morlet wavelet bank in the cardiac band."""
    if freqs is None:
        freqs = np.linspace(CARDIAC_BAND[0], CARDIAC_BAND[1], 25)
    n = len(sig)
    reconstructed = np.zeros(n)
    w_len = min(n, int(fps * 2.0))
    if w_len % 2 == 0:
        w_len += 1
    t = np.arange(-(w_len // 2), (w_len // 2) + 1) / fps
    
    for f in freqs:
        omega = 2 * np.pi * f
        wavelet = np.exp(1j * omega * t) * np.exp(-0.5 * (t * omega / 5.0) ** 2)
        real_wavelet = np.real(wavelet) / (np.sum(np.abs(np.real(wavelet))) + 1e-12)
        conv = signal.convolve(sig, real_wavelet, mode='same')
        reconstructed += conv
        
    return reconstructed / max(len(freqs), 1)


def filter_signal(raw_signal: np.ndarray, fps: float, cwt_clean: bool = False) -> np.ndarray:
    """Detrend and bandpass 0.65-3.0 Hz (4th-order Butterworth, zero-phase)."""
    raw = np.asarray(raw_signal, float)
    if len(raw) < 15 or fps < MIN_FPS or np.all(np.isnan(raw)):
        return np.full_like(raw, np.nan)
        
    # Interpolate isolated missing values for filtering
    valid = np.isfinite(raw)
    if valid.sum() < 0.5 * len(raw):
        return np.full_like(raw, np.nan)
    x = np.arange(len(raw))
    interpolated = np.interp(x, x[valid], raw[valid])
    
    # Detrend
    detrended = signal.detrend(interpolated, type='linear')
    
    # 4th-order Butterworth zero-phase bandpass filter between 0.65 Hz and 3.0 Hz
    sos = signal.butter(4, list(CARDIAC_BAND), btype='bandpass', fs=fps, output='sos')
    filtered = signal.sosfiltfilt(sos, detrended)
    
    if cwt_clean:
        filtered = cwt_clean_signal(filtered, fps)
        
    return filtered


def check_spectral_snr(filtered_segment: np.ndarray, fps: float, snr_min: float = SNR_MIN) -> Tuple[bool, float]:
    """Quality check: spectral peak SNR in cardiac band above threshold."""
    if len(filtered_segment) < int(fps * 4) or not np.all(np.isfinite(filtered_segment)):
        return False, 0.0
    nperseg = min(len(filtered_segment), int(fps * 10))
    if nperseg < 8:
        return False, 0.0
    f, pxx = signal.welch(filtered_segment, fs=fps, nperseg=nperseg)
    band = (f >= CARDIAC_BAND[0]) & (f <= CARDIAC_BAND[1])
    if not np.any(band):
        return False, 0.0
    peak_p = float(np.max(pxx[band]))
    median_p = float(np.median(pxx[band]))
    snr = peak_p / max(median_p, 1e-12)
    return snr >= snr_min, snr


def compute_pulse_trace(filtered: np.ndarray, times: np.ndarray, fps: float) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Detect peaks, compute instantaneous HR, and resample to 30 Hz by linear interpolation.
    
    Returns: (t_30hz, hr_trace_30hz, peak_times)
    """
    if len(filtered) < 15 or len(times) < 15 or not np.all(np.isfinite(filtered)):
        return np.array([]), np.array([]), np.array([])
        
    # scipy.signal.find_peaks with min distance from 3 Hz
    min_dist = max(1, int(fps / CARDIAC_BAND[1]))
    peaks, _ = signal.find_peaks(filtered, distance=min_dist)
    if len(peaks) < 2:
        return np.array([]), np.array([]), np.array([])
        
    peak_times = times[peaks]
    ibi = np.diff(peak_times)  # in seconds
    
    # Exclude non-physiological intervals outside [1/3.0, 1/0.65] s
    valid_ibi = (ibi >= 1.0 / CARDIAC_BAND[1]) & (ibi <= 1.0 / CARDIAC_BAND[0])
    if valid_ibi.sum() < 2:
        return np.array([]), np.array([]), np.array([])
        
    inst_hr = 60.0 / ibi
    hr_midpoints = (peak_times[:-1] + peak_times[1:]) / 2.0
    
    # Resample to 30 Hz by linear interpolation
    t_start = float(times[0])
    t_end = float(times[-1])
    t_30hz = np.arange(t_start, t_end, 1.0 / 30.0)
    if len(t_30hz) == 0:
        return np.array([]), np.array([]), np.array([])
        
    hr_trace_30hz = np.interp(t_30hz, hr_midpoints[valid_ibi], inst_hr[valid_ibi],
                              left=float(inst_hr[valid_ibi][0]), right=float(inst_hr[valid_ibi][-1]))
                              
    return t_30hz, hr_trace_30hz, peak_times


def compute_window_features(w_hr: np.ndarray, peaks_in_window: np.ndarray, fps_hr: float = 30.0) -> Dict[str, float]:
    """Compute the 7 paper features + RMSSD_rr on a 30 s window of HR trace."""
    if len(w_hr) < int(fps_hr * 10) or not np.all(np.isfinite(w_hr)):
        return {k: np.nan for k in (*PULSE_FEATURES, 'RMSSD_rr')}
        
    mean_hr = float(np.mean(w_hr))
    std_hr = float(np.std(w_hr, ddof=1)) if len(w_hr) > 1 else 0.0
    d_hr = np.diff(w_hr)
    der_hr = float(np.mean(d_hr)) if len(d_hr) > 0 else 0.0
    rmssd = float(np.sqrt(np.mean(d_hr ** 2))) if len(d_hr) > 0 else 0.0
    
    # Welch PSD on zero-mean HR trace resampled at 30 Hz
    nperseg = min(len(w_hr), int(fps_hr * 16))
    f, pxx = signal.welch(w_hr - mean_hr, fs=fps_hr, nperseg=nperseg)
    
    lf_mask = (f >= 0.04) & (f <= 0.15)
    hf_mask = (f >= 0.15) & (f <= 0.35)
    
    lf = float(trapezoid(pxx[lf_mask], f[lf_mask])) if np.any(lf_mask) else 0.0
    hf = float(trapezoid(pxx[hf_mask], f[hf_mask])) if np.any(hf_mask) else 0.0
    lf_hf = float(lf / (hf + 1e-8))
    
    # RMSSD_rr: standard RMSSD from inter-beat intervals in milliseconds
    if len(peaks_in_window) >= 2:
        ibis_ms = np.diff(peaks_in_window) * 1000.0
        d_ibi = np.diff(ibis_ms)
        rmssd_rr = float(np.sqrt(np.mean(d_ibi ** 2))) if len(d_ibi) > 0 else np.nan
    else:
        rmssd_rr = np.nan
        
    return {
        'meanHR': mean_hr,
        'StdHR': std_hr,
        'DerHR': der_hr,
        'RMSSD': rmssd,
        'LF': lf,
        'HF': hf,
        'LF_HF': lf_hf,
        'RMSSD_rr': rmssd_rr,
    }


def extract_sliding_windows(
    times: np.ndarray,
    filtered_signal: np.ndarray,
    valid_face_mask: np.ndarray,
    fps: float,
    window_sec: float = 30.0,
    step_sec: float = 2.0,
    snr_min: float = SNR_MIN,
) -> List[Dict[str, Any]]:
    """Compute sliding 30 s windows (step 2 s) with quality gating.
    
    Quality gate: require FPS >= 15, >= 80% valid face frames in window,
    spectral peak SNR >= SNR_MIN. Failed windows are missing (NaN), not imputed.
    """
    times = np.asarray(times, float)
    n = len(times)
    if n == 0:
        return []
        
    t_start = float(times[0])
    t_end = float(times[-1])
    
    # Compute 30 Hz HR trace across entire signal
    t_30hz, hr_trace, peak_times = compute_pulse_trace(filtered_signal, times, fps)
    
    windows = []
    w_start = t_start
    while w_start + window_sec <= t_end + 1e-6:
        w_end = w_start + window_sec
        w_center = w_start + window_sec / 2.0
        
        # Frame indices in this window
        f_mask = (times >= w_start) & (times < w_end)
        total_frames = int(np.sum(f_mask))
        valid_frames = int(np.sum(valid_face_mask[f_mask])) if total_frames > 0 else 0
        valid_ratio = valid_frames / max(total_frames, 1)
        
        # Quality gates
        fps_ok = fps >= MIN_FPS
        ratio_ok = valid_ratio >= MIN_VALID_RATIO
        
        snr_ok, snr_val = False, 0.0
        if fps_ok and ratio_ok and total_frames > 0:
            sig_segment = filtered_signal[f_mask]
            snr_ok, snr_val = check_spectral_snr(sig_segment, fps, snr_min=snr_min)
            
        gate_passed = fps_ok and ratio_ok and snr_ok
        
        row: Dict[str, Any] = {
            'time': w_center,
            'start_time': w_start,
            'end_time': w_end,
            'fps': fps,
            'valid_ratio': valid_ratio,
            'snr': snr_val,
            'gate_passed': gate_passed,
        }
        
        if gate_passed and len(t_30hz) > 0:
            hr_mask = (t_30hz >= w_start) & (t_30hz < w_end)
            w_hr = hr_trace[hr_mask]
            w_peaks = peak_times[(peak_times >= w_start) & (peak_times < w_end)]
            feats = compute_window_features(w_hr, w_peaks)
            row.update(feats)
        else:
            # Failed windows are missing, not imputed
            for k in (*PULSE_FEATURES, 'RMSSD_rr'):
                row[k] = np.nan
                
        windows.append(row)
        w_start += step_sec
        
    return windows


class PulseIndex:
    """Training-free personal baseline calibration and scoring for pulse features.
    
    Baseline = designated 25 s rest window: mean and std per pulse feature,
    with the existing sigma floor max(raw_sd, 0.05 * abs(mu) + 1e-3).
    z clipped to [-3, 3].
    Signs fixed in code: meanHR +, StdHR +, DerHR +, RMSSD -, HF -, LF +, LF/HF +.
    Pulse score P = 100 * sigmoid(mean(signed_z)).
    """
    def __init__(self, baseline_windows: Sequence[Dict[str, Any]], selected: Sequence[str] = PULSE_FEATURES):
        self.selected = tuple(selected)
        self.mu: Dict[str, float] = {}
        self.sd: Dict[str, float] = {}
        self.raw_sd: Dict[str, float] = {}
        
        for k in self.selected:
            vals = np.array([w[k] for w in baseline_windows if k in w and np.isfinite(w[k])], float)
            if len(vals) >= 1:
                self.mu[k] = float(np.mean(vals))
                raw = float(np.std(vals)) if len(vals) > 1 else 0.0
                self.raw_sd[k] = raw
                # Existing sigma floor formula
                self.sd[k] = max(raw, 0.05 * abs(self.mu[k]) + 1e-3)
                
    def score(self, window_record: Dict[str, Any]) -> float:
        """Compute training-free pulse score P for a window record."""
        keys = [k for k in self.selected if k in self.mu and np.isfinite(window_record.get(k, np.nan))]
        if not keys:
            return np.nan
            
        signed_zs = []
        for k in keys:
            val = float(window_record[k])
            z = np.clip((val - self.mu[k]) / (self.sd[k] + 1e-6), -3.0, 3.0)
            sign = PULSE_SIGNS.get(k, 1.0)
            signed_zs.append(sign * z)
            
        mean_signed_z = float(np.mean(signed_zs))
        # P = sigmoid of equal-weight mean of signed z, scaled to 0-100
        return float(100.0 * expit(mean_signed_z))
