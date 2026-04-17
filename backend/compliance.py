from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _risk_terms_path() -> Path:
    # Keep co-located under backend/data for easy ops editing
    return Path(__file__).resolve().parent / "data" / "compliance" / "risk_terms.json"


@dataclass(frozen=True)
class RiskTerm:
    term: str
    severity: str = "warn"  # warn | block
    note: str = ""


_CACHE: dict[str, Any] | None = None


def load_risk_terms() -> dict[str, Any]:
    """Phase 26/E — read from SQLite (seeded from risk_terms.json).

    Falls back to the JSON file on disk if the DB store is unreachable so
    unit tests and one-off scripts that never call ``run_migrations`` still
    get sensible data.
    """
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    try:
        from compliance_store import load_all_grouped

        data = load_all_grouped()
        if data.get("global") or data.get("platform_overrides") or data.get("region_overrides"):
            data.setdefault("global", [])
            data.setdefault("platform_overrides", {})
            data.setdefault("region_overrides", {})
            _CACHE = data
            return data
    except Exception:
        pass
    p = _risk_terms_path()
    if not p.exists():
        _CACHE = {"global": [], "platform_overrides": {}, "region_overrides": {}}
        return _CACHE
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raw = {}
    except Exception:
        raw = {}
    raw.setdefault("global", [])
    raw.setdefault("platform_overrides", {})
    raw.setdefault("region_overrides", {})
    _CACHE = raw
    return raw


def invalidate_cache() -> None:
    """Drop the in-memory cache so the next read pulls fresh DB state."""
    global _CACHE
    _CACHE = None


def _norm(s: str) -> str:
    return str(s or "").strip()


def _compile_terms(
    *,
    platform_id: str = "",
    region_id: str = "",
) -> list[RiskTerm]:
    cfg = load_risk_terms()
    terms: list[dict[str, Any]] = []
    if isinstance(cfg.get("global"), list):
        terms.extend([x for x in cfg["global"] if isinstance(x, dict)])
    po = cfg.get("platform_overrides")
    if platform_id and isinstance(po, dict) and isinstance(po.get(platform_id), list):
        terms.extend([x for x in po[platform_id] if isinstance(x, dict)])
    ro = cfg.get("region_overrides")
    if region_id and isinstance(ro, dict) and isinstance(ro.get(region_id), list):
        terms.extend([x for x in ro[region_id] if isinstance(x, dict)])

    out: list[RiskTerm] = []
    seen: set[str] = set()
    for t in terms:
        term = _norm(t.get("term", ""))
        if not term:
            continue
        key = term.lower()
        if key in seen:
            continue
        seen.add(key)
        sev = _norm(t.get("severity", "")) or "warn"
        if sev not in {"warn", "block"}:
            sev = "warn"
        out.append(RiskTerm(term=term, severity=sev, note=_norm(t.get("note", ""))))
    return out


def _find_hits(text: str, term: str) -> list[tuple[int, int]]:
    """
    Return [(start,end)] occurrences. Simple substring match (case-insensitive for latin).
    """
    s = str(text or "")
    if not s:
        return []
    # If term has any latin letters, do casefold; otherwise preserve (CJK/Arabic etc.)
    if any("A" <= c <= "Z" or "a" <= c <= "z" for c in term):
        hay = s.casefold()
        needle = term.casefold()
    else:
        hay = s
        needle = term
    hits: list[tuple[int, int]] = []
    start = 0
    while True:
        idx = hay.find(needle, start)
        if idx < 0:
            break
        hits.append((idx, idx + len(needle)))
        start = idx + max(1, len(needle))
        if len(hits) > 50:
            break
    return hits


def build_ad_copy_tiles(ad_copy_matrix: Any, *, region_id: str = "") -> list[dict[str, Any]]:
    """
    Return a flat array for looping render: [{id, region_id?, locale, kind, text}].
    Supports both shapes:
      - {primary_texts/headlines/hashtags} (generate)
      - {locales/default_locale/variants[locale]{...}} (quick-copy)
    """
    tiles: list[dict[str, Any]] = []
    if not isinstance(ad_copy_matrix, dict):
        return tiles

    def add(locale: str, kind: str, text: str):
        tid = f"{region_id}:{locale}:{kind}:{len(tiles)}" if region_id else f"{locale}:{kind}:{len(tiles)}"
        item = {"id": tid, "locale": locale, "kind": kind, "text": text}
        if region_id:
            item["region_id"] = region_id
        tiles.append(item)

    if isinstance(ad_copy_matrix.get("variants"), dict):
        locales = ad_copy_matrix.get("locales")
        if not isinstance(locales, list) or not locales:
            locales = [ad_copy_matrix.get("default_locale") or "en"]
        variants = ad_copy_matrix.get("variants") or {}
        for loc in [str(x) for x in locales if str(x).strip()]:
            v = variants.get(loc) if isinstance(variants, dict) else None
            if not isinstance(v, dict):
                continue
            for h in v.get("headlines") if isinstance(v.get("headlines"), list) else []:
                add(loc, "headline", str(h))
            for p in v.get("primary_texts") if isinstance(v.get("primary_texts"), list) else []:
                add(loc, "primary_text", str(p))
            for tag in v.get("hashtags") if isinstance(v.get("hashtags"), list) else []:
                add(loc, "hashtag", str(tag))
        return tiles

    # single-locale (director generate)
    loc = str(ad_copy_matrix.get("default_locale") or "default")
    for h in ad_copy_matrix.get("headlines") if isinstance(ad_copy_matrix.get("headlines"), list) else []:
        add(loc, "headline", str(h))
    for p in ad_copy_matrix.get("primary_texts") if isinstance(ad_copy_matrix.get("primary_texts"), list) else []:
        add(loc, "primary_text", str(p))
    for tag in ad_copy_matrix.get("hashtags") if isinstance(ad_copy_matrix.get("hashtags"), list) else []:
        add(loc, "hashtag", str(tag))
    return tiles


