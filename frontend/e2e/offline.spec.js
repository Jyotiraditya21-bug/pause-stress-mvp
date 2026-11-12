import {test,expect} from '@playwright/test';

test.skip(!process.env.PW_PREVIEW,'Run with PW_PREVIEW=1 against the production PWA.');
test('installed PWA opens and initializes the scan offline after first load',async({page,context})=>{
  await page.addInitScript(()=>localStorage.setItem('pause.onboarded.v1','1'));
  await page.goto('/');
  await page.evaluate(async()=>{await navigator.serviceWorker.ready;if(!navigator.serviceWorker.controller)await new Promise(resolve=>navigator.serviceWorker.addEventListener('controllerchange',resolve,{once:true}));});
  await page.getByRole('button',{name:'Start 10-second scan'}).hover();
  await expect.poll(()=>page.evaluate(async()=>{
    const cache=await caches.open('pause-mediapipe-v1');const urls=(await cache.keys()).map(request=>request.url);
    return urls.some(url=>url.endsWith('/face_landmarker.task'))&&urls.some(url=>url.endsWith('.wasm'));
  }),{timeout:30000}).toBeTruthy();
  await context.setOffline(true);await page.reload();
  await expect(page.getByRole('heading',{name:'Your Calm index'})).toBeVisible();
  await page.getByRole('button',{name:'Start 10-second scan'}).click();
  await expect(page.locator('.scan-circle.is-loading')).toBeVisible();
  await expect(page.locator('.scan-circle:not(.is-loading)')).toBeVisible({timeout:20000});
  await expect(page.getByRole('button',{name:'Cancel'})).toBeVisible();
});
