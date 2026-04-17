# 业务流审查 (Business Flow Audit) — v2.2

**审查日期**：2026-04-16
**审查对象**：已实现能力（对应 `docs/PRD.md` v2.2 与 `docs/MEMORY_BANK.md` Phase 1–21）
**审查口径**：端到端业务流视角 —— 从用户目标出发，逐环节检查“触发 → 数据 → 副作用 → 失败路径 → 下一步”的完整性。

> 本文档面向产品/工程联合评审。每条流给出：**步骤拆解 / 数据依赖 / 关键风险 / 改进建议**。
> 结论汇总见 §9“综合体检结论”。

---

## 1. 流 A：项目初始化（Project Onboarding）

**用户目标**：从零开始，为一个新游戏建档。

### 步骤
1. Dashboard → `New Project` → `ProjectSetupModal`
2. 输入 `title / core_gameplay / usp / target_persona / value_hooks`
3. 可选：贴 Google Play URL → `POST /api/extract-url` 回填字段
4. `POST /api/projects` 持久化到 `backend/data/workspaces/{id}.json`
5. `setCurrentProject` 写入 Context + `localStorage` 缓存

### 数据依赖
- 前端：`ProjectContext.tsx`（init 阶段并发获取 projects + 从 cache 恢复 currentProject）
- 后端：`projects_api.py` + `workspaces/` 目录可写

### 关键风险
- **R-A1（中）** `extract-url` 在云端调用失败或未配置 `DEEPSEEK_API_KEY` 时静默降级为**规则抽取**，字段质量低于 LLM 输出；用户可能误以为 AI 已生成。
- **R-A2（低）** `value_hooks` 未做唯一性/长度校验；过长会影响后续 prompt token 消耗。
- **R-A3（低）** Apple App Store 未支持，v2.2 路线图明确但当前缺失。

### 改进建议
- Extract 响应增加 `source: llm|rule` 字段，前端显式提示“规则抽取 / 建议手工校对”。
- `value_hooks` 增加前端 maxLength + 计数器。
- 接入 Apple Store（同 JSON contract，复用 `EXTRACT_USP_VIA_LLM_SYSTEM_PROMPT`）。

---

## 2. 流 B：Full SOP 生成（Director Flow）

**用户目标**：为当前项目产出一条可交付剪辑的完整分镜 + 文案矩阵。

### 步骤
1. Lab → 配置 `region / platform / angle / output_type=Full SOP / output_mode(cn|en) / gen_mode(auto|draft|director)`
2. `POST /api/generate` ↓
   - `_run_draft_stage`（可选）→ `drafts.hooks[] + pick_recommendation`
   - `_run_director_stage` → 分镜脚本 + `ad_copy_matrix`
3. `finalize_response` 注入：
   - `generation_metrics.elapsed_ms / mode / rag_rules_used`
   - `ad_copy_tiles`（扁平化）
   - `compliance.risk_level + hits`（可选 `suggestions`）
4. `_write_markdown_snapshot` → `@OUT/{project_id}/{LANG}_{Game}_{Region}_{Platform}_{Strategy}_{SOPID}.md`
5. `record_history` → history_log 追加条目
6. 前端 `synthesisResult` 更新 → 用户点 `Open Result` 打开 `ResultDashboardView`

### 数据依赖
- `data/knowledge/factors/{regions,platforms,angles}/*.json`
- `data/knowledge/vector_store/local_storage.json`（RAG）
- `@OUT/` 目录可写
- LLM 连通性（云端 DeepSeek）

### 关键风险
- **R-B1（高）** **静默 `draft` 失败降级为 `director`** 时，用户不知道草案失效 → 影响审计与分析。
  - 位置：`_run_draft_stage` 捕获 Exception 后仅 warn。
