# 多模块联调 & 产品评审 (Product Integration Review) — v2.2

**撰写日期**：2026-04-16
**视角**：资深 AI 应用产品经理（跨"产品 / 技术 / 增长 / 合规"联动审视）
**对象**：当前已交付的 AdCreative AI Script Generator（对齐 `docs/PRD.md v2.2` 与 `docs/BUSINESS_FLOW_AUDIT.md`）
**与既有文档关系**：
- `PRD.md` 回答 **"我们要做什么"**
- `BUSINESS_FLOW_AUDIT.md` 回答 **"单条业务流有没有走通"**
- **本文档** 回答 **"模块之间是否真正联动、用户旅程是否连贯、我们漏掉了什么"**

---

## 0. 一句话诊断

当前系统是一个**"会生成、能导出、有记录"的单体工具**；但它还不是一个**"会学习、能沉淀、可协作"的 UA 平台**。
核心结构性问题：**各模块内部已成熟，但跨模块是单向或无回路**——RAG 不反哺 Factor、合规不反哺 Prompt、Compare 不沉淀为实验、真实投放 CTR 不回流。
产品角度，下一阶段的胜负手不是继续加模块，而是**把现有模块连成闭环**。

---

## 1. 模块依赖关系 · 真实图谱

### 1.1 当前联动现状

```
                 +-----------------+
                 |  Dashboard UI   |
                 |  (history_log)  |
                 +--------+--------+
                          |
         ┌────────────────┼────────────────┐
         ▼                ▼                ▼
   [Open Result]    [Compare]          [Refresh]
         │                │                │
         ▼                ▼                ▼
+----------------+   +----------+   +--------------+
| ResultDashboard|   | Compare  |   | /quick-copy/ |
|   View         |   | Modal    |   |   refresh    |
+-------+--------+   +----------+   +------+-------+
        │                                  │
        ▼                                  ▼
+---------------+                 +-----------------+
| @OUT / MD /   |                 | record_history  |
| XLSX / PDF    |                 | (append)        |
+---------------+                 +--------+--------+
                                           │
                                           ▼
                                    +--------------+
                                    |  workspaces/ |
                                    |   {id}.json  |
                                    +--------------+


Lab ─▶ /api/generate ─▶ [Factor JSON] + [Oracle RAG] + [Project DNA] ─▶ Prompt ─▶ LLM
                                                                            │
                                                                            ▼
                                                                      finalize + compliance
                                                                            │
                                                                            ▼
                                                                      record_history
```

### 1.2 联动强度矩阵

| 从 ↓ / 到 → | Factor | Oracle RAG | Prompt | Compliance | History | Result UI | Usage |
|---|---|---|---|---|---|---|---|
| **Project/USP**      | 单向读 | 单向读 | 注入 | — | — | 展示 | — |
| **Factor JSON**      | —      | ❌无联动 | 注入 | ❌无联动 | — | 展示 | — |
| **Oracle RAG**       | ❌无反哺 | — | 注入 | — | ❌未入库 | 展示 evidence | — |
| **Compliance**       | — | — | ❌无反哺 | — | 写入 | 展示 | — |
| **History**          | — | ❌无回流 | ❌不参考 | — | — | 可复现 | — |
| **LLM usage**        | — | — | — | — | 部分入 metrics | 无感 | 聚合 |
| **真实投放 CTR**     | ❌缺失 | ❌缺失 | ❌缺失 | ❌缺失 | ❌缺失 | ❌缺失 | ❌缺失 |

> 6 处标红的 ❌ 是本评审要解决的核心缺口。

---

## 2. 联动性诊断（Where the Wires Are Cut）

### 2.1 🔴 断点一：Oracle RAG 是"只读博物馆"，不是"学习型知识库"

**现象**
- `/api/refinery/ingest` 摄取情报 → `local_storage.json`
- 生成时检索 `rag_evidence` → 拼进 Prompt → 前端展示证据
- **但**：RAG evidence 没有沉淀成 Factor；生成后也没有把新 angle/hook 回写 RAG。

**产品后果**
- 用户精心 ingest 一批优质对标素材后，**只在"下一次生成"里被用一次**；没有形成长期"品类知识"。
- 同一个 rule 被反复命中，但没被"提级"成 Factor 的正式条目。

