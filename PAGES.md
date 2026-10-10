# GitHub Pages deployment

The workflow .github/workflows/pages.yml builds frontend/ and deploys only frontend/dist. It selects browser storage and derives the repository base path automatically. Camera analysis, questionnaire, history, trends, deletion and local suggestions work without FastAPI. Gemini is disabled in this mode; keys must never go in GitHub Pages JavaScript. Sessions stay in the visitor browser profile and are not synchronized; clearing site data erases them.

1. Sign in locally with gh auth login.
2. Create or choose a repository; publish project source while excluding .env, SQLite data, virtual environments and node_modules (already ignored).
3. Push main and select Settings → Pages → Source: GitHub Actions.
4. Wait for Deploy Pages demo workflow and use its deployment URL.

Local smoke build: VITE_STORAGE_MODE=browser VITE_BASE_PATH=/repository-name/ npm --prefix frontend run build. Never publish the original backend as a shared unauthenticated service. Retaining Gemini requires a separately secured backend and a reviewed deployment configuration.

Status: deployed successfully at https://jyotiraditya21-bug.github.io/pause-stress-mvp/ . Repository: https://github.com/Jyotiraditya21-bug/pause-stress-mvp . Browser-storage smoke checks passed; Pages Actions run 38063419747 succeeded. Only frontend, workflow and gitignore were pushed. Backend and private local data remain local.
