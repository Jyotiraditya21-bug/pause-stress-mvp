# Deploy Pause

The production scan is the static app in `frontend/`. It does not use or deploy the FastAPI backend.

## GitHub Pages

Push an reviewed commit to `main`, or run **Deploy Pages demo** from the Actions tab. The workflow uses Node 22, runs unit tests, builds with browser storage and the repository base path, then publishes `frontend/dist`.

```sh
cd frontend
npm ci
npm test
VITE_BASE=/pause-stress-mvp/ VITE_STORAGE_MODE=browser npm run build
```

## Cloudflare Pages

Create a Pages project from the repository with:

- Root directory: `frontend`
- Build command: `npm run build`
- Build output directory: `frontend/dist` when configured from repository root, or `dist` when Cloudflare treats `frontend` as the root
- Node version: `22`
- `VITE_BASE=/`
- `VITE_STORAGE_MODE=browser`
- Optional `VITE_SENTRY_DSN`
- Optional `VITE_ANALYTICS_DOMAIN`

Do not configure backend deployment. Camera scoring, saved history and personal baselines run in the browser.

To attach a domain, open the Pages project, choose **Custom domains**, select **Set up a custom domain**, enter the hostname and follow the DNS instructions. Keep HTTPS enabled because browsers require a secure context for camera access.

Cloudflare applies `frontend/public/_headers`. GitHub Pages ignores that file, so the equivalent Content Security Policy is also present in `frontend/index.html`.


## Rollback and cache recovery

Each Pages deployment is tied to a commit in the Actions run. To roll back, identify the last known-good commit in the Deploy Pages demo history, revert the faulty release commit on `main`, and push the revert. The normal Pages workflow rebuilds that revision; do not edit `dist/` or publish a local build by hand. Confirm the deployment run succeeded, then open the live site in a fresh private window and verify the versioned model/WASM requests, scan start, cancel, result, and History. The service worker uses automatic updates. If an installed PWA keeps a broken shell, close and reopen it while online so the worker can activate the rollback; clearing the site's storage is a last resort because it deletes local history.

Pages deployment now waits for Chromium/WebKit/offline checks and Lighthouse; Lighthouse category scores must meet 0.90 rather than reporting warnings. The separate `Checks` workflow also runs the frontend build, backend boundary tests, and Python/research parity. Confirm both workflows pass for the release commit before announcing it.
