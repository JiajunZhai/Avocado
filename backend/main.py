from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import os
import sys
import json
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

@app.get("/")
def read_root():
    return {"status": "ok", "message": "AdCreative AI Engine Sandbox is running"}


from scraper import fetch_playstore_data, extract_usp_via_llm_with_usage
from exporter import generate_pdf_report
from refinery import retrieve_context, distill_and_store
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
        if audio_meaning and "语气" not in audio_meaning and "节奏" not in audio_meaning:
            line["audio_meaning"] = f"{audio_meaning}（语气：自然口语；节奏：短句有力）"
    return payload

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

    ctx, citations = retrieve_context(
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
    return merged


@app.post("/api/generate", response_model=GenerateScriptResponse)
def generate_script(request: GenerateScriptRequest):
    import os, json
    from prompts import render_system_prompt

    # 1. READ DATABASES (MOCK DB FETCH)
    # Get Workspace / Project DNA
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

    # 2. RUN RECIPE SYNTHESIS
    final_prompt = render_system_prompt(
        game_context=game_context,
        culture_context=region_json,
        platform_rules=platform_json,
        creative_logic=angle_json
    )

    print("\n[ATOMIC DB SYNTHESIS SUCCESS - SUPER CONTEXT GENERATED]")
    _print_console_safe(final_prompt)
    
    from usage_tracker import record_generate_success

    def record_history(project_data, req, resp_dict, engine):
        try:
            if not project_data.get('id') or project_data.get('id') == "Unknown": return
            from projects_api import save_project
            if 'history_log' not in project_data:
                project_data['history_log'] = []
            
            import uuid
            project_data['history_log'].append({
                "id": resp_dict.get('script_id') or str(uuid.uuid4()),
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "engine": engine,
                "recipe": {"region": req.region_id, "platform": req.platform_id, "angle": req.angle_id},
                "script": resp_dict.get('script', [])
            })
            save_project(project_data)
        except Exception as e:
            print(f"Failed to record history: {e}")

    def finalize_response(resp: dict[str, Any], engine_label: str) -> GenerateScriptResponse:
        resp = _normalize_script_lines(resp)
        resp.setdefault("citations", [])
        if resp.get("cultural_notes") is None:
            resp["cultural_notes"] = []
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

    # 3. IF LOCAL ENGINE PREFERRED
    script_id = "SOP-" + uuid.uuid4().hex[:6].upper()
    if request.engine == 'local':
        rag_parts: list[str] = [
            request.region_id,
            request.platform_id,
            request.angle_id,
            game_context,
        ]
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
        resp = generate_script_local(
            request,
            final_prompt,
            rag_supplement=rag_supplement,
            region_boost_tokens=region_boost or None,
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
        record_history(project_json, request, resp, "local")
        return finalize_response(resp, "local")

    # 4. DEFAULT CLOUD CLUSTER
    if cloud_client:
        try:
            response = cloud_client.chat.completions.create(
                model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
                messages=[ 
                    {"role": "system", "content": final_prompt},
                    {"role": "user", "content": "Please generate the script JSON based on this context."}
                ],
                response_format={ "type": "json_object" }
            )
            raw = response.choices[0].message.content
            parsed = json.loads(raw)
            parsed = _normalize_script_lines(parsed)
            parsed["script_id"] = script_id
            parsed.setdefault("citations", [])
            if parsed.get("cultural_notes") is None:
                parsed["cultural_notes"] = []
            record_generate_success(engine='cloud', measured_tokens=0)
            record_history(project_json, request, parsed, 'cloud')
            return finalize_response(parsed, "cloud")
        except Exception as e:
            print(f"Synthesis Engine failed: {e}")
            pass

    record_generate_success(engine='mock', measured_tokens=0)
    # Mock fallback
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
    record_history(project_json, request, mock_resp, 'mock')
    return finalize_response(mock_resp, "mock")
