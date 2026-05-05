import json
import logging
import os
from pathlib import Path

import psycopg2.extras

from .db import get_conn, get_or_create_fighter, transaction

log = logging.getLogger(__name__)


def _la(obj, key=None):
    if obj is None:
        return 0, 0
    if key:
        obj = obj.get(key, {})
    if not isinstance(obj, dict):
        return 0, 0
    return int(obj.get("landed", 0)), int(obj.get("attempted", 0))


def _build_row(fight_id, round_num, fighter_id, stats):
    sig         = stats.get("sig_strikes", {})
    total       = stats.get("total_strikes", {})
    td          = stats.get("takedowns", {})
    detail      = stats.get("sig_strike_detail", {})
    by_target   = detail.get("by_target", {})
    by_position = detail.get("by_position", {})

    sl,  sa  = _la(sig)
    tl,  ta  = _la(total)
    tdl, tda = _la(td)
    hl,  ha  = _la(by_target, "head")
    bl,  ba  = _la(by_target, "body")
    ll,  la_ = _la(by_target, "leg")
    dl,  da  = _la(by_position, "distance")
    cl,  ca  = _la(by_position, "clinch")
    gl,  ga  = _la(by_position, "ground")

    return {
        "fight_id": fight_id, "round_num": round_num, "fighter_id": fighter_id,
        "knockdowns": int(stats.get("knockdowns", 0)),
        "sig_strikes_landed": sl, "sig_strikes_attempted": sa,
        "total_strikes_landed": tl, "total_strikes_attempted": ta,
        "takedowns_landed": tdl, "takedowns_attempted": tda,
        "submission_attempts": int(stats.get("submission_attempts", 0)),
        "reversals": int(stats.get("reversals", 0)),
        "control_time_sec": int(stats.get("control_time_sec", 0)),
        "head_landed": hl, "head_attempted": ha,
        "body_landed": bl, "body_attempted": ba,
        "leg_landed": ll,  "leg_attempted": la_,
        "distance_landed": dl, "distance_attempted": da,
        "clinch_landed": cl,   "clinch_attempted": ca,
        "ground_landed": gl,   "ground_attempted": ga,
    }


def load_fight_file(conn, path: Path) -> tuple[int, int]:
    data     = json.loads(path.read_text(encoding="utf-8"))
    fight_id = data.get("fight_id")
    if not fight_id:
        return 0, 0

    rounds   = data.get("rounds", [])
    fighters = data.get("fighters", [])
    rows     = []

    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM fact_fight WHERE fight_id = %s", (fight_id,))
        if not cur.fetchone():
            return 0, len(rounds)

        for rnd in rounds:
            round_num = rnd.get("round", 0)
            for f_idx, f_stats in enumerate(rnd.get("fighters", [])):
                name = f_stats.get("fighter") or (fighters[f_idx] if f_idx < len(fighters) else None)
                if not name:
                    continue
                fighter_id = get_or_create_fighter(cur, name)
                rows.append(_build_row(fight_id, round_num, fighter_id, f_stats))

    if not rows:
        return 0, 0

    cols = list(rows[0].keys())
    sql  = f"INSERT INTO fact_fight_round ({', '.join(cols)}) VALUES %s ON CONFLICT (fight_id, round_num, fighter_id) DO NOTHING"

    with transaction(conn):
        with conn.cursor() as cur:
            psycopg2.extras.execute_values(cur, sql, [[r[c] for c in cols] for r in rows])
            return cur.rowcount, 0


def load_all_rounds(raw_data_path: str | None = None) -> dict:
    fights_dir = Path(raw_data_path or os.getenv("RAW_DATA_PATH", "./data/raw")) / "fights"
    files = sorted(fights_dir.rglob("*.json"))
    if not files:
        log.warning(f"No fight JSON files found under {fights_dir}.")
        return {"fight_files": 0, "round_rows_inserted": 0}

    log.info(f"Loading round stats from {len(files)} fight file(s).")
    conn = get_conn()
    total_inserted = 0

    for f in files:
        inserted, _ = load_fight_file(conn, f)
        total_inserted += inserted

    conn.close()
    return {"fight_files": len(files), "round_rows_inserted": total_inserted}