- **R-B2（中）** `generation_metrics.rag_rules_used` 目前仅统计数量，未回写“具体命中哪几条 rule”到 history，Compare 时无法对比 RAG 粒度差异。
- **R-B3（中）** `@OUT` 落盘失败不会阻断返回（catch all），但 history 里的 `markdown_path` 仍写入，用户点击下载会 404。
- **R-B4（低）** 中文 ↔ 英文切换 `output_mode` 时，文件名包含 `LANG_`，但 history 列表 UI 不显示 lang，Dashboard 右侧记录上**视觉上无法区分**同参数 CN/EN 两条。

### 改进建议
- Response 增加 `draft_status: ok|fallback|skipped` 并在结果页显示小 badge。
- history_log 存 `rag_rule_ids[]`；Compare 视图加 “RAG diff” 维度。
- `_write_markdown_snapshot` 失败时返回 `markdown_path=None`，前端严格依据此字段渲染下载按钮。
- history 列表行中，在 output_kind badge 旁补 `CN|EN` 小标签。

---

## 3. 流 C：Quick Copy 多地区生成

**用户目标**：不要分镜，只要一把批量 headlines/primary_texts/hashtags，且跨 region 一次出全。

### 步骤
1. Lab → `output_type=Quick Copy` → 选 `region_ids[]`（1..n）+ `locales[]` + `tones[]` + `quantity`
2. `POST /api/quick-copy`
3. 后端循环 region：分别加载 factor、执行 `render_copy_prompt` → LLM → 解析 JSON
4. 合并：`ad_copy_matrix.variants` 键统一为 `"{region_id}:{locale}"`；`ad_copy_tiles` / `compliance` 聚合
5. `record_history(output_kind="copy")`
6. Result Dashboard 的 Copy Hub 按 locale 分组渲染

### 数据依赖
- 与流 B 相同，但 **不访问 RAG / director prompts**（理论上更快）

### 关键风险
- **R-C1（高）** **无部分失败语义**：循环里任何一个 region 抛错会影响整体返回；当前实现 try/except 仅对单 region LLM 失败 fallthrough，但合并层没有标注“哪个 region 失败”。
- **R-C2（中）** `variants` key `"{region}:{locale}"` 前端按 locale 分组展示时，**region 信息被“扁平化”丢失**（UI 只看 locale）。多 region 模式下用户无法一眼区分 US×en 与 SEA×en 的差异。
- **R-C3（中）** Quick Copy 未写 `markdown_path`（只有 XLSX 导出），但 history 的 `output_kind=copy` 条目在 Dashboard 上点 `Open` 走 `ResultDashboardView`，而该组件默认会尝试 fetch markdown → 触发 404/空态。
- **R-C4（低）** `quantity` 与 `primary_texts>=5 / headlines>=10 / hashtags>=20` 下限的耦合未在 prompt 层显式校验，可能少于预期数量。

### 改进建议
- 返回体增加 `per_region_status[]` 或 `errors[]`；结果页 WARN 区显示“Region X 失败”。
- 前端 Copy Hub 多 region 模式增加二级分组（Region → Locale）；当只有一个 region 时兼容当前扁平布局。
- `ResultDashboardView` 根据 `result.output_kind` 跳过 Markdown fetch 或展示“仅文案”空态。
- `render_copy_prompt` 显式 assert 最小数量；解析后后端做补齐/降级。

---

## 4. 流 D：Refresh Copy（素材复用）

**用户目标**：同一条分镜想再出一轮新文案对抗疲劳。

### 步骤
1. Dashboard 记录面板 → 选一条 `output_kind=sop` → `Refresh`
2. `POST /api/quick-copy/refresh` 带 `project_id + source_script_id + compliance_suggest`
3. 后端用原 recipe 填 Quick Copy 流程，`record_history(output_kind="copy")`
4. `refreshProjects()` 重新加载项目，列表顶出现新条目

### 数据依赖
- history_log 存在 `id` 与 `recipe` 字段

### 关键风险
- **R-D1（高）** **没有 `parent_script_id` 字段**：新生成的 copy 条目与源 SOP 条目在 history 上没有**反向指针**；未来做“源素材 × 文案轮次”分析将缺原始关系。
- **R-D2（中）** 若源 SOP 是 3 个月前旧 recipe（factor JSON 已更新），Refresh 仍旧复用旧 recipe，可能与当前 factor 冲突（例如某平台新加的合规约束）。
- **R-D3（低）** Dashboard 上未显示“某条 SOP 已被 Refresh 过 N 次” → 运营无法快速找到“最活跃的素材”。

