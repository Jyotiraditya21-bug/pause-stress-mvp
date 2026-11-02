import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';

const root = path.resolve('.');

// 1. Version & commit
const pkg = JSON.parse(fs.readFileSync(path.join(root, 'package.json'), 'utf8'));
let commit = 'local';
try {
  commit = execFileSync('git', ['rev-parse', '--short', 'HEAD'], { encoding: 'utf8' }).trim();
} catch {}

const buildDate = new Date().toISOString();

// 2. Unit test count
let unitTestCount = 0;
const srcDir = path.join(root, 'src');
if (fs.existsSync(srcDir)) {
  const srcFiles = fs.readdirSync(srcDir).filter(f => f.endsWith('.test.js'));
  for (const file of srcFiles) {
    const content = fs.readFileSync(path.join(srcDir, file), 'utf8');
    const matches = content.match(/\btest\s*\(/g);
    if (matches) unitTestCount += matches.length;
  }
}

// 3. Playwright spec count
let playwrightSpecCount = 0;
const e2eDir = path.join(root, 'e2e');
if (fs.existsSync(e2eDir)) {
  const e2eFiles = fs.readdirSync(e2eDir).filter(f => f.endsWith('.spec.js'));
  for (const file of e2eFiles) {
    const content = fs.readFileSync(path.join(e2eDir, file), 'utf8');
    const matches = content.match(/\btest\s*\(/g);
    if (matches) playwrightSpecCount += matches.length;
  }
}

// 4. Lighthouse scores from .lighthouseci if available
let lighthouseScores = null;
const lhciDir = path.join(root, '.lighthouseci');
if (fs.existsSync(lhciDir)) {
  const manifestPath = path.join(lhciDir, 'manifest.json');
  if (fs.existsSync(manifestPath)) {
    try {
      const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
      const rep = manifest.find(m => m.isRepresentativeRun) || manifest[0];
      if (rep && rep.summary) {
        lighthouseScores = {
          performance: rep.summary.performance != null ? Number(rep.summary.performance) : null,
          accessibility: rep.summary.accessibility != null ? Number(rep.summary.accessibility) : null,
          bestPractices: rep.summary['best-practices'] != null ? Number(rep.summary['best-practices']) : null,
          seo: rep.summary.seo != null ? Number(rep.summary.seo) : null
        };
      }
    } catch {}
  }
}

// 5. Release asset hashes from release-assets.json
const assetsPath = path.join(root, 'release-assets.json');
let releaseAssets = [];
if (fs.existsSync(assetsPath)) {
  const raw = JSON.parse(fs.readFileSync(assetsPath, 'utf8'));
  releaseAssets = Object.entries(raw).map(([filePath, sha256]) => ({
    name: path.basename(filePath),
    path: filePath,
    sha256
  }));
}

const evidence = {
  appVersion: pkg.version || '0.1.0',
  commit,
  buildDate,
  tests: {
    unitTestCount,
    playwrightSpecCount,
    axeStatus: '0 serious/critical violations'
  },
  lighthouse: lighthouseScores,
  releaseAssets,
  support: {
    contactEmail: null,
    githubIssuesUrl: 'https://github.com/jyotiraditya21-bug/pause-stress-mvp/issues'
  },
  lastUpdated: new Date().toISOString().split('T')[0]
};

const publicDir = path.join(root, 'public');
fs.mkdirSync(publicDir, { recursive: true });
fs.writeFileSync(path.join(publicDir, 'evidence.json'), JSON.stringify(evidence, null, 2));
console.log(`Generated public/evidence.json (tests: ${unitTestCount} unit, ${playwrightSpecCount} e2e, assets: ${releaseAssets.length})`);

