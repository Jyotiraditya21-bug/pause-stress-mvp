import {test,expect} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

async function expectAccessible(page){
  const report=await new AxeBuilder({page}).analyze();
  const serious=report.violations.filter(v=>['serious','critical'].includes(v.impact));
  expect(serious,serious.map(v=>`${v.id}: ${v.help}`).join('\n')).toEqual([]);
}

test('idle scan renders and is accessible',async({page})=>{
  await page.goto('/');
  await expect(page.getByRole('heading',{name:'Your 10-second scan.'})).toBeVisible();
  await expect(page.getByRole('button',{name:'Start 10-second scan'})).toBeVisible();
  await expectAccessible(page);
});

test('permission denial gives a specific next step',async({page})=>{
  await page.addInitScript(()=>{
    Object.defineProperty(navigator,'mediaDevices',{value:{getUserMedia:async()=>{throw new DOMException('denied','NotAllowedError');}}});
  });
  await page.goto('/');
  await page.getByRole('button',{name:'Start 10-second scan'}).click();
  await expect(page.getByText(/Camera permission denied/)).toBeVisible();
});

test('cancel releases the video element',async({page})=>{
  await page.goto('/');
  await page.getByRole('button',{name:'Start 10-second scan'}).click();
  await expect(page.getByRole('button',{name:'Cancel and stop camera'})).toBeVisible({timeout:15000});
  await page.getByRole('button',{name:'Cancel and stop camera'}).click();
  await expect(page.getByRole('button',{name:'Start 10-second scan'})).toBeVisible();
  expect(await page.locator('video').evaluate(v=>v.srcObject===null)).toBeTruthy();
});

test('navigation tabs work and are accessible',async({page})=>{
  await page.goto('/');
  await page.getByRole('button',{name:'Overview'}).click();
  await expect(page.getByRole('heading',{name:/Pause\. Watch\./})).toBeVisible();
  await expectAccessible(page);

  await page.getByRole('button',{name:'About Model'}).click();
  await expect(page.getByRole('heading',{name:/Understanding your stress check-in/})).toBeVisible();
  await expectAccessible(page);

  await page.getByRole('button',{name:'History'}).click();
  await expect(page.getByRole('heading',{name:/Your previous graphs\./})).toBeVisible();
  await expectAccessible(page);

  await page.getByRole('button',{name:'Live',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Your 10-second scan.'})).toBeVisible();
});
