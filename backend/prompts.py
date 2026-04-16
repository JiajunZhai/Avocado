from typing import Dict, Any

def _build_common_context(game_context: str, culture_context: Dict[str, Any], platform_rules: Dict[str, Any], creative_logic: Dict[str, Any]) -> tuple[str, str, str]:
    culture_notes = "\n".join(f"- {note}" for note in culture_context.get("culture_notes", []))
    specs = platform_rules.get("specs", [])
    if isinstance(specs, dict):
        platform_specs = "\n".join(
            [
                f"- Format: {', '.join(specs.get('format', [])) if isinstance(specs.get('format'), list) else specs.get('format', '')}",
                f"- Safe Zone: {specs.get('safe_zone', '')}",
                f"- Pacing: {specs.get('pacing', '')}",
            ]
        )
    else:
        platform_specs = "\n".join(f"- {spec}" for spec in specs)
    logic_steps = "\n".join(f"- {step}" for step in creative_logic.get("logic_steps", []))
    base = f"""
    [Project DNA - Baseline]
    {game_context}

    [Target Region Constraints: {culture_context.get('name', 'Global')}]
    You MUST adhere to these cultural/linguistic rules:
    {culture_notes}
    - Preferred BGM: {culture_context.get('preferred_bgm', 'Any')}
    - Focus: {culture_context.get('focus', 'Standard')}

    [Distribution Pipeline Rules: {platform_rules.get('name', 'Generic')}]
    You MUST strictly build the visual pacing according to these specs:
    {platform_specs}

    [Creative Angle Logic: {creative_logic.get('name', 'Standard')}]
    Core Emotion: {creative_logic.get('core_emotion', 'None')}
    Mandatory Execution Steps:
    {logic_steps}
    """
    return base, culture_notes, platform_specs


def render_draft_prompt(game_context: str, culture_context: Dict[str, Any], platform_rules: Dict[str, Any], creative_logic: Dict[str, Any]) -> str:
    """
    Stage-1 fast ideation prompt:
    output concise hook/storyboard skeletons for later director expansion.
    """
    base, _culture_notes, _platform_specs = _build_common_context(game_context, culture_context, platform_rules, creative_logic)
    return f"""
    You are a performance creative strategist for mobile UA.
    Generate concise ad concept drafts first, not full production script.

    {base}

    Output ONLY valid JSON:
    {{
      "drafts": [
        {{
          "id": "D1",
          "title": "<short concept title>",
          "hook": "<0-3s hook idea>",
          "story_arc": "<crisis->action->payoff in one line>",
          "gameplay_bridge": "<how hook transitions to true gameplay>",
          "risk_flags": ["<possible policy or logic risk>"],
          "estimated_ctr": <int 0-100>,
          "estimated_quality": <int 0-100>
        }}
      ],
      "pick_recommendation": "<id of best draft>"
    }}
    Constraints:
    - Return 3 to 5 drafts.
    - Keep each draft compact and production-usable.
    - Avoid fake system-native UI bait.
    """


