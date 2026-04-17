# 产品需求文档 (PRD): AdCreative AI Script Generator

**版本**： v2.7（与当前实现对齐）
**状态**： Storage-Upgrade V2.7（`docs/MEMORY_BANK.md` Phase 1–26；Phase 26·E 收口"存储底座升级"— SQLite 运行期读写层 + BM25(FTS5)+Vector+RRF+MMR 混合检索 + 可选 Cross-Encoder 重排）
**目标**： 通过 AI 自动化生成基于买量逻辑的游戏素材脚本与文案，并把“生成一次”升级为“可连续迭代”的生产力闭环。

> 本版在保留 v1.0 愿景的前提下，补齐了当前代码库已实现但旧 PRD 未覆盖的产品能力，并显式标注“愿景 vs 当前实现”的差异与延后项。旧 v1.0 规划内容在 §9/§11 做了版本差异说明，便于后续决策参考。

---


## 1. 项目概述

### 1.1 背景

移动游戏买量（UA）市场素材消耗极快，创意团队面临“构思慢、爆款率不稳定、跨平台风格适配难、素材疲劳快”的问题。
随着生成式 AI 成熟，真正的瓶颈已经从“产出单条脚本”转移到：
- 项目级 DNA 对齐（USP、核心玩法、目标人群）
- 地区 × 平台 × 心理学角度的组合爆炸
- 合规与素材疲劳下的**二轮迭代**（Refresh）与**对比**（Compare）
- 投放文案（headline/primary_text/hashtag）与分镜脚本分离的**双轨生产**

### 1.2 目标

构建一套 UA 中控台，围绕**项目**串联：档案提取 → 参数调制 → 生成（SOP/Copy）→ 结果审阅 → 记录归档 → 刷新/对比 → 多格式导出。
不仅输出单条脚本，更提供**可复用资产库**与**素材迭代工作流**。

---

## 2. 用户角色与核心流程

### 2.1 用户角色
- **UA Creative Lead / 投放师**：负责选 Angle、生成脚本、审批、下发剪辑。
- **视频制作人 / 剪辑师**：负责读取分镜 SOP（中文/英文执行导向）并交付。
- **本地化编辑 / 翻译**：负责多语言 transcreation，不是机翻。
- **UA Manager / 运营**：关注产出速度、用量成本、合规风险、迭代效率。

### 2.2 核心流程（当前实现，**MVP Path 闭环**）

```
选项目 (Dashboard)
  ↓
配参数 (Lab: region / platform / angle / output_type / output_mode)
  ↓
生成
  ├─ Full SOP (POST /api/generate, mode=auto|draft|director)
  └─ Quick Copy (POST /api/quick-copy, 支持 region_ids 多选)
  ↓
结果页 (ResultDashboardView: Markdown + Copy Hub + 合规)
  ├─ 复制 / 下载 MD / 导出 XLSX / 导出 PDF / 打开 @OUT 文件夹
  └─ @OUT/ 自动落盘 Markdown
  ↓
自动归档 (backend/data/workspaces/{project_id}.json -> history_log[])
  ↓
Dashboard 右侧「生成记录管理」
  ├─ Open  → 复现结果页
  ├─ Compare(勾两条) → 参数/文案/合规差异
  └─ Refresh Copy (SOP) → POST /api/quick-copy/refresh → 写回 history_log
```

---

## 3. 功能需求 (Functional Requirements)

以下标记说明：
- ✅ 已实现（与本版 PRD 对齐）
- 🧭 规划中/部分实现（愿景方向明确，当前未全量覆盖）
- ⏸ 延后（v1.0 愿景但当前判定不优先）

### 3.1 模块一：项目工作台 (Project Workspace) ✅

> v1.0 原 PRD 未显式设计此模块；实际交付中它是所有流的入口。

- **[F1.0.1] 项目 CRUD**（`backend/projects_api.py`）：`GET/POST/PUT/DELETE /api/projects`；项目数据落 `backend/data/workspaces/{project_id}.json`。
- **[F1.0.2] 项目档案**：`game_info`（title / core_gameplay / usp / target_persona / value_hooks 等）+ `market_targets`。
- **[F1.0.3] 生成记录（history_log[]）**：每次成功生成自动追加；schema 含 `id / timestamp / engine / recipe / output_kind(sop|copy) / output_mode / markdown_path / ad_copy_matrix / ad_copy_tiles / compliance / generation_metrics / script`。
- **[F1.0.4] 当前项目缓存**（`frontend/src/context/ProjectContext.tsx`）：`localStorage` 缓存 `currentProject`，防止 F5 闪回 “No Project Selected”。

