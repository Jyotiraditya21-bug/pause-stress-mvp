import test from 'node:test';
import assert from 'node:assert/strict';
import { computeGroupInsights, median, mad } from './historyInsights.js';

test('median and mad calculations', () => {
  assert.equal(median([1, 2, 3, 4, 5]), 3);
  assert.equal(median([1, 2, 3, 4]), 2.5);
  assert.equal(mad([2, 2, 2]), 0);
  assert.equal(mad([1, 2, 3, 4, 5]), 1);
});

test('computeGroupInsights computes counts, dates, median, mad and quality share', () => {
  const baseTime = Date.parse('2026-10-20T10:00:00.000Z');
  const rows = [
    { id: '1', created_at: new Date(baseTime).toISOString(), average: 6.0, quality: 'good' },
    { id: '2', created_at: new Date(baseTime + 10 * 60 * 1000).toISOString(), average: 6.4, quality: 'good' },
    { id: '3', created_at: new Date(baseTime + 20 * 60 * 1000).toISOString(), average: 6.2, quality: 'limited' },
    { id: '4', created_at: new Date(baseTime + 86400 * 1000).toISOString(), average: 7.0, quality: 'good' }
  ];

  const insights = computeGroupInsights(rows);
  assert.equal(insights.scansSaved, 4);
  assert.equal(insights.daysWithScans, 2);
  assert.equal(Number(insights.medianScore.toFixed(1)), 6.3);
  assert.ok(insights.madScore !== null);
  assert.equal(insights.goodQualityShare, 75); // 3 of 4 are good
  assert.equal(insights.repeatPairsCount, 2); // 1-2 and 2-3 are within 30 min, 3-4 is 1 day later
  assert.equal(insights.repeatConsistency, null); // fewer than 3 pairs
});

test('computeGroupInsights computes repeat consistency when >= 3 repeat pairs exist', () => {
  const baseTime = Date.parse('2026-10-20T10:00:00.000Z');
  const rows = [
    { id: '1', created_at: new Date(baseTime).toISOString(), average: 6.0, quality: 'good' },
    { id: '2', created_at: new Date(baseTime + 5 * 60 * 1000).toISOString(), average: 6.2, quality: 'good' }, // diff 0.2
    { id: '3', created_at: new Date(baseTime + 10 * 60 * 1000).toISOString(), average: 6.5, quality: 'good' }, // diff 0.3
    { id: '4', created_at: new Date(baseTime + 15 * 60 * 1000).toISOString(), average: 6.4, quality: 'good' }  // diff 0.1
  ];

  const insights = computeGroupInsights(rows);
  assert.equal(insights.repeatPairsCount, 3);
  // differences: 0.2, 0.3, 0.1 => median is 0.2
  assert.equal(Number(insights.repeatConsistency.toFixed(1)), 0.2);
});
