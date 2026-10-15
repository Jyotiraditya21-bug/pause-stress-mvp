# Contributing to Pause

Use Node 22 for `frontend/` and Python 3.11/3.12 for `stress_math/`. Follow the current README and applicable `AGENTS.md` instructions.

## Workflow

1. Create a focused branch and describe the user-visible problem.
2. Keep browser scoring, historical backend behavior, and offline research distinct.
3. Preserve camera consent, cleanup, local processing, and explicit result-saving behavior.
4. Run `npm test` and `npm run build` for frontend changes. Run relevant Playwright checks for UI or lifecycle changes and relevant Python tests for research changes.
5. Record actual verification and limitations. Do not invent dataset metrics, replace unavailable values with guesses, or tune fixed evaluation rules on test outcomes.
6. Open a pull request with the final behavior, checks run, and any remaining evidence gaps.

## Claims and data

Use “Calm index” or “experimental facial index” for the displayed result. Do not describe it as a validated stress measurement. Keep fixed formula changes separate from acquisition/UI work and maintain JavaScript/Python parity when applicable.

Do not commit recordings, face landmarks, personal results, datasets, credentials, caches, SQLite files, or dependency/build directories. Use synthetic fixtures for tests. Retain third-party notices and review model licensing before integration.
