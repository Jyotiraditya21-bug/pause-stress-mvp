export function assessFrame(points, faceCount, brightness, previous) {
  if (faceCount !== 1 || !points?.length) return {good: false, reason: faceCount > 1 ? 'Only one person should be in view.' : 'Position your face inside the camera view.'};
  const xs = points.map(p => p.x), ys = points.map(p => p.y);
  const width = Math.max(...xs) - Math.min(...xs);
  const height = Math.max(...ys) - Math.min(...ys);
  const center = {x: (Math.max(...xs) + Math.min(...xs))/2, y: (Math.max(...ys) + Math.min(...ys))/2};
  let reason = '';
  if (brightness < 18) reason = 'Add more light in front of your face.';
  else if (brightness > 240) reason = 'Reduce bright light or backlighting.';
  else if (width < .15 || height < .20) reason = 'Move closer to the camera.';
  else if (width > .85 || height > .95) reason = 'Move a little farther from the camera.';
  else if (Math.abs(center.x - .5) > .24 || Math.abs(center.y - .5) > .24) reason = 'Move your face toward the centre.';
  const movement = previous ? Math.hypot(center.x - previous.x, center.y - previous.y) : 0;
  if (!reason && movement > .05) reason = 'Hold still for a clearer reading.';
  return {good: !reason, reason: reason || 'Good framing. Keep still and look toward the camera.', center, movement};
}

export function summarize(samples, total, duration) {
  const ratio = samples.length / Math.max(total, 1);
  const mean = key => samples.length ? samples.reduce((n,s) => n+s[key],0)/samples.length : null;
  return {quality: ratio >= .75 && samples.length >= 30 ? 'good' : 'poor',
    usablePercent: Math.round(ratio*100), frames: samples.length, durationSeconds: Math.round(duration),
    meanBlinkCoefficient: mean('blink'), meanBrowCoefficient: mean('brow'), meanMovement: mean('movement')};
}


// Scan-specific checks keep the existing assessFrame API available to old callers.
export function assessQuickFrame(points,faceCount,brightness,previous) {
  if(!Number.isFinite(brightness))return {good:false,reason:'Position your face inside the circle.'};
  const q=assessFrame(points,faceCount,brightness,previous);
  if(!q.good)return q;
  const width=Math.max(...points.map(p=>p.x))-Math.min(...points.map(p=>p.x));
  const height=Math.max(...points.map(p=>p.y))-Math.min(...points.map(p=>p.y));
  let reason='';
  if(width<.15||height<.20)reason='Move closer so your face fills the circle.';
  else if(width>.85||height>.95)reason='Move a little farther from the camera.';
  else if(Math.abs(q.center.x-.5)>.24||Math.abs(q.center.y-.5)>.24)reason='Centre your face inside the circle.';
  else if(q.movement>.05)reason='Hold still for a repeatable scan.';
  return {...q,good:!reason,reason:reason||q.reason};
}

export function faceBrightness(pixels,width,height,points) {
  if(!points?.length)return NaN;
  const xs=points.map(p=>p.x),ys=points.map(p=>p.y);
  if(![...xs,...ys].every(Number.isFinite))return NaN;
  const x0=Math.max(0,Math.floor(Math.min(...xs)*width)),x1=Math.min(width,Math.ceil(Math.max(...xs)*width));
  const y0=Math.max(0,Math.floor(Math.min(...ys)*height)),y1=Math.min(height,Math.ceil(Math.max(...ys)*height));
  let sum=0,n=0;
  for(let y=y0;y<y1;y++)for(let x=x0;x<x1;x++){
    const i=(y*width+x)*4;sum+=(pixels[i]+pixels[i+1]+pixels[i+2])/3;n++;
  }
  return n?sum/n:NaN;
}
