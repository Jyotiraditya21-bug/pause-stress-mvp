"""Verify the original chosen state dict against ONNX; inference only, no downloads."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import torch
from torch import nn
from torchvision.models import mobilenet_v3_small
import onnxruntime as ort

class StressHead(nn.Module):
    def __init__(self):
        super().__init__()
        self.fc1 = nn.Linear(576, 128)
        self.bn1 = nn.BatchNorm1d(128)
        self.relu = nn.ReLU(inplace=True)
        self.dropout = nn.Dropout(.2)
        self.fc2 = nn.Linear(128, 2)
    def forward(self, x):
        return self.fc2(self.dropout(self.relu(self.bn1(self.fc1(x)))))

class FullStressModel(nn.Module):
    def __init__(self):
        super().__init__()
        base = mobilenet_v3_small(weights=None)
        self.backbone = nn.Sequential(base.features, base.avgpool, nn.Flatten(1))
        self.head = StressHead()
    def forward(self, x):
        return self.head(self.backbone(x))

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def run(checkpoint, onnx, out, torchscript=None):
    if out.exists():
        raise FileExistsError('Preserve existing parity report.')
    torch.set_num_threads(2)
    model = FullStressModel().eval()
    model.load_state_dict(torch.load(checkpoint, map_location='cpu', weights_only=True), strict=True)
    session = ort.InferenceSession(str(onnx), providers=['CPUExecutionProvider'])
    rng = np.random.default_rng(42)
    fixtures = rng.normal(size=(20, 3, 224, 224)).astype(np.float32)
    with torch.inference_mode():
        reference = model(torch.from_numpy(fixtures)).numpy()
    actual = session.run(None, {session.get_inputs()[0].name: fixtures})[0]
    error = float(np.max(np.abs(reference - actual)))
    result = dict(checkpoint_sha256=sha(checkpoint), onnx_sha256=sha(onnx),
                  inputs=20,seed=42,tolerance=1e-4,max_absolute_logit_error=error,
                  passed=error <= 1e-4,training=False,scope='Normalized tensor inference parity; not face crop parity')
    if torchscript:
        # Only load the user's original model, never arbitrary downloaded code.
        scripted = torch.jit.load(str(torchscript), map_location='cpu').eval()
        with torch.inference_mode():
            scripted_logits = scripted(torch.from_numpy(fixtures)).numpy()
        se = float(np.max(np.abs(reference-scripted_logits)))
        result.update(torchscript_sha256=sha(torchscript),torchscript_max_absolute_logit_error=se)
        result['passed'] = result['passed'] and se <= 1e-4
    out.write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
    if not result['passed']:
        raise RuntimeError('Parity criterion failed; no automatic tolerance changes allowed.')

if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--checkpoint',type=Path,required=True)
    p.add_argument('--onnx',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--torchscript',type=Path)
    a=p.parse_args();run(a.checkpoint,a.onnx,a.out,a.torchscript)