### 3.2 模块二：输入与解析 (Input Hub) ✅

- **[F1.1] 文本录入**：`ProjectSetupModal` 收集游戏元数据与卖点。
- **[F1.2] URL 抓取**：`POST /api/extract-url`（`backend/scraper.py` + `backend/main.py`）
  - 优先走云端 DeepSeek + `EXTRACT_USP_VIA_LLM_SYSTEM_PROMPT`（结构化 JSON 校验）。
  - 云端未配置或调用失败 → 回落到确定性规则抽取（Bilingual Director Archive，避免随机 hook）。
- **[F1.3] 投放参数选择**（`frontend/src/pages/Lab.tsx` 参数控制台）：
  - **Region**（`data/knowledge/factors/regions`）
  - **Platform**（`data/knowledge/factors/platforms`）
  - **Angle**（`data/knowledge/factors/angles`）
  - **Output Type**：`Full SOP` / `Quick Copy`
  - **Output Mode**：`cn` / `en`
  - **Gen Mode**（仅 SOP）：`auto` / `draft` / `director`

### 3.3 模块三：AI 创意引擎 (Core Engine) ✅

- **[F2.1] 1+1+3 生成链路**（Phase 19）
  - `1` 项目/游戏 DNA（workspace）
  - `1` Oracle RAG（向量知识库，`backend/refinery.py`，TF-IDF，带证据）
  - `3` Region × Platform × Angle 因子 JSON（`backend/data/knowledge/factors/*`）
- **[F2.2] Prompt 拆分**（`backend/prompts.py`）
  - `render_draft_prompt` → 轻量草案 JSON（多 hook 候选 + `pick_recommendation`）
  - `render_director_prompt` → 最终分镜导演稿（可注入入选草案）
  - `render_copy_prompt` → 文案矩阵专用（点击欲望 / 多变量组合 / transcreation）
  - 历史单测兼容 `get_system_prompt_template`（Phase 21 修复）
- **[F2.3] 脚本结构化输出**
  - 分镜字段：`time / visual / visual_meaning / audio_content / audio_meaning / text_content / text_meaning / sticker_text / sticker_meaning / direction_note / sfx_transition_note`
  - `ad_copy_matrix`：`primary_texts(>=5) / headlines(>=10, with emoji) / hashtags(>=20) / visual_stickers`
  - 可选 `drafts / review / rag_evidence / generation_metrics`

### 3.4 模块四：效果预测评分 (Prediction System) ✅

- **[F3.1] 评分维度**（LLM 侧直出 + `review` 规则审校）
  - `hook_score + hook_reasoning`
  - `clarity_score + clarity_reasoning`
  - `conversion_score + conversion_reasoning`
- **[F3.2] 自动审校（`review`）**：规则层 issues/warnings/score_breakdown（Phase 19）。
- **[F3.3] 竞品/市场上下文**：通过 Oracle RAG 的 `rag_evidence` 返回命中证据（rule/source/year_quarter/match_score/reason_tag）。

### 3.5 模块五：极速文案 (Quick Copy) ✅

> v1.0 原 PRD 未覆盖；实际交付为解决“不必为几条标题跑整套分镜”的运营痛点。

- **[F5.1] `POST /api/quick-copy`**：仅输出 `ad_copy_matrix`；支持 `quantity / tones / locales / region_ids[]`（多地区合并 variants：键为 `"{region}:{locale}"`）。
- **[F5.2] `POST /api/quick-copy/refresh`**：基于 `history_log` 内既有 SOP 记录刷新文案（素材复用）。
- **[F5.3] 文案超市视图**：Copy Hub 按 locale 分组 headlines / primary_texts / hashtags，支持复制/全部复制/XLSX 导出。

### 3.6 模块六：结果审阅 (Result Dashboard) ✅

