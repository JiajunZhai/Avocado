"""Write Lab / SOP synthesis results as Markdown under repository @OUT/."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

_OUT_DIR_NAME = "@OUT"
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def _contains_cjk(s: str) -> bool:
    return bool(_CJK_RE.search(s or ""))


def _should_translate(text: str, mode: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    if mode == "cn":
        return not _contains_cjk(t)
    return _contains_cjk(t)


def _translate_batch(texts: list[str], mode: str) -> list[str]:
    """
    Best-effort translation using DeepSeek/OpenAI-compatible endpoint.
    Falls back to original texts when API key is unavailable or request fails.
    """
    if not texts:
        return texts
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        return texts
    try:
        from openai import OpenAI

        client = OpenAI(
            api_key=api_key,
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        )
        target = "简体中文" if mode == "cn" else "English"
        system = (
            "You are a translation engine for ad production docs. "
            "Translate each input string into target language only. "
            "Keep brand names, IDs, URLs, and numbers unchanged. "
            "Return strict JSON object: {\"items\":[\"...\", ...]} with same length."
        )
        user = json.dumps({"target": target, "items": texts}, ensure_ascii=False)
        resp = client.chat.completions.create(
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        raw = resp.choices[0].message.content or ""
        parsed = json.loads(raw)
        items = parsed.get("items")
        if isinstance(items, list) and len(items) == len(texts):
            return [str(x) for x in items]
        return texts
    except Exception:
        return texts


def _translate_for_mode(text: str, mode: str) -> str:
    if not _should_translate(text, mode):
        return text
    out = _translate_batch([text], mode)
    return out[0] if out else text


def repo_root() -> Path:
    """backend/ -> parent -> monorepo root."""
    return Path(__file__).resolve().parent.parent


def _safe_path_segment(value: str, max_len: int = 160) -> str:
    s = re.sub(r"[^\w.\-]+", "_", value.strip(), flags=re.UNICODE)
    s = s.strip("._") or "unknown"
    return s[:max_len]


def synthesis_to_markdown(
    project_name: str,
    recipe: dict[str, str],
    engine: str,
    payload: dict[str, Any],
    output_mode: str = "cn",
) -> str:
    """Build a readable Markdown document from a generate API payload dict."""
    mode = (output_mode or "cn").strip().lower()
    if mode not in {"cn", "en"}:
        mode = "cn"
    sid = payload.get("script_id", "")
    # Quick Copy Mode: render a copywriting booklet instead of storyboard table
    acm = payload.get("ad_copy_matrix")
    script = payload.get("script")
    if isinstance(acm, dict) and not isinstance(script, list):
        def loc(v: Any) -> str:
            return _translate_for_mode(str(v or ""), mode)

        title = "# 文案矩阵" if mode == "cn" else "# Ad Copy Matrix"
        lines: list[str] = [
            title + f"：{project_name}",
            "",
            f"- **Project**: {project_name}",
            f"- **Copy ID**: `{sid}`",
            f"- **Engine**: `{engine}`",
            f"- **Region**: `{recipe.get('region', '')}`",
            f"- **Platform**: `{recipe.get('platform', '')}`",
            f"- **Angle**: `{recipe.get('angle', '')}`",
            "",
        ]
        variants = acm.get("variants")
        default_locale = str(acm.get("default_locale") or "en")
        locales = acm.get("locales") if isinstance(acm.get("locales"), list) else [default_locale]
        if not isinstance(variants, dict):
            variants = {default_locale: acm}
        for loc_code in [str(x) for x in locales if str(x).strip()]:
            v = variants.get(loc_code) if isinstance(variants, dict) else None
            if not isinstance(v, dict):
                continue
            headlines = v.get("headlines") if isinstance(v.get("headlines"), list) else []
            primary = v.get("primary_texts") if isinstance(v.get("primary_texts"), list) else []
            hashtags = v.get("hashtags") if isinstance(v.get("hashtags"), list) else []

            if mode == "cn":
                lines.extend([f"## 🌍 语言：{loc_code}", "", "## 🎯 核心标题集 (Headlines)", ""])
            else:
                lines.extend([f"## 🌍 Locale: {loc_code}", "", "## 🎯 Headlines", ""])
            for h in headlines:
                lines.append(f"- {h}")

            if mode == "cn":
                lines.extend(["", "## 📝 深度描述集 (Primary Texts)", ""])
            else:
                lines.extend(["", "## 📝 Primary Texts", ""])
            for p in primary:
                lines.append(f"- {p}")

            if mode == "cn":
                lines.extend(["", "## # 标签 (Hashtags)", ""])
            else:
                lines.extend(["", "## # Hashtags", ""])
            if hashtags:
                lines.append(" ".join(str(x) for x in hashtags))
            else:
                lines.append("_（无）_" if mode == "cn" else "_(none)_")
            lines.append("")

        # Optional: expert summary
        if mode == "cn":
            lines.extend(["## 🕵️‍♂️ 专家总结", "", "本次输出为极速文案模式：不生成分镜，仅用于日更买量测试。"])
        else:
            lines.extend(["## 🕵️‍♂️ Expert Notes", "", "Quick Copy Mode output: no storyboard; optimized for daily UA iteration."])
        return "\n".join(lines)

    def loc(v: Any) -> str:
        return _translate_for_mode(str(v or ""), mode)
    if mode == "en":
        lines: list[str] = [
            "# Video Script (SOP Output)",
            "",
            f"- **Project**: {project_name}",
            f"- **Script ID**: `{sid}`",
            f"- **Engine**: `{engine}`",
            f"- **Region**: `{recipe.get('region', '')}`",
            f"- **Platform**: `{recipe.get('platform', '')}`",
            f"- **Angle**: `{recipe.get('angle', '')}`",
            "",
            "## Scores",
            "",
            f"- **Hook** ({payload.get('hook_score')}/100): {loc(payload.get('hook_reasoning', ''))}",
            f"- **Clarity** ({payload.get('clarity_score')}/100): {loc(payload.get('clarity_reasoning', ''))}",
            f"- **Conversion** ({payload.get('conversion_score')}/100): {loc(payload.get('conversion_reasoning', ''))}",
            "",
            "## Production Params",
            "",
            f"- **BGM**: {loc(payload.get('bgm_direction', ''))}",
            f"- **Editing Rhythm**: {loc(payload.get('editing_rhythm', ''))}",
            "",
            "## Psychology Insight",
            "",
            loc(payload.get("psychology_insight", "")),
            "",
            "## Cultural + Competitor Notes",
            "",
        ]
    else:
        lines = [
            "# 素材脚本（SOP 合成输出）",
            "",
            f"- **项目**: {project_name}",
            f"- **Script ID**: `{sid}`",
            f"- **引擎**: `{engine}`",
            f"- **Region**: `{recipe.get('region', '')}`",
            f"- **Platform**: `{recipe.get('platform', '')}`",
            f"- **Angle**: `{recipe.get('angle', '')}`",
            "",
            "## 指标",
            "",
            f"- **Hook** ({payload.get('hook_score')}/100): {loc(payload.get('hook_reasoning', ''))}",
            f"- **Clarity** ({payload.get('clarity_score')}/100): {loc(payload.get('clarity_reasoning', ''))}",
            f"- **Conversion** ({payload.get('conversion_score')}/100): {loc(payload.get('conversion_reasoning', ''))}",
            "",
            "## 制作参数",
            "",
            f"- **BGM**: {loc(payload.get('bgm_direction', ''))}",
            f"- **剪辑节奏**: {loc(payload.get('editing_rhythm', ''))}",
            "",
            "## 心理学洞察",
            "",
            loc(payload.get("psychology_insight", "")),
            "",
            "## 文化与竞品",
            "",
        ]
    notes = payload.get("cultural_notes") or []
    if isinstance(notes, list) and notes:
        for n in notes:
            lines.append(f"- {loc(n)}")
    else:
        lines.append("_（无）_")
    if mode == "en":
        lines.extend(["", "## Competitor Trend", "", loc(payload.get("competitor_trend", "")), "", "## Storyboard", ""])
    else:
        lines.extend(["", "## 竞品趋势", "", loc(payload.get("competitor_trend", "")), "", "## 分镜脚本", ""])

    script = payload.get("script") or []
    if isinstance(script, list):
        for i, line in enumerate(script, start=1):
            if not isinstance(line, dict):
                continue
            if mode == "en":
                lines.append(f"### Shot {i} - {line.get('time', '')}")
                lines.extend(
                    [
                        "",
                        f"**Visual**: {loc(line.get('visual', ''))}",
                        "",
                        f"**Voiceover**: {line.get('audio_content', '')}",
                        "",
                        f"**VO Notes**: {loc(line.get('audio_meaning', ''))}",
                        "",
                        f"**On-screen Text**: {line.get('text_content', '')}",
                        "",
                        f"**Text Notes**: {loc(line.get('text_meaning', ''))}",
                        "",
                        f"**Director Notes**: {loc(line.get('direction_note', ''))}",
                        "",
                        f"**SFX/Transition Notes**: {loc(line.get('sfx_transition_note', ''))}",
                        "",
                    ]
                )
            else:
                lines.append(f"### 镜 {i} — {line.get('time', '')}")
                visual_cn = loc(line.get('visual_meaning', '') or line.get('visual', ''))
                audio = str(line.get('audio_content', '') or '').strip()
                sticker = str(line.get('text_content', '') or '').strip()
                direction = loc(line.get('direction_note', ''))
                sfx_note = loc(line.get('sfx_transition_note', ''))
                lines.extend(
                    [
                        "",
                        f"**画面**: {visual_cn}",
                        "",
                        f"**配音**: {audio}",
                    ]
                )
                if sticker:
                    lines.extend(
                        [
                            "",
                            f"**贴纸字**: {sticker}",
                        ]
                    )
                lines.extend(
                    [
                        "",
                        f"**导演提示（中文）**: {direction}",
                        "",
                        f"**音效/转场提示（中文）**: {sfx_note}",
                        "",
                    ]
                )

    cites = payload.get("citations") or []
    lines.extend(["## 引用 / Citations" if mode == "cn" else "## Citations", ""])
    if isinstance(cites, list) and cites:
        for c in cites:
            lines.append(f"- {c}")
    else:
        lines.append("_（无）_")

    return "\n".join(lines) + "\n"


def write_synthesis_markdown(project_id: str, script_id: str, body: str) -> str:
    """
    Write UTF-8 Markdown to repo_root() / @OUT / {project_id} / {script_id}.md
    Returns a POSIX-style relative path from repo root, e.g. @OUT/uuid/SOP-ABC123.md
    """
    root = repo_root()
    out_dir = root / _OUT_DIR_NAME / _safe_path_segment(project_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = f"{_safe_path_segment(script_id, max_len=80)}.md"
    path = out_dir / fname
    path.write_text(body, encoding="utf-8")
    try:
        rel = path.relative_to(root)
    except ValueError:
        rel = Path(_OUT_DIR_NAME) / _safe_path_segment(project_id) / fname
    return rel.as_posix()


def _build_markdown_name(
    output_mode: str,
    project_name: str,
    recipe: dict[str, str],
    script_id: str,
) -> str:
    """
    Filename convention:
    <lang>_<game>_<region>_<platform>_<strategy>_<SOPID>.md
    """
    lang = "CN" if (output_mode or "cn").strip().lower() == "cn" else "EN"
    def compact(v: str, fallback: str, max_len: int = 24) -> str:
        raw = (v or "").strip()
        if not raw:
            raw = fallback
        # Prefer concise labels: remove brackets/long separators and keep first 3 tokens.
        raw = re.sub(r"\(.*?\)|\[.*?\]", "", raw).strip()
        tokens = [t for t in re.split(r"[\s,/_\-]+", raw) if t]
        if len(tokens) > 3:
            raw = " ".join(tokens[:3])
        else:
            raw = " ".join(tokens) if tokens else raw
        return _safe_path_segment(raw, max_len=max_len)

    region_label = recipe.get("region_short") or recipe.get("region_name") or recipe.get("region", "") or "region_unknown"
    platform_label = recipe.get("platform_short") or recipe.get("platform_name") or recipe.get("platform", "") or "platform_unknown"
    angle_label = recipe.get("angle_short") or recipe.get("angle_name") or recipe.get("angle", "") or "strategy_unknown"

    parts = [
        lang,
        compact(str(project_name or "UnknownGame"), "UnknownGame", max_len=36),
        compact(str(region_label), "region_unknown", max_len=20),
        compact(str(platform_label), "platform_unknown", max_len=20),
        compact(str(angle_label), "strategy_unknown", max_len=20),
        str(script_id or "SOP-UNKNOWN"),
    ]
    safe_parts = [_safe_path_segment(p, max_len=80) for p in parts]
    return "_".join(safe_parts)


def export_markdown_after_generate(
    project_id: str,
    project_name: str,
    recipe: dict[str, str],
    engine: str,
    resp_dict: dict[str, Any],
    output_mode: str = "cn",
) -> str | None:
    """Serialize resp_dict to Markdown and write under @OUT/. Returns relative path or None on failure."""
    try:
        sid = str(resp_dict.get("script_id") or "").strip()
        if not sid:
            return None
        body = synthesis_to_markdown(project_name, recipe, engine, resp_dict, output_mode)
        file_stem = _build_markdown_name(output_mode, project_name, recipe, sid)
        return write_synthesis_markdown(project_id, file_stem, body)
    except OSError as e:
        print(f"[md_export] write failed: {e}")
        return None
    except Exception as e:
        print(f"[md_export] export failed: {e}")
        return None