def scan_ad_copy(
    ad_copy_tiles: list[dict[str, Any]],
    *,
    platform_id: str = "",
    region_id: str = "",
) -> dict[str, Any]:
    terms = _compile_terms(platform_id=platform_id, region_id=region_id)
    hits: list[dict[str, Any]] = []
    max_sev = "ok"
    for tile in ad_copy_tiles:
        text = str(tile.get("text") or "")
        for rt in terms:
            occ = _find_hits(text, rt.term)
            if not occ:
                continue
            if rt.severity == "block":
                max_sev = "block"
            elif max_sev != "block":
                max_sev = "warn"
            for (s, e) in occ[:10]:
                hits.append(
                    {
                        "term": rt.term,
                        "severity": rt.severity,
                        "note": rt.note,
                        "locale": tile.get("locale"),
                        "region_id": tile.get("region_id"),
                        "kind": tile.get("kind"),
                        "tile_id": tile.get("id"),
                        "span": [int(s), int(e)],
                    }
                )
                if len(hits) >= 200:
                    break
        if len(hits) >= 200:
            break
    return {"risk_level": max_sev, "hits": hits}


def maybe_generate_rewrite_suggestions(
    *,
    cloud_client: Any,
    hits: list[dict[str, Any]],
    tiles_by_id: dict[str, dict[str, Any]],
    output_mode: str = "cn",
    model: str | None = None,
) -> list[dict[str, Any]]:
    """
    Best-effort cloud suggestions. Only runs when caller opts in and cloud client exists.
    Returns a list of {tile_id, original, suggested, reason}.
    """
    if not cloud_client:
        return []
    # limit to first N unique tiles
    target_ids: list[str] = []
    for h in hits:
        tid = str(h.get("tile_id") or "")
        if tid and tid not in target_ids:
            target_ids.append(tid)
        if len(target_ids) >= 12:
            break
    if not target_ids:
        return []

    items: list[dict[str, str]] = []
    for tid in target_ids:
        t = tiles_by_id.get(tid) or {}
        items.append(
            {
                "tile_id": tid,
                "kind": str(t.get("kind") or ""),
                "locale": str(t.get("locale") or ""),
                "text": str(t.get("text") or ""),
            }
        )
    lang = "简体中文" if (output_mode or "cn").lower() == "cn" else "English"
    system = (
        "You are an ad compliance copy editor. "
        "For each item, rewrite it to reduce account-ban/compliance risk while preserving selling points. "
        f"Output ONLY valid JSON: {{\"suggestions\":[{{\"tile_id\":\"...\",\"suggested\":\"...\",\"reason\":\"...\"}}]}}. "
        f"Write suggestions in {lang}. Keep emojis if appropriate. Do not add extra keys."
    )
    user = json.dumps({"items": items}, ensure_ascii=False)
    try:
        resp = cloud_client.chat.completions.create(
            model=(model or os.getenv("DEEPSEEK_MODEL", "deepseek-chat")),
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        raw = resp.choices[0].message.content or "{}"
        parsed = json.loads(raw)
        sugs = parsed.get("suggestions")
        if not isinstance(sugs, list):
            return []
        out: list[dict[str, Any]] = []
        for s in sugs[:20]:
            if not isinstance(s, dict):
                continue
            tid = str(s.get("tile_id") or "")
            if tid not in tiles_by_id:
                continue
            original = str(tiles_by_id[tid].get("text") or "")
            suggested = str(s.get("suggested") or "")
            reason = str(s.get("reason") or "")
            if not suggested.strip():
                continue
            out.append({"tile_id": tid, "original": original, "suggested": suggested, "reason": reason})
        return out
    except Exception:
        return []

