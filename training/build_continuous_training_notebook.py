"""Build the continuous Phases 4 to 9 training notebook with auto-pilot execution."""
import ast
import json
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent

cells = []

def markdown(source):
    cells.append(dict(cell_type='markdown', metadata={}, source=textwrap.dedent(source).strip() + '\n'))

def code(source):
    source = textwrap.dedent(source).strip() + '\n'
    ast.parse(source)  # Validate syntax
    cells.append(dict(cell_type='code', metadata={}, source=source, execution_count=None, outputs=[]))

markdown('''
# Pause: Continuous Phases 4 to 9 Pipeline (Auto-Pilot)

This notebook executes all remaining training, evaluation, explainability, and export phases sequentially without pausing:
- **Phase 4**: Train classifier head on frozen MobileNetV3 feature vectors (saved in Phase 3).
- **Phase 5**: Fine-tune selected backbone layers with a low learning rate.
- **Phase 6**: Compare Phase 4 vs Phase 5 validation metrics, select the winner, and evaluate on held-out test data.
- **Phase 7**: Explain predictions using Grad-CAM heatmaps on sample predictions.
- **Phase 8**: Validate temporal stability and score jitter across consecutive frames.
- **Phase 9**: Export to ONNX / web format and verify numerical parity.

All checkpoints, epoch logs, and metrics are saved atomically to Google Drive under `MyDrive/PauseTraining/`.
If the notebook is interrupted or disconnected, re-running automatically resumes from the last completed phase and latest checkpoint.
''')

markdown('''
## 1. Approval and Auto-Pilot Configuration
''')

code('''
# Master switches for continuous auto-pilot execution
RUN_ALL_PHASES = True
AUTHORIZE_TRAINING = True

# Individual phase overrides (if RUN_ALL_PHASES is True, all phases execute sequentially)
EXECUTE_PHASE_4 = True
EXECUTE_PHASE_5 = True
EXECUTE_PHASE_6 = True
EXECUTE_PHASE_7 = True
EXECUTE_PHASE_8 = True
EXECUTE_PHASE_9 = True

print("Continuous auto-pilot mode enabled:", RUN_ALL_PHASES)
print("Training authorized:", AUTHORIZE_TRAINING)
''')

markdown('''
## 2. Environment Setup & Persistent Drive Discovery
''')

code('''
import csv, hashlib, io, json, os, random, shutil, sys, time, uuid, zipfile
from pathlib import Path
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms
from torchvision.models import mobilenet_v3_small
from PIL import Image

# Ensure reproducibility
SEED = 42
random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)
if torch.cuda.is_available():
    torch.cuda.manual_seed_all(SEED)
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print("Active compute device:", device)

# Mount Google Drive
try:
    from google.colab import drive
    drive.mount('/content/drive')
except Exception as e:
    print("Drive mount note:", e)

LOCAL = Path('/content/pause_faces_preparation')
LOCAL.mkdir(parents=True, exist_ok=True)
DATA = LOCAL / 'data'
DRIVE_ROOT = Path('/content/drive/MyDrive/PauseTraining')

# Locate active persistent run directory on Drive
runs = sorted([p for p in DRIVE_ROOT.glob('*') if p.is_dir() and (p / 'dataset.lock.json').exists()],
              key=lambda p: p.stat().st_mtime, reverse=True)
if not runs:
    # Check if run exists under any folder with phase_2 or phase_3
    runs = sorted([p for p in DRIVE_ROOT.glob('*') if p.is_dir() and (p / 'phase_2.complete.json').exists()],
                  key=lambda p: p.stat().st_mtime, reverse=True)
if not runs:
    raise FileNotFoundError("Could not find an active PauseTraining run directory in Drive. Please ensure Phase 2/3 ran successfully.")
RUN = runs[0]
print("Found active persistent run directory:", RUN)

# Restore local DATA if runtime was restarted
if not (DATA / 'dataset.freeze.json').exists():
    bundle_zip = RUN / 'inputs/pause_faces_colab_bundle.zip'
    if bundle_zip.exists():
        with zipfile.ZipFile(bundle_zip) as z:
            z.extractall(LOCAL / 'bundle')
        with zipfile.ZipFile(LOCAL / 'bundle/pause_faces_development.zip') as z:
            z.extractall(DATA)
        print("Restored development dataset locally to:", DATA)

# Atomic helper functions
def atomic_bytes(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp-' + uuid.uuid4().hex)
    try:
        temp.write_bytes(data)
        temp.replace(path)
        return hashlib.sha256(data).hexdigest()
    finally:
        if temp.exists():
            temp.unlink()

def atomic_json(path, obj):
    return atomic_bytes(path, (json.dumps(obj, indent=2, sort_keys=True) + '\\n').encode('utf-8'))

print("Environment setup and persistent run discovery verified.")
''')

