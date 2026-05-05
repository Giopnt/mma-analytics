import json
import logging
import os
from datetime import datetime
from pathlib import Path

from .db import get_conn, get_or_create_fighter, get_or_create_method, transaction

log = logging.getLogger(__name__)


def _parse_date(raw: str) -> str | None:
    if not raw:
        return None
    for fmt in ("%B %d, %Y", "%Y-%m-%d", "%b %d, %Y"):
        try:
            return datetime.strptime(raw.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def load_event_file(conn, path: Path) -> tuple[int, int]:
    data = json.loads(path.read_text(encoding="utf-8"))
    loaded = skipped = 0

    with transaction(conn):
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO dim_event (event_id, event_name, event_date, location) VALUES (%s, %s, %s, %s) ON CONFLICT (event_id) DO NOTHING",
                (data["event_id"], data.get("event_name", ""), _parse_date(data.get("date", "")), data.get("location", "")),
            )

            for fight in data.get("fights", []):
                fighters = fight.get("fighters", [])
                if len(fighters) < 2:
                    skipped += 1
                    continue

                fighter_a_id = get_or_create_fighter(cur, fighters[0])
                fighter_b_id = get_or_create_fighter(cur, fighters[1])
                winner       = fight.get("winner", "")
                winner_id    = get_or_create_fighter(cur, winner) if winner else None
                method_id    = get_or_create_method(cur, fight.get("method", ""), fight.get("method_detail", ""))

                cur.execute(
                    "INSERT INTO fact_fight (fight_id, event_id, fighter_a_id, fighter_b_id, winner_id, method_id, weight_class, round_stopped, time_stopped, result, is_title_fight, is_main_event) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (fight_id) DO NOTHING",
                    (fight["fight_id"], data["event_id"], fighter_a_id, fighter_b_id, winner_id, method_id,
                     fight.get("weight_class", ""), fight.get("round_stopped") or None, fight.get("time", ""),
                     fight.get("result", ""), fight.get("is_title_fight", False), fight.get("is_main_event", False)),
                )
                loaded += 1

    return loaded, skipped


def load_all_events(raw_data_path: str | None = None) -> dict:
    events_dir = Path(raw_data_path or os.getenv("RAW_DATA_PATH", "./data/raw")) / "events"
    files = sorted(events_dir.glob("*.json"))
    if not files:
        raise FileNotFoundError(f"No event JSON files found in {events_dir}")

    log.info(f"Loading {len(files)} event file(s)")
    conn = get_conn()
    total_events = total_fights = total_skipped = 0

    for f in files:
        loaded, skipped = load_event_file(conn, f)
        total_events  += 1
        total_fights  += loaded
        total_skipped += skipped
        log.info(f"  {f.stem[:40]}: {loaded} fights loaded")

    conn.close()
    return {"events_processed": total_events, "fights_loaded": total_fights, "fights_skipped": total_skipped}
