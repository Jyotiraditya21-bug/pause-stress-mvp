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
test('invalid historical denominator fields are unavailable rather than misleading or crashing',()=>{
  assert.equal(normalizeCoverageDetails({observedFrames:'bad'}),null);
  assert.equal(normalizeCoverageDetails({version:'coverage-denominators-1',observedFrames:1,validFrames:2,occupiedSlots:1,totalSlots:45}),null);
  const r=normalizeCoverageDetails({version:'coverage-denominators-1',observedFrames:100,validFrames:5,occupiedSlots:45,totalSlots:45,validFramePercent:100});
  assert.equal(r.validFramePercent,5);assert.equal(r.timeSlotOccupancyPercent,100);
});
