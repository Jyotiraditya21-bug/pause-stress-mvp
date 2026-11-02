import test from 'node:test';
import assert from 'node:assert/strict';
import { deriveScanQuality, QUALITY_THRESHOLDS } from './scanQuality.js';

test('deriveScanQuality returns Good when all criteria meet thresholds', () => {
  const result = deriveScanQuality({
    coveragePercent: 95,
    agreeingWindows: 8,
    totalWindows: 9,
    validFrames: 85,
    observedFrames: 90,
    status: 'ok'
  });
  assert.equal(result.quality, 'good');
  assert.equal(result.label, 'Good');
  assert.ok(result.validRatio >= 0.75);
});

test('deriveScanQuality returns Limited when coverage or consensus or ratio falls below Good but meets Limited', () => {
  // Moderate coverage 60%
  const res1 = deriveScanQuality({
    coveragePercent: 60,
    agreeingWindows: 5,
    totalWindows: 9,
    validFrames: 50,
    observedFrames: 80,
    status: 'ok'
  });
  assert.equal(res1.quality, 'limited');
  assert.equal(res1.label, 'Limited');

  // Low valid ratio 50%
  const res2 = deriveScanQuality({
    coveragePercent: 90,
    agreeingWindows: 7,
    totalWindows: 9,
    validFrames: 45,
    observedFrames: 90,
    status: 'ok'
  });
  assert.equal(res2.quality, 'limited');
  assert.equal(res2.label, 'Limited');

  // Low agreeing windows (3 of 9)
  const res3 = deriveScanQuality({
    coveragePercent: 85,
    agreeingWindows: 3,
    totalWindows: 9,
    validFrames: 70,
    observedFrames: 80,
    status: 'ok'
  });
  assert.equal(res3.quality, 'limited');
});

test('deriveScanQuality returns Insufficient when failing Limited criteria or status is failed', () => {
  // Very low coverage
  const res1 = deriveScanQuality({
    coveragePercent: 30,
    agreeingWindows: 1,
    totalWindows: 9,
    validFrames: 20,
    observedFrames: 80,
    status: 'ok'
  });
  assert.equal(res1.quality, 'insufficient');
  assert.equal(res1.label, 'Insufficient');

  // Failed status
  const res2 = deriveScanQuality({
    coveragePercent: 95,
    agreeingWindows: 8,
    totalWindows: 9,
    validFrames: 85,
    observedFrames: 90,
    status: 'failed'
  });
  assert.equal(res2.quality, 'insufficient');

  // Zero observed frames / empty
  const res3 = deriveScanQuality({});
  assert.equal(res3.quality, 'insufficient');
});