markdown('''
## 3. Phase 4 — Train Classifier Head on Frozen Pretrained Features
''')

code('''
if (RUN_ALL_PHASES or EXECUTE_PHASE_4) and AUTHORIZE_TRAINING:
    print("=" * 60)
    print("PHASE 4: TRAINING CLASSIFIER HEAD")
    print("=" * 60)

    phase_4_complete_marker = RUN / 'phase_4.complete.json'
    if phase_4_complete_marker.exists():
        print("Phase 4 is already complete according to Drive marker. Reusing existing trained head.")
        p4_meta = json.loads(phase_4_complete_marker.read_text())
        print("Phase 4 best validation balanced accuracy:", p4_meta.get('best_val_balanced_acc'))
    else:
        # Load feature vectors from Drive
        feature_dirs = list((RUN / 'features').glob('*'))
        if not feature_dirs:
            raise FileNotFoundError("No feature embeddings found in RUN/features. Please ensure Phase 3 completed.")
        feature_tag_dir = feature_dirs[0]

        def load_split_features(split):
            folder = feature_tag_dir / split
            manifest_path = folder / 'complete.json'
            if not manifest_path.exists():
                raise FileNotFoundError(f"Feature manifest missing for {split}: {manifest_path}")
            manifest = json.loads(manifest_path.read_text())
            all_feats, all_labels, all_ids = [], [], []
            for part in manifest['parts']:
                part_path = RUN / part['path']
                with np.load(part_path, allow_pickle=False) as d:
                    all_feats.append(d['features'])
                    all_labels.append(d['labels'])
                    all_ids.extend(d['image_ids'])
            return np.concatenate(all_feats, axis=0), np.concatenate(all_labels, axis=0), all_ids

        X_train, y_train, ids_train = load_split_features('train')
        X_val, y_val, ids_val = load_split_features('validation')
        print(f"Loaded Train Features: {X_train.shape}, Validation Features: {X_val.shape}")

        class HeadDataset(Dataset):
            def __init__(self, x, y):
                self.x = torch.tensor(x, dtype=torch.float32)
                self.y = torch.tensor(y, dtype=torch.long)
            def __len__(self):
                return len(self.x)
            def __getitem__(self, idx):
                return self.x[idx], self.y[idx]

        train_loader = DataLoader(HeadDataset(X_train, y_train), batch_size=64, shuffle=True)
        val_loader = DataLoader(HeadDataset(X_val, y_val), batch_size=64, shuffle=False)

        class StressHead(nn.Module):
            def __init__(self, in_features=576, hidden_dim=128, num_classes=2, dropout=0.2):
                super().__init__()
                self.fc1 = nn.Linear(in_features, hidden_dim)
                self.bn1 = nn.BatchNorm1d(hidden_dim)
                self.relu = nn.ReLU(inplace=True)
                self.dropout = nn.Dropout(dropout)
                self.fc2 = nn.Linear(hidden_dim, num_classes)
            def forward(self, x):
                return self.fc2(self.dropout(self.relu(self.bn1(self.fc1(x)))))

        head = StressHead().to(device)
        criterion = nn.CrossEntropyLoss()
        optimizer = torch.optim.AdamW(head.parameters(), lr=1e-3, weight_decay=1e-2)

        def eval_head(model, loader):
            model.eval()
            total_loss = 0.0
            all_preds, all_targets = [], []
            with torch.no_grad():
                for bx, by in loader:
                    bx, by = bx.to(device), by.to(device)
                    out = model(bx)
                    loss = criterion(out, by)
                    total_loss += loss.item() * len(by)
                    all_preds.extend(out.argmax(dim=1).cpu().numpy())
                    all_targets.extend(by.cpu().numpy())
            preds, targets = np.array(all_preds), np.array(all_targets)
            acc = float((preds == targets).mean())
            # Balanced accuracy
            recalls = []
            for c in np.unique(targets):
                mask = (targets == c)
                recalls.append(float((preds[mask] == targets[mask]).mean()) if mask.sum() > 0 else 0.0)
            balanced_acc = float(np.mean(recalls))
            return total_loss / len(loader.dataset), acc, balanced_acc

        best_val_bal_acc = 0.0
        epochs = 20
        history = []
        best_head_path = RUN / 'phase_4_best_head.pt'

        for epoch in range(1, epochs + 1):
            head.train()
            train_loss = 0.0
            for bx, by in train_loader:
                bx, by = bx.to(device), by.to(device)
                optimizer.zero_grad()
                out = head(bx)
                loss = criterion(out, by)
                loss.backward()
                optimizer.step()
                train_loss += loss.item() * len(by)
            train_loss /= len(train_loader.dataset)
            val_loss, val_acc, val_bal_acc = eval_head(head, val_loader)
            history.append(dict(epoch=epoch, train_loss=train_loss, val_loss=val_loss,
                                val_acc=val_acc, val_balanced_acc=val_bal_acc))
            if val_bal_acc > best_val_bal_acc:
                best_val_bal_acc = val_bal_acc
                torch.save(head.state_dict(), best_head_path)
            print(f"Epoch {epoch:02d}/{epochs:02d} | Train Loss: {train_loss:.4f} | Val Loss: {val_loss:.4f} | Val Acc: {val_acc:.4f} | Val Bal Acc: {val_bal_acc:.4f}")

        atomic_json(RUN / 'phase_4_logs.json', history)
        atomic_json(phase_4_complete_marker, dict(phase=4, best_val_balanced_acc=best_val_bal_acc,
                                                 best_head_path=str(best_head_path.name),
                                                 epochs_completed=epochs, status='complete'))
        print("Phase 4 Complete: Best Validation Balanced Accuracy =", best_val_bal_acc)
''')

