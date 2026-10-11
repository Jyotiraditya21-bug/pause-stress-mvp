"""Supervised reference evaluation for pulse features (LOSO vs Random Split).

NOT our method; clearly labeled as a supervised comparator to quantify leakage.
Leave-one-subject-out (LOSO) vs. random window split using SVM (RBF) and LDA
on the 7 physiological pulse features.
"""
from __future__ import annotations
from typing import Dict, List, Any, Optional, Sequence, Tuple
import numpy as np
from sklearn.svm import SVC
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import LeaveOneGroupOut, StratifiedKFold
from sklearn.metrics import accuracy_score, roc_auc_score, f1_score

from .pulse_features import PULSE_FEATURES


def evaluate_supervised(
    window_records: Sequence[Dict[str, Any]],
    features: Sequence[str] = PULSE_FEATURES,
    seed: int = 42,
) -> Dict[str, Any]:
    """Run LOSO vs Random split using SVM (RBF) and LDA on pulse features.
    
    Standardized inside each fold, default hyperparameters (C=1, gamma='scale'),
    no tuning on held-out subject.
    """
    usable = [
        r for r in window_records
        if not r.get('excluded', False)
        and r.get('label') in (0, 1)
        and all(np.isfinite(r.get(k, np.nan)) for k in features)
        and r.get('subject_id') is not None
    ]
    
    if not usable:
        return {
            'status': 'unavailable: no eligible window records with complete features and labels',
            'records_count': 0,
            'table': '| Method | split | accuracy | AUC | F1 |\n|---|---|---|---|---|\n| N/A | N/A | N/A | N/A | N/A |',
            'summary': {},
            'leakage_gap': {},
        }
        
    X = np.array([[r[k] for k in features] for r in usable], float)
    y = np.array([int(r['label']) for r in usable], int)
    subjects = np.array([str(r['subject_id']) for r in usable])
    
    unique_labels = np.unique(y)
    unique_subjects = np.unique(subjects)
    
    if len(unique_labels) < 2 or len(unique_subjects) < 2:
        return {
            'status': 'unavailable: requires at least 2 distinct subjects and 2 task classes',
            'records_count': len(usable),
            'subjects_count': len(unique_subjects),
            'table': '| Method | split | accuracy | AUC | F1 |\n|---|---|---|---|---|\n| N/A | N/A | N/A | N/A | N/A |',
            'summary': {},
            'leakage_gap': {},
        }
        
    results: Dict[str, Dict[str, Any]] = {
        'SVM (RBF)': {},
        'LDA': {},
    }
    
    # -------------------------------------------------------------
    # 1. Leave-One-Subject-Out (LOSO) - Participant-Separated
    # -------------------------------------------------------------
    logo = LeaveOneGroupOut()
    loso_preds = {'SVM (RBF)': [], 'LDA': []}
    loso_probs = {'SVM (RBF)': [], 'LDA': []}
    loso_y_true = []
    
    for train_idx, test_idx in logo.split(X, y, groups=subjects):
        # Strict verification: held-out subject is never in train
        train_subs = set(subjects[train_idx])
        test_subs = set(subjects[test_idx])
        assert train_subs.isdisjoint(test_subs), "LOSO error: subject leakage in training set!"
        
        y_train = y[train_idx]
        y_test = y[test_idx]
        
        # Standardize inside fold
        scaler = StandardScaler()
        X_tr = scaler.fit_transform(X[train_idx])
        X_te = scaler.transform(X[test_idx])
        
        # If train fold contains only one class, skip probability estimation
        has_both_classes = len(np.unique(y_train)) == 2
        
        # SVM (RBF)
        svm = SVC(kernel='rbf', C=1.0, gamma='scale', probability=True, random_state=seed)
        if has_both_classes:
            svm.fit(X_tr, y_train)
            loso_preds['SVM (RBF)'].extend(svm.predict(X_te).tolist())
            loso_probs['SVM (RBF)'].extend(svm.predict_proba(X_te)[:, 1].tolist())
        else:
            loso_preds['SVM (RBF)'].extend([y_train[0]] * len(y_test))
            loso_probs['SVM (RBF)'].extend([float(y_train[0])] * len(y_test))
            
        # LDA
        lda = LinearDiscriminantAnalysis()
        if has_both_classes:
            lda.fit(X_tr, y_train)
            loso_preds['LDA'].extend(lda.predict(X_te).tolist())
            loso_probs['LDA'].extend(lda.predict_proba(X_te)[:, 1].tolist())
        else:
            loso_preds['LDA'].extend([y_train[0]] * len(y_test))
            loso_probs['LDA'].extend([float(y_train[0])] * len(y_test))
            
        loso_y_true.extend(y_test.tolist())
        
    y_true_arr = np.array(loso_y_true, int)
    for model_name in ('SVM (RBF)', 'LDA'):
        preds = np.array(loso_preds[model_name], int)
        probs = np.array(loso_probs[model_name], float)
        acc = float(accuracy_score(y_true_arr, preds))
        f1 = float(f1_score(y_true_arr, preds, zero_division=0))
        auc = float(roc_auc_score(y_true_arr, probs)) if len(np.unique(y_true_arr)) == 2 else None
        results[model_name]['LOSO'] = {
            'accuracy': acc,
            'roc_auc': auc,
            'f1': f1,
            'n': len(y_true_arr),
        }
        
    # -------------------------------------------------------------
    # 2. Random Window Split (Paper's protocol - Subject Leakage)
    # -------------------------------------------------------------
    n_splits = min(5, len(usable))
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    rand_preds = {'SVM (RBF)': [], 'LDA': []}
    rand_probs = {'SVM (RBF)': [], 'LDA': []}
    rand_y_true = []
    
    for train_idx, test_idx in skf.split(X, y):
        y_train = y[train_idx]
        y_test = y[test_idx]
        
        scaler = StandardScaler()
        X_tr = scaler.fit_transform(X[train_idx])
        X_te = scaler.transform(X[test_idx])
        
        has_both = len(np.unique(y_train)) == 2
        
        # SVM (RBF)
        svm = SVC(kernel='rbf', C=1.0, gamma='scale', probability=True, random_state=seed)
        if has_both:
            svm.fit(X_tr, y_train)
            rand_preds['SVM (RBF)'].extend(svm.predict(X_te).tolist())
            rand_probs['SVM (RBF)'].extend(svm.predict_proba(X_te)[:, 1].tolist())
        else:
            rand_preds['SVM (RBF)'].extend([y_train[0]] * len(y_test))
            rand_probs['SVM (RBF)'].extend([float(y_train[0])] * len(y_test))
            
        # LDA
        lda = LinearDiscriminantAnalysis()
        if has_both:
            lda.fit(X_tr, y_train)
            rand_preds['LDA'].extend(lda.predict(X_te).tolist())
            rand_probs['LDA'].extend(lda.predict_proba(X_te)[:, 1].tolist())
        else:
            rand_preds['LDA'].extend([y_train[0]] * len(y_test))
            rand_probs['LDA'].extend([float(y_train[0])] * len(y_test))
            
        rand_y_true.extend(y_test.tolist())
        
    y_true_rand_arr = np.array(rand_y_true, int)
    for model_name in ('SVM (RBF)', 'LDA'):
        preds = np.array(rand_preds[model_name], int)
        probs = np.array(rand_probs[model_name], float)
        acc = float(accuracy_score(y_true_rand_arr, preds))
        f1 = float(f1_score(y_true_rand_arr, preds, zero_division=0))
        auc = float(roc_auc_score(y_true_rand_arr, probs)) if len(np.unique(y_true_rand_arr)) == 2 else None
        results[model_name]['random'] = {
            'accuracy': acc,
            'roc_auc': auc,
            'f1': f1,
            'n': len(y_true_rand_arr),
        }
        
    # Leakage gap calculation
    leakage_gap = {}
    for model_name in ('SVM (RBF)', 'LDA'):
        loso_acc = results[model_name]['LOSO']['accuracy']
        rand_acc = results[model_name]['random']['accuracy']
        loso_auc = results[model_name]['LOSO']['roc_auc']
        rand_auc = results[model_name]['random']['roc_auc']
        
        leakage_gap[model_name] = {
            'accuracy_difference': float(rand_acc - loso_acc) if rand_acc is not None and loso_acc is not None else None,
            'auc_difference': float(rand_auc - loso_auc) if rand_auc is not None and loso_auc is not None else None,
        }
        
    # Format required Markdown Table: Method | split | accuracy | AUC | F1
    lines = [
        "| Method | split | accuracy | AUC | F1 |",
        "|---|---|---|---|---|",
    ]
    for model_name in ('SVM (RBF)', 'LDA'):
        loso_info = results[model_name]['LOSO']
        rand_info = results[model_name]['random']
        loso_auc_str = f"{loso_info['roc_auc']:.3f}" if loso_info['roc_auc'] is not None else "N/A"
        rand_auc_str = f"{rand_info['roc_auc']:.3f}" if rand_info['roc_auc'] is not None else "N/A"
        lines.append(
            f"| {model_name} (supervised ref) | LOSO (subject-separated) | "
            f"{loso_info['accuracy']:.3f} | {loso_auc_str} | {loso_info['f1']:.3f} |"
        )
        lines.append(
            f"| {model_name} (supervised ref) | Random window split (leaked) | "
            f"{rand_info['accuracy']:.3f} | {rand_auc_str} | {rand_info['f1']:.3f} |"
        )
        
    table_str = "\n".join(lines)
    
    return {
        'status': 'complete',
        'records_count': len(usable),
        'subjects_count': len(unique_subjects),
        'table': table_str,
        'summary': results,
        'leakage_gap': leakage_gap,
    }
