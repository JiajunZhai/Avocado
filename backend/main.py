from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import os
import sys
import json
from pathlib import Path
from typing import Any, Optional
from dotenv import load_dotenv
from openai import OpenAI
import uuid
from datetime import datetime

load_dotenv()
cloud_client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
) if os.getenv("DEEPSEEK_API_KEY") else None

app = FastAPI(
    title="AdCreative AI Script Generator API",
    description="Backend API for generating structured video ad scripts using AI with Culture Intelligence.",
    version="1.1.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from projects_api import router as projects_router
app.include_router(projects_router)

class GenerateScriptRequest(BaseModel):
    project_id: str
    region_id: str
    platform_id: str
    angle_id: str
    engine: str = Field(default="cloud", description="The LLM source engine (cloud or local)")
    output_mode: str = Field(default="cn", description="Markdown output mode: cn or en")
    mode: str = Field(default="auto", description="Generation mode: draft | director | auto")
    compliance_suggest: bool = Field(
        default=False,
        description="When true and cloud engine is available, generate rewrite suggestions for compliance hits.",
    )

class AdCopyMatrix(BaseModel):
    primary_texts: list[str] = Field(default_factory=list, description="Long-form ad primary texts (>=5)")
    headlines: list[str] = Field(default_factory=list, description="Short high-CTR headlines with emoji (>=10)")
    hashtags: list[str] = Field(default_factory=list, description="Global high-frequency hashtags (>=20)")
    visual_stickers: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Per-shot sticker allocation items: {shot_index, sticker_text, sticker_meaning_cn}",
    )

class GenerateScriptResponse(BaseModel):
    script_id: str
    hook_score: int
    hook_reasoning: str
    clarity_score: int
    clarity_reasoning: str
    conversion_score: int
    conversion_reasoning: str
    bgm_direction: str
    editing_rhythm: str
    script: list[dict]
    psychology_insight: str
    cultural_notes: list[str]
    competitor_trend: str
    citations: list[str] = []
    markdown_path: Optional[str] = None
    drafts: Optional[list[dict]] = None
    review: Optional[dict] = None
    generation_metrics: Optional[dict] = None
    ad_copy_matrix: Optional[AdCopyMatrix] = None
    ad_copy_tiles: Optional[list[dict[str, Any]]] = None
    compliance: Optional[dict[str, Any]] = None

@app.get("/")
def read_root():
    return {"status": "ok", "message": "AdCreative AI Engine Sandbox is running"}


from scraper import fetch_playstore_data, extract_usp_via_llm_with_usage
from exporter import generate_pdf_report
from refinery import retrieve_context, retrieve_context_with_evidence, distill_and_store
from md_export import export_markdown_after_generate
from knowledge_paths import FACTORS_DIR, ensure_knowledge_layout
from usage_tokens import total_tokens_from_completion
from usage_tracker import (
    get_summary as usage_get_summary,
    record_extract_url_success,
    record_generate_success,
    record_oracle_ingest_success,
)

class GeneratePdfRequest(BaseModel):
    data: dict


class OutPathRequest(BaseModel):
    path: str

class QuickCopyRequest(BaseModel):
    project_id: str
    region_id: str
    region_ids: list[str] = Field(default_factory=list, description="Optional multi-region IDs (checkbox multi-select)")
    platform_id: str
    angle_id: str
    engine: str = Field(default="cloud", description="The LLM source engine (cloud or local)")
    output_mode: str = Field(default="cn", description="Markdown output mode: cn or en")
    quantity: int = Field(default=20, description="Number of headlines per locale")
    tones: list[str] = Field(default_factory=list, description="Tone preferences: humor, pro, clickbait, benefit, FOMO, etc.")
    locales: list[str] = Field(default_factory=list, description="Locales to generate copies for (e.g., en, ja, ar)")
    compliance_suggest: bool = Field(default=False, description="Generate compliance rewrite suggestions (cloud only).")

class RefreshCopyRequest(BaseModel):
    project_id: str
    base_script_id: str
    engine: str = Field(default="cloud", description="The LLM source engine (cloud or local)")
    output_mode: str = Field(default="cn", description="Markdown output mode: cn or en")
    quantity: int = Field(default=20, description="Number of headlines per locale")
    tones: list[str] = Field(default_factory=list)
    locales: list[str] = Field(default_factory=list)
    compliance_suggest: bool = Field(default=False, description="Generate compliance rewrite suggestions (cloud only).")

class QuickCopyResponse(BaseModel):
    script_id: str
    project_id: str
    ad_copy_matrix: dict[str, Any]
    markdown_path: Optional[str] = None
    generation_metrics: Optional[dict] = None
    ad_copy_tiles: Optional[list[dict[str, Any]]] = None
    compliance: Optional[dict[str, Any]] = None

REQUIRED_SCRIPT_FIELDS = {
    "hook_score",
    "hook_reasoning",
    "clarity_score",
    "clarity_reasoning",
    "conversion_score",
    "conversion_reasoning",
    "bgm_direction",
    "editing_rhythm",
    "script",
    "psychology_insight",
    "cultural_notes",
    "competitor_trend"
}

REQUIRED_SCRIPT_LINE_FIELDS = {
    "time",
    "visual",
    "visual_meaning",
    "audio_content",
    "audio_meaning",
    "text_content",
    "text_meaning",
    "direction_note",
    "sfx_transition_note",
}


def _resolve_out_path(rel: str) -> tuple[str, str]:
    """
    Resolve an @OUT-relative path safely.

    Returns (abs_file_path, abs_out_dir) as strings.
    Raises HTTPException(400) on invalid input / traversal.
    """
    from md_export import repo_root

    raw = str(rel or "").strip()
    if not raw.startswith("@OUT/"):
        raise HTTPException(status_code=400, detail="path must start with @OUT/")
    # normalize to OS path segments
    rel_tail = raw[len("@OUT/") :]
    # basic traversal guards (still verify via resolved path)
    if ".." in rel_tail.replace("\\", "/").split("/"):
        raise HTTPException(status_code=400, detail="path traversal is not allowed")

    out_dir = (repo_root() / "@OUT").resolve()
    abs_path = (out_dir / rel_tail).resolve()
    try:
        common = os.path.commonpath([str(out_dir), str(abs_path)])
    except Exception:
        raise HTTPException(status_code=400, detail="invalid @OUT path")
    if str(Path(common).resolve()).lower() != str(out_dir).lower():
        raise HTTPException(status_code=400, detail="invalid @OUT path")
    return str(abs_path), str(out_dir)


def _is_localhost_request(request: Request) -> bool:
    host = (request.client.host if request.client else "") or ""
    return host in {"127.0.0.1", "localhost", "::1"}


@app.get("/api/out/markdown")
def out_markdown(path: str):
    abs_path, _abs_out = _resolve_out_path(path)
    if not abs_path.lower().endswith(".md"):
        raise HTTPException(status_code=400, detail="only .md is supported")
    if not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail="markdown file not found")
    try:
        with open(abs_path, "r", encoding="utf-8") as f:
            body = f.read()
        return {"success": True, "markdown": body}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"failed to read markdown: {e}")


@app.post("/api/out/open-folder")
def out_open_folder(request: Request, payload: OutPathRequest):
    # Safety: never allow remote-triggered folder opening.
    if not _is_localhost_request(request) and os.getenv("ALLOW_OUT_OPEN_FOLDER", "").strip() != "1":
        raise HTTPException(status_code=403, detail="open-folder is allowed only from localhost")
    abs_path, abs_out = _resolve_out_path(payload.path)
    folder = os.path.dirname(abs_path)
    if not folder:
        folder = abs_out
    folder = str(Path(folder).resolve())
    if not folder.lower().startswith(str(Path(abs_out).resolve()).lower()):
        raise HTTPException(status_code=400, detail="invalid folder")
    try:
        if not os.path.exists(folder):
            raise HTTPException(status_code=404, detail="folder not found")
        os.startfile(folder)  # type: ignore[attr-defined]  # Windows only
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"failed to open folder: {e}")

