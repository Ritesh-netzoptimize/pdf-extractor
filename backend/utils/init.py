import os
import json
from typing import Dict

CONFIG_DIR = r"C:\PDFs"
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")

def ensure_config_dir():
    os.makedirs(CONFIG_DIR, exist_ok=True)


def read_config() -> Dict:
    ensure_config_dir()
    if not os.path.exists(CONFIG_PATH):
        # Default config
        config = {"team_member_id": "TM-001"}
        write_config(config)
        return config
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def write_config(config: Dict):
    ensure_config_dir()
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
