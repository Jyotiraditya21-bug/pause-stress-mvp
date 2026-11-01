import {test,expect} from '@playwright/test';

test('MobileNetV3-Large browser output matches the frozen ONNX fixture',async({page})=>{
  await page.goto('/ml-verification.html');
  const result=page.locator('#result');
  await expect(result).toContainText('"passed": true',{timeout:45_000});
  await expect(result).toContainText('a3a32ee1343fed415d8f70d16ff8ffde6f7c131ab2ce2de99c540f31ecfa6fa8');
  await expect(result).toContainText('not camera, repeatability or stress validation');
});
