/**
 * On-device Machine Learning inference utilities for the Pause experimental face model.
 * Handles bounding-box face cropping, ImageNet normalization, softmax probability extraction,
 * and temporal EMA filtering (alpha=0.20) as established in Phases 8 & 9.
 */

export const MODEL_INPUT_SIZE = 224;
export const DEFAULT_EMA_ALPHA = 0.20;

export const IMAGENET_NORM = {
  mean: [0.485, 0.456, 0.406],
  std: [0.229, 0.224, 0.225]
};

/**
 * Calculates a bounding box around facial landmarks with an expansion margin.
 * @param {Array<{x: number, y: number}>} landmarks - Normalized landmark coordinates [0, 1]
 * @param {number} width - Source image/video width
 * @param {number} height - Source image/video height
 * @param {number} margin - Expansion margin ratio (default 0.15 for 15% padding)
 */
export function getFaceBoundingBox(landmarks, width, height, margin = 0.15) {
  if (!landmarks || landmarks.length === 0) return null;
  let minX = 1, maxX = 0, minY = 1, maxY = 0;
  for (let i = 0; i < landmarks.length; i++) {
    const p = landmarks[i];
    if (p.x < minX) minX = p.x;
    if (p.x > maxX) maxX = p.x;
    if (p.y < minY) minY = p.y;
    if (p.y > maxY) maxY = p.y;
  }

  let boxW = (maxX - minX) * width;
  let boxH = (maxY - minY) * height;
  const side = Math.max(boxW, boxH) * (1 + margin * 2);

  const centerX = ((minX + maxX) / 2) * width;
  const centerY = ((minY + maxY) / 2) * height;

  const left = Math.max(0, centerX - side / 2);
  const top = Math.max(0, centerY - side / 2);
  const actualW = Math.min(width - left, side);
  const actualH = Math.min(height - top, side);

  return { left, top, width: actualW, height: actualH };
}

/**
 * Normalizes RGBA pixel data into a flat Float32Array in NCHW format [1, 3, 224, 224].
 * @param {Uint8ClampedArray} rgbaPixels - RGBA pixel array from a 224x224 canvas
 * @returns {Float32Array} NCHW normalized tensor data
 */
export function normalizePixelsToNCHW(rgbaPixels) {
  const pixelCount = MODEL_INPUT_SIZE * MODEL_INPUT_SIZE;
  const tensor = new Float32Array(3 * pixelCount);

  const rOffset = 0;
  const gOffset = pixelCount;
  const bOffset = 2 * pixelCount;

  const { mean, std } = IMAGENET_NORM;

  for (let i = 0; i < pixelCount; i++) {
    const rgbaIdx = i * 4;
    const r = rgbaPixels[rgbaIdx] / 255.0;
    const g = rgbaPixels[rgbaIdx + 1] / 255.0;
    const b = rgbaPixels[rgbaIdx + 2] / 255.0;

    tensor[rOffset + i] = (r - mean[0]) / std[0];
    tensor[gOffset + i] = (g - mean[1]) / std[1];
    tensor[bOffset + i] = (b - mean[2]) / std[2];
  }

  return tensor;
}

/**
 * Computes numerically stable softmax probabilities from 2-class logits.
 * @param {number[]} logits - Raw model output [logit_nostress, logit_stress]
 * @returns {{ nostress: number, stress: number }} Class probabilities
 */
export function softmax(logits) {
  if (!logits || logits.length < 2) return { nostress: 0.5, stress: 0.5 };
  const maxLogit = Math.max(logits[0], logits[1]);
  const exp0 = Math.exp(logits[0] - maxLogit);
  const exp1 = Math.exp(logits[1] - maxLogit);
  const sum = exp0 + exp1;
  return {
    nostress: exp0 / sum,
    stress: exp1 / sum
  };
}

/**
 * Temporal Exponential Moving Average (EMA) filter for video stream stability.
 * Slashes raw frame jitter by ~83% as validated in Phase 8.
 */
export class TemporalEMAFilter {
  constructor(alpha = DEFAULT_EMA_ALPHA) {
    this.alpha = alpha;
    this.value = null;
    this.frameCount = 0;
  }

  update(rawProbability) {
    if (typeof rawProbability !== 'number' || !Number.isFinite(rawProbability)) {
      return this.value;
    }
    this.frameCount++;
    if (this.value === null) {
      this.value = rawProbability;
    } else {
      this.value = this.alpha * rawProbability + (1 - this.alpha) * this.value;
    }
    return this.value;
  }

  getValue() {
    return this.value;
  }

  reset() {
    this.value = null;
    this.frameCount = 0;
  }
}
