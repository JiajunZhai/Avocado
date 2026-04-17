"""Phase 26 / E — SQLite-backed project + history storage.

The HTTP surface / Pydantic models are preserved from Phase 25 so the frontend
does not need to change. On first boot we migrate any legacy
``backend/data/workspaces/*.json`` files into the ``projects`` + ``history_log``
tables. After that the DB is the source of truth; the JSON files stay on disk
as a one-shot backup (no longer written to).
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from db import execute, fetchall, fetchone, get_conn


router = APIRouter(prefix="/api/projects", tags=["projects"])

WORKSPACE_DIR = Path(__file__).resolve().parent / "data" / "workspaces"


class GameInfo(BaseModel):
    # Legacy fields for backward compatibility
    core_gameplay: str = ""
    core_usp: str = ""
    target_persona: str = ""
    value_hooks: str = ""

    # Advanced 5-Pillar Project DNA
    core_loop: str = Field(default="", description="The mechanical loop (e.g., Mow down -> Drop -> Upgrade).")
    usp: dict[str, str] = Field(default_factory=dict, description="Matrix of visual, gameplay, stats, and social hooks.")
    persona: str = Field(default="", description="Motivation-driven audience profiles (e.g., stress-relief).")
    visual_dna: str = Field(default="", description="Art style constraints (e.g., anime, realistic, dark).")
    competitive_set: list[str] = Field(default_factory=list, description="Cross-reference tags linking to Oracle competitor insights.")


class TargetAnalysis(BaseModel):
    region_analysis: str = ""
    platform_analysis: str = ""


class MarketTarget(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    region: str
    platform: str
    analysis: TargetAnalysis = Field(default_factory=TargetAnalysis)
    historical_best_script_id: Optional[str] = None


class ProjectBase(BaseModel):
    name: str
    game_info: GameInfo = Field(default_factory=GameInfo)
    market_targets: List[MarketTarget] = Field(default_factory=list)
    history_log: List[dict] = Field(default_factory=list)
    archived_at: Optional[str] = None
    user_preference_notes: str = Field(default="", description="LLM-summarized notes based on semantic save-point analysis of user edits.")


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(ProjectBase):
    pass


class Project(ProjectBase):
    id: str
    created_at: str
    updated_at: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _row_to_dict(row) -> dict[str, Any]:
    try:
        game_info = json.loads(row["game_info_json"] or "{}")
    except Exception:
        game_info = {}
    try:
        targets = json.loads(row["market_targets_json"] or "[]")
    except Exception:
        targets = []
    return {
        "id": row["id"],
        "name": row["name"],
        "game_info": game_info if isinstance(game_info, dict) else {},
        "market_targets": targets if isinstance(targets, list) else [],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "archived_at": row["archived_at"] if "archived_at" in row.keys() else None,
        "user_preference_notes": row["user_preference_notes"] if "user_preference_notes" in row.keys() else "",
    }


def _history_row_to_entry(row) -> dict[str, Any]:
    try:
        payload = json.loads(row["payload_json"] or "{}")
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    # Prefer the canonical script_id over the autogen row id so compare / refresh
    # look-ups keep matching on the same identifier the UI renders.
    script_id = str(row["script_id"] or row["id"])
    merged = dict(payload)
    merged.update(
        {
            "id": script_id,
            "timestamp": row["created_at"],
            "engine": row["engine"],
            "output_kind": row["kind"] or payload.get("output_kind"),
            "output_mode": row["output_mode"] or payload.get("output_mode"),
            "markdown_path": row["markdown_path"] or payload.get("markdown_path"),
            "decision": row["decision"] or payload.get("decision") or "pending",
            "decision_at": row["decision_at"] or payload.get("decision_at"),
            "provider": row["provider"] or payload.get("provider"),
            "model": row["model"] or payload.get("model"),
            "schema_version": row["schema_version"] or payload.get("schema_version") or 3,
            "parent_script_id": row["parent_script_id"] or payload.get("parent_script_id"),
            "factor_version": row["factor_version"] or payload.get("factor_version"),
            "draft_status": row["draft_status"] or payload.get("draft_status"),
        }
    )
    recipe = {
        "region": row["region_id"] or "",
        "platform": row["platform_id"] or "",
        "angle": row["angle_id"] or "",
    }
    merged.setdefault("recipe", recipe)
    if not isinstance(merged.get("recipe"), dict):
        merged["recipe"] = recipe
    return merged


def _load_history(project_id: str) -> list[dict[str, Any]]:
    rows = fetchall(
        "SELECT * FROM history_log WHERE project_id = ? ORDER BY created_at ASC",
        (project_id,),
    )
    return [_history_row_to_entry(r) for r in rows]


def _assemble_project(row) -> dict[str, Any]:
    data = _row_to_dict(row)
    data["history_log"] = _load_history(data["id"])
    return data


def _persist_history_entry(project_id: str, entry: dict[str, Any]) -> None:
    script_id = str(entry.get("id") or f"HIST-{uuid4().hex[:8]}")
    recipe = entry.get("recipe") if isinstance(entry.get("recipe"), dict) else {}
    created_at = str(entry.get("timestamp") or _now())
    params = (
        script_id,
        project_id,
        created_at,
        entry.get("output_kind"),
        (recipe or {}).get("region"),
        (recipe or {}).get("platform"),
        (recipe or {}).get("angle"),
        script_id,
        entry.get("decision") or "pending",
        entry.get("decision_at"),
        entry.get("provider"),
        entry.get("model"),
        int(entry.get("schema_version") or 3),
        entry.get("engine"),
        entry.get("output_mode"),
        entry.get("markdown_path"),
        entry.get("parent_script_id"),
        entry.get("factor_version"),
        entry.get("draft_status"),
        json.dumps(entry, ensure_ascii=False),
    )
    execute(
        """
        INSERT INTO history_log(
            id, project_id, created_at, kind, region_id, platform_id, angle_id,
            script_id, decision, decision_at, provider, model, schema_version,
            engine, output_mode, markdown_path, parent_script_id, factor_version,
            draft_status, payload_json
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            created_at=excluded.created_at,
            kind=excluded.kind,
            region_id=excluded.region_id,
            platform_id=excluded.platform_id,
            angle_id=excluded.angle_id,
            decision=excluded.decision,
            decision_at=excluded.decision_at,
            provider=excluded.provider,
            model=excluded.model,
            schema_version=excluded.schema_version,
            engine=excluded.engine,
            output_mode=excluded.output_mode,
            markdown_path=excluded.markdown_path,
            parent_script_id=excluded.parent_script_id,
            factor_version=excluded.factor_version,
            draft_status=excluded.draft_status,
            payload_json=excluded.payload_json
        """,
        params,
    )


def _upsert_project_row(project: dict[str, Any]) -> None:
    execute(
        """
        INSERT INTO projects(id, name, game_info_json, market_targets_json, created_at, updated_at, archived_at, user_preference_notes)
        VALUES(?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name=excluded.name,
            game_info_json=excluded.game_info_json,
            market_targets_json=excluded.market_targets_json,
            updated_at=excluded.updated_at,
            archived_at=excluded.archived_at,
            user_preference_notes=excluded.user_preference_notes
        """,
        (
            project["id"],
            project.get("name") or "Untitled Project",
            json.dumps(project.get("game_info") or {}, ensure_ascii=False),
            json.dumps(project.get("market_targets") or [], ensure_ascii=False),
            project.get("created_at") or _now(),
            project.get("updated_at") or _now(),
            project.get("archived_at"),
            project.get("user_preference_notes") or "",
        ),
    )


# ---------------------------------------------------------------------------
# Public helpers (also imported by main.py)
# ---------------------------------------------------------------------------


def load_projects() -> List[dict[str, Any]]:
    rows = fetchall("SELECT * FROM projects ORDER BY created_at DESC")
    return [_assemble_project(r) for r in rows]


def load_project(project_id: str) -> Optional[dict[str, Any]]:
    row = fetchone("SELECT * FROM projects WHERE id = ?", (project_id,))
    if row is None:
        return None
    return _assemble_project(row)


def save_project(project: dict[str, Any]) -> None:
    """Persist a Project dict (optionally with ``history_log``) into SQLite.

    Matches the legacy signature used by ``main.py`` callers. Each history
    entry upserts by ``id``, so repeated saves with mutated entries (e.g.
    Phase 22 decision updates) are idempotent.
    """
    if not project.get("id"):
        raise ValueError("project must have an id")
    project.setdefault("created_at", _now())
    project["updated_at"] = _now()
    get_conn().execute("BEGIN")
    try:
        _upsert_project_row(project)
        history = project.get("history_log") or []
        if isinstance(history, list):
            for entry in history:
                if isinstance(entry, dict) and entry.get("id"):
                    _persist_history_entry(project["id"], entry)
        get_conn().execute("COMMIT")
    except Exception:
        get_conn().execute("ROLLBACK")
        raise


def append_history_entry(project_id: str, entry: dict[str, Any]) -> None:
    """Insert/upsert a single history row without touching project meta.

    Used by ``_record_history`` in ``main.py`` so we avoid re-serialising the
    full history log on every generation.
    """
    if not project_id or not isinstance(entry, dict):
        return
    _persist_history_entry(project_id, entry)
    execute("UPDATE projects SET updated_at = ? WHERE id = ?", (_now(), project_id))


def update_history_decision(
    project_id: str, script_id: str, decision: str, decision_at: str, diff_length: int = 0
) -> bool:
    cur = get_conn().execute(
        """
        UPDATE history_log
        SET decision = ?, decision_at = ?,
            payload_json = json_set(payload_json, '$.decision', ?, '$.decision_at', ?)
        WHERE project_id = ? AND (id = ? OR script_id = ?)
        """,
        (decision, decision_at, decision, decision_at, project_id, script_id, script_id),
    )
    if decision == "approved" and diff_length > 0:
        try:
            from telemetry import process_diff_feedback
            process_diff_feedback(script_id, diff_length)
        except Exception:
            pass
    return cur.rowcount > 0


# ---------------------------------------------------------------------------
# Legacy JSON migration (one-shot)
# ---------------------------------------------------------------------------


def migrate_legacy_workspaces() -> dict[str, Any]:
    """Import any ``workspaces/*.json`` files missing from the projects table.

    Idempotent — existing project rows are left alone. Returns a small summary
    for logs / tests.
    """
    if not WORKSPACE_DIR.exists():
        return {"imported": 0, "skipped": 0}

    known = {
        r["id"]
        for r in fetchall("SELECT id FROM projects")
    }
    imported = 0
    skipped = 0
    for path in WORKSPACE_DIR.glob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(payload, dict) or not payload.get("id"):
            continue
        if payload["id"] in known:
            skipped += 1
            continue
        save_project(payload)
        imported += 1
    return {"imported": imported, "skipped": skipped}


# ---------------------------------------------------------------------------
# HTTP routes
# ---------------------------------------------------------------------------


@router.get("/", response_model=List[Project])
def get_projects():
    return load_projects()


@router.post("/", response_model=Project)
def create_project(project_in: ProjectCreate):
    new_project = project_in.model_dump()
    new_project["id"] = str(uuid4())
    for target in new_project.get("market_targets", []):
        if not target.get("id"):
            target["id"] = str(uuid4())
    now = _now()
    new_project["created_at"] = now
    new_project["updated_at"] = now
    save_project(new_project)
    stored = load_project(new_project["id"])
    return stored or new_project


@router.put("/{project_id}", response_model=Project)
def update_project(project_id: str, project_in: ProjectUpdate):
    existing = load_project(project_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Project not found")
    updated = project_in.model_dump()
    updated["id"] = project_id
    updated["created_at"] = existing.get("created_at") or _now()
    updated["updated_at"] = _now()
    # Preserve history from DB (the PUT body on the UI mirrors what came in via GET).
    updated["history_log"] = existing.get("history_log") or []
    for target in updated.get("market_targets", []):
        if not target.get("id"):
            target["id"] = str(uuid4())
    save_project(updated)
    return load_project(project_id) or updated


@router.delete("/{project_id}")
def delete_project(project_id: str):
    row = fetchone("SELECT id FROM projects WHERE id = ?", (project_id,))
    if row is None:
        raise HTTPException(status_code=404, detail="Project not found")
    execute("DELETE FROM projects WHERE id = ?", (project_id,))
    return {"success": True}


class SavepointRequest(BaseModel):
    original_text: str
    edited_text: str

def _run_semantic_savepoint(project_id: str, original: str, edited: str):
    from openai import OpenAI
    cloud_client = OpenAI(
        api_key=os.getenv("DEEPSEEK_API_KEY", ""),
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    )
    if not cloud_client.api_key:
        return
    
    prompt = f"对比原始 AI 脚本与用户修改后的版本，总结用户的主要偏好变化（例如：更短的开头、移除了恐吓式营销、增加了当地俚语）。将总结提炼成一页精简的笔记。\n\n[原始文本]\n{original[:2000]}\n\n[修改后文本]\n{edited[:2000]}"
    try:
        response = cloud_client.chat.completions.create(
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            messages=[{"role": "user", "content": prompt}],
        )
        notes = response.choices[0].message.content
        existing = fetchone("SELECT user_preference_notes FROM projects WHERE id = ?", (project_id,))
        if existing:
            current_notes = existing["user_preference_notes"] or ""
            new_notes = f"{current_notes}\n- {notes}".strip()
            get_conn().execute(
                "UPDATE projects SET user_preference_notes = ?, updated_at = ? WHERE id = ?",
                (new_notes, _now(), project_id)
            )
    except Exception as e:
        print(f"Semantic savepoint failed: {e}")

@router.post("/{project_id}/savepoint")
def semantic_savepoint(project_id: str, req: SavepointRequest, background_tasks: BackgroundTasks):
    """Triggered when user clicks Save/Copy. Enqueues a lightweight semantic diff of their tweaks."""
    background_tasks.add_task(_run_semantic_savepoint, project_id, req.original_text, req.edited_text)
    return {"status": "enqueued"}
