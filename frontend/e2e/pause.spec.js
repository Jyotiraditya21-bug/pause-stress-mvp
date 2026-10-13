import {test,expect} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

async function onboard(page){
  await page.addInitScript(()=>localStorage.setItem('pause.onboarded.v1','1'));
}
async function expectAccessible(page){
  const report=await new AxeBuilder({page}).analyze();
  const serious=report.violations.filter(v=>['serious','critical'].includes(v.impact));
  expect(serious,serious.map(v=>`${v.id}: ${v.help}`).join('\n')).toEqual([]);
}

test('idle scan renders and is accessible',async({page})=>{
  await onboard(page);await page.goto('/');
  await expect(page.getByRole('heading',{name:'Your Calm index'})).toBeVisible();
  await expect(page.getByRole('button',{name:'Start 10-second scan'})).toBeVisible();
  await expectAccessible(page);
});

test('permission denial gives a specific next step',async({page})=>{
  await onboard(page);
  await page.addInitScript(()=>{Object.defineProperty(navigator,'mediaDevices',{value:{getUserMedia:async()=>{throw new DOMException('blocked','NotAllowedError')}}});});
  await page.goto('/');await page.getByRole('button',{name:'Start 10-second scan'}).click();
  await expect(page.getByText(/Camera access was blocked/)).toBeVisible();
});

test('cancel releases the video element',async({page})=>{
  await onboard(page);await page.goto('/');await page.getByRole('button',{name:'Start 10-second scan'}).click();
  await expect(page.getByRole('button',{name:'Cancel'})).toBeVisible({timeout:15000});await page.getByRole('button',{name:'Cancel'}).click();
  await expect(page.getByRole('button',{name:'Start 10-second scan'})).toBeVisible();
  expect(await page.locator('video').evaluate(v=>v.srcObject===null)).toBeTruthy();
});

test('fake-camera scan reaches a result or a clear failed state',async({page})=>{
  await onboard(page);await page.goto('/');await page.getByRole('button',{name:'Start 10-second scan'}).click();
  await expect(page.getByText(/We couldn't get a reading|Calm signs|In between|Tense signs/)).toBeVisible({timeout:35000});
});

test('result can be saved, viewed accessibly, and deleted from History',async({page})=>{
  await onboard(page);await page.goto('/?fixture=result');
  await expect(page.getByLabel(/Calm index 6.2 out of 10/)).toBeVisible();await expectAccessible(page);
  await page.getByRole('button',{name:'Save this result'}).click();await page.getByRole('button',{name:'History'}).click();
  await expect(page.getByText('6.2 /10')).toBeVisible();await expectAccessible(page);
  await page.getByRole('button',{name:/Delete scan/}).click();await expect(page.getByText(/No saved scans yet/)).toBeVisible();
});

test('personal baseline can be reset',async({page})=>{
  await page.addInitScript(()=>{localStorage.setItem('pause.onboarded.v1','1');localStorage.setItem('pause.baseline.v1',JSON.stringify({createdAt:new Date().toISOString(),algoVersion:'quick-2.0',features:Object.fromEntries(['brow_furrow','lip_press','lip_corner','jaw_clench'].map(k=>[k,{median:0,mad:.1}]))}));});
  await page.goto('/');await page.getByRole('button',{name:'Settings'}).click();await page.getByRole('button',{name:'Reset baseline'}).click();
  await expect(page.getByText('Your calm baseline was reset.')).toBeVisible();expect(await page.evaluate(()=>localStorage.getItem('pause.baseline.v1'))).toBeNull();
});

for(const viewport of [{width:360,height:640},{width:390,height:844},{width:768,height:1024},{width:1280,height:800}]){
  test(`scan has no horizontal overflow at ${viewport.width}x${viewport.height}`,async({page})=>{
    await onboard(page);await page.setViewportSize(viewport);await page.goto('/');
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  });
}
