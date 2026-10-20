export const STUDY_KEY='pause.prospective-study.v1';
export function pairTiming(records,now=Date.now()){
  if(!records.length)return {stage:'first',canStart:true,remaining:0,elapsed:null};
  if(records.length>=2)return {stage:'complete',canStart:false,remaining:0,elapsed:(Date.parse(records[1].created_at)-Date.parse(records[0].created_at))/1000};
  const elapsed=(now-Date.parse(records[0].created_at))/1000;
  return {stage:elapsed<300?'waiting':elapsed<=600?'repeat':'expired',canStart:elapsed>=300&&elapsed<=600,remaining:Math.max(0,Math.ceil(420-elapsed)),elapsed};
}
export function derivedStudyRecord(result){
  if(result?.acceptancePolicy?.version!=='prospective-acquisition-1'||!Number.isFinite(Date.parse(result.created_at)))return null;
  return {id:result.id,created_at:result.created_at,status:result.status,average:result.average,
    reason:result.reason,acceptancePolicy:result.acceptancePolicy,acquisitionVersion:result.acquisitionVersion,
    coverageDetails:result.coverageDetails,windowScores:result.windowScores,windowDiagnostics:result.windowDiagnostics,
    mlResult:result.mlResult,mode:result.mode,algoVersion:result.algoVersion};
}
