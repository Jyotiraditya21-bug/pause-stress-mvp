import {QuickIndex,geometry,headPose} from '../frontend/src/liveIndex.js';
import {assessQuickFrame,faceBrightness} from '../frontend/src/scanMetrics.js';
import fs from 'node:fs';
const input=JSON.parse(fs.readFileSync(0,'utf8'));
const output=input.map(f=>{
  const points=f.points.map(([x,y])=>({x,y}));
  const brightness=faceBrightness(f.pixels,f.width,f.height,points);
  const quality=assessQuickFrame(points,f.faceCount,brightness,f.previous);
  const scan=new QuickIndex();
  for(const row of f.scan) scan.update(row.time,row.points.map(([x,y])=>[x*f.width,y*f.height]),row.pose,row.good,{brightness:row.brightness});
  return {brightness,quality,pose:headPose(f.poseMatrix),geometry:geometry(f.scan[1].points.map(([x,y])=>[x*f.width,y*f.height])),result:scan.finish()};
});
process.stdout.write(JSON.stringify(output));
