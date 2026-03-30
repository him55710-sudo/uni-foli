import { test, expect, devices } from '@playwright/test';

const sites = [
  { name: 'VibeOn', url: 'https://www.vibeon.ai/' },
  { name: 'UniGo', url: 'https://unigo.kr/' },
  { name: 'HakZzongPro', url: 'https://hakzzongpro.com/' },
  { name: 'Hamaroom', url: 'https://hamaroom.com/landing' },
];

test.describe('Competitor UI Pattern Collection - Mobile', () => {
  test.use({ ...devices['iPhone 13'] });

  for (const site of sites) {
    test(`Mobile Capture: ${site.name}`, async ({ page }) => {
      console.log(`[START] Capturing Mobile ${site.name}`);
      try {
        await page.goto(site.url, { waitUntil: 'networkidle', timeout: 60000 });
        
        // Take a mobile full page screenshot
        await page.screenshot({ path: `screenshots/${site.name.toLowerCase()}_mobile.png`, fullPage: true });

        // Extract Hero Copy
        const h1 = await page.locator('h1').first().innerText().catch(() => 'No H1');
        const cta = await page.locator('button, a.btn, a[class*="button"]').first().innerText().catch(() => 'No CTA');
        console.log(`[PATTERN] ${site.name} | Mobile H1: ${h1} | Mobile CTA: ${cta}`);

      } catch (err) {
        console.error(`[ERROR] ${site.name} | ${err.message}`);
      }
    });
  }
});

// Desktop specific section analysis for Top 3
test.describe('Competitor Section Analysis - Desktop', () => {
  for (const site of sites.slice(0, 3)) {
    test(`Section Analysis: ${site.name}`, async ({ page }) => {
       await page.goto(site.url, { waitUntil: 'networkidle' });
       
       // Hero section screenshot
       const hero = page.locator('section').first();
       await hero.screenshot({ path: `screenshots/${site.name.toLowerCase()}_hero.png` });

       // Feature cards analysis
       const featureCards = page.locator('.card, [class*="feature"], [class*="item"]');
       const cardCount = await featureCards.count();
       console.log(`[INFO] ${site.name} has ~${cardCount} feature-like elements`);

       // Footer check
       const footer = page.locator('footer');
       if (await footer.isVisible()) {
          console.log(`[INFO] ${site.name} footer found`);
          await footer.screenshot({ path: `screenshots/${site.name.toLowerCase()}_footer.png` });
       }
    });
  }
});
