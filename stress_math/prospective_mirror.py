"""Opt-in prospective acquisition mirror; existing deployed module APIs stay unchanged."""
import json,hashlib
from .deployed_mirror import ScanReliability,QuickIndex,FRONTEND,finite,median,BASELINE_KEYS
POLICY=json.loads((FRONTEND/'prospectivePolicy.json').read_text())

class ProspectiveReliability(ScanReliability):
    def usable_slots(self):
        slots=super().usable_slots()
        for i,samples in self.slots.items():
            if sum(s is not None for s in samples)/len(samples)<POLICY['minSlotValidFraction']:
                slots.pop(i,None)
        return slots

    def finish(self):
        r=super().finish()
        observations=[s for samples in self.slots.values() for s in samples]
        valid=sum(s is not None for s in observations)
        percentage=100*valid/len(observations) if observations else None
        values=[v for v in r['windowScores'] if finite(v)]
        centre=median(values)
        mask=[finite(v) and abs(v-centre)<=1 for v in r['windowScores']]
        r['consensusWindowMask']=mask
        r['coverageDetails']=dict(version='coverage-denominators-1',scope='Processed observations after the first second; not all camera frames.',observedFrames=len(observations),validFrames=valid,validFramePercent=percentage,occupiedSlots=r['reliability']['usableSlots'],totalSlots=45,timeSlotOccupancyPercent=r['coveragePercent'])
        codes=[]
        if len(observations)<POLICY['minObservedSamples']:codes.append('insufficient_observations')
        if percentage is None or percentage<100*POLICY['minObservationValidFraction']:codes.append('insufficient_valid_observations')
        if r['coveragePercent']<100*POLICY['minSlotOccupancy']:codes.append('insufficient_slot_occupancy')
        if r['reliability']['usableWindows']<POLICY['minMeasuredWindows']:codes.append('insufficient_windows')
        half=r['reliability']['halfDifference']
        if half is not None and half>POLICY['maxUnfilteredHalfDifference']:codes.append('unfiltered_temporal_change')
        def excluded(i):return finite(r['windowScores'][i]) and not mask[i]
        if POLICY['rejectExcludedTerminalPair'] and ((excluded(0) and excluded(1)) or (excluded(7) and excluded(8))):codes.append('excluded_terminal_pair')
        r['acceptancePolicy']=dict(version=POLICY['version'],policySha256=hashlib.sha256((FRONTEND/'prospectivePolicy.json').read_bytes()).hexdigest(),adopted=False,failureCodes=codes)
        r['reliability']['ruleVersion']=POLICY['version']
        if codes:
            r.update(status='failed',quality='poor',average=None,latest=None,range=None,warnings=[])
            r['reason']=r['failReason']='The scan did not meet the prospective acquisition rules: '+', '.join(codes)+'. No score was produced.'
        return r

class ProspectiveQuickIndex(QuickIndex):
    def __init__(self,baseline=None,mode=None):
        super().__init__(baseline,mode)
        self.measurements=ProspectiveReliability(self.keys,self.score,BASELINE_KEYS)