def _print_console_safe(text: str) -> None:
    """Avoid UnicodeEncodeError on Windows consoles (e.g. cp936) when prompt/context has rare symbols."""
    try:
        print(text)
    except UnicodeEncodeError:
        sys.stdout.buffer.write(text.encode("utf-8", errors="replace"))
        sys.stdout.buffer.write(b"\n")


def _is_valid_script_payload(payload: dict[str, Any]) -> bool:
    if not isinstance(payload, dict):
        return False
    if not REQUIRED_SCRIPT_FIELDS.issubset(payload.keys()):
        return False
    if not isinstance(payload.get("script"), list) or not payload["script"]:
        return False
    if not isinstance(payload.get("cultural_notes"), list):
        return False
    for line in payload["script"]:
        if not isinstance(line, dict):
            return False
        if not REQUIRED_SCRIPT_LINE_FIELDS.issubset(line.keys()):
            return False
    return True


def _normalize_script_lines(payload: dict[str, Any]) -> dict[str, Any]:
    """Backfill new director-facing fields for backward compatibility."""
    script = payload.get("script")
    if not isinstance(script, list):
        return payload
    for line in script:
        if not isinstance(line, dict):
            continue
        visual = str(line.get("visual", "")).strip()
        audio_meaning = str(line.get("audio_meaning", "")).strip()
        line.setdefault("visual_meaning", visual)
        line.setdefault("direction_note", "")
        line.setdefault("sfx_transition_note", "")
        # Unify sticker fields: legacy export reads text_content/text_meaning
        sticker_text = str(line.get("sticker_text", "") or "").strip()
        sticker_meaning = str(line.get("sticker_meaning", "") or "").strip()
        if not str(line.get("text_content", "") or "").strip() and sticker_text:
            line["text_content"] = sticker_text
        if not str(line.get("text_meaning", "") or "").strip() and sticker_meaning:
            line["text_meaning"] = sticker_meaning
        if not sticker_text and str(line.get("text_content", "") or "").strip():
            line["sticker_text"] = str(line.get("text_content", "")).strip()
        if not sticker_meaning and str(line.get("text_meaning", "") or "").strip():
            line["sticker_meaning"] = str(line.get("text_meaning", "")).strip()
        if audio_meaning and "语气" not in audio_meaning and "节奏" not in audio_meaning:
            line["audio_meaning"] = f"{audio_meaning}（语气：自然口语；节奏：短句有力）"
    return payload


def _extract_headline_keywords(headlines: list[str]) -> list[str]:
    if not headlines:
        return []
    first = str(headlines[0] or "")
    # Keep it simple and robust: ASCII-ish tokens only
    tokens = []
    for raw in first.replace("#", " ").replace("|", " ").replace("-", " ").split():
        w = "".join(ch for ch in raw if ch.isalnum())
        if len(w) >= 3:
            tokens.append(w.lower())
    # de-dup while preserving order
    out: list[str] = []
    for t in tokens:
        if t not in out:
            out.append(t)
    return out[:6]


def _ensure_ad_copy_matrix(
    payload: dict[str, Any],
    *,
    angle_name: str,
    platform_name: str,
    region_name: str,
) -> dict[str, Any]:
    """Best-effort backfill to satisfy Ad Copy Matrix minimum counts."""
    acm = payload.get("ad_copy_matrix")
    if not isinstance(acm, dict):
        acm = {}
    primary_texts = acm.get("primary_texts")
    headlines = acm.get("headlines")
    hashtags = acm.get("hashtags")
    visual_stickers = acm.get("visual_stickers")

    if not isinstance(primary_texts, list):
        primary_texts = []
    if not isinstance(headlines, list):
        headlines = []
    if not isinstance(hashtags, list):
        hashtags = []
    if not isinstance(visual_stickers, list):
        visual_stickers = []

    # Primary texts (5 styles)
    style_templates = [
        ("拯救", f"他/她只差一步就被毁掉…你能在 3 秒内救回来吗？立刻进 {platform_name} 爆款玩法：点一下，逆转结局。"),
        ("智商", f"你以为这是随机？其实是策略题。{region_name} 热门解法：看穿陷阱 → 一步翻盘 → 爽感爆表。"),
        ("ASMR", "听这一声“咔哒”就上瘾。慢一点、爽一点：刮开、解压、连击反馈，每一帧都舒服。"),
        ("福利", "新手福利拉满：开局送资源，连抽不断，轻松追上老玩家。今天就把奖励拿走。"),
        ("简洁", "3 秒看懂，1 分钟上头。真实玩法，不演。"),
    ]
    for name, t in style_templates:
        if len(primary_texts) >= 5:
            break
        primary_texts.append(f"[{name}] {t}")
    primary_texts = [str(x) for x in primary_texts if str(x).strip()][: max(5, len(primary_texts))]

    # Headlines (>=10, include emoji)
    headline_pool = [
        "Level 1 vs Level 99 😱",
        "Huge Win in 3s 🏆",
        "Scared? Watch this 😳",
        "One Tap Comeback 🔥",
        "Stop Doing This ❌",
        "Only 1% Can Solve 🧠",
        "So Satisfying... 😌",
        "Free Rewards Today 🎁",
        "Fail? Try Again ✅",
        "Real Gameplay, No Cap 🎮",
        f"{angle_name} Hook Works 😈",
        f"{platform_name} Trend Alert 🚀",
    ]
    for h in headline_pool:
        if len(headlines) >= 10:
            break
        headlines.append(h)
    headlines = [str(x) for x in headlines if str(x).strip()]

    # Hashtags (>=20)
    tag_pool = [
        "#mobilegame", "#gaming", "#ad", "#ua", "#fyp", "#viral", "#tiktokads", "#reels", "#shorts",
        "#gameplay", "#strategy", "#puzzle", "#satisfying", "#asmr", "#reward", "#free", "#levelup",
        "#challenge", "#comedy", "#fail", "#win", "#trend", "#newgame", "#casualgame", "#hypercasual",
    ]
    for tag in tag_pool:
        if len(hashtags) >= 20:
            break
        hashtags.append(tag)
    hashtags = [str(x) for x in hashtags if str(x).strip()]

    # Visual stickers: per shot >=1 + CN meaning, align first 3s with headline keywords
    script = payload.get("script")
    if isinstance(script, list) and script:
        existing_by_idx: dict[int, dict[str, Any]] = {}
        for it in visual_stickers:
            if isinstance(it, dict) and isinstance(it.get("shot_index"), int):
                existing_by_idx[it["shot_index"]] = it

        keywords = _extract_headline_keywords(headlines)
        default_pairs = [
            ("LEVEL 1 vs LEVEL 99", "1 级 vs 99 级（强对比）"),
            ("HUGE WIN", "巨大胜利（强爽点）"),
            ("DON'T DO THIS", "千万别这样做（反差警告）"),
            ("FREE REWARDS", "免费奖励（福利暗示）"),
            ("SO SATISFYING", "太解压了（ASMR/解压向）"),
        ]

        for i, line in enumerate(script):
            if not isinstance(line, dict):
                continue
            if i in existing_by_idx:
                continue
            sticker_text = str(line.get("sticker_text") or line.get("text_content") or "").strip()
            sticker_meaning_cn = str(line.get("sticker_meaning") or line.get("text_meaning") or "").strip()
            if not sticker_text:
                pair = default_pairs[i % len(default_pairs)]
                sticker_text = pair[0]
                sticker_meaning_cn = sticker_meaning_cn or pair[1]
            # Ensure first ~3s (first 2 shots is typical) mention headline keyword when available
            if i <= 1 and keywords and not any(k in sticker_text.lower() for k in keywords):
                sticker_text = f"{keywords[0].upper()} | {sticker_text}"
                sticker_meaning_cn = sticker_meaning_cn or "与标题关键词对齐（前3秒）"
            visual_stickers.append(
                {
                    "shot_index": i,
                    "sticker_text": sticker_text,
                    "sticker_meaning_cn": sticker_meaning_cn or "画面贴纸强化冲击与信息密度",
                }
            )
            # Keep shot-level fields in sync for export/UI
            line.setdefault("sticker_text", sticker_text)
            line.setdefault("sticker_meaning", sticker_meaning_cn or "画面贴纸强化冲击与信息密度")
            if not str(line.get("text_content", "") or "").strip():
                line["text_content"] = sticker_text
            if not str(line.get("text_meaning", "") or "").strip():
                line["text_meaning"] = line.get("sticker_meaning", "")

    payload["ad_copy_matrix"] = {
        "primary_texts": primary_texts[: max(5, len(primary_texts))],
        "headlines": headlines[: max(10, len(headlines))],
        "hashtags": hashtags[: max(20, len(hashtags))],
        "visual_stickers": visual_stickers,
    }
    return payload


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _pick_top_draft(drafts_payload: dict[str, Any]) -> tuple[list[dict], dict | None]:
    drafts = drafts_payload.get("drafts") if isinstance(drafts_payload, dict) else None
    if not isinstance(drafts, list):
        return [], None
    cleaned = [d for d in drafts if isinstance(d, dict)]
    if not cleaned:
        return [], None
    recommend = str(drafts_payload.get("pick_recommendation", "")).strip()
    for d in cleaned:
        if str(d.get("id", "")).strip() == recommend:
            return cleaned, d
    top = max(
        cleaned,
        key=lambda x: (_safe_int(x.get("estimated_quality")), _safe_int(x.get("estimated_ctr"))),
    )
    return cleaned, top


