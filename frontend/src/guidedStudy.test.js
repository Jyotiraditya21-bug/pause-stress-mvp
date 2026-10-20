import test from 'node:test';
import assert from 'node:assert/strict';
import {pairTiming,derivedStudyRecord} from './guidedStudy.js';
test('guided timing uses completion timestamps and enforces the fixed interval',()=>{
 const a={created_at:'2026-10-20T00:00:00Z'};
 assert.equal(pairTiming([a],Date.parse(a.created_at)+299000).canStart,false);
 assert.equal(pairTiming([a],Date.parse(a.created_at)+300000).canStart,true);
 assert.equal(pairTiming([a],Date.parse(a.created_at)+600000).canStart,true);
 assert.equal(pairTiming([a],Date.parse(a.created_at)+601000).stage,'expired');
});
test('study records retain failed attempts but never raw camera data or prior policies',()=>{
 assert.equal(derivedStudyRecord({created_at:new Date().toISOString()}),null);
 const r=derivedStudyRecord({id:'failure',created_at:'2026-10-20T00:00:00Z',acceptancePolicy:{version:'prospective-acquisition-1'},status:'failed',average:null,landmarks:[1],video:'private'});
 assert.equal(r.status,'failed');assert.equal(r.average,null);
 assert.ok(!('landmarks' in r));assert.ok(!('video' in r));
});
