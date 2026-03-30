import { test, expect, devices } from '@playwright/test';

// Use a separate project for mobile if needed, but here we can just set viewport
test.describe('Uni Folia QA Audit - Desktop', () => {
  test.beforeEach(async ({ page }) => {
    // Listen for console errors
    page.on('console', msg => {
      if (msg.type() === 'error') console.log(`[CONSOLE ERROR] ${msg.text()}`);
    });
  });

  test('1. Public Landing Page (/)', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle(/Polio|Uni Folia/i);
    
    // Check main CTA
    const mainCTA = page.locator('button:has-text("시작"), a:has-text("시작"), a:has-text("Get Started")');
    await expect(mainCTA.first()).toBeVisible();
    
    // Check for broken images
    const images = await page.locator('img').all();
    for (const img of images) {
      const src = await img.getAttribute('src');
      if (src) {
        const response = await page.request.get(new URL(src, page.url()).href);
        if (response.status() !== 200) console.log(`[BROKEN IMG] ${src}`);
      }
    }
    
    await page.screenshot({ path: 'screenshots/qa_landing.png' });
  });

  test('2. FAQ Page (/faq)', async ({ page }) => {
    await page.goto('/faq');
    // Check if FAQ items exist
    const faqItems = page.locator('.faq-item, [class*="faq"], details');
    if (await faqItems.count() > 0) {
      console.log(`[INFO] Found ${await faqItems.count()} FAQ items`);
      // Try to open first accordion if it's a details element or click-based
      await faqItems.first().click().catch(() => {});
    } else {
      console.log('[WARN] No FAQ items found in regular locators');
    }
    await page.screenshot({ path: 'screenshots/qa_faq.png' });
  });

  test('3. Contact Page (/contact)', async ({ page }) => {
    await page.goto('/contact');
    // Check for contact form
    const contactForm = page.locator('form');
    await expect(contactForm).toBeVisible().catch(() => console.log('[WARN] No contact form found'));
    
    // Test validation
    const submitBtn = page.locator('button[type="submit"]');
    if (await submitBtn.isVisible()) {
      await submitBtn.click();
      // Check for error messages
      const errors = page.locator('.error, [class*="error"], .text-red-500');
      if (await errors.count() > 0) {
         console.log('[INFO] Validation working: error messages appeared');
      }
    }
    await page.screenshot({ path: 'screenshots/qa_contact.png' });
  });

  test('4. Auth Page (/auth) and Protected Routes', async ({ page }) => {
    await page.goto('/auth');
    await expect(page.locator('form')).toBeVisible();
    
    // Try to access protected route /app without login
    await page.goto('/app');
    // Should redirect to /auth or /login
    await expect(page).not.toHaveURL(/\/app/);
    console.log(`[INFO] Protected route /app redirected correctly to: ${page.url()}`);
    
    await page.screenshot({ path: 'screenshots/qa_auth.png' });
  });

  test('5. Footer & Navigation', async ({ page }) => {
    await page.goto('/');
    const footer = page.locator('footer');
    await expect(footer).toBeVisible();
    
    // Check for common links
    const links = await footer.locator('a').all();
    console.log(`[INFO] Found ${links.length} links in footer`);
    for (const link of links) {
       const href = await link.getAttribute('href');
       if (!href || href === '#') console.log(`[WARN] Placeholder link in footer: ${await link.innerText()}`);
    }
  });
});

test.describe('Uni Folia QA Audit - Mobile', () => {
  test('Mobile Menu/Layout Check', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 }); // iPhone 13 size
    await page.goto('/');
    // Check if burger menu appears
    const burger = page.locator('button:has-text("menu"), .lucide-menu, [aria-label*="menu"]');
    if (await burger.isVisible()) {
      console.log('[INFO] Mobile menu (burger) is visible');
      await burger.click();
      // Check if menu opens
      const nav = page.locator('nav:visible, [role="navigation"]:visible');
      await expect(nav).toBeVisible();
    } else {
      console.log('[WARN] Mobile burger menu not found or not visible');
    }
    await page.screenshot({ path: 'screenshots/qa_mobile.png' });
  });
});
