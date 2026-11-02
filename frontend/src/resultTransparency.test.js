import test from 'node:test';
import assert from 'node:assert/strict';
import {windowTransparency} from './resultTransparency.js';
test('presentation retains excluded extremes and never infers historical membership',()=>{
  assert.deepEqual(windowTransparency([9,6,4],[true,false,false]),{observedRange:[4,9],excluded:[2,3]});
  assert.equal(windowTransparency([9,6,4]).excluded,null);
  assert.equal(windowTransparency([9,6,4],[true]).excluded,null);
  assert.deepEqual(windowTransparency([null,5],[false,true]),{observedRange:[5,5],excluded:[]});
});

import {normalizeCoverageDetails} from './resultTransparency.js';
test('normalizeCoverageDetails handles weighted-coverage-1, old coverage-denominators-1, and missing or invalid data',()=>{
  // 1. Missing or invalid data returns null
  assert.equal(normalizeCoverageDetails(null),null);
  assert.equal(normalizeCoverageDetails(undefined),null);
  assert.equal(normalizeCoverageDetails({observedFrames:'bad'}),null);
  assert.equal(normalizeCoverageDetails({version:'unknown-version',observedFrames:10,validFrames:8,occupiedSlots:40,totalSlots:45}),null);
  assert.equal(normalizeCoverageDetails({version:'coverage-denominators-1',observedFrames:1,validFrames:2,occupiedSlots:1,totalSlots:45}),null);
  assert.equal(normalizeCoverageDetails({version:'weighted-coverage-1',observedFrames:10,validFrames:12,occupiedSlots:10,totalSlots:45}),null);
  assert.equal(normalizeCoverageDetails({version:'weighted-coverage-1',observedFrames:10,validFrames:5,occupiedSlots:50,totalSlots:45}),null);

  // 2. Old version: coverage-denominators-1
  const oldRes=normalizeCoverageDetails({version:'coverage-denominators-1',observedFrames:100,validFrames:5,occupiedSlots:45,totalSlots:45,validFramePercent:100});
  assert.equal(oldRes.validFramePercent,5);
  assert.equal(oldRes.timeSlotOccupancyPercent,100);

  // 3. Current version: weighted-coverage-1
  const weightedRes=normalizeCoverageDetails({version:'weighted-coverage-1',observedFrames:90,validFrames:72,occupiedSlots:36,totalSlots:45});
  assert.equal(weightedRes.validFramePercent,80);
  assert.equal(weightedRes.timeSlotOccupancyPercent,80);
  assert.equal(weightedRes.occupiedSlots,36);
  assert.equal(weightedRes.totalSlots,45);
});
