# 🧠 Project Memory Bank / Context Document

**Project Name**: AdCreative AI Script Generator
**Last Updated**: 2026-04-17
**Version Level**: Storage-Upgrade V2.7 (Phase 26 E-line: SQLite runtime store for projects/history/factors/compliance + hybrid BM25(FTS5)+Vector+RRF+MMR retrieval + optional Cross-Encoder rerank). Previous: V2.6 / Phase 25 D-line multi-provider entry. Supported providers: DeepSeek / SiliconFlow / Alibaba Cloud Bailian / OpenRouter / ZEN (deferred placeholder). Earlier: V2.5 / Phase 24 asset-layer (C-line) — Localization Matrix, Dashboard history search, Compliance admin, Delivery Pack. **Phase 26 is a storage-and-retrieval refactor; JSON seeds under `backend/data` remain git-tracked and are idempotently imported into SQLite on boot.**

This document serves as the global memory bank and active context tracker for the project. It outlines exactly where the project stands, structural choices, and development conventions to assist future AI/developer context loading.

> **Engine policy (current)**: The system runs DeepSeek-only. `engine=local`, `ollama_client.py`, `OLLAMA_*` / `LLM_RUNTIME_MODE` env vars, and the `LocalLLMResult` / `generate_with_local_llm` contract have all been removed. Historical phase entries below that reference Ollama are preserved for audit and marked `[SUPERSEDED 2026-04-17]` where applicable.

---

## 1. 🎯 Project Vision & Core Goal

Develop an AI-powered SaaS tool for Global User Acquisition (UA) teams. It dynamically generates psychologically optimized, region-specific advertising scripts for mobile games, dramatically cutting down creative ideation time from hours to minutes.

---

## 2. 🏛️ Architecture & Tech Stack

The project follows a decoupled **Monorepo** structure.

### Frontend (`frontend/`)

- **Framework**: `React 19` + `Vite v8` + `TypeScript`.
- **Styling Pipeline**: **Tailwind CSS v4** (No `tailwind.config.js`; everything relies on the `@tailwindcss/vite` plugin and is extended directly in `src/index.css` via `@theme` definitions).
- **Icons & Animations**: `lucide-react` for scalable iconography. `framer-motion` for stepper transitions and component micro-animations.
- **State Management**: React hooks; wizard state stays in `src/pages/Generator.tsx`. **Global shell activity** for sidebar: `src/context/ShellActivityContext.tsx` (`ShellActivityProvider` in `App.tsx`) exposes Generator/Oracle async busy labels consumed by `MainLayout.tsx`.
- **Key UI Patterns**:
  - **Glassmorphism**: Leveraged extensively via custom `.glass` utilities in `index.css`.
  - **Dark Mode**: Configured directly on the DOM root class (`html.dark`). **`ThemeAppearanceControl`** (`src/components/ThemeAppearanceControl.tsx`) persists preference in `localStorage` under `adcreative-theme` (`light` | `dark` | `system`); `index.html` boot script should stay aligned on that key.
  - **Semantic buttons**: Shared utilities in `index.css` — `btn-director-primary` / `secondary` / `ghost` / `link` / `success` / `primary-compact`; shell helpers `header-module-tab` (+ `--active`), `nav-director-link--active`. Success uses `@theme` tokens `--color-success` / `--color-on-success` (replaces ad-hoc `emerald-600` for done states).
  - **Brand color**: Primary palette is **blue-forward** (`#3b82f6` / `#2563eb` light; `#93c5fd` / `#3b82f6` dark) to reduce purple dominance; shell chrome (sidebar logo chip, active nav icons, some accents) leans **neutral + secondary (cyan)** where noted in code.

### Backend (`backend/`)

- **Framework**: `Python` + `FastAPI`.
- **Data Validation**: `Pydantic` models (`GenerateScriptRequest`, `GenerateScriptResponse`).
- **Server**: `uvicorn` (Dev command: `python -m uvicorn main:app --reload`).
- **State**: Handlers are mostly stateless; Oracle/RAG (`refinery.py`) persists a local TF-IDF-backed store. **Daily usage** for the quota UI persists in `backend/usage_counters.json` (gitignored): Oracle retrieval/ingest counts + LLM token tallies (`backend/usage_tracker.py`). **`GET /api/usage/summary`** returns budget, remaining, provider vs estimate token breakdown, and `billing_quality`. Cloud DeepSeek responses record **`response.usage.total_tokens`** when present (`backend/usage_tokens.py`); when `usage` is missing, env-based fallbacks apply.
- **SOP / Lab synthesis export**: On successful **`POST /api/generate`**, **`backend/md_export.py`** writes UTF-8 Markdown to **repository root** `@OUT/{project_id}/{script_id}.md` and the JSON response includes optional **`markdown_path`** (POSIX-style path from repo root, e.g. `@OUT/uuid/SOP-ABC123.md`). Write failures are logged only; they do not fail the HTTP response. **`.gitignore`** ignores `@OUT/**/*.md`; `@OUT/.gitkeep` keeps the folder in version control.
- **Cloud-only generate path**: **`/api/generate`** runs the DeepSeek draft + director pipeline; missing `DEEPSEEK_API_KEY` or an upstream exception surfaces as **HTTP 502** with `error_code` ∈ {`CLOUD_UNAVAILABLE`, `CLOUD_SYNTHESIS_FAILED`, `DRAFT_UNAVAILABLE`} + `error_message` + `elapsed_ms` (see `backend/tests/test_api_routes.py`). There is no mock/local fallback — failures are loud by design.

---

## 3. 🚀 Current Progress & Roadmap State

### ✅ Completed Milestones

