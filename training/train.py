"""Train on half the participants; evaluate on the untouched other half.

Input must be real extracted video features, not synthetic observations.
No pickle loading; model exports numeric coefficients and documented metrics.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import numpy as np
from sklearn.dummy import DummyClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, precision_score, recall_score, f1_score, confusion_matrix, roc_auc_score, brier_score_loss
from sklearn.model_selection import GroupKFold, cross_val_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

FEATURES = ['meanBlinkCoefficient', 'meanBrowCoefficient', 'meanMovement']

def metrics(y, prediction, probability):
    return {'accuracy': accuracy_score(y, prediction),
            'balanced_accuracy': balanced_accuracy_score(y, prediction),
            'precision': precision_score(y, prediction, zero_division=0),
            'recall': recall_score(y, prediction, zero_division=0),
            'f1': f1_score(y, prediction, zero_division=0),
            'confusion_matrix_labels': [0, 1],
            'confusion_matrix': confusion_matrix(y, prediction, labels=[0, 1]).tolist(),
            'roc_auc': roc_auc_score(y, probability),
            'brier_score': brier_score_loss(y, probability)}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--csv', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=Path('artifacts'))
    parser.add_argument('--dataset-name', required=True)
    parser.add_argument('--label-definition', required=True)
    parser.add_argument('--license-note', required=True)
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()
    with args.csv.open() as handle:
        rows = list(csv.DictReader(handle))
    required = {'participant_id', 'label', *FEATURES}
    if not rows or not required.issubset(rows[0]):
        raise ValueError('Required columns: ' + ', '.join(sorted(required)))
    groups = np.array([row['participant_id'] for row in rows])
    y = np.array([int(row['label']) for row in rows])
    x = np.array([[float(row[f]) for f in FEATURES] for row in rows])
    if not np.isfinite(x).all() or set(y) != {0, 1}:
        raise ValueError('Require finite features and both binary labels 0 and 1')
    if not ((x[:, :2] >= 0) & (x[:, :2] <= 1)).all() or (x[:, 2] < 0).any():
        raise ValueError('Features must match the browser coefficient definitions')
    participants = np.unique(groups)
    if len(participants) < 8:
        raise ValueError('Need at least 8 participants for this experimental split')
    rng = np.random.default_rng(args.seed)
    rng.shuffle(participants)
    train_people = participants[:len(participants)//2]
    train = np.isin(groups, train_people)
    test = ~train
    if set(y[train]) != {0, 1} or set(y[test]) != {0, 1}:
        raise ValueError('Both participant partitions must contain both labels')
    cv = GroupKFold(n_splits=min(5, len(train_people)))
    folds = list(cv.split(x[train], y[train], groups[train]))
    if any(set(y[train][a]) != {0,1} or set(y[train][b]) != {0,1} for a,b in folds):
        raise ValueError('CV folds must contain both labels; review participant coverage')
    candidates = []
    for c in [.01, .1, 1, 10]:
        model = make_pipeline(StandardScaler(), LogisticRegression(C=c, class_weight='balanced', max_iter=2000, random_state=args.seed))
        score = float(cross_val_score(model, x[train], y[train], cv=folds, scoring='balanced_accuracy').mean())
        candidates.append((score, c, model))
    cv_score, c, model = max(candidates, key=lambda item: item[0])
    model.fit(x[train], y[train])
    probabilities = model.predict_proba(x[test])[:, 1]
    result = metrics(y[test], model.predict(x[test]), probabilities)
    dummy = DummyClassifier(strategy='prior').fit(x[train], y[train])
    baseline = metrics(y[test], dummy.predict(x[test]), dummy.predict_proba(x[test])[:, 1])
    # Bootstrap whole held-out people, preserving within-person dependence.
    held_out = participants[len(train_people):]
    boot = []
    prediction = model.predict(x[test]); test_y=y[test]; test_groups=groups[test]
    for _ in range(1000):
        sampled = rng.choice(held_out, len(held_out), replace=True)
        index = np.concatenate([np.flatnonzero(test_groups == person) for person in sampled])
        if len(np.unique(test_y[index])) == 2:
            boot.append(balanced_accuracy_score(test_y[index], prediction[index]))
    scaler, logistic = model.steps[0][1], model.steps[1][1]
    report = {'dataset': args.dataset_name, 'label_definition': args.label_definition,
              'license_note': args.license_note, 'input_sha256': hashlib.sha256(args.csv.read_bytes()).hexdigest(),
              'seed': args.seed, 'features': FEATURES, 'train_participants': train_people.tolist(),
              'test_participants': held_out.tolist(), 'train_rows': int(train.sum()), 'test_rows': int(test.sum()),
              'train_fraction_participants': len(train_people)/len(participants),
              'selected_C': c, 'training_group_cv_balanced_accuracy': cv_score,
              'held_out_metrics': result, 'dummy_baseline': baseline,
              'balanced_accuracy_95pct_participant_bootstrap': np.quantile(boot,[.025,.975]).tolist() if boot else None,
              'limitations': ['Laboratory task labels may be proxies for stress.', 'Facial behavior can reveal speech/task differences rather than stress.', 'No real-world or clinical validity established.', 'Do not tune this model against the held-out test set.']}
    artifact = {'features': FEATURES, 'mean': scaler.mean_.tolist(), 'scale': scaler.scale_.tolist(),
                'coefficients': logistic.coef_[0].tolist(), 'intercept': float(logistic.intercept_[0]),
                'threshold': .5, 'experimental': True, 'report': 'metrics.json'}
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output/'metrics.json').write_text(json.dumps(report, indent=2))
    (args.output/'model.json').write_text(json.dumps(artifact, indent=2))
    print(json.dumps({'held_out_metrics': result, 'dummy_baseline': baseline}, indent=2))

if __name__ == '__main__':
    main()
