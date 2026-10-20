// Presentation only: never reconstruct historical selection or change scores.
export function windowTransparency(windows=[],mask){
  const values=windows.filter(Number.isFinite);
  const known=Array.isArray(mask)&&mask.length===windows.length&&mask.every(v=>typeof v==='boolean');
  return {observedRange:values.length?[Math.min(...values),Math.max(...values)]:null,
    excluded:known?windows.flatMap((v,i)=>Number.isFinite(v)&&!mask[i]?[i+1]:[]):null};
}

export function normalizeCoverageDetails(value){
  if(!value||value.version!=='coverage-denominators-1')return null;
  const {observedFrames,validFrames,occupiedSlots,totalSlots}=value;
  if(![observedFrames,validFrames,occupiedSlots,totalSlots].every(n=>Number.isSafeInteger(n)&&n>=0)||
    totalSlots===0||validFrames>observedFrames||occupiedSlots>totalSlots)return null;
  return {...value,validFramePercent:observedFrames?100*validFrames/observedFrames:null,
    timeSlotOccupancyPercent:100*occupiedSlots/totalSlots};
}
