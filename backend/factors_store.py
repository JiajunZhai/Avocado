"""Phase 26 / E — SQLite-backed factor store.

JSON files under ``backend/data/knowledge/factors/{angles,platforms,regions}``
remain the git-tracked source of truth. This module mirrors them into the
``factors`` SQLite table on boot (idempotent, fingerprint-gated) so runtime
lookups get proper indexing and future CRUD flows (admin page, etc.) can write
back cleanly.

Callers should use ``read_insight`` / ``list_by_type`` / ``upsert_factor``
instead of poking ``FACTORS_DIR`` directly.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional

from db import execute, fetchall, fetchone, get_conn
from knowledge_paths import FACTORS_DIR, ensure_knowledge_layout


TYPE_DIR_MAP = {
    "angle": "angles",
    "platform": "platforms",
    "region": "regions",
}
_REVERSE_MAP = {v: k for k, v in TYPE_DIR_MAP.items()}


def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _fingerprint(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8", errors="replace")).hexdigest()[:16]


def _infer_type_from_id(factor_id: str) -> Optional[str]:
    if not factor_id:
        return None
    head = factor_id.split("_", 1)[0]
    if head in TYPE_DIR_MAP:
        return head
    return None


def _infer_type_from_path(path: Path) -> Optional[str]:
    parent = path.parent.name.lower()
    return _REVERSE_MAP.get(parent)


def upsert_factor(
    factor_id: str,
    *,
    type: str,
    data: dict[str, Any],
    fingerprint: Optional[str] = None,
    short_name: Optional[str] = None,
    name: Optional[str] = None,
    enabled: bool = True,
) -> None:
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True)
    fp = fingerprint or _fingerprint(payload)
    execute(
        """
        INSERT INTO factors(id, type, short_name, name, data_json, file_fingerprint, enabled, updated_at)
        VALUES(?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            type=excluded.type,
            short_name=excluded.short_name,
            name=excluded.name,
            data_json=excluded.data_json,
            file_fingerprint=excluded.file_fingerprint,
            enabled=excluded.enabled,
            updated_at=excluded.updated_at
        """,
        (
            factor_id,
            type,
            short_name or str(data.get("short_name") or "") or None,
            name or str(data.get("name") or "") or None,
            payload,
            fp,
            1 if enabled else 0,
            _now(),
        ),
    )


def increment_factor_weight(factor_id: str, delta: float = 0.1) -> bool:
    """Telemetry feedback loop: bump the priority_weight inside the Factor JSON."""
    row = fetchone("SELECT data_json FROM factors WHERE id = ?", (factor_id,))
    if not row:
        return False
    try:
        data = json.loads(row["data_json"])
        current_weight = float(data.get("priority_weight", 1.0))
        data["priority_weight"] = current_weight + delta
        new_payload = json.dumps(data, ensure_ascii=False, sort_keys=True)
        fp = _fingerprint(new_payload)
        execute(
            """
            UPDATE factors
            SET data_json = ?, file_fingerprint = ?, updated_at = ?
            WHERE id = ?
            """,
            (new_payload, fp, _now(), factor_id),
        )
        return True
    except Exception:
        return False


def read_insight(insight_id: Optional[str]) -> dict[str, Any]:
    """Return the atomic-factor JSON dict for a given id; empty dict if missing.

    Signature compatible with the legacy ``read_insight`` closures scattered in
    ``main.py`` (quick-copy, refresh, retry-region, generate).
    """
    if not insight_id:
        return {}
    row = fetchone("SELECT data_json FROM factors WHERE id = ? AND enabled = 1", (insight_id,))
    if row is None:
        return {}
    try:
        data = json.loads(row["data_json"])
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def list_by_type(factor_type: str) -> list[dict[str, Any]]:
    rows = fetchall(
        "SELECT id, short_name, name, data_json FROM factors WHERE type = ? AND enabled = 1 ORDER BY id",
        (factor_type,),
    )
    out: list[dict[str, Any]] = []
    for r in rows:
        try:
            data = json.loads(r["data_json"])
        except Exception:
            data = {}
        out.append(
            {
                "id": r["id"],
                "short_name": r["short_name"],
                "name": r["name"],
                "data": data,
            }
        )
    return out


def _iter_factor_files(root: Path) -> Iterable[Path]:
    if not root.exists():
        return []
    results: list[Path] = []
    for subdir in ("angles", "platforms", "regions"):
        folder = root / subdir
        if not folder.exists():
            continue
        for p in folder.glob("*.json"):
            if p.is_file():
                results.append(p)
    return results


def seed_from_filesystem(*, force: bool = False) -> dict[str, Any]:
    """Scan ``FACTORS_DIR`` and upsert newer files into the DB.

    Returns a summary ``{inserted, updated, skipped, total}`` useful for logs.
    """
    ensure_knowledge_layout()
    root = Path(FACTORS_DIR)
    inserted = updated = skipped = 0
    total = 0
    conn = get_conn()

    existing = {
        r["id"]: (r["file_fingerprint"] or "")
        for r in conn.execute("SELECT id, file_fingerprint FROM factors").fetchall()
    }

    for path in _iter_factor_files(root):
        try:
            raw = path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        fid = str(data.get("id") or path.stem)
        ftype = _infer_type_from_path(path) or _infer_type_from_id(fid)
        if not ftype:
            continue
        fp = _fingerprint(raw)
        total += 1
        if not force and existing.get(fid) == fp:
            skipped += 1
            continue
        is_new = fid not in existing
        upsert_factor(fid, type=ftype, data=data, fingerprint=fp)
        if is_new:
            inserted += 1
        else:
            updated += 1

    return {"inserted": inserted, "updated": updated, "skipped": skipped, "total": total}


def stats() -> dict[str, Any]:
    rows = fetchall(
        "SELECT type, COUNT(*) AS n FROM factors WHERE enabled = 1 GROUP BY type"
    )
    return {r["type"]: int(r["n"]) for r in rows}