### 改进建议
- history_log schema 增加 `parent_script_id: string?`；Refresh 时写入源 SOP id。
- Refresh 前拉取最新 factor JSON 与源 recipe `diff`，若差异显著给 UI warning “因子已更新，建议重跑 Full SOP”。
- 面板计算 `children_count` 并在行尾显示 `Refreshed ×N`。

---

## 5. 流 E：Compare 两条记录

**用户目标**：A/B 对比两条生成结果的关键差异，为下一版决策提供依据。

### 步骤
1. Dashboard → 勾两条 → `Compare picked` → `CompareViewModal`
2. 展示：参数差异（recipe）/ Headlines diff（added in B / removed from A）/ Primary texts diff / Compliance hit terms diff

### 关键风险
- **R-E1（中）** 仅 set diff，**未做语义聚合**（例如 "Free Gift" vs "Free Rewards" 被判为两条独立项）。
- **R-E2（中）** 两条记录 `output_kind` 不一致（一条 SOP、一条 Copy）时，Compare 仍展示但缺少 “分镜层 diff”。
- **R-E3（低）** Compare 结果无法导出，审稿会议上要手抄。

### 改进建议
- 增加 “Normalized diff” 选项（lowercased + 去 emoji + trim 后做 set diff）。
- 对 `output_kind` 不一致的组合，禁用或显示“仅文案维度可比”提示。
- 提供 Compare → MD 导出 / 截图入库功能（辅助评审）。

---

## 6. 流 F：Result Dashboard 审阅与导出

**用户目标**：打开一次结果，做复制 / 下载 / 打开 @OUT / 导出 PDF、XLSX。

### 步骤
1. 入口：Lab `Open Result` 或 Dashboard 记录 `Open`
2. `ResultDashboardView`：
   - Markdown 区 → `GET /api/out/markdown?path=...`
   - Copy Hub → 本地渲染
   - 合规区 → 本地渲染（可选 LLM suggestion）
3. 导出动作：
   - Markdown：前端直接 Blob 下载
   - XLSX：`xlsx` 包前端生成
   - PDF：`POST /api/export/pdf`
   - Open folder：`POST /api/out/open-folder`（localhost/ENV 放行）

### 关键风险
- **R-F1（高）** **Open Folder 只对 Windows 有效**（`os.startfile`）；macOS/Linux 无适配。
- **R-F2（中）** Markdown fetch 使用 `path` query，尽管 `_resolve_out_path` 有 `commonpath` 校验，但 **未校验文件扩展名**（当前只读取 `.md`），如有扩展字段可能混入。建议 MIME/扩展白名单。
- **R-F3（中）** Quick Copy 记录进入该页时，默认会尝试 fetch markdown（即便无 `markdown_path`），导致一次 404。
- **R-F4（低）** PDF 导出依赖 `script` 字段；对 `output_kind=copy` 无效，但前端未隐藏该按钮。

### 改进建议
- `/api/out/open-folder` 增加跨平台分支（`subprocess.run(['open', path])` / `['xdg-open', path]`）并在 UI 上只对支持平台显示。
- `out_markdown` 校验扩展名白名单 + size cap。
- `ResultDashboardView` 根据 `output_kind` 条件渲染 Markdown 区 / PDF 按钮。
- 导出操作失败做 toast 反馈（目前静默居多）。

---

## 7. 流 G：合规扫描与 LLM 改写

**用户目标**：避免文案触碰平台/地区违禁词；拿到可直接替换的改写建议。

### 步骤
1. `finalize_response` / `quick_copy` 内调用 `scan_ad_copy(tiles, platform, region)`
2. 若 `compliance_suggest=true` 且云端 client 可用 → `maybe_generate_rewrite_suggestions`
3. 前端：Copy Hub 高亮 risky tile + 合规 Modal 展示 hits/suggestions