**建议**
- 新增 **"Promote to Factor"** 动作：Resonance Feed 命中某条 RAG rule ≥ N 次（或用户手动点收藏）→ 一键写成 factor JSON 的 `hooks[]` / `do_rules[]`。
- RAG 摄取后自动尝试 `tag by angle/region/platform`，作为未来生成时的二级检索 facet。

### 2.2 🔴 断点二：Compliance 是"事后标红"，没有"事前制约"

**现象**
- 生成完成才扫描；BLOCK 仍可导出；LLM 改写建议未二次扫描。
- 历史命中的违禁词没有回流进 Prompt 的"negative rules"。

**产品后果**
- 同一个项目反复撞同一批违禁词，用户陷入"改了又撞→撞了又改"的 loop。
- 合规相当于安置了"警报器"，但没有"防撞栏"。

**建议**
- **Prompt-level Negative List**：从 history_log 聚合该项目最近 N 次的 `compliance.hits[].term`，生成时自动作为"avoid list"注入 Prompt。
- **Pre-generate Budget Check**：生成按钮旁显示"项目最近 7 天 WARN 率 X%，建议启用改写建议"，引导勾选 `compliance_suggest`。
- **Suggestion 二次扫描**：生成建议后 replay `scan_ad_copy`，在 UI 显示"建议仍残留 X 词，请进一步修改"。

### 2.3 🔴 断点三：Compare 是"一次性 diff"，不是"实验档案"

**现象**
- Compare 只是两条 history_log 的前端 diff；关闭窗口即失忆。
- 没有"这次 Compare 得出结论 → 采用 A / 采用 B / 都不用"的决策痕迹。

**产品后果**
- UA Creative Lead 每天要做无数次 A/B 抉择，这些判断没有沉淀为团队知识。
- 没法回答"上季度我们累计做了多少 A/B？获胜模式倾向哪种 Angle？"

**建议**
- 引入 **Experiment** 概念（轻量）：
  - `experiment_group_id`（任意两条以上可组成）
  - `decision: pick_a | pick_b | reject_all | pick_merged`
  - 可选 `external_ctr`（CSV 回填）
- Dashboard 增加 "Experiments" tab，长期聚合"获胜 Angle / 获胜 Region / 获胜 tone"。

### 2.4 🟠 断点四：History 与 Prompt 之间无"学习回路"

**现象**
- history_log 只用于展示与 Refresh；不作为生成时的 context。

**产品后果**
- 用户新 SOP 可能与上周的 SOP 高度雷同；系统"不知道自己已经出过这个 hook"。

**建议**
- 生成时在 Prompt 中注入 **"最近 5 条 SOP 的 headline 头尾 token"** 作为 avoid-repetition hint（可关闭）。
- 前端结果页在 headline 旁显示"与 2 周前雷同 60%"的提示（客户端 fuzzy match 即可）。

### 2.5 🟠 断点五：Factor JSON × Oracle 的双知识源缺少 governance

**现象**
- Factor JSON 是代码仓库级工件；Oracle RAG 是运行时数据文件。两者没有"版本绑定"。
- 生成时如果 factor 被改过、RAG 被清过，历史 SOP 的可复现性下降。

**产品后果**
- Compare 跨越 factor 更新期时，差异被"无版本背景"地展示。
- 审计回溯困难（某条 SOP 的 Angle 规则当时长什么样？）。

**建议**
- 每次生成在 history 里写 `factor_version`（hash or ISO date）与 `rag_version`。
- Dashboard 顶部状态条展示当前 factor / rag 版本，更新时 toast 通知。

### 2.6 🟠 断点六：Quick Copy 多 region 结果展示"拍扁了"

**现象**
- `variants["US:en"]` 与 `variants["SEA:en"]` 在 UI 上按 locale 分组后无法区分 region。
- 本地化评审时无法一眼看"同 locale 不同 region 的语气差异"。

**产品后果**
- 多地区功能是"看着酷炫的 API"，但结果页呈现未跟上，实际使用价值打折。

