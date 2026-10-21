# Experimental facial check-in release checklist

Reviewed 2026-10-20. This checklist defines the current GitHub Pages release. It is a software release checklist; passing it does not validate stress measurement.

## Shipped behavior

- Static React frontend on GitHub Pages; camera analysis and optional history stay in the browser. No FastAPI deployment, account, synchronization, or cloud storage.
- Default scan: fixed 10-second geometric Calm index (`quick-2.0`, `capture-clock-1`). The prospective acquisition policy (`prospective-acquisition-1`, SHA-256 `8666fc4ec616ef061b3c570e9305964131ff357be96de27adb1970318e72eb13`) is available only by explicit opt-in and remains unvalidated. Movement-tolerant acquisition is also opt-in.
- MobileNetV3-Small neural output is enabled by default and can be turned off in Settings. A saved off preference is respected; when browser storage is unavailable the current in-memory choice still applies. It remains an experimental dataset-class output, separate from the geometric index. Camera preview does not wait for neural initialization. Model asset SHA-256: `55a5cf41a63f71763127fc62e638975a7e35acf18d973c01591e1a658be36b5f`. It does not measure a person's stress.
- Raw camera video and audio are not uploaded or persisted by the app. Saving results and guided research records requires explicit user action/consent and writes derived data to local browser storage. Users can export and delete saved records.
- Main flow: onboarding, camera permission, positioning, scan, result, optional save, and History. Camera preview attaches as soon as permission is granted while face-analysis initialization continues. Model warmup starts on button hover/focus or scan request; there is no high-priority model download or eager initialization during initial rendering. After loading, the service worker may cache analysis assets for offline use.

## Known limits and deferred evidence

- The Calm index is experimental and cannot diagnose or establish psychological/clinical stress. Image classifier metrics describe dataset labels only.
- Dataset label provenance, license, participant separation and model redistribution rights remain unresolved. Do not reuse or commercially redistribute the optional neural model based on this release checklist.
- Real-device camera permission/interruption testing, physical Safari/iPhone checks, representative startup/memory/battery measurements, broader participant repeatability, task discrimination and nuisance/subgroup evaluation remain outstanding.
- Local browser storage is not encrypted, is tied to one browser profile, and is erased when site data is cleared. Offline scan availability depends on the app and model assets having been cached successfully.

## Deployment gates

- [x] Frontend build, unit tests, parity checks and browser/offline suites have passed in the reported release workflow.
- [x] Claims explicitly describe an experimental facial index and validation hold.
- [x] Pages deployment waits for browser/offline checks and Lighthouse at 0.90 minimum category scores; the required reusable Checks workflow covers frontend build, backend boundary tests and research parity. A failed check blocks deployment.
- [x] Rollback and service-worker recovery steps are documented in `DEPLOY.md`.
- [x] Delayed-model camera-preview regression passes in Chromium; face preview appears before model initialization completes.
- [x] Local Lighthouse preview: performance 0.98, accessibility 1.00, LCP 2.0 s, TBT 0 ms after removing eager model downloads from initial page load.
- [ ] Smoke-test the resulting live commit. The Pages workflow `39443667426` passed `live-smoke` against f24aa3a, including the camera, history, accessibility, mobile, network and offline checks. It reported 101 ms to the first synthetic camera frame (68 ms after permission grant). Physical device timing remains unverified.
- [ ] Complete physical-device camera and representative performance checks before claiming supported-device coverage.
- [ ] Resolve third-party/model/dataset rights before expanding neural-model distribution.

Known development-only advisories are tracked in `RELEASE_AUDIT_2026-10-20.md`; production dependency audit reported none.

The MVP may remain an experimental demo while the empirical stress-validation gates remain open. Do not describe the validation hold as a pass.

## Phase status and evidence boundaries

| Phase | Engineering disposition | Remaining evidence or work |
|---|---|---|
| 0 Scope | Frozen in this checklist and asset manifest | Prospective policy remains opt-in/unvalidated. |
| 1 Repository | Build checks, unused-runtime cleanup, notices and dependency/secret-pattern audit implemented | Model rights unknown; development-only advisories unresolved. |
| 2 Architecture | Static frontend, browser computation/storage, no public API | No cloud feature in this release. |
| 3 Scan | Independent camera preview, gating/timestamps/caps, missing-data handling, teardown/regressions | Physical camera interruptions need device testing. |
| 4 Flows | Onboarding, permission/failure/cancel, result/save/history tested | Physical OS permission UI remains unverified. |
| 5 UI | Existing light palette/layout preserved; responsive/focus/accessibility checks | Human assistive-technology review remains useful. |
| 6 Visuals | Real progress/countdown, gaps/exclusions, reduced-motion/text equivalents implemented | No physiological claim inferred. |
| 7 Results/history | Separate geometry/neural output, coverage, compatibility grouping/export/delete | Neural provenance unknown. |
| 8 Backend | Browser-only architecture selected; FastAPI not published | Accounts/sync deferred. |
| 9 Privacy/security | Local processing, explicit save, disabled monitoring, local fonts, integrity/CSP checks | Development advisory follow-up and model-license review remain open. |
| 10 Performance/offline | Lighthouse and cached offline automation pass | Physical-device startup/memory/battery evidence outstanding. |
| 11 Testing | Unit/parity/backend/Chromium/WebKit/offline CI required | Real Safari/iPhone camera and physical device matrix outstanding. |
| 12 Evidence | Limitations and unknown provenance explicit | Clinical/live stress validity, participant-separated repeatability/nuisance evidence not established. |
| 13 Deployment | HTTPS/base paths, required CI, exact commit metadata, rollback/cache instructions | Each candidate must pass its own checks. |
| 14 Live | Automated exact-commit smoke added after deployment | Confirm the current run/artifact; never infer live success from localhost. |
| 15 Maintenance | Named owner, sanitized reports, dependency review, versioning and rollback documented | Ongoing operational work; not permanently complete. |

The original 16-phase program is not wholly complete: physical-device testing, rights clarification, development-tool remediation and empirical validation remain open. The implemented software is an experimental release candidate until its production workflow and live smoke pass.
