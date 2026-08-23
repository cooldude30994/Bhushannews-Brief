"""
Summarisation via the Gemini API free tier (no billing account needed).

One call per bucket (not per article) to stay well inside free-tier rate
limits — a typical run makes 5-8 calls total, twice a day.

If the API call fails (rate-limited, network error, bad JSON back), we don't
crash the whole run — we fall back to a plain bullet list built directly from
the RSS titles, so the user still gets *something* at 9am/9pm.
"""
import json
import os
import re
import time

import requests

MODEL = "gemini-2.5-flash"
API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"{MODEL}:generateContent"
)
PROMPT_PATH = os.path.join(os.path.dirname(__file__), "prompts", "digest.txt")

MAX_RETRIES = 4
BACKOFF_BASE = 2  # seconds: 2, 4, 8, 16


def _load_prompt_template():
    with open(PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read()


def _strip_code_fences(text):
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    return text


def _call_gemini(prompt, api_key):
    headers = {"Content-Type": "application/json"}
    params = {"key": api_key}
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json",
        },
    }
    for attempt in range(MAX_RETRIES):
        resp = requests.post(API_URL, headers=headers, params=params,
                              json=body, timeout=60)
        if resp.status_code == 200:
            data = resp.json()
            try:
                text = data["candidates"][0]["content"]["parts"][0]["text"]
            except (KeyError, IndexError):
                raise RuntimeError(f"Unexpected Gemini response shape: {data}")
            return _strip_code_fences(text)
        if resp.status_code == 429:
            wait = BACKOFF_BASE ** (attempt + 1)
            print(f"    [warn] Gemini 429, backing off {wait}s (attempt {attempt+1})")
            time.sleep(wait)
            continue
        resp.raise_for_status()
    raise RuntimeError("Gemini API: exhausted retries on 429")


def _fallback_bullets(items):
    """No-AI fallback: raw titles, impact defaulted to MEDIUM."""
    out = []
    for it in items:
        out.append({
            "headline": it["title"][:80],
            "bullet": it["title"],
            "impact": "MEDIUM",
            "url": it["link"],
        })
    return out


def summarise_bucket(bucket_name, items, api_key):
    """items: list of dicts with title/summary/link/source/also_covered_by.
    Returns list of {headline, bullet, impact, url, also_covered_by}."""
    if not items:
        return []

    if not api_key:
        print("    [warn] no GEMINI_API_KEY set, using fallback bullets")
        result = _fallback_bullets(items)
    else:
        payload = [
            {"title": it["title"], "summary": it["summary"][:400],
             "url": it["link"], "source": it.get("source", "")}
            for it in items
        ]
        template = _load_prompt_template()
        prompt = template.format(
            bucket_name=bucket_name,
            items_json=json.dumps(payload, ensure_ascii=False, indent=2),
        )
        try:
            raw = _call_gemini(prompt, api_key)
            parsed = json.loads(raw)
            result = parsed.get("items", [])
            if not result:
                raise ValueError("empty items from model")
        except Exception as e:  # noqa: BLE001
            print(f"    [warn] Gemini summarisation failed ({e}); using fallback")
            result = _fallback_bullets(items)

    # Re-attach also_covered_by by matching on URL
    by_url = {it["link"]: it.get("also_covered_by", []) for it in items}
    for r in result:
        r["also_covered_by"] = by_url.get(r.get("url", ""), [])

    impact_rank = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    result.sort(key=lambda r: impact_rank.get(r.get("impact", "LOW"), 3))
    return result
