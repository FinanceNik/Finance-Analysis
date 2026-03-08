import json
import os

SETTINGS_FILE = "data/user_settings.json"


def load() -> dict:
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE) as f:
            return json.load(f)
    return {}


def save(settings: dict):
    current = load()
    current.update(settings)
    with open(SETTINGS_FILE, "w") as f:
        json.dump(current, f, indent=2)


def get(key: str, default=None):
    return load().get(key, default)