def _build_script_review(
    script_payload: dict[str, Any],
    *,
    core_gameplay: str,
    angle_name: str,
) -> dict[str, Any]:
    script_lines = script_payload.get("script", [])
    issues: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    joined_visual = " ".join(str((ln or {}).get("visual", "")) for ln in script_lines if isinstance(ln, dict)).lower()
    if any(k in joined_visual for k in ("low battery", "phone call", "system warning", "os alert", "native ui")):
        issues.append(
            {
                "code": "policy_fake_system_ui",
                "message": "脚本含疑似系统原生UI伪装元素，存在拒审风险。",
            }
        )

    first_two = " ".join(
        str((ln or {}).get("visual", ""))
        for ln in script_lines[:2]
        if isinstance(ln, dict)
    ).lower()
    gameplay_keywords = [w.lower() for w in str(core_gameplay or "").split() if len(w) >= 4][:8]
    if gameplay_keywords and not any(k in first_two for k in gameplay_keywords):
        warnings.append(
            {
                "code": "hook_gameplay_gap",
                "message": "前2镜未明显体现核心玩法关键词，可能出现高CTR低留存。",
            }
        )

    if len(script_lines) < 5:
        warnings.append(
            {
                "code": "low_story_density",
                "message": "分镜数量偏少，建议至少5镜以保证完整叙事闭环。",
            }
        )

    if "asmr" in str(angle_name).lower():
        rhythm = str(script_payload.get("editing_rhythm", "")).lower()
        if any(k in rhythm for k in ("0.8", "1.0", "hyper-fast", "extreme fast")):
            warnings.append(
                {
                    "code": "asmr_pacing_too_fast",
                    "message": "ASMR方向节奏过快，建议在展示段延长单镜头时长。",
                }
            )

    score = max(0, 100 - 20 * len(issues) - 8 * len(warnings))
    return {
        "issues": issues,
        "warnings": warnings,
        "score_breakdown": {
            "overall": score,
            "issue_penalty": 20 * len(issues),
            "warning_penalty": 8 * len(warnings),
        },
    }

def _looks_like_error_placeholder(data: dict[str, Any]) -> bool:
    haystacks = [
        str(data.get("hook_reasoning", "")),
        str(data.get("clarity_reasoning", "")),
        str(data.get("conversion_reasoning", "")),
        str(data.get("bgm_direction", "")),
        str(data.get("editing_rhythm", ""))
    ]
    for line in data.get("script", []):
        if isinstance(line, dict):
            haystacks.append(str(line.get("visual", "")))

    flags = (
        "Ollama parsing failure",
        "Error Local LLM Output",
        "LOCAL_JSON_PARSE_FAILED",
        "LOCAL_REQUEST_FAILED"
    )
    return any(flag in text for text in haystacks for flag in flags)


def _normalize_ad_copy_matrix(acm: Any, *, quantity: int) -> dict[str, Any]:
    """Best-effort normalize quick-copy output structure + enforce minimums."""
    q = max(5, min(int(quantity or 20), 200))
    if not isinstance(acm, dict):
        acm = {}
    default_locale = str(acm.get("default_locale") or "en").strip() or "en"
    locales = acm.get("locales")
    if not isinstance(locales, list) or not locales:
        locales = [default_locale]
    locales = [str(x).strip() for x in locales if str(x).strip()]
    if default_locale not in locales:
        locales.insert(0, default_locale)
    variants = acm.get("variants")
    if not isinstance(variants, dict):
        variants = {}

    def ensure_variant(loc: str, v: Any) -> dict[str, Any]:
        if not isinstance(v, dict):
            v = {}
        pt = v.get("primary_texts")
        hl = v.get("headlines")
        ht = v.get("hashtags")
        if not isinstance(pt, list):
            pt = []
        if not isinstance(hl, list):
            hl = []
        if not isinstance(ht, list):
            ht = []

        # backfill minimums (keep content simple; prompt should do heavy lifting)
        while len(pt) < 5:
            pt.append(f"[Minimal] Clean hook + clear benefit ({loc})")
        while len(hl) < q:
            hl.append(f"Level 1 vs Level 99 😱 ({loc})")
        hl = [str(x) for x in hl if str(x).strip()][:q]

        tag_pool = [
            "#mobilegame", "#gaming", "#fyp", "#viral", "#shorts",
            "#gameplay", "#strategy", "#puzzle", "#satisfying", "#asmr",
            "#reward", "#free", "#levelup", "#challenge", "#win",
            "#trend", "#newgame", "#casualgame", "#hypercasual", "#tiktokads",
        ]
        for tag in tag_pool:
            if len(ht) >= 20:
                break
            ht.append(tag)
        ht = [str(x) for x in ht if str(x).strip()]
        # ensure hash prefix
        ht = [x if x.startswith("#") else f"#{x.lstrip()}" for x in ht]

        return {"primary_texts": pt, "headlines": hl, "hashtags": ht[: max(20, len(ht))]}

    for loc in locales:
        variants[loc] = ensure_variant(loc, variants.get(loc))

    return {"default_locale": default_locale, "locales": locales, "variants": variants}


def _script_to_context(script_lines: Any) -> str:
    if not isinstance(script_lines, list) or not script_lines:
        return ""
    chunks: list[str] = []
    for i, ln in enumerate(script_lines[:20], start=1):
        if not isinstance(ln, dict):
            continue
        t = str(ln.get("time", "")).strip()
        v = str(ln.get("visual", "")).strip()
        vo = str(ln.get("audio_content", "")).strip()
        st = str(ln.get("text_content", "")).strip()
        if v or vo or st:
            chunks.append(f"[Shot {i} {t}] visual={v} | vo={vo} | sticker={st}")
    return "\n".join(chunks)


