import {TolerantScan,frontalize,poseWeight,speedWeight,rangeWeight,weightedMedian,adaptiveState} from '../frontend/src/tolerantScan.js';
import {toleranceFixtures} from '../frontend/src/toleranceFixtures.js';
const output=toleranceFixtures().map(f=>{
  const scan=new TolerantScan({baseline:f.baseline,frontalize3d:f.frontalize3d});
  for(const r of f.frames)scan.update(r.time,r.points,r.pose,true,r.context);
  return{fixture:f,result:scan.finish(f.frames.length/10)};
});
const angle=.3,c=Math.cos(angle),s=Math.sin(angle);
const matrix={rows:4,columns:4,data:[c,0,-s,0,0,1,0,0,s,0,c,0,0,0,0,1]};
const probes={pose:[null,[0,20,0],[0,30,0],[0,40,0],[0,45,0],[0,51,0]].map(poseWeight),speed:[0,.15,.4,.6,.8,1,1.1].map(speedWeight),light:[17,18,23,28,120,230,235,240,241].map(v=>rangeWeight(v,18,240,10)),median:weightedMedian([null,1,5,9],[5,1,10,1]),adaptive:[adaptiveState(9,.8),adaptiveState(10,.3),adaptiveState(13,.6),adaptiveState(20,0)]};
process.stdout.write(JSON.stringify({output,probes,rotation:{points:[[1,2,3],[4,5,6]],matrix,result:frontalize([[1,2,3],[4,5,6]],matrix)}}));
