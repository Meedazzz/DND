from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from .models import Campaign, starter_campaign


APP_DIR = Path(os.environ.get("DRAGON_SAGA_HOME", Path.home() / ".dragon-saga"))
DEFAULT_SAVE = APP_DIR / "campaign.json"


def save_campaign(campaign: Campaign, path: str | Path = DEFAULT_SAVE) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(campaign.to_dict(), ensure_ascii=False, indent=2)
    fd, temporary = tempfile.mkstemp(prefix="dragon-saga-", suffix=".tmp", dir=destination.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return destination


def load_campaign(path: str | Path = DEFAULT_SAVE) -> Campaign:
    source = Path(path)
    if not source.exists():
        return starter_campaign()
    with source.open("r", encoding="utf-8") as handle:
        return Campaign.from_dict(json.load(handle))


def export_campaign(campaign: Campaign, path: str | Path) -> Path:
    return save_campaign(campaign, path)