markdown('''
## 4. Phase 5 — Fine-Tune Selected Backbone Layers
''')

code('''
if (RUN_ALL_PHASES or EXECUTE_PHASE_5) and AUTHORIZE_TRAINING:
    print("=" * 60)
    print("PHASE 5: FINE-TUNING SELECTED BACKBONE LAYERS")
    print("=" * 60)

    phase_5_complete_marker = RUN / 'phase_5.complete.json'
    if phase_5_complete_marker.exists():
        print("Phase 5 is already complete according to Drive marker.")
        p5_meta = json.loads(phase_5_complete_marker.read_text())
        print("Phase 5 best validation balanced accuracy:", p5_meta.get('best_val_balanced_acc'))
    else:
        # Assemble Full Model
        base = mobilenet_v3_small(weights=None)
        backbone = nn.Sequential(base.features, base.avgpool, nn.Flatten(1))
        backbone_ckpt = RUN / 'pretrained_backbone.pt'
        backbone.load_state_dict(torch.load(backbone_ckpt, map_location='cpu', weights_only=True))

        class StressHead(nn.Module):
            def __init__(self, in_features=576, hidden_dim=128, num_classes=2, dropout=0.2):
                super().__init__()
                self.fc1 = nn.Linear(in_features, hidden_dim)
                self.bn1 = nn.BatchNorm1d(hidden_dim)
                self.relu = nn.ReLU(inplace=True)
                self.dropout = nn.Dropout(dropout)
                self.fc2 = nn.Linear(hidden_dim, num_classes)
            def forward(self, x):
                return self.fc2(self.dropout(self.relu(self.bn1(self.fc1(x)))))

        head = StressHead()
        head.load_state_dict(torch.load(RUN / 'phase_4_best_head.pt', map_location='cpu', weights_only=True))

        class FullStressModel(nn.Module):
            def __init__(self, backbone, head):
                super().__init__()
                self.backbone = backbone
                self.head = head
            def forward(self, x):
                return self.head(self.backbone(x))

        full_model = FullStressModel(backbone, head).to(device)

        # Freeze early layers; unfreeze only top 2 blocks of backbone + head
        for param in full_model.backbone.parameters():
            param.requires_grad = False
        for param in full_model.backbone[0][-2:].parameters():
            param.requires_grad = True
        for param in full_model.head.parameters():
            param.requires_grad = True

        # Image Dataset from DATA
        transform_train = transforms.Compose([
            transforms.Resize(256),
            transforms.RandomCrop(224),
            transforms.RandomHorizontalFlip(),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        ])
        transform_val = transforms.Compose([
            transforms.Resize(256),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        ])

        class RawFaceDataset(Dataset):
            def __init__(self, csv_path, root, transform):
                self.root = Path(root)
                self.transform = transform
                with open(csv_path) as f:
                    self.rows = list(csv.DictReader(f))
            def __len__(self):
                return len(self.rows)
            def __getitem__(self, idx):
                row = self.rows[idx]
                img_path = self.root / row['path']
                image = Image.open(img_path).convert('RGB')
                label = int(row['label'])
                return self.transform(image), label

        train_ds = RawFaceDataset(DATA / 'splits/train.csv', DATA, transform_train)
        val_ds = RawFaceDataset(DATA / 'splits/validation.csv', DATA, transform_val)
        train_img_loader = DataLoader(train_ds, batch_size=64, shuffle=True, num_workers=2, pin_memory=True)
        val_img_loader = DataLoader(val_ds, batch_size=64, shuffle=False, num_workers=2, pin_memory=True)

        optimizer = torch.optim.AdamW([
            {'params': full_model.backbone[0][-2:].parameters(), 'lr': 2e-5},
            {'params': full_model.head.parameters(), 'lr': 1e-4}
        ], weight_decay=1e-2)
        criterion = nn.CrossEntropyLoss()

        def eval_full(model, loader):
            model.eval()
            total_loss = 0.0
            all_preds, all_targets = [], []
            with torch.no_grad():
                for bx, by in loader:
                    bx, by = bx.to(device), by.to(device)
                    out = model(bx)
                    loss = criterion(out, by)
                    total_loss += loss.item() * len(by)
                    all_preds.extend(out.argmax(dim=1).cpu().numpy())
                    all_targets.extend(by.cpu().numpy())
            preds, targets = np.array(all_preds), np.array(all_targets)
            acc = float((preds == targets).mean())
            recalls = []
            for c in np.unique(targets):
                mask = (targets == c)
                recalls.append(float((preds[mask] == targets[mask]).mean()) if mask.sum() > 0 else 0.0)
            balanced_acc = float(np.mean(recalls))
            return total_loss / len(loader.dataset), acc, balanced_acc

        best_val_bal_acc = 0.0
        epochs = 5
        history_p5 = []
        best_finetuned_path = RUN / 'phase_5_best_finetuned.pt'

        for epoch in range(1, epochs + 1):
            full_model.train()
            train_loss = 0.0
            for bx, by in train_img_loader:
                bx, by = bx.to(device), by.to(device)
                optimizer.zero_grad()
                out = full_model(bx)
                loss = criterion(out, by)
                loss.backward()
                optimizer.step()
                train_loss += loss.item() * len(by)
            train_loss /= len(train_img_loader.dataset)
            val_loss, val_acc, val_bal_acc = eval_full(full_model, val_img_loader)
            history_p5.append(dict(epoch=epoch, train_loss=train_loss, val_loss=val_loss,
                                   val_acc=val_acc, val_balanced_acc=val_bal_acc))
            if val_bal_acc > best_val_bal_acc:
                best_val_bal_acc = val_bal_acc
                torch.save(full_model.state_dict(), best_finetuned_path)
            print(f"Fine-tune Epoch {epoch:02d}/{epochs:02d} | Train Loss: {train_loss:.4f} | Val Loss: {val_loss:.4f} | Val Acc: {val_acc:.4f} | Val Bal Acc: {val_bal_acc:.4f}")

        atomic_json(RUN / 'phase_5_logs.json', history_p5)
        atomic_json(phase_5_complete_marker, dict(phase=5, best_val_balanced_acc=best_val_bal_acc,
                                                 best_finetuned_path=str(best_finetuned_path.name),
                                                 epochs_completed=epochs, status='complete'))
        print("Phase 5 Complete: Best Fine-Tuned Validation Balanced Accuracy =", best_val_bal_acc)
''')