@app.post("/api/quick-copy", response_model=QuickCopyResponse)
def quick_copy(request: QuickCopyRequest):
    import os, json, time
    from prompts import render_copy_prompt

    t0 = time.perf_counter()
    if not request.project_id:
        raise HTTPException(status_code=400, detail="project_id is required")

    ensure_knowledge_layout()
    base_dir = str(FACTORS_DIR)
    def read_insight(insight_id: str):
        if not insight_id:
            return {}
        category = insight_id.split('_')[0] + 's'
        path = os.path.join(base_dir, category, f"{insight_id}.json")
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    # workspace
    project_json = {"name": "Unknown", "game_info": {"core_usp": "Generic Game"}}
    workspace_file = os.path.join(os.path.dirname(__file__), 'data', 'workspaces', f"{request.project_id}.json")
    if os.path.exists(workspace_file):
        with open(workspace_file, 'r', encoding='utf-8') as f:
            project_json = json.load(f)

    platform_json = read_insight(request.platform_id)
    angle_json = read_insight(request.angle_id)
    gi = project_json.get('game_info', {})
    game_context = (
        f"Title: {project_json.get('name')}\n"
        f"Core Gameplay: {gi.get('core_gameplay', '')}\n"
        f"USP: {gi.get('core_usp', '')}\n"
        f"Target Persona: {gi.get('target_persona', '')}\n"
        f"Extended Hooks: {gi.get('value_hooks', '')}"
    )

    script_id = "COPY-" + uuid.uuid4().hex[:6].upper()
    regions_to_run = [str(x) for x in (request.region_ids or []) if str(x).strip()] or [request.region_id]
    region_acm: dict[str, dict[str, Any]] = {}
    for rid in regions_to_run:
        region_json = read_insight(rid)
        # Optional: lightweight RAG context only (no heavy stitching)
        rag_context, _, _ = retrieve_context_with_evidence(
            f"{rid} {request.platform_id} {request.angle_id}",
            top_k=4,
            supplement=f"{rid}\n{request.platform_id}\n{request.angle_id}\n{game_context}",
            region_boost_tokens=[str(region_json.get("name"))] if isinstance(region_json, dict) and region_json.get("name") else None,
        )
        prompt = render_copy_prompt(
            game_context=game_context,
            culture_context=region_json if isinstance(region_json, dict) else {},
            platform_rules=platform_json if isinstance(platform_json, dict) else {},
            creative_logic=angle_json if isinstance(angle_json, dict) else {},
            quantity=request.quantity,
            tones=request.tones,
            locales=request.locales,
        )
        user_input = f"Market context (optional):\n{rag_context}\n\nReturn copy matrix JSON only."

        result_obj: dict[str, Any] = {}
        if request.engine == "local":
            from ollama_client import generate_with_local_llm

            result = generate_with_local_llm(system_prompt=prompt, user_input=user_input, expected_json=True)
            if isinstance(result.output, dict):
                result_obj = result.output
        elif cloud_client:
            try:
                resp = cloud_client.chat.completions.create(
                    model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": user_input},
                    ],
                )
                result_obj = json.loads(resp.choices[0].message.content or "{}")
            except Exception as e:
                print(f"Quick copy failed ({rid}): {e}")
                result_obj = {}
        acm_raw = result_obj.get("ad_copy_matrix") if isinstance(result_obj, dict) else None
        region_acm[rid] = _normalize_ad_copy_matrix(acm_raw, quantity=request.quantity)

    # Merge multi-region into one stable {locales, variants} shape by namespacing locale keys: "{region}:{locale}"
    combined_locales: list[str] = []
    combined_variants: dict[str, Any] = {}
    for rid, acm in region_acm.items():
        locales = acm.get("locales") if isinstance(acm.get("locales"), list) else [acm.get("default_locale") or "en"]
        variants = acm.get("variants") if isinstance(acm.get("variants"), dict) else {}
        for loc in [str(x) for x in locales if str(x).strip()]:
            key = f"{rid}:{loc}"
            combined_locales.append(key)
            combined_variants[key] = variants.get(loc) if isinstance(variants, dict) else {}
    default_locale = combined_locales[0] if combined_locales else f"{regions_to_run[0]}:en"
    acm = {
        "default_locale": default_locale,
        "locales": combined_locales,
        "variants": combined_variants,
        "regions": regions_to_run,
    }
    payload = {
        "script_id": script_id,
        "project_id": request.project_id,
        "ad_copy_matrix": acm,
        "generation_metrics": {
            "mode": "copy_only",
            "elapsed_ms": int((time.perf_counter() - t0) * 1000),
            "quantity": int(request.quantity),
            "locales": acm.get("locales", []),
            "regions": regions_to_run,
        },
    }
    # Tiles + compliance scan (best-effort)
    try:
        from compliance import build_ad_copy_tiles, maybe_generate_rewrite_suggestions, scan_ad_copy

        tiles: list[dict[str, Any]] = []
        compliance_by_region: dict[str, Any] = {}
        for rid, one in region_acm.items():
            t = build_ad_copy_tiles(one, region_id=rid)
            tiles.extend(t)
            compliance_by_region[rid] = scan_ad_copy(t, platform_id=request.platform_id, region_id=rid)
        payload["ad_copy_tiles"] = tiles
        # overall compliance: worst risk_level + merged hits
        risk_order = {"ok": 0, "warn": 1, "block": 2, "unknown": 3}
        overall_risk = "ok"
        overall_hits: list[dict[str, Any]] = []
        for rid, c in compliance_by_region.items():
            rl = str((c or {}).get("risk_level") or "ok")
            if risk_order.get(rl, 0) > risk_order.get(overall_risk, 0):
                overall_risk = rl
            hits = (c or {}).get("hits")
            if isinstance(hits, list):
                overall_hits.extend(hits)
        compliance_obj: dict[str, Any] = {"risk_level": overall_risk, "hits": overall_hits[:200], "by_region": compliance_by_region}
        if request.compliance_suggest and cloud_client:
            tiles_by_id = {str(t.get("id")): t for t in tiles if isinstance(t, dict) and t.get("id")}
            suggestions = maybe_generate_rewrite_suggestions(
                cloud_client=cloud_client,
                hits=list(compliance_obj.get("hits") or []),
                tiles_by_id=tiles_by_id,
                output_mode=request.output_mode,
            )
            if suggestions:
                compliance_obj["suggestions"] = suggestions
        payload["compliance"] = compliance_obj
    except Exception:
        pass
    md_rel = export_markdown_after_generate(
        request.project_id,
        str(project_json.get("name") or "Unknown"),
        {
            "region": ",".join(regions_to_run),
            "platform": request.platform_id,
            "angle": request.angle_id,
            "region_name": ",".join(regions_to_run),
            "platform_name": str(platform_json.get("name") or request.platform_id) if isinstance(platform_json, dict) else request.platform_id,
            "angle_name": str(angle_json.get("name") or request.angle_id) if isinstance(angle_json, dict) else request.angle_id,
            "region_short": "",
            "platform_short": str(platform_json.get("short_name") or "") if isinstance(platform_json, dict) else "",
            "angle_short": str(angle_json.get("short_name") or "") if isinstance(angle_json, dict) else "",
        },
        request.engine,
        payload,
        request.output_mode,
    )
    payload["markdown_path"] = md_rel
    # record usage as light call (estimate path still 0 here)
    record_generate_success(engine=request.engine if request.engine in {"local", "cloud"} else "mock", measured_tokens=0)
    # record history for management UI
    try:
        record_history(project_json, request, payload, request.engine, recipe_override={"region": ",".join(regions_to_run), "platform": request.platform_id, "angle": request.angle_id})
    except Exception:
        pass
    return QuickCopyResponse(**payload)


