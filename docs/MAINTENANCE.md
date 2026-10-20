# Release maintenance

The repository owner, @Jyotiraditya21-bug, owns triage and recovery for the Pages demo. Review new reports against the deployed commit and reproduce with synthetic inputs where possible. Ask reporters not to attach face images, video, saved session exports, or other biometric data. A useful report contains the release URL/commit, browser and OS version, device class, steps to reproduce, expected behavior, actual behavior, and a sanitized console/network error.

For a release-blocking frontend fault, revert the faulty commit on `main` and follow the rollback steps in `DEPLOY.md`. Verify both the rollback workflow and a fresh-browser smoke check. Record the incident and recovery commit in the issue. Review dependency updates and the Actions security/dependency alerts as part of each release; pin algorithm, policy and model changes to new versions and evaluate them before adoption.

Technical error reporting is optional. Its sanitizer removes request data and cookies and does not send video, landmarks, or scores. Keep it disabled unless its configuration and outgoing event fields have been reviewed for the release.
