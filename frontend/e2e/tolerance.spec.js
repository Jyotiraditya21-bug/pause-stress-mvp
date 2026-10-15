import {test,expect} from '@playwright/test';

test('tolerant no-face scan ends by the cap without a fabricated number or camera stream',async({page})=>{
  await page.addInitScript(()=>localStorage.setItem('pause.onboarded.v1','1'));
  await page.goto('/?tolerance=1');await page.getByRole('button',{name:'Start 10-second scan'}).click();
  await expect(page.getByText('Almost there, small movements are fine')).toBeVisible({timeout:25000});
  await expect(page.getByText("We couldn't get a reading")).toBeVisible({timeout:15000});
  await expect(page.locator('.pz-score')).toHaveCount(0);
  await expect(page.locator('video')).toHaveCount(0);
});
test('cancel during tolerant startup detaches camera immediately',async({page})=>{
  await page.addInitScript(()=>localStorage.setItem('pause.onboarded.v1','1'));
  await page.goto('/?tolerance=1');await page.getByRole('button',{name:'Start 10-second scan'}).click();
  await page.getByRole('button',{name:'Cancel'}).click();
  expect(await page.locator('video').evaluate(v=>v.srcObject===null)).toBe(true);
});
