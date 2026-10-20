import test from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {build} from 'esbuild';
const compiled=await build({entryPoints:[new URL('./components/ResultCard.jsx',import.meta.url).pathname],bundle:true,write:false,platform:'node',format:'cjs',jsx:'automatic',external:['react','react-dom']});
const module={exports:{}};
new Function('require','module','exports',compiled.outputFiles[0].text)(createRequire(import.meta.url),module,module.exports);
const ResultCard=module.exports.default;

test('failed scan renders diagnostic children without inventing a score',()=>{
  const html=renderToStaticMarkup(React.createElement(ResultCard,{status:'failed',score:null},React.createElement('details',null,'Technical scan diagnostics')));
  assert.match(html,/Technical scan diagnostics/);
  assert.doesNotMatch(html,/Calm index .* out of 10/);
});
test('result separates processed validity, occupancy and excluded extremes',()=>{
  const html=renderToStaticMarkup(React.createElement(ResultCard,{status:'limited',score:9,windows:[9,6,4],consensusMask:[true,false,false],coverageDetails:{version:'coverage-denominators-1',observedFrames:100,validFrames:5,occupiedSlots:45,totalSlots:45}}));
  assert.match(html,/Valid processed observations: 5.0%/);
  assert.match(html,/Time-slot occupancy: 100.0%/);
  assert.match(html,/Windows excluded from the final score: 2, 3/);
  assert.match(html,/Full observed window range: 4.0/);
  assert.match(html,/not a confidence interval/);
});
