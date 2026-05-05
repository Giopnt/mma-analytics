#!/usr/bin/env python3
"""
MMA Pipeline scraper.

Run from project root (mma-analytics/):

    python -m ingestion.main --limit 5 --fights-only   # fast test
    python -m ingestion.main --limit 20                 # full with rounds
    python -m ingestion.main --no-minio                 # skip MinIO upload
    python -m ingestion.main --event <event_id>         # single event
"""

import argparse
import sys

from tqdm import tqdm

from .events import scrape_event_list
from .fights import scrape_event_fights
from .rounds import scrape_fight_rounds
from .utils  import make_session, save_json, load_json, event_path, fight_path, RAW_DIR, log


def get_minio():
    try:
        from .minio_client import get_client
        client = get_client()
        client.list_buckets()
        log.info("MinIO connected.")
        return client, True
    except Exception as e:
        log.warning(f"MinIO unavailable ({e}) — local files only.")
        return None, False


def scrape_all(limit=None, fights_only=False, single_event=None, use_minio=True):
    session = make_session()
    minio_client, minio_enabled = get_minio() if use_minio else (None, False)

    if single_event:
        from .events import EventStub
        events = [EventStub(
            event_id=single_event, name="(single event)",
            date="", location="",
            url=f"http://ufcstats.com/event-details/{single_event}",
        )]
    else:
        events = scrape_event_list(session)
        if limit:
            events = events[:limit]

    log.info(f"Processing {len(events)} event(s). fights_only={fights_only} minio={minio_enabled}")
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    events_written = fights_written = fights_skipped = 0

    for event in tqdm(events, desc="Events", unit="event"):
        e_path = event_path(event.event_id)
        cached  = load_json(e_path)

        if cached and cached.get("fight_count", 0) > 0:
            event_data = cached
        else:
            try:
                event_data = scrape_event_fights(session, event.event_id)
            except Exception as exc:
                log.error(f"  Failed: {event.event_id}: {exc}")
                continue

            if save_json(e_path, event_data):
                events_written += 1
                log.info(f"  Saved: {event_data['event_name']} ({event_data['fight_count']} fights)")

            if minio_enabled:
                from .minio_client import upload_json, event_key
                upload_json(minio_client, event_key(event.event_id), event_data)

        if fights_only:
            continue

        for fight in tqdm(
            event_data.get("fights", []),
            desc=f"  {event_data.get('event_name', event.event_id)[:30]}",
            unit="fight",
            leave=False,
        ):
            f_id   = fight["fight_id"]
            f_path = fight_path(event.event_id, f_id)

            if f_path.exists():
                fights_skipped += 1
                continue

            try:
                round_data = scrape_fight_rounds(session, f_id, fight["fighters"])
            except Exception as exc:
                log.error(f"    Failed fight {f_id}: {exc}")
                continue

            round_data["event_id"]     = event.event_id
            round_data["winner"]       = fight.get("winner", "")
            round_data["method"]       = fight.get("method", "")
            round_data["weight_class"] = fight.get("weight_class", "")

            if save_json(f_path, round_data):
                fights_written += 1

            if minio_enabled:
                from .minio_client import upload_json, fight_key
                upload_json(minio_client, fight_key(event.event_id, f_id), round_data)

    log.info("─" * 50)
    log.info(f"Done. Events: {events_written}  Fights: {fights_written}  Skipped: {fights_skipped}")
    if minio_enabled:
        log.info("Uploaded to MinIO bucket: mma-raw")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit",       type=int, default=None)
    parser.add_argument("--fights-only", action="store_true")
    parser.add_argument("--event",       type=str, default=None)
    parser.add_argument("--no-minio",    action="store_true")
    args = parser.parse_args()

    try:
        scrape_all(
            limit=args.limit,
            fights_only=args.fights_only,
            single_event=args.event,
            use_minio=not args.no_minio,
        )
    except KeyboardInterrupt:
        log.info("Interrupted.")
        sys.exit(0)


if __name__ == "__main__":
    main()
