import fs from 'node:fs';
import path from 'node:path';
import { expect, test } from '@playwright/test';

const UPLOAD_PDF_PATH =
  process.env.E2E_PDF_PATH ??
  'C:\\Users\\\uC784\uD604\uC218\\Downloads\\\uC784\uD604\uC218 \uC0DD\uAE30\uBD80 \uD30C\uC77C.pdf';

const API_BASE = process.env.E2E_API_BASE ?? 'http://127.0.0.1:8000';
const ARTIFACT_DIR = path.resolve(process.cwd(), '..', 'artifacts', 'e2e');
const ARTIFACT_JSON_PATH = path.join(ARTIFACT_DIR, 'real_diagnosis_result.json');
const DOWNLOADED_PDF_PATH = path.join(ARTIFACT_DIR, 'diagnosis_export_from_e2e.pdf');

type GuidedPageButton = {
  testId: string;
  pageCount: number;
};

function parseGuidedPageButtons(rawTestIds: string[]): GuidedPageButton[] {
  return rawTestIds
    .map((value) => {
      const match = value.match(/^guided-pages-(\d+)$/);
      if (!match) return null;
      return {
        testId: value,
        pageCount: Number.parseInt(match[1], 10),
      };
    })
    .filter((item): item is GuidedPageButton => Boolean(item))
    .sort((a, b) => a.pageCount - b.pageCount);
}

async function ensureGuestLogin(page: import('@playwright/test').Page): Promise<void> {
  await page.goto('/auth', { waitUntil: 'domcontentloaded' });

  if (!page.url().includes('/auth')) return;

  const firstAgreementCheckbox = page.locator('input[type="checkbox"]').first();
  await expect(firstAgreementCheckbox).toBeVisible({ timeout: 30_000 });
  await firstAgreementCheckbox.check({ force: true });

  const guestButton = page.locator('button.bg-blue-50').first();
  await expect(guestButton).toBeEnabled({ timeout: 15_000 });
  await guestButton.click();

  await page.waitForURL((url) => !url.pathname.startsWith('/auth'), { timeout: 60_000 });
}

async function upsertOnboardingTargets(page: import('@playwright/test').Page): Promise<void> {
  // Local-dev backend supports bypass auth for this endpoint; we keep this deterministic for E2E.
  await page.request.post(`${API_BASE}/api/v1/users/onboarding/profile`, {
    data: {
      grade: '고3',
      track: '자연',
      career: '데이터 사이언스',
      marketing_agreed: false,
    },
  });
  await page.request.post(`${API_BASE}/api/v1/users/onboarding/goals`, {
    data: {
      target_university: '서울대학교',
      target_major: '컴퓨터공학과',
      admission_type: '학생부종합',
      interest_universities: ['연세대학교 (컴퓨터과학과)'],
    },
  });
}

test.describe('Real User Diagnosis E2E', () => {
  test.setTimeout(25 * 60_000);

  test('upload -> diagnose -> export download should succeed with >=5-page option', async ({ page }) => {
    if (!fs.existsSync(UPLOAD_PDF_PATH)) {
      throw new Error(`E2E input PDF file not found: ${UPLOAD_PDF_PATH}`);
    }

    const consoleErrors: string[] = [];
    page.on('console', (message) => {
      if (message.type() === 'error') {
        consoleErrors.push(message.text());
      }
    });

    await ensureGuestLogin(page);
    await upsertOnboardingTargets(page);

    await page.goto('/app/diagnosis', { waitUntil: 'domcontentloaded' });

    const uploadInput = page.getByTestId('diagnosis-upload-input');
    let uploadReady = false;
    try {
      await expect(uploadInput).toBeVisible({ timeout: 8_000 });
      uploadReady = true;
    } catch {
      uploadReady = false;
    }

    if (!uploadReady) {
      const continueButton = page.getByTestId('diagnosis-goals-continue');
      await expect(continueButton).toBeVisible({ timeout: 30_000 });
      await continueButton.click();
      await expect(uploadInput).toBeVisible({ timeout: 30_000 });
    }

    await uploadInput.setInputFiles(UPLOAD_PDF_PATH);

    const diagnosisPanel = page.getByTestId('diagnosis-result-panel');
    await expect(diagnosisPanel).toBeVisible({ timeout: 15 * 60_000 });

    const guidedPanel = page.getByTestId('guided-choice-panel');
    await expect(guidedPanel).toBeVisible({ timeout: 120_000 });

    const pageButtons = page.locator('[data-testid^="guided-pages-"]');
    await expect(pageButtons.first()).toBeVisible({ timeout: 30_000 });
    const pageButtonCount = await pageButtons.count();
    const rawTestIds: string[] = [];
    for (let index = 0; index < pageButtonCount; index += 1) {
      const testId = await pageButtons.nth(index).getAttribute('data-testid');
      if (testId) rawTestIds.push(testId);
    }

    const parsedPageOptions = parseGuidedPageButtons(rawTestIds);
    if (!parsedPageOptions.length) {
      throw new Error('No guided page-count options were detected.');
    }

    const selectedPageOption =
      parsedPageOptions.find((option) => option.pageCount >= 5) ??
      parsedPageOptions[parsedPageOptions.length - 1];
    await page.getByTestId(selectedPageOption.testId).click();
    expect(selectedPageOption.pageCount).toBeGreaterThanOrEqual(5);

    await page.getByTestId('guided-build-outline').click();
    await expect(page.getByTestId('guided-outline-preview')).toBeVisible({ timeout: 5 * 60_000 });

    const downloadResponsePromise = page.waitForResponse(
      (response) =>
        response.request().method() === 'GET' &&
        /\/api\/v1\/render-jobs\/[^/]+\/download$/i.test(response.url()),
      { timeout: 5 * 60_000 },
    );

    const [download, , downloadResponse] = await Promise.all([
      page.waitForEvent('download', { timeout: 5 * 60_000 }),
      page.getByTestId('guided-export').click(),
      downloadResponsePromise,
    ]);

    fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
    await download.saveAs(DOWNLOADED_PDF_PATH);
    const downloadedStats = fs.statSync(DOWNLOADED_PDF_PATH);
    expect(downloadedStats.size).toBeGreaterThan(0);
    expect(downloadResponse.status()).toBe(200);

    const responseContentType = String(downloadResponse.headers()['content-type'] || '').toLowerCase();
    expect(responseContentType).toContain('application/pdf');

    await expect(page.getByTestId('guided-download-latest')).toBeVisible({ timeout: 120_000 });

    await page.screenshot({
      path: path.resolve(ARTIFACT_DIR, 'real_diagnosis_result.png'),
      fullPage: true,
    });

    const downloadUrl = download.url();
    fs.writeFileSync(
      ARTIFACT_JSON_PATH,
      JSON.stringify(
        {
          timestamp: new Date().toISOString(),
          uploadPdfPath: UPLOAD_PDF_PATH.replace(/\\/g, '/'),
          finalUrl: page.url(),
          selectedGuidedPageCount: selectedPageOption.pageCount,
          downloadUrl,
          downloadHttpStatus: downloadResponse.status(),
          downloadContentType: responseContentType,
          downloadedPdfPath: DOWNLOADED_PDF_PATH.replace(/\\/g, '/'),
          downloadedPdfBytes: downloadedStats.size,
          consoleErrors,
        },
        null,
        2,
      ),
      'utf-8',
    );
  });
});
