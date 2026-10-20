# Prospective acceptance policy — frozen 2026-10-20

Version: prospective-acquisition-1. Research candidate, not adopted for the default/deployed experience. The existing scoring formula, sigma floor, feature definitions, consensus radius and model weights are unchanged. The old participant scans are exploratory development observations and cannot be held-out validation for this policy. No parameter was searched or optimized against their scores or labels.

Fixed engineering rules, declared before candidate implementation/evaluation:

- Keep the fixed 10-second video-clock capture and exclude the first second.
- A time slot requires at least 80% valid processed observations within that slot. Missing slots stay missing.
- Require at least 45 processed observations after settling (the existing 45-slot schedule represents a nominal minimum 5-Hz sampling rate), at least 80% valid processed observations overall, at least 80% occupied slots, and at least 8 measured one-second windows.
- Require the unfiltered early/late median difference ≤0.75 index points, applying the existing half-difference tolerance BEFORE consensus filtering as an additional gate.
- Reject when both of the first two or both of the last two measured window positions are excluded by the existing consensus rule. This distinguishes terminal runs from a single isolated spike. Missing edge windows do not masquerade as excluded observations; other coverage/visibility gates still apply.
- All existing rejection rules also apply. Failed scans return no aggregate score or range. Candidate outputs preserve measured windows and report policy failure codes.

The 80% and0.75 thresholds reuse existing engineering quality settings; the nominal sample floor comes from the existing slot schedule. These are unvalidated priors, not clinical thresholds, and may reject more scans. Do not relax them after examining new participant data. Any change requires a new version, a new freeze and fresh evaluation data.

Candidate is opt-in with `?policy=prospective-1&tolerance=0&diagnostics=1&ml=1`. It forces the standard10-second path, not movement-tolerant mode. Candidate and legacy records have different acquisition versions so History cannot connect them as one trend. Existing saved results are preserved.

Synthetic checks: complete stable streams, sparse5%-valid observations, no data, duplicate/backward timestamps, exact boundary fractions, terminal shifts and isolated outliers. Python mirrors candidate acquisition using the existing numerical scorer; cross-language fixtures must agree on acceptance and scores. No participant image/video inputs are used in these checks.

## Fresh participant protocol and release gate

Use the collection protocol in VERIFICATION.md. Keep model, pipeline and policy hashes, task labels, timestamps, accepted/failed status, valid-observation counts, slot occupancy and derived diagnostic windows. Consent precedes camera processing/saving; no raw images/video/landmarks stored or uploaded by default.

Collect two visits5–10minutes apart, two scans per rest/speech/arithmetic condition, counterbalanced task order, target20 consenting adults. Smaller samples are feasibility only. Retain every failed attempt; never repeat until a preferred score appears. Compare legacy/candidate on the same offline observations when consented matching inputs exist; separate sessions alone are not a paired pipeline comparison.

Predeclared release criteria remain: both within-subject rest-vs-task AUC lower95%CI bounds>0.60; every matched nuisance mean absolute shift<0.5× each absolute task effect; MDC95≤1point and ICC(2,1) lower95%CI≥0.75 for the0–10 output; accepted/attempted coverage≥80% in every condition. Seed42,1000subject bootstrap draws. No data or undefined estimates mean NOT ESTABLISHED, never PASS. Geometry/neural outputs analysed separately. These gates assess an engineering pilot, not clinical stress validity.

Current release decision: HOLD. No fresh candidate participant results exist at freeze time. Do not deploy/adopt candidate as validated based on synthetic tests or old image-classification metrics.
