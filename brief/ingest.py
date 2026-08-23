"""
Ingestion: turns feeds.yaml into a flat list of fresh news items.

Two source types per bucket:
  - "queries": plain-English search phrases, auto-converted into Google News
    RSS search URLs (no API key needed).
  - "rss": any RSS feed URL you paste directly (publisher feeds, OECD, etc).

Only items published after the watermark are kept. Items containing a
"noise_terms" word (case-insensitive) are dropped outright.
"""
import datetime as dt
import re
import urllib.parse
import html as htmllib

import feedparser
from dateutil import parser as dateparser

GOOGLE_NEWS_BASE = "https://news.google.com/rss/search"


def build_google_news_url(query, lang="en-IN", country="IN"):
    q = urllib.parse.quote(query)
    return f"{GOOGLE_NEWS_BASE}?q={q}&hl={lang}&gl={country}&ceid={country}:{lang.split('-')[0]}"


def strip_html(text):
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = htmllib.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def parse_pubdate(entry):
    for key in ("published", "updated"):
        val = entry.get(key)
        if val:
            try:
                d = dateparser.parse(val)
                if d.tzinfo is None:
                    d = d.replace(tzinfo=dt.timezone.utc)
                return d.astimezone(dt.timezone.utc)
            except (ValueError, TypeError):
                continue
    return None


def contains_noise(text, noise_terms):
    low = text.lower()
    return any(term.lower() in low for term in noise_terms)


def fetch_feed(url, timeout=20):
    try:
        return feedparser.parse(url)
    except Exception as e:  # noqa: BLE001 - a single bad feed must not kill the run
        print(f"  [warn] failed to fetch {url}: {e}")
        return None


def collect_items(feeds_cfg, watermark, verbose=True):
    """Returns a list of dicts: bucket, priority, title, link, summary,
    source, published (ISO string)."""
    noise_terms = feeds_cfg.get("noise_terms", [])
    items = []

    for bucket in feeds_cfg.get("buckets", []):
        bucket_name = bucket["name"]
        priority = bucket.get("priority", 2)
        urls = []

        for q in bucket.get("queries", []) or []:
            urls.append(build_google_news_url(q))
        for u in bucket.get("rss", []) or []:
            urls.append(u)

        bucket_count = 0
        for url in urls:
            feed = fetch_feed(url)
            if not feed or not getattr(feed, "entries", None):
                continue
            for entry in feed.entries:
                pub = parse_pubdate(entry)
                if pub is None or pub <= watermark:
                    continue
                title = strip_html(entry.get("title", "")).strip()
                summary = strip_html(entry.get("summary", entry.get("description", "")))
                link = entry.get("link", "")
                if not title or not link:
                    continue
                if contains_noise(f"{title} {summary}", noise_terms):
                    continue
                source = ""
                if isinstance(entry.get("source"), dict):
                    source = entry["source"].get("title", "")
                elif hasattr(entry, "source"):
                    source = getattr(entry.source, "title", "")

                items.append({
                    "bucket": bucket_name,
                    "priority": priority,
                    "title": title,
                    "summary": summary,
                    "link": link,
                    "source": source,
                    "published": pub.isoformat(),
                })
                bucket_count += 1

        if verbose:
            print(f"  [{bucket_name}] {bucket_count} new item(s)")

    return items
