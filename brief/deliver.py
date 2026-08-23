"""
Delivery to Telegram.

Sends one header message, then one message per bucket (kept under Telegram's
4096-char cap with headroom). Priority-2 buckets get trimmed to the top 5
items (by impact) if they run long, so a heavy news day doesn't bury you.
"""
import datetime as dt
import html

import requests

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
CHAR_LIMIT = 3800
PRIORITY2_CAP = 5

IMPACT_EMOJI = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "⚪"}


def _esc(text):
    return html.escape(text or "", quote=False)


def _format_bucket(bucket_name, bucket_items, priority):
    shown = bucket_items
    trimmed = 0
    if priority == 2 and len(bucket_items) > PRIORITY2_CAP:
        shown = bucket_items[:PRIORITY2_CAP]
        trimmed = len(bucket_items) - PRIORITY2_CAP

    lines = [f"<b>{_esc(bucket_name)}</b>"]
    for it in shown:
        emoji = IMPACT_EMOJI.get(it.get("impact", "LOW"), "⚪")
        bullet = _esc(it.get("bullet", it.get("headline", "")))
        url = it.get("url", "")
        line = f"{emoji} {bullet}"
        if url:
            line += f'\n   <a href="{_esc(url)}">source</a>'
        also = it.get("also_covered_by") or []
        if also:
            line += f"\n   <i>also: {_esc(', '.join(also[:4]))}</i>"
        lines.append(line)

    if trimmed:
        lines.append(f"<i>...and {trimmed} more lower-priority item(s) not shown</i>")

    return "\n\n".join(lines)


def build_messages(run_label, window_start, window_end, buckets_ordered,
                    grouped_items, raw_total, dedup_total):
    """buckets_ordered: list of (bucket_name, priority) in feeds.yaml order.
    grouped_items: dict bucket_name -> list of summarised items."""
    header = (
        f"📊 <b>Tax &amp; Group Brief — {run_label}</b>\n"
        f"Window: {window_start} → {window_end}\n"
        f"{raw_total} item(s) found → {dedup_total} after dedup"
    )
    messages = [header]

    for bucket_name, priority in buckets_ordered:
        items = grouped_items.get(bucket_name, [])
        if not items:
            continue
        body = _format_bucket(bucket_name, items, priority)
        messages.extend(_chunk(body))

    if len(messages) == 1:
        messages.append("No new items in this window across any tracked topic.")

    return messages


def _chunk(text, limit=CHAR_LIMIT):
    if len(text) <= limit:
        return [text]
    parts, current = [], []
    length = 0
    for block in text.split("\n\n"):
        block_len = len(block) + 2
        if length + block_len > limit and current:
            parts.append("\n\n".join(current))
            current, length = [], 0
        current.append(block)
        length += block_len
    if current:
        parts.append("\n\n".join(current))
    return parts


def send_telegram(messages, token, chat_id):
    url = TELEGRAM_API.format(token=token)
    for msg in messages:
        resp = requests.post(url, json={
            "chat_id": chat_id,
            "text": msg,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }, timeout=30)
        if resp.status_code != 200:
            print(f"  [warn] Telegram send failed: {resp.status_code} {resp.text[:300]}")
        resp.raise_for_status()


def send_failure_alert(token, chat_id, error_text):
    url = TELEGRAM_API.format(token=token)
    msg = f"⚠️ Tax brief run failed:\n{error_text[:500]}"
    try:
        requests.post(url, json={"chat_id": chat_id, "text": msg}, timeout=30)
    except Exception as e:  # noqa: BLE001
        print(f"  [warn] could not even send failure alert: {e}")