- **[F6.1] 可复用视图**（`frontend/src/components/ResultDashboardView.tsx`）：Lab 与 Dashboard 共用。
- **[F6.2] Markdown Viewer**：通过 `GET /api/out/markdown` 拉取 `@OUT/` 文件，支持渲染/复制/下载。
- **[F6.3] Copy Hub**：按 locale 磁贴化展示 + 合规风险高亮。
- **[F6.4] 合规 Modal**：Hit 列表（原文 + 高亮 span + term + severity）+ LLM rewrite suggestions（开启 `compliance_suggest` 时）。
- **[F6.5] 多格式导出**：
  - Markdown（本地生成）
  - XLSX（按 locale 分 sheet，headlines/primary_texts/hashtags）
  - PDF（`POST /api/export/pdf`，需含 `script` 字段）
  - 打开 @OUT 所在文件夹（`POST /api/out/open-folder`，**仅 Windows + localhost/环境变量放开**）

### 3.7 模块七：生成记录管理 (Records Panel) ✅

- **[F7.1] 按项目过滤**：Dashboard 右侧面板默认当前项目，可在下拉切换。
- **[F7.2] 列表项信息**：输出类型（SOP/COPY）、risk badge（OK/WARN/BLOCK）、region/platform/angle、时间。
- **[F7.3] Open** → 打开同款 `ResultDashboardView`。
- **[F7.4] Compare（勾选两条）** → `CompareViewModal`：参数差异 + 文案差异（headlines/primary_texts added/removed）+ 合规命中词差异。
- **[F7.5] Refresh Copy（SOP）** → 调用 `/api/quick-copy/refresh` 写回 history_log。

### 3.8 模块八：合规扫描 (Compliance) ✅

- **[F8.1] 规则层**（`backend/compliance.py` + `backend/data/compliance/risk_terms.json`）：
  - `build_ad_copy_tiles` / `scan_ad_copy` 返回 `{ risk_level: ok|warn|block, hits: [...] }`。
  - 覆盖 global / platform_overrides / region_overrides。
- **[F8.2] LLM 改写建议**（可选）：`compliance_suggest=true` 且 cloud 引擎可用 → `maybe_generate_rewrite_suggestions` 产出 `suggestions[]`。
- **[F8.3] 前端可视化**：结果页 badge + 点开查看 Hit 列表 + 改写建议（复制/应用）。

### 3.9 模块九：用量与成本治理 (Quota & Usage) ✅

> v1.0 原 PRD 未覆盖；运营落地必需能力。

- **[F9.1] 后端统计**（`backend/usage_tracker.py` + `usage_tokens.py`）：
  - Provider `usage.total_tokens` 优先；估算补齐；`script_generations_today / last_script_tokens / avg_tokens_per_script_today` + provider/estimate 样本拆分。
- **[F9.2] `GET /api/usage/summary`**：`budget / remaining / billing_quality`。
- **[F9.3] 前端 Quota 弹窗**（`MainLayout.tsx`）：侧边栏 Pro Plan 可 focus / pin，≈45s 客户端缓存。

### 3.10 模块十：Oracle 情报炼金 (RAG) ✅

- **[F10.1] `POST /api/refinery/ingest`**：URL / 文本归档（`refinery.distill_and_store`）。
- **[F10.2] `GET /api/refinery/stats`**：知识库规模。
- **[F10.3] `POST /api/refinery/recommend-strategy`**：基于 RAG 的策略推荐。
- **[F10.4] 检索证据**：`retrieve_context_with_evidence` 每条证据含 rule/source/year_quarter/match_score/reason_tag。

### 3.11 模块十一：脚本管理与导出 ✅

- **[F11.1] 在线编辑**：Lab 结果区支持 headlines 就地编辑（contentEditable onBlur 写回 `synthesisResult.ad_copy_matrix`）。
- **[F11.2] 多格式导出**：MD / XLSX / PDF（实际交付，替代 v1.0 原规划的 Word）。
- **[F11.3] 文件命名**（Phase 17）：`<LANG>_<Game>_<Region>_<Platform>_<Strategy>_<SOPID>.md`，优先使用因子 JSON 的 `short_name`。

---

## 4. 技术设计建议 (Technical Design)

### 4.1 技术栈现状
- **前端**：React 19 + Vite v8 + TypeScript + Tailwind v4（`@theme` + `@apply` 约束见 MEMORY_BANK）；动画 framer-motion；图标 lucide-react；i18n react-i18next。
- **后端**：Python + FastAPI + Pydantic；RAG 采用 `Scikit-Learn TF-IDF`（非 Chroma，Python 3.14 兼容性选择）；PDF 用 `fpdf2`。
- **LLM**：
  - 云端 DeepSeek（OpenAI 兼容），`DEEPSEEK_API_KEY` / `DEEPSEEK_BASE_URL` / `DEEPSEEK_MODEL` 控制；无二次 LLM 回退。
  - `DEEPSEEK_TIMEOUT_SECONDS` 统一管控 draft/director 单次调用超时，失败时显式 502（不做 mock 占位）。
