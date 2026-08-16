import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  // All spec files share one server and one throwaway database (below), and
  // more than one file now edits `enzyme` — a shared reference-data row read
  // by every formulation. Two files' worth of edit/reset around it race under
  // multiple workers even though each file resets what it touched (M4's
  // trial.spec.ts's dose-preview test was seen to fail deterministically
  // against variants.spec.ts's unconditional per-test reset, running in a
  // different worker at the same moment). One worker serializes every test
  // against that shared state; the fix belongs at the run level rather than
  // in any individual spec file.
  workers: 1,
  use: { baseURL: 'http://127.0.0.1:8000', trace: 'retain-on-failure' },
  // Runs the real container path: uvicorn serving the built assets, one origin,
  // against a throwaway database so a local run never touches ./data.
  webServer: {
    command:
      'FOODBREW_DB_PATH=.e2e/foodbrew.db FOODBREW_WEB_DIST=dist ' +
      '../.venv/bin/uvicorn foodbrew.api.app:app --port 8000',
    url: 'http://127.0.0.1:8000/api/v1/health',
    reuseExistingServer: false,
    timeout: 60_000,
  },
})
