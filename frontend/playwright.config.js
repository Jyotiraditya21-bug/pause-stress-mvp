import {defineConfig,devices} from '@playwright/test';

export default defineConfig({
  testDir:'./e2e',timeout:45_000,fullyParallel:false,retries:0,
  use:{baseURL:'http://127.0.0.1:4173',trace:'retain-on-failure'},
  projects:[{name:'chromium',use:{...devices['Desktop Chrome'],launchOptions:{args:['--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream']}}}],
  webServer:{command:'npm run dev -- --host 127.0.0.1 --port 4173',url:'http://127.0.0.1:4173',reuseExistingServer:true,timeout:120_000}
});
