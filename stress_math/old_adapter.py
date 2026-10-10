"""Existing repository has camera summaries, not a video stress score."""
import numpy as np

def score_video(path, shared_frames):
    return np.full(len(shared_frames['times']),np.nan)

REASON='OLD has no video scorer. Existing scanMetrics.js returns quality and mean blink/brow/movement coefficients. Questionnaire stress is self-reported, not video-derived. OLD stress metrics are unavailable.'
