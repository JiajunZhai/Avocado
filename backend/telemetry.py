"""Phase 27 / Telemetry & Heatmap — Actional intel from generated results."""

from typing import Dict, Any, List
from db import fetchall

def get_angle_heatmap(project_id: str = None) -> List[Dict[str, Any]]:
    """
    Returns a heatmap representation of angle success rates.
    If project_id is None, aggregates globally.
    """
    query = """
        SELECT angle_id, decision, count(*) as cnt 
        FROM history_log 
        WHERE angle_id IS NOT NULL 
    """
    params = []
    if project_id:
        query += " AND project_id = ?"
        params.append(project_id)
        
    query += " GROUP BY angle_id, decision"
    
    rows = fetchall(query, params)
    
    heatmap = {}
    for r in rows:
        aid = r["angle_id"]
        dec = r["decision"] or "pending"
        cnt = int(r["cnt"])
        
        if aid not in heatmap:
            heatmap[aid] = {"approved": 0, "rejected": 0, "pending": 0, "total": 0}
            
        if dec in ["approved", "rejected", "pending"]:
            heatmap[aid][dec] += cnt
        heatmap[aid]["total"] += cnt
        
    # Calculate win rate
    results = []
    for aid, st in heatmap.items():
        win_rate = (st["approved"] / st["total"]) if st["total"] > 0 else 0.0
        results.append({
            "angle_id": aid,
            "win_rate": round(win_rate, 2),
            "total_uses": st["total"]
        })
        
    return sorted(results, key=lambda x: x["win_rate"], reverse=True)

def process_diff_feedback(script_id: str, diff_length: int) -> None:
    """
    Called when an edit is approved, assessing if it deviated significantly from AI output.
    Diff mechanism triggered on frontend, sending back length of changes.
    """
    # If the user consistently rewrites > 20% of an angle, we could downgrade its weight.
    # This function acts as the webhook sink for frontend Edit tracking.
    pass

import os
import json
import csv
import math
from db import execute, fetchone, get_conn, fetchall

def _get_strategy_config() -> dict:
    config_path = os.path.join(os.path.dirname(__file__), "data", "strategy_config.json")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {
            "noise_filter": {"min_impressions": 2000, "min_clicks": 20},
            "weight_adjustment_trigger": {"min_spend": 50, "ctr_multiplier": 1.1, "cvr_multiplier": 1.1},
            "logic_distill_trigger": {"min_spend": 1000, "ctr_multiplier": 1.5, "cvr_multiplier": 1.5},
            "risk_threshold": {"min_spend": 50, "ctr_multiplier": 0.5, "max_project_failures": 3}
        }

def _llm_evolve_positive_logic(angle_id: str, script_json: dict, current_logic: dict = None) -> None:
    """Soft Update: Given a Top 5% successful script, extract its exact logic formula and update the Angle's script_logic.
    Performs Consistency Check against current_logic."""
    from openai import OpenAI
    cloud_client = OpenAI(
        api_key=os.getenv("DEEPSEEK_API_KEY", ""),
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    )
    if not cloud_client.api_key:
        return
        
    current_context = json.dumps(current_logic, ensure_ascii=False) if current_logic else "None"
    prompt = f"这个脚本表现极佳(CVR Top 5%)。提取其最核心的前3秒Hook和高潮表达，总结出一条新的执行策略。\n请对照[当前策略]:\n{current_context}\n如果你的新策略与[当前策略]存在显著冲突（比如当前要求慢节奏，而该成功案例是极快节奏），请在返回中明确标注 [CONFLICT]，然后给出建议。否则只需给出优化后的新策略 JSON。\n\n[成功脚本]\n{json.dumps(script_json, ensure_ascii=False)[:3000]}"
    try:
        response = cloud_client.chat.completions.create(
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            messages=[{"role": "user", "content": prompt}],
        )
        new_logic = response.choices[0].message.content
        execute("INSERT INTO pending_evolutions(factor_id, field, proposed_value) VALUES (?, ?, ?)", (angle_id, "script_logic", new_logic))
    except Exception as e:
        print(f"Evolve positive failed: {e}")

def _llm_evolve_negative_taboo(region_id: str, platform_id: str, script_json: dict) -> None:
    """Soft Update: Given a Bottom 5% failure, abstract its fatal flaw and push it to Taboos."""
    from openai import OpenAI
    cloud_client = OpenAI(
        api_key=os.getenv("DEEPSEEK_API_KEY", ""),
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    )
    if not cloud_client.api_key:
        return
        
    prompt = f"这个脚本在大量消耗后表现极差(Bottom 5%)。分析它可能触犯了哪些地区/平台的禁忌或无效表达(例如：节奏太慢/未触及痛点)，将其提炼为一句警告。\n[失败脚本]\n{json.dumps(script_json, ensure_ascii=False)[:3000]}"
    try:
        response = cloud_client.chat.completions.create(
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            messages=[{"role": "user", "content": prompt}],
        )
        taboo_warning = response.choices[0].message.content
        execute("INSERT INTO pending_evolutions(factor_id, field, proposed_value) VALUES (?, ?, ?)", (region_id, "taboo", taboo_warning))
        execute("INSERT INTO pending_evolutions(factor_id, field, proposed_value) VALUES (?, ?, ?)", (platform_id, "taboo", taboo_warning))
    except Exception as e:
        print(f"Evolve negative failed: {e}")