### 数据依赖
- `backend/data/compliance/risk_terms.json`

### 关键风险
- **R-G1（高）** `risk_terms.json` 是**代码级工件**，非运营可维护；任何新增违禁词都要发版。
- **R-G2（中）** LLM rewrite 未做 replay 合规二次扫描——**建议改写文本本身可能仍然 WARN**。
- **R-G3（低）** 规则匹配为 case-insensitive substring，**无词边界**（例如规则 `ad` 会误命中 `advance`）。

### 改进建议
- 构建 `/api/compliance/rules` CRUD 与前端 Admin Panel（只读 + 版本化开始）。
- 生成 suggestion 后自动再次 `scan_ad_copy`，输出 `suggestion.risk_level`。
- 规则结构升级为 `{term, type: substring|word|regex}`；默认词边界。

---

## 8. 流 H：用量 & 预算治理

**用户目标**：随时知道当天用了多少 token、还剩多少，防止月末爆预算。

### 步骤
1. `MainLayout.tsx` 定时/按需 `GET /api/usage/summary`（≈45s 客户端缓存）
2. 后端 `usage_tracker` / `usage_tokens` 聚合 provider + estimate
3. 侧边栏 Pro Plan 卡 + Focus Modal 展示

### 关键风险
- **R-H1（中）** `billing_quality` 指标语义对非开发者不直观（provider/estimate 拆分），UI 解释不足。
- **R-H2（低）** 无 webhook / 报警：超 80% 预算时没有前端 toast 或后端阻断。
- **R-H3（低）** `usage_counters.json` 有进仓库风险（git status 已见未 ignore）。

### 改进建议
- UI 增加 hover tooltip：“provider=真实账单；estimate=本地估算（LLM 未返回 usage）”。
- 阈值告警（80% / 100%），100% 时可选软阻断（按钮置灰 + 提示）。
- 将 `backend/usage_counters.json` 加入 `.gitignore`。

---

## 9. 综合体检结论

### 9.1 总体评估
已实现工作流在 **单项目 / 单机使用** 下闭环完整：Onboard → Generate → Review → Archive → Refresh/Compare → Export。
核心卖点（多地区 transcreation、Oracle RAG 证据、合规扫描、用量监控）均已超出 v1.0 PRD。

### 9.2 关键待办（按优先级）

> 进度更新（2026-04-17，Phase 26·E）：**E 主线"存储底座升级"完成**。`backend/data` 下 projects / history_log / factors / compliance_rules / knowledge_docs / knowledge_vectors 全部迁进 SQLite（`backend/db.py` 统一连接工厂 + 幂等 migrations + FTS5），JSON（factors / `local_storage.json` / `risk_terms.json`）保留作为 git 受控 seed 并按 SHA1 fingerprint 幂等 upsert。RAG 升级为 **BM25(FTS5) + Vector + RRF(k=60) + Region Boost + MMR(λ=0.7) + 可选 Cross-Encoder 重排**，并加 `QueryExpander` 基于 angle/region 策略因子扩展 query；新增 `GET /api/knowledge/stats` + `POST /api/knowledge/reindex`，Oracle Ingestion 前端页加 Backend / FTS5 / Rerank / vectors 胶囊 + Reindex 按钮。`pytest -q` **121/121**（109 baseline + 12 新），`npm run build` 绿。
> 进度更新（2026-04-17，Phase 25）：**D 主线"多模型入口"完成**（Provider Registry / Per-call 路由 / Engine Selector UI，覆盖 DeepSeek / SiliconFlow / 阿里云百炼 / OpenRouter，ZEN 先作占位）。Phase 24 完成 C 主线"资产化"：Localization Matrix 视图、Dashboard 历史搜索、Compliance 只读管理页、Delivery Pack zip 导出。Phase 23 完成 B 主线四件套（注入清洗 + 成本预估 + 队列/预设 + 部分失败协议）。Phase 22 完成 R-B1 / R-D1 + 合规反哺 + Decision(Winner/Loser)。`pytest -q` **109/109**，`npm run build` 绿。

