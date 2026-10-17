import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  getFaceBoundingBox,
  normalizePixelsToNCHW,
  softmax,
  TemporalEMAFilter,
  MODEL_INPUT_SIZE,
  IMAGENET_NORM
} from './mlInference.js';

test('getFaceBoundingBox: correctly calculates bounded square with margin', () => {
  const landmarks = [
    { x: 0.4, y: 0.4 },
    { x: 0.6, y: 0.6 }
  ];
  const box = getFaceBoundingBox(landmarks, 1000, 1000, 0.1);
  assert.ok(box !== null);
  assert.ok(box.width > 200);
  assert.ok(box.height > 200);
  assert.equal(box.width, box.height); // Square cropping
  assert.ok(box.left >= 0);
  assert.ok(box.top >= 0);
});

test('getFaceBoundingBox: handles null/empty landmarks gracefully', () => {
  assert.equal(getFaceBoundingBox([], 640, 480), null);
  assert.equal(getFaceBoundingBox(null, 640, 480), null);
});

test('normalizePixelsToNCHW: converts RGBA buffer to normalized Float32 NCHW tensor', () => {
  const pixelCount = MODEL_INPUT_SIZE * MODEL_INPUT_SIZE;
  const rgba = new Uint8ClampedArray(pixelCount * 4);
  // Fill all pixels with pure red (255, 0, 0, 255)
  for (let i = 0; i < pixelCount; i++) {
    rgba[i * 4] = 255;
    rgba[i * 4 + 1] = 0;
    rgba[i * 4 + 2] = 0;
    rgba[i * 4 + 3] = 255;
  }

  const tensor = normalizePixelsToNCHW(rgba);
  assert.equal(tensor.length, 3 * pixelCount);

  // Expected R: (1.0 - 0.485) / 0.229 = 2.2489
  const expectedR = (1.0 - IMAGENET_NORM.mean[0]) / IMAGENET_NORM.std[0];
  // Expected G: (0.0 - 0.456) / 0.224 = -2.0357
  const expectedG = (0.0 - IMAGENET_NORM.mean[1]) / IMAGENET_NORM.std[1];

  assert.ok(Math.abs(tensor[0] - expectedR) < 1e-4);
  assert.ok(Math.abs(tensor[pixelCount] - expectedG) < 1e-4);
});

test('softmax: returns numerically stable probabilities summing to 1.0', () => {
  const res = softmax([2.0, 1.0]);
  assert.ok(Math.abs(res.nostress + res.stress - 1.0) < 1e-6);
  assert.ok(res.nostress > res.stress);

  // Large logits to check numerical stability against overflow
  const large = softmax([1000, 1001]);
  assert.ok(Math.abs(large.nostress + large.stress - 1.0) < 1e-6);
  assert.ok(large.stress > large.nostress);
});

test('TemporalEMAFilter: applies exponential smoothing and dampens jitter', () => {
  const ema = new TemporalEMAFilter(0.20);
  assert.equal(ema.getValue(), null);

  // First sample sets initial value
  ema.update(0.50);
  assert.equal(ema.getValue(), 0.50);

  // Spike to 1.0 is smoothed: 0.2 * 1.0 + 0.8 * 0.5 = 0.60
  ema.update(1.0);
  assert.equal(Math.round(ema.getValue() * 100) / 100, 0.60);

  // Drop to 0.0: 0.2 * 0.0 + 0.8 * 0.60 = 0.48
  ema.update(0.0);
  assert.equal(Math.round(ema.getValue() * 100) / 100, 0.48);

  ema.reset();
  assert.equal(ema.getValue(), null);
});