- **知识层**：`backend/data/knowledge/factors/{regions,platforms,angles}/*.json` + `backend/data/knowledge/vector_store/local_storage.json`（`backend/knowledge_paths.py` 统一路径 + 历史目录迁移）。
- **产物**：`@OUT/{project_id}/{...}.md`（gitignored，通过 `/api/out/markdown` 读回展示）。

### 4.2 关键 API（v2.2 现状）
- `POST /api/extract-url` — Store URL → 双语导演档案
- `POST /api/generate` — Full SOP（`mode=auto|draft|director`）
- `POST /api/quick-copy` / `POST /api/quick-copy/refresh` — Copy Mode
- `POST /api/export/pdf` — PDF 导出
- `GET /api/out/markdown` — 读 @OUT Markdown
- `POST /api/out/open-folder` — 打开 @OUT 文件夹（localhost/ENV gated）
- `POST /api/refinery/ingest` / `GET /api/refinery/stats` / `POST /api/refinery/recommend-strategy`
- `GET /api/insights/metadata` / `POST /api/insights/manage/update` / `POST /api/insights/manage/delete`
- `GET /api/usage/summary`
- `GET/POST/PUT/DELETE /api/projects` (via `projects_api.py`)

---

## 5. UI/UX 设计要求

### 5.1 工作流引导
- 从“Stepper”演化为 **三页心智**：
  - **Dashboard**：项目总览 + 生成记录管理（资产库入口）。
  - **Lab**：配置 + 生成（三栏：Source / Mixing Console / Resonance Feed）。
  - **Result Dashboard**（覆盖层）：Markdown + Copy Hub + 合规详情。
- 所有 Modal/Drawer 遵守：body scroll lock、Esc 关闭、点击遮罩关闭、统一遮罩强度。

### 5.2 信息层级（Atomic Design）
- **Level-0** 页面任务（Generate / Open Result / Export）
- **Level-1** 关键参数（region / platform / angle / output）
- **Level-2** 解释性文本（rules / notes）
- Badge（OK / WARN / BLOCK）与按钮系统（`btn-director-*`）共用视觉语义。

### 5.3 交互稳定性（新增）
- 统一 `scrollbar-gutter: stable` 避免展开/加载抖动。
- 折叠控件隐藏默认 marker（`list-none [&::-webkit-details-marker]:hidden`）。

### 5.4 深色模式
- `html.dark` 根类切换，`ThemeAppearanceControl` 持久化 `adcreative-theme` (`light | dark | system`)。

### 5.5 i18n
- 中/英双语覆盖 Lab / Dashboard / Result Dashboard / Compare；新增 UI 文案必须走 `t()`。

---

## 6. 非功能性需求

- **生成速度**：SOP ≈ 15–20s（`auto` 模式草案+导演串联），Quick Copy ≈ 5–10s（单 locale）。
- **准确性**：
  - Prompt 硬约束不能捏造机制；Gene Grafting 协议约束 RAG 上下文不覆盖项目 DNA。
  - 本地生成失败以结构化 502 返回（`error_code / error_message / raw_excerpt`），前端不伪造 mock。
- **安全性**：
  - `@OUT` 路径严格校验（`os.path.commonpath`），阻断目录穿越。
  - 打开本机文件夹仅放行 localhost 或 `ALLOW_OUT_OPEN_FOLDER=1`。
  - API 无认证（单机工具）；如走 SaaS 化需在前置引入鉴权/租户隔离。
- **可观测性**：`/api/usage/summary` 提供每日预算/剩余/估算-provider 拆分；generation_metrics 提供 `elapsed_ms / mode / rag_rules_used`。
- **Windows 特例**：打印/uvicorn 输出走 `_print_console_safe`，避免 GBK 编码崩溃。

---

## 7. 衡量成功的指标 (KPIs)

- **效率提升**：单脚本耗时从人工 1h 降到 15–20s 级别。
- **采纳率**：每个 history_log 条目后续发生的 Refresh / Compare / Export 比例。
- **疲劳对抗**：单 SOP 平均 Refresh 次数、Refresh 后新 headline 覆盖率。
- **合规质量**：BLOCK 比例 < 2%，WARN 比例可控（与 risk_terms 更新相关）。
- **成本治理**：平均单脚本 token / 日预算命中率 / provider-vs-estimate 比例。