@app.post("/api/quick-copy/refresh", response_model=QuickCopyResponse)
def refresh_copy(request: RefreshCopyRequest):
    import os, json, time
    from prompts import render_copy_prompt

    t0 = time.perf_counter()
    workspace_file = os.path.join(os.path.dirname(__file__), 'data', 'workspaces', f"{request.project_id}.json")
    if not os.path.exists(workspace_file):
        raise HTTPException(status_code=404, detail="Project not found")
    with open(workspace_file, 'r', encoding='utf-8') as f:
        project_json = json.load(f)

    history = project_json.get("history_log", [])
    if not isinstance(history, list) or not history:
        raise HTTPException(status_code=400, detail="No history_log found for refresh")
    found = None
    for item in reversed(history):
        if isinstance(item, dict) and str(item.get("id") or "") == str(request.base_script_id):
            found = item
            break
    if not found:
        raise HTTPException(status_code=404, detail="base_script_id not found in project history")

    recipe = (found.get("recipe") or {}) if isinstance(found, dict) else {}
    region_id = str(recipe.get("region") or "").strip()
    platform_id = str(recipe.get("platform") or "").strip()
    angle_id = str(recipe.get("angle") or "").strip()
    if not (region_id and platform_id and angle_id):
        raise HTTPException(status_code=400, detail="History entry missing recipe (region/platform/angle)")

    ensure_knowledge_layout()
    base_dir = str(FACTORS_DIR)
    def read_insight(insight_id: str):
        if not insight_id:
            return {}
        category = insight_id.split('_')[0] + 's'
        path = os.path.join(base_dir, category, f"{insight_id}.json")
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    region_json = read_insight(region_id)
    platform_json = read_insight(platform_id)
    angle_json = read_insight(angle_id)
    gi = (project_json.get("game_info") or {}) if isinstance(project_json, dict) else {}
    game_context = (
        f"Title: {project_json.get('name')}\n"
        f"Core Gameplay: {gi.get('core_gameplay', '')}\n"
        f"USP: {gi.get('core_usp', '')}\n"
        f"Target Persona: {gi.get('target_persona', '')}\n"
        f"Extended Hooks: {gi.get('value_hooks', '')}"
    )
    base_script_context = _script_to_context(found.get("script"))

    rag_context, _, _ = retrieve_context_with_evidence(
        f"{region_id} {platform_id} {angle_id}",
        top_k=4,
        supplement=f"{region_id}\n{platform_id}\n{angle_id}\n{game_context}",
        region_boost_tokens=[str(region_json.get("name"))] if isinstance(region_json, dict) and region_json.get("name") else None,
    )

    prompt = render_copy_prompt(
        game_context=game_context,
        culture_context=region_json if isinstance(region_json, dict) else {},
        platform_rules=platform_json if isinstance(platform_json, dict) else {},
        creative_logic=angle_json if isinstance(angle_json, dict) else {},
        quantity=request.quantity,
        tones=request.tones,
        locales=request.locales,
        base_script_context=base_script_context,
    )
    user_input = f"Market context (optional):\n{rag_context}\n\nReturn refreshed copy matrix JSON only."

    script_id = "COPY-" + uuid.uuid4().hex[:6].upper()
    result_obj: dict[str, Any] = {}
    if request.engine == "local":
        from ollama_client import generate_with_local_llm
        result = generate_with_local_llm(system_prompt=prompt, user_input=user_input, expected_json=True)
        if isinstance(result.output, dict):
            result_obj = result.output
    elif cloud_client:
        try:
            resp = cloud_client.chat.completions.create(
                model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_input},
                ],
            )
            result_obj = json.loads(resp.choices[0].message.content or "{}")
        except Exception as e:
            print(f"Refresh copy failed: {e}")
            result_obj = {}

    acm_raw = result_obj.get("ad_copy_matrix") if isinstance(result_obj, dict) else None
    acm = _normalize_ad_copy_matrix(acm_raw, quantity=request.quantity)
    payload = {
        "script_id": script_id,
        "project_id": request.project_id,
        "ad_copy_matrix": acm,
        "generation_metrics": {
            "mode": "copy_refresh",
            "elapsed_ms": int((time.perf_counter() - t0) * 1000),
            "quantity": int(request.quantity),
            "base_script_id": request.base_script_id,
            "locales": acm.get("locales", []),
        },
    }
    # Tiles + compliance scan (best-effort)
    try:
        from compliance import build_ad_copy_tiles, maybe_generate_rewrite_suggestions, scan_ad_copy

        tiles = build_ad_copy_tiles(acm, region_id=region_id)
        payload["ad_copy_tiles"] = tiles
        compliance_obj = scan_ad_copy(tiles, platform_id=platform_id, region_id=region_id)
        if request.compliance_suggest and cloud_client:
            tiles_by_id = {str(t.get("id")): t for t in tiles if isinstance(t, dict) and t.get("id")}
            suggestions = maybe_generate_rewrite_suggestions(
                cloud_client=cloud_client,
                hits=list(compliance_obj.get("hits") or []),
                tiles_by_id=tiles_by_id,
                output_mode=request.output_mode,
            )
            if suggestions:
                compliance_obj["suggestions"] = suggestions
        payload["compliance"] = compliance_obj
    except Exception:
        pass
    md_rel = export_markdown_after_generate(
        request.project_id,
        str(project_json.get("name") or "Unknown"),
        {
            "region": region_id,
            "platform": platform_id,
            "angle": angle_id,
            "region_name": str(region_json.get("name") or region_id) if isinstance(region_json, dict) else region_id,
            "platform_name": str(platform_json.get("name") or platform_id) if isinstance(platform_json, dict) else platform_id,
            "angle_name": str(angle_json.get("name") or angle_id) if isinstance(angle_json, dict) else angle_id,
            "region_short": str(region_json.get("short_name") or "") if isinstance(region_json, dict) else "",
            "platform_short": str(platform_json.get("short_name") or "") if isinstance(platform_json, dict) else "",
            "angle_short": str(angle_json.get("short_name") or "") if isinstance(angle_json, dict) else "",
        },
        request.engine,
        payload,
        request.output_mode,
    )
    payload["markdown_path"] = md_rel
    record_generate_success(engine=request.engine if request.engine in {"local", "cloud"} else "mock", measured_tokens=0)
    # record history for management UI (refresh)
    try:
        record_history(
            project_json,
            request,
            payload,
            request.engine,
            recipe_override={"region": region_id, "platform": platform_id, "angle": angle_id},
        )
    except Exception:
        pass
    return QuickCopyResponse(**payload)

@app.post("/api/export/pdf")
def export_pdf(request: GeneratePdfRequest):
    if not _is_valid_script_payload(request.data):
        raise HTTPException(status_code=400, detail="Invalid script payload for PDF export.")
    if _looks_like_error_placeholder(request.data):
        raise HTTPException(status_code=400, detail="Refusing to export error placeholder content.")
    try:
        pdf_b64 = generate_pdf_report(request.data)
        return {"success": True, "pdf_base64": pdf_b64}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class ExtractUrlRequest(BaseModel):
    url: str
    engine: str = Field(default="cloud", description="The LLM source engine (cloud or local)")

class ExtractUrlResponse(BaseModel):
    success: bool
    title: str = ""
    extracted_usp: str = ""
    error: str = ""

@app.get("/api/usage/summary")
def usage_summary():
    """Daily usage snapshot: Oracle ops + LLM tokens (provider usage when available)."""
    return usage_get_summary()


