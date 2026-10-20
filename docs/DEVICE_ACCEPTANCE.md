# Physical-device acceptance protocol

Automation does not substitute for physical camera testing. Owner: @Jyotiraditya21-bug. Record browser/OS, device, commit, date, conditions and result; do not attach face images or private logs.

| Evidence | Current status | Procedure |
|---|---|---|
| Real Mac camera / Safari | Not verified | Allow, deny, revoke and retry permission; cancel during model load; background tab and navigate; confirm OS camera indicator turns off. |
| Physical iPhone / Android | Not verified | Portrait/landscape, small screen, interruption, return from lock, front camera orientation, successful/poor-light scans. |
| Startup / processing | Not verified on representative hardware | Cold and warm cache, record click-to-permission and grant-to-first-frame separately; model-ready delay separately. Five runs per device; record medians/ranges. |
| Memory / battery | Not verified | Ten consecutive scans; profile memory after cleanup and record device battery/thermal observations over a fixed 15-minute workload, with idle comparison. |
| Offline / cache update | Automated Chromium only | Online first load, wait for service worker cache, go offline, reload and scan. Test new release activation with an existing old tab. Optional neural assets may be unavailable offline. |

Acceptance: no crash, stuck camera, invented score, or inaccessible recovery. Record unsupported conditions explicitly. Browser permission and hardware startup cannot be guaranteed instantaneous. No clinical or psychological validity is inferred from any row.