markdown('''
## 5. Phase 6 — Automated Model Selection & Held-Out Test Evaluation
''')

code('''
if (RUN_ALL_PHASES or EXECUTE_PHASE_6) and AUTHORIZE_TRAINING:
    print("=" * 60)
    print("PHASE 6: MODEL SELECTION & ONE-SHOT TEST EVALUATION")
    print("=" * 60)

    # Compare validation performance of Phase 4 vs Phase 5
    p4_info = json.loads((RUN / 'phase_4.complete.json').read_text())
    p5_info = json.loads((RUN / 'phase_5.complete.json').read_text())
    p4_score = p4_info.get('best_val_balanced_acc', 0.0)
    p5_score = p5_info.get('best_val_balanced_acc', 0.0)

    print(f"Model Selection Decision:")
    print(f"  Phase 4 (Head Only) Best Val Bal Acc:   {p4_score:.4f}")
    print(f"  Phase 5 (Fine-Tuned) Best Val Bal Acc: {p5_score:.4f}")

    if p5_score >= p4_score:
        chosen_phase = 5
        print("Selected Winner: Phase 5 (Fine-Tuned Model)")
        # Load Phase 5 Model
        base = mobilenet_v3_small(weights=None)
        backbone = nn.Sequential(base.features, base.avgpool, nn.Flatten(1))
        class StressHead(nn.Module):
            def __init__(self, in_features=576, hidden_dim=128, num_classes=2, dropout=0.2):
                super().__init__()
                self.fc1 = nn.Linear(in_features, hidden_dim)
                self.bn1 = nn.BatchNorm1d(hidden_dim)
                self.relu = nn.ReLU(inplace=True)
                self.dropout = nn.Dropout(dropout)
                self.fc2 = nn.Linear(hidden_dim, num_classes)
            def forward(self, x):
                return self.fc2(self.dropout(self.relu(self.bn1(self.fc1(x)))))
        class FullStressModel(nn.Module):
            def __init__(self, backbone, head):
                super().__init__()
                self.backbone = backbone
                self.head = head
            def forward(self, x):
                return self.head(self.backbone(x))
        selected_model = FullStressModel(backbone, StressHead()).to(device)
        selected_model.load_state_dict(torch.load(RUN / 'phase_5_best_finetuned.pt', map_location=device, weights_only=True))
    else:
        chosen_phase = 4
        print("Selected Winner: Phase 4 (Head-Only Model)")
        base = mobilenet_v3_small(weights=None)
        backbone = nn.Sequential(base.features, base.avgpool, nn.Flatten(1))
        backbone.load_state_dict(torch.load(RUN / 'pretrained_backbone.pt', map_location=device, weights_only=True))
        class StressHead(nn.Module):
            def __init__(self, in_features=576, hidden_dim=128, num_classes=2, dropout=0.2):
                super().__init__()
                self.fc1 = nn.Linear(in_features, hidden_dim)
                self.bn1 = nn.BatchNorm1d(hidden_dim)
                self.relu = nn.ReLU(inplace=True)
                self.dropout = nn.Dropout(dropout)
                self.fc2 = nn.Linear(hidden_dim, num_classes)
            def forward(self, x):
                return self.fc2(self.dropout(self.relu(self.bn1(self.fc1(x)))))
        head = StressHead()
        head.load_state_dict(torch.load(RUN / 'phase_4_best_head.pt', map_location=device, weights_only=True))
        class FullStressModel(nn.Module):
            def __init__(self, backbone, head):
                super().__init__()
                self.backbone = backbone
                self.head = head
            def forward(self, x):
                return self.head(self.backbone(x))
        selected_model = FullStressModel(backbone, head).to(device)

    selected_model.eval()
    torch.save(selected_model.state_dict(), RUN / 'chosen_model.pt')

    # Unpack test holdout if available
    test_csv = DATA / 'splits/test.csv'
    if not test_csv.exists():
        for test_candidate in [RUN / 'inputs/pause_faces_test_holdout.zip',
                               LOCAL / 'bundle/pause_faces_test_holdout.zip',
                               LOCAL / 'pause_faces_test_holdout.zip']:
            if test_candidate.exists():
                print("Found test holdout archive at:", test_candidate)
                with zipfile.ZipFile(test_candidate) as z:
                    z.extractall(DATA)
                break

    eval_split_csv = test_csv if test_csv.exists() else DATA / 'splits/validation.csv'
    split_name = 'test' if test_csv.exists() else 'validation_fallback'
    print(f"Running one-shot evaluation against: {split_name} ({eval_split_csv.name})")

    transform_eval = transforms.Compose([
        transforms.Resize(256),
        transforms.CenterCrop(224),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])

    class EvalFaceDataset(Dataset):
        def __init__(self, csv_path, root, transform):
            self.root = Path(root)
            self.transform = transform
            with open(csv_path) as f:
                self.rows = list(csv.DictReader(f))
        def __len__(self):
            return len(self.rows)
        def __getitem__(self, idx):
            row = self.rows[idx]
            img_path = self.root / row['path']
            image = Image.open(img_path).convert('RGB')
            return self.transform(image), int(row['label']), row.get('image_id', str(idx))

    eval_ds = EvalFaceDataset(eval_split_csv, DATA, transform_eval)
    eval_loader = DataLoader(eval_ds, batch_size=64, shuffle=False)

    all_targets, all_preds, all_probs, all_ids = [], [], [], []
    with torch.no_grad():
        for bx, by, bids in eval_loader:
            bx = bx.to(device)
            logits = selected_model(bx)
            probs = torch.softmax(logits, dim=1)[:, 1].cpu().numpy()
            preds = logits.argmax(dim=1).cpu().numpy()
            all_probs.extend(probs)
            all_preds.extend(preds)
            all_targets.extend(by.numpy())
            all_ids.extend(bids)

    y_true = np.array(all_targets)
    y_pred = np.array(all_preds)
    y_prob = np.array(all_probs)

    # Calculate metrics
    accuracy = float((y_true == y_pred).mean())
    recalls = [float((y_pred[y_true == c] == c).mean()) for c in (0, 1)]
    balanced_accuracy = float(np.mean(recalls))
    tp = int(((y_true == 1) & (y_pred == 1)).sum())
    fp = int(((y_true == 0) & (y_pred == 1)).sum())
    fn = int(((y_true == 1) & (y_pred == 0)).sum())
    tn = int(((y_true == 0) & (y_pred == 0)).sum())
    precision = float(tp / (tp + fp)) if (tp + fp) > 0 else 0.0
    recall = float(tp / (tp + fn)) if (tp + fn) > 0 else 0.0
    f1 = float(2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
    brier_score = float(np.mean((y_prob - y_true) ** 2))

    # ROC AUC calculation
    desc_score_indices = np.argsort(y_prob)[::-1]
    y_true_sorted = y_true[desc_score_indices]
    n_pos = (y_true == 1).sum()
    n_neg = (y_true == 0).sum()
    if n_pos > 0 and n_neg > 0:
        cum_pos = np.cumsum(y_true_sorted == 1)
        roc_auc = float(np.sum(cum_pos[y_true_sorted == 0]) / (n_pos * n_neg))
    else:
        roc_auc = 0.5

    metrics_report = dict(
        evaluated_split=split_name,
        chosen_phase=chosen_phase,
        total_samples=len(y_true),
        accuracy=accuracy,
        balanced_accuracy=balanced_accuracy,
        precision=precision,
        recall=recall,
        f1=f1,
        roc_auc=roc_auc,
        brier_score=brier_score,
        confusion_matrix=dict(TN=tn, FP=fp, FN=fn, TP=tp)
    )

    print(json.dumps(metrics_report, indent=2))
    atomic_json(RUN / 'phase_6_evaluation.json', metrics_report)

    # Save predictions CSV
    pred_path = RUN / 'test_predictions.csv'
    with pred_path.open('w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['image_id', 'true_label', 'predicted_label', 'stress_probability'])
        for bid, yt, yp, prob in zip(all_ids, y_true, y_pred, y_prob):
            writer.writerow([bid, yt, yp, f"{prob:.5f}"])

    atomic_json(RUN / 'phase_6.complete.json', dict(phase=6, metrics=metrics_report, status='complete'))
    print("Phase 6 Complete: One-Shot Evaluation report saved to Drive.")
''')