---

## 8. 路线图 (Roadmap)

### ✅ 已交付（v1.0 → v2.3）
- F1/F2/F3 基础；多地区 × 多平台 × 多 Angle；多语种 transcreation；RAG 证据；CN/EN 双输出；Quick Copy；Refresh；Compare；合规扫描（规则 + LLM 建议）；XLSX/MD/PDF 导出；用量监控；结果页组件化复用；Dashboard 记录管理。
- **Phase 22 闭环学习**：history_log schema v2（`parent_script_id / factor_version / rag_rule_ids / draft_status / lang / decision`）；`POST /api/history/decision` Winner/Loser 决策回流；合规命中词自动反哺 Director/Copy prompt 的负向词列表；修复 quick_copy/refresh_copy 的 history 丢写隐蔽 bug。

### 🧭 计划中
- **Apple App Store 抓取** 与 Google Play 对齐（同 JSON contract）。
- **云端 extract** 与本地 extract 契约完全一致（目前云端为规则抽取）。
- **multi-locale 并发结果并排**（当前 Quick Copy 已支持 region_ids 合并，结果页仍按 locale 卡片；“Side-by-side diff across locales” 待做）。
- **合规规则在线可维护**：risk_terms 的前端管理 UI + 版本化。
- **History schema v2**：补齐 `parent_script_id`（Refresh 源）、`tags` 与 `cost`，为 KPI 看板准备。

### ⏸ 延后/降优先
- **AI 配音预览（ElevenLabs）** — v1.0 v2.0 愿景，延至 MVP 稳定后评估。
- **DALL-E/Midjourney 视觉草图** — 同上。
- **Word 导出** — 已被 MD/XLSX 取代，除非明确运营需求。
- **真身多租户 + 鉴权** — 当前是单机中控台；SaaS 化需单独立项。

---

## 9. 全球本地化引擎（保留 + 现状对齐）

### 9.1 核心地区买量风格画像
- 保留 v1.0 四大区画像（T1 / Japan / SEA / MEA），实现上落到 `backend/data/knowledge/factors/regions/*.json` 可维护，前端三栏 Resonance Feed 实时展示命中 rule。

### 9.2 语言适配模块
- **Transcreation**：`render_copy_prompt` 明确要求非机翻，含 locale 约束。
- **RTL**：Lab/Result 在 Middle East 区上允许 `dir="rtl"` 的脚本节点渲染（Phase 早期已实现）。
- **字体自动匹配** / **德语缩放** 为 🧭：当前依赖下游剪辑实现，PRD 仍保留方向。

### 9.3 竞品分析模块
- RAG `recommend-strategy` 接口已就位，配合 Oracle Ingestion 面板可归档情报；“差异化建议”的叙事 UI 为 🧭。

---

## 10. 愿景 vs 当前实现 差异矩阵（新增）

| 领域 | PRD v1.0 愿景 | v2.2 当前实现 | 差异 / 延后 |
|---|---|---|---|
| 输入 | URL 抓取 + 文本 | Google Play + 双语档案 + 本地/云端双路径 | Apple Store 🧭 |
| Angle | 至少 5 种 | 8+（`angles/*.json`，如 asmr/dev_leak/drama/fail_trap/national_pride/progression/rescue/whale_flex） | 已超出 |
| 评分 | Hook/Clarity/Conversion | 同上 + `review` 规则审校 + `rag_evidence` | 已超出 |
| 竞品 | 提示对标素材 | RAG 证据 + `recommend-strategy` | UI 层“差异化建议”叙事 🧭 |
| 导出 | PDF / Excel / Word | MD / XLSX / PDF + @OUT 文件夹 | Word ⏸；加入 @OUT 目录管理 |
| 多语种 | 一键翻译 | 真正 transcreation（`locales[]` + tones） | 已超出 |
| 工作流 | 单次生成 | 生成→复用→刷新→对比→导出（history_log 驱动） | 显著超出 v1.0 |
| 合规 | 未覆盖 | 规则 + LLM suggestion（Phase 21） | v2.2 新增能力 |
| 成本 | 未覆盖 | `/api/usage/summary` + Quota UI | v2.2 新增能力 |
| AI 配音 | v2.0 目标 | 未实现 | ⏸ |
| AI 视觉草图 | v2.0 目标 | 未实现 | ⏸ |

