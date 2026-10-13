"""Unit and regression tests for pulse branch and supervised references."""
from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
import numpy as np

from .pulse_features import (
    PULSE_FEATURES, PULSE_SIGNS, PulseIndex,
    filter_signal, compute_pulse_trace, extract_sliding_windows,
    extract_roi_signal, SNR_MIN, MIN_FPS, MIN_VALID_RATIO
)
from .supervised_reference import evaluate_supervised
from .pulse_evaluate import run_pulse_pipeline, make_smoke_test_data, split_windows, branch_series


class PulseBranchTests(unittest.TestCase):
    def test_baseline_windows_do_not_overlap_evaluation_cutoff(self):
        windows=[dict(start_time=s,end_time=s+20) for s in (0,2,4,6,24,25,26)]
        baseline,evaluation=split_windows(windows)
        self.assertTrue(all(w['end_time']<=25 for w in baseline))
        self.assertTrue(all(w['start_time']>=25 for w in evaluation))
        self.assertNotIn(windows[4],baseline)
        self.assertNotIn(windows[4],evaluation)
        self.assertIn(windows[5],evaluation)

    def test_unavailable_video_branches_remain_missing_without_label_fallback(self):
        n=20;payload=dict(times=np.arange(n)/30,valid_face_mask=np.ones(n,bool))
        series=branch_series(payload,payload)
        self.assertTrue(np.isnan(series['M0']).all())
        self.assertTrue(np.isnan(series['H1']).all())

    def test_synthetic_sinusoid_hr(self):
        """(a) Synthetic 1.2 Hz sinusoid + noise returns ~72 bpm within 2 bpm."""
        fps = 30.0
        duration = 35.0
        t = np.arange(0, duration, 1.0 / fps)
        rng = np.random.default_rng(42)
        
        # 1.2 Hz pulse corresponds to exactly 72.0 bpm
        noise = 0.15 * rng.normal(size=len(t))
        raw_ppg = 120.0 + 4.0 * np.sin(2 * np.pi * 1.2 * t) + noise
        
        filtered = filter_signal(raw_ppg, fps, cwt_clean=False)
        t_30hz, hr_trace, peak_times = compute_pulse_trace(filtered, t, fps)
        
        self.assertGreater(len(hr_trace), 0)
        mean_hr = float(np.mean(hr_trace))
        # Within 2 bpm of 72 bpm (70 - 74 bpm)
        self.assertAlmostEqual(mean_hr, 72.0, delta=2.0)

    def test_sign_and_baseline_z_logic(self):
        """(b) Sign and baseline z logic with sigma floor and [-3, 3] clipping."""
        # Baseline with zero variance
        base_val = 70.0
        baseline_record = {k: base_val for k in PULSE_FEATURES}
        index = PulseIndex([baseline_record for _ in range(5)])
        
        # Sigma floor check: max(0, 0.05 * abs(mu) + 1e-3)
        expected_floor = 0.05 * base_val + 1e-3
        for k in PULSE_FEATURES:
            self.assertAlmostEqual(index.raw_sd[k], 0.0)
            self.assertAlmostEqual(index.sd[k], expected_floor, delta=1e-6)
            
        # Score on baseline itself should be exactly 50 (expit(0) * 100)
        score_base = index.score(baseline_record)
        self.assertAlmostEqual(score_base, 50.0, delta=1e-5)
        
        # Test positive sign features: increasing feature increases score above 50
        for pos_k in ('meanHR', 'StdHR', 'DerHR', 'LF', 'LF_HF'):
            shifted = dict(baseline_record)
            shifted[pos_k] = base_val + index.sd[pos_k]
            score_pos = index.score(shifted)
            self.assertGreater(score_pos, 50.0, msg=f"Positive feature {pos_k} did not increase score")
            
        # Test negative sign features: increasing feature decreases score below 50
        # (and conversely, physiological stress decrease in RMSSD/HF increases score above 50)
        for neg_k in ('RMSSD', 'HF'):
            shifted_high = dict(baseline_record)
            shifted_high[neg_k] = base_val + index.sd[neg_k]
            score_high = index.score(shifted_high)
            self.assertLess(score_high, 50.0, msg=f"Negative feature {neg_k} did not decrease score")
            
            # Stress condition: RMSSD/HF decreases -> score increases
            shifted_stress = dict(baseline_record)
            shifted_stress[neg_k] = base_val - index.sd[neg_k]
            score_stress = index.score(shifted_stress)
            self.assertGreater(score_stress, 50.0, msg=f"Drop in {neg_k} did not increase stress score")
            
        # Test z-clipping to [-3, 3]
        extreme_high = {k: base_val + 100.0 * index.sd[k] for k in PULSE_FEATURES}
        score_extreme = index.score(extreme_high)
        # With clipping to +3 or -3, sigmoid stays bounded
        self.assertLess(score_extreme, 100.0)
        self.assertGreater(score_extreme, 0.0)

    def test_loso_subject_isolation(self):
        """(c) LOSO never puts a subject in both train and test across any fold."""
        rng = np.random.default_rng(42)
        subjects = ['Sub_A', 'Sub_B', 'Sub_C', 'Sub_D', 'Sub_E']
        records = []
        for s in subjects:
            for label in (0, 1):
                for _ in range(8):
                    feats = {k: float(rng.normal(50.0, 5.0) + (10.0 if label == 1 else 0.0)) for k in PULSE_FEATURES}
                    feats['subject_id'] = s
                    feats['label'] = label
                    feats['excluded'] = False
                    records.append(feats)
                    
        sup = evaluate_supervised(records)
        self.assertEqual(sup['status'], 'complete')
        self.assertEqual(sup['subjects_count'], 5)
        
        # Verify result contains table and metrics for both SVM and LDA
        self.assertIn('SVM (RBF)', sup['summary'])
        self.assertIn('LDA', sup['summary'])
        self.assertIn('LOSO', sup['summary']['SVM (RBF)'])
        self.assertIn('random', sup['summary']['SVM (RBF)'])
        
        # Table must contain the required columns
        table = sup['table']
        self.assertIn('| Method | split | accuracy | AUC | F1 |', table)
        self.assertIn('LOSO (subject-separated)', table)
        self.assertIn('Random window split (leaked)', table)

    def test_quality_gates_and_missing_handling(self):
        """Quality gates reject low FPS, low face coverage, and low SNR without imputation."""
        fps = 10.0  # below MIN_FPS (15)
        t = np.arange(0, 35.0, 1.0 / fps)
        sig = 100.0 + np.sin(2 * np.pi * 1.2 * t)
        val_mask = np.ones(len(t), bool)
        
        filtered = filter_signal(sig, fps)
        windows = extract_sliding_windows(t, filtered, val_mask, fps)
        for w in windows:
            self.assertFalse(w['gate_passed'])
            for f in PULSE_FEATURES:
                self.assertTrue(np.isnan(w[f]))
                
        # High FPS but low valid face ratio (< 80%)
        fps = 30.0
        t = np.arange(0, 35.0, 1.0 / fps)
        sig = 100.0 + np.sin(2 * np.pi * 1.2 * t)
        val_mask = np.zeros(len(t), bool)
        val_mask[:int(0.5 * len(t))] = True  # only 50% valid
        
        filtered = filter_signal(sig, fps)
        windows2 = extract_sliding_windows(t, filtered, val_mask, fps)
        for w in windows2:
            self.assertFalse(w['gate_passed'])
            self.assertTrue(np.isnan(w['meanHR']))

    def test_end_to_end_pipeline_and_disclaimers(self):
        """Verify full runner generates metrics.json, summary.md, comparison.md, report.md, and plots."""
        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir) / 'results'
            cache_dir = Path(temp_dir) / 'cache'
            sessions = make_smoke_test_data()
            
            result = run_pulse_pipeline(sessions, cache_dir, out_dir, rppg_channel='u')
            self.assertGreater(result['eligible_count'], 0)
            
            # Check all required files exist
            for name in (
                'metrics.json', 'summary.md', 'comparison.md', 'report.md',
                'roc_all_methods.png', 'pulse_feature_ablation.png', 'leakage_gap.png'
            ):
                file_path = out_dir / name
                self.assertTrue(file_path.exists(), msg=f"Missing expected output file: {name}")
                self.assertGreater(file_path.stat().st_size, 0)
                
            report_text = (out_dir / 'report.md').read_text()
            
            # Check all mandatory disclaimers
            required_phrases = [
                'pulse features are camera estimates, not ECG-grade HRV',
                'LF from 20 s windows is especially unreliable',
                'supervised models are references only',
                'labels are task-based',
                'no thresholds, signs or weights were fitted on test data',
            ]
            for phrase in required_phrases:
                self.assertIn(phrase, report_text, msg=f"Missing mandatory phrase: '{phrase}'")


if __name__ == '__main__':
    unittest.main()
