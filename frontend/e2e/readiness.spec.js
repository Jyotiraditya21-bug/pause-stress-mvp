import {test,expect} from '@playwright/test';

test('ordinary navigation exits calibration without starting the camera',async({page})=>{
  await page.addInitScript(()=>localStorage.setItem('pause.onboarded.v1','1'));
  await page.goto('/');await page.getByRole('button',{name:'Settings',exact:true}).click();
  await page.getByRole('button',{name:'Calibrate when calm',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Calibrate when calm'})).toBeVisible();
  await page.getByRole('button',{name:'History',exact:true}).click();
  await page.getByRole('button',{name:'Scan',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Your Calm index'})).toBeVisible();
  expect(await page.locator('video').evaluate(v=>v.srcObject===null)).toBeTruthy();
});

test('damaged history is recoverable without losing valid records',async({page})=>{
  await page.addInitScript(()=>{
    localStorage.setItem('pause.onboarded.v1','1');
    localStorage.setItem('pause-camera-sessions-v2',JSON.stringify([null,{id:'valid',average:5,created_at:'2026-01-01T00:00:00Z',mode:'generic'}]));
  });
  await page.goto('/');await page.getByRole('button',{name:'History',exact:true}).click();
  await expect(page.getByText('5.0 /10')).toBeVisible();
  await page.getByRole('button',{name:'Recover saved history'}).click();
  await expect(page.getByText(/History recovered/)).toBeVisible();
  expect(await page.evaluate(()=>Object.keys(localStorage).some(k=>k.startsWith('pause-camera-sessions-v2.recovery.')))).toBeTruthy();
  await page.getByRole('button',{name:'Settings',exact:true}).click();
  await page.getByRole('button',{name:'Delete recovery backups'}).click();
  expect(await page.evaluate(()=>Object.keys(localStorage).some(k=>k.startsWith('pause-camera-sessions-v2.recovery.')))).toBeFalsy();
  await page.getByRole('button',{name:'History',exact:true}).click();
  await expect(page.getByText('5.0 /10')).toBeVisible();
  await page.getByRole('button',{name:/Delete scan/}).click();
  await expect(page.getByText('No saved scans yet.',{exact:false})).toBeVisible();
});

test('experimental mode and variable duration are visible before permission',async({page})=>{
  await page.addInitScript(()=>localStorage.setItem('pause.onboarded.v1','1'));
  await page.goto('/?tolerance=1');
  await expect(page.getByText(/Experimental movement-tolerant mode/)).toBeVisible();
  await expect(page.getByText(/10–20 seconds/)).toBeVisible();
});

for(const viewport of [{width:390,height:844},{width:360,height:640}]){
  test(`small-screen layout and reduced motion at ${viewport.width}x${viewport.height}`,async({page})=>{
    await page.addInitScript(()=>localStorage.setItem('pause.onboarded.v1','1'));
    await page.setViewportSize(viewport);await page.emulateMedia({reducedMotion:'reduce'});await page.goto('/');
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
    await expect(page.getByRole('button',{name:'Start 10-second scan'})).toBeInViewport();
    expect(await page.locator('.welcome-chip>span').evaluate(n=>getComputedStyle(n).animationName)).toBe('none');
  });
}

test('trends do not join different baselines and use elapsed date spacing',async({page})=>{
  await page.addInitScript(()=>{
    localStorage.setItem('pause.onboarded.v1','1');
    const row={average:5,mode:'baseline',source:'math',algoVersion:'quick-2.0',baselineId:'A'};
    localStorage.setItem('pause-camera-sessions-v2',JSON.stringify([
      {...row,id:'1',created_at:'2026-01-01T00:00:00Z'}, {...row,id:'2',created_at:'2026-01-02T00:00:00Z'}, {...row,id:'3',created_at:'2026-01-11T00:00:00Z'}, {...row,id:'4',baselineId:'B',created_at:'2026-01-12T00:00:00Z'}, {...row,id:'5',mode:'calibration',created_at:'2026-01-12T00:00:00Z'}
    ]));
  });
  await page.goto('/');await page.getByRole('button',{name:'History',exact:true}).click();
  await expect(page.getByRole('img',{name:'Saved Calm index trend by date'})).toHaveCount(2);
  const xs=await page.locator('.history-trend').first().locator('circle').evaluateAll(nodes=>nodes.map(n=>Number(n.getAttribute('cx'))));
  expect((xs[1]-xs[0])/(xs[2]-xs[0])).toBeCloseTo(.1);
});


test('neural model defaults on and its off/on preference survives reloads',async({page})=>{
  await page.addInitScript(()=>localStorage.setItem('pause.onboarded.v1','1'));
  await page.goto('/');
  await page.getByRole('button',{name:'Settings',exact:true}).click();
  const toggle=page.getByRole('switch',{name:'Experimental neural model'});
  await expect(toggle).toBeChecked();
  await toggle.click();await expect(toggle).not.toBeChecked();
  await page.reload();await page.getByRole('button',{name:'Settings',exact:true}).click();
  await expect(toggle).not.toBeChecked();
  await toggle.click();await expect(toggle).toBeChecked();
  await page.reload();await page.getByRole('button',{name:'Settings',exact:true}).click();
  await expect(toggle).toBeChecked();
});

test('previously saved neural off preference is respected',async({page})=>{
  await page.addInitScript(()=>{localStorage.setItem('pause.onboarded.v1','1');localStorage.setItem('pause.ml.enabled','0');});
  await page.goto('/');await page.getByRole('button',{name:'Settings',exact:true}).click();
  await expect(page.getByRole('switch',{name:'Experimental neural model'})).not.toBeChecked();
});