**建议**
- Copy Hub 多 region 时改为 **Region → Locale** 二级标签；或新增"Localization Matrix"视图（行 region × 列 locale 的 headline 墙）。

### 2.7 🟡 断点七：用户真实 CTR 信号完全缺席

**现象**
- 所有评分（hook/clarity/conversion）都是 LLM 自评；没有"真实投放后 CTR / CPI / IPM"回流通道。

**产品后果**
- 系统逐渐成为"自娱自乐的评分器"；无法回答"AI 预测高分 vs 实际爆款"的一致性。
- KPI `测试一致性` 在 PRD 存在但无数据来源。

**建议**
- 最小可行版本：Dashboard 记录行上增加 `Mark as Winner / Loser` 按钮（二元反馈）+ 可选 CPI/CTR CSV 导入。
- 后端聚合 per-angle/per-region 胜率；生成时作为 `preferred_style_signal` 注入 Prompt。

---

## 3. PRD 未覆盖的功能点（PM 角度的 12 个缺失）

按**用户价值 × 实现成本**的 PM 直觉排序：

### P0（高价值 / 中低成本）

1. **生成预览成本（Pre-flight token estimate）**
   用户点 Generate 之前，展示"预计耗时/预计 tokens/预计成本"，尤其对 Quick Copy 多 region × 多 locale 的组合爆炸场景。避免事后才发现"一次花了 5000 tokens"。

2. **生成队列 / 批量作业（Generation Queue）**
   允许一次排入 `[region × platform × angle]` 的 N 个组合，后台串行/并发执行，完成后 Dashboard 归档。改变单次手动点击的低效体验。

3. **参数配置模板（Recipe Presets）**
   把常用的 `region+platform+angle+tones+locales` 组合保存为 Preset（per project 或全局），一键套用。目前 Lab 只在 localStorage 存最近一次。

4. **多地区并排对比结果视图（Side-by-side Locale Matrix）**
   专为本地化总监的视图：一个 USP 跑 3 地区 × 2 语言 = 6 组 headlines 并排陈列，配 CTA 差异、合规 badge 差异。

5. **交付包一键导出（Delivery Pack Zip）**
   一次性打包 MD + XLSX + Compliance Report + 参数卡（JSON）给剪辑师 / 投放团队。

### P1（中价值 / 低成本）

6. **角色视图切换（Persona Workspace）**
   PRD 定义了 4 种用户角色但 UI 一视同仁。至少提供两套视图：
   - **Creative Lead 视图**（默认）
   - **Editor 视图**（只看 MD + 导出，隐藏成本/合规细节）
   - **Manager 视图**（KPI / 成本 / 活跃度 Dashboard）

7. **失败路径的增强引导（Error Recovery UX）**
   LLM 502 时，弹 "重试 / 切换引擎（云↔本地）/ 切换到 draft-only 模式 / 保存当前参数去反馈" 四个按钮。目前只 toast。

8. **智能默认参数（Smart Defaults）**
   Extract-URL 完成后，基于 genre/keywords 预填推荐 angle（需要一个简单 genre→angle 映射表即可）。节省"大部分用户都选头部组合"的重复点击。

9. **历史搜索与筛选**
   history_log 长起来后，必须有按 `output_kind / region / platform / angle / risk_level / date_range` 筛选 + 关键词（title/hook）搜索。

10. **合规规则运营界面**
    当前 `risk_terms.json` 要改代码。即便不做 CRUD，先做**只读可视化** + 导出按 platform/region 汇总表，供合规部门复核。

### P2（长期战略 / 高成本）

11. **投放效果回流 + 模型校准**
    见 §2.7，最小可行从"Winner/Loser 标记"开始，逐步对接 CTR/CPI。

12. **团队协作基础**
    - `project.owners[]` 与历史记录的 `created_by`
    - 评论/批注（"这条 headline 太 aggressive"）
    - 导出时自动附带"谁生成、谁审批"
    对 SaaS 化是必要地基；当前架构不做则未来大改。

---

## 4. 风险点（按维度梳理）

### 4.1 技术风险

