"""
Shared config and state helpers.

state.json keeps two things across runs:
  - "watermark": ISO timestamp of the last successful run. We only pull news
    published AFTER this. This makes the system self-healing: if a run fails
    or GitHub Actions is late, the next run just pulls the wider gap. No
    hardcoded "9am to 9pm" windows anywhere.
  - "seen": a rolling ~7-day record of article fingerprints we've already
    sent, so the same story doesn't get repeated across runs.
"""
import json
import os
import datetime as dt
import yaml

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FEEDS_PATH = os.path.join(REPO_ROOT, "feeds.yaml")
STATE_PATH = os.path.join(REPO_ROOT, "state.json")

SEEN_RETENTION_DAYS = 7


def load_feeds():
    with open(FEEDS_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_state():
    if not os.path.exists(STATE_PATH):
        return {"watermark": None, "seen": {}}
    with open(STATE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("watermark", None)
    data.setdefault("seen", {})
    return data


def save_state(state):
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False, default=str)


def get_watermark(state, fallback_hours):
    """Return a timezone-aware UTC datetime to use as the cutoff."""
    if state.get("watermark"):
        try:
            return dt.datetime.fromisoformat(state["watermark"])
        except ValueError:
            pass
    return dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=fallback_hours)


def prune_seen(state, now=None):
    """Drop fingerprints older than SEEN_RETENTION_DAYS so state.json stays small."""
    now = now or dt.datetime.now(dt.timezone.utc)
    cutoff = now - dt.timedelta(days=SEEN_RETENTION_DAYS)
    kept = {}
    for fp, ts in state.get("seen", {}).items():
        try:
            if dt.datetime.fromisoformat(ts) > cutoff:
                kept[fp] = ts
        except ValueError:
            continue
    state["seen"] = kept