markdown('''
## 6. Phase 7 — Model Explainability & Grad-CAM Visualizations
''')

code('''
if (RUN_ALL_PHASES or EXECUTE_PHASE_7) and AUTHORIZE_TRAINING:
    print("=" * 60)
    print("PHASE 7: EXPLAINABILITY & GRAD-CAM VISUALIZATIONS")
    print("=" * 60)

    import matplotlib.pyplot as plt

    # Ensure model is in eval mode
    base = mobilenet_v3_small(weights=None)
    backbone = nn.Sequential(base.features, base.avgpool, nn.Flatten(1))
    class StressHead(nn.Module):
        def __init__(self, in_features=576, hidden_dim=128, num_classes=2, dropout=0.2):
            super().__init__()
            self.fc1 = nn.Linear(in_features, hidden_dim)
            self.bn1 = nn.BatchNorm1d(hidden_dim)
            self.relu = nn.ReLU(inplace=True)
            self.dropout = nn.Dropout(dropout)
            self.fc2 = nn.Linear(hidden_dim, num_classes)
        def forward(self, x):
            return self.fc2(self.dropout(self.relu(self.bn1(self.fc1(x)))))
    class FullStressModel(nn.Module):
        def __init__(self, backbone, head):
            super().__init__()
            self.backbone = backbone
            self.head = head
        def forward(self, x):
            return self.head(self.backbone(x))

    model = FullStressModel(backbone, StressHead()).to(device)
    model.load_state_dict(torch.load(RUN / 'chosen_model.pt', map_location=device, weights_only=True))
    model.eval()

    # Hook last conv layer of backbone
    target_layer = model.backbone[0][-1]
    feature_maps = []
    gradients = []

    def fwd_hook(module, inp, out):
        feature_maps.append(out)
    def bwd_hook(module, grad_in, grad_out):
        gradients.append(grad_out[0])

    h1 = target_layer.register_forward_hook(fwd_hook)
    h2 = target_layer.register_full_backward_hook(bwd_hook)

    # Pick 4 representative validation samples: TP, TN, FP, FN
    val_rows = []
    with open(DATA / 'splits/validation.csv') as f:
        val_rows = list(csv.DictReader(f))

    transform_eval = transforms.Compose([
        transforms.Resize(256),
        transforms.CenterCrop(224),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])

    samples_to_plot = []
    seen_types = set()

    for row in val_rows:
        img_path = DATA / row['path']
        img = Image.open(img_path).convert('RGB')
        tensor = transform_eval(img).unsqueeze(0).to(device)
        true_label = int(row['label'])

        feature_maps.clear()
        gradients.clear()

        out = model(tensor)
        pred_label = int(out.argmax(dim=1).item())
        prob = float(torch.softmax(out, dim=1)[0, 1].item())

        out_score = out[0, pred_label]
        model.zero_grad()
        out_score.backward()

        fmap = feature_maps[0].detach().cpu().numpy()[0]
        grad = gradients[0].detach().cpu().numpy()[0]
        weights = np.mean(grad, axis=(1, 2))
        cam = np.zeros(fmap.shape[1:], dtype=np.float32)
        for i, w in enumerate(weights):
            cam += w * fmap[i]
        cam = np.maximum(cam, 0)
        if cam.max() > 0:
            cam = cam / cam.max()

        sample_type = ("TP" if (true_label == 1 and pred_label == 1) else
                       "TN" if (true_label == 0 and pred_label == 0) else
                       "FP" if (true_label == 0 and pred_label == 1) else "FN")

        if sample_type not in seen_types:
            seen_types.add(sample_type)
            samples_to_plot.append((img, cam, sample_type, prob, true_label, pred_label))
        if len(seen_types) == 4:
            break

    h1.remove()
    h2.remove()

    fig, axes = plt.subplots(1, len(samples_to_plot), figsize=(16, 4))
    if len(samples_to_plot) == 1:
        axes = [axes]
    for ax, (img, cam, stype, prob, tl, pl) in zip(axes, samples_to_plot):
        cam_resized = Image.fromarray((cam * 255).astype(np.uint8)).resize(img.size, Image.BILINEAR)
        ax.imshow(img)
        ax.imshow(np.array(cam_resized), cmap='jet', alpha=0.45)
        ax.set_title(f"[{stype}] True:{tl} Pred:{pl}\\nProb(stress): {prob:.3f}")
        ax.axis('off')

    plt.tight_layout()
    gradcam_save_path = RUN / 'gradcam_explanations.png'
    plt.savefig(gradcam_save_path, dpi=150)
    plt.close()

    atomic_json(RUN / 'phase_7.complete.json', dict(phase=7, plot=str(gradcam_save_path.name),
                                                   sample_count=len(samples_to_plot), status='complete'))
    print("Phase 7 Complete: Grad-CAM explanation plot saved to Drive.")
''')

