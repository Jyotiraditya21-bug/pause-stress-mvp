import { chromium } from '@playwright/test';
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const outDir = process.argv[2] || '/tmp/before';
fs.mkdirSync(outDir, { recursive: true });

const seededSessions = [
  {
    id: 'seed-1',
    created_at: new Date(Date.now() - 3600 * 1000 * 24).toISOString(),
    average: 6.2,
    status: 'ok',
    mode: 'generic',
    algoVersion: 'quick-2.0',
    source: 'camera',
    acquisitionVersion: 'robust-10s-2.0',
    windowScores: [6.0, 6.1, 6.2, 6.3, 6.2, 6.1, 6.2, 6.3, 6.2],
    range: [6.0, 6.3],
    coveragePercent: 96,
    qualityFlags: {}
  },
  {
    id: 'seed-2',
    created_at: new Date(Date.now() - 3600 * 1000 * 12).toISOString(),
    average: 4.8,
    status: 'ok',
    mode: 'generic',
    algoVersion: 'quick-2.0',
    source: 'camera',
    acquisitionVersion: 'robust-10s-2.0',
    windowScores: [4.6, 4.7, 4.8, 4.9, 4.8, 4.7, 4.8, 4.9, 4.8],
    range: [4.6, 4.9],
    coveragePercent: 92,
    qualityFlags: {}
  },
  {
    id: 'seed-3',
    created_at: new Date(Date.now() - 3600 * 1000 * 2).toISOString(),
    average: 7.1,
    status: 'ok',
    mode: 'generic',
    algoVersion: 'quick-2.0',
    source: 'camera',
    acquisitionVersion: 'robust-10s-2.0',
    windowScores: [6.9, 7.0, 7.1, 7.2, 7.1, 7.0, 7.1, 7.2, 7.1],
    range: [6.9, 7.2],
    coveragePercent: 100,
    qualityFlags: {}
  }
];

// Start vite dev server on 5199
const vite = spawn('npx', ['vite', '--port', '5199', '--host', '127.0.0.1'], {
  cwd: path.resolve('frontend'),
  stdio: 'pipe',
  shell: true
});

await new Promise((resolve) => {
  vite.stdout.on('data', (d) => {
    if (d.toString().includes('5199')) resolve();
  });
  setTimeout(resolve, 3000);
});

const browser = await chromium.launch();

const viewports = [
  { name: 'desktop', width: 1280, height: 800 },
  { name: 'mobile', width: 360, height: 640 }
];

try {
  for (const vp of viewports) {
    const context = await browser.newContext({ viewport: { width: vp.width, height: vp.height } });
    const page = await context.newPage();

    // 1. Scan screen (onboarded)
    await page.addInitScript((sessions) => {
      localStorage.setItem('pause.onboarded.v1', '1');
      localStorage.setItem('pause-camera-sessions-v2', JSON.stringify(sessions));
    }, seededSessions);

    await page.goto('http://127.0.0.1:5199/');
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(outDir, `${vp.name}-scan.png`), fullPage: true });

    // 2. Result screen (?fixture=result)
    await page.goto('http://127.0.0.1:5199/?fixture=result');
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(outDir, `${vp.name}-result.png`), fullPage: true });

    // 3. History screen
    await page.goto('http://127.0.0.1:5199/');
    await page.getByRole('button', { name: 'History' }).click();
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(outDir, `${vp.name}-history.png`), fullPage: true });

    // 4. Settings screen
    await page.getByRole('button', { name: 'Settings' }).click();
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(outDir, `${vp.name}-settings.png`), fullPage: true });

    // 5. About screen
    await page.getByRole('button', { name: 'About this index' }).click();
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(outDir, `${vp.name}-about.png`), fullPage: true });

    // 6. Privacy screen
    await page.getByRole('button', { name: 'Privacy' }).click();
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(outDir, `${vp.name}-privacy.png`), fullPage: true });

    await context.close();
  }
} finally {
  await browser.close();
  vite.kill('SIGTERM');
}

console.log(`Saved baseline screenshots to ${outDir}`);