def ingest_performance_data(csv_content: str, background_tasks) -> dict:
    """
    Processes a manually uploaded CSV containing [creative_id, spend, ctr, cvr].
    Maps creative_id back to history_log -> recipe -> factors.
    formula: priority_weight += log(spend) * performance_score
    Triggers Background Tasks for extreme performances.
    """
    from factors_store import increment_factor_weight
    
    config = _get_strategy_config()
    noise_cfg = config.get("noise_filter", {})
    weight_cfg = config.get("weight_adjustment_trigger", {})
    distill_cfg = config.get("logic_distill_trigger", {})
    risk_cfg = config.get("risk_threshold", {})
    
    reader = csv.DictReader(csv_content.splitlines())
    records = []
    
    mean_ctr = 0.0
    mean_cvr = 0.0
    
    for row in reader:
        try:
            impressions = int(row.get("impressions", 0))
            clicks = int(row.get("clicks", 0))
            
            if impressions < noise_cfg.get("min_impressions", 2000) or clicks < noise_cfg.get("min_clicks", 20):
                continue  # Skip junk data outright
                
            r = {
                "creative_id": row.get("creative_id", ""),
                "spend": max(1.1, float(row.get("spend", 1.0))),
                "ctr": float(row.get("ctr", 0.0)),
                "cvr": float(row.get("cvr", 0.0))
            }
            if r["creative_id"]:
                records.append(r)
        except Exception:
            pass
            
    if not records:
        return {"status": "success", "updates": 0, "errors": 0}
        
    mean_ctr = sum(r["ctr"] for r in records) / len(records)
    mean_cvr = sum(r["cvr"] for r in records) / len(records)
    
    updates = 0
    errors = 0
    evolutions_triggered = 0
    
    for r in records:
        spend = r["spend"]
        ctr = r["ctr"]
        cvr = r["cvr"]
        cid = r["creative_id"]
        
        parts = cid.split("_")
        if len(parts) < 2:
            errors += 1
            continue
            
        script_prefix = parts[-1]
        history_row = fetchone("SELECT id, project_id, region_id, platform_id, angle_id, payload_json FROM history_log WHERE id LIKE ?", (f"{script_prefix}%",))
        if not history_row:
            errors += 1
            continue
            
        angle_id = history_row["angle_id"]
        region_id = history_row["region_id"]
        platform_id = history_row["platform_id"]
        payload = json.loads(history_row["payload_json"] or "{}")
        
        # 1. Evaluate Weight Adjustment Thresholds
        if spend >= weight_cfg.get("min_spend", 50):
            # Check if logic exceeds relative baseline or is generally good
            if ctr >= (mean_ctr * weight_cfg.get("ctr_multiplier", 1.0)) or cvr >= (mean_cvr * weight_cfg.get("cvr_multiplier", 1.0)):
                # Adjust weight positively
                perf_score = (ctr * 100) + (cvr * 100)
                delta = math.log10(spend) * perf_score * 0.01
                if angle_id:
                    if increment_factor_weight(angle_id, delta):
                        updates += 1
            elif ctr <= (mean_ctr * risk_cfg.get("ctr_multiplier", 0.5)):
                # Deduct weight
                delta = -1.0 * math.log10(spend) * 0.05
                if angle_id:
                    increment_factor_weight(angle_id, delta)
                    
        # 2. Evaluate Deep Logic Distill Iteration
        if spend >= distill_cfg.get("min_spend", 1000):
            if cvr >= (mean_cvr * distill_cfg.get("cvr_multiplier", 1.5)) and angle_id:
                # Need to fetch the current JSON to check for semantic conflicts
                from factors_store import _get_factor_store
                store = _get_factor_store("angles")
                current_f = store.get(angle_id, {})
                current_logic = current_f.get("script_logic", {})
                
                background_tasks.add_task(_llm_evolve_positive_logic, angle_id, payload, current_logic)
                evolutions_triggered += 1
                
            elif ctr <= (mean_ctr * 0.5) and (region_id or platform_id):
                background_tasks.add_task(_llm_evolve_negative_taboo, region_id, platform_id, payload)
                evolutions_triggered += 1
                
    return {"status": "success", "updates": updates, "evolutions_queued": evolutions_triggered, "errors": errors}