---

## 11. 开放问题 / 待决策

- **SaaS 化门槛**：当前鉴权/多租户缺失，若要对外开放，需要先补 `project_id` 归属校验与 Token 隔离。
- **History log 体积**：`history_log[]` 目前无分页/软删；项目长期使用后需要压缩/归档策略。
- **Compliance 规则治理**：`risk_terms.json` 的增删目前是代码改动；建议尽快补一个只读可视化 + PR 流。
- **Compare 维度**：当前覆盖参数/文案/合规；分镜级 diff（shot-by-shot）为 🧭。

---

## 12. 变更历史

- **v2.7（2026-04-17）**：Phase 26·E "存储底座升级" 收口。目标：把 `backend/data` 下 projects / history / factors / compliance / knowledge 全部迁进 SQLite 做运行期读写层，并把 RAG 升级为混合检索 + 可选重排，直接强化分镜脚本与文案素材的内容质量。三项核心能力：
  1. **SQLite 运行期读写层**：`backend/db.py` 统一连接工厂（WAL、FK、Row factory）+ 幂等 migrations；六张表 `projects / history_log / factors / compliance_rules / knowledge_docs / knowledge_vectors` + FTS5 虚拟表 `knowledge_fts`。`DB_PATH` 默认 `backend/data/app.sqlite3`。git 受控的 JSON（factors / `local_storage.json` / `risk_terms.json`）仍作为 seed，启动时按 SHA1 fingerprint 幂等 upsert 进 DB；Projects 以 DB 为唯一真源，老 `workspaces/*.json` 作为一次性导入兜底。
  2. **Projects / History / Factors / Compliance 统一入口**：`projects_api.py` 全量走 DB（`load / save / append_history_entry / update_history_decision`），对外 API schema 与 Phase 25 兼容（前端零改动）；`_record_history` 改为 `INSERT INTO history_log`（`schema_version=3`）。`factors_store` / `compliance_store` 替换 `main.py` 7 处 `base_dir` + 内嵌 `read_insight` 闭包；compliance 缓存新增 `invalidate_cache()`。
  3. **混合检索 RAG（BM25+Vector+RRF+MMR+可选 Rerank）**：`refinery.KnowledgeStore` 接管 `knowledge_docs / knowledge_fts / knowledge_vectors`；`QueryExpander` 基于 angle 的 `logic_steps / psychological_triggers / commercial_bridge / regional_adaptations[region]` 对 query 做扩展；FTS5 BM25 + sentence-transformers 向量（TF-IDF 兜底）→ RRF(k=60) → Region Boost → MMR(λ=0.7) → 可选 `sentence-transformers/CrossEncoder` 重排；`retrieve_context_with_evidence` 按 `reason_tag`（hook / format / editing / psychology / general）分组，evidence 加 `reason_tag` 字段，向量缺失时自动降级。新 route `GET /api/knowledge/stats` + `POST /api/knowledge/reindex`；Oracle Ingestion 页新增 Backend / FTS5 / Rerank / vectors 状态胶囊 + Reindex 按钮。
  - **环境变量**：`DB_PATH` / `RAG_RETRIEVAL`(`hybrid|bm25|vector|tfidf`) / `RAG_EMBEDDING_MODEL` / `RAG_TOPN` / `RAG_RRF_K` / `RAG_MMR_LAMBDA` / `RAG_RERANK`(`on|off`) / `RAG_RERANK_MODEL`。
  - **测试**：`pytest -q` → **121 passed**（Phase 25 baseline 109 + 12 新：`test_db_migrations` 3 / `test_factors_store` 2 / `test_compliance_store` 2 / `test_knowledge_hybrid` 5；`test_phase22 / test_partial_failure / test_compliance_admin / test_providers_api` 的 `_write_workspace` 同步 DB+JSON 双写，`_load_workspace` DB 优先读）；`npm run build` OK。
