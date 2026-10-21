const {chromium,expect}=require('@playwright/test');
const AxeBuilder=require('@axe-core/playwright').default;
const fs=require('node:fs');
const url=process.env.PAUSE_SMOKE_URL||'https://jyotiraditya21-bug.github.io/pause-stress-mvp/';
const expected=process.env.PAUSE_SMOKE_COMMIT;
(async()=>{
 fs.mkdirSync('test-results',{recursive:true});
 const browser=await chromium.launch({args:['--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream']});
 const report={url,date:new Date().toISOString(),syntheticCamera:true,checks:[]};
 const errors=[],external=[],httpErrors=[];
 try{
 const context=await browser.newContext({serviceWorkers:'block'});
 const page=await context.newPage();
 page.on('pageerror',e=>errors.push(e.message));
 page.on('request',r=>{if(/^https?:/.test(r.url())&&new URL(r.url()).origin!==new URL(url).origin)external.push(r.url());});
 page.on('response',r=>{if(r.status()>=400)httpErrors.push({url:r.url(),status:r.status()});});
 // Allow Pages/CDN publication to settle; accept only the intended commit.
 if(expected){
   await expect.poll(async()=>{const response=await context.request.get(url+'release.json?revision='+encodeURIComponent(expected));if(!response.ok())return null;report.release=await response.json();return report.release.commit;},{timeout:90000,intervals:[2000,5000]}).toBe(expected);
 }else{
   const response=await context.request.get(url+'release.json');expect(response.ok()).toBeTruthy();report.release=await response.json();
 }
 await page.goto(url,{waitUntil:'domcontentloaded'});
 await expect(page.getByRole('heading',{name:'A quiet moment to check in'})).toBeVisible();
 await page.getByRole('button',{name:'Continue to scan'}).click();
 report.checks.push('onboarding');
 await page.getByRole('button',{name:'Settings',exact:true}).click();
 const neuralToggle=page.getByRole('switch',{name:'Experimental neural model'});
 await expect(neuralToggle).toBeChecked();await neuralToggle.click();await expect(neuralToggle).not.toBeChecked();
 await page.reload();await page.getByRole('button',{name:'Settings',exact:true}).click();
 await expect(neuralToggle).not.toBeChecked();await neuralToggle.click();await expect(neuralToggle).toBeChecked();
 await page.getByRole('button',{name:'Scan',exact:true}).click();
 report.checks.push('neural enabled by default; saved off preference survives reload; can re-enable');
 const axe=await new AxeBuilder({page}).analyze();expect(axe.violations.filter(v=>['serious','critical'].includes(v.impact))).toEqual([]);
 report.checks.push('scan accessibility');
 await page.evaluate(()=>{
 window.previewTiming={};window.smokeStreams=[];
 const original=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
 navigator.mediaDevices.getUserMedia=async options=>{window.previewTiming.request=performance.now();const s=await original(options);window.previewTiming.granted=performance.now();window.smokeStreams.push(s);return s;};
 document.querySelector('video').addEventListener('playing',()=>{window.previewTiming.playing=performance.now();},{once:true});
 });
 let unblock;const gate=new Promise(r=>unblock=r);
 await page.route('**/mediapipe/face_landmarker.task',async route=>{await gate;await route.continue();});
 try{
 await page.getByRole('button',{name:'Start 10-second scan'}).click();
 await expect(page.locator('.scan-camera video')).toHaveClass(/is-ready/,{timeout:10000});
 await expect.poll(()=>page.evaluate(()=>Boolean(window.previewTiming.playing))).toBeTruthy();
 report.preview=await page.evaluate(()=>({requestToFrameMs:Math.round(window.previewTiming.playing-window.previewTiming.request),grantToFrameMs:Math.round(window.previewTiming.playing-window.previewTiming.granted)}));
 await page.getByRole('button',{name:'Cancel',exact:true}).click();
 expect(await page.evaluate(()=>window.smokeStreams.every(s=>s.getTracks().every(t=>t.readyState==='ended')))).toBeTruthy();
 }finally{unblock();}
 await page.unrouteAll({behavior:'wait'});
 report.checks.push('preview before model download completes; cancel stops tracks');
 await page.getByRole('button',{name:'Start 10-second scan'}).click();
 await expect(page.getByText(/We couldn't get a reading/)).toBeVisible({timeout:45000});
 expect(await page.evaluate(()=>window.smokeStreams.every(s=>s.getTracks().every(t=>t.readyState==='ended')))).toBeTruthy();
 report.checks.push('no-face failure without invented score; completion stops tracks');
 // Synthetic derived record only, in a disposable browser profile.
 await page.evaluate(()=>localStorage.setItem('pause-camera-sessions-v2',JSON.stringify([{id:'smoke-synthetic',created_at:'2026-01-01T00:00:00Z',average:6.2,status:'ok',mode:'generic',algoVersion:'quick-2.0',source:'quick-canonical-index-v3',acquisitionVersion:'capture-clock-1',range:[5.8,6.6],windowScores:[6,null,6.2,6.3],coveragePercent:80,qualityFlags:{}}])));
 await page.reload();await page.getByRole('button',{name:'History',exact:true}).click();
 await expect(page.getByText('6.2 /10')).toBeVisible();
 const dl=page.waitForEvent('download');await page.getByRole('button',{name:'Export saved results'}).click();expect((await dl).suggestedFilename()).toBe('pause-history.json');
 await page.getByRole('button',{name:/6.2 \/10/}).click();await expect(page.getByRole('heading',{name:'Calm index result'})).toBeVisible();
 const resultAxe=await new AxeBuilder({page}).analyze();expect(resultAxe.violations.filter(v=>['serious','critical'].includes(v.impact))).toEqual([]);
 await page.getByRole('button',{name:'History',exact:true}).click();await page.getByRole('button',{name:/Delete scan/}).click();await expect(page.getByText(/No saved scans yet/)).toBeVisible();
 report.checks.push('synthetic history/result/export/delete; result accessibility');
 await page.getByRole('button',{name:'Scan',exact:true}).click();await page.setViewportSize({width:360,height:640});await page.emulateMedia({reducedMotion:'reduce'});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
 await page.screenshot({path:'test-results/live-smoke-mobile.png'});
 report.checks.push('360px mobile layout; reduced motion');
 await page.evaluate(()=>{navigator.mediaDevices.getUserMedia=async()=>{throw new DOMException('blocked','NotAllowedError');};});
 await page.getByRole('button',{name:'Start 10-second scan'}).click();await expect(page.getByText(/Camera access was blocked/)).toBeVisible();
 report.checks.push('permission denial recovery');
 expect(errors).toEqual([]);expect(httpErrors).toEqual([]);expect(external).toEqual([]);
 report.checks.push('no page exceptions, failed HTTP assets, backend calls or external requests');
 await context.close();
 const offline=await browser.newContext();const op=await offline.newPage();
 await op.addInitScript(()=>localStorage.setItem('pause.onboarded.v1','1'));
 await op.goto(url);await op.evaluate(async()=>{await navigator.serviceWorker.ready;if(!navigator.serviceWorker.controller)await new Promise(resolve=>navigator.serviceWorker.addEventListener('controllerchange',resolve,{once:true}));});
 await offline.setOffline(true);await op.reload();await expect(op.getByRole('heading',{name:'Your Calm index'})).toBeVisible();await op.getByRole('button',{name:'Start 10-second scan'}).click();await expect(op.locator('.scan-circle:not(.is-loading)')).toBeVisible({timeout:25000});await op.getByRole('button',{name:'Cancel',exact:true}).click();await offline.close();
 report.checks.push('live installed PWA reload and analysis initialization offline');
 fs.writeFileSync('test-results/live-smoke-report.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