def render_director_prompt(
    game_context: str,
    culture_context: Dict[str, Any],
    platform_rules: Dict[str, Any],
    creative_logic: Dict[str, Any],
    selected_draft_json: str = "",
) -> str:
    """
    Stage-2 director prompt: build final production script.
    """
    base, _culture_notes, _platform_specs = _build_common_context(game_context, culture_context, platform_rules, creative_logic)
    draft_section = ""
    if selected_draft_json.strip():
        draft_section = f"""
    [Selected Draft Blueprint - MUST follow]
    {selected_draft_json}
    """
    return f"""
    You are an expert Mobile Game User Acquisition (UA) Director with 10 years of experience.
    Your audience is a DOMESTIC VIDEO EDITOR (Chinese/English speaking).

    {base}
    {draft_section}

    [GENE GRAFTING PROTOCOL (Conflict Resolution)]
    If the [Project DNA - Baseline] contains "[Market Context from Vector Intelligence]", you MUST execute Gene Grafting:
    1. The core mechanics of the game MUST remain based on the original game info constraints.
    2. However, you MUST graft (inject) the visual hooks, trends, and mechanics found in the Market Context.
    3. If there is a direct conflict (e.g. game is "Hardcore Strategy" but Market Context suggests "Comedic Fail-bait"), keep game truthfulness first and then adapt the trend wrapper.

    [QUALITY + COMPLIANCE GUARDRAILS]
    - Never use fake OS/system-native UI bait (e.g., fake low battery alert, fake phone call, fake system warning).
    - Hook can be dramatic, but must remain logically connected to game mechanics within 1-2 shots.
    - For ASMR / stress-relief mechanics, provide longer shot duration for tactile payoff (usually 1.5s-2.0s each in showcase phase).
    - Avoid animal-abuse tone. If using "rescue/fail" hook, keep the character comedic/resilient rather than cruel/despairing.
    - Prefer production-ready direction over literal translation.

    Your task is to generate a highly detailed, localized "Bilingual Bridge Script" outputting ONLY valid JSON formatting without markdown blocks.
    
    JSON SCHEMA:
    {{
        "hook_score": <int 0-100>,
        "hook_reasoning": "<str>",
        "clarity_score": <int 0-100>,
        "clarity_reasoning": "<str>",
        "conversion_score": <int 0-100>,
        "conversion_reasoning": "<str>",
        "bgm_direction": "<str>",
        "editing_rhythm": "<str>",
        "ad_copy_matrix": {{
            "primary_texts": ["<at least 5 long-form primary texts in different styles: rescue, iq, asmr, benefit, minimal>"],
            "headlines": ["<at least 10 short high-CTR headlines WITH emoji>"],
            "hashtags": ["<at least 20 global high-frequency search hashtags>"],
            "visual_stickers": [
                {{
                    "shot_index": <int 0-based>,
                    "sticker_text": "<impactful sticker text (e.g., Level 1 vs Level 99, Huge Win, Scared?)>",
                    "sticker_meaning_cn": "<Chinese meaning/intent for editor>"
                }}
            ]
        }},
        "script": [
            {{
                "time": "0s",
                "visual": "<English shot description for production>",
                "visual_meaning": "<Chinese director-facing visual instruction>",
                "audio_content": "<ACTUAL Native Voiceover text>",
                "audio_meaning": "<Chinese meaning + delivery emotion guidance>",
                "text_content": "<Sticker Text (impactful on-screen sticker words, MUST be present for every shot)>",
                "text_meaning": "<Chinese meaning of Sticker Text>",
                "sticker_text": "<same as text_content (explicit sticker field, MUST be present)>",
                "sticker_meaning": "<same as text_meaning (Chinese meaning)>",
                "direction_note": "<Chinese director note: pacing/camera/performance>",
                "sfx_transition_note": "<Chinese post note: SFX, pause, transition, beat>"
            }}
        ],
        "psychology_insight": "<str>",
        "cultural_notes": ["<str>"],
        "competitor_trend": "<str>"
    }}

    HARD REQUIREMENTS:
    - For EVERY shot, you MUST output Sticker Text fields: text_content/text_meaning AND sticker_text/sticker_meaning (they can be identical).
    - Sticker Text must be visually punchy: short, high-contrast, clickable (examples: "LEVEL 1 vs LEVEL 99", "HUGE WIN", "SCAM?", "DON'T DO THIS").
    - The first 3 seconds (usually shot 1-2) Sticker Text MUST share keywords with the top headlines (same core words).
    - ad_copy_matrix must meet minimum counts: primary_texts>=5, headlines>=10 (with emoji), hashtags>=20, visual_stickers must cover EVERY shot.
    """


def render_system_prompt(game_context: str, culture_context: Dict[str, Any], platform_rules: Dict[str, Any], creative_logic: Dict[str, Any]) -> str:
    """
    Backward-compatible alias for existing callers.
    """
    return render_director_prompt(game_context, culture_context, platform_rules, creative_logic)


