import {ScanReliability} from './scanReliability.js';
import policy from './prospectivePolicy.json' with {type:'json'};
import fingerprint from './prospectivePolicyFingerprint.json' with {type:'json'};
export const PROSPECTIVE_POLICY=Object.freeze(policy);
export class ProspectiveReliability extends ScanReliability {
  usableSlots(){
    const slots=super.usableSlots();
    for(const [id,samples] of this.slots){
      if(samples.filter(Boolean).length/samples.length<policy.minSlotValidFraction)slots.delete(id);
    }
    return slots;
  }
  finish(){
    const r=super.finish(),d=r.coverageDetails,codes=[];
    if(d.observedFrames<policy.minObservedSamples)codes.push('insufficient_observations');
    if(d.validFramePercent===null||d.validFramePercent<100*policy.minObservationValidFraction)codes.push('insufficient_valid_observations');
    if(d.timeSlotOccupancyPercent<100*policy.minSlotOccupancy)codes.push('insufficient_slot_occupancy');
    if(r.reliability.usableWindows<policy.minMeasuredWindows)codes.push('insufficient_windows');
    if(r.reliability.halfDifference!==null&&r.reliability.halfDifference>policy.maxUnfilteredHalfDifference)codes.push('unfiltered_temporal_change');
    const excluded=i=>Number.isFinite(r.windowScores[i])&&!r.consensusWindowMask[i];
    if(policy.rejectExcludedTerminalPair&&((excluded(0)&&excluded(1))||(excluded(7)&&excluded(8))))codes.push('excluded_terminal_pair');
    r.acceptancePolicy={version:policy.version,policySha256:fingerprint.sha256,adopted:false,failureCodes:codes};
    r.reliability.ruleVersion=policy.version;
    if(codes.length){
      r.status='failed';r.quality='poor';r.average=null;r.latest=null;r.range=null;
      r.reason=r.failReason='The scan did not meet the prospective acquisition rules: '+codes.join(', ')+'. No score was produced.';
      r.warnings=[];
    }
    return r;
  }
}
