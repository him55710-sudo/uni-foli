# Dev-Browser (Playwright) Usage Guide

This document outlines how to use Playwright (internally referred to as `dev-browser`) for competitor analysis automation and QA automation in the Uni Folia project.

## 1. Installation and Setup

Playwright is installed as a development dependency in the `frontend` directory.

### Quick Install
```powershell
cd frontend
npm install -D @playwright/test
npx playwright install chromium
```

### Checking the Environment
To verify that Playwright is correctly installed and accessible:
```powershell
npx playwright --version
npx playwright test --project=chromium
```

---

## 2. Configuration for Automated Runs

To ensure browser automation runs without permission prompts (e.g., camera, location, or download confirmations), the `playwright.config.ts` is configured with predefined permissions.

### Example Configuration (`frontend/playwright.config.ts`)
```typescript
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  use: {
    baseURL: 'http://localhost:3001',
    permissions: ['geolocation', 'notifications'], // Silences common prompts
    acceptDownloads: true,                        // Automatically handles downloads
    launchOptions: {
      args: ['--no-sandbox', '--disable-setuid-sandbox'], // Safe for many CI/env
    },
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
});
```

---

## 3. Key Automation Scenarios

### A. Competitor Analysis
Automate visiting competitor sites to capture screenshots, map their menus, and extract landing page messages.
- **Goal**: Research and trend tracking.
- **Workflow**: Create a script in `tests/research/` that visits a list of URLs and saves full-page screenshots to `screenshots/`.

### B. Public Landing / FAQ / Contact QA
Automated verification of the "first impression" and help channels.
- **Goal**: Ensure that public-facing pages load and core CTA buttons work.
- **Workflow**: Validate that links are not broken and specific text/images are present.

### C. Login / Onboarding Flow Verification
End-to-end testing of the most critical conversion paths.
- **Goal**: Confirm that new users can sign up and reach the dashboard.
- **Workflow**: Simulate user input in the signup form, handle Google Auth (mocked or with test account), and verify redirection to the onboarding modal.

---

## 4. Headless vs. Connect Mode

| Mode | Use Case | Description |
| :--- | :--- | :--- |
| **Headless** | CI/CD, Background tasks | Runs without a visible browser window. Faster and uses fewer resources. Default in automation. |
| **Headed** | Debugging, Local development | Opens a real browser window. Useful for watching exactly what the script is doing. |
| **Connect** | Remote browser, Persistence | Connects to an already running browser instance (local or remote/CDN). Useful for debugging long sessions or bypassing auth once. |

---

## 5. Execution Examples (CLI)

### 1. Run all health check tests (Headless)
```powershell
npx playwright test tests/health.spec.ts --project=chromium
```

### 2. Run with UI/Headed mode for local debugging
```powershell
npx playwright test tests/health.spec.ts --project=chromium --headed
```

### 3. Generate and view a visual test report
```powershell
npx playwright test --project=chromium; npx playwright show-report
```