- **v2.6（2026-04-17）**：Phase 25 "多模型入口" 收口。三项核心能力（仅云端 OpenAI 兼容协议）：
  1. **Provider Registry**：`backend/providers.py` 统一管理 5 个 provider（`deepseek` / `siliconflow` / `bailian` / `openrouter` / `zen`-deferred），封装 base URL、default model、JSON-mode 支持、价格 env 开关与 model_choices；`.env.example` 新增五段云端厂商配置模板。`get_client` 带缓存，`list_providers` 对外零密钥泄漏。
  2. **Per-call 路由 + history schema v3**：所有 LLM 入口（generate / quick_copy / refresh_copy / retry_region / extract_url）新增 `engine_provider` / `engine_model`；`resolve_llm_client` 实现 "provider key → legacy cloud_client → None skip" 三级回落；`usage_tracker` 加 `by_provider[pid] = {tokens, calls}` 维度；history_log `schema_version = 3`，写入 `provider` / `model`，用于后续成本归因与 A/B 对比。
  3. **Engine Selector UI**：Lab 新增 Engine 卡片（provider 下拉 + model 下拉 + `READY/FALLBACK` 徽章），选择 localStorage 持久化；`/api/providers` 新 route 驱动 UI；Cost Estimator 按 provider 单价实时重算；Dashboard 历史条目增加 `provider · model` 胶囊徽章（老条目优雅降级）。
  - **测试**：`pytest -q` → 109 passed（新增 test_providers 14 + test_providers_api 6）；`npm run build` OK。
- **v2.5（2026-04-17）**：Phase 24 "资产化" 收口。四项核心能力：
  1. **Localization Matrix 视图**：Result Dashboard 新增 Cards ↔ Matrix 切换；Matrix 按 kind（headlines / primary_texts / hashtags）分 tab 展示 locale × slot 矩阵，支持关键词搜索、就地编辑（回流到 `result.ad_copy_matrix`）、BOM 前缀 CSV 导出。
  2. **Dashboard 历史搜索面板**：关键词 + region/platform/angle/kind 下拉 + decision 过滤 + 时间区间；localStorage 持久化；三态空视图（无历史 / 无匹配 / 正常）。
  3. **Compliance 只读管理页**：新增 `/api/compliance/rules` 与 `/api/compliance/stats` + 前端 `/compliance` 路由；展示全局/平台/地区规则树、跨项目命中排行榜、avoid_terms 预览、rules_path。
  4. **Delivery Pack**：`POST /api/export/delivery-pack` 打 zip（README.md + script.md + ad_copy.csv + payload.json），前端 Result Dashboard 一键下载；`delivery_{project}_{script_id}.zip`。
  - **测试**：`pytest -q` 89 passed（新增 test_compliance_admin 2 + test_delivery_pack 3）；`npm run build` OK。
- **v2.4（2026-04-17）**：Phase 23 "可靠生产" 收口。新增四大能力：
  1. **Prompt Injection Sanitize**：`backend/sanitize.py` 中枢化，所有进入 LLM 的用户输入都经过零宽/控制字符剥离、注入模板 defuse、`<<<USER_INPUT>>>` 分隔符包裹；`prompts.py` 系统段前置 `INJECTION_GUARD` 明确告知 LLM 分隔符内为 data。
  2. **Pre-flight 成本预估**：`backend/cost_estimator.py` + `POST /api/estimate`，支持 generate_full / draft / quick_copy / refresh_copy 四类作业；Lab 前端吸附条实时显示 Tokens / CNY / 当日剩余预算，按 `near / over` 分级告警并要求二次确认超预算生成。
  3. **Queue & Presets（客户端）**：`useLabQueue` Hook 提供最多 10 条 Presets（pin/rename/delete）+ 串行 Queue 调度；`localStorage` 持久化；EMA 估算的 ETA；一键回填结果页；对后端无侵入。
  4. **quick_copy 部分失败协议**：多 region 生成每个 region 独立 try/except，写入 `regions_status` / `regions_error`；响应新增 `partial_failure` 字段；`POST /api/quick-copy/retry-region` 支持单 region 重试并合并回 history；ResultDashboard 展示失败横幅 + 区域徽章 + 重试按钮。
  - **测试**：`pytest -q` 84 passed（新增 test_sanitize 17 + test_cost_estimator 10 + test_partial_failure 4），`npm run build` OK。
- **v2.3（2026-04-17）**：Phase 22 "闭环学习" 收口。history schema v2 + compliance 负向词反哺 + Winner/Loser 决策回流 + `_record_history` 关键 Bug 修复。
- **v2.2（2026-04-16）**：对齐 Phase 1–21 实现；补全 Workspace / Quick Copy / Refresh / Compare / Compliance / Quota / Oracle RAG / @OUT / 多语种 transcreation 等模块；显式“愿景 vs 实现”差异矩阵。
- **v1.0**：初版，奠定 Input → Generate → Predict → Export 骨架与全球本地化引擎愿景。