def get_system_prompt_template(
    *,
    title: str,
    usp: str,
    platform: str,
    angle: str,
    region: str,
    oracle_context: str = "",
) -> str:
    """
    Legacy prompt template used by older unit tests.

    Newer codepaths should use `render_director_prompt` / `render_copy_prompt`.
    """
    r = (region or "").strip().lower()
    regional_directives: list[str] = []
    if "japan" in r or r in {"jp", "ja"}:
        regional_directives += [
            "- Use Danmaku-style on-screen reactions when appropriate.",
            "- Reference Voice Actor (CV) culture when it fits.",
            "- Prefer anime/game meme pacing over western 'meme cut' edits.",
        ]
    elif "na" in r or "eu" in r or "north america" in r or "europe" in r:
        regional_directives += [
            "- Use meme cut pacing and bold punchlines when appropriate.",
        ]
    else:
        regional_directives += [
            "- Localize slang and cultural hooks for the target region.",
        ]

    oracle = (oracle_context or "").strip()
    oracle_block = f"\n[Market Context from Vector Intelligence]\n{oracle}\n" if oracle else ""

    return f"""
You are a performance creative strategist for mobile UA.

[Project]
- Title: {title}
- USP: {usp}
- Platform: {platform}
- Angle: {angle}
- Region: {region}
{oracle_block}
[REGIONAL DIRECTIVES]
{chr(10).join(regional_directives)}

[CONFLICT RESOLUTION: If you detect contradictory instructions]
- Follow Project truth first (core gameplay must remain accurate).
- Use Market Context as wrapper/trend inspiration, not as a rewrite of mechanics.
""".strip()


def render_copy_prompt(
    *,
    game_context: str,
    culture_context: Dict[str, Any],
    platform_rules: Dict[str, Any],
    creative_logic: Dict[str, Any],
    quantity: int = 20,
    tones: list[str] | None = None,
    locales: list[str] | None = None,
    base_script_context: str = "",
) -> str:
    """
    Quick Copy Mode prompt: generate ad copy matrix only (no storyboard).
    - Focus on click desire, diversity, and transcreation for locales.
    """
    base, _culture_notes, _platform_specs = _build_common_context(game_context, culture_context, platform_rules, creative_logic)
    q = max(5, min(int(quantity or 20), 200))
    tone_list = [t.strip() for t in (tones or []) if str(t).strip()]
    locale_list = [l.strip() for l in (locales or []) if str(l).strip()]
    tones_line = ", ".join(tone_list) if tone_list else "humor, pro, clickbait, benefit-driven, FOMO"
    locales_line = ", ".join(locale_list) if locale_list else "en"
    script_section = ""
    if base_script_context.strip():
        script_section = f"""
    [Existing Video Script Context - DO NOT rewrite storyboard]
    Use this ONLY as creative truth for copy refresh. Do NOT generate any shots.
    {base_script_context[:6000]}
    """

    return f"""
    You are an elite UA Copywriter specializing in performance advertising.
    Your ONLY job is to generate a high-volume, high-diversity Ad Copy Matrix.
    Do NOT generate storyboard / shots / SFX / camera directions.

    {base}
    {script_section}

    TARGETS:
    - Quantity of headlines per locale: {q}
    - Tone preferences: {tones_line}
    - Locales: {locales_line}

    DIVERSITY ENGINE (must follow):
    - Use multi-variable combinations to avoid sameness:
      [Benefit Word] + [CTA] + [Emotion Hook] + [Contrast Pattern] + [Numeric Specificity]
    - Cover at least these psychological motives across the set:
      rescue, IQ/challenge, ASMR/satisfying, benefits/free rewards, minimal/clean
    - No fake system-native UI bait (low battery / phone call / OS warning).

    LOCALIZATION:
    - For non-English locales, do TRANSCREATION: keep intent + punchiness + cultural fit.
    - Keep hashtags relevant and high-frequency for that locale; do not machine-translate hashtags.

    Output ONLY valid JSON (no markdown), with this exact schema:
    {{
      "ad_copy_matrix": {{
        "default_locale": "en",
        "locales": ["en"],
        "variants": {{
          "en": {{
            "primary_texts": ["... (>=5, 5 styles)"],
            "headlines": ["... (exactly {q}, include emoji)"],
            "hashtags": ["... (>=20, start with #)"]
          }}
        }}
      }}
    }}

    RULES:
    - For EACH locale:
      - primary_texts: at least 5 items
      - headlines: exactly {q} items, each must include at least one emoji
      - hashtags: at least 20 items, each starts with '#'
    - Ensure the TOP 5 headlines share core keywords with each other (for A/B themed testing).
    """
