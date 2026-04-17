import json
import glob
from pathlib import Path

def migrate_angles():
    angle_files = glob.glob("data/knowledge/factors/angles/*.json")
    for filepath in angle_files:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Add priority_weight
        if "priority_weight" not in data:
            data["priority_weight"] = 1.0
            
        # Convert logic_steps to script_logic if exists
        if "logic_steps" in data and isinstance(data["logic_steps"], list):
            steps = data["logic_steps"]
            if "script_logic" not in data:
                data["script_logic"] = {
                    "hook": steps[0] if len(steps) > 0 else "",
                    "build_up": steps[1] if len(steps) > 1 else "",
                    "climax": steps[2] if len(steps) > 2 else "",
                    "cta": steps[3] if len(steps) > 3 else "Call to action..."
                }
            
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    print(f"Migrated {len(angle_files)} angles.")

def migrate_regions():
    region_files = glob.glob("data/knowledge/factors/regions/*.json")
    for filepath in region_files:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        if "taboo" not in data:
            data["taboo"] = ["General extreme violence or severe local offenses"]
        if "local_hook" not in data:
            data["local_hook"] = "Local cultural meme/hook placeholder"
        if "language_nuance" not in data:
            data["language_nuance"] = "Standard localization tone"
            
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    print(f"Migrated {len(region_files)} regions.")

def migrate_platforms():
    platform_files = glob.glob("data/knowledge/factors/platforms/*.json")
    for filepath in platform_files:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        if "safety_zone" not in data:
            data["safety_zone"] = "Center screen, avoid bottom 20% overlay"
        if "attention_span" not in data:
            data["attention_span"] = "First 3 seconds critical drop-off point"
        if "cta_style" not in data:
            data["cta_style"] = "Direct and high urgency"
            
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    print(f"Migrated {len(platform_files)} platforms.")

if __name__ == "__main__":
    import os
    os.chdir(Path(__file__).parent)
    migrate_angles()
    migrate_regions()
    migrate_platforms()
    print("Migration complete!")
