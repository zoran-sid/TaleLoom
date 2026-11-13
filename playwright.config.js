import { defineConfig } from '@playwright/test';
import process from 'node:process';

// 用例按耗时分成三组，CI 上三台机器并行各跑一组（见 .github/workflows/web.yml）。
// 前两组各放一两个长的影像剧情文件；第三组收下其余全部文件，
// 新增的用例文件不用登记，自动归入第三组。本机直接 `npx playwright test` 仍然跑全部。
const CLIPS = /cinematic-(transitions|audio-sync|backdrops)\.spec\.js$/;
const FILM = /cinematic(-ledger)?\.spec\.js$/;
const CI = Boolean(process.env.CI);

export default defineConfig({
  testDir: './tests/browser',
  timeout: 120_000,
  expect: { timeout: 15_000 },
  workers: 1,
  // CI 上失败的用例重试一次：偶发失败不必整轮重跑，报告里会标成 flaky。
  retries: CI ? 1 : 0,
  reporter: CI ? [['list'], ['github']] : 'list',
  use: { baseURL: 'http://127.0.0.1:4173', browserName: 'chromium', trace: 'retain-on-failure' },
  projects: [
    { name: 'clips', testMatch: CLIPS },
    { name: 'film', testMatch: FILM },
    { name: 'rest', testIgnore: [CLIPS, FILM] },
  ],
  webServer: {
    command: 'npx vite preview --host 127.0.0.1 --port 4173',
    url: 'http://127.0.0.1:4173',
    reuseExistingServer: false,
    timeout: 60_000,
  },
});