| 优先级 | ID | 标题 | 涉及流 | 状态 |
|---|---|---|---|---|
| P0 | R-B1 | draft→director 降级需在 UI 显式标注 | 流 B | ✅ 已实现（history 写 `draft_status`，Dashboard 显示 `draft→fallback` badge） |
| P0 | R-C1 | Quick Copy 多地区部分失败需可见性 | 流 C | ✅ 已实现（Phase 23/B4；`regions_status` + 部分失败横幅 + `/api/quick-copy/retry-region`） |
| P0 | R-X1 | Prompt Injection 防护 | 全流 | ✅ 已实现（Phase 23/B1；`backend/sanitize.py` + `INJECTION_GUARD` + `USER_INPUT` 分隔符） |
| P0 | R-X2 | LLM 成本预估与预算告警 | 流 B/C/D | ✅ 已实现（Phase 23/B2；`/api/estimate` + Lab 吸附条 + 橙/红分级） |
| P1 | R-X3 | 参数 Presets + 批量队列 | 流 B/C | ✅ 已实现（Phase 23/B3；`useLabQueue` + Presets 抽屉 + Queue 串行调度 + ETA） |
| P0 | R-G1 | risk_terms 运营可维护（只读 + 版本化） | 流 G | ✅ 已实现（Phase 24/C3；`/api/compliance/rules` + `/api/compliance/stats` + `/compliance` 前端页） |
| P1 | R-C3 / R-F3 | Result Dashboard 对 `output_kind=copy` 自适应 | 流 C/F | ✅ 已实现（Phase 24/C1；Localization Matrix 视图 + 就地编辑 + CSV 导出） |
| P1 | R-X4 | 历史列表缺少搜索/过滤 | 流 B/C/D | ✅ 已实现（Phase 24/C2；Dashboard 搜索面板 + 筛选持久化） |
| P1 | R-X5 | 对外交付缺少标准化打包 | 流 F | ✅ 已实现（Phase 24/C4；`/api/export/delivery-pack` 打 zip） |
| P0 | R-D1 | history_log 补 `parent_script_id` | 流 D | ✅ 已实现（`refresh_copy` 写入 `parent_script_id`，UI 显示 `Refresh of <id>`） |
| P0 | R-G1 | risk_terms 运营可维护（至少只读 + 版本化） | 流 G | 🧭 待做 |
| P1 | R-F1 | Open Folder 跨平台 | 流 F |
| P1 | R-C3 / R-F3 | Result Dashboard 对 `output_kind=copy` 自适应 | 流 C/F |
| P1 | R-B3 | `markdown_path` 失败兜底 | 流 B |
| P1 | R-G2 | rewrite 建议再扫描 | 流 G |
| P2 | R-A1 | extract source (llm/rule) 显式标注 | 流 A |
| P2 | R-E1 | Compare normalized diff | 流 E |
| P2 | R-H1 | billing_quality UI 解释 | 流 H |
| P2 | R-B4 | history 行显示 CN/EN | 流 B |
| P3 | R-H3 | usage_counters.json gitignore | 流 H |

### 9.3 架构层建议
1. **History schema v2**：补齐 `parent_script_id / rag_rule_ids / draft_status / output_kind / lang`，为 KPI 看板铺路。
2. **跨平台外壳**：打开文件夹、`@OUT` 路径展示需脱离 Windows 硬假设。
3. **规则层运营化**：risk_terms / factors JSON 都应具备可视化管理（因子管理已在 `/api/insights/manage/*`，合规差一层）。
4. **部分失败协议**：所有循环型 endpoint（Quick Copy 多地区）采用 `status=partial` + `errors[]` 语义。
5. **可观测性**：`generation_metrics` 下沉至 history 并在 Dashboard 做看板（单脚本 token、平均耗时、WARN 比例）。

