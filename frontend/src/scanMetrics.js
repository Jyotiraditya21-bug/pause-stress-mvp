export function assessFrame(points, faceCount, brightness, previous) {
  if (faceCount !== 1 || !points?.length) return {good: false, reason: faceCount > 1 ? 'Only one person should be in view.' : 'Position your face inside the camera view.'};
  const xs = points.map(p => p.x), ys = points.map(p => p.y);
  const width = Math.max(...xs) - Math.min(...xs);
  const height = Math.max(...ys) - Math.min(...ys);
  const center = {x: (Math.max(...xs) + Math.min(...xs))/2, y: (Math.max(...ys) + Math.min(...ys))/2};
  let reason = '';
  if (brightness < 45) reason = 'Add more light in front of your face.';
  else if (brightness > 225) reason = 'Reduce bright light or backlighting.';
  else if (width < .18 || height < .22) reason = 'Move closer to the camera.';
  else if (width > .8 || height > .9) reason = 'Move a little farther from the camera.';
  else if (Math.abs(center.x - .5) > .2 || Math.abs(center.y - .5) > .22) reason = 'Move your face toward the centre.';
  const movement = previous ? Math.hypot(center.x - previous.x, center.y - previous.y) : 0;
  if (!reason && movement > .035) reason = 'Hold still for a clearer reading.';
  return {good: !reason, reason: reason || 'Good framing. Keep still and look toward the camera.', center, movement};
}

export function summarize(samples, total, duration) {
  const ratio = samples.length / Math.max(total, 1);
  const mean = key => samples.length ? samples.reduce((n,s) => n+s[key],0)/samples.length : null;
  return {quality: ratio >= .75 && samples.length >= 30 ? 'good' : 'poor',
    usablePercent: Math.round(ratio*100), frames: samples.length, durationSeconds: Math.round(duration),
    meanBlinkCoefficient: mean('blink'), meanBrowCoefficient: mean('brow'), meanMovement: mean('movement')};
}
