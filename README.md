![logo](logo.png)

# 🎬 AdCreative AI Script Generator

![License](https://img.shields.io/badge/License-MIT-blue.svg)
![Python](https://img.shields.io/badge/Python-3.10%2B-green.svg)
![React](https://img.shields.io/badge/React-19.x-61DAFB.svg)
![Engine](https://img.shields.io/badge/Engine-DeepSeek%20%7C%20Ollama-orange.svg)

面向全球买量（UA）团队的 AI 脚本生成系统：  
输入项目档案 + 地区/平台/转化角度，输出可执行分镜脚本，并集成情报检索、用量监控、导出交付。

## 当前应用状况（2026-04）

- 已进入稳定迭代阶段（见 `docs/MEMORY_BANK.md`，当前 V2.1）
- 核心链路可用：`extract -> generate -> export(pdf/md)`  
- 前端/后端分离：`React + Vite` / `FastAPI`
- 默认支持云端 DeepSeek + 本地 Ollama 双引擎
- 已具备运行级用量监控（Token、Oracle 检索/归档、单脚本/平均消耗）

## 核心能力

### 1) 智能档案提取（`/api/extract-url`）

- 解析 Google Play 文案，生成双语导演档案（JSON contract）
- 本地模式优先走 Ollama；失败回落规则提取
- 云端可用时优先云提取，失败回落规则提取

### 2) SOP/Lab 脚本合成（`/api/generate`）

- 输入：`project_id + region_id + platform_id + angle_id`
- 支持 `output_mode=cn|en`
- 输出结构化评分、分镜脚本、心理洞察、文化备注、引用
- 成功后服务端自动导出 Markdown 到 `@OUT/`，返回 `markdown_path`

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
  src/layout/MainLayout.tsx
  src/context/
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
- `OLLAMA_BASE_URL`
- `OLLAMA_MODEL_EXTRACT`
- `OLLAMA_MODEL_DIRECTOR`
- `USAGE_DAILY_TOKEN_BUDGET`
- `USAGE_TOKENS_ESTIMATE_GENERATE_CLOUD`
- `USAGE_TOKENS_ESTIMATE_GENERATE_LOCAL`
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

## 本地 Ollama 排障

1. 确认 `OLLAMA_BASE_URL` 可访问  
2. 确认模型已拉取：`gemma4:e4b`、`qwen3.5:9b`  
3. 若出现 `LOCAL_REQUEST_FAILED` / `LOCAL_JSON_PARSE_FAILED`：
   - 检查模型名、地址、资源占用（显存/内存）
   - 先切更轻模型验证链路

## 路线图

- [ ] Apple App Store 提取支持
- [ ] 云端提取与本地提取 contract 完全对齐
- [ ] 继续完善 E2E Runbook 与真实环境回归

_Built for UA creative operators._
