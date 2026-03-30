import { test, expect } from '@playwright/test';

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

test.describe('Deep Competitor Analysis', () => {
  for (const site of sites) {
    test(`Deep Analysis: ${site.name}`, async ({ page }) => {
      console.log(`[START] Analyzing ${site.name} | ${site.url}`);
      
      try {
        await page.goto(site.url, { waitUntil: 'networkidle', timeout: 60000 });
        
        // 1. Initial State
        const title = await page.title();
        const h1 = await page.locator('h1').first().innerText().catch(() => 'No H1');
        
        // 2. Menu Analysis
        const menuItems = await page.locator('nav a, header a').allInnerTexts();
        const uniqueMenu = Array.from(new Set(menuItems)).filter(t => t.trim().length > 1).slice(0, 10);
        
        // 3. CTA Analysis
        const primaryCTA = await page.locator('button, a[class*="button"], a[class*="btn"], a:has-text("시작"), a:has-text("신청")').first().innerText().catch(() => 'No clear CTA');
        
        // 4. FAQ presence
        const hasFAQ = await page.locator('text=/FAQ|자주 묻는|질문/i').isVisible().catch(() => false);
        
        // 5. Contact info
        const footerText = await page.locator('footer').innerText().catch(() => 'No Footer');
        
        console.log(`[INFO] ${site.name} | H1: ${h1} | Menu: ${uniqueMenu.join(', ')} | CTA: ${primaryCTA} | FAQ: ${hasFAQ}`);
        
        // 6. Interaction: Try clicking CTA to see next step (if safe)
        // We will just peek at the href if it's a link
        const ctaHref = await page.locator('a:has-text("' + primaryCTA + '")').getAttribute('href').catch(() => 'No Link');
        console.log(`[FLOW] ${site.name} | CTA Link: ${ctaHref}`);

        await page.screenshot({ path: `screenshots/${site.name.toLowerCase()}_deep.png`, fullPage: true });

      } catch (err) {
        console.error(`[ERROR] ${site.name} | ${err.message}`);
      }
    });
  }
});