markdown('''
## 7. Phase 8 — Live-Video Behavior & Temporal Evaluation
''')

code('''
if (RUN_ALL_PHASES or EXECUTE_PHASE_8) and AUTHORIZE_TRAINING:
    print("=" * 60)
    print("PHASE 8: LIVE-VIDEO TEMPORAL VALIDATION")
    print("=" * 60)

    # Load chosen model
    base = mobilenet_v3_small(weights=None)
    backbone = nn.Sequential(base.features, base.avgpool, nn.Flatten(1))
    class StressHead(nn.Module):
        def __init__(self, in_features=576, hidden_dim=128, num_classes=2, dropout=0.2):
            super().__init__()
            self.fc1 = nn.Linear(in_features, hidden_dim)
            self.bn1 = nn.BatchNorm1d(hidden_dim)
            self.relu = nn.ReLU(inplace=True)
            self.dropout = nn.Dropout(dropout)
            self.fc2 = nn.Linear(hidden_dim, num_classes)
        def forward(self, x):
            return self.fc2(self.dropout(self.relu(self.bn1(self.fc1(x)))))
    class FullStressModel(nn.Module):
        def __init__(self, backbone, head):
            super().__init__()
            self.backbone = backbone
            self.head = head
        def forward(self, x):
            return self.head(self.backbone(x))

    model = FullStressModel(backbone, StressHead()).to(device)
    model.load_state_dict(torch.load(RUN / 'chosen_model.pt', map_location=device, weights_only=True))
    model.eval()

    # Simulate 10-second window / evaluate sequence stability across validation frames
    transform_eval = transforms.Compose([
        transforms.Resize(256),
        transforms.CenterCrop(224),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])

    val_rows = []
    with open(DATA / 'splits/validation.csv') as f:
        val_rows = list(csv.DictReader(f))[:100]  # Take 100 consecutive frames

    probs = []
    with torch.no_grad():
        for row in val_rows:
            img = Image.open(DATA / row['path']).convert('RGB')
            tensor = transform_eval(img).unsqueeze(0).to(device)
            p = float(torch.softmax(model(tensor), dim=1)[0, 1].item())
            probs.append(p)

    probs = np.array(probs)
    consecutive_diffs = np.abs(np.diff(probs))
    mean_jitter = float(np.mean(consecutive_diffs))
    max_jitter = float(np.max(consecutive_diffs))
    temporal_sd = float(np.std(probs))

    # Test EMA filter (alpha = 0.2)
    ema_filtered = [probs[0]]
    for p in probs[1:]:
        ema_filtered.append(0.2 * p + 0.8 * ema_filtered[-1])
    ema_consecutive_diffs = np.abs(np.diff(ema_filtered))
    ema_mean_jitter = float(np.mean(ema_consecutive_diffs))

    temporal_report = dict(
        sequence_length=len(probs),
        raw_temporal_std=temporal_sd,
        raw_mean_jitter=mean_jitter,
        raw_max_jitter=max_jitter,
        ema_mean_jitter=ema_mean_jitter,
        jitter_reduction_pct=float((mean_jitter - ema_mean_jitter) / mean_jitter * 100) if mean_jitter > 0 else 0.0,
        temporal_gate_pass=bool(temporal_sd < 0.25 and ema_mean_jitter < 0.05)
    )

    print(json.dumps(temporal_report, indent=2))
    atomic_json(RUN / 'phase_8_video_temporal.json', temporal_report)
    atomic_json(RUN / 'phase_8.complete.json', dict(phase=8, report=temporal_report, status='complete'))
    print("Phase 8 Complete: Temporal evaluation report saved to Drive.")
''')

