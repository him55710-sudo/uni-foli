import { test, expect } from '@playwright/test';

test('has title', async ({ page }) => {
  await page.goto('/');
  // Expect a title "to contain" a substring.
  // Replace this with the actual title of your app
  await expect(page).toHaveTitle(/Polio/i);
});

test('get started link', async ({ page }) => {
  await page.goto('/');
  // This is a sample check, replace with your landing page element
  // await page.getByRole('button', { name: 'Get Started' }).click();
});
