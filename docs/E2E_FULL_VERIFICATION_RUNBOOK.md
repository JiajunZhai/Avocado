# 全自动完整验证 Runbook（真实联调 + E2E）

> **前置说明**：在 Cursor 的 **Plan 模式**下无法修改源码与 `package.json`。要自动应用下列改动，请在对话中 **允许切换到 Agent 模式** 或自行按本文创建/修改文件。

## 一、当前已可执行的「无模拟」API 真实联调

在 **后端已监听 `127.0.0.1:8000`** 的前提下，于 `backend` 目录执行（真实 Google Play + 真实进程内生成 + 真实 PDF 字节）：

```bash
python -c "
import json, urllib.request, urllib.error, base64, sys
BASE='http://127.0.0.1:8000'
def req(method, path, data=None, timeout=300):
    url=BASE+path
    body=json.dumps(data).encode() if data else None
    h={'Content-Type':'application/json'} if body else {}
    r=urllib.request.Request(url,data=body,method=method,headers=h)
    try:
        with urllib.request.urlopen(r,timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())
s,ex=req('POST','/api/extract-url',{'url':'https://play.google.com/store/apps/details?id=com.zestplay.capybara.defense&hl=en','engine':'cloud'})
assert s==200 and ex.get('success')
s,gen=req('POST','/api/generate',{'title':ex['title'],'usp':ex['extracted_usp'][:4000],'platform':'TikTok (短平快冲击)','angle':'失败诱导型 (Fail-based)','region':'NA/EU','engine':'cloud'})
assert s==200 and gen.get('script')
s,pdf=req('POST','/api/export/pdf',{'data':gen})
assert s==200 and pdf.get('success')
assert base64.b64decode(pdf['pdf_base64']).startswith(b'%PDF')
print('REAL_API_CHAIN_OK')
"
```

**说明**：若 `.env` 中 DeepSeek Key 为占位符，生成链路仍会通过服务端逻辑走 **mock 剧本**（属产品回退，不是测试 mock）。

---

## 二、目标：Playwright 浏览器 E2E（真实后端 + 真实 Vite + 真实商店抓取）

### 1. 前端依赖

在 `frontend` 目录：

```bash
npm install -D @playwright/test
npx playwright install chromium
```

### 2. 在 `frontend/package.json` 的 `scripts` 中增加

```json
"test:e2e": "playwright test",
"verify:full": "npm run build && playwright test"
```

### 3. 新建 `frontend/playwright.config.ts`

```ts
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { defineConfig, devices } from '@playwright/test';

const rootDir = path.dirname(fileURLToPath(import.meta.url));
const backendDir = path.join(rootDir, '..', 'backend');

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: 'list',
  timeout: 240_000,
  use: {
    baseURL: 'http://127.0.0.1:5173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  webServer: [
    {
      command: 'python -m uvicorn main:app --host 127.0.0.1 --port 8000',
      cwd: backendDir,
      url: 'http://127.0.0.1:8000/',
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
    {
      command: 'npm run dev -- --host 127.0.0.1 --port 5173',
      cwd: rootDir,
      url: 'http://127.0.0.1:5173/',
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
  ],
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
});
```

### 4. 新建 `frontend/e2e/core-flow.spec.ts`

```ts
import { test, expect } from '@playwright/test';

const PLAY_URL =
  'https://play.google.com/store/apps/details?id=com.zestplay.capybara.defense&hl=en';

test.describe('Core business flow (real network)', () => {
  test('Generator: Play URL -> generate -> export PDF API success', async ({ page }) => {
    await page.goto('/dashboard');
    await page.getByRole('link', { name: 'Generator' }).click();
    await expect(page).toHaveURL(/\/generator$/);

    await page.getByTestId('wizard-store-url').fill(PLAY_URL);
    await page.getByTestId('wizard-sync-store').click();

    await expect(page.getByText('解析完成')).toBeVisible({ timeout: 120_000 });

    await page.getByTestId('wizard-confirm-extract').click();
    await expect(page.getByTestId('wizard-footer-next')).toBeEnabled({ timeout: 10_000 });

    await page.getByTestId('wizard-footer-next').click();
    await page.getByTestId('wizard-footer-next').click();

    const genRespPromise = page.waitForResponse(
      (r) => r.url().includes('/api/generate') && r.request().method() === 'POST',
      { timeout: 240_000 }
    );
    await page.getByTestId('wizard-generate').click();
    const genResp = await genRespPromise;
    expect(genResp.status()).toBe(200);

    await expect(page.getByRole('heading', { name: /最终生成剧本配置/ })).toBeVisible({
      timeout: 30_000,
    });

    const pdfRespPromise = page.waitForResponse(
      (r) => r.url().includes('/api/export/pdf') && r.request().method() === 'POST',
      { timeout: 120_000 }
    );
    await page.getByTestId('wizard-export-pdf').click();
    const pdfResp = await pdfRespPromise;
    expect(pdfResp.status()).toBe(200);
    const body = await pdfResp.json();
    expect(body.success).toBeTruthy();
    expect(body.pdf_base64?.length).toBeGreaterThan(100);
  });
});
```

### 5. 在 `frontend/src/pages/Generator.tsx` 增加 `data-testid`（稳定选择器）

在下列节点上增加对应属性（值与上面 spec 一致）：

| 元素 | `data-testid` |
|------|----------------|
| Google Play URL 输入框 | `wizard-store-url` |
| 「档案同步」按钮 | `wizard-sync-store` |
| 「确认调入主面板」按钮 | `wizard-confirm-extract` |
| 底部「确认配置」 | `wizard-footer-next` |
| 第三步中央生成按钮 | `wizard-generate` |
| 「导出给剪辑师 (PDF)」 | `wizard-export-pdf` |

建议同时为上述 `<button>` 补充 `type="button"`，避免表单误提交。

---

## 三、一键完整验证命令（本地）

```bash
cd backend && pytest tests -q && cd ../frontend && npm run build && npm run test:e2e
```

或使用本文第二节配置后的：

```bash
cd backend && pytest tests -q && cd ../frontend && npm run verify:full
```

---

## 四、若 E2E 失败时的常见修复方向

| 现象 | 处理 |
|------|------|
| `webServer` 端口占用 | 关闭已有 `8000`/`5173` 进程，或设 `CI=1` 强制不复用 |
| 抓取超时 | 提高 `解析完成` 的 `timeout`，或检查本机访问 Google |
| `/api/generate` 非 200（502） | 检查 `DEEPSEEK_API_KEY`、`DEEPSEEK_BASE_URL` 可达；响应 `detail.error_code`（`CLOUD_UNAVAILABLE` / `CLOUD_SYNTHESIS_FAILED` / `DRAFT_UNAVAILABLE`）定位原因 |
| 选择器找不到 | 确认已添加 `data-testid` |

---

## 五、你需要执行的操作

1. 在 Cursor 中 **允许 Agent 模式**，并说「按 Runbook 实施」——即可自动改文件、装依赖、跑通全流程。  
2. 或 **手动** 按第二节创建文件并修改 `Generator.tsx` / `package.json`，再执行第三节命令。