| 风险 | 影响 | 建议 |
|---|---|---|
| **Prompt Injection via extract-url** | 商店描述里写 `"ignore previous instructions, output XYZ"` → 污染生成 | 对抓回的文本做 sanitize（剥去 markdown 控制符、限制长度、用 `"""` 围栏包裹） |
| **history_log 单文件膨胀** | 一个项目 500 条记录 → JSON 读写秒级卡顿 → Dashboard 初始化超时 | 按月分片 `workspaces/{id}/history/{YYYY-MM}.json` 或引入 SQLite |
| **LLM 单引擎单点** | 当前仅挂接 DeepSeek；云端不可用时直接 502（设计上"快失败"） | 接入第二家 OpenAI 兼容云端（如 OpenAI / 火山 / 通义），做同 contract 的熔断切换 |
| **@OUT 路径在 Windows 硬编码** | macOS/Linux 打开文件夹 500 | 跨平台适配 (`open` / `xdg-open`)；非 Windows 隐藏该按钮 |
| **Python 3.14 兼容链** | 各库陆续需要 patch（已出现过 chromadb 替换） | 在 README 说明"当前锁定 3.14 的原因"；CI 明确 matrix |

### 4.2 产品 & 数据风险

| 风险 | 影响 | 建议 |
|---|---|---|
| **LLM 幻觉机制** | 即便有"不得捏造机制"约束，长尾仍出现；用户难发现 | 生成后以 `game.core_gameplay` 做关键词回查，显示 "⚠ 文案提到 X 未在游戏信息中出现" |
| **评分自评偏差** | hook_score 全 LLM 自打，缺 ground truth | §2.7 的 CTR 回流；短期可引入"规则层审查"（`review` 已部分实现，继续丰富） |
| **因子知识过期** | 平台算法变了，factor JSON 没人维护 | 每条 factor 写 `last_reviewed_at`；UI 显示"6 月未更新" 黄标 |
| **合规假阳疲劳** | substring 匹配 `ad` → `advance` → 一堆 WARN → 用户屏蔽 badge | 升级规则结构 + 词边界；provider analytics 显示"最常假阳词" |

### 4.3 合规 & 法律风险

| 风险 | 建议 |
|---|---|
| **商店抓取版权** | 明确声明仅做 metadata 提取；不存储全文；robots/TOS 合规声明放 README |
| **LLM 生成的第三方 IP 侵权** | 对 "Disney/Marvel/Pokemon..." 等 IP 进入 risk_terms BLOCK |
| **地区敏感内容**（MEA 宗教、CN 等） | factor JSON 继续强化 `taboos[]`；生成侧强校验 |

### 4.4 增长 / 商业风险

| 风险 | 建议 |
|---|---|
| **单用户工具 vs 团队工具定位模糊** | 下一次迭代前做方向决策：强化单机生产力 OR 走向团队协作（影响鉴权/同步优先级） |
| **竞品（已有 MidJourney+GPT 组合式工作流）** | 核心差异化在"买量专属 factor 库 + 合规 + 成本透明"；要持续强化这条护城河，而非复刻通用 ChatGPT 体验 |

---

## 5. 用户 × 应用 交互优化（分角色）

### 5.1 UA Creative Lead（权重最高）

- **Pain**：每天跑 20+ 次生成，重复点相同参数。
- **Lift**：
  - Recipe Presets + Generation Queue
  - Keyboard shortcut：`⌘/Ctrl + Enter` 触发生成；`⌘/Ctrl + E` 打开 Export。
  - Dashboard 顶部插件："今日你已生成 N 条 / 最活跃 Angle：X"。

### 5.2 视频剪辑师

- **Pain**：只需要 MD，被复杂 UI 分心。
- **Lift**：
  - `?persona=editor` URL 参数进入 Editor 视图（极简，只看 MD + 打开 @OUT）。
  - MD 顶部自动渲染"关键拍摄要点卡"（从 `direction_note / sfx_transition_note` 聚合）。

### 5.3 本地化编辑

- **Pain**：多语言质量参差，没对比工具。
- **Lift**：
  - Localization Matrix 视图。
  - Transcreation 行级"建议改写"按钮（调 LLM，仅针对单条）。
  - `locale diff`：同 USP 不同 locale 的"语气差异自解释"（可选 LLM 解释）。

