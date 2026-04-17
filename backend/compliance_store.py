"""Phase 26 / E — SQLite-backed compliance rule store.

``backend/data/compliance/risk_terms.json`` remains the git-tracked source of
truth; on boot we SHA1 the file and rebuild ``compliance_rules`` rows only when
the fingerprint changed. The existing ``compliance.py`` runtime continues to
work through ``load_risk_terms()`` which now proxies back into the DB.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from db import execute, fetchall, fetchone, get_conn


BACKEND_DIR = Path(__file__).resolve().parent
RISK_TERMS_PATH = BACKEND_DIR / "data" / "compliance" / "risk_terms.json"


def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _fingerprint(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8", errors="replace")).hexdigest()[:16]


def _row_id(scope: str, platform_id: str, region_id: str, term: str) -> str:
    base = f"{scope}|{platform_id}|{region_id}|{term.lower()}"
    return hashlib.sha1(base.encode("utf-8", errors="replace")).hexdigest()[:24]


def _insert_terms(
    entries: list[dict[str, Any]],
    *,
    scope: str,
    platform_id: str = "",
    region_id: str = "",
    fp: str,
) -> None:
    now = _now()
    rows: list[tuple[Any, ...]] = []
    for t in entries:
        if not isinstance(t, dict):
            continue
        term = str(t.get("term") or "").strip()
        if not term:
            continue
        severity = str(t.get("severity") or "warn").strip().lower()
        if severity not in {"warn", "block"}:
            severity = "warn"
        note = str(t.get("note") or "").strip()
        rows.append(
            (
                _row_id(scope, platform_id, region_id, term),
                scope,
                region_id or None,
                platform_id or None,
                term,
                severity,
                note,
                json.dumps(t, ensure_ascii=False),
                fp,
                now,
            )
        )
    if not rows:
        return
    conn = get_conn()
    conn.executemany(
        """
        INSERT INTO compliance_rules(id, scope, region_id, platform_id, term, severity, note, data_json, file_fingerprint, updated_at)
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            severity=excluded.severity,
            note=excluded.note,
            data_json=excluded.data_json,
            file_fingerprint=excluded.file_fingerprint,
            updated_at=excluded.updated_at
        """,
        rows,
    )


def _current_fp() -> str:
    row = fetchone(
        "SELECT file_fingerprint FROM compliance_rules ORDER BY updated_at DESC LIMIT 1"
    )
    if row is None:
        return ""
    return str(row["file_fingerprint"] or "")


def seed_from_filesystem(*, force: bool = False) -> dict[str, Any]:
    """Idempotently rebuild the compliance_rules table from risk_terms.json."""
    if not RISK_TERMS_PATH.exists():
        return {"seeded": False, "reason": "risk_terms.json missing"}
    raw = RISK_TERMS_PATH.read_text(encoding="utf-8")
    fp = _fingerprint(raw)
    if not force and _current_fp() == fp:
        return {"seeded": False, "fingerprint": fp}
    try:
        payload = json.loads(raw)
    except Exception as exc:
        return {"seeded": False, "reason": f"invalid JSON: {exc}"}
    if not isinstance(payload, dict):
        return {"seeded": False, "reason": "payload is not an object"}

    # Rebuild: cheaper than trying to diff.
    conn = get_conn()
    conn.execute("DELETE FROM compliance_rules")

    _insert_terms(payload.get("global") or [], scope="global", fp=fp)

    po = payload.get("platform_overrides") or {}
    if isinstance(po, dict):
        for pid, entries in po.items():
            if isinstance(entries, list):
                _insert_terms(entries, scope="platform", platform_id=str(pid), fp=fp)

    ro = payload.get("region_overrides") or {}
    if isinstance(ro, dict):
        for rid, entries in ro.items():
            if isinstance(entries, list):
                _insert_terms(entries, scope="region", region_id=str(rid), fp=fp)

    return {"seeded": True, "fingerprint": fp}


def load_all_grouped() -> dict[str, Any]:
    """Return ``{global, platform_overrides, region_overrides}`` from DB.

    The shape matches what ``compliance.load_risk_terms()`` used to return so
    ``scan_ad_copy`` / admin endpoints keep working unchanged.
    """
    rows = fetchall(
        "SELECT scope, region_id, platform_id, term, severity, note, data_json FROM compliance_rules"
    )
    global_terms: list[dict[str, Any]] = []
    platform_overrides: dict[str, list[dict[str, Any]]] = {}
    region_overrides: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        item = {"term": r["term"], "severity": r["severity"], "note": r["note"] or ""}
        scope = str(r["scope"])
        if scope == "global":
            global_terms.append(item)
        elif scope == "platform" and r["platform_id"]:
            platform_overrides.setdefault(str(r["platform_id"]), []).append(item)
        elif scope == "region" and r["region_id"]:
            region_overrides.setdefault(str(r["region_id"]), []).append(item)
    return {
        "global": global_terms,
        "platform_overrides": platform_overrides,
        "region_overrides": region_overrides,
    }