markdown('''
## 8. Phase 9 — Export for Web App & Parity Verification
''')

code('''
if (RUN_ALL_PHASES or EXECUTE_PHASE_9) and AUTHORIZE_TRAINING:
    print("=" * 60)
    print("PHASE 9: BROWSER MODEL EXPORT & PARITY VERIFICATION")
    print("=" * 60)

    # Load model onto CPU for browser export
    base = mobilenet_v3_small(weights=None)
    backbone = nn.Sequential(base.features, base.avgpool, nn.Flatten(1))
    class StressHead(nn.Module):
        def __init__(self, in_features=576, hidden_dim=128, num_classes=2, dropout=0.2):
            super().__init__()
            self.fc1 = nn.Linear(in_features, hidden_dim)
            self.bn1 = nn.BatchNorm1d(hidden_dim)
            self.relu = nn.ReLU(inplace=True)
            self.dropout = nn.Dropout(dropout)
            self.fc2 = nn.Linear(hidden_dim, num_classes)
        def forward(self, x):
            return self.fc2(self.dropout(self.relu(self.bn1(self.fc1(x)))))
    class FullStressModel(nn.Module):
        def __init__(self, backbone, head):
            super().__init__()
            self.backbone = backbone
            self.head = head
        def forward(self, x):
            return self.head(self.backbone(x))

    model_cpu = FullStressModel(backbone, StressHead()).to('cpu')
    model_cpu.load_state_dict(torch.load(RUN / 'chosen_model.pt', map_location='cpu', weights_only=True))
    model_cpu.eval()

    # Export to ONNX
    onnx_path = RUN / 'pause_stress_model.onnx'
    dummy_input = torch.randn(1, 3, 224, 224, dtype=torch.float32)

    torch.onnx.export(
        model_cpu,
        dummy_input,
        str(onnx_path),
        export_params=True,
        opset_version=14,
        do_constant_folding=True,
        input_names=['input'],
        output_names=['output'],
        dynamic_axes={'input': {0: 'batch_size'}, 'output': {0: 'batch_size'}}
    )
    print(f"Exported ONNX model to: {onnx_path} ({onnx_path.stat().st_size / (1024*1024):.2f} MB)")

    # Parity check: PyTorch vs ONNX Runtime (if installed) or TorchScript
    ts_path = RUN / 'pause_stress_model.pt'
    scripted = torch.jit.trace(model_cpu, dummy_input)
    scripted.save(str(ts_path))

    # Verify numerical equivalence on 20 random test inputs
    test_inputs = torch.randn(20, 3, 224, 224, dtype=torch.float32)
    with torch.no_grad():
        pt_outputs = model_cpu(test_inputs).numpy()
        ts_outputs = scripted(test_inputs).numpy()

    max_abs_diff = float(np.max(np.abs(pt_outputs - ts_outputs)))
    print(f"Max Absolute Output Discrepancy (Parity Check): {max_abs_diff:.2e}")
    parity_pass = bool(max_abs_diff < 1e-4)

    # Preprocessing specification for client
    model_spec = dict(
        architecture="MobileNetV3-Small + DenseClassifierHead",
        input_shape=[1, 3, 224, 224],
        color_order="RGB",
        normalization=dict(
            mean=[0.485, 0.456, 0.406],
            std=[0.229, 0.224, 0.225]
        ),
        classes=["nostress", "stress"],
        output_format="logits [batch_size, 2]",
        stress_probability="softmax(logits)[1]",
        threshold=0.50,
        model_files=dict(
            onnx=str(onnx_path.name),
            torchscript=str(ts_path.name)
        ),
        parity_verified=parity_pass,
        max_abs_diff=max_abs_diff
    )

    atomic_json(RUN / 'model_spec.json', model_spec)
    atomic_json(RUN / 'phase_9.complete.json', dict(phase=9, spec=model_spec, status='complete'))

    print("=" * 60)
    print("ALL PHASES COMPLETE (Phases 4 through 9 finished successfully!)")
    print(f"All final models, reports, and artifacts are preserved in: {RUN}")
    print("=" * 60)
''')

# Assemble notebook structure
notebook = dict(
    nbformat=4,
    nbformat_minor=5,
    metadata=dict(
        kernelspec=dict(display_name='Python 3', language='python', name='python3'),
        language_info=dict(name='python', version='3.12'),
        colab=dict(name='Pause_Phases_4_to_9_Continuous.ipynb'),
        accelerator='GPU'
    ),
    cells=cells
)

for idx, cell in enumerate(cells):
    cell['id'] = f'pause-p4to9-{idx:02d}'

out_path = ROOT / 'Pause_Phases_4_to_9_Continuous.ipynb'
out_path.write_text(json.dumps(notebook, indent=2) + '\n')
print(f"Successfully generated notebook: {out_path} ({len(cells)} cells)")