### 5.4 UA Manager

- **Pain**：只想看健康度与成本，不想进 Lab。
- **Lift**：
  - Manager Dashboard：每日生成量 / token 成本 / BLOCK 率 / Refresh 活跃度 / per-angle win rate。
  - 每周摘要邮件/本地报表导出。

### 5.5 跨角色（全局）

- **首次使用引导**：一个可跳过的 3 步 Onboarding（选 demo 项目 → 跑一次 Full SOP → 看结果页）。
- **空状态复活**：无记录的 Dashboard 显示"Try Sample Project"。
- **微交互一致性**：所有破坏性动作（删除项目 / 清空 @OUT）二次确认；所有网络失败 toast 结构化（操作名 + 原因 + 再试按钮）。

---

## 6. 优先级总表（用于 Phase 22 Planning）

> 打分口径：V = 用户价值（1–5）；C = 成本（1–5，越低越好做）；R = 风险缓解（1–5）。
> ROI ≈ (V × R) / C。

| # | 议题 | V | C | R | ROI | 归属 |
|---|---|---|---|---|---|---|
| 1 | History schema v2（parent_script_id / factor_version / lang / rag_rule_ids） | 5 | 2 | 5 | 12.5 | 架构 |
| 2 | Compliance Negative List 反哺 Prompt | 4 | 2 | 5 | 10 | AI 引擎 |
| 3 | Prompt Injection sanitize（extract-url） | 3 | 1 | 5 | 15 | 安全 |
| 4 | Pre-flight Token Estimate | 4 | 2 | 3 | 6 | 成本治理 |
| 5 | Generation Queue + Recipe Presets | 5 | 3 | 3 | 5 | 效率 |
| 6 | Quick Copy 部分失败协议 + Region 二级分组 UI | 4 | 2 | 4 | 8 | 可靠性 |
| 7 | Localization Matrix 视图 | 4 | 3 | 3 | 4 | 本地化价值 |
| 8 | 历史搜索/筛选 | 4 | 2 | 3 | 6 | 资产库 |
| 9 | Experiment 概念 + Winner/Loser 反馈 | 5 | 3 | 4 | 6.7 | 学习回路 |
| 10 | Compliance Admin（只读） | 3 | 2 | 4 | 6 | 运营 |
| 11 | Open Folder 跨平台 + Delivery Pack Zip | 3 | 2 | 2 | 3 | 交付 |
| 12 | Promote-to-Factor（RAG 反哺） | 5 | 4 | 3 | 3.75 | 战略 |
| 13 | Persona 视图切换 | 4 | 3 | 2 | 2.7 | UX |
| 14 | Onboarding Tour + 空状态 | 3 | 2 | 1 | 1.5 | UX |

### 建议 Phase 22 主题（三条主线）

**A. "闭环学习"** — #1 + #2 + #9 + #12
把 history/compliance/RAG 从"展示"升级为"反哺"。

**B. "可靠生产"** — #3 + #4 + #5 + #6
让批量生产不翻车：安全 + 成本可预测 + 批量调度 + 部分失败可见。

**C. "资产化"** — #7 + #8 + #10 + #11
把 MD/Copy 从"散装文件"升级为"可检索、可筛选、可一键交付"的资产。

> 三条线每条各 ~1 周量级，是健康的 Phase 22 节奏；不建议同周期并行 A+B+C 全部。

---

## 7. 结尾 · 产品定位提醒

本系统当前在以下三件事上已经做到**领先同类开源方案**：
- 1+1+3 的 DNA × RAG × Factor prompt 拼装
- 合规扫描 + LLM 改写的双层防御
- 生成→复用→刷新→对比→导出 的完整中控闭环

不应被稀释或牺牲的护城河：
- **买量专属 factor 库**（region/platform/angle 的产品级沉淀）
- **成本透明度**（provider vs estimate 可见）
- **本地 + 云端双引擎切换**

下一个阶段要回答的核心产品问题：
> **"我们是一把更好的生成枪，还是一支会学习的投放军队？"**
>
> 建议选后者——本评审提出的联动断点与回流建议，都是朝"军队"方向的地基。
