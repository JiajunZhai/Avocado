"""Phase 27 / Oracle Refiner — Automated pipeline for standardizing UA intelligence."""

from typing import Dict, Any, List
import json
import uuid

import csv
import os

def parse_csv_uploads(csv_content: str) -> List[Dict[str, Any]]:
    """
    Parses a manually uploaded CSV containing raw ad descriptions or competitor metadata.
    Extracts the 'ad_copy' column and pushes it through an LLM to format it into Oracle structure.
    """
    reader = csv.DictReader(csv_content.splitlines())
    raw_feed = []
    for row in reader:
        ad_copy = row.get("ad_copy") or row.get("description")
        if not ad_copy:
            continue
        raw_feed.append({
            "suggested_tier": "Tier 2",
            "game_type": row.get("game_type", "Unknown"),
            "region": row.get("region", "Global"),
            "angle": row.get("angle", "Misc"),
            "performance": row.get("performance", "Mid"),
            "text": ad_copy,
            "url": row.get("url", "CSV Upload")
        })
    
    return ingest_from_feed(raw_feed)

def _llm_reverse_engineer(raw_text: str) -> dict:
    from openai import OpenAI
    cloud_client = OpenAI(
        api_key=os.getenv("DEEPSEEK_API_KEY", ""),
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    )
    if not cloud_client.api_key:
        return {}
    
    prompt = f"Reverse-engineer this raw ad copy into a structured UA script.\nFormat as JSON with keys: hook, build_up, climax, cta.\n\nRaw Audio/Text: {raw_text[:2000]}"
    try:
        response = cloud_client.chat.completions.create(
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            messages=[{"role": "user", "content": prompt}]
        )
        import re
        content = response.choices[0].message.content
        match = re.search(r"(\{.*\})", content, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        return json.loads(content)
    except Exception:
        return {}

def ingest_from_feed(feed_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Simulated ingestion from an RSS/API source (e.g., AppGrowing, SensorTower).
    Returns normalized pending knowledge docs ready to be committed to Oracle.
    """
    pending_docs = []
    
    for item in feed_data:
        # Standardize raw feed into our required structure
        llm_logic = _llm_reverse_engineer(item.get("text", ""))
        
        pending_doc = {
            "id": f"PENDING-{uuid.uuid4().hex[:8]}",
            "tier": item.get("suggested_tier", "Tier 2"),
            "game_type": item.get("game_type", "Unknown"),
            "region": item.get("region", "Global"),
            "angle": item.get("angle", "Misc"),
            "performance_level": item.get("performance", "Mid"),
            "script_logic": {
                "hook": llm_logic.get("hook", "Extracted hook..."),
                "build_up": llm_logic.get("build_up", "Extracted build-up..."),
                "climax": llm_logic.get("climax", "Extracted climax..."),
                "cta": llm_logic.get("cta", "Extracted cta...")
            },
            "source": item.get("url", "feed"),
            "raw_text": item.get("text", "")
        }
        pending_docs.append(pending_doc)
        
    return pending_docs

def promote_to_oracle(doc_id: str, verified_doc: Dict[str, Any]) -> bool:
    """
    Triggered when an Operator clicks 'Add to Oracle'. 
    Commits the pending intelligence directly into `knowledge_docs`.
    """
    from db import get_conn, execute
    from datetime import datetime
    
    now = datetime.utcnow().isoformat() + "Z"
    meta = {
        "tier": verified_doc.get("tier"),
        "game_type": verified_doc.get("game_type"),
        "performance_level": verified_doc.get("performance_level"),
        "script_logic": verified_doc.get("script_logic")
    }
    
    doc_text = json.dumps(verified_doc.get("script_logic", {}), ensure_ascii=False)
    
    try:
        execute(
            """
            INSERT OR IGNORE INTO knowledge_docs(
                id, doc_text, source, region, category, meta_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                doc_id.replace("PENDING", "ORACLE"),
                doc_text,
                verified_doc.get("source", ""),
                verified_doc.get("region", "Global"),
                verified_doc.get("angle", ""),
                json.dumps(meta, ensure_ascii=False),
                now
            )
        )
        return True
    except Exception as e:
        print(f"Failed to promote to oracle: {e}")
        return False
