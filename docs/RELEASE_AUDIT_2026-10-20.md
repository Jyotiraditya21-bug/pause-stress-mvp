# Release audit — 2026-10-20

The default release remains a local browser experimental geometric check-in. No backend deployment, accounts or sync. Optional neural output remains distinct and opt-in. User explicitly chose to keep training provenance unknown; no rights or validation clearance is asserted.

- Production npm audit: zero reported vulnerabilities (2026-10-20). This is an advisory snapshot, not proof of absence of defects.
- Frozen SHA-256 manifest covers MediaPipe assets, neural weights/specification, reference and acquisition configurations. Builds verify this manifest; deliberate changes require review and version updates.
- Removed unused public ONNX runtime duplicates; active runtime assets come from the locked npm package via Vite imports.
- Same Figtree font and weights are now served locally, with OFL notice; palette/layout preserved. Direct runtime license notices and a lockfile inventory are included. Model/data rights remain unknown.
- Pages requires frontend/backend/research checks, browser/offline checks and Lighthouse before deploying. Exact source commit is exposed in release.json.
- Technical monitoring remains disabled. Maintainer triage and rollback are documented in MAINTENANCE.md and DEPLOY.md.
- Representative physical device, memory/battery, participant repeatability and stress-validity evidence remain open. See DEVICE_ACCEPTANCE.md and RELEASE_CHECKLIST.md. Never substitute automated test passes for that evidence.

## Verification and unresolved engineering risks

- 60 unit tests pass. Chromium flow/accessibility suite passed; new pending-model cancel/restart/navigation regression passes after teardown fixes. Cached production offline initialization passes.
- Final local Lighthouse: performance 0.94, accessibility/best practices/SEO 1.00, LCP 2.62 seconds, TBT 0 ms. This single synthetic run is not representative-device evidence.
- Camera tracks and MediaPipe/ONNX analysis resources are released on exit, including late initialization; navigation remounts the suspense boundary so a lazy destination cannot keep the old camera mounted.
- Tracked filename and credential-pattern audit found no secret/private-data candidates; `stress_math/datasets/__init__.py` is source code, not a dataset. This scan is not a forensic audit of all git history.
- Full npm audit: 17 development-only Lighthouse-toolchain findings (11 high, 4 moderate, 2 low), zero critical. npm proposes a breaking downgrade of @lhci/cli rather than a compatible complete fix. No forced downgrade applied. Owner @Jyotiraditya21-bug must review upstream fixes monthly. Lighthouse runs only against localhost and writes reports locally, with no participant data or public report upload; these packages are not shipped in the browser bundle. Do not run this toolchain on untrusted sites or expose its development server. These findings remain unresolved and are not counted as fixed.
- Deployment now runs a synthetic live smoke job after Pages publication. It checks exact commit metadata, onboarding, preview during blocked model download, cleanup, honest no-face failure, synthetic history/export/delete, accessibility/mobile layout, same-origin requests and cached offline initialization. CI uploads the evidence without face recordings.
