import test from 'node:test';
import assert from 'node:assert/strict';
import {awaitResource} from './resourceWait.js';
test('successful resource is returned',async()=>{assert.equal(await awaitResource(Promise.resolve(7),{isCurrent:()=>true,message:'timeout'}),7);});
test('cancelled initialization disposes of its late resource',async()=>{
  let disposed=0;
  await assert.rejects(awaitResource(Promise.resolve(7),{isCurrent:()=>false,dispose:()=>disposed++,message:'timeout'}),{name:'AbortError'});
  assert.equal(disposed,1);
});
test('timed-out initialization disposes of a late resource',async()=>{
  let release,disposed=0;
  const source=new Promise(resolve=>{release=resolve;});
  await assert.rejects(awaitResource(source,{isCurrent:()=>true,dispose:()=>disposed++,message:'permission pending',timeoutMs:5}),/permission pending/);
  release(7);await Promise.resolve();assert.equal(disposed,1);
});
