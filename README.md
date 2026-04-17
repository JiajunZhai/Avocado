<img src="frontend/public/logo.png" alt="logo" width="220" />

# 🎬 AdCreative AI Script Generator

![License](https://img.shields.io/badge/License-MIT-blue.svg)
![Python](https://img.shields.io/badge/Python-3.10%2B-green.svg)
![React](https://img.shields.io/badge/React-19.x-61DAFB.svg)
![Engine](https://img.shields.io/badge/Engine-Multi--Provider-orange.svg)

面向全球买量（UA）团队的 AI 脚本生成系统：
输入项目档案 + 地区/平台/转化角度，输出可执行分镜脚本，并集成情报检索、用量监控、导出交付。

## 当前应用状况（2026-04）

- 已进入稳定迭代阶段（见 `docs/MEMORY_BANK.md`，当前 V2.6，Multi-Provider）
- 核心链路可用：`extract -> generate/quick-copy -> result -> export`
- 前端/后端分离：`React + Vite` / `FastAPI`
- **多 LLM 供应商（云端 OpenAI 兼容协议）**：DeepSeek / SiliconFlow / 阿里云百炼 / OpenRouter / ZEN（占位）；Lab 内 Engine Selector 二级下拉即可切换；未配置或调用失败仍以 502 显式报错，不做 mock/占位降级。
- 已具备运行级用量监控（Token、Oracle 检索/归档、单脚本/平均消耗、**by_provider** 维度）

## 工作流闭环（生成→复用→刷新→对比→导出）

- **生成**：在 `Lab` 配参数并生成（Full SOP / Quick Copy）
- **复用**：结果页（Result Dashboard）支持 Markdown + Copy Hub 审阅、复制与导出
- **刷新**：在 `Dashboard` 右侧记录列表对 SOP 一键 `Refresh copy`，生成新记录继续迭代
- **对比**：在 `Dashboard` 勾选两条记录一键 Compare（参数/文案/合规差异）
- **导出**：结果页支持 `MD / XLSX / PDF`（视数据而定）

## 核心能力

### 1) 智能档案提取（`/api/extract-url`）

- 解析 Google Play 文案，生成双语导演档案（JSON contract）
- 云端 DeepSeek 优先；未配置或失败时回落到规则化抽取

### 2) SOP/Lab 脚本合成（`/api/generate`）

- 输入：`project_id + region_id + platform_id + angle_id`
- 支持 `output_mode=cn|en`
- 输出结构化评分、分镜脚本、心理洞察、文化备注、引用
- 成功后服务端自动导出 Markdown 到 `@OUT/`，返回 `markdown_path`
- **无 mock 降级**：`DEEPSEEK_API_KEY` 缺失或 DeepSeek 调用失败 → 502 `CLOUD_UNAVAILABLE` / `CLOUD_SYNTHESIS_FAILED`

### 2.5) 极速文案模式（`/api/quick-copy` / `/api/quick-copy/refresh`）

- **Quick Copy**：跳过分镜，直接输出多语言/多风格 `ad_copy_matrix`
- **Refresh Copy**：基于历史 SOP 脚本一键刷新文案（用于素材复用与二轮测试）

### 3) Oracle 情报炼金（RAG）

- `Scikit-Learn TF-IDF` 本地向量检索
- 支持 `ingest` 录入文本/URL 抽取
- 生成时可引用检索结果并返回 citations

### 4) 计费与用量可视化（`/api/usage/summary`）

- 统计今日预算、剩余额度、provider 实计量与估算补齐
- 统计单脚本消耗、平均脚本消耗、样本量（真实/估算）
- 支持侧边栏 Quota 弹窗实时查看

### 5) 中英文输出模式

- `cn`：中文执行优先（分镜去冗余解释行）
- `en`：保留跨语种协作所需的注释型字段

## 关键目录

```text
backend/
  main.py
  prompts.py
  scraper.py
  refinery.py
  usage_tracker.py
  usage_tokens.py
  md_export.py
  knowledge_paths.py
  tests/
  data/knowledge/

frontend/
  src/pages/Lab.tsx
  src/pages/Dashboard.tsx
  src/layout/MainLayout.tsx
  src/context/
  src/components/ResultDashboardView.tsx
  src/components/CompareViewModal.tsx
  src/i18n/locales/

@OUT/   # 生成后的 markdown（默认不提交）
```

## 快速启动

### 1. 后端

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000
```

接口文档：`http://127.0.0.1:8000/docs`

### 2. 前端

```bash
cd frontend
npm install
npm run dev
```

默认地址：`http://localhost:5173`

## 环境变量（常用）

- `DEEPSEEK_API_KEY`
- `DEEPSEEK_BASE_URL`
- `DEEPSEEK_MODEL`
- `DEEPSEEK_TIMEOUT_SECONDS`（单次调用超时秒数，draft 默认 90，director 默认 120）
- `USAGE_DAILY_TOKEN_BUDGET`
- `USAGE_TOKENS_ESTIMATE_GENERATE_CLOUD`
- `USAGE_TOKENS_ESTIMATE_EXTRACT`
- 前端：`VITE_API_BASE`（可覆盖默认后端地址）

## 测试与验证

### 后端 pytest

```bash
cd backend
pytest tests/ -q
```

### 前端构建

```bash
cd frontend
npm run build
```

### E2E（可选）

```bash
cd frontend
npm run test:e2e
```

详细流程见：[`docs/E2E_FULL_VERIFICATION_RUNBOOK.md`](docs/E2E_FULL_VERIFICATION_RUNBOOK.md)

## 支持的云端大模型（Phase 25 / V2.6）

所有 Provider 都走 OpenAI 兼容协议，只需配置对应的 API Key 即可启用。未配置的 Provider 会在 Engine Selector 中显示 `no key`，选中后服务端自动回落到已配置的 `DEEPSEEK_API_KEY`（缺省兜底）。

| Provider ID | 厂商 / 说明 | API Key Env | Base URL（默认） | 默认模型 | 备注 |
|---|---|---|---|---|---|
| `deepseek` | DeepSeek（默认） | `DEEPSEEK_API_KEY` | `https://api.deepseek.com` | `deepseek-chat` | 也可切 `deepseek-reasoner` |
| `siliconflow` | 硅基流动 | `SILICONFLOW_API_KEY` | `https://api.siliconflow.cn/v1` | `deepseek-ai/DeepSeek-V3` | 支持 Qwen2.5-72B / Llama-3.1-70B 等 |
| `bailian` | 阿里云百炼（DashScope 兼容模式） | `BAILIAN_API_KEY` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` | 可切 `qwen-max` / `qwen-turbo` |
| `openrouter` | OpenRouter | `OPENROUTER_API_KEY` | `https://openrouter.ai/api/v1` | `deepseek/deepseek-chat` | 可走 `anthropic/claude-3.5-sonnet` 等 |
| `zen` | Open Code ZEN | `ZEN_API_KEY` | `https://api.opencode.zen/v1` | `zen-default` | **deferred**（占位，等官方生产入口） |

`backend/.env.example` 内已放好五段模板，去掉注释即可启用。单次调用可通过请求体 `engine_provider` / `engine_model` 覆盖默认；前端 Lab 的 Engine Selector 会自动透传到 `/api/generate`、`/api/quick-copy`、`/api/quick-copy/refresh`、`/api/quick-copy/retry-region`、`/api/extract-url` 与 `/api/estimate`。

### 在前端直接管理 API Key / 模型列表（Phase 27 · F）

导航栏 → **LLM Providers**（`/settings/providers`）可以在运行时修改：

- **API Key**：粘贴后立即写入 `backend/data/app.sqlite3` 的 `provider_settings` 表，Engine Selector 下次下拉即显示 `READY`；支持 `连通性测试` 按钮做一次最小调用（优先 `models.list`，失败回退 `max_tokens=1` 的 chat ping）
- **Base URL**：自建网关 / 反向代理一键切换
- **默认模型**：留空沿用内置默认；非空覆盖所有 call path
- **自定义模型列表**：手动添加或点 `拉取模型` 直接调 `client.models.list()`，结果合并到 Engine Selector 下拉框
- 单行 `清空 DB 覆盖` 按钮即可回落到 `.env` / 内置默认

优先级 `call-arg > DB > env > built-in default` —— `.env` 值仍然有效，CI 环境下完全不受影响。**安全提示**：API Key 以明文存放于 `backend/data/app.sqlite3`，请把该文件视同密钥文件保管。

历史记录（`history_log`，schema v3）会持久化每条生成所使用的 `provider` / `model`，用于 `by_provider` 维度的成本归因；Dashboard 历史条目会以胶囊徽章形式直接显示。

## 排障（LLM 调用）

1. 确认至少一家 Provider 的 API Key 已在 `backend/.env` 或进程环境中设置（DeepSeek 作为兜底推荐始终保留）
2. 确认网络可达对应 `*_BASE_URL`（默认值见上表或 `providers.py`）
3. 前端报 502：查看响应 `detail.error_code`
   - `CLOUD_UNAVAILABLE`：未配置任何可用 Provider 的 API Key
   - `CLOUD_SYNTHESIS_FAILED`：调用上游失败；`detail.error_message` 含原因，`detail.elapsed_ms` 含耗时
   - `DRAFT_UNAVAILABLE`：draft 阶段未能返回候选，检查 prompt / 上游响应

## 路线图

- [ ] Apple App Store 提取支持
- [ ] 继续完善 E2E Runbook 与真实环境回归

_Built for UA creative operators._