- **[MVP v1.0] Scaffold Foundation**: Monorepo created, split-pane architecture implemented, UX stepper functional.
- **[MVP v1.0] Configured "Wait & See" Mock API**: `POST /api/generate` runs successfully over localhost with CORS configured.
- **[V1.1] Global Localization Engine API**: FastAPI backend natively understands region targets (`NA/EU`, `Japan`, `SEA`, `Middle East`) and intercepts the response context with targeted localization data and real-time competitor trend mocks.
- **[V1.1] RTL & Compliance Radar**: The frontend correctly renders RTL text flows when "Middle East" is queried. The Cultural warning components (`ShieldAlert`) properly populate dynamically.
- **[Phase 1] Prompter Engine Engineered**: Created `backend/prompts.py` which houses the 5 hardcore creative DNA logics (Fail-based, Evolution, Drama, ASMR, UGC) and dynamically injects regional constraints into a scalable system prompt. Verified via console test script.
- **[Phase 2] Store Scraper & Input Hub**: Integrated `google-play-scraper` into `backend/scraper.py`. Implemented `POST /api/extract-url` for instant Play Store data parsing (Title, Genre, Description, Installs, What's New). Store copy is distilled into a **Bilingual Director Archive** (see Phase 11); legacy “(Translated to English)” USP block format is retired.
- **[Phase 2] Frontend Automation**: Upgraded `Generator.tsx` with a dual-mode Input switch (`Auto Extract` vs `Manual`). The Auto mode securely fetches Play Store strings and features a high-fidelity "✨ Auto-Fill" button that elegantly patches information across into the Prompt State and throws a "Source: Google Play Scraped" UI verification badge.

- **[Phase 3] Prediction Logic & Dashboards**: Substantially upgraded the Prompt JSON constraints via `backend/prompts.py` to force LLM score justifications. Transformed the static UI in `Generator.tsx` into a granular Performance Metrics breakdown where Hook, Clarity, and Conversion bars render explicitly with underlying logical derivations, accompanied by a dynamic `Psychological Trigger` warning box.
- **[Phase 4] Delivery & LLM API Ignition**:
  - Front-end table changed to an interactive Script Editor (textareas replacing text).
  - Built an "Instant Markdown Export" leveraging `navigator.clipboard`.
  - Added Backend PDF routing (`exporter.py` utilizing `fpdf2`).
  - Added `.env` and `openai` SDK logic into `main.py` enabling genuine GPT-4o invocations when an API Key is present.
- **[Phase 5] Bilingual Director Mode**:
  - Pivoted from simple translation logic to a "Domestic Editor Instruction" model.
  - LLM Prompts & API Schemas now separate Audio/Text into `Local Content` and `Domestic Meaning` (Translation).
  - Front-end integrated a seamless `CopyButton` component (`navigator.clipboard.writeText`) dynamically appended to Local Content columns for zero-friction copying by video editors.
  - LLM Prompt engine (`prompts.py`) expanded with a `region_style_map` ensuring authentic Region-Specific execution rules (e.g., Danmaku floating UI for Japan; chaotic Meme cuts for NA/EU) are explicitly requested from the GPT model.
  - Injecting High-level directorial production parameters (`BGM Direction` and `Editing Rhythm`) into JSON.
  - Refactored `Generator.tsx` UI into a robust side-by-side editing grid for translators & video editors.
- **[Phase 6] Cloud Engine (DeepSeek V3/R1)** _[local/LAN hybrid path SUPERSEDED by Phase 26 — 2026-04-17]_:
  - Default Cloud reasoning engine explicitly swapped to `DeepSeek-Chat`, harnessing their high-logic models for robust psychological script parsing at a fraction of standard API costs.
  - Hard-capped Scraped Google Play description strings to `1500` characters before extraction to keep context budget predictable.
- **[Phase 7] Project Oracle (RAG Intelligence Refinery)**:
  - Removed massive `chromadb` C++ dependency due to Python 3.14 / Pydantic v1 failure.
  - Added pure `backend/refinery.py` housing a `Scikit-Learn TF-IDF` persistent NLP Matrix using localized JSON strings for `Creative Genes` extraction.
  - Implemented automatic HTML URL scraping if raw text is not present during intelligence ingestion.
  - Attached Recency metrics (`year_quarter`) strictly to RAG metadata to ensure time-relevant citations.
  - Enforced a Prompt Conflict Resolution parameter ordering the LLM to output A/B test splits if multiple RAG records collide.
  - Expanded frontend with a `OracleIngestion.tsx` URL panel and injected `📚 Siphon Pipeline Citations` onto the generated UI.
- **[Phase 8] Test Automation Pipeline (Pytest)**:
  - Transformed monolithic `test_*.py` debugging scrips into a formalized `tests/` namespace.
  - Deployed `pytest==8.1.1` and `httpx==0.27.0` for rapid automated assertion validation (`pytest tests/ -v`).
  - Implemented API Boundary protection (`test_api_routes.py`), Scraper Truncation safeguards (`test_scraper.py`), Translation Instruction assertions (`test_engine.py`), and raw PDF parsing validation (`test_exporter.py`).
- **[Phase 9] Engine Reliability Patch (2026-04-13)** _[local/Ollama specifics SUPERSEDED by Phase 26 — 2026-04-17]_:
  - Hardened `backend/main.py`:
    - Added strict schema validation on generation payloads.
    - Added structured HTTP 502 mapping for inference failures.
    - Added `/api/export/pdf` payload validation and explicit rejection of error-placeholder content.
  - Updated `frontend/src/pages/Generator.tsx`:
    - Removed client-side fake script fallback for generation failures.
    - Added user-facing error panel for generation failures.
    - Disabled PDF export when generation result is invalid/failed.
  - Expanded test coverage:
    - `backend/tests/test_api_routes.py` now covers success/failure/schema mismatch, extract-url branches, export success/error rejection.
    - Added `backend/tests/test_refinery.py` for API key missing and retrieval exception fallback.
- **[Phase 10] Inference Quality & History UX Patch (2026-04-13)**:
  - Upgraded `backend/scraper.py` extraction pipeline (superseded by Phase 11 JSON shape; rules remain as fallback):
    - Removed random hook generation to eliminate unstable USP outputs.
    - Deterministic description-driven rules for gameplay/hooks/audience.
  - Upgraded `frontend/src/pages/Generator.tsx`:
    - Added generated script history archive (localStorage persistence, latest 20 items).
    - Added load/delete/clear controls in preview step for rapid iteration and reuse.
    - Fixed Framer Motion SVG warning by setting explicit `motion.circle` `cx/cy` initial values.
  - Expanded extraction tests:
    - Added deterministic output assertions and local-success/local-fallback branches in `backend/tests/test_scraper.py`.
- **[Phase 11] E2E + Extract Contract + Windows Console Hardening (2026-04-13–14)**:
  - **Playwright (real network)**: `frontend/e2e/core-flow.spec.ts` drives Dashboard → Generator → Play URL sync → generate → export PDF; `frontend/playwright.config.ts` starts or reuses `uvicorn` (8000) + Vite (5173). Scripts: `npm run test:e2e`, `npm run verify:full`. Runbook: `docs/E2E_FULL_VERIFICATION_RUNBOOK.md`.
  - **Stable selectors**: `data-testid` on key wizard controls in `Generator.tsx` (`wizard-store-url`, `wizard-sync-store`, `wizard-confirm-extract`, `wizard-footer-next`, `wizard-generate`, `wizard-export-pdf`).
  - **Playwright tuning**: Global timeout relaxed for real scrape + LLM; `waitForResponse` matches URL/method then asserts status (avoids hanging on non-2xx). `reuseExistingServer` defaults to reuse unless `PLAYWRIGHT_FORCE_SPAWN=1` (avoids broken local runs when `CI` is accidentally set). Backend `webServer` env sets `PYTHONUTF8` / `PYTHONIOENCODING` for child `uvicorn`.
  - **`backend/main.py`**: `_print_console_safe` prevents `UnicodeEncodeError` when printing huge prompts on Windows GBK consoles (stops `/api/generate` from dying mid-request).
  - **`backend/scraper.py` — Bilingual Director Archive**:
    - Public API: **`extract_usp_via_llm`** (alias **`extract_usp_via_llm_mock`** kept for compatibility).
    - Target JSON inside `extracted_usp`: `core_gameplay` / `value_hooks[]` / `target_persona`, each bilingual `{ en, cn }` (`en` = prompt-grade English; `cn` = director-facing for domestic editors). LLM path consumes constant **`EXTRACT_USP_VIA_LLM_SYSTEM_PROMPT`**; a deterministic rule-based archive is used when the cloud call is unavailable or fails.
    - Serialized string = JSON block + optional `[Store scale signal]` / recent-update footer for downstream `usp` injection in `prompts.py`.
- **[Phase 12] ProjectArchiveCard & Generator URL 确认流 (2026-04-14)**:
  - **`frontend/src/components/ProjectArchiveCard.tsx`**: Light “专业制片档案” worksheet (`bg-slate-50`, hairline border, `rounded-md`): header `[档案 ID: …]` + optional **✓ DNA Parsed** badge; bilingual rows (EN Inter / CN PingFang 栈); **Value hooks** table (`Content` / `Meaning`); micro **Edit** pencil affordances (callbacks optional).
  - **`frontend/src/utils/directorArchive.ts`**: `parseDirectorArchiveExtractedUsp` splits on `\n\n[Store scale signal]` then validates JSON; `buildUspEnContext` builds **English-only** USP text for `POST /api/generate` (`usp`); `fallbackDirectorArchive` for non-JSON / legacy mock; `shortArchiveIdFromUrl` for card ID.
  - **`Generator.tsx` (wizard step 「1. 录入游戏档案」, URL / 灵感源)**:
    - After **档案同步** succeeds (`extractionStatus === 'confirm'`): **hide** the Play URL input block (shown only in `idle`); render **`ProjectArchiveCard`** from parsed archive (`usedStructuredJson` toggles DNA badge).
    - **确认配置** (`wizard-confirm-extract`): if structured JSON was parsed → `setUsp(buildUspEnContext(…))` so generation uses **EN context**; else keep raw `extracted_usp` string (e.g. offline mock).
    - **重新扫描**: reset to `idle`, clear `tempData`; **驳回** also clears `tempData`.
- **[Phase 15] `@OUT` Markdown export + Lab response path (2026-04-15)**:
  - **`backend/md_export.py`**: `synthesis_to_markdown` + `export_markdown_after_generate`; output directory **`repo_root() / "@OUT" / {project_id}`** (repo root = parent of `backend/`).
  - **`backend/main.py`**: `GenerateScriptResponse.markdown_path`; `finalize_response()` after each successful generate. _(A parallel `generate_script_local` + `engine=local` branch shipped here was SUPERSEDED by Phase 26 — 2026-04-17.)_
  - **`frontend/src/pages/Lab.tsx`** + **i18n** (`lab.markdown_saved`): surfaces `markdown_path` when present after synthesis.
  - **Tests**: `tests/test_md_export.py`; `test_api_routes.py` / `test_business_flow_e2e.py` use valid `project_id` + insight ids (`data/workspaces`, `data/insights`).
- **[Phase 16] Quota popup analytics + real usage hardening (2026-04-15)**:
  - **`backend/usage_tracker.py`**: usage payload expanded with script-level metrics: `script_generations_today`, `last_script_tokens`, `avg_tokens_per_script_today`, provider/estimate sample counters, and per-script provider/estimate averages.
  - **`backend/main.py`**: cloud extract usage now reads tokens via **`total_tokens_from_completion(response)`** (统一口径，避免 provider SDK usage 结构差异).
  - **`frontend/src/layout/MainLayout.tsx`**: quota popover now displays **today total used**, **single script cost**, **avg cost/script**, and **sample count (provider/estimate split)** in addition to remaining/budget and Oracle counters.
  - **i18n**: new keys in `frontend/src/i18n/locales/zh.json` + `en.json` (`quota.tokens_used`, `last_script`, `avg_script`, `sample_count`).
  - **Tests**: `backend/tests/test_usage_api.py` extended for new fields + derived script stats; `backend/tests/test_api_routes.py` extract success test monkeypatch adjusted to `scraper.extract_usp_via_llm_with_usage`.
- **[Phase 17] Knowledge path unification + export delivery hardening (2026-04-15)**:
  - **Unified knowledge layout**:
    - Added `backend/knowledge_paths.py` as the single source of truth for KB paths.
    - New canonical paths:
      - factors: `backend/data/knowledge/factors`
      - vector store: `backend/data/knowledge/vector_store/local_storage.json`
    - Automatic compatibility migration on startup/use:
      - `backend/data/insights` -> `backend/data/knowledge/factors`
      - `backend/chroma_db/local_storage.json` -> `backend/data/knowledge/vector_store/local_storage.json`
  - **Bilingual output mode**:
    - `GenerateScriptRequest` now supports `output_mode` (`cn` / `en`).
    - `Lab.tsx` adds output mode selector and persists it to `localStorage` (`sop_output_mode`).
    - `md_export.py` renders CN/EN document templates based on mode.
  - **Localization behavior for exported Markdown**:
    - In CN mode, document explanatory fields are translated to Chinese.
    - In EN mode, document explanatory fields are translated to English.
    - `audio_content` and `text_content` are preserved as original source text in both modes.
  - **Delivery naming convention**:
    - Exported file names now follow:
      - `<LANG>_<Game>_<Region>_<Platform>_<Strategy>_<SOPID>.md`
    - Name resolution priority:
      - `*_short` -> `*_name` -> raw id
    - Added compacting/sanitization for readability and Windows-safe filenames.
  - **`short_name` rollout**:
    - Added `short_name` fields across insight factor JSON under `backend/data/insights/{regions,platforms,angles}` for concise naming.
    - Example usage in filenames: `US`, `TikTok`, `Rescue` (when configured).
- **[Phase 18] CN storyboard execution-only rows (2026-04-15)**:
  - **`backend/md_export.py`** CN mode was simplified to avoid bilingual duplication in per-shot sections.
  - CN shot rows now output execution-focused fields only:
    - `画面` (prefer `visual_meaning`, fallback `visual`)
    - `配音`
    - `贴纸字` (only when non-empty)
    - `导演提示（中文）`
    - `音效/转场提示（中文）`
  - Removed in CN mode: `画面释义（中文）` / `配音释义` / `贴纸释义`.
  - EN mode remains unchanged (keeps note-style bridge fields for cross-language review workflows).
  - **Tests**: `backend/tests/test_md_export.py` updated to assert removed CN rows are absent.
- **[Phase 19] 1+1+3 生成链路整改：草案/导演分阶段 + RAG 结构化证据 + 自动审校 (2026-04-16)**:
  - **语义**：`1` = 项目/游戏 DNA（workspace）；`1` = 向量知识库检索（Oracle）；`3` = 地区 + 平台 + 心理策略因子 JSON。
  - **`POST /api/generate` 新增 `mode`**：`draft` | `director` | `auto`（默认 `auto`：先草案再导演全稿）。
  - **Prompt 拆分**（[backend/prompts.py](backend/prompts.py)）：
    - `render_draft_prompt`：轻量草案 JSON（多条 hook/叙事候选 + `pick_recommendation`）。
    - `render_director_prompt`：最终分镜导演稿；可注入入选草案 JSON。`render_system_prompt` 保留为导演稿别名以兼容旧调用。
  - **RAG 结构化证据**（[backend/refinery.py](backend/refinery.py)）：
    - `collection.query` 返回 `scores`；新增 `retrieve_context_with_evidence()`，每条证据含 `rule`、`source`、`year_quarter`、`match_score`、`reason_tag`。
    - `retrieve_context()` 仍为 `(context, citations)` 兼容旧代码。
  - **生成响应扩展**（[backend/main.py](backend/main.py)）：
    - 可选字段：`drafts`、`review`（规则审校：issues/warnings/score_breakdown）、`rag_evidence`、`generation_metrics`（含 `mode`、`elapsed_ms`、`rag_rules_used`）。
    - 本地路径：`generate_script_local` 使用 `retrieve_context_with_evidence` 并合并 `rag_evidence`。_[SUPERSEDED 2026-04-17 — `generate_script_local` removed in Phase 26; 云端路径仍使用 `retrieve_context_with_evidence`。]_
  - **Lab UI**（[frontend/src/pages/Lab.tsx](frontend/src/pages/Lab.tsx)）：`GEN MODE` 下拉（auto/draft/director），`localStorage` 键 `sop_synthesis_mode`；结果区展示 `review` 与草案摘要。
  - **测试**：`test_api_routes.py` 对 `retrieve_context` 的 monkeypatch 改为 `retrieve_context_with_evidence`；`test_refinery.py` 覆盖证据结构。
  - **验证**：合并后应跑 `pytest tests/test_api_routes.py tests/test_refinery.py tests/test_md_export.py` 确认 `mode` / `review` / RAG 不破坏既有 JSON 契约。
- **[Phase 20] 极速文案模式（Quick Copy Mode）+ 文案超市 + Refresh Copy + CSV 导出 (2026-04-16)**:
  - **痛点**：日更投放文案需要高频迭代；不应为几条标题强制生成整套分镜（Token 成本 + UI 负担）。
  - **双轨生成（前端输出类型开关）**（[frontend/src/pages/Lab.tsx](frontend/src/pages/Lab.tsx)）：
    - `🎬 Full SOP`：仍走 `POST /api/generate`（支持 `mode=draft|director|auto`）。
    - `✍️ Quick Copy`：走 `POST /api/quick-copy`（只产出文案矩阵，不生成分镜）。
    - 本地持久化：`sop_output_type`、`sop_copy_quantity`、`sop_copy_tones`、`sop_copy_locales`。
  - **Quick Copy 后端 API**（[backend/main.py](backend/main.py)）：
    - `POST /api/quick-copy`：入参支持 `quantity`（每语言 headlines 数量）、`tones`、`locales`；返回 `ad_copy_matrix` + `markdown_path`（Copywriting Booklet）。
    - `POST /api/quick-copy/refresh`：输入 `project_id + base_script_id`，从 workspace 的 `history_log` 读取脚本上下文，仅刷新文案（保持分镜不变）。
  - **专用提示词（文案工厂）**（[backend/prompts.py](backend/prompts.py)）：
    - `render_copy_prompt`：强制输出 `ad_copy_matrix`（按 locale variants），强调 **点击欲望**、**多变量组合（卖点词+CTA+情绪钩子）**、多心理动机覆盖、以及非英语的 **Transcreation**（非机翻）。
  - **“文案超市”结果形态 + 导出**（[frontend/src/pages/Lab.tsx](frontend/src/pages/Lab.tsx)）：
    - Quick Copy 结果区全屏矩阵化呈现（按 locale 卡片）。
    - 支持 **CSV 导出**（用于 TikTok Ads Manager 批量上传）。
    - 支持 **就地编辑** headlines（contentEditable onBlur 写回到 `synthesisResult.ad_copy_matrix`）。
  - **MD 渲染适配**（[backend/md_export.py](backend/md_export.py)）：
    - 当 payload 仅含 `ad_copy_matrix`（无 `script`）时，导出为 “Copywriting Booklet” Markdown（标题集/描述集/标签集）。
  - **测试**：
    - 新增 `backend/tests/test_quick_copy.py` 覆盖 `/api/quick-copy` 结构与数量约束（cloud no-key fallback）；`refresh` 缺历史时返回 400/404 均可接受（依 fixture workspace）。
- **[Phase 26·E] 存储底座升级：SQLite + 混合检索（2026-04-17）**:
  - **目标**：把 `backend/data` 的 projects / history_log / factors / compliance / knowledge 迁进 SQLite 做运行期读写层，并把 RAG 升级为 **BM25(FTS5) + Vector + RRF 融合 + Region Boost + MMR 多样性 + 可选 Cross-Encoder 重排**，以 factor 展开的 supplement 强化分镜脚本与文案素材的内容质量。`pytest -q` **121/121 绿**（109 baseline + 12 新增），`npm run build` OK。
  - **源头约定（seed_only）**：
    - `backend/data/knowledge/factors/**`、`backend/data/knowledge/vector_store/local_storage.json`、`backend/data/compliance/risk_terms.json` 仍作为 git 受控 seed；
    - 启动时 `main._bootstrap_storage()` 调用 `run_migrations` → `factors_store.seed_from_filesystem` → `compliance_store.seed_from_filesystem` → `projects_api.migrate_legacy_workspaces` → `refinery.ensure_seeded`，按 fingerprint 幂等 upsert 到 SQLite；
    - Projects 以 SQLite 为唯一真源（`workspaces/*.json` 仅作一次性导入兜底）。
  - **E1 DB 底座** (`backend/db.py`):
    - 连接工厂 `connect()` + WAL/FK/Row factory；`DB_PATH` 默认 `backend/data/app.sqlite3`；
    - `run_migrations()` 幂等；创建 `projects / history_log / factors / compliance_rules / knowledge_docs / knowledge_vectors` 表 + 索引；FTS5 可用时建 `knowledge_fts`；
    - `get_conn()` 首次访问自动跑迁移，测试用 `reset_for_tests()` 重置缓存。
  - **E2 Projects / History 迁移** (`backend/projects_api.py`):
    - `load_projects / load_project / save_project / append_history_entry / update_history_decision` 全部走 DB；
    - Project 对外 API 仍返回 Phase 25 的 schema（包括 `history_log[]`），前端零改动；
    - `_record_history`（`backend/main.py` L313）不再 append 到 project JSON，而是 `INSERT INTO history_log`；schema_version=3；
    - `/api/history/decision` 改成 `UPDATE history_log SET decision=...`；
    - 首次启动从 `workspaces/*.json` 幂等导入，之后 JSON 文件只读。
  - **E3 Factors / Compliance seed** (`backend/factors_store.py` + `backend/compliance_store.py`):
    - `factors_store.seed_from_filesystem()` 扫描 `FACTORS_DIR` 下 `angles / platforms / regions`，按 SHA1 fingerprint 幂等 upsert；替换 `main.py` 原先 7 处 `base_dir = str(FACTORS_DIR)` + 内嵌 `read_insight` 闭包（L904 / L1154 / L1365 / L1986 / L2011 / L2027 / L2055）；
    - `compliance_store.seed_from_filesystem()` 读 `risk_terms.json` 重建 `compliance_rules`；`compliance.load_risk_terms()` 改走 DB，JSON 作为兜底；`invalidate_cache()` 暴露给测试；
    - `/api/insights/manage/update` 写 JSON 后立即 `_seed_now`；`/api/insights/manage/delete` 同步从 `factors` 表删除。
  - **E4 Knowledge + 混合检索** (`backend/refinery.py`):
    - `KnowledgeStore(db)` 取代旧 `ScikitLearnLocalDB` / `EmbeddingLocalDB`；`add()` 同时写 `knowledge_docs` + `knowledge_fts` + BLOB 向量 `knowledge_vectors(doc_id, model_id, dim, vec)`；
    - 首次 seed 自动从 `local_storage.json` 导入（`ensure_seeded`）；
    - 检索流水线：`QueryExpander`（用 angle 的 `logic_steps / psychological_triggers / commercial_bridge / regional_adaptations[region]` 扩充 query）→ `_bm25_topn`（FTS5 MATCH + `bm25()` → 1/(1+s) 归一）+ `_vector_topn`（sentence-transformers 或 TF-IDF 兜底）→ `_rrf_fuse(k=60)` → `_apply_region_boost`（老 region_boost_tokens 逻辑保留）→ `_mmr_select(lambda=0.7)` → 可选 `_rerank_cross_encoder`；
    - `retrieve_context_with_evidence` 返回签名不变 `(context, citations, evidence)`，`context` 按 `reason_tag`（hook / format / editing / psychology / general）分组，evidence 多出 `reason_tag` 字段；
    - 新路由 `GET /api/knowledge/stats` 返回 `{retrieval_backend, fts5, vectors, rerank, rerank_model, total_rules, recent_intel}`；`POST /api/knowledge/reindex` 重建向量；
    - 环境变量：`DB_PATH / RAG_RETRIEVAL / RAG_EMBEDDING_MODEL / RAG_TOPN / RAG_RRF_K / RAG_MMR_LAMBDA / RAG_RERANK / RAG_RERANK_MODEL`。
  - **E5 前端面板** (`frontend/src/pages/OracleIngestion.tsx` + i18n):
    - Intelligence Feed 标题行新增 `Backend / FTS5 / Rerank / vectors` 4 个状态胶囊 + `Reindex` 按钮；
    - 翻译键：`oracle.retrieval_backend / fts_tag / rerank_tag / vectors_tag / reindex / reindexing`（zh + en 双语）；
    - Dashboard / Lab 其余视图保持零改动（API 返回结构兼容）。
  - **E6 收口 / 测试**:
    - 新增 `tests/test_db_migrations.py`（3 用例）/ `tests/test_factors_store.py`（2）/ `tests/test_compliance_store.py`（2）/ `tests/test_knowledge_hybrid.py`（5）；
    - `tests/conftest.py` 接管 `DB_PATH` 指向 per-session 临时文件，避免污染开发 DB；
    - `test_phase22 / test_partial_failure / test_compliance_admin / test_providers_api` 的 `_write_workspace` 帮助函数改为同时写 JSON + `save_project` 到 DB，读端通过 `_load_workspace`（DB 优先）；
    - 验证：`pytest -q` → **121 passed**（109 baseline + 12 新）；`npm run build` 无错。
  - **性能 / 兼容 / 回滚**:
    - FTS5 不可用时自动降级为 `LIKE`；sentence-transformers 不可用时退回 TF-IDF，rerank 自动 off；
    - 未配 `DB_PATH` 默认落在 `backend/data/app.sqlite3`（WAL 模式、外键、`synchronous=NORMAL`，本地 SSD 体感无感知开销）；
    - 前端依靠 `/api/knowledge/stats` 获取新字段（retrieval_backend / fts5 / vectors / rerank），老前端即使不用新键也不会报错（均为加项）。

- **[Phase 26] Engine consolidation — Ollama / 本地引擎全量下线 (2026-04-17)**:
  - **背景**：实战中本地 LAN 推理链路（LM Studio / Ollama 192.168.0.48）稳定性差，引发过“分镜数量偏少”的静默 mock 降级事故（SOP-008649）。决策：不再维护第二条推理链路，全面收敛为 DeepSeek 云端。
  - **删除文件**：`backend/ollama_client.py`、`backend/tests/test_ollama_client.py`、`backend/fix.py`（历史一次性迁移脚本）、`docs/Ollama-Integration.md`。
  - **`backend/main.py`**：移除 `generate_script_local` / `generate_draft_local`；`/api/generate` 的 draft + director 阶段彻底去掉 `engine == "local"` 分支；`/api/quick-copy` & `/api/quick-copy/refresh` 本地分支同步删除；`/api/extract-url` 收敛为「云端优先 → 规则回落」，不再读 `request.engine`。`record_generate_success(...)` / `_record_history(...)` 统一传 `"cloud"`。Request Pydantic 模型保留 `engine: str = "cloud"` 字段以兼容前端请求体，但仅作 metadata。`_looks_like_error_placeholder` 的 flag 集由 `Ollama parsing failure` / `LOCAL_*` 改为 `CLOUD_SYNTHESIS_FAILED` / `CLOUD_UNAVAILABLE` / `DRAFT_UNAVAILABLE`。
  - **`backend/scraper.py`**：删除 `_local_llm_usp_with_tokens` 与 `from ollama_client import ...`；`extract_usp_via_llm(title, meta)` / `extract_usp_via_llm_with_usage(title, meta)` 签名不再接受 `engine`。
  - **`backend/usage_tracker.py`**：`record_generate_success` / `record_extract_url_success` 的 `engine` 入参退化为 no-op；`USAGE_TOKENS_ESTIMATE_GENERATE_LOCAL` 分支与 env 变量双双下线。
  - **配置**：`backend/.env` 与 `.env.example` 删除 `OLLAMA_BASE_URL` / `OLLAMA_MODEL_EXTRACT` / `OLLAMA_MODEL_DIRECTOR` / `LLM_RUNTIME_MODE`；新增 `DEEPSEEK_TIMEOUT_SECONDS`（默认 90s draft / 120s director）。
  - **测试**：`test_api_routes.py` 移除三个 `test_api_generate_local_*`，新增 `test_api_generate_cloud_success`（mock `cloud_client` 返回合法 director JSON）；`test_business_flow_e2e.py` 全切云端 + fake DeepSeek 客户端；`test_scraper.py` 删除两个 local monkeypatch 用例，新增 `test_extract_usp_with_usage_reports_no_llm`；`test_usage_api.py` 把第二次 `record_generate_success("local", ...)` 改为 `"cloud"`。
  - **README / docs**：README 徽章与排障章节收敛为 DeepSeek-only；`docs/PRD.md` / `docs/BUSINESS_FLOW_AUDIT.md` / `docs/BUSINESS_AVAILABILITY_TEST_CASES.md` / `docs/PRODUCT_INTEGRATION_REVIEW.md` / `docs/E2E_FULL_VERIFICATION_RUNBOOK.md` / `docs/AUTOMATION_SCOPE.md` 相关句段一并更新；本文件历史 Phase 条目保留但标注 `[SUPERSEDED 2026-04-17]`。
  - **验证**：`pytest tests/ -q` → **53 passed**；无 lint 错误。
- **[Phase 25] 多模型入口：Provider Registry + Per-call 路由 + Engine Selector UI（2026-04-17）**:
  - **目标**：在 Phase 23/24（可靠生产 + 资产化）基础上，把"只能调 DeepSeek"升级为"可按需切换云端大模型"。全部走 OpenAI 兼容协议，单用户/私部署友好；ZEN 先做占位，等官方放出生产入口再启用。`pytest -q` **109/109 绿**，`npm run build` OK。
  - **D1 · Provider Registry**（`backend/providers.py` 新增 + `.env.example` 扩展）：
    - `ProviderSpec` 冻结数据类 + `PROVIDERS` 元组：`deepseek` / `siliconflow` / `bailian` / `openrouter` / `zen`（deferred）。
    - 统一字段：`api_key_env` / `base_url_env` / `model_env` / `supports_json_mode` / `default_price_prompt_cny` / `default_price_completion_cny` / `model_choices`。
    - 工具函数 `get_provider_spec` / `get_client`（带缓存）/ `resolve_model` / `resolve_base_url` / `is_json_mode_supported` / `get_price_per_1k` / `list_providers`（**不泄漏** API key，只返回 `available` 布尔值）/ `default_provider_id`（优先选已配置 key 的厂商）。
    - `.env.example` 新增五段（SiliconFlow / Bailian / OpenRouter / ZEN + 每家 `*_PRICE_*` 可选 env 开关）。
    - 单测 `backend/tests/test_providers.py`（14 用例）：列表顺序、安全字段、模型优先级（param > env > default）、兜底厂商、JSON mode 支持、价格 env 覆盖、无 key 时返回 None、client 缓存、default_provider_id 选择、zen 标注 deferred、模块可重载。
  - **D2 · Per-call 路由 + History schema v3**（`backend/main.py` + `backend/usage_tracker.py` + `backend/cost_estimator.py` + `backend/compliance.py`）：
    - 新增 `resolve_llm_client(provider, model, *, default_env_model=None) -> (client, provider_id, model)`：优先新注册表客户端；缺 key 时回落 legacy `cloud_client`（DeepSeek）；都无则返回 `(None, pid, model)` 供 graceful skip。
    - 请求模型新增 `engine_provider` / `engine_model`：`GenerateScriptRequest` / `QuickCopyRequest` / `RefreshCopyRequest` / `RetryRegionRequest` / `ExtractUrlRequest` / `EstimateRequest` 六个入口。
    - 五处 call site 迁移：`quick_copy` / `refresh_copy` / `retry_region` / `extract_url` / `generate_script`（draft + director 两阶段复用同一次解析）——每次调用都先 `resolve_llm_client(...)`，再把 `active_client` + `model_id` 传给 `chat.completions.create`。
    - `compliance.maybe_generate_rewrite_suggestions` 接 `model: str | None = None`，与调用方同步。
    - `usage_tracker`：`_add_llm_tokens` / `record_generate_success` / `record_extract_url_success` 新增 `provider` 关键字，按 `by_provider[pid] = {tokens, calls}` 聚合；`_fresh_row` / `_normalize_loaded` / `get_summary` 同步扩展，向前兼容遗留的 `tokens_used_estimate` 字段。
    - `history_log` schema 升级为 v3：`_record_history` 新增 `provider` / `model` 入参；所有写入点（generate_script / quick_copy / refresh_copy）透传；`schema_version = 3`。
    - `cost_estimator._input_price` / `_output_price` 支持 `provider_id` 参数，从 `providers.get_price_per_1k` 取价；`estimate_tokens` 吃 `params["engine_provider"]`，返回新增 `provider_id` 字段。
    - 回归：`test_phase22` 的 `schema_version == 2` 改为 `>= 2`（向前兼容 v3）。
  - **D3 · Engine Selector UI**（`frontend/src/pages/Lab.tsx` + `frontend/src/pages/Dashboard.tsx` + i18n）：
    - `GET /api/providers` 新 route：返回 `{default_provider_id, providers: [{id, label, available, default_model, resolved_model, supports_json_mode, base_url, model_choices, price}]}`，前端 Engine Selector 唯一数据源，**零密钥泄漏**。
    - Lab 右上新增 Engine 卡片：`provider` 下拉（按 catalog 顺序，未配 key 的显示"no key"标签）+ `model` 下拉（`Default (xxx)` + provider.model_choices）；右上角 `READY / FALLBACK` 徽章反映该 provider 是否有 API key。
    - 选择持久化 `localStorage` (`sop_engine_provider` / `sop_engine_model`)；切换 provider 时自动清空 model 回退默认。
    - 所有前端出口都透传 `engine_provider` / `engine_model`：`handleSynthesize` / `handleRefreshCopy` / `buildCurrentPayload` / `/api/estimate` 请求体；`useLabQueue` 的 `QuickCopyJobPayload` / `FullSopJobPayload` / `RefreshCopyJobPayload` 类型增 `EngineOverrides`，Preset/Queue 回放自带 provider 配置。
    - Cost Estimator 条按 provider 单价实时重算（相同 token，OpenRouter vs DeepSeek 价格差异直观可见）。
    - Dashboard 历史条目增加 `provider · model` 胶囊徽章（仅 Phase 25 后生成的条目有值，老条目优雅降级）。
    - i18n 中英新增 `lab.console.engine.{label,provider,model,default_model,no_key,available,fallback_hint,hint}`。
  - **D 收口测试**：
    - `backend/tests/test_providers.py`：14 用例（registry 层）。
    - `backend/tests/test_providers_api.py`：6 用例（`GET /api/providers` 形状 + env 感知 available + `resolve_llm_client` 回落语义 + `quick_copy` 透传 `engine_provider/model` 并写入 history v3 + `/api/estimate` 按 provider 单价重算且 tokens 一致）。
    - 全量回归：`pytest -q` → **109 passed**（Phase 24 基线 89 → +14 providers + +6 providers_api = 109）。
    - 前端 `npm run build`：tsc + vite 均绿。
- **[Phase 24] 资产化：Localization Matrix + 历史搜索 + Compliance 只读管理 + Delivery Pack（2026-04-17）**:
  - **目标**：把 Phase 23 的"可靠生产"进一步升级为"可流通资产"。Copy 不再只是 UI 卡片，而是可搜索、可编辑、可打包交付的本地化矩阵。`pytest -q` 全套件 **89/89 绿**，`npm run build` 无错。
  - **C1 · Localization Matrix 视图**（`frontend/src/components/ResultDashboardView.tsx`）：
    - Ad Copy Hub 顶部加 `Cards ↔ Matrix` 二段切换；Matrix 视图支持 `headline / primary_text / hashtag` 三种 kind tabs 切换。
    - Matrix = locale × slot 表格：每个 region:locale 是一列，每行是第 N 条；单元格为可编辑 textarea，自动适配行高；失败 region 在列头显示 FAILED/FALLBACK 徽章。
    - 就地编辑回流：`updateMatrixCell` 修改 `result.ad_copy_matrix.variants[locale][kind][idx]` 并通过 `onResultUpdate` 透传给 Lab / Dashboard，XLSX / Delivery Pack 导出都会吃到最新内容。
    - Matrix 搜索过滤：任何单元格包含关键词的行才显示；空态提示 `matrix_empty`。
    - Matrix CSV 导出：`slot, {locales...}` 结构，BOM 前缀兼容 Excel 中文。
  - **C2 · Dashboard 历史搜索面板**（`frontend/src/pages/Dashboard.tsx`）：
    - 关键词搜索（脚本 id / term / region/platform/angle / parent / lang / compliance 命中词 全文）。
    - 可折叠 Filters 抽屉：region / platform / angle / output_kind / decision 下拉 + dateFrom / dateTo + 一键 Reset。
    - 选项从当前项目 `history_log` 动态聚合；筛选结果落地在旁边的记数（`filteredHistory.length / projectHistory.length`）。
    - localStorage 持久化（key `dashboard.history_filter.v1`）；三种空态：完全无历史 / 筛选无匹配 / 正常列表。
  - **C3 · Compliance 只读管理页**（`backend/main.py` + `frontend/src/pages/ComplianceAdmin.tsx`）：
    - 新增 `GET /api/compliance/rules`：返回 `risk_terms.json` 完整结构（global / platform_overrides / region_overrides）+ 按 severity 的计数摘要。
    - 新增 `GET /api/compliance/stats`：跨 *所有* 项目 `history_log` 聚合 term 命中次数、risk_level 分布、recent_hits 列表、`avoid_terms_preview`（与 `_collect_avoid_terms` 语义一致的前 12 条）。
    - 前端路由 `/compliance`（`ComplianceAdmin.tsx`）+ 侧边栏导航新增 ShieldCheck 图标：规则树（term / severity / note 搜索过滤） + 横向统计卡片（records / risky / block） + 命中排行榜（进度条占比） + avoid_terms 预览；规则为只读，并展示 `rules_path` 供运营确认。
    - 测试 `backend/tests/test_compliance_admin.py`（2 用例）：规则 endpoint 形状、跨项目 stats 聚合 + avoid_terms_preview cap。
  - **C4 · Delivery Pack**（`backend/main.py` + `frontend/src/components/ResultDashboardView.tsx`）：
    - 新增 `POST /api/export/delivery-pack`：接受 `{data, markdown_path?, project_name?}`，打 zip 返回 base64；包内结构：`README.md`（生成时间 / script_id / locales / partial_failure）、`script.md`（若 `markdown_path` 在 @OUT 下可解析）、`ad_copy.csv`（locale × slot）、`payload.json`（完整响应）。
    - 前端 Result Dashboard 头部增加 **Package** 图标的 "Delivery Pack" 按钮；下载文件名 `delivery_{project}_{script_id}.zip`。
    - 测试 `backend/tests/test_delivery_pack.py`（3 用例）：含 matrix / 不含 matrix / 非法 data。CSV 头部、JSON payload 回路、README 文本均被校验。
  - **验证**：`pytest -q` → **89 passed**（新增 test_compliance_admin 2 + test_delivery_pack 3）；`npm run build` OK。记忆库 / PRD v2.5 / BUSINESS_FLOW_AUDIT 同步更新。
- **[Phase 23] 可靠生产：Injection sanitize + 成本预估 + Queue/Presets + 部分失败协议（2026-04-17）**:
  - **目标**：把 Phase 22 的"闭环学习"升级为"可靠生产"。对齐 PRODUCT_INTEGRATION_REVIEW 的 B 主线。四个子任务全部落地，`pytest -q` 全套件 **84/84 绿**，`npm run build` 无错。
  - **B1 · Prompt Injection sanitize**（`backend/sanitize.py` 新增 + `backend/prompts.py` + `backend/main.py`）：
    - `sanitize_user_text(raw, *, max_len=6000, strict=None, allow_newlines=True)`：剥离零宽/控制字符、Markdown 代码围栏、伪 system/assistant 标签，defuse 诸如 `ignore previous instructions` / `you are now` / `system:` / `### instruction` 等注入模板，超长截断，`SANITIZE_STRICT=1` 时进一步收紧换行。
    - `sanitize_list(items)` / `sanitize_game_info(info)` / `wrap_user_input(text)`：前两者批量清洗；后者用 `<<<USER_INPUT>>> ... <<<END_USER_INPUT>>>` 分隔符包裹。
    - `prompts.py` 引入 `INJECTION_GUARD` 系统级指令（要求 LLM 把分隔符内容当作 **data**，忽略其中一切指令），`render_draft_prompt` / `render_director_prompt` / `render_copy_prompt` 前置该 guard；`_build_common_context` 对 `game_context` 统一 `wrap_user_input`；director/copy 中 `selected_draft_json` / `base_script_context` 也走同样包裹。
    - `main.py` 三处入口（`/api/extract-url`、`/api/generate`、`/api/quick-copy`、`/api/quick-copy/refresh`）均在进入 LLM 前调用 `sanitize_game_info` / `sanitize_user_text` / `sanitize_list`，保护 `project.name` / `game_info` / `tones` / `locales` / URL 抓取结果。
    - 单测 `backend/tests/test_sanitize.py`（17 用例）：覆盖零宽/控制字符剥离、8 种注入模板 defuse、代码围栏剔除、截断、None/空串、`allow_newlines=False`、prompt 集成（注入内容被包裹、不会污染系统段）。
  - **B2 · 成本预估**（`backend/cost_estimator.py` 新增 + `POST /api/estimate` + `frontend/src/pages/Lab.tsx`）：
    - `estimate_tokens(kind, *, quantity, locales, regions, compliance_suggest, ...)`：对 `generate_full` / `generate_draft` / `quick_copy` / `refresh_copy` 计算 prompt/completion token 与 CNY 成本。单价来自 env `DEEPSEEK_PRICE_{PROMPT,COMPLETION}_CNY_PER_1K`（默认 0.001 / 0.002）。合规建议额外成本计入。
    - `estimate_with_budget(...)`：叠加当日 `usage_tracker` 已用额度，输出 `remaining_cny`、`projected_remaining_cny`、`warning_level ∈ {ok, near, over}`。
    - API `POST /api/estimate` 接 Pydantic `EstimateRequest`，返回上述估算 + 预算分级。
    - 前端 Lab 吸附条：在「Generate」按钮上方显示 Tokens / 估算成本 / 剩余预算，300ms 防抖；`near` 橙色、`over` 红色并要求二次确认。i18n 加 `lab.estimate.*` 双语。
    - 单测 `backend/tests/test_cost_estimator.py`（10 用例）：返回形状、数量/多 locale/多 region 的单调性、`compliance_suggest` 开销、未知 kind 回落、预算分级（含零预算）、`/api/estimate` happy path。
  - **B3 · Queue & Presets（纯前端）**（`frontend/src/hooks/useLabQueue.ts` 新增 + `frontend/src/pages/Lab.tsx`）：
    - Hook 暴露 `presets` / `queue` / `isRunning` / `runProgress` / `etaSeconds` 等状态与 `addJob / removeJob / clearQueue / runAll / cancelRun / savePreset / deletePreset / renamePreset / togglePinPreset` 方法。
    - Presets：最多 10 条，支持 pin / rename / delete；`localStorage` 持久化。
    - Queue：串行调度；每个 job 带 `pending / running / ok / failed` 四态，`runAll` 内部通过 `queueRunner` 调 `/api/generate` 或 `/api/quick-copy`；`avgJobMs` EMA 估算 ETA，存 `localStorage`；支持 `cancelRun` 立即中止；每条成功 job 的 `result` 可一键回填 Result Dashboard。
    - Lab 新增两个可折叠抽屉（Presets / Queue），按钮区 `ListPlus` / `ListChecks` 加入当前参数或执行队列；i18n `lab.presets.*` / `lab.queue.*` 双语补齐。
  - **B4 · quick_copy 部分失败协议**（`backend/main.py` + `frontend/src/components/ResultDashboardView.tsx`）：
    - `/api/quick-copy` 每个 region 单独 try/except LLM 调用，写入 `region_statuses[rid] ∈ {ok, failed, fallback, skipped}` 与 `region_errors[rid]`（截断 300 字）。
    - 语义：只要**任一 region 尝试过 LLM**（非 `skipped`）且存在非 `ok`，`partial_failure=True`；全 `skipped`（无 cloud_client）保留 Phase 22 语义（`draft_status="skipped"`，不算失败）。
    - `QuickCopyResponse.partial_failure: bool` 新字段；`ad_copy_matrix.regions_status` / `regions_error` 下发前端；`_record_history` 在部分失败时把 `draft_status` 置为 `fallback`。
    - 新 API `POST /api/quick-copy/retry-region {project_id, script_id, region_id}`：只重跑单一 region，与原 history 条目的 `ad_copy_matrix` 合并；刷新 `regions_status` / `regions_error` / `partial_failure`；拒绝非 copy 类型的 script_id（400）。
    - 前端 `ResultDashboardView`：
      - 新 prop `onResultUpdate?(next)`：Lab 直接把 `synthesisResult` 同步。
      - `useMemo` 推导 `regionStatuses` / `regionErrors` / `partialFailure`；Ad Copy Hub 顶部横幅（AlertTriangle + 全部 region 状态列表）；每张 locale 卡右上角按 region 展示徽章；`failed` / `fallback` 卡片显示「Retry region」按钮（RefreshCw 旋转态），调 `retryRegion(rid)` → `/api/quick-copy/retry-region`。
    - 测试 `backend/tests/test_partial_failure.py`（4 用例）：多 region 成功/失败混合、全部成功（`partial_failure=False`）、retry-region happy path、非 copy 类型的 script_id 400。
  - **验证**：`pytest -q` → **84 passed**；`npm run build` OK。记忆库 / PRD / BUSINESS_FLOW_AUDIT 同步更新（v2.4）。
- **[Phase 22] 闭环学习：history schema v2 + 合规反哺 + Winner/Loser 决策回流（2026-04-17）**:
  - **目标**：把 Phase 21 的“资产记录”升级为“可学习回路”。历史数据不再只服务于 UI，而是回馈 Prompt（负向词）与评分（Winner/Loser 信号）。对齐 `docs/PRODUCT_INTEGRATION_REVIEW.md` 的 A 主线。
  - **history_log schema v2**（`backend/main.py`）：
    - 在 `record_history` 写入：`schema_version=2` / `lang` / `parent_script_id` / `factor_version` / `rag_rule_ids[]` / `draft_status` / `decision="pending"` / `decision_at`。
    - **关键 Bug 修复**：`record_history` 原来是 `generate_script` 内嵌函数，`quick_copy` / `refresh_copy` 对它的调用被 `try/except pass` 静默为 `NameError`，意味着 **Phase 21 之前 quick_copy / refresh_copy 根本没写入 history_log**。本期提升为模块级 `_record_history` 修复。
    - `refresh_copy` 现把 `base_script_id` 写入新条目的 `parent_script_id`，首次建立 Refresh 血缘。
    - `factor_version`：对（region/platform/angle 或 多 region 合集）JSON 做 sha1 前 12 位摘要；用于 Compare 检测因子改版。
    - `rag_rule_ids`：从 RAG evidence 的 `id/rule_id/source/citation` 按顺序去重提取，cap 20。
    - `draft_status`：`"ok" | "fallback" | "skipped"`；`generate_script` 的 draft 阶段精确跟踪失败降级。
  - **Compliance 负向词反哺 Prompt**（`backend/prompts.py` / `main.py`）：
    - 新增 `_collect_avoid_terms(project_data)`：聚合项目近 5 条历史里的 `compliance.hits[].term`，大小写去重 cap 12。
    - `render_director_prompt` / `render_copy_prompt` 新增 `avoid_terms: list[str] | None = None` 参数；当存在时在 prompt 末尾追加 `[COMPLIANCE NEGATIVE LIST - Must Avoid]` 区块。
    - `generate_script` / `quick_copy` / `refresh_copy` 三路入口均在调用 LLM 前计算并注入。
  - **Winner/Loser 决策反馈（新 API + UI）**：
    - 后端 `POST /api/history/decision {project_id, script_id, decision}`：`decision ∈ {pending, winner, loser, neutral}`，更新 `history_log` 对应条目，附 `decision_at` ISO 时间戳；非法 decision 400、未知 project/script 404。
    - 前端 `frontend/src/pages/Dashboard.tsx` 记录行追加三段小按钮（Trophy / ThumbsDown / Minus），点击即调用该 API；已决策条目在头部显示彩色 badge。Refresh 产物新增显示 `Refresh of <parent id>`，draft 降级显示 `draft→fallback` badge；多语言输出显示 `CN/EN` 小标签。
  - **i18n**：`dashboard.history.decision_*` / `mark_*` / `clear_decision` / `draft_fallback` / `parent_of` en/zh 双语补齐。
  - **测试**：新增 `backend/tests/test_phase22.py`（12 用例），覆盖 `_render_avoid_terms_block` / `render_director_prompt` / `render_copy_prompt` 的 avoid list 注入、`_collect_avoid_terms` / `_compute_factor_version` / `_extract_rag_rule_ids` 的正确性、`quick_copy` 写入 schema v2、`/api/history/decision` 的 happy/invalid/missing 路径。**完整后端套件 59/59 全绿**（`pytest -q`）。
- **[Phase 21] 生产力闭环：结果页复用 + 记录管理 + 对比视图（2026-04-16）**:
  - **目标**：把“生成一次”升级为“生成 → 复用 → 刷新 → 对比 → 导出”的连续迭代路径，降低产物分散在 Lab/@OUT 的查找与二轮测试成本。
  - **Result Dashboard 组件化复用**：
    - 新增 `frontend/src/components/ResultDashboardView.tsx`：统一结果页遮罩、body scroll lock、Markdown 拉取（`GET /api/out/markdown`）、复制/下载/导出（MD/XLSX/PDF）与合规详情入口。
    - `frontend/src/pages/Lab.tsx` 与 `frontend/src/pages/Dashboard.tsx` 复用同一结果页视图，保证体验与能力一致。
  - **Dashboard 右侧“生成记录管理”面板**（资产库入口）：
    - `frontend/src/pages/Dashboard.tsx` 右侧改为**按项目过滤**的 `history_log` 列表（时间、region/platform/angle、output_kind、risk badge）。
    - 支持一键 **Open** 打开 `ResultDashboardView` 复现结果。
    - 支持勾选两条记录进行对比；对 SOP 记录支持一键 **Refresh copy**（调用 `POST /api/quick-copy/refresh` 并刷新项目数据）。
  - **两条记录对比视图**：
    - 新增 `frontend/src/components/CompareViewModal.tsx`：展示参数差异 + 文案差异（headlines/primary_texts added/removed）+ 合规命中词差异（term added/removed）。
  - **交互稳定性**：
    - 对 Dashboard/Result/Compare 的滚动容器统一加 `scrollbar-gutter: stable`（通过 `style={{ scrollbarGutter: 'stable' }}`）以减少滚动条出现/消失引起的宽度抖动。
  - **i18n 补齐**：
    - 为 Dashboard 记录管理/对比新增文案补齐 `frontend/src/i18n/locales/en.json` 与 `zh.json`，并将时间相对展示（Just now / Xm ago 等）也纳入 `t()`。
  - **后端测试兼容修复**：
    - 为历史单测恢复 `backend/prompts.py:get_system_prompt_template(...)`（旧测试依赖），新链路仍以 `render_draft_prompt` / `render_director_prompt` / `render_copy_prompt` 为主。
- **[Phase 14] Director button system + palette + Tailwind v4 CSS hardening (2026-04-13–14)**:
  - **`frontend/src/index.css`**: `btn-director-*` + `success` tokens; `header-module-tab` / `nav-director-link--active`; segmented control border aligned with secondary outline weight. **Tailwind v4 limitation**: `@apply` inside `@layer utilities` **must not** reference other custom utilities from the same file (e.g. `transition-director-*`, `ring-focus-brand`, `shadow-elev-1`). Mitigations in tree: duplicate **focus ring** utilities on button rules; **transition** as raw `transition-property` / `var(--duration-*)`; **nav active shadow** inlined instead of `@apply shadow-elev-1`. Standalone classes `.ring-focus-brand`, `.transition-director-colors`, `.transition-director-transform` remain for TSX.
  - **`MainLayout.tsx`**: New Script / module tabs / Strategy Matrix / ghost nav actions aligned to the button system; sidebar **logo** uses neutral `bg-on-surface text-on-primary` (not primary-dim); active route icons use **`text-secondary-fixed-dim`**.
  - **`Generator.tsx`**, **`ThemeAppearanceControl.tsx`**, **`Dashboard.tsx`**, **`OracleIngestion.tsx`**, **`Library.tsx`**, **`Editor.tsx`**: CTAs and accents migrated to `btn-director-*` or neutral surfaces; removed heavy indigo/violet panels in favor of `surface-panel` / outline tokens where applicable; clarity metric bar uses **secondary** to differentiate from hook emerald.
- **[Phase 13] Sidebar shell context + quota card + billing-aware usage (2026-04-14)**:
  - **`frontend/src/layout/MainLayout.tsx`**: Generator / Oracle `NavLink` show a small **busy dot** (breathing animation; respects `prefers-reduced-motion`) with `aria-busy` and status `title`/`aria-label` when `ShellActivityContext` reports work in progress. **Pro Plan** is a focusable control: hover / focus-within / tap-to-pin opens a **quota popover** that calls **`GET /api/usage/summary`** (≈45s client cache).
  - **`frontend/src/pages/Generator.tsx`** / **`OracleIngestion.tsx`**: Report shell busy state via `useShellActivity` (Generator: generate + extract fetching/parsing only, not `confirm` idle). **`frontend/src/config/apiBase.ts`**: `API_BASE` from `import.meta.env.VITE_API_BASE` or `http://127.0.0.1:8000` for all axios calls.
  - **`frontend/src/index.css`**: `.shell-activity-dot` keyframes for the nav pulse.
  - **`backend/usage_tracker.py`**: `record_generate_success(engine="cloud", measured_tokens=None)`, `record_extract_url_success(engine="cloud", measured_tokens=None, used_llm=False)`, `record_oracle_ingest_success()`. Extract path only charges when `used_llm=True` (cloud DeepSeek returned valid structured JSON via **`extract_usp_via_llm_with_usage`**). `engine` kwarg is retained for signature compat only. _(Phase 26 — 2026-04-17: Ollama local path + `_LOCAL` estimate bucket removed.)_
  - **`backend/scraper.py`**: **`extract_usp_via_llm_with_usage(title, metadata) -> (text, tokens|None, used_llm)`**; **`extract_usp_via_llm`** remains a thin wrapper returning text only. **`extract_usp_via_llm_mock`** alias unchanged. Rule-based distillation is the only path now; the cloud LLM call was relocated to `main.extract_url`.
  - **Env tuning**: `USAGE_DAILY_TOKEN_BUDGET`, `USAGE_TOKENS_ESTIMATE_GENERATE_CLOUD`, `USAGE_TOKENS_ESTIMATE_EXTRACT` when provider `usage` is missing.

### ✅ Latest Validation Snapshot (2026-04-17 · Phase 26·E)

- Backend full regression: `pytest -q` → **121 passed** (Phase 25 baseline 109 + 12 new: `test_db_migrations` 3 / `test_factors_store` 2 / `test_compliance_store` 2 / `test_knowledge_hybrid` 5).
- Backend (Phase 19 spot-check): `pytest tests/test_api_routes.py tests/test_refinery.py tests/test_md_export.py` → **21 passed** (covers `mode` / `review` / `retrieve_context_with_evidence` mocks + md export).
- Backend (Phase 20 spot-check): `pytest tests/test_quick_copy.py` → **2 passed** (Quick Copy endpoint contract).
- Backend (historical): run `pytest tests/ -q` excluding known-broken collectors if any (e.g. `test_engine.py` import drift); **`test_api_routes`**, **`test_business_flow_e2e`**, **`test_md_export`**, **`test_refinery`**, **`test_scraper`** exercised after Phase 15. _(`test_ollama_client.py` was removed in Phase 26 — 2026-04-17 alongside the local engine.)_
- Frontend: `npm run build` → **success** (includes Lab i18n + unused-import cleanups where needed).
- Outcomes:
  - Cloud generation failures stay explicit in API and UI (502 with `CLOUD_*` error codes); PDF export blocked on bad payloads.
  - Extraction returns structured bilingual JSON (+ metadata tail); cloud LLM validates schema or falls back to deterministic rules.
  - E2E covers the main Generator business path against real backend + Vite.
  - Sidebar reflects Generator/Oracle async work; quota card reflects server-tracked usage and provider vs estimate token split when available.
  - UI: consistent director button classes; primary brand reads blue (not purple-heavy); `npm run build` must stay green after touching `index.css` compound utilities.
  - Lab/SOP: successful `/api/generate` produces on-disk Markdown under **`@OUT/`** and returns **`markdown_path`** for UI display.
  - Quota popover: exposes operational metrics for cost governance (per-call + average + sample size), with provider-vs-estimate transparency for mixed billing days.
  - CN markdown storyboard is now shorter and production-oriented, reducing repeated explanatory lines for Chinese editor workflows.

### ⏳ Imminent Next Steps (To-Do List)

1. **Apple App Store Support**: Extend `scraper.py` logic to parse dual-platform markets.
2. **Runbook drift**: Keep `docs/E2E_FULL_VERIFICATION_RUNBOOK.md` aligned with Playwright timeout / `PLAYWRIGHT_FORCE_SPAWN` behavior.

---

## 4. 🧩 Development Details & Constraints

### ⚠️ Coding Nuances to Remember

- **Tailwind Versioning**: We are strictly using **Tailwind v4**. Do not attempt to run `npx tailwindcss init` or create `tailwind.config.js`. Theme extensions go into `frontend/src/index.css` under `@theme`.
- **Tailwind v4 + `@apply`**: Do not `@apply` **project-defined** utility class names (e.g. `ring-focus-brand`, `transition-director-transform`, `shadow-elev-1`) inside other utilities in the same CSS file — the Vite/Tailwind pipeline treats them as unknown. Expand to core utilities or plain CSS (`box-shadow`, `transition-*`, etc.).
- **Generation Failure Policy**: The frontend no longer fabricates mock scripts when generation fails. Backend/LLM failures must remain explicit (HTTP 502 with `CLOUD_UNAVAILABLE` / `CLOUD_SYNTHESIS_FAILED` / `DRAFT_UNAVAILABLE`) so operators can diagnose network / API-key / schema issues without polluting downstream exports. There is **no mock/local fallback** — this was intentionally removed in Phase 26 (2026-04-17).
- **Extraction Strategy Policy**: Cloud DeepSeek is invoked inside `main.extract_url` with `EXTRACT_USP_VIA_LLM_SYSTEM_PROMPT` and strict JSON validation; when the key is missing or the call fails, `scraper.extract_usp_via_llm_with_usage` returns a deterministic rule-based bilingual director archive (no random hooks, no LLM spend). `extracted_usp` is a string: leading JSON + optional store metadata sections. **Frontend** mirrors the same split in `directorArchive.ts`; **confirmed** URL flows set React `usp` state to **`buildUspEnContext`** when JSON is valid so `/api/generate` receives English-only structured context.
- **Usage & billing policy**: Token counts prefer **provider `usage`** (OpenAI-compatible completions). No-key generation now fails loud — it does **not** increment any token bucket. **`/api/extract-url`** billing: rule-based fallback → no tokens; cloud LLM success → measured or `USAGE_TOKENS_ESTIMATE_EXTRACT` fallback.
- **Quota popup metrics policy**: `last_script_tokens` / `avg_tokens_per_script_today` are based on successful `/api/generate` calls only (not extract/ingest). Mixed days must disclose provider/estimate sample split to prevent “false precision” in cost interpretation.
- **Windows / uvicorn logging**: Avoid non-ASCII `print` of uncontrolled prompt text without safe encoding; use `_print_console_safe` or ASCII-only logs for hot paths.
- **RTL Conditional Rendering**: The UI currently drives RTL changes explicitly via the `dir='rtl'` property inside the individual script nodes when the parameter reads "Middle East". Do not attempt to force-rebuild the entirety of `index.css` for RTL.
- **`@OUT` Markdown files**: Generated by the backend next to the repo root; do not commit `*.md` there (gitignored). For local dev, confirm the `uvicorn` process can write to the workspace directory.
- **Knowledge path policy**: New work should use `knowledge_paths.py` constants (`FACTORS_DIR`, `VECTOR_DB_PATH`) instead of hardcoding `data/insights` or `chroma_db` paths. Legacy paths are compatibility-only.
- **Filename policy**: Prefer concise readable labels (`short_name`) for region/platform/angle to keep SOP exports scannable in production ops.
- **CN storyboard policy**: `output_mode=cn` should prioritize “执行指令密度” over bilingual explainability; avoid duplicate interpretation rows when source fields are already Chinese-facing.

### 🗂️ Workspace Layout

```text
D:\PRO\AdCreative AI Script Generator\
│
├── @OUT/                   <-- synthesis Markdown output ( *.md gitignored; .gitkeep optional )
├── docs/
│   ├── PRD.md
│   ├── MEMORY_BANK.md      <-- This file (Context)
│   └── E2E_FULL_VERIFICATION_RUNBOOK.md
│
├── backend/
│   ├── knowledge_paths.py  <-- canonical knowledge/factor/vector path registry + legacy migration
│   ├── main.py             <-- FastAPI routes (generate, extract, usage summary, …)
│   ├── md_export.py      <-- @OUT Markdown writers for /api/generate success
│   ├── projects_api.py   <-- workspaces JSON CRUD (project history_log, …)
│   ├── prompts.py          <-- 5-DNA Core Prompter Engine (+ compliance & director-note schema constraints)
│   ├── scraper.py          <-- Play metadata + bilingual director archive extract
│   ├── usage_tracker.py    <-- Daily counters + /api/usage/summary payload
│   ├── usage_tokens.py     <-- Parse completion.usage total_tokens
│   ├── usage_counters.json <-- Persisted daily usage (gitignored)
│   ├── data/
│   │   └── knowledge/
│   │       ├── factors/    <-- canonical regions/platforms/angles store (migrated from data/insights)
│   │       └── vector_store/
│   │           └── local_storage.json
│   ├── tests/              <-- pytest (incl. test_md_export, test_api_routes, …)
│   └── requirements.txt
│
└── frontend/
    ├── package.json        <-- scripts: test:e2e, verify:full
    ├── playwright.config.ts
    ├── e2e/                <-- Playwright specs (e.g. core-flow)
    ├── vite.config.ts      <-- @tailwindcss/vite plugin
    └── src/
        ├── index.css
        ├── App.tsx
        ├── config/
        │   └── apiBase.ts           <-- API_BASE / VITE_API_BASE
        ├── context/
        │   ├── ShellActivityContext.tsx
        │   └── ProjectContext.tsx   <-- projects from /api/projects; current workspace
        ├── components/
        │   ├── ProjectArchiveCard.tsx
        │   └── ThemeAppearanceControl.tsx   <-- theme pref + segmented control / mobile menu
        ├── utils/
        │   └── directorArchive.ts   <-- parse JSON extract + build EN usp for generate
        ├── layout/
        │   └── MainLayout.tsx       <-- sidebar busy dots + Pro Plan quota popover
        └── pages/
            ├── Dashboard.tsx
            ├── Lab.tsx              <-- SOP mixing console; POST /api/generate; shows markdown_path
            ├── Generator.tsx
            └── OracleIngestion.tsx
```
