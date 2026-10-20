"""Evaluate an existing ONNX export; never train, select models or optimize thresholds.

Outputs contain dataset predictions: keep them outside the public repository.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import time

import numpy as np
from PIL import Image
import onnxruntime as ort
from sklearn.metrics import (roc_auc_score, accuracy_score, balanced_accuracy_score,
                             precision_score, recall_score, f1_score, brier_score_loss,
                             confusion_matrix)
from torchvision.models import MobileNet_V3_Small_Weights


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def metrics(y, probability):
    pred = probability > .5
    return dict(roc_auc=float(roc_auc_score(y, probability)),
                accuracy=float(accuracy_score(y, pred)),
                balanced_accuracy=float(balanced_accuracy_score(y, pred)),
                precision=float(precision_score(y, pred, zero_division=0)),
                recall=float(recall_score(y, pred, zero_division=0)),
                f1=float(f1_score(y, pred, zero_division=0)),
                brier=float(brier_score_loss(y, probability)))


def bootstrap(y, p, draws=1000):
    """Stratified IMAGE bootstrap: subjects are unknown, no subject-level claims."""
    rng = np.random.default_rng(42)
    groups = [np.flatnonzero(y == c) for c in (0, 1)]
    samples = []
    for _ in range(draws):
        ix = np.concatenate([rng.choice(g, len(g), replace=True) for g in groups])
        samples.append(metrics(y[ix], p[ix]))
    return {key: np.percentile([s[key] for s in samples], [2.5, 97.5]).tolist()
            for key in samples[0]}


def run(data, model, out, evaluation_split='test'):
    if evaluation_split not in ('validation', 'test'):
        raise ValueError('Only frozen validation or test evaluation is allowed.')
    out.mkdir(parents=True, exist_ok=True)
    if (out / 'metrics.json').exists():
        raise FileExistsError('Preserve prior evaluation; choose a new output directory.')
    freeze = json.loads((data / 'dataset.freeze.json').read_text())
    ids = set()
    for split in ('train', 'validation', 'test'):
        manifest = data / 'splits' / f'{split}.csv'
        assert sha(manifest) == freeze['split_sha256'][split], split
        rows = list(csv.DictReader(manifest.open()))
        assert len(rows) == sum(freeze['counts'][split].values())
        for row in rows:
            assert row['image_id'] not in ids, 'Exact decoded image overlap'
            ids.add(row['image_id'])
            assert sha(data / row['path']) == row['sha256'], row['path']
    lock = dict(model_sha256=sha(model), dataset_sha256=freeze['dataset_sha256'],
                threshold=.5, positive_class=1, split=evaluation_split, training=False,
                preprocessing='MobileNet_V3_Small_Weights.IMAGENET1K_V1.transforms()',
                bootstrap_draws=1000, seed=42, subject_disjointness_verified=False,
                historical_holdout_access='unknown; cannot prove never inspected')
    (out / 'evaluation_lock.json').write_text(json.dumps(lock, indent=2))
    session = ort.InferenceSession(str(model), providers=['CPUExecutionProvider'])
    transform = MobileNet_V3_Small_Weights.IMAGENET1K_V1.transforms()
    rows = list(csv.DictReader((data / 'splits' / f'{evaluation_split}.csv').open()))
    probabilities, labels = [], []
    elapsed = 0.
    for i, row in enumerate(rows):
        with Image.open(data / row['path']) as image:
            x = transform(image.convert('RGB')).unsqueeze(0).numpy()
        start = time.perf_counter()
        logits = session.run(None, {session.get_inputs()[0].name: x})[0]
        elapsed += time.perf_counter() - start
        assert logits.shape == (1, 2) and np.isfinite(logits).all()
        e = np.exp(logits[0] - logits[0].max())
        probabilities.append(float(e[1] / e.sum()))
        labels.append(int(row['label']))
        if i == 0:
            # Identical normalized RGB tensor for native ONNX/browser comparison.
            rgba = np.zeros((224, 224, 4), dtype=np.uint8)
            yy, xx = np.indices((224, 224))
            rgba[:, :, 0] = xx % 256
            rgba[:, :, 1] = yy % 256
            rgba[:, :, 2] = (xx + yy) % 256
            rgba[:, :, 3] = 255
            tensor = (rgba[:, :, :3].astype(np.float32) / np.float32(255) -
                      np.array([.485, .456, .406], np.float32)) / np.array([.229, .224, .225], np.float32)
            tensor = tensor.transpose(2, 0, 1)[None].copy()
            native = session.run(None, {session.get_inputs()[0].name: tensor})[0]
            (out / 'parity_fixture.json').write_text(json.dumps(dict(
                model_sha256=sha(model), logits=native[0].tolist(), tolerance=1e-4,
                description='Synthetic RGB ramp; inference parity only, not camera validation')))
        if (i + 1) % 200 == 0:
            print(f'{i+1}/{len(rows)} images evaluated', flush=True)
    y, p = np.array(labels), np.array(probabilities)
    with (out / 'predictions.csv').open('w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['image_id', 'label', 'stress_probability'])
        writer.writerows((r['image_id'], int(t), float(v)) for r, t, v in zip(rows, y, p))
    result = dict(lock, count=len(y), metrics=metrics(y, p),
                  ci95=bootstrap(y, p), confusion_matrix=confusion_matrix(y, p > .5).tolist(),
                  inference_ms_per_image=elapsed / len(rows) * 1000,
                  ci_unit='image; NOT subject-cluster bootstrap',
                  note='Dataset-label discrimination only; not clinical stress or live-scan validation.')
    (out / 'metrics.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--split', choices=['validation', 'test'], default='test')
    args = parser.parse_args()
    run(args.data, args.model, args.out, args.split)
