import { test, expect } from '@playwright/test';

test.describe('Uni Folia QA Audit - Refined', () => {
  test.beforeEach(async ({ page }) => {
    page.on('console', msg => {
      if (msg.type() === 'error') console.log(`[CONSOLE ERROR] ${msg.text()}`);
    });
  });

  test('1. Public Landing Page (/)', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle(/Polio|Uni Folia/i);
    
    // Check main CTA - Based on Landing.tsx, it should be "무료로 시작하기" or "앱으로 이동"
    const mainCTA = page.locator('a:has-text("시작하기"), a:has-text("앱으로 이동")');
    await expect(mainCTA.first()).toBeVisible();
    
    // Check Navigation Links
    const navLinks = page.locator('nav a, header a');
    const faqLink = navLinks.filter({ hasText: /FAQ/i });
    const contactLink = navLinks.filter({ hasText: /문의/i });
    await expect(faqLink.first()).toBeVisible();
    await expect(contactLink.first()).toBeVisible();
    
    await page.screenshot({ path: 'screenshots/qa_landing_refined.png' });
  });

  test('2. FAQ Page (/faq)', async ({ page }) => {
    await page.goto('/faq');
    // The FAQ uses FaqAccordion component. Let's look for buttons inside it.
    const accordionButtons = page.locator('button[aria-expanded]');
    const count = await accordionButtons.count();
    if (count > 0) {
      console.log(`[INFO] Found ${count} FAQ accordion buttons`);
      await accordionButtons.first().click();
      // Check if it expanded (aria-expanded should change or content become visible)
      await expect(accordionButtons.first()).toHaveAttribute('aria-expanded', 'true');
    } else {
      console.log('[WARN] No FAQ accordion buttons found. Check if page loaded correctly.');
    }
    await page.screenshot({ path: 'screenshots/qa_faq_refined.png' });
  });

  test('3. Contact Page (/contact)', async ({ page }) => {
    await page.goto('/contact');
    
    // Check Tab Switching
    const partnershipTab = page.locator('button:has-text("협업/도입 문의")');
    await partnershipTab.click();
    await expect(page.locator('h2:has-text("학교·학원 단위")')).toBeVisible();
    console.log('[INFO] Tab switching to Partnership working');

    // Test validation on 1:1 Inquiry (default tab)
    const supportTab = page.locator('button:has-text("1:1 문의")');
    await supportTab.click();
    
    const submitBtn = page.locator('button:has-text("문의 보내기")');
    await submitBtn.click();
    
    // Check for error toast or field errors
    const errorMessages = page.locator('p.text-red-600');
    if (await errorMessages.count() > 0) {
       console.log(`[INFO] Validation working: ${await errorMessages.count()} field errors found`);
    } else {
       console.log('[WARN] No field validation errors found after empty submit');
    }
    
    // Check query string basic tab selection
    await page.goto('/contact?type=partnership');
    await expect(partnershipTab).toHaveAttribute('aria-selected', 'true');
    console.log('[INFO] Query string tab selection working');

    await page.screenshot({ path: 'screenshots/qa_contact_refined.png' });
  });

  test('4. Auth Page (/auth) and Protected Routes', async ({ page }) => {
    await page.goto('/auth');
    // Auth page check - Should have social login buttons
    const googleBtn = page.locator('button:has-text("Google로 계속하기")');
    await expect(googleBtn).toBeVisible();
    
    // Check navigation from Auth
    const homeLink = page.locator('a:has-text("홈으로")');
    await homeLink.click();
    await expect(page).toHaveURL('/');
    
    // Protected route check
    await page.goto('/app');
    await expect(page).toHaveURL(/\/auth/);
    console.log('[INFO] Protected route /app redirected to /auth correctly');
  });

  test('5. Footer & Legal', async ({ page }) => {
    await page.goto('/');
    const footer = page.locator('footer');
    await expect(footer).toBeVisible();
    
    const termsLink = footer.locator('a:has-text("이용약관")');
    const privacyLink = footer.locator('a:has-text("개인정보")');
    
    if (await termsLink.isVisible()) {
      await termsLink.click();
      await expect(page).toHaveURL(/\/terms/);
      console.log('[INFO] Terms of Service link working');
      await page.goBack();
    }
    
    if (await privacyLink.isVisible()) {
      await privacyLink.click();
      await expect(page).toHaveURL(/\/privacy/);
      console.log('[INFO] Privacy Policy link working');
    }
  });

  test('6. Mobile Layout Hand-check', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto('/');
    
    // Mobile navigation often uses a burger menu. In Landing.tsx, is there a header?
    // Wait, Landing.tsx doesn't have a header, it uses PublicLayout.
    // Let's check PublicLayout.
    const burgerMenu = page.locator('button[aria-label*="메뉴"], button .lucide-menu').first();
    if (await burgerMenu.isVisible()) {
       await burgerMenu.click();
       console.log('[INFO] Mobile burger menu opened');
    } else {
       console.log('[INFO] Mobile layout might be using a simplified fixed header or no burger');
    }
    await page.screenshot({ path: 'screenshots/qa_mobile_refined.png' });
  });
});
