# Business Availability Test Cases

## 1. Scope
- Frontend pages: `Generator`, `OracleIngestion`, route switching in `MainLayout`.
- Backend APIs: `/api/extract-url`, `/api/generate`, `/api/export/pdf`, `/api/refinery/ingest`.
- Core business path: `抓取 -> 生成 -> 编辑 -> 导出` and `Oracle入库 -> 生成引用`.

## 2. Environment Baseline
- Backend: `python -m uvicorn main:app --reload --port 8000`
- Frontend: `npm run dev`
- Browser: latest Chrome
- Test account: not required

## 3. P0 Blocking Cases

| ID | Business Path | Preconditions | Steps | Expected Result |
|---|---|---|---|---|
| P0-01 | Route landing | Frontend running | Open `/` | Auto redirect to `/generator` |
| P0-02 | Top navigation | App loaded | Click top switch button | Toggle between `/generator` and `/oracle` |
| P0-03 | URL extraction success | Backend running | In step1 paste valid Play URL and click parse | `Extraction Complete` appears, title/USP are populated |
| P0-04 | Main generate flow (cloud) | Step1+2 completed | Click generate button in step3 | Enters step4 with full script schema and scores |
| P0-05 | Script editable | Step4 loaded | Edit one `visual` and one `audio_content` field | Value updates in place, unsaved indicator appears |
| P0-06 | Markdown export | Step4 loaded | Click `复制文案 (Markdown)` | Clipboard is updated and no UI crash |
| P0-07 | PDF export success | Step4 loaded | Click `导出给剪辑师 (PDF)` | PDF download starts and UI remains responsive |
| P0-08 | Cloud failure visibility | Force DeepSeek failure (unset `DEEPSEEK_API_KEY` or simulate upstream error) | Trigger generate in step3 | HTTP 502 with `CLOUD_UNAVAILABLE` / `CLOUD_SYNTHESIS_FAILED` surfaced in UI, no jump to step4 |
| P0-09 | Export gate blocks bad payload | Trigger error placeholder payload | Request `/api/export/pdf` with invalid/error data | HTTP 400 and clear error detail |
| P0-10 | Script history persistence | At least one successful generation | Refresh page and return to step4 | History list still exists with latest item |
| P0-11 | Script history load | History has multiple items | Click `加载` on one record | Form + result restored for selected record |
| P0-12 | Script history delete/clear | History has records | Click `删除`, then `清空记录` | Record removed, then list empty |

## 4. P1 High-Value Cases

| ID | Focus | Steps | Expected Result |
|---|---|---|---|
| P1-01 | Invalid URL branch | Use malformed Play URL | API returns `success=false`, UI shows parse failure |
| P1-02 | Extraction determinism | Run same URL extraction twice | USP structure and key hooks remain stable |
| P1-03 | Region semantics | Set region `Middle East` and generate | Cultural notes mention compliance/RTL; UI inputs use RTL where applicable |
| P1-04 | Oracle linkage | Ingest one report in `/oracle`, then generate in `/generator` | `citations` field exists and renders in trend panel |
| P1-05 | Export 500 branch | Mock PDF exception | UI shows export failure without freezing |

## 5. P2 Robustness Cases

| ID | Focus | Steps | Expected Result |
|---|---|---|---|
| P2-01 | Long USP boundary | Paste very long USP text | Generation still returns schema-valid result |
| P2-02 | Multilingual chars | Include Arabic/Japanese in USP | No encoding crash in generation/export |
| P2-03 | Repeated generations | Generate 25+ times | History capped at latest 20 records |
| P2-04 | Responsive behavior | Test narrow viewport/mobile emulation | Critical actions remain reachable and visible |

## 6. API Assertions (Contract-level)
- `/api/extract-url`:
  - success path: `success=true`, `title` non-empty, `extracted_usp` non-empty.
  - failure path: `success=false`, `error` non-empty.
- `/api/generate`:
  - success path must include schema keys:
    - score trio + reasoning trio
    - `bgm_direction`, `editing_rhythm`
    - `script` non-empty list with 6 required line fields
    - `psychology_insight`, `cultural_notes`, `competitor_trend`, `citations`
  - local failure path must return `502` + `detail.error_code`.
- `/api/export/pdf`:
  - success path: `success=true`, `pdf_base64` non-empty.
  - invalid/error placeholder path: HTTP `400`.
- `/api/refinery/ingest`:
  - returns `success`, `extracted_count`, `error` fields consistently.

## 7. Entry / Exit Criteria
- Entry:
  - Backend and frontend boot successful.
  - Required env vars available for target mode (cloud/local as needed).
- Exit:
  - All P0 pass.
  - No unresolved Critical/High defects.
  - P1 pass rate >= 90%.
