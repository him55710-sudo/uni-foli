import { test, expect } from '@playwright/test';

// Define the target sites
const sites = [
  { name: 'VibeOn', url: 'https://www.vibeon.ai/' },
  { name: 'Skoologic', url: 'https://www.skoologicedu.com/collaboration' },
  { name: 'AIBU', url: 'https://www.aibu.co.kr/' },
  { name: 'HakZzongPro', url: 'https://hakzzongpro.com/' },
  { name: 'AIBUFF', url: 'https://www.aibuff.co.kr/home' },
  { name: 'UniGo', url: 'https://unigo.kr/' },
  { name: 'Padii', url: 'https://padii.net/' },
  { name: 'Hamaroom', url: 'https://hamaroom.com/landing' },
  { name: 'RiroSchool', url: 'https://riroschool.kr/research' }
];

test.describe('Competitor Analysis Research', () => {
  for (const site of sites) {
    test(`Analyze ${site.name}`, async ({ page }) => {
      console.log(`Navigating to ${site.name}: ${site.url}`);
      
      // Navigate with a reasonable timeout
      try {
        await page.goto(site.url, { waitUntil: 'networkidle', timeout: 60000 });
        
        // Basic metadata extraction
        const title = await page.title();
        const header = await page.locator('h1').first().innerText().catch(() => 'No H1');
        const cta = await page.locator('button, a.btn, a[class*="button"]').first().innerText().catch(() => 'No CTA');
        console.log(`[ANALYSIS] ${site.name} | Title: ${title} | Header: ${header} | CTA: ${cta}`);
        
        // Take a screenshot for visual analysis
        await page.screenshot({ path: `screenshots/${site.name.toLowerCase()}_landing.png`, fullPage: true });
        
        // Check for common CTA elements or messages
        const bodyText = await page.innerText('body');
        // console.log(`Sample text from ${site.name}: ${bodyText.substring(0, 200)}...`);
        
      } catch (error) {
        console.error(`Failed to analyze ${site.name}: ${error.message}`);
      }
    });
  }
});
