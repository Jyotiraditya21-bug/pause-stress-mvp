# Scan consensus and confidence review

Reviewed 2026-10-20. No training, fitting, threshold selection, scoring changes or deployment performed. Participant-derived records remain outside Git. Synthetic reproductions are retained in the private verification directory as consensus_synthetic_audit.json.

## Findings

1. **Late change can be filtered away before contradiction is assessed.** The synthetic nine-window sequence `[9,9,9,9,9,9,9,6,4]` returns 9 with limited status. Unfiltered first/last median difference is 1.5; after consensus selection it is zero. This follows the existing rule allowing two outlier windows. The rule cannot distinguish two isolated artifacts from a sustained terminal change. Report both differences and temporal placement of excluded windows. Design an explicit terminal-change policy before fresh evaluation; do not choose it to reproduce any participant's earlier score.

2. **Reported coverage is slot occupancy, not valid-frame proportion.** `usableSlots()` retains a slot if it contains any valid observation, despite a comment suggesting invalid observations prevent that. Synthetic 100-Hz observations with only one valid sample per 0.2-second slot (5% valid) report 100% coverage and good status. Missing observations without callbacks are a different denominator again. Retain separate observed-frame validity, time-slot occupancy, and per-slot valid fractions; label them honestly. Define any revised acceptance thresholds prospectively, not from this pilot.

3. **MAD is within-scan dispersion, not a confidence interval or repeatability bound.** The same synthetic sequence yields range 9–9 because most windows equal 9. The two low windows remain on the chart but cannot widen the MAD. 'Likely scan range' suggests more certainty than this statistic supports. Label it as robust within-scan dispersion; separately display full observed window range, exclusions and limitations. Do not infer a 95% confidence interval or between-session reliability from it.

4. **Good signal is not a cross-session consistency guarantee.** Status depends on acquisition warnings and consensus; `scoreSpread` is calculated but not an independent rejection criterion. `maxScoreSpread` controls each window's distance from the median, not full-series spread. Scans internally stable under different head poses or expressions may still receive different scores against the generic reference.

5. **Failed-results UI hides diagnostic children.** ResultScreen supplies technical diagnostics, but ResultCard returns early on failure and never renders its children. Therefore the promised failed-scan diagnostics cannot currently be inspected through the UI. Render diagnostic children in the failed branch without a score, and retain failed attempts in research coverage denominators with explicit consent.

6. **Geometry and neural probabilities are different, unvalidated outputs.** Neither confidence-like label establishes stress accuracy. Neural `abs(p-0.5)*2` expresses distance from the decision boundary, not calibrated reliability. Generic facial geometry also remains sensitive to mouth configuration and static face shape. Keep the outputs separate.

## Recommended implementation sequence

1. Correct diagnostic visibility and terminology; expose observation counts, slot occupancy, exclusions and unfiltered/filtered temporal statistics. This must not silently change stored scores.
2. Version and freeze a revised acquisition/terminal-change policy using synthetic edge cases and independent development data. Preserve the current pipeline for comparison; no result anchoring, score blending with prior sessions, or tuning to this participant's scores.
3. Re-run image/export checks only if preprocessing or model behavior changes. Evaluate revised scan logic on fresh, correctly timed participant pairs and task/nuisance sessions. Report failures and all acceptance denominators.
4. Keep release validity/repeatability status NOT ESTABLISHED until prospective gates have sufficient real data. Do not ask the participant for repeated informal scans to substitute for a defined protocol.

## Phase 1 reporting corrections completed

As of 2026-10-20, the frontend reports processed-observation validity separately from slot occupancy for new standard scans, shows stored excluded windows and full observed range, labels dispersion as not a confidence interval, labels acquisition status without confidence claims, and renders diagnostic children for failed results. Legacy absent denominator fields are explicitly unavailable. Fifty-two frontend tests and production build pass, including unchanged-score synthetic checks. Existing saved scores and all acquisition/scoring rules are unchanged. Phase 2 policy design and prospective validation remain pending.
