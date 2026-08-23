"""
Orchestrator. Run with: python -m brief.run

Pipeline: load feeds/state -> ingest -> dedupe -> summarise per bucket
          -> deliver to Telegram -> save new watermark + seen fingerprints.

On any unhandled error, tries to send a short failure alert to Telegram
(if credentials are available) before re-raising, so a broken run is never
silent.
"""
import datetime as dt
import os
import sys

from brief import config, ingest, dedupe, summarise, deliver


def main():
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    tg_token = os.environ.get("TELEGRAM_TOKEN", "")
    tg_chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")

    if not tg_token or not tg_chat_id:
        print("FATAL: TELEGRAM_TOKEN / TELEGRAM_CHAT_ID not set.")
        sys.exit(1)

    try:
        feeds_cfg = config.load_feeds()
        state = config.load_state()
        now = dt.datetime.now(dt.timezone.utc)
        watermark = config.get_watermark(
            state, feeds_cfg.get("lookback_hours_fallback", 14)
        )

        print(f"Window: {watermark.isoformat()} -> {now.isoformat()}")
        print("Fetching feeds...")
        raw_items = ingest.collect_items(feeds_cfg, watermark)
        print(f"Total raw items: {len(raw_items)}")

        print("Deduplicating...")
        deduped, new_fps = dedupe.dedupe(raw_items, set(state["seen"].keys()))
        print(f"After dedup: {len(deduped)}")

        grouped = {}
        for it in deduped:
            grouped.setdefault(it["bucket"], []).append(it)

        buckets_ordered = [(b["name"], b.get("priority", 2))
                            for b in feeds_cfg.get("buckets", [])]

        print("Summarising per bucket...")
        summarised = {}
        for bucket_name, _priority in buckets_ordered:
            bucket_items = grouped.get(bucket_name, [])
            if not bucket_items:
                continue
            print(f"  [{bucket_name}] summarising {len(bucket_items)} item(s)")
            summarised[bucket_name] = summarise.summarise_bucket(
                bucket_name, bucket_items, gemini_key
            )

        run_label = now.strftime("%d %b %Y, %H:%M IST")
        # Note: GitHub Actions runners use UTC; label says what it is
        run_label = now.astimezone(dt.timezone.utc).strftime("%d %b %Y, %H:%M UTC")

        messages = deliver.build_messages(
            run_label=run_label,
            window_start=watermark.strftime("%d %b %H:%M UTC"),
            window_end=now.strftime("%d %b %H:%M UTC"),
            buckets_ordered=buckets_ordered,
            grouped_items=summarised,
            raw_total=len(raw_items),
            dedup_total=len(deduped),
        )

        print(f"Sending {len(messages)} Telegram message(s)...")
        deliver.send_telegram(messages, tg_token, tg_chat_id)

        # Only advance the watermark and persist state AFTER a successful send,
        # so a delivery failure doesn't silently drop this window's news.
        state["watermark"] = now.isoformat()
        for fp in new_fps:
            state["seen"][fp] = now.isoformat()
        config.prune_seen(state, now)
        config.save_state(state)
        print("Done.")

    except Exception as e:  # noqa: BLE001
        print(f"FATAL: {e}")
        if tg_token and tg_chat_id:
            deliver.send_failure_alert(tg_token, tg_chat_id, str(e))
        raise


if __name__ == "__main__":
    main()