@app.post("/api/extract-url", response_model=ExtractUrlResponse)
def extract_url(request: ExtractUrlRequest):
    data = fetch_playstore_data(request.url)
    
    if not data["success"]:
        return {"success": False, "error": data.get("error", "Failed to parse.")}
        
    if request.engine == 'cloud' and cloud_client:
        from scraper import EXTRACT_USP_VIA_LLM_SYSTEM_PROMPT, _serialize_director_archive, _validate_director_archive
        import json
        desc = data.get("description", "")[:1500]
        genre = data.get("genre", "Game")
        installs = data.get("installs", "Unknown")
        recent_changes = data.get("recentChanges", "")[:300]
        
        user_prompt = (
            f"Game title: {data.get('title')}\n"
            f"Genre (store): {genre}\n"
            f"Installs (store label): {installs}\n"
            f"Recent changes / What's new:\n{recent_changes}\n\n"
            f"--- Raw store description (may truncate) ---\n{desc}\n"
        )
        try:
            response = cloud_client.chat.completions.create(
                model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
                response_format={ "type": "json_object" },
                messages=[
                    {"role": "system", "content": EXTRACT_USP_VIA_LLM_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ]
            )
            raw_content = response.choices[0].message.content
            parsed = json.loads(raw_content)
            
            if _validate_director_archive(parsed):
                extracted_usp = _serialize_director_archive(parsed, installs, recent_changes)
                extract_tokens = total_tokens_from_completion(response)
                extract_used_llm = True
            else:
                raise ValueError("JSON validation failed")
        except Exception as e:
            print(f"Cloud extract failed, fallback: {e}")
            from scraper import extract_usp_via_llm_with_usage as ext_fallback
            extracted_usp, extract_tokens, extract_used_llm = ext_fallback(data["title"], data, "mock")
    else:
        from scraper import extract_usp_via_llm_with_usage as ext_fallback
        extracted_usp, extract_tokens, extract_used_llm = ext_fallback(data["title"], data, request.engine)
    record_extract_url_success(
        request.engine,
        measured_tokens=extract_tokens,
        used_llm=extract_used_llm,
    )
    return {
        "success": True,
        "title": data["title"],
        "extracted_usp": extracted_usp
    }

class IngestRequest(BaseModel):
    raw_text: str = ""
    source_url: str
    year_quarter: str = "Unknown Date"

class IngestResponse(BaseModel):
    success: bool
    extracted_count: int = 0
    error: str = ""

@app.post("/api/refinery/ingest", response_model=IngestResponse)
def ingest_report(request: IngestRequest):
    result = distill_and_store(request.raw_text, request.source_url, request.year_quarter)
    success = result.get("success", False)
    if success:
        record_oracle_ingest_success()
    return {
        "success": success,
        "extracted_count": result.get("extracted_count", 0),
        "error": result.get("error", "")
    }

@app.get("/api/refinery/stats")
def get_refinery_stats():
    from refinery import get_collection_stats
    return get_collection_stats()

class RecommendStrategyRequest(BaseModel):
    title: str
    core_gameplay: str
    core_usp: str
    region: str
    platform: str

class RecommendStrategyResponse(BaseModel):
    region_analysis: str
    platform_analysis: str

@app.post("/api/refinery/recommend-strategy", response_model=RecommendStrategyResponse)
def recommend_strategy(request: RecommendStrategyRequest):
    if cloud_client:
        prompt = f"""You are an elite UA strategy manager.
Given Game: {request.title}
Gameplay: {request.core_gameplay}
USP: {request.core_usp}
Target Region: {request.region}
Target Platform: {request.platform}

Output a JSON with two keys:
1. "region_analysis": A 1-2 sentence tactical insight on what this culture/region wants.
2. "platform_analysis": A 1-2 sentence tactical insight for this platform.
Keep it strictly technical and UA focused."""
        try:
            response = cloud_client.chat.completions.create(
                model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
                response_format={ "type": "json_object" },
                messages=[{"role": "user", "content": prompt}]
            )
            raw = response.choices[0].message.content
            import json
            parsed = json.loads(raw)
            return RecommendStrategyResponse(
                region_analysis=parsed.get("region_analysis", f"Emphasis on {request.region} localized visuals."),
                platform_analysis=parsed.get("platform_analysis", f"First 3 seconds hook for {request.platform}.")
            )
        except Exception as e:
            print(f"Recommend error: {e}")
            pass
            
    # Mock fallback
    return RecommendStrategyResponse(
        region_analysis=f"Recommended for {request.region}: Culturally resonant voiceovers and targeted localization.",
        platform_analysis=f"Recommended for {request.platform}: Format matching with fast jump cuts targeting user behavior."
    )


@app.get("/api/insights/metadata")
def get_insights_metadata():
    """Reads the JSON DB and returns available config options for frontend."""
    import os, json
    ensure_knowledge_layout()
    base_dir = str(FACTORS_DIR)
    if not os.path.exists(base_dir):
        return {"regions": [], "platforms": [], "angles": []}
    
    regions, platforms, angles = [], [], []
    for category_dir, target_list in [('regions', regions), ('platforms', platforms), ('angles', angles)]:
        dir_path = os.path.join(base_dir, category_dir)
        if not os.path.exists(dir_path): continue
        for f in os.listdir(dir_path):
            if not f.endswith('.json'): continue
            with open(os.path.join(dir_path, f), 'r', encoding='utf-8') as file:
                data = json.load(file)
                target_list.append(data)
                
    return {"regions": regions, "platforms": platforms, "angles": angles}

class InsightManageRequest(BaseModel):
    category: str
    insight_id: str
    content: dict

@app.post("/api/insights/manage/update")
def update_insight(req: InsightManageRequest):
    import os, json
    ensure_knowledge_layout()
    base_dir = str(FACTORS_DIR)
    target_dir = os.path.join(base_dir, req.category)
    os.makedirs(target_dir, exist_ok=True)
    file_path = os.path.join(target_dir, f"{req.insight_id}.json")
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(req.content, f, ensure_ascii=False, indent=4)
    return {"success": True}

class InsightDeleteRequest(BaseModel):
    category: str
    insight_id: str

@app.post("/api/insights/manage/delete")
def delete_insight(req: InsightDeleteRequest):
    import os
    ensure_knowledge_layout()
    base_dir = str(FACTORS_DIR)
    file_path = os.path.join(base_dir, req.category, f"{req.insight_id}.json")
    if os.path.exists(file_path):
        os.remove(file_path)
        return {"success": True}
    return {"success": False, "error": "Not found"}


def generate_script_local(
    request: GenerateScriptRequest,
    final_prompt: str,
    *,
    rag_supplement: str = "",
    region_boost_tokens: list[str] | None = None,
) -> dict[str, Any]:
    """Run director synthesis via local Ollama; merges RAG citations from retrieve_context."""
    from ollama_client import generate_with_local_llm

    ctx, citations, evidence = retrieve_context_with_evidence(
        f"{request.region_id} {request.platform_id} {request.angle_id}",
        top_k=5,
        supplement=rag_supplement,
        region_boost_tokens=region_boost_tokens,
    )
    user_input = (
        f"Oracle / market context (may be empty):\n{ctx}\n\n"
        "Produce one JSON object with all required director script fields (hook scores, script lines, etc.)."
    )
    result = generate_with_local_llm(system_prompt=final_prompt, user_input=user_input, expected_json=True)
    out = _normalize_script_lines(result.output) if isinstance(result.output, dict) else result.output
    if not isinstance(out, dict):
        return {
            "success": False,
            "error_code": "LOCAL_JSON_PARSE_FAILED",
            "error_message": "Local model output is not a JSON object.",
            "raw_excerpt": str(out)[:500],
        }
    if out.get("success") is False:
        return out
    merged = dict(out)
    if not merged.get("citations"):
        merged["citations"] = list(citations or [])
    if not merged.get("rag_evidence"):
        merged["rag_evidence"] = evidence
    return merged


def generate_draft_local(system_prompt: str, user_input: str) -> dict[str, Any]:
    """Stage-1 draft generation on local engine."""
    from ollama_client import generate_with_local_llm

    result = generate_with_local_llm(system_prompt=system_prompt, user_input=user_input, expected_json=True)
    out = result.output
    if isinstance(out, dict):
        return out
    return {"drafts": [], "pick_recommendation": ""}


@app.post("/api/generate", response_model=GenerateScriptResponse)
def generate_script(request: GenerateScriptRequest):
    import os, json
    import time
    from prompts import render_draft_prompt, render_director_prompt

    t0 = time.perf_counter()
    mode = (request.mode or "auto").strip().lower()
    if mode not in {"draft", "director", "auto"}:
        mode = "auto"

    # 1. READ DATABASES
    project_json = {"name": "Unknown", "game_info": {"core_usp": "Generic Game"}}
    workspace_file = os.path.join(os.path.dirname(__file__), 'data', 'workspaces', f"{request.project_id}.json")
    if os.path.exists(workspace_file):
        with open(workspace_file, 'r', encoding='utf-8') as f:
            project_json = json.load(f)
    
    # Get Atomic Insights
    ensure_knowledge_layout()
    base_dir = str(FACTORS_DIR)
    def read_insight(insight_id: str):
        if not insight_id: return {"error": "not provided"}
        category = insight_id.split('_')[0] + 's' # 'region' -> 'regions'
        path = os.path.join(base_dir, category, f"{insight_id}.json")
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"error": "not found"}

    region_json = read_insight(request.region_id)
    platform_json = read_insight(request.platform_id)
    angle_json = read_insight(request.angle_id)

    gi = project_json.get('game_info', {})
    game_context = (
        f"Title: {project_json.get('name')}\n"
        f"Core Gameplay: {gi.get('core_gameplay', '')}\n"
        f"USP: {gi.get('core_usp', '')}\n"
        f"Target Persona: {gi.get('target_persona', '')}\n"
        f"Extended Hooks: {gi.get('value_hooks', '')}"
    )
    from usage_tracker import record_generate_success
    script_id = "SOP-" + uuid.uuid4().hex[:6].upper()

    def record_history(project_data, req, resp_dict, engine, *, recipe_override: dict[str, str] | None = None):
        try:
            if not project_data.get('id') or project_data.get('id') == "Unknown": return
            from projects_api import save_project
            if 'history_log' not in project_data:
                project_data['history_log'] = []
            
            import uuid
            recipe = recipe_override or {"region": req.region_id, "platform": req.platform_id, "angle": req.angle_id}
            project_data['history_log'].append({
                "id": resp_dict.get('script_id') or str(uuid.uuid4()),
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "engine": engine,
                "recipe": recipe,
                "output_kind": "copy" if str(resp_dict.get("script_id", "")).startswith("COPY-") else "sop",
                "output_mode": str(req.output_mode or "cn"),
                "markdown_path": resp_dict.get("markdown_path"),
                "generation_metrics": resp_dict.get("generation_metrics"),
                "compliance": resp_dict.get("compliance"),
                "ad_copy_matrix": resp_dict.get("ad_copy_matrix"),
                "ad_copy_tiles": resp_dict.get("ad_copy_tiles"),
                "script": resp_dict.get('script', []),
            })
            save_project(project_data)
        except Exception as e:
            print(f"Failed to record history: {e}")

    def build_rag_supplement() -> tuple[str, list[str], list[dict]]:
        rag_parts: list[str] = [request.region_id, request.platform_id, request.angle_id, game_context]
        if isinstance(region_json, dict):
            n = region_json.get("name")
            if n:
                rag_parts.append(str(n))
            for key in ("culture_notes", "creative_hooks", "focus"):
                val = region_json.get(key)
                if isinstance(val, list):
                    rag_parts.append(" ".join(str(x) for x in val[:6]))
                elif isinstance(val, str) and val:
                    rag_parts.append(val[:800])
        if isinstance(platform_json, dict):
            specs = platform_json.get("specs")
            if isinstance(specs, dict):
                fmt = specs.get("format")
                if isinstance(fmt, list):
                    rag_parts.append(" ".join(str(x) for x in fmt))
                for sk in ("pacing", "safe_zone"):
                    sv = specs.get(sk)
                    if isinstance(sv, str) and sv:
                        rag_parts.append(sv[:500])
            elif isinstance(specs, list):
                rag_parts.append(" ".join(str(x) for x in specs[:8]))
            ph = platform_json.get("psychological_hooks")
            if isinstance(ph, list):
                rag_parts.append(" ".join(str(x) for x in ph[:6]))
            for key in ("name", "native_behavior", "focus"):
                v = platform_json.get(key)
                if isinstance(v, str) and v:
                    rag_parts.append(v[:600])
        if isinstance(angle_json, dict):
            for key in ("name", "core_emotion", "logic_steps"):
                v = angle_json.get(key)
                if isinstance(v, list):
                    rag_parts.append(" ".join(str(x) for x in v[:8]))
                elif isinstance(v, str) and v:
                    rag_parts.append(v[:600])
        rag_supplement = "\n".join(p for p in rag_parts if p)
        region_boost: list[str] = []
        if isinstance(region_json, dict) and region_json.get("name"):
            region_boost.append(str(region_json["name"]))
        ctx, citations, evidence = retrieve_context_with_evidence(
            f"{request.region_id} {request.platform_id} {request.angle_id}",
            top_k=5,
            supplement=rag_supplement,
            region_boost_tokens=region_boost or None,
        )
        return ctx, citations, evidence

    def finalize_response(
        resp: dict[str, Any],
        engine_label: str,
        *,
        drafts: list[dict] | None = None,
        evidence: list[dict] | None = None,
    ) -> GenerateScriptResponse:
        resp = _normalize_script_lines(resp)
        resp.setdefault("citations", [])
        if resp.get("cultural_notes") is None:
            resp["cultural_notes"] = []
        # Enforce Ad Copy Matrix requirements (best-effort backfill)
        resp = _ensure_ad_copy_matrix(
            resp,
            angle_name=str(angle_json.get("name", request.angle_id)) if isinstance(angle_json, dict) else request.angle_id,
            platform_name=str(platform_json.get("name", request.platform_id)) if isinstance(platform_json, dict) else request.platform_id,
            region_name=str(region_json.get("name", request.region_id)) if isinstance(region_json, dict) else request.region_id,
        )
        review = _build_script_review(
            resp,
            core_gameplay=str(gi.get("core_gameplay", "")),
            angle_name=str(angle_json.get("name", request.angle_id)) if isinstance(angle_json, dict) else request.angle_id,
        )
        resp["review"] = review
        # Build render-friendly ad copy tiles + compliance scan (best-effort; never fail the request)
        try:
            from compliance import (
                build_ad_copy_tiles,
                maybe_generate_rewrite_suggestions,
                scan_ad_copy,
            )

            tiles = build_ad_copy_tiles(resp.get("ad_copy_matrix"), region_id=request.region_id)
            resp["ad_copy_tiles"] = tiles
            compliance_obj = scan_ad_copy(tiles, platform_id=request.platform_id, region_id=request.region_id)
            if request.compliance_suggest and cloud_client:
                tiles_by_id = {str(t.get("id")): t for t in tiles if isinstance(t, dict) and t.get("id")}
                suggestions = maybe_generate_rewrite_suggestions(
                    cloud_client=cloud_client,
                    hits=list(compliance_obj.get("hits") or []),
                    tiles_by_id=tiles_by_id,
                    output_mode=request.output_mode,
                )
                if suggestions:
                    compliance_obj["suggestions"] = suggestions
            resp["compliance"] = compliance_obj
        except Exception:
            resp["ad_copy_tiles"] = resp.get("ad_copy_tiles") or []
            resp["compliance"] = resp.get("compliance") or {"risk_level": "unknown", "hits": []}
        if drafts:
            resp["drafts"] = drafts
        if evidence:
            resp["rag_evidence"] = evidence
        resp["generation_metrics"] = {
            "mode": mode,
            "elapsed_ms": int((time.perf_counter() - t0) * 1000),
            "rag_rules_used": len(evidence or []),
        }
        md_rel = export_markdown_after_generate(
            request.project_id,
            str(project_json.get("name") or "Unknown"),
            {
                "region": request.region_id,
                "platform": request.platform_id,
                "angle": request.angle_id,
                "region_name": str(region_json.get("name") or request.region_id) if isinstance(region_json, dict) else request.region_id,
                "platform_name": str(platform_json.get("name") or request.platform_id) if isinstance(platform_json, dict) else request.platform_id,
                "angle_name": str(angle_json.get("name") or request.angle_id) if isinstance(angle_json, dict) else request.angle_id,
                "region_short": str(region_json.get("short_name") or "") if isinstance(region_json, dict) else "",
                "platform_short": str(platform_json.get("short_name") or "") if isinstance(platform_json, dict) else "",
                "angle_short": str(angle_json.get("short_name") or "") if isinstance(angle_json, dict) else "",
            },
            engine_label,
            resp,
            request.output_mode,
        )
        payload = {**resp, "markdown_path": md_rel}
        return GenerateScriptResponse(**payload)

    # shared context
    rag_context, rag_citations, rag_evidence = build_rag_supplement()
    selected_draft: dict[str, Any] | None = None
    drafts: list[dict] = []

    # 2. DRAFT STAGE
    if mode in {"draft", "auto"}:
        draft_prompt = render_draft_prompt(
            game_context=game_context,
            culture_context=region_json,
            platform_rules=platform_json,
            creative_logic=angle_json,
        )
        draft_user = f"Market context:\n{rag_context}\n\nReturn draft concepts JSON only."
        if request.engine == "local":
            draft_payload = generate_draft_local(draft_prompt, draft_user)
        elif cloud_client:
            try:
                dresp = cloud_client.chat.completions.create(
                    model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": draft_prompt},
                        {"role": "user", "content": draft_user},
                    ],
                )
                draft_payload = json.loads(dresp.choices[0].message.content or "{}")
            except Exception as e:
                print(f"Draft stage failed: {e}")
                draft_payload = {}
        else:
            draft_payload = {
                "drafts": [
                    {
                        "id": "D1",
                        "title": "Fast hook to gameplay",
                        "hook": "Start with high-stakes fail then immediate gameplay correction.",
                        "story_arc": "mistake -> retry -> clean payoff",
                        "gameplay_bridge": "show true game mechanic within 2 shots",
                        "risk_flags": [],
                        "estimated_ctr": 80,
                        "estimated_quality": 78,
                    }
                ],
                "pick_recommendation": "D1",
            }
        drafts, selected_draft = _pick_top_draft(draft_payload)
        if mode == "draft":
            base_line = {
                "time": "0s",
                "visual": str((selected_draft or {}).get("hook", "Hook gameplay concept")),
                "visual_meaning": str((selected_draft or {}).get("gameplay_bridge", "前2镜完成与玩法闭环")),
                "audio_content": "Voiceover placeholder",
                "audio_meaning": "根据入选草案补齐导演口播情绪与节奏。",
                "text_content": "On-screen text placeholder",
                "text_meaning": "根据草案补齐贴纸文案意图。",
                "direction_note": "草案模式：先用于创意评审，再进入导演定稿。",
                "sfx_transition_note": "草案模式：标记关键节拍点，待定稿补充细节。",
            }
            draft_resp = {
                "script_id": script_id,
                "hook_score": _safe_int((selected_draft or {}).get("estimated_ctr"), 70),
                "hook_reasoning": f"Selected draft: {(selected_draft or {}).get('title', 'N/A')}",
                "clarity_score": _safe_int((selected_draft or {}).get("estimated_quality"), 70),
                "clarity_reasoning": "Draft mode prioritizes ideation speed over full production details.",
                "conversion_score": 70,
                "conversion_reasoning": "Conversion is estimated only at draft stage.",
                "bgm_direction": "Draft stage placeholder",
                "editing_rhythm": "Draft stage placeholder",
                "script": [base_line],
                "psychology_insight": str((selected_draft or {}).get("story_arc", "")),
                "cultural_notes": [str((selected_draft or {}).get("gameplay_bridge", ""))],
                "competitor_trend": "Draft stage only",
                "citations": rag_citations,
            }
            record_generate_success(engine=request.engine if request.engine in {"local", "cloud"} else "mock", measured_tokens=0)
            finalized = finalize_response(draft_resp, request.engine, drafts=drafts, evidence=rag_evidence)
            record_history(project_json, request, finalized.model_dump(), request.engine)
            return finalized

    # 3. DIRECTOR STAGE
    director_prompt = render_director_prompt(
        game_context=game_context,
        culture_context=region_json,
        platform_rules=platform_json,
        creative_logic=angle_json,
        selected_draft_json=json.dumps(selected_draft, ensure_ascii=False) if selected_draft else "",
    )
    _print_console_safe("\n[ATOMIC DB SYNTHESIS SUCCESS - SUPER CONTEXT GENERATED]")
    _print_console_safe(director_prompt)

    if request.engine == "local":
        rag_supplement = f"{rag_context}\n\nSelected Draft:\n{json.dumps(selected_draft or {}, ensure_ascii=False)}"
        region_boost = [str(region_json.get("name"))] if isinstance(region_json, dict) and region_json.get("name") else None
        resp = generate_script_local(
            request,
            director_prompt,
            rag_supplement=rag_supplement,
            region_boost_tokens=region_boost,
        )
        if resp.get("success") is False:
            raise HTTPException(
                status_code=502,
                detail={
                    "error_code": resp.get("error_code", "LOCAL_UNKNOWN"),
                    "error_message": resp.get("error_message", ""),
                    "raw_excerpt": resp.get("raw_excerpt", ""),
                },
            )
        if not _is_valid_script_payload(resp):
            raise HTTPException(
                status_code=502,
                detail={
                    "error_code": "LOCAL_SCHEMA_MISMATCH",
                    "error_message": "Local model output failed schema validation.",
                    "raw_excerpt": json.dumps(resp, ensure_ascii=False)[:500],
                },
            )
        resp["script_id"] = script_id
        resp.setdefault("citations", rag_citations)
        record_generate_success(engine='local', measured_tokens=0)
        finalized = finalize_response(resp, "local", drafts=drafts, evidence=rag_evidence)
        record_history(project_json, request, finalized.model_dump(), "local")
        return finalized

    if cloud_client:
        try:
            response = cloud_client.chat.completions.create(
                model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
                messages=[
                    {"role": "system", "content": director_prompt},
                    {
                        "role": "user",
                        "content": (
                            f"Market context:\n{rag_context}\n\n"
                            f"Selected draft:\n{json.dumps(selected_draft or {}, ensure_ascii=False)}\n\n"
                            "Please generate the final director script JSON."
                        ),
                    },
                ],
                response_format={"type": "json_object"},
            )
            raw = response.choices[0].message.content
            parsed = _normalize_script_lines(json.loads(raw))
            parsed["script_id"] = script_id
            parsed.setdefault("citations", rag_citations)
            if parsed.get("cultural_notes") is None:
                parsed["cultural_notes"] = []
            record_generate_success(engine='cloud', measured_tokens=0)
            finalized = finalize_response(parsed, "cloud", drafts=drafts, evidence=rag_evidence)
            record_history(project_json, request, finalized.model_dump(), "cloud")
            return finalized
        except Exception as e:
            print(f"Synthesis Engine failed: {e}")

    record_generate_success(engine='mock', measured_tokens=0)
    # 4. MOCK fallback
    def _platform_editing_rhythm(pj: dict[str, Any]) -> str:
        s = pj.get("specs")
        if isinstance(s, list) and len(s) > 0:
            return str(s[0])
        if isinstance(s, dict) and s:
            return str(next(iter(s.values())))
        return "Standard cuts"

    def _angle_visual_step(aj: dict[str, Any]) -> str:
        steps = aj.get("logic_steps")
        if isinstance(steps, list) and len(steps) > 0:
            return str(steps[0])
        return "Action"

    mock_resp = {
        "script_id": script_id,
        "hook_score": 95,
        "hook_reasoning": "Synthesized context match guaranteed.",
        "clarity_score": 90,
        "clarity_reasoning": "Direct mapping from atomic DB rules.",
        "conversion_score": 95,
        "conversion_reasoning": "High emotional resonance based on Angle isolation.",
        "bgm_direction": region_json.get('preferred_bgm', 'Epic Score'),
        "editing_rhythm": _platform_editing_rhythm(platform_json),
        "script": [
            {
                "time": "0s",
                "visual": _angle_visual_step(angle_json),
                "visual_meaning": "中文画面说明：突出核心玩法动作与结果反馈，避免仿系统原生 UI 误导。",
                "audio_content": "Native Voiceover (Simulated)",
                "audio_meaning": "哦不！（语气：夸张但不刺耳；节奏：短促）",
                "text_content": "Local text",
                "text_meaning": "提示文案",
                "direction_note": "导演提示：前 2 秒快节奏钩子，随后切入真实玩法并放慢镜头展示反馈。",
                "sfx_transition_note": "后期提示：失误点后插入 0.15-0.25 秒静音真空，再进 ASMR 或主 BGM。"
            }
        ],
        "psychology_insight": angle_json.get('core_emotion', 'None'),
        "cultural_notes": region_json.get('culture_notes', []),
        "competitor_trend": "Mock trend based on resonance",
        "citations": [f"JSON: {request.region_id}", f"JSON: {request.platform_id}", f"JSON: {request.angle_id}"]
    }
    finalized = finalize_response(mock_resp, "mock", drafts=drafts, evidence=rag_evidence)
    record_history(project_json, request, finalized.model_dump(), "mock")
    return finalized