### 9.4 下一步推荐迭代主题
- **Phase 22（已完成）**：History v2 & 合规反哺 & Winner/Loser 决策回流。
- **Phase 23（已完成）**：可靠生产四件套 — Injection sanitize / 成本预估 / Queue & Presets / quick_copy 部分失败协议。
- **Phase 24（已完成）**：资产化 — Localization Matrix + 历史搜索 + Compliance 只读管理 + Delivery Pack。
- **Phase 25（已完成）：多模型入口 — DeepSeek / SiliconFlow / 阿里云百炼 / OpenRouter / ZEN(deferred)**
  - `providers.py` Registry（各家 OpenAI 兼容 Base URL + supports_json_mode + 价格 env）
  - per-call 路由：`engine_provider / engine_model` 透传到 5 处 LLM 入口
  - 前端 Engine Selector 二级下拉（provider → model）+ READY/FALLBACK 徽章
  - Cost Estimator 按 provider 单价重算，usage_tracker 加 by_provider 维度
  - history_log schema v3（provider / model 字段），Dashboard 胶囊徽章展示
- **Phase 26·E（已完成）：存储底座升级 — SQLite 运行期读写层 + 混合检索 RAG**
  - `backend/db.py`：统一连接工厂（WAL / FK / Row factory）+ 幂等 migrations；六张表 `projects / history_log / factors / compliance_rules / knowledge_docs / knowledge_vectors` + FTS5 `knowledge_fts`
  - `factors_store` / `compliance_store` / `projects_api` 重写，`main.py` 7 处 `base_dir` + `read_insight` 闭包全部替换；JSON 仍作为 git 受控 seed，按 SHA1 fingerprint 幂等 upsert
  - `projects_api` DB-first（`load / save / append_history_entry / update_history_decision`），`_record_history` 改为 `INSERT INTO history_log`（schema_version=3）；首次启动从 `workspaces/*.json` 一次性导入
  - `refinery.KnowledgeStore` + `QueryExpander`：FTS5 BM25 + sentence-transformers 向量（TF-IDF 兜底） → RRF(k=60) → Region Boost → MMR(λ=0.7) → 可选 `CrossEncoder` 重排；`retrieve_context_with_evidence` 按 reason_tag 分组
  - 新 route：`GET /api/knowledge/stats` / `POST /api/knowledge/reindex`；前端 Oracle Ingestion 加 Backend / FTS5 / Rerank / vectors 胶囊 + Reindex 按钮 + zh/en i18n
  - 环境变量：`DB_PATH` / `RAG_RETRIEVAL` / `RAG_EMBEDDING_MODEL` / `RAG_TOPN` / `RAG_RRF_K` / `RAG_MMR_LAMBDA` / `RAG_RERANK` / `RAG_RERANK_MODEL`
  - 测试：`pytest -q` **121 passed**（新增 `test_db_migrations` 3 + `test_factors_store` 2 + `test_compliance_store` 2 + `test_knowledge_hybrid` 5）；`npm run build` 无错

---

## 10. 附录：流与代码入口映射

| 流 | 前端入口 | 后端入口 | 产物 |
|---|---|---|---|
| A | `Dashboard.tsx` + `ProjectSetupModal` | `projects_api.py` / `/api/extract-url` | `workspaces/{id}.json` |
| B | `Lab.tsx` | `main.py:generate_script` + `prompts.render_director_prompt` | `@OUT/*.md` + history_log |
| C | `Lab.tsx` | `main.py:quick_copy` + `prompts.render_copy_prompt` | history_log (copy) |
| D | `Dashboard.tsx:runRefreshCopy` | `main.py:refresh_copy` | history_log (copy) |
| E | `Dashboard.tsx` + `CompareViewModal.tsx` | — （前端纯本地 diff） | — |
| F | `ResultDashboardView.tsx` | `/api/out/markdown`, `/api/out/open-folder`, `/api/export/pdf` | 本地文件 |
| G | `ResultDashboardView.tsx` 合规 Modal | `compliance.py` + `risk_terms.json` | response `compliance` |
| H | `MainLayout.tsx` Quota | `/api/usage/summary` | `usage_counters.json` |
