import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
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
